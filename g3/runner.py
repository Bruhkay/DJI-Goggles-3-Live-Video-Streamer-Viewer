"""Connect / stream / reconnect loop shared by the command line tool and the app helper."""
import socket
import threading

from .live import LiveView
from .transport import UsbTransport, NetTransport, TransportError, DeviceNotFound


def os_route_to_goggles():
    """True if the OS already has a working network link to the goggles (192.168.60.x)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.60.2", 9003))
        return s.getsockname()[0].startswith("192.168.60.")
    except OSError:
        return False
    finally:
        s.close()


class Runner(object):
    """Keeps a LiveView running across unplug/replug until stopped.

    run() returns one of: "stopped", "closed" (a required sink went away),
    "needs_admin" (USB access denied), "error" (with once=True).
    """

    def __init__(self, sinks, log=print, status=None, on_state=None, on_stats=None,
                 transport="auto", transport_factory=None, once=False, should_quit=None):
        self.sinks = sinks
        self.log = log
        self.status = status
        self.on_state = on_state or (lambda s, **kw: None)
        self.on_stats = on_stats
        self.kind = transport
        self.factory = transport_factory or self._default_factory
        self.once = once
        self.should_quit = should_quit or (lambda: False)
        self._stop = threading.Event()
        self._view = None
        self.raw_hook = None          # set at any time; receives non-video packets

    def _default_factory(self):
        kind = self.kind
        if kind == "auto":
            kind = "net" if os_route_to_goggles() else "usb"
        return UsbTransport(self.log) if kind == "usb" else NetTransport(self.log)

    def stop(self):
        self._stop.set()
        v = self._view
        if v is not None:
            v.stop()

    def _sleep(self, seconds):
        return self._stop.wait(seconds)

    def run(self):
        waited = False
        while not self._stop.is_set():
            if self.should_quit():
                return "closed"
            transport = self.factory()
            try:
                transport.start()
            except DeviceNotFound:
                if not waited:
                    self.log("Waiting for the goggles on USB-C ...")
                    self.on_state("searching")
                    waited = True
                self._sleep(1.0)
                continue
            except TransportError as e:
                self.log("\n[error] %s" % e)
                if getattr(e, "needs_admin", False):
                    self.on_state("needs_admin", message=str(e))
                    return "needs_admin"
                self.on_state("error", message=str(e))
                if self.once:
                    return "error"
                self._sleep(3.0)
                waited = False
                continue
            waited = False
            self.log("Connected: %s" % transport.description)
            self.on_state("connected", device=transport.description)
            lv = LiveView(transport, self.sinks, log=self.log, status=self.status,
                          on_state=lambda s: self.on_state(s), on_stats=self.on_stats,
                          raw_hook=lambda pkt: self.raw_hook and self.raw_hook(pkt))
            self._view = lv
            if self._stop.is_set():
                lv.stop()
            try:
                result = lv.run()
            except TransportError as e:
                self.log("\n[disconnected] %s" % e)
                self.on_state("disconnected", message=str(e))
                result = "lost"
            finally:
                self._view = None
                transport.close()
            if result in ("closed", "stopped"):
                return result
            if self.once:
                return "error"
            self.log("Reconnecting ...")
            self._sleep(1.0)
        return "stopped"
