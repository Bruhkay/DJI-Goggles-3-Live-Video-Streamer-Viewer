"""The receive loop: handshake, reassemble, ack, gate on keyframe, fan out to sinks."""
import time

from . import protocol as p
from .transport import TransportError

KEYFRAME_HINT = """
  >>> Video is arriving but the goggles have not sent a keyframe yet.
  >>> On the goggles: open the quick menu and switch
  >>>   "Share Liveview to Mobile Device via Wi-Fi"  OFF, then ON again.
  >>> The picture appears a moment later.
"""


class Stats(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.t0 = time.monotonic()
        self.frames = 0
        self.bytes = 0
        self.packets = 0


class LiveView(object):
    HANDSHAKE_EVERY = 2.0      # re-send handshake after this much silence
    STALL_AFTER = 5.0          # declare the link stalled
    HINT_AFTER = 5.0           # show the keyframe hint after this long without one

    def __init__(self, transport, sinks, log=print, status=None, clock=time.monotonic,
                 on_state=None, on_stats=None, raw_hook=None):
        self.t = transport
        self.sinks = sinks
        self.log = log
        self.status = status or (lambda s: None)
        self.on_state = on_state or (lambda s: None)
        self.on_stats = on_stats or (lambda d: None)
        self.raw_hook = raw_hook
        self.type_counts = {}
        self.clock = clock
        self.session = p.Session()
        self.reasm = p.Reassembler()
        self.gate = p.KeyframeGate()
        self.stats = Stats()
        self.state = "handshaking"
        self.running = True
        self._hint_shown = False

    def stop(self):
        self.running = False

    def _emit(self, unit):
        for s in self.sinks:
            s.write(unit)

    def _on_packet(self, pkt):
        head = p.parse_outer(pkt)
        if head is None:
            return
        seq, ptype = head
        self.stats.packets += 1
        key = "0x%02x" % ptype
        self.type_counts[key] = self.type_counts.get(key, 0) + 1
        if ptype != p.T_VIDEO:
            if self.raw_hook is not None:
                self.raw_hook(pkt)
            return
        v = p.parse_video(pkt)
        if v is None:
            return
        frame_no, index, count, data = v
        for payload, s0, s1 in self.reasm.add(seq, frame_no, index, count, data, now=self.clock()):
            self.t.send(self.session.ack(s0, s1))
            for unit in self.gate.push(payload):
                self._emit(unit)
                self.stats.frames += 1
                self.stats.bytes += len(unit)

    def run(self, max_seconds=None):
        """Run until stop(), a required sink closes, or the transport fails (raises)."""
        start = now = self.clock()
        self.t.send(self.session.handshake())
        last_rx = last_hs = video_since = now
        last_stat = now
        got_video = False
        while self.running:
            pkts = self.t.recv(0.05)
            now = self.clock()
            if pkts:
                last_rx = now
                if not got_video:
                    got_video = True
                    video_since = now
                for pkt in pkts:
                    self._on_packet(pkt)

            # state machine
            if self.gate.open:
                new_state = "live"
            elif got_video:
                new_state = "waiting for keyframe"
            else:
                new_state = "handshaking"
            if now - last_rx > self.STALL_AFTER and got_video:
                new_state = "stalled"
            if new_state != self.state:
                self.state = new_state
                self.log("[state] %s" % new_state)
                self.on_state(new_state)
                if new_state == "live":
                    self._hint_shown = False

            if not self.gate.open and got_video and not self._hint_shown and now - video_since > self.HINT_AFTER:
                self._hint_shown = True
                self.log(KEYFRAME_HINT)

            if now - last_rx > self.HANDSHAKE_EVERY and now - last_hs > self.HANDSHAKE_EVERY:
                last_hs = now
                if self.state == "stalled":
                    # new session id, otherwise keyframes are not delivered after reconnect
                    self.session = p.Session()
                self.t.send(self.session.handshake())

            if now - last_stat >= 1.0:
                dt = max(now - self.stats.t0, 1e-6)
                fps, mbps = self.stats.frames / dt, self.stats.bytes * 8 / dt / 1e6
                self.status("%-21s %5.1f fps  %5.1f Mbit/s  dropped %d" % (self.state, fps, mbps, self.reasm.dropped))
                self.on_stats({"state": self.state, "fps": fps, "mbps": mbps, "dropped": self.reasm.dropped,
                               "types": dict(self.type_counts)})
                self.stats.reset()
                last_stat = now
                for s in self.sinks:
                    if not s.alive() and getattr(s, "required", False):
                        self.log("Viewer window closed.")
                        return "closed"

            if max_seconds is not None and now - start > max_seconds:
                return "timeout"
        return "stopped"


__all__ = ["LiveView", "TransportError"]
