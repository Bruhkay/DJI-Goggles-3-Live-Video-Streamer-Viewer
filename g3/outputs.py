"""Output engine: one hardware H.264 encoder, many destinations.

The goggles' own stream has a keyframe only at the very start, so a viewer
that joins late (YouTube, OBS, a phone) could never start decoding it. For
outputs we therefore re-encode the processed picture (stabilized, framed)
with a keyframe every couple of seconds, and fan the
encoded packets out to every destination. The original recording stays a
bit-exact passthrough.
"""
import collections
import io
import os
import struct
import queue
import socket
import ssl
import threading
import time
from fractions import Fraction
from urllib.parse import urlsplit

import av
import numpy as np

TB = Fraction(1, 90000)

try:
    from av.codec.context import Flags as _Flags
    GLOBAL_HEADER = _Flags.global_header
except Exception:      # older PyAV
    GLOBAL_HEADER = 1 << 22


# ----------------------------------------------------------------------------- encoder

class Packet(object):
    __slots__ = ("data", "pts", "dts", "key")

    def __init__(self, data, pts, dts, key):
        self.data, self.pts, self.dts, self.key = data, pts, dts, key


class Encoder(object):
    """H.264 encoder: Apple VideoToolbox (hardware) when available, else x264."""

    def __init__(self, width, height, bitrate_kbps=8000, gop_seconds=2.0, fps=60, hardware=True):
        self.width, self.height = int(width) & ~1, int(height) & ~1
        self.bitrate = int(bitrate_kbps) * 1000
        self.gop = max(1, int(round(gop_seconds * fps)))
        self.fps = fps
        self.ctx = None
        self.name = None
        self.pix_fmt = None
        self.last_pts = -1
        self.t0 = None
        self.force_key = False
        order = ["h264_videotoolbox", "libx264"] if hardware else ["libx264", "h264_videotoolbox"]
        self.error = None
        for name in order:
            try:
                self._open(name)
                break
            except Exception as e:   # codec missing or refused to open
                self.error = "%s: %s" % (name, e)
                self.ctx = None
        if self.ctx is None:
            raise RuntimeError("No H.264 encoder available (%s)" % self.error)

    def _open(self, name):
        ctx = av.CodecContext.create(name, "w")
        ctx.width, ctx.height = self.width, self.height
        ctx.time_base = TB
        ctx.framerate = Fraction(self.fps, 1)
        ctx.bit_rate = self.bitrate
        ctx.gop_size = self.gop
        ctx.max_b_frames = 0
        ctx.flags |= GLOBAL_HEADER
        if name == "h264_videotoolbox":
            ctx.pix_fmt = "nv12"
            ctx.options = {"realtime": "1", "profile": "high", "allow_sw": "1",
                           "max_ref_frames": "2", "prio_speed": "1"}
        else:
            ctx.pix_fmt = "yuv420p"
            ctx.options = {"preset": "veryfast", "tune": "zerolatency", "profile": "high",
                           "x264-params": "keyint=%d:min-keyint=%d:scenecut=0:bframes=0" % (self.gop, self.gop),
                           "maxrate": str(self.bitrate), "bufsize": str(self.bitrate)}
        ctx.open()
        self.ctx, self.name, self.pix_fmt = ctx, name, ctx.pix_fmt

    @property
    def extradata(self):
        return self.ctx.extradata

    @property
    def hardware(self):
        return self.name == "h264_videotoolbox"

    def encode(self, rgb, t):
        if self.t0 is None:
            self.t0 = t
        pts = max(int(round((t - self.t0) * 90000)), self.last_pts + 1)
        self.last_pts = pts
        frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format="rgb24")
        frame = frame.reformat(width=self.width, height=self.height, format=self.pix_fmt)
        frame.pts = pts
        frame.time_base = TB
        if self.force_key:
            try:
                frame.pict_type = av.video.frame.PictureType.I
            except Exception:
                pass
            self.force_key = False
        return [self._pkt(p) for p in self.ctx.encode(frame)]

    def flush(self):
        try:
            return [self._pkt(p) for p in self.ctx.encode(None)]
        except Exception:
            return []

    @staticmethod
    def _pkt(p):
        return Packet(bytes(p), p.pts, p.dts if p.dts is not None else p.pts, bool(p.is_keyframe))


