"""Software stand-in for DJI Goggles 3 (tests and demo mode).

Speaks the observed wire protocol: handshake on UDP 9003, then fragmented
H.264 with SPS+PPS bundled into one blob, acks expected per frame.
"""
import os
import random
import struct
import time

from . import protocol as p


def nal_units(h264):
    return [p.START + n for n in p.split_nals(h264)]


class FakeGoggles(object):
    def __init__(self, h264, frag_size=1400, loss=0.0, reorder=False, params_separate=True, seed=1,
                 loop=False):
        units = nal_units(h264)
        if params_separate:
            merged, blob = [], b""
            for u in units:
                t = u[4] & 0x1F
                if t in (7, 8):
                    blob += u
                    continue
                if blob:
                    merged.append(blob)
                    blob = b""
                merged.append(u)
            units = merged
        self.units = units
        self.frag_size = frag_size
        self.loss = loss
        self.reorder = reorder
        self.loop = loop
        self.rng = random.Random(seed)
        self.seq = 0
        self.frame_no = 0
        self.streaming = False
        self.session = None
        self.acks = []
        self.handshakes = 0
        self.pos = 0

    def on_payload(self, payload):
        seq, ptype = p.parse_outer(payload)
        x = 0
        for b in payload[:7]:
            x ^= b
        assert payload[7] == x, "bad header checksum"
        if ptype == p.T_HANDSHAKE:
            assert payload[8:] == p.HANDSHAKE_BODY
            self.session = struct.unpack_from("<H", payload, 2)[0]
            self.handshakes += 1
            self.streaming = True
        elif ptype == p.T_ACK:
            assert payload[12:] == p.ACK_TAIL
            self.acks.append(struct.unpack_from("<HH", payload, 8))

    def next_packets(self, n_units=4):
        out = []
        if not self.streaming:
            return out
        for _ in range(n_units):
            if self.pos >= len(self.units):
                if not self.loop:
                    break
                self.pos = 0
            unit = self.units[self.pos]
            self.pos += 1
            body = unit[4:] if self.rng.random() < 0.5 else unit
            chunks = [body[i:i + self.frag_size] for i in range(0, len(body), self.frag_size)] or [b""]
            pkts = []
            for idx, c in enumerate(chunks):
                self.seq = (self.seq + 1) & 0xFFFF
                pkts.append(p.build_video(self.session, self.seq, self.frame_no, idx, len(chunks), c))
            self.frame_no = (self.frame_no + 1) & 0xFF
            if self.reorder and len(pkts) > 2:
                pkts[0], pkts[1] = pkts[1], pkts[0]
            out += [x for x in pkts if self.rng.random() >= self.loss]
        return out

    def done(self):
        return not self.loop and self.pos >= len(self.units)


class FakeTransport(object):
    """Talks to FakeGoggles at the UDP-payload level, as fast as asked."""
    name = "fake"
    description = "simulated goggles"

    def __init__(self, goggles):
        self.g = goggles

    def start(self):
        pass

    def close(self):
        pass

    def send(self, payload):
        self.g.on_payload(payload)

    def recv(self, timeout):
        return self.g.next_packets()


class RealtimeSimTransport(FakeTransport):
    """Plays an .h264 file in a loop at roughly real-time speed (demo mode)."""
    description = "demo (simulated goggles)"

    def __init__(self, h264_path, fps=56.0):
        with open(h264_path, "rb") as f:
            super(RealtimeSimTransport, self).__init__(FakeGoggles(f.read(), loop=True))
        self.period = 1.0 / fps
        self.next_t = time.monotonic()

    def recv(self, timeout):
        now = time.monotonic()
        if now < self.next_t:
            time.sleep(min(timeout, self.next_t - now))
            if time.monotonic() < self.next_t:
                return []
        self.next_t = max(self.next_t + self.period, time.monotonic() - 0.1)
        extra = []
        if os.environ.get("G3_SIM_TELEMETRY") and self.g.streaming and int(time.monotonic() * 2) != getattr(self, "_tt", 0):
            self._tt = int(time.monotonic() * 2)   # test hook: a fake telemetry packet with OSD-like text
            self.g.seq = (self.g.seq + 1) & 0xFFFF
            extra.append(p.build_outer(self.g.session, self.g.seq, p.T_TELEMETRY, b"\x01\x02BAT 16.4V\x00RSSI 99"))
        # one picture per tick (parameter-set blobs ride along with the next picture)
        out = []
        while True:
            unit_before = self.g.pos
            out += self.g.next_packets(1)
            unit = self.g.units[unit_before % len(self.g.units)]
            if not self.g.streaming or any(t in (1, 5) for t in p.nal_types(unit)):
                return out + extra
