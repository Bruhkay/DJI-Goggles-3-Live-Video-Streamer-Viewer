"""SkyFeed Studio - live view, recording and streaming for DJI Goggles 3.

Threads:
  GUI            Qt widgets, settings, timers.
  StreamWorker   receives H.264 from the USB helper, records the original
                 stream, decodes, stabilizes, renders the preview.
  OutputWorker   renders output frames (stabilized / framed), encodes once and
                 feeds every destination, the web viewer and the replay buffer.
The USB helper (g3.helper) is a separate process, started with administrator
rights through the macOS password dialog only when needed.

The video is always shown clean; the app's own data lives around it.
"""
import collections
import json
import os
import queue
import re
import secrets
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid

import av
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from . import __version__, ipc
from . import render as R
from . import stabilizer as S
from .i18n import LANGS, set_language, tr
from .outputs import MuxSink, OutputHub, rtmp_target
from .protocol import nal_types
from .recorder import Recorder

try:
    import cv2
except Exception:
    cv2 = None

APP_NAME = "SkyFeed Studio"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACCENT = "#ff5a36"
LIVE_RED = "#ff3b30"
GREEN = "#34d17b"
WARN = "#f5b83d"
ERR = "#ff4d4d"
IDLE = "#8a93a3"
MONO = "'SF Mono', Menlo, Consolas, monospace"

# state -> (status key, color, banner title key, banner body key)
STATES = {
    "starting": ("st_starting", IDLE, "bn_starting_t", None),
    "searching": ("st_searching", IDLE, "bn_searching_t", "bn_searching_b"),
    "connected": ("st_connected", WARN, "bn_wait_t", "bn_wait_b"),
    "handshaking": ("st_handshaking", WARN, "bn_wait_t", "bn_wait_b"),
    "waiting for keyframe": ("st_waiting_kf", WARN, "bn_kf_t", "bn_kf_b"),
    "live": ("st_live", GREEN, None, None),
    "stalled": ("st_stalled", ERR, "bn_stalled_t", "bn_reconnecting"),
    "disconnected": ("st_disconnected", ERR, "bn_disc_t", "bn_disc_b"),
    "needs_admin": ("st_needs_admin", WARN, "bn_admin_t", "bn_admin_b"),
    "admin_denied": ("st_admin_denied", ERR, "bn_denied_t", "bn_denied_b"),
    "error": ("st_error", ERR, "bn_error_t", None),
    "helper_gone": ("st_helper_gone", ERR, "bn_gone_t", "bn_denied_b"),
}

PLATFORMS = [
    ("youtube", "YouTube", "rtmp://a.rtmp.youtube.com/live2", "#ff0033"),
    ("twitch", "Twitch", "rtmp://ingest.global-contribute.live-video.net/app", "#9146ff"),
    ("facebook", "Facebook", "rtmps://live-api-s.facebook.com:443/rtmp/", "#1877f2"),
    ("instagram", "Instagram", "", "#e1306c"),
    ("kick", "Kick", "", "#53fc18"),
    ("custom", None, "", "#8a93a3"),
]
PLATFORM = {p[0]: p for p in PLATFORMS}
VOLTAGE_RE = re.compile(r"(?<![\d.])(\d{1,2}\.\d{1,2})\s?V\b")


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def is_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def applescript_quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def default_record_folder():
    sub = "Movies" if sys.platform == "darwin" else "Videos"
    return os.path.join(os.path.expanduser("~"), sub, APP_NAME)


def fmt_dur(s):
    s = int(max(0, s))
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else "%02d:%02d" % (s // 60, s % 60)


# ============================================================================ secrets

class Keys(object):
    """Stream keys in the system keychain when possible, settings file otherwise."""

    def __init__(self, settings):
        self.settings = settings
        try:
            import keyring
            self.kr = keyring
        except Exception:
            self.kr = None

    def get(self, ident):
        if self.kr:
            try:
                v = self.kr.get_password(APP_NAME, ident)
                if v is not None:
                    return v
            except Exception:
                pass
        return self.settings.value("keys/" + ident, "", type=str)

    def set(self, ident, value):
        if self.kr:
            try:
                self.kr.set_password(APP_NAME, ident, value)
                self.settings.remove("keys/" + ident)
                return
            except Exception:
                pass
        self.settings.setValue("keys/" + ident, value)

    def delete(self, ident):
        if self.kr:
            try:
                self.kr.delete_password(APP_NAME, ident)
            except Exception:
                pass
        self.settings.remove("keys/" + ident)


# ============================================================================ shared state

class Shared(object):
    """Plain attributes read by worker threads, written by the GUI."""

    def __init__(self):
        self.pic = R.Picture()
        self.out_lines = 1080
        self.out_kbps = 8000
        self.out_hw = True


class Bridge(QtCore.QObject):
    event = QtCore.Signal(dict)
    frame = QtCore.Signal()


# ============================================================================ output worker

class OutputWorker(threading.Thread):
    def __init__(self, bridge, shared):
        super(OutputWorker, self).__init__(name="outputs", daemon=True)
        self.bridge = bridge
        self.shared = shared
        self.q = queue.Queue(maxsize=3)
        self.hub = OutputHub()
        self.rd = R.Renderer()
        self.web = None
        self.snap_req = None
        self.last_web = 0.0
        self.err_t = 0.0
        self.ms = collections.deque(maxlen=60)
        self.stopping = False

    def wanted(self):
        return self.hub.active() or (self.web is not None and self.web.wants_frame()) or self.snap_req is not None

    def submit(self, frame, t, corr, zoom):
        if not self.wanted():
            return
        item = (frame, t, corr, zoom)
        try:
            self.q.put_nowait(item)
        except queue.Full:            # never hold up the preview: drop the oldest
            try:
                self.q.get_nowait()
            except queue.Empty:
                pass
            try:
                self.q.put_nowait(item)
            except queue.Full:
                pass

    def run(self):
        while not self.stopping:
            item = self.q.get()
            if item is None:
                break
            try:
                self._process(*item)
            except Exception as e:
                if time.monotonic() - self.err_t > 5:
                    self.err_t = time.monotonic()
                    self.bridge.event.emit({"type": "enc_error", "message": str(e)[:200]})

    def _process(self, frame, t, corr, zoom):
        t0 = time.monotonic()
        pic = self.shared.pic
        W, H = frame.width, frame.height
        if self.snap_req is not None:
            path, self.snap_req = self.snap_req, None
            cw, ch = R.canvas_size(pic, W, H, 1080)
            rgb = self.rd.render(frame, pic, cw, ch, corr, zoom)
            saved = cv2 is not None and cv2.imwrite(path, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            self.bridge.event.emit({"type": "snapshot", "ok": bool(saved), "path": path})
        enc_on = self.hub.active()
        web_on = self.web is not None and self.web.wants_frame() and time.monotonic() - self.last_web >= 1 / 30.0
        if not (enc_on or web_on):
            return
        cw, ch = R.canvas_size(pic, W, H, self.shared.out_lines if enc_on else 720)
        rgb = self.rd.render(frame, pic, cw, ch, corr, zoom)
        if enc_on:
            enc = self.hub.ensure_encoder(cw, ch, self.shared.out_kbps, 2.0, self.shared.out_hw)
            self.hub.dispatch(enc.encode(rgb, t))
        if web_on and cv2 is not None:
            self.last_web = time.monotonic()
            small = rgb
            if max(cw, ch) > 1280:
                k = 1280.0 / max(cw, ch)
                small = cv2.resize(rgb, (int(cw * k), int(ch * k)), interpolation=cv2.INTER_AREA)
            ok_j, jpg = cv2.imencode(".jpg", cv2.cvtColor(small, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 78])
            if ok_j:
                self.web.publish(jpg.tobytes())
        self.ms.append((time.monotonic() - t0) * 1000)

    def encoder_name(self):
        e = self.hub.encoder
        return e.name if e else ""

    def shutdown(self):
        self.stopping = True
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass
        self.hub.close()
        if self.web:
            self.web.stop()


# ============================================================================ stream worker

class StreamWorker(threading.Thread):
    """Accepts the helper's connection, records, decodes, stabilizes, renders the preview."""

    def __init__(self, bridge, token, shared, out):
        super(StreamWorker, self).__init__(name="stream", daemon=True)
        self.bridge = bridge
        self.token = token
        self.shared = shared
        self.out = out
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(2)
        self.port = self.server.getsockname()[1]
        self.lock = threading.Lock()
        self.chan = None
        self.conn = None
        self.latest = None
        self.target = (1280, 720)
        self.dpr = 1.0
        self.params = None
        self.last_idr = None
        self.recorder = None
        self.record_folder = default_record_folder()
        self.auto_record = False
        self.armed = True
        self.stopping = False
        self.rd = R.Renderer()
        self.est = None
        self.stab = S.Stabilizer()
        self.proc_ms = collections.deque(maxlen=60)
        self.capture = None
        self.capture_path = None
        self.capture_count = 0
        self.strings = collections.Counter()
        self.src_size = None
        self.voltage = None
        self.stab_delay = 0

    # ---- GUI thread API
    def set_target(self, w, h, dpr):
        self.target = (max(2, int(w * dpr)), max(2, int(h * dpr)))
        self.dpr = dpr

    def take_frame(self):
        with self.lock:
            return self.latest

    def drop_connection(self):
        c = self.conn
        if c is not None:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def start_recording(self):
        with self.lock:
            if self.recorder is None:
                self._start_recording_locked(include_idr=True)

    def stop_recording(self, background=True):
        with self.lock:
            rec, self.recorder = self.recorder, None
        if rec is not None:
            rec.stop(background=background)

    def recording_elapsed(self):
        rec = self.recorder
        return rec.elapsed() if rec else None

    def set_capture(self, on):
        if on and self.capture is None:
            os.makedirs(self.record_folder, exist_ok=True)
            self.capture_path = os.path.join(self.record_folder, time.strftime("telemetry_%Y%m%d_%H%M%S.bin"))
            self.capture = open(self.capture_path, "wb")
            self.capture_count = 0
            self.strings.clear()
        elif not on and self.capture is not None:
            self.capture.close()
            self.capture = None

    def shutdown(self):
        self.stopping = True
        self.drop_connection()
        try:
            self.server.close()
        except OSError:
            pass
        if self.capture:
            self.capture.close()

    # ---- worker thread
    def _start_recording_locked(self, include_idr):
        def done(ok, path):
            self.bridge.event.emit({"type": "rec_saved", "ok": ok, "path": path})
        rec = Recorder(self.record_folder, on_done=done)
        for unit in (self.params, self.last_idr if include_idr else None):
            if unit:
                rec.write(unit)
        self.recorder = rec
        self.bridge.event.emit({"type": "rec_started", "path": rec.mp4})

    def run(self):
        while not self.stopping:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            try:
                self._serve(conn)
            except Exception as e:
                self.bridge.event.emit({"type": "log", "message": "stream error: %r" % (e,)})
            finally:
                self.conn = None
                self.chan = None
                try:
                    conn.close()
                except OSError:
                    pass
            if not self.stopping:
                self.bridge.event.emit({"type": "helper_gone"})

    def _serve(self, conn):
        conn.settimeout(10)
        kind, payload = ipc.read_message(conn)
        hello = json.loads(payload) if kind == ipc.EVENT else {}
        if hello.get("type") != "hello" or hello.get("token") != self.token:
            return
        conn.settimeout(None)
        self.conn = conn
        self.chan = ipc.Channel(conn)
        self.chan.command(cmd="capture", on=True)     # always scan non-video packets for telemetry
        self.bridge.event.emit(hello)
        ctx, pending = self._new_decoder(), b""
        while True:
            try:
                kind, payload = ipc.read_message(conn)
            except (ConnectionError, OSError):
                return
            if kind == ipc.EVENT:
                ev = json.loads(payload)
                if ev.get("type") == "connected":
                    ctx, pending = self._new_decoder(), b""
                    self.est = None
                    self.stab.flush()
                self.bridge.event.emit(ev)
                continue
            if kind == ipc.RAW:
                self._on_raw(payload)
                continue
            unit = payload
            types = nal_types(unit)
            picture = 1 in types or 5 in types
            with self.lock:
                if 7 in types and not picture:
                    self.params = unit
                if 5 in types:
                    if self.auto_record and self.recorder is None and self.armed:
                        self.armed = False
                        self._start_recording_locked(include_idr=False)
                    self.last_idr = unit
                rec = self.recorder
            if rec is not None:
                rec.write(unit)
            if not picture:
                pending += unit
                continue
            try:
                frames = ctx.decode(av.Packet(pending + unit))
            except av.error.FFmpegError:
                frames = []
            pending = b""
            if frames:
                try:
                    self._on_frame(frames[-1])
                except Exception as e:          # one bad frame must never drop the connection
                    now = time.monotonic()
                    if now - getattr(self, "_err_t", 0) > 5:
                        self._err_t = now
                        self.bridge.event.emit({"type": "log", "message": "frame error: %r" % (e,)})

    def _on_raw(self, payload):
        t = struct.unpack(">d", payload[:8])[0]
        data = payload[8:]
        if self.capture is not None:
            self.capture.write(struct.pack(">dI", t, len(data)) + data)
            self.capture_count += 1
        run = bytearray()
        for b in data + b"\x00":
            if 32 <= b < 127:
                run.append(b)
            else:
                if len(run) >= 3:
                    text = run.decode("ascii")
                    if self.capture is not None:
                        self.strings[text] += 1
                    m = VOLTAGE_RE.search(text)
                    if m and 2.5 <= float(m.group(1)) <= 60.0:
                        self.voltage = (float(m.group(1)), time.monotonic())
                run = bytearray()

    @staticmethod
    def _new_decoder():
        ctx = av.CodecContext.create("h264", "r")
        ctx.thread_type = "SLICE"              # frame threading would add latency
        ctx.options = {"flags": "low_delay"}
        return ctx

    def _on_frame(self, f):
        t0 = time.monotonic()
        pic = self.shared.pic
        W, H = f.width, f.height
        self.src_size = (W, H)
        corr, zoom, t = None, 1.0, t0
        if pic.stab != "off" and S.available():
            if self.est is None or self.est.fov != pic.lens_fov:
                self.est = S.RotationEstimator(float(pic.lens_fov))
            self.stab.configure(pic.stab, pic.smooth, pic.roll, float(pic.lens_fov))
            rv, ok = self.est.step(R.gray_small(f))
            res = self.stab.push((f, t0), rv, ok, W)
            self.stab_delay = self.stab.delay if pic.smooth else 0
            if res is None:                    # look-ahead still filling
                return
            (f, t), corr, zoom = res
        else:
            self.est = None
            self.stab_delay = 0
            if self.stab.strength is not None:
                self.stab.configure(None, True, True, 150.0)
        cw, ch = R.fit(pic, W, H, *self.target)
        rgb = self.rd.render(f, pic, cw, ch, corr, zoom)
        img = QtGui.QImage(rgb.data, cw, ch, rgb.strides[0], QtGui.QImage.Format.Format_RGB888).copy()
        img.setDevicePixelRatio(self.dpr)
        with self.lock:
            self.latest = img
        self.bridge.frame.emit()
        self.out.submit(f, t, corr, zoom)
        self.proc_ms.append((time.monotonic() - t0) * 1000)


# ============================================================================ widgets

class VideoView(QtWidgets.QWidget):
    """Shows the picture centered and untouched; only state banners are drawn on top."""
    toggle_fullscreen = QtCore.Signal()
    resized = QtCore.Signal()

    def __init__(self, parent=None):
        super(VideoView, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(320, 180)
        self.image = None
        self.banner = None
        self.dim = False

    def mouseDoubleClickEvent(self, e):
        self.toggle_fullscreen.emit()

    def resizeEvent(self, e):
        self.resized.emit()
        super(VideoView, self).resizeEvent(e)

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor("#000000"))
        if self.image is not None:
            dpr = self.image.devicePixelRatio() or 1.0
            iw, ih = self.image.width() / dpr, self.image.height() / dpr
            k = min(self.width() / iw, self.height() / ih, 1.0)
            tw, th = iw * k, ih * k
            target = QtCore.QRectF((self.width() - tw) / 2.0, (self.height() - th) / 2.0, tw, th)
            if k < 1.0:
                p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(target, self.image)
            if self.dim:
                p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 150))
        if self.banner:
            self._banner(p, *self.banner)
        p.end()

    def _banner(self, p, title, text, color):
        w = min(600, self.width() - 48)
        tf = QtGui.QFont(self.font())
        tf.setPointSizeF(self.font().pointSizeF() * 1.45)
        tf.setWeight(QtGui.QFont.Weight.DemiBold)
        bf = QtGui.QFont(self.font())
        flags = int(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.TextFlag.TextWordWrap)
        tr_ = QtGui.QFontMetrics(tf).boundingRect(QtCore.QRect(0, 0, w - 56, 1000), flags, title)
        br = QtGui.QFontMetrics(bf).boundingRect(QtCore.QRect(0, 0, w - 56, 1000), flags, text) if text else QtCore.QRect()
        h = 30 + 28 + 18 + tr_.height() + (12 + br.height() if text else 0) + 30
        box = QtCore.QRectF((self.width() - w) / 2.0, (self.height() - h) / 2.0, w, h)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(18, 21, 27, 238))
        p.drawRoundedRect(box, 18, 18)
        c = QtGui.QColor(color)
        ring = QtGui.QColor(c)
        ring.setAlpha(60)
        cx, cy = box.center().x(), box.top() + 30 + 14
        p.setBrush(ring)
        p.drawEllipse(QtCore.QPointF(cx, cy), 14, 14)
        p.setBrush(c)
        p.drawEllipse(QtCore.QPointF(cx, cy), 7, 7)
        y = box.top() + 30 + 28 + 18
        p.setFont(tf)
        p.setPen(QtGui.QColor("#f2f4f8"))
        p.drawText(QtCore.QRectF(box.left() + 28, y, w - 56, tr_.height()), flags, title)
        if text:
            y += tr_.height() + 12
            p.setFont(bf)
            p.setPen(QtGui.QColor("#a7afbd"))
            p.drawText(QtCore.QRectF(box.left() + 28, y, w - 56, br.height()), flags, text)


