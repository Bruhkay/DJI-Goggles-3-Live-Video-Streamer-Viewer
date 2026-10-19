"""Ways of exchanging UDP-9003 packets with the goggles.

UsbTransport  - drives the goggles' USB network link ourselves (default).
NetTransport  - uses the OS network stack, for when the OS RNDIS driver
                already gives you a working 192.168.60.x interface.
"""
import os
import queue
import socket
import sys
import threading
import time

from . import netstack as ns

VENDOR_DJI = 0x2CA3
PRODUCT_GOGGLES3 = 0x0020


class TransportError(Exception):
    def __init__(self, msg, needs_admin=False):
        super(TransportError, self).__init__(msg)
        self.needs_admin = needs_admin


class DeviceNotFound(TransportError):
    pass


def _libusb_backend():
    import usb.backend.libusb1 as lb
    try:
        import libusb_package
        be = libusb_package.get_libusb1_backend()
        if be is not None:
            return be
    except Exception:
        pass
    candidates = []
    bundle = getattr(sys, "_MEIPASS", None)   # inside the packaged app
    if bundle:
        candidates += [os.path.join(bundle, "libusb-1.0.dylib"), os.path.join(bundle, "libusb-1.0.0.dylib")]
    candidates += ["/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib",
                   "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib"]
    for path in candidates:
        if os.path.exists(path):
            be = lb.get_backend(find_library=lambda _n, p=path: p)
            if be is not None:
                return be
    be = lb.get_backend()
    if be is None:
        raise TransportError("libusb not found. Run the setup script again.")
    return be


def find_goggles():
    import usb.core
    backend = _libusb_backend()
    dev = usb.core.find(idVendor=VENDOR_DJI, idProduct=PRODUCT_GOGGLES3, backend=backend)
    if dev is None:
        # Other DJI goggles PIDs may work too (N3 has been reported to share the protocol).
        dev = usb.core.find(idVendor=VENDOR_DJI, backend=backend)
    return dev


class UsbTransport(object):
    name = "usb"

    def __init__(self, log=print):
        self.log = log
        self.link = None
        self.goggles_mac = None
        self._rx = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self._error = None
        self._defrag = ns.IpDefragmenter()
        self._send_lock = threading.Lock()
        self.description = ""

    # -- lifecycle
    def start(self):
        import usb.core
        from .rndis import RndisLink, RndisError
        dev = find_goggles()
        if dev is None:
            raise DeviceNotFound("Goggles not found on USB")
        try:
            product = dev.product or "?"
        except Exception:
            product = "?"
        self.description = "%s (%04x:%04x)" % (product, dev.idVendor, dev.idProduct)
        try:
            self.link = RndisLink(dev, self.log)
            self.link.claim()
            self.link.initialize()
        except NotImplementedError:
            raise TransportError(_driver_hint())
        except usb.core.USBError as e:
            if self.link:
                self.link.release()
            # access denied / busy (a system driver holds the interface): needs admin rights on macOS
            denied = getattr(e, "errno", None) in (1, 13, 16) or \
                getattr(e, "backend_error_code", None) in (-3, -6) or "access" in str(e).lower()
            raise TransportError("Could not open the goggles' USB interfaces: %s\n%s" % (e, _driver_hint()),
                                 needs_admin=denied and sys.platform != "win32")
        except RndisError as e:
            raise TransportError("USB network link did not come up: %s" % e)
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, name="usb-rx", daemon=True)
        self._thread.start()
        self._resolve_mac()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.link:
            self.link.release()
        self.link = None

    # -- I/O
    def _reader(self):
        while not self._stop.is_set():
            try:
                for frame in self.link.read_frames(100):
                    self._rx.put(frame)
            except Exception as e:   # unplugged etc.
                self._error = e
                self._rx.put(None)
                return

    def _send_eth(self, frame):
        with self._send_lock:
            self.link.send_frame(frame)

    def _handle_frame(self, frame, out):
        info = ns.parse_frame(frame, self._defrag)
        if isinstance(info, ns.ArpInfo):
            if info.sender_ip == ns.GOGGLES_IP:
                self.goggles_mac = info.sender_mac
            if info.op == ns.ARP_REQUEST and info.target_ip == ns.HOST_IP:
                self._send_eth(ns.build_arp_reply(info.sender_mac, info.sender_ip))
        elif isinstance(info, ns.UdpInfo) and info.src_port == ns.GOGGLES_PORT:
            if info.src_ip == ns.GOGGLES_IP:
                self.goggles_mac = info.src_mac
            out.append(info.payload)

    def _resolve_mac(self):
        for _ in range(6):
            self._send_eth(ns.build_arp_request())
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline and self.goggles_mac is None:
                self.recv(0.05)
            if self.goggles_mac is not None:
                self.log("Goggles answered at %s (%s)" % (ns.ip_str(ns.GOGGLES_IP), ns.mac_str(self.goggles_mac)))
                return
        raise TransportError("Goggles did not answer on the USB network link. "
                             "Check 'OTG Wired Connection to Computer' is ON, then power-cycle the goggles.")

    def send(self, payload):
        if self.goggles_mac is None:
            raise TransportError("Goggles address unknown")
        self._send_eth(ns.build_udp(self.goggles_mac, payload))

    def recv(self, timeout):
        """Return a list of UDP payloads that came from the goggles' port 9003."""
        out = []
        try:
            frame = self._rx.get(timeout=timeout)
        except queue.Empty:
            return out
        while True:
            if frame is None:
                raise TransportError("USB connection lost: %s" % self._error)
            self._handle_frame(frame, out)
            try:
                frame = self._rx.get_nowait()
            except queue.Empty:
                return out


class NetTransport(object):
    """Plain UDP socket. Works only if your computer already has 192.168.60.1."""
    name = "net"

    def __init__(self, log=print, goggles_ip="192.168.60.2"):
        self.log = log
        self.addr = (goggles_ip, ns.GOGGLES_PORT)
        self.sock = None
        self.description = "network %s:%d" % self.addr

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
        try:
            self.sock.bind(("0.0.0.0", ns.HOST_PORT))
        except OSError as e:
            raise TransportError("Cannot bind UDP %d: %s" % (ns.HOST_PORT, e))

    def close(self):
        if self.sock:
            self.sock.close()
        self.sock = None

    def send(self, payload):
        try:
            self.sock.sendto(payload, self.addr)
        except OSError as e:
            raise TransportError("Network send failed: %s" % e)

    def recv(self, timeout):
        out = []
        self.sock.settimeout(timeout)
        try:
            data, addr = self.sock.recvfrom(65535)
        except socket.timeout:
            return out
        except OSError as e:
            raise TransportError("Network receive failed: %s" % e)
        if addr[1] == ns.GOGGLES_PORT:
            out.append(data)
        self.sock.setblocking(False)
        try:
            while True:
                data, addr = self.sock.recvfrom(65535)
                if addr[1] == ns.GOGGLES_PORT:
                    out.append(data)
        except (BlockingIOError, socket.timeout, OSError):
            pass
        return out


def _driver_hint():
    if sys.platform.startswith("win"):
        return ("On Windows the goggles' USB network interface needs the WinUSB driver (one-time).\n"
                "Run setup_windows.bat again and follow the Zadig steps in the README.")
    if sys.platform == "darwin":
        return "On macOS this tool must run with sudo (run_mac.command does that for you)."
    return "Try running with sudo, or add a udev rule for 2ca3:0020."
