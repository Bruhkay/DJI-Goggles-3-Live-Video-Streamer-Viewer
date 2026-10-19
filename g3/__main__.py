"""Goggles 3 Live - clean, low-latency live view from DJI Goggles 3 over USB-C.

    python -m g3                      # open the live window
    python -m g3 --record flight.mkv  # also record (no re-encode)
    python -m g3 --udp 127.0.0.1:5600 # also stream MPEG-TS for OBS / VLC
"""
import argparse
import datetime
import os
import signal
import sys

from . import __version__
from .sinks import ViewerSink, record_sink, udp_sink, rtmp_sink, RawFileSink
from .runner import Runner

CHECKLIST = """
Goggles 3 Live v%s
 Before you start (once):
   1. Goggles: Settings > About > "OTG Wired Connection to Computer" = ON
      (unplug the cable before switching it, then plug back in)
   2. Use a USB-C cable that carries data (not a charge-only cable).
 Every flight:
   3. Power the drone, wait until the goggles show video.
   4. If no picture after a few seconds: toggle
      "Share Liveview to Mobile Device via Wi-Fi" OFF and ON in the goggles.
 Close the video window or press Ctrl+C to quit.
""" % __version__


def log(msg):
    print(msg, flush=True)


def status(line):
    sys.stdout.write("\r" + line + "   ")
    sys.stdout.flush()


def default_record_path():
    folder = os.path.join(os.path.expanduser("~" + os.environ.get("SUDO_USER", "")),
                          "Movies" if sys.platform == "darwin" else "Videos", "Goggles3")
    os.makedirs(folder, exist_ok=True)
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid and hasattr(os, "chown"):   # created as root under sudo: give it back to the user
        for d in (os.path.dirname(folder), folder):
            try:
                os.chown(d, int(uid), int(gid))
            except OSError:
                pass
    return os.path.join(folder, datetime.datetime.now().strftime("goggles3_%Y%m%d_%H%M%S.mkv"))


def build_sinks(args):
    sinks = []
    if not args.no_view:
        sinks.append(ViewerSink(log, fullscreen=args.fullscreen))
    if args.record is not None:
        path = args.record or default_record_path()
        log("Recording to %s" % path)
        sinks.append(record_sink(path, log))
    if args.raw:
        sinks.append(RawFileSink(args.raw))
    if args.udp:
        port = args.udp.rsplit(":", 1)[-1]
        log("Streaming MPEG-TS to udp://%s  (OBS: Media Source, untick Local File, Input = udp://@:%s)" % (args.udp, port))
        sinks.append(udp_sink(args.udp, log))
    if args.rtmp:
        log("Streaming to %s" % args.rtmp)
        sinks.append(rtmp_sink(args.rtmp, log))
    if not sinks:
        raise SystemExit("Nothing to do: --no-view given without --record/--raw/--udp/--rtmp.")
    return sinks


def main(argv=None):
    ap = argparse.ArgumentParser(prog="g3", description="Clean, low-latency live view from DJI Goggles 3 over USB-C.")
    ap.add_argument("--transport", choices=["auto", "usb", "net"], default="auto",
                    help="auto (default): use the OS network link if it already reaches 192.168.60.2, "
                         "otherwise drive the USB link directly.")
    ap.add_argument("--no-view", action="store_true", help="do not open the video window")
    ap.add_argument("--fullscreen", action="store_true", help="open the video window full screen")
    ap.add_argument("--record", nargs="?", const="", metavar="FILE.mkv",
                    help="record the stream without re-encoding (default: ~/Videos/Goggles3/...)")
    ap.add_argument("--raw", metavar="FILE.h264", help="dump the raw H.264 stream")
    ap.add_argument("--udp", metavar="HOST:PORT", help="also stream MPEG-TS over UDP, e.g. 127.0.0.1:5600")
    ap.add_argument("--rtmp", metavar="URL", help="also stream to an RTMP server (YouTube/Twitch)")
    ap.add_argument("--once", action="store_true", help="exit instead of reconnecting when the goggles disconnect")
    args = ap.parse_args(argv)

    log(CHECKLIST)
    sinks = build_sinks(args)
    for s in sinks:
        s.start()

    required = [s for s in sinks if getattr(s, "required", False)]
    runner = Runner(sinks, log=log, status=status, transport=args.transport, once=args.once,
                    should_quit=lambda: bool(required) and not any(s.alive() for s in required))
    signal.signal(signal.SIGINT, lambda *_: runner.stop())
    try:
        result = runner.run()
    except KeyboardInterrupt:
        result = "stopped"
    finally:
        log("\nShutting down ...")
        for s in sinks:
            s.close()
    if result == "needs_admin":
        log("Run again with administrator rights (on macOS: run_mac.command, or the Goggles3 Live app).")
    return 1 if result in ("error", "needs_admin") else 0


if __name__ == "__main__":
    sys.exit(main())
