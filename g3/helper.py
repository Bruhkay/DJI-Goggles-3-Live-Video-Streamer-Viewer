"""USB helper process for the app.

Owns the goggles (may run as root on macOS), streams H.264 units and status
events to the app over a localhost socket, and exits as soon as the app goes
away. Deliberately does not import any GUI code.
"""
import argparse
import json
import socket
import sys
import threading
import time

from . import ipc
from .runner import Runner


class SocketSink(object):
    required = True
    label = "app"

    def __init__(self, channel):
        self.ch = channel

    def start(self):
        pass

    def write(self, unit):
        self.ch.video(unit)

    def alive(self):
        return self.ch.ok

    def close(self):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="g3-helper")
    ap.add_argument("--selftest", action="store_true", help="check that libusb loads, then exit")
    ap.add_argument("--port", type=int)
    ap.add_argument("--token")
    ap.add_argument("--transport", default="auto", choices=["auto", "usb", "net"])
    ap.add_argument("--simulate", metavar="FILE.h264", help="demo mode: play a file as if it came from the goggles")
    args = ap.parse_args(argv)
    if args.selftest:
        from .transport import _libusb_backend
        import av   # noqa: F401  (the app decodes with it)
        print("libusb backend:", _libusb_backend())
        return 0
    if args.port is None or args.token is None:
        ap.error("--port and --token are required")

    sock = socket.create_connection(("127.0.0.1", args.port), timeout=5)
    sock.settimeout(None)
    ch = ipc.Channel(sock)
    ch.event("hello", token=args.token, uid=getattr(__import__("os"), "geteuid", lambda: -1)())

    factory = None
    if args.simulate:
        from .sim import RealtimeSimTransport
        factory = lambda: RealtimeSimTransport(args.simulate)   # noqa: E731

    runner = Runner([SocketSink(ch)],
                    log=lambda m: ch.event("log", message=str(m).strip()),
                    on_state=lambda s, **kw: ch.event("state", state=s, **kw),
                    on_stats=lambda d: ch.event("stats", **d),
                    transport=args.transport, transport_factory=factory,
                    should_quit=lambda: not ch.ok)

    capture = {"on": False}

    def raw_hook(pkt):
        if capture["on"]:
            ch.raw(time.time(), pkt)
    runner.raw_hook = raw_hook

    def watch():
        # commands from the app; when the connection closes the app is gone
        try:
            while True:
                kind, payload = ipc.read_message(sock)
                if kind == ipc.EVENT:
                    cmd = json.loads(payload)
                    if cmd.get("cmd") == "capture":
                        capture["on"] = bool(cmd.get("on"))
        except (OSError, ConnectionError, ValueError):
            pass
        ch.ok = False
        runner.stop()
    threading.Thread(target=watch, daemon=True).start()

    result = runner.run()
    ch.event("exit", result=result)
    try:
        sock.close()
    except OSError:
        pass
    return 0 if result in ("stopped", "closed") else 2


if __name__ == "__main__":
    sys.exit(main())