class VideoWindow(QtWidgets.QWidget):
    """The detached video: a plain window for a second monitor."""
    closed = QtCore.Signal()

    def __init__(self):
        super(VideoWindow, self).__init__(None, QtCore.Qt.WindowType.Window)
        self.setWindowTitle(APP_NAME + " — Video")
        self.setStyleSheet("background:#000;")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = VideoView()
        self.view.toggle_fullscreen.connect(self.toggle_fullscreen)
        lay.addWidget(self.view)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self, activated=self.showNormal)
        QtGui.QShortcut(QtGui.QKeySequence("F"), self, activated=self.toggle_fullscreen)
        self.resize(1280, 720)

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def closeEvent(self, e):
        self.closed.emit()
        super(VideoWindow, self).closeEvent(e)


class InfoStrip(QtWidgets.QWidget):
    """The app's own data, in tiles along the bottom edge (never on the video)."""

    def __init__(self, parent=None):
        super(InfoStrip, self).__init__(parent)
        self.setFixedHeight(70)
        self.data = {}
        self.latency = False

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor("#0b0d10"))
        p.setPen(QtGui.QColor("#1a1d24"))
        p.drawLine(0, 0, self.width(), 0)
        d = self.data
        state = {"x": 12.0}
        h, y = self.height() - 18.0, 9.0
        small = QtGui.QFont(self.font())
        small.setPointSizeF(self.font().pointSizeF() * 0.8)
        small.setWeight(QtGui.QFont.Weight.DemiBold)
        big = QtGui.QFont()
        big.setFamilies(["SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono"])
        big.setPointSizeF(self.font().pointSizeF() * 1.2)
        big.setWeight(QtGui.QFont.Weight.Bold)

        def tile(w, title, value, accent=None, extra=None):
            x = state["x"]
            if x + w > self.width() - 12:
                return
            r = QtCore.QRectF(x, y, w, h)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor("#14171d"))
            p.drawRoundedRect(r, 10, 10)
            if accent:
                p.setBrush(QtGui.QColor(accent))
                p.drawEllipse(QtCore.QPointF(r.left() + 14, r.top() + 14), 4, 4)
            p.setFont(small)
            p.setPen(QtGui.QColor("#8a93a3"))
            p.drawText(QtCore.QRectF(r.left() + (24 if accent else 12), r.top() + 4, w - 24, 18),
                       int(QtCore.Qt.AlignmentFlag.AlignVCenter), title.upper())
            p.setFont(big)
            p.setPen(QtGui.QColor("#f2f4f8"))
            p.drawText(QtCore.QRectF(r.left() + 12, r.top() + 22, w - 24, h - 24),
                       int(QtCore.Qt.AlignmentFlag.AlignVCenter), value)
            if extra:
                extra(r)
            state["x"] = x + w + 8

        q = d.get("quality", 1.0)
        if d.get("fps") is not None:
            color = GREEN if q > 0.8 else WARN if q > 0.5 else ERR

            def link_extra(r):
                lit = int(round(q * 4))
                for i in range(4):
                    bh = 5 + i * 3.5
                    p.setPen(QtCore.Qt.PenStyle.NoPen)
                    p.setBrush(QtGui.QColor(color) if i < lit else QtGui.QColor(255, 255, 255, 40))
                    p.drawRoundedRect(QtCore.QRectF(r.right() - 112 + i * 6, r.top() + 18 - bh, 4, bh), 1, 1)
                hist = list(d.get("mbps_hist") or [])[-40:]
                if len(hist) >= 2:
                    mx = max(max(hist), 1.0)
                    sx, sw, top, bot = r.right() - 84, 72, r.top() + 24, r.bottom() - 8
                    path = QtGui.QPainterPath()
                    for i, v in enumerate(hist):
                        pt = QtCore.QPointF(sx + sw * i / (len(hist) - 1), bot - (bot - top) * v / mx)
                        path.moveTo(pt) if i == 0 else path.lineTo(pt)
                    p.setPen(QtGui.QPen(QtGui.QColor(color), 1.6))
                    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                    p.drawPath(path)
            tile(300, tr("tile_link"), "%2.0f fps  %4.1f Mb/s" % (d["fps"], d.get("mbps", 0)), extra=link_extra)
        else:
            tile(300, tr("tile_link"), "—")
        if d.get("voltage") is not None:
            tile(110, "BAT", "%.1f V" % d["voltage"], accent=GREEN)
        tile(116, tr("tile_flight"), fmt_dur(d["flight_s"]) if d.get("flight_s") is not None else "—")
        if d.get("rec_s") is not None:
            on = int(time.monotonic() * 2) % 2 == 0
            tile(130, tr("tile_rec"), fmt_dur(d["rec_s"]), accent=LIVE_RED if on else "#7a2020")
        if d.get("live_s") is not None:
            tile(170, tr("tile_live"), fmt_dur(d["live_s"]) + d.get("live_extra", ""), accent=LIVE_RED)
        if d.get("stab"):
            tile(150, tr("tile_stab"), d["stab"], accent="#5aa9ff")
        tile(116, tr("tile_clock"), time.strftime("%H:%M:%S"))
        if self.latency:
            t = time.time()
            tile(210, tr("tile_latency"), time.strftime("%H:%M:%S", time.localtime(t)) + ".%03d" % int((t % 1) * 1000),
                 accent=WARN)
        p.end()