def avcc_to_annexb(extradata):
    """avcC (ISO) parameter sets -> Annex-B. Annex-B input is returned unchanged."""
    if not extradata or extradata[0] != 1:
        return extradata or b""
    out, pos = [], 5
    n_sps = extradata[pos] & 0x1F
    pos += 1
    for _ in range(n_sps):
        ln = struct.unpack(">H", extradata[pos:pos + 2])[0]
        out.append(b"\x00\x00\x00\x01" + extradata[pos + 2:pos + 2 + ln])
        pos += 2 + ln
    n_pps = extradata[pos]
    pos += 1
    for _ in range(n_pps):
        ln = struct.unpack(">H", extradata[pos:pos + 2])[0]
        out.append(b"\x00\x00\x00\x01" + extradata[pos + 2:pos + 2 + ln])
        pos += 2 + ln
    return b"".join(out)


def stream_template(extradata, keyframe):
    """An input stream describing our encoded video, used as a template for output streams.

    (Creating the output stream from a codec name would make PyAV open a second
    encoder whose parameter sets replace ours: the result would not decode.)
    """
    probe = io.BytesIO(avcc_to_annexb(extradata) + keyframe)
    inp = av.open(probe, format="h264")
    return inp, inp.streams.video[0]


# ----------------------------------------------------------------------------- RTMPS bridge

def _ssl_context(verify=True):
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


class TlsBridge(object):
    """Local plain-TCP port that tunnels to a TLS server (turns rtmp:// into rtmps://)."""

    def __init__(self, host, port, verify=True):
        self.host, self.port = host, port
        self.ctx = _ssl_context(verify)
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.local_port = self.srv.getsockname()[1]
        self.closed = False
        threading.Thread(target=self._accept, daemon=True, name="tls-bridge").start()

    def _accept(self):
        while not self.closed:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, local):
        try:
            raw = socket.create_connection((self.host, self.port), timeout=10)
            remote = self.ctx.wrap_socket(raw, server_hostname=self.host)
            remote.settimeout(None)
        except Exception:
            local.close()
            return

        def pipe(a, b):
            try:
                while True:
                    data = a.recv(65536)
                    if not data:
                        break
                    b.sendall(data)
            except OSError:
                pass
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        threading.Thread(target=pipe, args=(remote, local), daemon=True).start()
        pipe(local, remote)

    def close(self):
        self.closed = True
        try:
            self.srv.close()
        except OSError:
            pass


def rtmp_target(server, key, verify=True):
    """Return (url, options, bridge) for an RTMP/RTMPS server URL + stream key.

    The bundled ffmpeg has no TLS, so rtmps:// goes through a local TlsBridge:
    ffmpeg speaks plain RTMP to 127.0.0.1, the bridge encrypts to the server.
    """
    server = server.strip().rstrip("/")
    key = (key or "").strip().lstrip("/")
    full = server + ("/" + key if key else "")
    u = urlsplit(server)
    opts = {"flvflags": "no_duration_filesize"}
    if u.scheme.lower() == "rtmps":
        bridge = TlsBridge(u.hostname, u.port or 443, verify=verify)
        return "rtmp://127.0.0.1:%d%s" % (bridge.local_port, urlsplit(full).path), opts, bridge
    return full, opts, None


# ----------------------------------------------------------------------------- sinks

