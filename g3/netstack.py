"""Minimal Ethernet / ARP / IPv4 / UDP builder and parser.

The goggles expose a USB network link (RNDIS). When we drive that link
ourselves from userspace there is no operating-system network stack in the
middle, so we build and parse the frames by hand. Only what the goggles
protocol needs is implemented.
"""
import struct
import time

HOST_MAC = bytes.fromhex("020000000001")      # synthetic, locally administered
BROADCAST_MAC = b"\xff" * 6
HOST_IP = bytes([192, 168, 60, 1])
GOGGLES_IP = bytes([192, 168, 60, 2])
HOST_PORT = 54321
GOGGLES_PORT = 9003

ETH_IPV4 = 0x0800
ETH_ARP = 0x0806
ARP_REQUEST = 1
ARP_REPLY = 2


def ip_str(b):
    return ".".join(str(x) for x in b)


def mac_str(b):
    return ":".join("%02x" % x for x in b)


def ip_checksum(header):
    if len(header) % 2:
        header += b"\x00"
    total = sum(struct.unpack("!%dH" % (len(header) // 2), header))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def _eth(dst, src, ethertype, payload):
    return dst + src + struct.pack("!H", ethertype) + payload


def _arp(op, sha, spa, tha, tpa):
    return struct.pack("!HHBBH", 1, ETH_IPV4, 6, 4, op) + sha + spa + tha + tpa


def build_arp_request(target_ip=GOGGLES_IP):
    return _eth(BROADCAST_MAC, HOST_MAC, ETH_ARP,
                _arp(ARP_REQUEST, HOST_MAC, HOST_IP, b"\x00" * 6, target_ip))


def build_arp_reply(dst_mac, dst_ip):
    return _eth(dst_mac, HOST_MAC, ETH_ARP,
                _arp(ARP_REPLY, HOST_MAC, HOST_IP, dst_mac, dst_ip))


_ip_id = [0]


def build_udp(dst_mac, payload, src_port=HOST_PORT, dst_port=GOGGLES_PORT,
              src_ip=HOST_IP, dst_ip=GOGGLES_IP):
    # UDP checksum 0 = "not computed", allowed for IPv4 (the goggles accept it).
    udp = struct.pack("!HHHH", src_port, dst_port, 8 + len(payload), 0) + payload
    _ip_id[0] = (_ip_id[0] + 1) & 0xFFFF
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), _ip_id[0],
                      0x4000, 64, 17, 0, src_ip, dst_ip)
    hdr = hdr[:10] + struct.pack("!H", ip_checksum(hdr)) + hdr[12:]
    return _eth(dst_mac, HOST_MAC, ETH_IPV4, hdr + udp)


class ArpInfo(object):
    __slots__ = ("op", "sender_mac", "sender_ip", "target_ip")

    def __init__(self, op, sender_mac, sender_ip, target_ip):
        self.op, self.sender_mac, self.sender_ip, self.target_ip = op, sender_mac, sender_ip, target_ip


class UdpInfo(object):
    __slots__ = ("src_mac", "src_ip", "src_port", "dst_port", "payload")

    def __init__(self, src_mac, src_ip, src_port, dst_port, payload):
        self.src_mac, self.src_ip, self.src_port, self.dst_port, self.payload = (
            src_mac, src_ip, src_port, dst_port, payload)


class IpDefragmenter(object):
    """Reassembles fragmented IPv4 datagrams (in case big video packets get split)."""

    def __init__(self, max_age=0.5):
        self.max_age = max_age
        self.pending = {}

    def push(self, src, ident, offset, more, data):
        now = time.monotonic()
        for k in [k for k, v in self.pending.items() if now - v["t"] > self.max_age]:
            del self.pending[k]
        key = (src, ident)
        entry = self.pending.setdefault(key, {"t": now, "parts": {}, "total": None})
        entry["parts"][offset] = data
        if not more:
            entry["total"] = offset + len(data)
        if entry["total"] is None:
            return None
        buf, pos = [], 0
        for off in sorted(entry["parts"]):
            if off != pos:
                return None
            buf.append(entry["parts"][off])
            pos += len(entry["parts"][off])
        if pos != entry["total"]:
            return None
        del self.pending[key]
        return b"".join(buf)


def parse_frame(frame, defrag=None):
    """Return ArpInfo, UdpInfo or None for one Ethernet frame."""
    if len(frame) < 14:
        return None
    src_mac = frame[6:12]
    ethertype = struct.unpack_from("!H", frame, 12)[0]
    body = frame[14:]
    if ethertype == ETH_ARP and len(body) >= 28:
        op = struct.unpack_from("!H", body, 6)[0]
        return ArpInfo(op, body[8:14], body[14:18], body[24:28])
    if ethertype != ETH_IPV4 or len(body) < 20 or (body[0] >> 4) != 4:
        return None
    ihl = (body[0] & 0x0F) * 4
    total_len = struct.unpack_from("!H", body, 2)[0]
    ident = struct.unpack_from("!H", body, 4)[0]
    flags_frag = struct.unpack_from("!H", body, 6)[0]
    proto = body[9]
    src_ip = body[12:16]
    if proto != 17:
        return None
    data = body[ihl:total_len] if total_len >= ihl else body[ihl:]
    more = bool(flags_frag & 0x2000)
    offset = (flags_frag & 0x1FFF) * 8
    if more or offset:
        if defrag is None:
            return None
        data = defrag.push(bytes(src_ip), ident, offset, more, bytes(data))
        if data is None:
            return None
    if len(data) < 8:
        return None
    sport, dport, ulen = struct.unpack_from("!HHH", data, 0)
    payload = data[8:ulen] if 8 <= ulen <= len(data) else data[8:]
    return UdpInfo(src_mac, src_ip, sport, dport, bytes(payload))
