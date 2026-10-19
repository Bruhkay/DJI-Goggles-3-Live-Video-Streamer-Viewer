"""Recording without re-encoding.

While recording, units go to a plain .h264 file (crash-safe, nothing to
finalise) together with their arrival times. On stop the file is remuxed to
.mp4 with real timestamps, so playback speed matches what was flown.
"""
import datetime
import os
import sys
import threading
import time
from fractions import Fraction

from .protocol import nal_types

TB = Fraction(1, 90000)


def is_picture(unit):
    return any(t in (1, 5) for t in nal_types(unit))


def default_folder():
    sub = "Movies" if sys.platform == "darwin" else "Videos"
    return os.path.join(os.path.expanduser("~"), sub, "Goggles3")


def remux_h264_to_mp4(src, dst, times=None, fallback_fps=56.0):
    import av
    inp = av.open(src, format="h264")
    out = av.open(dst, "w", format="mp4")
    try:
        ist = inp.streams.video[0]
        ost = out.add_stream_from_template(ist)
        ost.time_base = TB
        t0 = times[0] if times else 0.0
        last_dts = -1
        i = 0
        for pkt in inp.demux(ist):
            if pkt.size == 0:
                continue
            if times and i < len(times):
                ts = times[i] - t0
            elif times:
                ts = last_dts / 90000.0 + 1.0 / fallback_fps
            else:
                ts = i / fallback_fps
            dts = max(int(round(ts * 90000)), last_dts + 1)
            pkt.pts = pkt.dts = dts
            pkt.time_base = TB
            pkt.stream = ost
            out.mux(pkt)
            last_dts = dts
            i += 1
        return i
    finally:
        out.close()
        inp.close()


class Recorder(object):
    def __init__(self, folder=None, on_done=None):
        self.folder = folder or default_folder()
        os.makedirs(self.folder, exist_ok=True)
        stamp = datetime.datetime.now().strftime("flight_%Y%m%d_%H%M%S")
        self.mp4 = os.path.join(self.folder, stamp + ".mp4")
        self.raw = os.path.join(self.folder, "." + stamp + ".h264")
        self.f = open(self.raw, "wb")
        self.times = []
        self.t_start = time.monotonic()
        self.bytes = 0
        self.lock = threading.Lock()
        self.on_done = on_done or (lambda ok, path: None)

    def elapsed(self):
        return time.monotonic() - self.t_start

    def write(self, unit, t=None):
        with self.lock:
            if self.f is None:
                return
            self.f.write(unit)
            self.bytes += len(unit)
            if is_picture(unit):
                self.times.append(time.monotonic() if t is None else t)

    def stop(self, background=True):
        with self.lock:
            if self.f is None:
                return
            self.f.close()
            self.f = None
        if background:
            threading.Thread(target=self._finish, daemon=True).start()
        else:
            self._finish()

    def _finish(self):
        if not self.times:
            os.remove(self.raw)
            self.on_done(False, None)
            return
        try:
            remux_h264_to_mp4(self.raw, self.mp4, self.times)
            os.remove(self.raw)
            self.on_done(True, self.mp4)
        except Exception:
            keep = self.mp4[:-4] + ".h264"
            try:
                if os.path.exists(self.mp4):
                    os.remove(self.mp4)
                os.rename(self.raw, keep)
            except OSError:
                keep = self.raw
            self.on_done(False, keep)