class MuxSink(object):
    """Muxes encoded packets into a file or network destination on its own thread.

    Starts at a keyframe, retries network destinations after errors, never
    blocks the encoder (drops to the next keyframe when it falls behind).
    """

    def __init__(self, name, url, fmt, options=None, audio=False, retry=True, bridge=None):
        self.name, self.url, self.fmt = name, url, fmt
        self.options = options or {}
        self.audio = audio
        self.retry = retry
        self.bridge = bridge
        self.q = queue.Queue(maxsize=180)
        self.state = "starting"      # starting | connecting | live | error | stopped
        self.error = ""
        self.bytes = 0
        self.rate_bps = 0.0
        self.since = None
        self.stream_info = None
        self.stop_evt = threading.Event()
        self.need_key = True
        self.thread = threading.Thread(target=self._run, name="out-" + name, daemon=True)

    def start(self, width, height, extradata):
        self.stream_info = (width, height, extradata)
        self.thread.start()

    def put(self, pkt):
        if self.stop_evt.is_set():
            return
        try:
            self.q.put_nowait(pkt)
        except queue.Full:
            # fell behind (slow network): clear and resume at the next keyframe
            self._drain()
            self.need_key = True

    def _drain(self):
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass

    def stop(self, wait=False):
        self.stop_evt.set()
        try:
            self.q.put_nowait(None)
        except queue.Full:
            self._drain()
            self.q.put_nowait(None)
        if wait and self.thread.is_alive():
            self.thread.join(timeout=8)
        if self.bridge:
            self.bridge.close()

    def _open(self, first_key):
        w, h, extradata = self.stream_info
        self.state = "connecting"
        probe, tpl = stream_template(extradata, first_key.data)
        out = av.open(self.url, "w", format=self.fmt, options=dict(self.options), timeout=(10, 10))
        vs = out.add_stream_from_template(tpl)
        vs.time_base = Fraction(1, 1000) if self.fmt == "flv" else TB
        probe.close()
        audio = None
        if self.audio:
            audio = out.add_stream("aac", rate=48000)
            audio.codec_context.layout = "stereo"
            audio.codec_context.format = "fltp"
            audio.codec_context.bit_rate = 96000
        return out, vs, audio

    def _run(self):
        while not self.stop_evt.is_set():
            out = None
            try:
                first = self._wait_key()
                if first is None:
                    break
                out, vs, ast = self._open(first)
                self._pump(out, vs, ast, first)
            except Exception as e:
                if self.stop_evt.is_set():
                    break
                self.state = "error"
                self.error = str(e).split("\n")[0][:200]
            finally:
                if out is not None:
                    try:
                        out.close()
                    except Exception:
                        pass
            if not self.retry or self.stop_evt.is_set():
                break
            self._drain()
            self.need_key = True
            self.stop_evt.wait(3.0)
        self.state = "stopped" if self.state != "error" or self.stop_evt.is_set() else self.state

    def _wait_key(self):
        while True:
            pkt = self.q.get()
            if pkt is None:
                return None
            if pkt.key:
                self.need_key = False
                return pkt

    def _pump(self, out, vs, ast, first):
        base = None
        a_samples = 0
        silent = None
        win_t, win_b = time.monotonic(), 0
        pending = first
        while True:
            if pending is not None:
                pkt, pending = pending, None
            else:
                pkt = self.q.get()
            if pkt is None:
                return
            if self.need_key:
                if not pkt.key:
                    continue
                self.need_key = False
            if base is None:
                base = pkt.dts
            p = av.Packet(pkt.data)
            p.pts, p.dts = pkt.pts - base, pkt.dts - base
            p.time_base = TB
            p.is_keyframe = pkt.key
            p.stream = vs
            out.mux(p)
            if self.state != "live":
                self.state, self.since, self.error = "live", time.monotonic(), ""
            if ast is not None:
                # silent AAC audio, kept in step with the video clock
                t_video = (pkt.pts - base) / 90000.0
                while a_samples / 48000.0 <= t_video:
                    if silent is None:
                        silent = np.zeros((2, 1024), dtype=np.float32)
                    af = av.AudioFrame.from_ndarray(silent, format="fltp", layout="stereo")
                    af.sample_rate = 48000
                    af.pts = a_samples
                    af.time_base = Fraction(1, 48000)
                    for ap in ast.encode(af):
                        out.mux(ap)
                    a_samples += 1024
            self.bytes += len(pkt.data)
            win_b += len(pkt.data)
            now = time.monotonic()
            if now - win_t >= 1.0:
                self.rate_bps = win_b * 8 / (now - win_t)
                win_t, win_b = now, 0