class WrapCheck(QtWidgets.QWidget):
    """A checkbox whose label wraps instead of being cut off."""
    toggled = QtCore.Signal(bool)

    def __init__(self, text, parent=None):
        super(WrapCheck, self).__init__(parent)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.box = QtWidgets.QCheckBox()
        self.label = QtWidgets.QLabel(text)
        self.label.setWordWrap(True)
        self.label.mousePressEvent = lambda e: self.box.isEnabled() and self.box.toggle()
        h.addWidget(self.box, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        h.addWidget(self.label, 1)
        self.box.toggled.connect(self.toggled.emit)

    def isChecked(self):
        return self.box.isChecked()

    def setChecked(self, on):
        self.box.setChecked(on)

    def setEnabled(self, on):
        self.box.setEnabled(on)
        self.label.setEnabled(on)


class Segmented(QtWidgets.QWidget):
    """A row of exclusive buttons (the button group lives as long as the widget)."""
    picked = QtCore.Signal(object)

    def __init__(self, options, current, parent=None):
        super(Segmented, self).__init__(parent)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for value, label in options:
            b = QtWidgets.QPushButton(label, objectName="seg")
            b.setCheckable(True)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            self.group.addButton(b)
            self.buttons[value] = b
            b.clicked.connect(lambda _=False, v=value: self.picked.emit(v))
            h.addWidget(b)
        self.set_value(current)

    def set_value(self, value):
        b = self.buttons.get(value)
        if b is not None:
            b.setChecked(True)


class VScroll(QtWidgets.QScrollArea):
    """Vertical scroll area that sizes its page with height-for-width (wrapped text never overlaps)."""

    def __init__(self, inner):
        super(VScroll, self).__init__()
        self.inner = inner
        self.setWidget(inner)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner.installEventFilter(self)

    def fit(self):
        try:
            w = self.viewport().width()
        except RuntimeError:
            return
        lay = self.inner.layout()
        h = lay.totalHeightForWidth(w) if lay.hasHeightForWidth() else lay.totalSizeHint().height()
        h = max(h, lay.totalMinimumSize().height())
        if self.inner.width() != w or self.inner.height() != h:
            self.inner.resize(w, h)

    def resizeEvent(self, e):
        super(VScroll, self).resizeEvent(e)
        self.fit()

    def showEvent(self, e):
        self.fit()
        super(VScroll, self).showEvent(e)

    def eventFilter(self, obj, e):
        if obj is self.inner and e.type() == QtCore.QEvent.Type.LayoutRequest:
            QtCore.QTimer.singleShot(0, self, self.fit)
        return False


class Sparkline(QtWidgets.QWidget):
    def __init__(self, color, fmt="{:.1f}", parent=None):
        super(Sparkline, self).__init__(parent)
        self.color = QtGui.QColor(color)
        self.fmt = fmt
        self.values = collections.deque(maxlen=90)
        self.setMinimumHeight(54)

    def push(self, v):
        self.values.append(float(v))
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor("#0d0f13"))
        p.drawRoundedRect(r, 8, 8)
        vals = list(self.values)
        if len(vals) >= 2:
            mx = max(max(vals) * 1.15, 1e-6)
            inner = r.adjusted(6, 8, -54, -6)
            step = inner.width() / float(self.values.maxlen - 1)
            n = len(vals)
            pts = [QtCore.QPointF(inner.right() - step * (n - 1 - i), inner.bottom() - inner.height() * v / mx)
                   for i, v in enumerate(vals)]
            fill = QtGui.QPainterPath(QtCore.QPointF(pts[0].x(), inner.bottom()))
            for pt in pts:
                fill.lineTo(pt)
            fill.lineTo(QtCore.QPointF(pts[-1].x(), inner.bottom()))
            fc = QtGui.QColor(self.color)
            fc.setAlpha(40)
            p.setBrush(fc)
            p.drawPath(fill)
            line = QtGui.QPainterPath(pts[0])
            for pt in pts[1:]:
                line.lineTo(pt)
            p.setPen(QtGui.QPen(self.color, 1.8))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawPath(line)
            p.setPen(QtGui.QColor("#e6e9ef"))
            f = QtGui.QFont(self.font())
            f.setWeight(QtGui.QFont.Weight.DemiBold)
            p.setFont(f)
            p.drawText(r.adjusted(0, 0, -8, 0),
                       int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter),
                       self.fmt.format(vals[-1]))


class QrWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(QrWidget, self).__init__(parent)
        self.matrix = None
        self.setFixedSize(132, 132)

    def set_text(self, text):
        try:
            import segno
            self.matrix = [list(row) for row in segno.make(text, error="m").matrix]
        except Exception:
            self.matrix = None
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("white"))
        if not self.matrix:
            return
        n = len(self.matrix) + 4
        cell = self.width() / float(n)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor("black"))
        for yy, row in enumerate(self.matrix):
            for xx, v in enumerate(row):
                if v:
                    p.drawRect(QtCore.QRectF((xx + 2) * cell, (yy + 2) * cell, cell + 0.3, cell + 0.3))


