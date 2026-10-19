"""Goggles 3 live-view wire protocol (UDP port 9003).

Reimplemented from the protocol notes published in the gogglecast project
(docs/design.md, section 3.3). All constants were observed on real hardware
by that project; a goggles firmware update may change them.
"""
import random
import struct
import time

T_HANDSHAKE = 0x00
T_TELEMETRY = 0x01
T_VIDEO = 0x02
T_ACK = 0x04

HANDSHAKE_BODY = bytes.fromhex(
    "d0 e9 64 00 64 00 c0 05 14 00 00 0a 00 64 00 64"
    "00 c0 05 14 00 00 64 00 14 00 64 00 c0 05 14 00"
    "00 64 00 01 01 04 0a 02".replace(" ", ""))
ACK_TAIL = bytes.fromhex("0000d0e9d0e90000d0e9d8e9000000000000")

assert len(HANDSHAKE_BODY) == 40
assert len(ACK_TAIL) == 18


def build_outer(session_id, seq, ptype, body=b""):
    head = struct.pack("<HHHB", (8 + len(body)) | 0x8000, session_id & 0xFFFF, seq & 0xFFFF, ptype)
    x = 0
    for b in head:
        x ^= b
    return head + bytes([x]) + body


def parse_outer(pkt):
    """Return (seq, type) or None."""
    if len(pkt) < 8:
        return None
    _, _, seq, ptype = struct.unpack_from("<HHHB", pkt)
    return seq, ptype


def parse_video(pkt):
    """Return (frame_no, frag_index, frag_count, data) for a type-0x02 packet."""
    if len(pkt) < 20:
        return None
    b17, b18 = pkt[17], pkt[18]
    count = b17 & 0x7F
    index = ((b18 & 0x1F) << 1) | (b17 >> 7)
    return pkt[16], index, count, pkt[20:]


def build_video(session_id, seq, frame_no, index, count, data):
    """Inverse of parse_video. Only used by tests / the simulator."""
    sub = bytes(8) + bytes([frame_no & 0xFF, ((index & 1) << 7) | (count & 0x7F), (index >> 1) & 0x1F, 0])
    return build_outer(session_id, seq, T_VIDEO, sub + data)


class Session(object):
    def __init__(self):
        self.session_id = random.randint(1, 0xFFFE)   # must be fresh per connection
        self.seq = random.randint(0, 0xFFFF)

    def _next(self):
        self.seq = (self.seq + 1) & 0xFFFF
        return self.seq

    def handshake(self):
        return build_outer(self.session_id, self._next(), T_HANDSHAKE, HANDSHAKE_BODY)

    def ack(self, start_seq, end_seq):
        body = struct.pack("<HH", start_seq & 0xFFFF, end_seq & 0xFFFF) + ACK_TAIL
        return build_outer(self.session_id, self._next(), T_ACK, body)


class Reassembler(object):
    """Collects video fragments into whole frames.

    Frames are keyed by an 8-bit frame number. Incomplete frames that fall
    too far behind (or get too old) are dropped instead of being merged with
    a later frame that reuses the same number.
    """

    def __init__(self, max_lag=5, max_age=0.25):
        self.max_lag = max_lag
        self.max_age = max_age
        self.frames = {}
        self.dropped = 0
        self.completed = 0

    def add(self, seq, frame_no, index, count, data, now=None):
        now = time.monotonic() if now is None else now
        out = []
        if count == 0 or index >= count:
            return out
        self._evict(frame_no, now)
        f = self.frames.get(frame_no)
        if f is None or f["count"] != count:
            f = {"count": count, "parts": {}, "seqs": {}, "t": now}
            self.frames[frame_no] = f
        f["parts"][index] = data
        f["seqs"][index] = seq
        if len(f["parts"]) == count:
            del self.frames[frame_no]
            payload = b"".join(f["parts"][i] for i in range(count))
            out.append((payload, f["seqs"][0], f["seqs"][count - 1]))
            self.completed += 1
        return out

    def _evict(self, newest, now):
        for k in list(self.frames):
            lag = (newest - k) & 0xFF
            if (0 < lag < 128 and lag > self.max_lag) or now - self.frames[k]["t"] > self.max_age:
                del self.frames[k]
                self.dropped += 1


# ---------------------------------------------------------------- H.264 helpers

START = b"\x00\x00\x00\x01"


def ensure_start_code(data):
    if data.startswith(START) or data.startswith(b"\x00\x00\x01"):
        return data
    return START + data


def split_nals(data):
    """Split an Annex-B buffer into NAL payloads (without start codes)."""
    nals, i, n = [], 0, len(data)
    starts = []
    while True:
        j = data.find(b"\x00\x00\x01", i)
        if j < 0:
            break
        starts.append(j + 3)
        i = j + 3
    if not starts:
        return [data] if data else []
    for k, s in enumerate(starts):
        e = starts[k + 1] - 3 if k + 1 < len(starts) else n
        nal = data[s:e]
        while k + 1 < len(starts) and nal.endswith(b"\x00"):
            nal = nal[:-1]   # trailing zero of a 4-byte start code
        if nal:
            nals.append(nal)
    return nals


def nal_types(data):
    return [nal[0] & 0x1F for nal in split_nals(ensure_start_code(data))]


class KeyframeGate(object):
    """Hold output back until a decoder can actually start (SPS + PPS + IDR)."""

    def __init__(self):
        self.params = None      # last parameter-set blob (SPS/PPS)
        self.open = False

    def push(self, unit):
        unit = ensure_start_code(unit)
        types = nal_types(unit)
        if self.open:
            if 7 in types:
                self.params = unit
            return [unit]
        if 7 in types and 8 in types:
            self.params = unit
            if 5 in types:
                self.open = True
                return [unit]
            return []
        if 5 in types and self.params is not None:
            self.open = True
            return [self.params, unit]
        return []
