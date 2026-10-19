"""Where the H.264 stream goes: a low-latency window, a recording, a network stream."""
import glob
import os
import queue
import shutil
import subprocess
import sys
import threading


def find_tool(name):
    """Locate ffplay/ffmpeg even when PATH is limited (sudo on macOS, fresh winget install)."""
    exe = name + (".exe" if sys.platform.startswith("win") else "")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.path.join(here, "tools", exe)]
    found = shutil.which(name)
    if found:
        candidates.insert(0, found)
    if sys.platform == "darwin":
        for pre in ("/opt/homebrew", "/usr/local"):
            candidates += [pre + "/bin/" + name, pre + "/opt/ffmpeg/bin/" + name, pre + "/opt/ffmpeg-full/bin/" + name]
    elif sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "")
        candidates += glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "bin", exe),
                                recursive=True)
        candidates += glob.glob(os.path.join(local, "Microsoft", "WinGet", "Links", exe))
        candidates += [os.path.join("C:\\", "ffmpeg", "bin", exe), os.path.join(os.environ.get("ProgramFiles", ""), "ffmpeg", "bin", exe)]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _as_user(cmd):
    """When running under sudo, open GUI/output as the real user, not root."""
    user = os.environ.get("SUDO_USER")
    if user and hasattr(os, "geteuid") and os.geteuid() == 0 and sys.platform == "darwin":
        return ["sudo", "-u", user] + cmd
    return cmd


class ProcessSink(object):
    """Feeds Annex-B H.264 to a child process through a writer thread."""

    label = "sink"

    def __init__(self, cmd, log=print, as_user=True):
        self.log = log
        self.cmd = _as_user(cmd) if as_user else cmd
        self.q = queue.Queue()
        self.proc = None
        self.thread = None

    def start(self):
        flags = 0x08000000 if sys.platform.startswith("win") and self.label != "viewer" else 0  # CREATE_NO_WINDOW
        self.proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, bufsize=0, creationflags=flags)
        self.thread = threading.Thread(target=self._writer, name=self.label, daemon=True)
        self.thread.start()

    def _writer(self):
        while True:
            chunk = self.q.get()
            if chunk is None:
                break
            try:
                self.proc.stdin.write(chunk)
            except (BrokenPipeError, OSError, ValueError):
                break
        try:
            self.proc.stdin.close()
        except Exception:
            pass

    def write(self, chunk):
        self.q.put(chunk)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def close(self):
        self.q.put(None)
        if self.thread:
            self.thread.join(timeout=3)
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()


def _need(tool):
    path = find_tool(tool)
    if not path:
        raise RuntimeError("%s not found. Run the setup script first (it installs ffmpeg)." % tool)
    return path


class ViewerSink(ProcessSink):
    label = "viewer"
    required = True   # closing the window ends the program

    def __init__(self, log=print, fullscreen=False):
        cmd = [_need("ffplay"), "-hide_banner", "-loglevel", "error",
               "-fflags", "nobuffer", "-flags", "low_delay", "-framedrop",
               "-probesize", "32", "-analyzeduration", "0", "-sync", "ext",
               "-f", "h264", "-framerate", "120", "-i", "-",
               "-vf", "setpts=0", "-window_title", "Goggles 3 - live"]
        if fullscreen:
            cmd.append("-fs")
        super(ViewerSink, self).__init__(cmd, log)


class FfmpegCopySink(ProcessSink):
    """Remux (no re-encode) to a file or a network stream, timestamped on arrival."""
    required = False

    def __init__(self, out_args, label, log=print):
        self.label = label
        cmd = [_need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
               "-fflags", "+genpts", "-use_wallclock_as_timestamps", "1",
               "-f", "h264", "-i", "-", "-c", "copy"] + out_args
        super(FfmpegCopySink, self).__init__(cmd, log, as_user=(label == "record"))


def record_sink(path, log=print):
    return FfmpegCopySink([path], "record", log)


def udp_sink(target, log=print):
    return FfmpegCopySink(["-f", "mpegts", "udp://%s?pkt_size=1316" % target], "udp", log)


def rtmp_sink(url, log=print):
    return FfmpegCopySink(["-f", "flv", url], "rtmp", log)


class RawFileSink(object):
    """Plain .h264 dump, no ffmpeg needed."""
    required = False
    label = "raw"

    def __init__(self, path):
        self.f = open(path, "wb")

    def start(self):
        pass

    def write(self, chunk):
        self.f.write(chunk)

    def alive(self):
        return True

    def close(self):
        self.f.close()