class DestinationDialog(QtWidgets.QDialog):
    def __init__(self, parent, dest, key):
        super(DestinationDialog, self).__init__(parent)
        self.setWindowTitle(tr("dd_title"))
        self.setMinimumWidth(480)
        self.dest = dict(dest)
        form = QtWidgets.QFormLayout(self)
        form.setSpacing(10)
        self.platform = QtWidgets.QComboBox()
        for pid, name, _, _ in PLATFORMS:
            self.platform.addItem(name or tr("dd_custom"), pid)
        self.platform.setCurrentIndex(max(0, self.platform.findData(dest.get("platform", "youtube"))))
        self.name = QtWidgets.QLineEdit(dest.get("name", ""))
        self.server = QtWidgets.QLineEdit(dest.get("server", ""))
        self.server.setPlaceholderText("rtmp://…  /  rtmps://…")
        self.key = QtWidgets.QLineEdit(key)
        self.key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        show = QtWidgets.QCheckBox(tr("dd_show"))
        show.toggled.connect(lambda on: self.key.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.Normal if on else QtWidgets.QLineEdit.EchoMode.Password))
        krow = QtWidgets.QHBoxLayout()
        krow.addWidget(self.key, 1)
        krow.addWidget(show)
        self.enabled = QtWidgets.QCheckBox(tr("dd_enabled"))
        self.enabled.setChecked(dest.get("enabled", True))
        hint = QtWidgets.QLabel(tr("dd_paste_hint"), objectName="muted")
        hint.setWordWrap(True)
        form.addRow(tr("dd_platform"), self.platform)
        form.addRow(tr("dd_name"), self.name)
        form.addRow(tr("dd_server"), self.server)
        form.addRow(tr("dd_key"), krow)
        form.addRow("", self.enabled)
        form.addRow(hint)
        btns = QtWidgets.QDialogButtonBox()
        btns.addButton(tr("dd_save"), QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(tr("dd_cancel"), QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)
        self.platform.currentIndexChanged.connect(self._platform_changed)
        if not dest.get("server"):
            self._platform_changed()

    def _platform_changed(self, *_):
        pid = self.platform.currentData()
        presets = [p[2] for p in PLATFORMS if p[2]]
        if not self.server.text() or self.server.text() in presets:
            self.server.setText(PLATFORM[pid][2])
        names = [p[1] for p in PLATFORMS if p[1]] + ["RTMP"]
        if not self.name.text() or self.name.text() in names:
            self.name.setText(PLATFORM[pid][1] or "RTMP")

    def result_dest(self):
        d = dict(self.dest)
        d.update(platform=self.platform.currentData(), name=self.name.text().strip() or "RTMP",
                 server=self.server.text().strip(), enabled=self.enabled.isChecked())
        return d, self.key.text().strip()


# ============================================================================ styling

STYLE = """
* { outline: 0; }
QMainWindow, #root { background: #000000; }
QWidget { color: #d9dee7; }
#header { background: #0b0d10; border-bottom: 1px solid #1a1d24; }
#brand { font-weight: 800; color: #ffffff; font-size: 15px; letter-spacing: 0.3px; }
#pill { background: #14171d; border: 1px solid #1f232c; border-radius: 15px; }
#status { font-weight: 700; }
#device { color: #8a93a3; }
#toast { color: #c3c9d4; }
#panel { background: #0f1115; border-left: 1px solid #1c1f27; }
#rail { background: #0b0d10; border-left: 1px solid #1c1f27; }
#rail QToolButton { color: #8a93a3; background: transparent; border: 0; border-radius: 10px;
                    padding: 8px 2px; font-size: 11px; font-weight: 600; }
#rail QToolButton:hover { background: #14171d; color: #d9dee7; }
#rail QToolButton:checked { background: #1c2029; color: #ffffff; }
#pageTitle { font-size: 18px; font-weight: 700; color: #ffffff; padding: 2px 0 6px 0; }
#card { background: #14171d; border: 1px solid #1f232c; border-radius: 12px; }
#cardTitle { font-weight: 700; color: #ffffff; }
#muted { color: #8a93a3; }
#mono { font-family: %(mono)s; color: #c3c9d4; }
QPushButton { color: #e6e9ef; background: #1b1e25; border: 1px solid #272b35; border-radius: 9px; padding: 7px 13px; font-weight: 600; }
QPushButton:hover { background: #232731; border-color: #343a47; }
QPushButton:pressed { background: #15181e; }
QPushButton:disabled { color: #5b6270; }
QPushButton#icon { padding: 7px 10px; min-width: 22px; }
QPushButton#rec { padding: 8px 16px; }
QPushButton#rec:checked { background: %(accent)s; border-color: %(accent)s; color: #fff; }
QPushButton#live { padding: 8px 16px; }
QPushButton#live:checked { background: %(red)s; border-color: %(red)s; color: #fff; }
QPushButton#seg { padding: 6px 6px; }
QPushButton#seg:checked { background: %(accent)s; border-color: %(accent)s; color: #fff; }
QPushButton#flat { background: transparent; border: 0; padding: 4px 8px; color: #a7afbd; }
QPushButton#flat:hover { color: #fff; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a3f4b; background: #0f1115; }
QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; }
QComboBox, QLineEdit, QSpinBox { background: #0f1115; border: 1px solid #272b35; border-radius: 8px; padding: 6px 8px; color: #e6e9ef; }
QComboBox:focus, QLineEdit:focus, QSpinBox:focus { border-color: %(accent)s; }
QComboBox QAbstractItemView { background: #14171d; border: 1px solid #272b35; selection-background-color: #232731; }
QSlider::groove:horizontal { height: 4px; background: #272b35; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 2px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; background: #ffffff; }
QListWidget#list { background: #0d0f13; border: 1px solid #1f232c; border-radius: 8px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #272b35; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 8px; }
QScrollBar::handle:horizontal { background: #272b35; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QToolTip { color: #e6e9ef; background: #1b1e25; border: 1px solid #343a47; padding: 6px; }
QDialog, QMessageBox { background: #14171d; }
""" % {"accent": ACCENT, "red": LIVE_RED, "mono": MONO}


def card(title=None, hint=None):
    f = QtWidgets.QFrame(objectName="card")
    v = QtWidgets.QVBoxLayout(f)
    v.setContentsMargins(14, 12, 14, 14)
    v.setSpacing(9)
    if title:
        v.addWidget(QtWidgets.QLabel(title, objectName="cardTitle"))
    if hint:
        v.addWidget(muted(hint))
    return f, v


def labeled(text, widget):
    w = QtWidgets.QWidget()
    h = QtWidgets.QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    lbl = QtWidgets.QLabel(text)
    lbl.setWordWrap(True)
    lbl.setMinimumWidth(100)
    lbl.setMaximumWidth(140)
    h.addWidget(lbl)
    h.addWidget(widget, 1)
    return w


def glyph_icon(glyph):
    """A crisp icon (normal / selected colors) drawn from a text symbol."""
    icon = QtGui.QIcon()
    for mode, color in ((QtGui.QIcon.Mode.Normal, "#8a93a3"), (QtGui.QIcon.Mode.Active, "#ffffff"),
                        (QtGui.QIcon.Mode.Selected, "#ffffff")):
        for state, col in ((QtGui.QIcon.State.Off, color), (QtGui.QIcon.State.On, ACCENT)):
            pm = QtGui.QPixmap(64, 64)
            pm.fill(QtCore.Qt.GlobalColor.transparent)
            p = QtGui.QPainter(pm)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            f = QtGui.QFont()
            f.setPixelSize(40)
            p.setFont(f)
            p.setPen(QtGui.QColor(col))
            p.drawText(pm.rect(), int(QtCore.Qt.AlignmentFlag.AlignCenter), glyph)
            p.end()
            pm.setDevicePixelRatio(2.0)
            icon.addPixmap(pm, mode, state)
    return icon


def muted(text):
    lbl = QtWidgets.QLabel(text, objectName="muted")
    lbl.setWordWrap(True)
    return lbl


# ============================================================================ main window

PAGES = [("◉", "nav_broadcast"), ("◐", "nav_picture"), ("●", "nav_record"), ("∿", "nav_diag"), ("⚙", "nav_settings")]


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, demo_file=None):
        super(MainWindow, self).__init__()
        self.settings = QtCore.QSettings(APP_NAME, APP_NAME)
        set_language(self.settings.value("lang", "en", type=str))
        self.setWindowTitle(APP_NAME)
        self.resize(1480, 920)
        self.setMinimumSize(1000, 620)
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self.keys = Keys(self.settings)
        self.demo_file = demo_file
        self.token = secrets.token_hex(16)
        self.bridge = Bridge()
        self.shared = Shared()
        self._load_settings()
        self.out = OutputWorker(self.bridge, self.shared)
        self.worker = StreamWorker(self.bridge, self.token, self.shared, self.out)
        self.worker.auto_record = self.settings.value("auto_record", False, type=bool)
        self.worker.record_folder = self.settings.value("rec_folder", default_record_folder(), type=str)
        self.state = "starting"
        self.error_text = ""
        self.helper_proc = None
        self.helper_admin = False
        self.helper_uid = None
        self.device = ""
        self.stats = {}
        self.frames_shown = 0
        self.fps_shown = 0.0
        self.fps_t0 = time.monotonic()
        self.toast_until = 0.0
        self.live_since = None
        self.flight_since = None
        self.last_dropped = 0
        self.quality = 1.0
        self.mbps_hist = collections.deque(maxlen=60)
        self.detached = None
        self.thumb_t = 0.0
        self.caffeinate = None
        self.header = self.panel = self.rail = None
        self._build()
        self.bridge.event.connect(self.on_event)
        self.bridge.frame.connect(self.on_frame)
        self.out.start()
        self.worker.start()
        self._apply_outputs_from_settings()
        self.tick = QtCore.QTimer(self)
        self.tick.timeout.connect(self.on_tick)
        self.tick.start(200)
        self.fast_tick = QtCore.QTimer(self)            # only for the latency test clock
        self.fast_tick.timeout.connect(self.strip.update)
        self._set_latency(self.settings.value("latency_clock", False, type=bool))
        self.set_state("starting")
        QtCore.QTimer.singleShot(50, self.start_helper)

    # ------------------------------------------------------------------ settings
    def _load_settings(self):
        st = self.settings
        pic = self.shared.pic
        pic.stab = st.value("pic/stab", "off", type=str)
        pic.smooth = st.value("pic/smooth", True, type=bool)
        pic.roll = st.value("pic/roll", True, type=bool)
        pic.lens_fov = st.value("pic/lens_fov", 150, type=int)
        pic.straighten = st.value("pic/straighten", False, type=bool)
        pic.aspect = st.value("pic/aspect2", "auto", type=str)
        pic.pan = st.value("pic/pan", 0.0, type=float)
        pic.zoom = st.value("pic/zoom", 1.0, type=float)
        pic.rotate180 = st.value("pic/rotate180", False, type=bool)
        pic.mirror = st.value("pic/mirror", False, type=bool)
        self.shared.out_lines = st.value("out/lines", 1080, type=int)
        self.shared.out_kbps = st.value("out/kbps", 8000, type=int)
        self.shared.out_hw = st.value("out/hw", True, type=bool)
        try:
            self.dests = json.loads(st.value("dests", "[]", type=str))
        except ValueError:
            self.dests = []

    def save_pic(self):
        pic = self.shared.pic
        for k in ("stab", "smooth", "roll", "lens_fov", "straighten", "pan", "zoom", "rotate180", "mirror"):
            self.settings.setValue("pic/" + k, getattr(pic, k))
        self.settings.setValue("pic/aspect2", pic.aspect)

    def save_dests(self):
        self.settings.setValue("dests", json.dumps(self.dests))

    def _apply_outputs_from_settings(self):
        if self.settings.value("obs_on", False, type=bool):
            self.set_obs(True)
        if self.settings.value("web_on", False, type=bool):
            self.set_web(True)
        if self.settings.value("replay_on", False, type=bool):
            self.out.hub.set_replay(self.settings.value("replay_secs", 30, type=int))
        if self.settings.value("ontop", False, type=bool):
            self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        self.sync_buttons()

    # ------------------------------------------------------------------ layout
    def _build(self):
        root = QtWidgets.QWidget(objectName="root")
        self.root_v = QtWidgets.QVBoxLayout(root)
        self.root_v.setContentsMargins(0, 0, 0, 0)
        self.root_v.setSpacing(0)
        self.body = QtWidgets.QHBoxLayout()
        self.body.setSpacing(0)
        center = QtWidgets.QWidget()
        cv = QtWidgets.QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        self.view = VideoView()
        self.view.toggle_fullscreen.connect(self.toggle_fullscreen)
        self.view.resized.connect(self._update_target)
        cv.addWidget(self.view, 1)
        self.strip = InfoStrip()
        cv.addWidget(self.strip)
        self.body.addWidget(center, 1)
        self.root_v.addLayout(self.body, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)
        self._build_chrome()
        for key, fn in (("R", self.toggle_record), ("Space", self.toggle_record), ("F", self.toggle_fullscreen),
                        ("H", self.toggle_clean), ("S", self.snapshot), ("B", self.save_replay),
                        ("D", self.toggle_detach), ("Tab", self.toggle_panel), ("Escape", self.exit_fullscreen)):
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(fn)

    def _build_chrome(self):
        """(Re)build header, panel and rail - called again when the language changes."""
        page = self.current_page if self.panel is not None else self.settings.value("panel_page", 1, type=int)
        visible = self.panel.isVisible() if self.panel is not None else \
            self.settings.value("panel_visible", True, type=bool)
        for w in (self.header, self.panel, self.rail):
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.header = self._build_header()
        self.root_v.insertWidget(0, self.header)
        self.panel = self._build_panel()
        self.rail = self._build_rail()
        self.body.addWidget(self.panel)
        self.body.addWidget(self.rail)
        self.show_page(page, visible)
        self.set_state(self.state)
        self.sync_buttons()
        self.strip.update()

    def _build_header(self):
        bar = QtWidgets.QFrame(objectName="header")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(14, 8, 12, 8)
        h.setSpacing(8)
        logo = QtWidgets.QLabel()
        icon = os.path.join(getattr(sys, "_MEIPASS", ROOT), "assets", "icon.png")
        if os.path.exists(icon):
            pm = QtGui.QPixmap(icon)
            pm.setDevicePixelRatio(2.0)
            logo.setPixmap(pm.scaled(52, 52, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                     QtCore.Qt.TransformationMode.SmoothTransformation))
        h.addWidget(logo)
        h.addWidget(QtWidgets.QLabel(APP_NAME, objectName="brand"))
        h.addSpacing(10)
        pill = QtWidgets.QFrame(objectName="pill")
        ph = QtWidgets.QHBoxLayout(pill)
        ph.setContentsMargins(12, 5, 14, 5)
        ph.setSpacing(8)
        self.dot = QtWidgets.QLabel()
        self.dot.setFixedSize(10, 10)
        self.status = QtWidgets.QLabel(objectName="status")
        self.device_lbl = QtWidgets.QLabel(objectName="device")
        ph.addWidget(self.dot)
        ph.addWidget(self.status)
        ph.addWidget(self.device_lbl)
        h.addWidget(pill)
        self.reconnect_btn = QtWidgets.QPushButton(tr("btn_reconnect"))
        self.reconnect_btn.clicked.connect(self.reconnect)
        h.addWidget(self.reconnect_btn)
        h.addSpacing(10)
        self.toast_lbl = QtWidgets.QLabel(objectName="toast")
        self.toast_lbl.setMinimumWidth(40)
        self.toast_lbl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        h.addWidget(self.toast_lbl, 1)
        self.replay_btn = QtWidgets.QPushButton("⟲  " + tr("btn_replay"))
        self.replay_btn.setToolTip(tr("sc_replay") + " (B)")
        self.replay_btn.clicked.connect(self.save_replay)
        snap = QtWidgets.QPushButton("◎", objectName="icon")
        snap.setToolTip(tr("btn_snapshot") + " (S)")
        snap.clicked.connect(self.snapshot)
        self.rec_btn = QtWidgets.QPushButton(objectName="rec")
        self.rec_btn.setCheckable(True)
        self.rec_btn.setToolTip("R / Space")
        self.rec_btn.clicked.connect(lambda *_: self.toggle_record())
        self.live_btn = QtWidgets.QPushButton(objectName="live")
        self.live_btn.setCheckable(True)
        self.live_btn.clicked.connect(lambda *_: self.toggle_live())
        sep = QtWidgets.QFrame()
        sep.setFixedSize(1, 24)
        sep.setStyleSheet("background:#272b35;")
        self.detach_btn = QtWidgets.QPushButton("⧉", objectName="icon")
        self.detach_btn.clicked.connect(self.toggle_detach)
        full = QtWidgets.QPushButton("⛶", objectName="icon")
        full.setToolTip(tr("btn_fullscreen") + " (F)")
        full.clicked.connect(self.toggle_fullscreen)
        for w in (self.replay_btn, snap, self.rec_btn, self.live_btn, sep, self.detach_btn, full):
            h.addWidget(w)
        return bar

    def _build_panel(self):
        panel = QtWidgets.QFrame(objectName="panel")
        panel.setFixedWidth(380)
        v = QtWidgets.QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        self.stack = QtWidgets.QStackedWidget()
        builders = [self._page_broadcast, self._page_picture, self._page_record, self._page_diag, self._page_settings]
        for (glyph, key), builder in zip(PAGES, builders):
            inner = QtWidgets.QWidget()
            iv = QtWidgets.QVBoxLayout(inner)
            iv.setContentsMargins(16, 16, 16, 16)
            iv.setSpacing(12)
            iv.addWidget(QtWidgets.QLabel(tr(key), objectName="pageTitle"))
            builder(iv)
            iv.addStretch(1)
            self.stack.addWidget(VScroll(inner))
        v.addWidget(self.stack)
        return panel

    def _build_rail(self):
        rail = QtWidgets.QFrame(objectName="rail")
        rail.setFixedWidth(84)
        v = QtWidgets.QVBoxLayout(rail)
        v.setContentsMargins(6, 10, 6, 10)
        v.setSpacing(4)
        self.rail_btns = []
        for i, (glyph, key) in enumerate(PAGES):
            b = QtWidgets.QToolButton()
            b.setText(tr(key))
            b.setIcon(glyph_icon(glyph))
            b.setIconSize(QtCore.QSize(26, 26))
            b.setCheckable(True)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.setMinimumHeight(58)
            b.clicked.connect(lambda _=False, idx=i: self.on_rail(idx))
            v.addWidget(b)
            self.rail_btns.append(b)
        v.addStretch(1)
        return rail

    def on_rail(self, idx):
        if self.panel.isVisible() and self.current_page == idx:
            self.show_page(idx, False)                # clicking the open tab collapses the panel
        else:
            self.show_page(idx, True)

    def show_page(self, idx, visible):
        self.current_page = idx
        self.stack.setCurrentIndex(idx)
        self.panel.setVisible(visible)
        for i, b in enumerate(self.rail_btns):
            b.setChecked(visible and i == idx)
        self.settings.setValue("panel_page", idx)
        self.settings.setValue("panel_visible", visible)

    # ---- pages -----------------------------------------------------------
    def _page_broadcast(self, v):
        c, cv = card(tr("bc_destinations"))
        self.dest_box = QtWidgets.QVBoxLayout()
        self.dest_box.setSpacing(6)
        cv.addLayout(self.dest_box)
        add = QtWidgets.QPushButton("+  " + tr("bc_add"))
        add.clicked.connect(lambda: self.edit_dest(None))
        cv.addWidget(add)
        cv.addWidget(muted(tr("bc_vertical_hint")))
        v.addWidget(c)
        self.render_dests()

        c, cv = card(tr("bc_quality"))
        res = QtWidgets.QComboBox()
        for lines in R.LINES:
            res.addItem("%dp" % lines, lines)
        res.setCurrentIndex(max(0, res.findData(self.shared.out_lines)))
        res.currentIndexChanged.connect(lambda i: self._set_out("lines", res.currentData()))
        cv.addWidget(labeled(tr("bc_resolution"), res))
        br = QtWidgets.QComboBox()
        for kb in (3000, 4500, 6000, 8000, 12000, 16000, 20000):
            br.addItem("%g Mbit/s" % (kb / 1000.0), kb)
        br.setCurrentIndex(max(0, br.findData(self.shared.out_kbps)))
        br.currentIndexChanged.connect(lambda i: self._set_out("kbps", br.currentData()))
        cv.addWidget(labeled(tr("bc_bitrate"), br))
        enc = QtWidgets.QComboBox()
        enc.addItem(tr("enc_hw"), True)
        enc.addItem(tr("enc_sw"), False)
        enc.setCurrentIndex(0 if self.shared.out_hw else 1)
        enc.currentIndexChanged.connect(lambda i: self._set_out("hw", enc.currentData()))
        cv.addWidget(labeled(tr("bc_encoder"), enc))
        audio = WrapCheck(tr("bc_audio"))
        audio.setChecked(self.settings.value("audio", True, type=bool))
        audio.toggled.connect(lambda on: self.settings.setValue("audio", on))
        cv.addWidget(audio)
        v.addWidget(c)

        c, cv = card(tr("bc_local"))
        self.obs_cb = WrapCheck(tr("bc_obs"))
        self.obs_cb.setChecked("obs" in self.out.hub.sinks)
        self.obs_cb.toggled.connect(self.set_obs)
        cv.addWidget(self.obs_cb)
        obs_url = "udp://127.0.0.1:%d" % self.settings.value("obs_port", 5600, type=int)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(obs_url, objectName="mono"), 1)
        cp = QtWidgets.QPushButton(tr("bc_copy"), objectName="flat")
        cp.clicked.connect(lambda: self.copy(obs_url))
        row.addWidget(cp)
        cv.addLayout(row)
        cv.addWidget(muted(tr("bc_obs_hint") + " " + obs_url))
        sep = QtWidgets.QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#1f232c;")
        cv.addWidget(sep)
        self.web_cb = WrapCheck(tr("bc_web"))
        self.web_cb.setChecked(self.out.web is not None)
        self.web_cb.toggled.connect(self.set_web)
        cv.addWidget(self.web_cb)
        webrow = QtWidgets.QHBoxLayout()
        self.qr = QrWidget()
        webrow.addWidget(self.qr)
        col = QtWidgets.QVBoxLayout()
        self.web_url = QtWidgets.QLabel("", objectName="mono")
        self.web_url.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.web_url.setWordWrap(True)
        col.addWidget(self.web_url)
        cpw = QtWidgets.QPushButton(tr("bc_copy"), objectName="flat")
        cpw.clicked.connect(lambda: self.copy(self.web_url.text().split("\n")[0]))
        col.addWidget(cpw, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.web_clients = QtWidgets.QLabel("", objectName="muted")
        col.addWidget(self.web_clients)
        col.addStretch(1)
        webrow.addLayout(col, 1)
        self.web_panel = QtWidgets.QWidget()
        self.web_panel.setLayout(webrow)
        cv.addWidget(self.web_panel)
        cv.addWidget(muted(tr("bc_web_hint")))
        v.addWidget(c)
        self._refresh_web_panel()

    def _page_picture(self, v):
        pic = self.shared.pic
        c, cv = card(tr("pic_stab"))
        self.stab_seg = Segmented([(k, tr("stab_" + k)) for k in ("off", "low", "medium", "high", "max")], pic.stab)
        self.stab_seg.picked.connect(lambda k: self._set_pic("stab", k))
        cv.addWidget(self.stab_seg)
        mode = QtWidgets.QComboBox()
        mode.addItem(tr("mode_smooth"), True)
        mode.addItem(tr("mode_live"), False)
        mode.setCurrentIndex(0 if pic.smooth else 1)
        mode.currentIndexChanged.connect(lambda i: self._set_pic("smooth", mode.currentData()))
        cv.addWidget(labeled(tr("pic_mode"), mode))
        cv.addWidget(muted(tr("pic_mode_hint")))
        roll = WrapCheck(tr("pic_roll"))
        roll.setChecked(pic.roll)
        roll.toggled.connect(lambda on: self._set_pic("roll", on))
        cv.addWidget(roll)
        if not S.available():
            cv.addWidget(muted("OpenCV not available: stabilization disabled."))
        v.addWidget(c)

        c, cv = card(tr("pic_lens"), tr("pic_lens_hint"))
        fov = QtWidgets.QComboBox()
        for d in S.LENS_FOVS:
            fov.addItem("%d°" % d, d)
        fov.setCurrentIndex(max(0, fov.findData(pic.lens_fov)))
        fov.currentIndexChanged.connect(lambda i: self._set_pic("lens_fov", fov.currentData()))
        cv.addWidget(fov)
        st = WrapCheck(tr("pic_straighten"))
        st.setChecked(pic.straighten)
        st.toggled.connect(lambda on: self._set_pic("straighten", on))
        cv.addWidget(st)
        v.addWidget(c)

        c, cv = card(tr("pic_framing"))
        cv.addWidget(QtWidgets.QLabel(tr("pic_aspect")))
        self.aspect_seg = Segmented([("auto", tr("aspect_auto"))] + [(a, a) for a in ("16:9", "9:16", "1:1", "4:5", "4:3")],
                                    pic.aspect)
        self.aspect_seg.picked.connect(lambda k: self._set_pic("aspect", k))
        cv.addWidget(self.aspect_seg)
        cv.addWidget(muted(tr("aspect_auto_hint")))
        self.pan_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.pan_slider.setRange(-100, 100)
        self.pan_slider.setValue(int(pic.pan * 100))
        self.pan_slider.valueChanged.connect(lambda val: self._set_pic("pan", val / 100.0))
        cv.addWidget(labeled(tr("pic_pan"), self.pan_slider))
        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(100, 200)
        self.zoom_slider.setValue(int(pic.zoom * 100))
        self.zoom_slider.valueChanged.connect(lambda val: self._set_pic("zoom", val / 100.0))
        cv.addWidget(labeled(tr("pic_zoom"), self.zoom_slider))
        self.rot_cb = WrapCheck(tr("pic_rotate"))
        self.rot_cb.setChecked(pic.rotate180)
        self.rot_cb.toggled.connect(lambda on: self._set_pic("rotate180", on))
        self.mir_cb = WrapCheck(tr("pic_mirror"))
        self.mir_cb.setChecked(pic.mirror)
        self.mir_cb.toggled.connect(lambda on: self._set_pic("mirror", on))
        cv.addWidget(self.rot_cb)
        cv.addWidget(self.mir_cb)
        reset = QtWidgets.QPushButton(tr("pic_reset"))
        reset.clicked.connect(self.reset_framing)
        cv.addWidget(reset, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        v.addWidget(c)

    def _page_record(self, v):
        c, cv = card(tr("rec_folder"))
        self.folder_lbl = QtWidgets.QLabel(self.worker.record_folder, objectName="mono")
        self.folder_lbl.setWordWrap(True)
        cv.addWidget(self.folder_lbl)
        self.free_lbl = QtWidgets.QLabel("", objectName="muted")
        cv.addWidget(self.free_lbl)
        row = QtWidgets.QHBoxLayout()
        ch = QtWidgets.QPushButton(tr("rec_change"))
        ch.clicked.connect(self.choose_folder)
        op = QtWidgets.QPushButton(tr("rec_open"))
        op.clicked.connect(self.open_folder)
        row.addWidget(ch)
        row.addWidget(op)
        row.addStretch(1)
        cv.addLayout(row)
        v.addWidget(c)
        c, cv = card(tr("nav_record"))
        auto = WrapCheck(tr("rec_auto"))
        auto.setChecked(self.worker.auto_record)
        auto.toggled.connect(self.set_auto_record)
        cv.addWidget(auto)
        cv.addWidget(muted(tr("rec_auto_hint")))
        orig = WrapCheck(tr("rec_original"))
        orig.setChecked(True)
        orig.setEnabled(False)
        cv.addWidget(orig)
        proc = WrapCheck(tr("rec_processed"))
        proc.setChecked(self.settings.value("rec_processed", False, type=bool))
        proc.toggled.connect(lambda on: self.settings.setValue("rec_processed", on))
        cv.addWidget(proc)
        v.addWidget(c)
        c, cv = card(tr("rec_replay"), tr("rec_replay_hint"))
        rp = WrapCheck(tr("on"))
        rp.setChecked(self.out.hub.replay is not None)
        secs = QtWidgets.QComboBox()
        for s in (15, 30, 60, 120):
            secs.addItem(tr("rec_replay_keep", n=s), s)
        secs.setCurrentIndex(max(0, secs.findData(self.settings.value("replay_secs", 30, type=int))))

        def apply_replay(*_):
            on = rp.isChecked()
            self.settings.setValue("replay_on", on)
            self.settings.setValue("replay_secs", secs.currentData())
            self.out.hub.set_replay(secs.currentData() if on else 0)
            self.sync_buttons()
        rp.toggled.connect(apply_replay)
        secs.currentIndexChanged.connect(apply_replay)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(rp)
        row.addWidget(secs, 1)
        cv.addLayout(row)
        self.replay_lbl = QtWidgets.QLabel("", objectName="muted")
        cv.addWidget(self.replay_lbl)
        v.addWidget(c)
        c, cv = card(tr("rec_recent"))
        self.recent_list = QtWidgets.QListWidget(objectName="list")
        self.recent_list.setMinimumHeight(150)
        self.recent_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setTextElideMode(QtCore.Qt.TextElideMode.ElideMiddle)
        self.recent_list.itemDoubleClicked.connect(
            lambda it: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(it.data(QtCore.Qt.ItemDataRole.UserRole))))
        cv.addWidget(self.recent_list)
        v.addWidget(c)
        self.refresh_recent()

    def _page_diag(self, v):
        c, cv = card(None)
        cv.addWidget(QtWidgets.QLabel(tr("dg_bitrate")))
        self.g_mbps = Sparkline(ACCENT)
        cv.addWidget(self.g_mbps)
        cv.addWidget(QtWidgets.QLabel(tr("dg_fps")))
        self.g_fps = Sparkline(GREEN, "{:.0f}")
        cv.addWidget(self.g_fps)
        cv.addWidget(QtWidgets.QLabel(tr("dg_proc")))
        self.g_ms = Sparkline("#5aa9ff")
        cv.addWidget(self.g_ms)
        v.addWidget(c)
        c, cv = card(None)
        self.diag_info = QtWidgets.QLabel("", objectName="mono")
        self.diag_info.setWordWrap(True)
        self.diag_info.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        cv.addWidget(self.diag_info)
        cp = QtWidgets.QPushButton(tr("dg_copy"))
        cp.clicked.connect(lambda: self.copy(self.diag_info.text()))
        cv.addWidget(cp, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        v.addWidget(c)
        c, cv = card(tr("dg_capture"), tr("dg_capture_hint"))
        self.cap_btn = QtWidgets.QPushButton(objectName="rec")
        self.cap_btn.setCheckable(True)
        self.cap_btn.clicked.connect(lambda on: self.worker.set_capture(on))
        cv.addWidget(self.cap_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.cap_lbl = QtWidgets.QLabel("", objectName="muted")
        cv.addWidget(self.cap_lbl)
        cv.addWidget(QtWidgets.QLabel(tr("dg_strings")))
        self.strings_list = QtWidgets.QListWidget(objectName="list")
        self.strings_list.setMinimumHeight(120)
        cv.addWidget(self.strings_list)
        v.addWidget(c)

    def _page_settings(self, v):
        c, cv = card(tr("set_language"))
        lang = QtWidgets.QComboBox()
        for code, name in LANGS:
            lang.addItem(name, code)
        lang.setCurrentIndex(max(0, lang.findData(self.settings.value("lang", "en", type=str))))
        lang.currentIndexChanged.connect(lambda i: QtCore.QTimer.singleShot(0, lambda: self.set_language(lang.currentData())))
        cv.addWidget(lang)
        v.addWidget(c)
        c, cv = card(None)
        lat = WrapCheck(tr("set_latency"))
        lat.setChecked(self.strip.latency)
        lat.toggled.connect(self._set_latency)
        cv.addWidget(lat)
        cv.addWidget(muted(tr("ov_latency_hint")))
        awake = WrapCheck(tr("set_awake"))
        awake.setChecked(self.settings.value("awake", True, type=bool))
        awake.toggled.connect(lambda on: self.settings.setValue("awake", on))
        cv.addWidget(awake)
        top = WrapCheck(tr("set_ontop"))
        top.setChecked(self.settings.value("ontop", False, type=bool))
        top.toggled.connect(self.set_on_top)
        cv.addWidget(top)
        port = QtWidgets.QSpinBox()
        port.setRange(1024, 65535)
        port.setValue(self.settings.value("web_port", 8090, type=int))
        port.valueChanged.connect(self._set_web_port)
        cv.addWidget(labeled(tr("set_web_port"), port))
        row = QtWidgets.QHBoxLayout()
        reset = QtWidgets.QPushButton(tr("set_reset_perm"))
        reset.clicked.connect(lambda: self.settings.setValue("needs_admin", False))
        reset_all = QtWidgets.QPushButton(tr("set_reset_all"))
        reset_all.clicked.connect(self.reset_all)
        row.addWidget(reset)
        row.addWidget(reset_all)
        row.addStretch(1)
        cv.addLayout(row)
        v.addWidget(c)
        c, cv = card(tr("set_shortcuts"))
        grid = QtWidgets.QGridLayout()
        for row_i, (k, key) in enumerate((("R / Space", "sc_rec"), ("S", "sc_snapshot"), ("B", "sc_replay"),
                                          ("D", "sc_detach"), ("F", "sc_full"), ("H", "sc_hide"),
                                          ("Tab", "sc_panel"), ("Esc", "sc_esc"))):
            grid.addWidget(QtWidgets.QLabel(k, objectName="mono"), row_i, 0)
            lbl = QtWidgets.QLabel(tr(key))
            lbl.setWordWrap(True)
            grid.addWidget(lbl, row_i, 1)
        grid.setColumnStretch(1, 1)
        cv.addLayout(grid)
        v.addWidget(c)
        c, cv = card(tr("set_about"))
        cv.addWidget(QtWidgets.QLabel("%s %s" % (APP_NAME, __version__), objectName="cardTitle"))
        cv.addWidget(muted(tr("set_about_text")))
        v.addWidget(c)

    # ------------------------------------------------------------------ setters
    def _set_pic(self, key, value):
        setattr(self.shared.pic, key, value)
        self.save_pic()

    def reset_framing(self):
        for key, val in (("aspect", "auto"), ("pan", 0.0), ("zoom", 1.0), ("rotate180", False), ("mirror", False)):
            setattr(self.shared.pic, key, val)
        self.aspect_seg.set_value("auto")
        for w, val in ((self.pan_slider, 0), (self.zoom_slider, 100)):
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)
        self.rot_cb.setChecked(False)
        self.mir_cb.setChecked(False)
        self.save_pic()

    def _set_out(self, key, value):
        setattr(self.shared, "out_" + key, value)
        self.settings.setValue("out/" + key, value)

    def _set_latency(self, on):
        self.strip.latency = on
        self.settings.setValue("latency_clock", on)
        self.fast_tick.start(16) if on else self.fast_tick.stop()
        self.strip.update()

    def set_language(self, code):
        self.settings.setValue("lang", code)
        set_language(code)
        self._build_chrome()

    def set_on_top(self, on):
        self.settings.setValue("ontop", on)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()

    def set_auto_record(self, on):
        self.worker.auto_record = on
        self.settings.setValue("auto_record", on)

    def reset_all(self):
        if QtWidgets.QMessageBox.question(self, APP_NAME, tr("set_reset_all") + "?") != \
                QtWidgets.QMessageBox.StandardButton.Yes:
            return
        keep = {k: self.settings.value(k) for k in ("dests", "lang")}
        self.settings.clear()
        for k, val in keep.items():
            if val is not None:
                self.settings.setValue(k, val)
        self._load_settings()
        self._build_chrome()

    def copy(self, text):
        QtWidgets.QApplication.clipboard().setText(text)
        self.show_flash(tr("bc_copied"))

    # ------------------------------------------------------------------ destinations / live
    def render_dests(self):
        while self.dest_box.count():
            it = self.dest_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.dest_rows = {}
        if not self.dests:
            self.dest_box.addWidget(muted(tr("bc_none")))
            return
        for d in self.dests:
            row = QtWidgets.QFrame(objectName="destrow")
            row.setStyleSheet("#destrow{background:#0f1115;border:1px solid #1f232c;border-radius:9px;}")
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(10, 6, 6, 6)
            h.setSpacing(8)
            en = QtWidgets.QCheckBox()
            en.setChecked(d.get("enabled", True))
            en.toggled.connect(lambda on, dd=d: (dd.__setitem__("enabled", on), self.save_dests()))
            dot = QtWidgets.QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet("background:%s;border-radius:5px;" % PLATFORM.get(d.get("platform"), PLATFORMS[-1])[3])
            name = QtWidgets.QLabel("<b>%s</b>" % d.get("name", "RTMP"))
            state = QtWidgets.QLabel("", objectName="muted")
            edit = QtWidgets.QPushButton(tr("bc_edit"), objectName="flat")
            edit.clicked.connect(lambda _=False, dd=d: self.edit_dest(dd))
            rm = QtWidgets.QPushButton("✕", objectName="flat")
            rm.setToolTip(tr("bc_remove"))
            rm.clicked.connect(lambda _=False, dd=d: self.remove_dest(dd))
            for w in (en, dot, name):
                h.addWidget(w)
            h.addWidget(state, 1)
            h.addWidget(edit)
            h.addWidget(rm)
            self.dest_box.addWidget(row)
            self.dest_rows[d["id"]] = state

    def edit_dest(self, dest):
        new = dest is None
        d = dest or {"id": uuid.uuid4().hex[:12], "platform": "youtube", "enabled": True}
        dlg = DestinationDialog(self, d, "" if new else self.keys.get(d["id"]))
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        nd, key = dlg.result_dest()
        self.keys.set(nd["id"], key)
        if new:
            self.dests.append(nd)
        else:
            self.dests[self.dests.index(dest)] = nd
        self.save_dests()
        self.render_dests()

    def remove_dest(self, dest):
        self.keys.delete(dest["id"])
        self.out.hub.remove_sink("dest:" + dest["id"])
        self.dests.remove(dest)
        self.save_dests()
        self.render_dests()

    def toggle_live(self):
        if self.live_since is not None:
            ans = QtWidgets.QMessageBox.question(self, APP_NAME, tr("confirm_end"))
            if ans == QtWidgets.QMessageBox.StandardButton.Yes:
                self.end_live()
            self.sync_buttons()
            return
        targets = [d for d in self.dests if d.get("enabled", True) and d.get("server")]
        if not targets:
            self.show_flash(tr("live_need_dest"))
            self.show_page(0, True)
            self.sync_buttons()
            return
        audio = self.settings.value("audio", True, type=bool)
        for d in targets:
            try:
                url, opts, bridge = rtmp_target(d["server"], self.keys.get(d["id"]))
            except Exception as e:
                self.show_flash("%s: %s" % (d.get("name"), e))
                continue
            self.out.hub.add_sink(MuxSink("dest:" + d["id"], url, "flv", opts, audio=audio, bridge=bridge))
        self.live_since = time.monotonic()
        self.show_flash(tr("live_started", n=len(targets)))
        self.sync_buttons()

    def end_live(self):
        for name in list(self.out.hub.sinks):
            if name.startswith("dest:"):
                self.out.hub.remove_sink(name)
        self.live_since = None
        self.show_flash(tr("live_ended"))

    def set_obs(self, on):
        self.settings.setValue("obs_on", on)
        if hasattr(self, "obs_cb") and self.obs_cb.isChecked() != on:
            self.obs_cb.blockSignals(True)
            self.obs_cb.setChecked(on)
            self.obs_cb.blockSignals(False)
        if on:
            port = self.settings.value("obs_port", 5600, type=int)
            self.out.hub.add_sink(MuxSink("obs", "udp://127.0.0.1:%d?pkt_size=1316" % port, "mpegts"))
        else:
            self.out.hub.remove_sink("obs")

    def set_web(self, on):
        from .webview import WebViewer
        self.settings.setValue("web_on", on)
        if on and self.out.web is None:
            web = WebViewer(self.settings.value("web_port", 8090, type=int), APP_NAME, tr("bn_reconnecting"))
            if web.start():
                self.out.web = web
            else:
                self.show_flash(tr("web_failed", err=web.error))
                self.settings.setValue("web_on", False)
        elif not on and self.out.web is not None:
            self.out.web.stop()
            self.out.web = None
        self._refresh_web_panel()

    def _set_web_port(self, port):
        self.settings.setValue("web_port", port)
        if self.out.web is not None:
            self.set_web(False)
            self.set_web(True)

    def _refresh_web_panel(self):
        if not hasattr(self, "web_panel"):
            return
        web = self.out.web
        self.web_cb.blockSignals(True)
        self.web_cb.setChecked(web is not None)
        self.web_cb.blockSignals(False)
        self.web_panel.setVisible(web is not None)
        if web is not None:
            urls = web.urls()
            self.web_url.setText("\n".join(urls))
            self.qr.set_text(urls[0])

    # ------------------------------------------------------------------ detach
    def toggle_detach(self):
        if self.detached is None:
            win = VideoWindow()
            geo = self.settings.value("detached_geometry")
            if geo is not None:
                win.restoreGeometry(geo)
            win.closed.connect(self._on_detached_closed)
            win.view.resized.connect(self._update_target)
            self.detached = win
            win.show()
            if self.settings.value("detached_full", False, type=bool):
                win.showFullScreen()
        else:
            self.detached.close()
        self._update_target()
        self.set_state(self.state)
        self.sync_buttons()

    def _on_detached_closed(self):
        win, self.detached = self.detached, None
        if win is not None:
            self.settings.setValue("detached_full", win.isFullScreen())
            if not win.isFullScreen():
                self.settings.setValue("detached_geometry", win.saveGeometry())
        self._update_target()
        self.set_state(self.state)
        self.sync_buttons()

    def _update_target(self):
        v = self.detached.view if self.detached is not None else self.view
        self.worker.set_target(v.width(), v.height(), v.devicePixelRatioF())

    # ------------------------------------------------------------------ helper process
    def helper_command(self):
        cmd = [sys.executable, "--helper"] if is_frozen() else [sys.executable, "-m", "g3.helper"]
        cmd += ["--port", str(self.worker.port), "--token", self.token]
        if self.demo_file:
            cmd += ["--simulate", os.path.abspath(self.demo_file)]
        return cmd

    def start_helper(self, admin=None):
        if admin is None:
            admin = self.settings.value("needs_admin", False, type=bool)
        if self.demo_file or is_root() or sys.platform != "darwin":
            admin = False
        self.helper_admin = admin
        cmd = self.helper_command()
        env = dict(os.environ)
        if not is_frozen():
            env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
        if not admin:
            flags = 0x08000000 if sys.platform.startswith("win") else 0
            self.helper_proc = subprocess.Popen(cmd, cwd=ROOT if not is_frozen() else None, env=env,
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL, creationflags=flags)
            return
        self.set_state("needs_admin")
        shell = " ".join(shlex.quote(c) for c in cmd) + " >/dev/null 2>&1 &"
        if not is_frozen():
            shell = "cd %s && PYTHONPATH=%s %s" % (shlex.quote(ROOT), shlex.quote(ROOT), shell)
        prompt = "%s: %s" % (APP_NAME, tr("bn_admin_b"))
        script = "do shell script %s with prompt %s with administrator privileges" % (
            applescript_quote(shell), applescript_quote(prompt))

        def ask():
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if r.returncode != 0:
                self.bridge.event.emit({"type": "state", "state": "admin_denied"})
        threading.Thread(target=ask, daemon=True).start()

    def reconnect(self):
        self.worker.drop_connection()
        if self.helper_proc and self.helper_proc.poll() is None:
            self.helper_proc.terminate()
        self.helper_proc = None
        self.view.image = None
        self.set_state("starting")
        QtCore.QTimer.singleShot(400, self.start_helper)

    def _keep_awake(self, on):
        """macOS: stop the display from sleeping while video is live (caffeinate)."""
        if sys.platform != "darwin":
            return
        on = on and self.settings.value("awake", True, type=bool)
        if on and self.caffeinate is None:
            try:
                self.caffeinate = subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(os.getpid())])
            except OSError:
                self.caffeinate = None
        elif not on and self.caffeinate is not None:
            self.caffeinate.terminate()
            self.caffeinate = None

    # ------------------------------------------------------------------ events
    @QtCore.Slot()
    def on_frame(self):
        img = self.worker.take_frame()
        if img is None:
            return
        self.frames_shown += 1
        if self.detached is not None:
            self.detached.view.image = img
            self.detached.view.update()
            now = time.monotonic()
            if now - self.thumb_t > 0.1:          # main window: light 10 fps preview
                self.thumb_t = now
                self.view.image = img
                self.view.update()
        else:
            self.view.image = img
            self.view.update()

    @QtCore.Slot(dict)
    def on_event(self, ev):
        t = ev.get("type")
        if t == "state":
            s = ev.get("state")
            if s == "needs_admin":
                self.settings.setValue("needs_admin", True)
                if not self.helper_admin:
                    self.start_helper(admin=True)
                    return
            if s == "error":
                msg = (ev.get("message") or "").strip()
                self.error_text = msg.splitlines()[0] if msg else ""
            if s == "live" and self.flight_since is None:
                self.flight_since = time.monotonic()
            if s in ("searching", "disconnected", "stalled"):
                self.flight_since = None
            if s in STATES:
                self.set_state(s)
        elif t == "stats":
            dropped = ev.get("dropped", 0)
            fps = ev.get("fps", 0.0)
            delta = max(0, dropped - self.last_dropped)
            self.last_dropped = dropped
            self.quality = max(0.0, min(1.0, fps / 50.0)) * max(0.0, 1.0 - delta / 6.0)
            self.mbps_hist.append(ev.get("mbps", 0.0))
            self.stats = ev
            try:
                self.g_mbps.push(ev.get("mbps", 0.0))
                self.g_fps.push(fps)
                ms = list(self.worker.proc_ms)
                self.g_ms.push(sum(ms) / len(ms) if ms else 0.0)
            except (RuntimeError, AttributeError):
                pass
        elif t == "connected":
            self.device = ev.get("device", "")
            self.last_dropped = 0
            self.set_state("connected")
        elif t == "hello":
            self.helper_uid = ev.get("uid")
            if ev.get("uid") == 0:
                self.settings.setValue("needs_admin", True)
        elif t == "helper_gone":
            if self.state not in ("admin_denied", "starting", "needs_admin"):
                self.set_state("helper_gone")
            self.stop_record()
        elif t == "rec_started":
            if self.settings.value("rec_processed", False, type=bool):
                path = ev["path"][:-4] + "_processed.mp4"
                self.out.hub.add_sink(MuxSink("processed", path, "mp4", {"movflags": "+faststart"}, retry=False))
            self.sync_buttons()
        elif t == "rec_saved":
            if ev.get("path"):
                self.show_flash(tr("rec_saved", name=os.path.basename(ev["path"])))
            self.refresh_recent()
        elif t == "snapshot":
            if ev.get("ok"):
                self.show_flash(tr("snapshot_saved", name=os.path.basename(ev["path"])))
            self.refresh_recent()
        elif t == "replay_saved":
            if ev.get("ok"):
                self.show_flash(tr("replay_saved", name=os.path.basename(ev["path"])))
            self.refresh_recent()
        elif t == "enc_error":
            self.show_flash(tr("enc_failed", err=ev.get("message", "")))

    def set_state(self, s):
        self.state = s
        skey, color, tkey, bkey = STATES.get(s, STATES["error"])
        self.status.setText(tr(skey))
        self.dot.setStyleSheet("background:%s;border-radius:5px;" % color)
        self.device_lbl.setText(self.device.split(" (")[0] if s == "live" and self.device else "")
        if tkey is None:
            banner, dim = None, False
        else:
            body = tr(bkey) if bkey else ""
            if s == "error" and self.error_text:
                body = self.error_text
            banner, dim = (tr(tkey), body, color), s in ("stalled", "disconnected", "waiting for keyframe")
            if s in ("searching", "connected", "disconnected", "helper_gone"):
                self.worker.armed = True
        if self.detached is not None:
            self.detached.view.banner, self.detached.view.dim = banner, dim
            self.detached.view.update()
            self.view.banner, self.view.dim = (tr("detached_t"), tr("detached_b"), IDLE), True
        else:
            self.view.banner, self.view.dim = banner, dim
        self.reconnect_btn.setVisible(s in ("admin_denied", "error", "helper_gone", "stalled", "disconnected"))
        self.view.update()
        self._keep_awake(s == "live")

    def sync_buttons(self):
        if self.header is None:
            return
        rec = self.worker.recorder is not None
        self.rec_btn.setChecked(rec)
        self.rec_btn.setText(("■  " + tr("btn_stop")) if rec else "●  " + tr("btn_rec"))
        live = self.live_since is not None
        self.live_btn.setChecked(live)
        self.live_btn.setText(("■  " + tr("btn_endlive")) if live else "◉  " + tr("btn_golive"))
        self.replay_btn.setVisible(self.out.hub.replay is not None)
        self.detach_btn.setToolTip((tr("btn_attach") if self.detached else tr("btn_detach")) + " (D)")

    def on_tick(self):
        now = time.monotonic()
        if now - self.fps_t0 >= 1.0:
            self.fps_shown = self.frames_shown / (now - self.fps_t0)
            self.frames_shown, self.fps_t0 = 0, now
        status = self.out.hub.status()
        dest_states = [st for k, st in status.items() if k.startswith("dest:")]
        live_extra = ""
        if dest_states:
            live_extra = "  %d/%d" % (sum(1 for st in dest_states if st["state"] == "live"), len(dest_states))
        pic = self.shared.pic
        stab_txt = ""
        if pic.stab != "off" and S.available():
            stab_txt = tr("stab_" + pic.stab) + ("  %.2fs" % (self.worker.stab_delay / 56.0) if pic.smooth else "")
        v = self.worker.voltage
        self.strip.data = {
            "fps": self.fps_shown if self.state == "live" else None,
            "mbps": self.stats.get("mbps", 0.0), "quality": self.quality, "mbps_hist": list(self.mbps_hist),
            "flight_s": (now - self.flight_since) if self.flight_since else None,
            "rec_s": self.worker.recording_elapsed(),
            "live_s": (now - self.live_since) if self.live_since else None, "live_extra": live_extra,
            "voltage": v[0] if v and now - v[1] < 5.0 else None,
            "stab": stab_txt,
        }
        self._render_toast()
        self.strip.update()
        self.sync_buttons()
        if self.panel.isVisible():
            self._tick_panel(status)
        if self.out.web is not None:
            self.out.web.status = {"live": self.state == "live", "fps": round(self.fps_shown, 1)}

    def _tick_panel(self, status):
        page = self.current_page
        cur = self.stack.currentWidget()
        if isinstance(cur, VScroll):
            cur.fit()
        if page == 0:
            for d in self.dests:
                lbl = self.dest_rows.get(d["id"])
                if lbl is None:
                    continue
                st = status.get("dest:" + d["id"])
                if not st:
                    lbl.setText(tr("state_off"))
                elif st["state"] == "live":
                    lbl.setText("<span style='color:%s'>● %s</span> · %.1f Mbit/s" % (
                        LIVE_RED, tr("state_live"), st["rate"] / 1e6))
                elif st["state"] == "error":
                    lbl.setText("<span style='color:%s'>%s</span>" % (ERR, tr("state_error")))
                    lbl.setToolTip(st["error"])
                elif self.out.hub.encoder is None:
                    lbl.setText(tr("state_waiting"))
                else:
                    lbl.setText(tr("state_connecting"))
            if self.out.web is not None:
                n = self.out.web.clients
                self.web_clients.setText("● %d" % n if n else "")
        elif page == 2:
            rp = self.out.hub.replay
            self.replay_lbl.setText(("%.0f s" % rp.duration()) if rp else "")
            try:
                free = shutil.disk_usage(self.worker.record_folder if os.path.isdir(self.worker.record_folder)
                                         else os.path.expanduser("~")).free / 1e9
                self.free_lbl.setText(tr("rec_free", gb=free))
            except OSError:
                pass
        elif page == 3:
            pkt = self.stats.get("types", {})
            ms = list(self.worker.proc_ms)
            oms = list(self.out.ms)
            lines = [
                "%s: %s" % (tr("dg_device"), self.device or tr("dg_none")),
                "%s: %s" % (tr("dg_helper"), tr("dg_admin") if self.helper_uid == 0 else
                            tr("dg_user") if self.helper_uid is not None else tr("dg_none")),
                "Video: %s  %.0f fps" % ("%dx%d" % self.worker.src_size if self.worker.src_size else "—",
                                         self.fps_shown),
                "%s: %d" % (tr("dg_dropped"), self.stats.get("dropped", 0)),
                "%s: %s" % (tr("dg_packets"), ", ".join("%s=%d" % kv for kv in sorted(pkt.items())) or "—"),
                "Preview: %.1f ms   Output: %.1f ms" % (sum(ms) / len(ms) if ms else 0,
                                                       sum(oms) / len(oms) if oms else 0),
                "%s: %s" % (tr("dg_encoder"), self.out.encoder_name() or tr("dg_none")),
                "%s %s · PyAV %s · %s" % (APP_NAME, __version__, av.__version__, sys.platform),
            ]
            self.diag_info.setText("\n".join(lines))
            on = self.worker.capture is not None
            self.cap_btn.setChecked(on)
            self.cap_btn.setText(tr("dg_capture_stop") if on else tr("dg_capture_start"))
            if self.worker.capture_path:
                self.cap_lbl.setText("%d · %s" % (self.worker.capture_count,
                                                  os.path.basename(self.worker.capture_path)))
            top = self.worker.strings.most_common(30)
            if self.strings_list.count() != len(top) or (top and self.strings_list.item(0).text() != "%s   ×%d" % top[0]):
                self.strings_list.clear()
                for s, n in top:
                    self.strings_list.addItem("%s   ×%d" % (s, n))

    def show_flash(self, text, seconds=6):
        self.toast_text = text
        self.toast_until = time.monotonic() + seconds
        self._render_toast()

    def _render_toast(self):
        if self.header is None:
            return
        text = getattr(self, "toast_text", "") if time.monotonic() < self.toast_until else ""
        fm = self.toast_lbl.fontMetrics()
        self.toast_lbl.setText(fm.elidedText(text, QtCore.Qt.TextElideMode.ElideMiddle, max(40, self.toast_lbl.width())))

    # ------------------------------------------------------------------ actions
    def toggle_record(self):
        if self.worker.recorder is not None:
            self.stop_record()
            self.worker.armed = False
        elif self.worker.last_idr is None:
            self.show_flash(tr("rec_need_video"))
        else:
            self.worker.start_recording()
        self.sync_buttons()

    def stop_record(self):
        if self.worker.recorder is not None:
            self.worker.stop_recording()
            self.show_flash(tr("rec_saving"))
        self.out.hub.remove_sink("processed")
        self.sync_buttons()

    def snapshot(self):
        os.makedirs(self.worker.record_folder, exist_ok=True)
        self.out.snap_req = os.path.join(self.worker.record_folder, time.strftime("snapshot_%Y%m%d_%H%M%S.png"))

    def save_replay(self):
        rp = self.out.hub.replay
        if rp is None:
            self.show_flash(tr("replay_off"))
            return
        os.makedirs(self.worker.record_folder, exist_ok=True)
        path = os.path.join(self.worker.record_folder, time.strftime("replay_%Y%m%d_%H%M%S.mp4"))

        def work():
            ok = rp.save(path)
            self.bridge.event.emit({"type": "replay_saved", "ok": ok, "path": path})
        threading.Thread(target=work, daemon=True).start()

    def choose_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, tr("rec_folder"), self.worker.record_folder)
        if d:
            self.worker.record_folder = d
            self.settings.setValue("rec_folder", d)
            self.folder_lbl.setText(d)
            self.refresh_recent()

    def open_folder(self):
        os.makedirs(self.worker.record_folder, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.worker.record_folder))

    def refresh_recent(self):
        if not hasattr(self, "recent_list"):
            return
        folder = self.worker.record_folder
        try:
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if f.lower().endswith((".mp4", ".png", ".h264")) and not f.startswith(".")]
        except OSError:
            files = []
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        try:
            self.recent_list.clear()
        except RuntimeError:
            return
        for f in files[:12]:
            it = QtWidgets.QListWidgetItem("%s   %.1f MB" % (os.path.basename(f), os.path.getsize(f) / 1e6))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, f)
            self.recent_list.addItem(it)

    def toggle_clean(self):
        clean = self.header.isVisible()
        for w in (self.header, self.strip, self.rail):
            w.setVisible(not clean)
        self.panel.setVisible(not clean and self.settings.value("panel_visible", True, type=bool))

    def toggle_panel(self):
        self.show_page(self.current_page, not self.panel.isVisible())

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        if not self.header.isVisible():
            self.toggle_clean()

    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        if self.detached is not None:
            self.detached.close()
        if self.worker.recorder is not None:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            self.worker.stop_recording(background=False)
            QtWidgets.QApplication.restoreOverrideCursor()
        self.out.shutdown()
        self.worker.shutdown()
        self._keep_awake(False)
        if self.helper_proc and self.helper_proc.poll() is None:
            self.helper_proc.terminate()
        super(MainWindow, self).closeEvent(e)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    demo = None
    if "--demo" in argv:
        i = argv.index("--demo")
        demo = argv[i + 1]
        del argv[i:i + 2]
    QtWidgets.QApplication.setApplicationName(APP_NAME)
    QtWidgets.QApplication.setApplicationDisplayName(APP_NAME)
    QtWidgets.QApplication.setApplicationVersion(__version__)
    app = QtWidgets.QApplication([sys.argv[0]] + argv)
    icon = os.path.join(getattr(sys, "_MEIPASS", ROOT), "assets", "icon.png")
    if os.path.exists(icon):
        app.setWindowIcon(QtGui.QIcon(icon))
    w = MainWindow(demo_file=demo)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