class ReplayBuffer(object):
    """Keeps the last N seconds of encoded packets; save() writes them to MP4."""

    def __init__(self, seconds=30):
        self.seconds = seconds
        self.packets = collections.deque()
        self.lock = threading.Lock()
        self.info = None

    def put(self, pkt):
        with self.lock:
            self.packets.append(pkt)
            limit = self.seconds * 90000
            while self.packets and pkt.dts - self.packets[0].dts > limit:
                self.packets.popleft()

    def duration(self):
        with self.lock:
            if len(self.packets) < 2:
                return 0.0
            return (self.packets[-1].dts - self.packets[0].dts) / 90000.0

    def save(self, path):
        with self.lock:
            pkts = list(self.packets)
        while pkts and not pkts[0].key:
            pkts.pop(0)
        if not pkts or self.info is None:
            return False
        w, h, extradata = self.info
        sink = MuxSink("replay", path, "mp4", {"movflags": "+faststart"}, retry=False)
        sink.q = queue.Queue()
        sink.stream_info = (w, h, extradata)
        for p in pkts:
            sink.q.put(p)
        sink.q.put(None)
        sink._run()
        return sink.state != "error" and os.path.exists(path)


class OutputHub(object):
    """Owns the encoder and all sinks; called from the output thread."""

    def __init__(self):
        self.encoder = None
        self.enc_key = None
        self.sinks = {}          # name -> MuxSink
        self.replay = None
        self.lock = threading.Lock()
        self.last_error = ""

    def active(self):
        return bool(self.sinks) or self.replay is not None

    def ensure_encoder(self, width, height, bitrate_kbps, gop, hardware):
        key = (int(width) & ~1, int(height) & ~1, bitrate_kbps, gop, hardware)
        if self.encoder is not None and self.enc_key == key:
            return self.encoder
        self.encoder = Encoder(width, height, bitrate_kbps, gop, hardware=hardware)
        self.enc_key = key
        # encoder (and its parameter sets) changed: everyone restarts at the next keyframe
        with self.lock:
            sinks = list(self.sinks.items())
        for name, s in sinks:
            self.restart_sink(name)
        if self.replay is not None:
            self.replay.packets.clear()
            self.replay.info = (self.encoder.width, self.encoder.height, self.encoder.extradata)
        return self.encoder

    def add_sink(self, sink):
        with self.lock:
            old = self.sinks.pop(sink.name, None)
            self.sinks[sink.name] = sink
        if old:
            old.stop()
        if self.encoder is not None:
            sink.start(self.encoder.width, self.encoder.height, self.encoder.extradata)
            self.encoder.force_key = True

    def restart_sink(self, name):
        with self.lock:
            s = self.sinks.get(name)
        if s is None:
            return
        clone = MuxSink(s.name, s.url, s.fmt, s.options, s.audio, s.retry, s.bridge)
        s.bridge = None
        s.stop()
        self.add_sink(clone)

    def remove_sink(self, name, wait=False):
        with self.lock:
            s = self.sinks.pop(name, None)
        if s:
            s.stop(wait=wait)
        return s

    def set_replay(self, seconds):
        if seconds:
            if self.replay is None:
                self.replay = ReplayBuffer(seconds)
                if self.encoder:
                    self.replay.info = (self.encoder.width, self.encoder.height, self.encoder.extradata)
            self.replay.seconds = seconds
        else:
            self.replay = None

    def dispatch(self, packets):
        with self.lock:
            sinks = list(self.sinks.values())
        for s in sinks:
            if s.stream_info is None and self.encoder is not None:
                s.start(self.encoder.width, self.encoder.height, self.encoder.extradata)
        for p in packets:
            for s in sinks:
                s.put(p)
            if self.replay is not None:
                self.replay.put(p)

    def status(self):
        with self.lock:
            return {n: {"state": s.state, "error": s.error, "rate": s.rate_bps,
                        "since": s.since} for n, s in self.sinks.items()}

    def close(self):
        with self.lock:
            sinks = list(self.sinks.values())
            self.sinks.clear()
        for s in sinks:
            s.stop(wait=True)
        self.encoder = None
