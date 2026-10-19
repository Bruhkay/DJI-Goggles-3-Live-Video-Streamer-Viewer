"""Test doubles. FakeGoggles/FakeTransport live in g3.sim (also used by demo mode)."""
from g3 import netstack as ns
from g3 import rndis
from g3.sim import FakeGoggles, FakeTransport  # noqa: F401

GOGGLES_MAC = bytes.fromhex("ca3cb48d51c3")


class FakeRndisLink(object):
    """Pretends to be the goggles at the USB/RNDIS level (Ethernet + ARP + IPv4 + UDP)."""

    def __init__(self, goggles):
        self.g = goggles
        self.pending = []

    def send_frame(self, eth):
        frames = rndis.unwrap_packets(rndis.wrap_packet(eth))
        assert frames == [eth]
        info = ns.parse_frame(eth)
        if isinstance(info, ns.ArpInfo) and info.op == ns.ARP_REQUEST and info.target_ip == ns.GOGGLES_IP:
            arp = bytearray(ns.build_arp_reply(info.sender_mac, info.sender_ip))
            arp[0:6] = ns.HOST_MAC
            arp[6:12] = GOGGLES_MAC
            arp[14 + 8:14 + 14] = GOGGLES_MAC
            arp[14 + 14:14 + 18] = ns.GOGGLES_IP
            arp[14 + 18:14 + 24] = ns.HOST_MAC
            arp[14 + 24:14 + 28] = ns.HOST_IP
            self.pending.append(bytes(arp))
        elif isinstance(info, ns.UdpInfo) and info.dst_port == ns.GOGGLES_PORT:
            assert eth[0:6] == GOGGLES_MAC
            self.g.on_payload(info.payload)

    def read_frames(self, timeout_ms=100):
        out, self.pending = self.pending, []
        for pkt in self.g.next_packets():
            frame = ns.build_udp(ns.HOST_MAC, pkt, src_port=ns.GOGGLES_PORT, dst_port=ns.HOST_PORT,
                                 src_ip=ns.GOGGLES_IP, dst_ip=ns.HOST_IP)
            out.append(frame[:6] + GOGGLES_MAC + frame[12:])
        blob = b"".join(rndis.wrap_packet(f) for f in out)
        return rndis.unwrap_packets(blob)

    def release(self):
        pass
