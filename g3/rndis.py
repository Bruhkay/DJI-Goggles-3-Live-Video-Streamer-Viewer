"""Userspace RNDIS driver over libusb (pyusb).

The goggles present a USB network adapter (RNDIS). On macOS the built-in
driver brings it up as "media inactive", so instead we claim the two RNDIS
interfaces ourselves and exchange raw Ethernet frames.
"""
import struct
import usb.core
import usb.util

RNDIS_PACKET_MSG = 0x00000001
RNDIS_INITIALIZE_MSG = 0x00000002
RNDIS_SET_MSG = 0x00000005
RNDIS_INITIALIZE_CMPLT = 0x80000002
RNDIS_SET_CMPLT = 0x80000005
OID_GEN_CURRENT_PACKET_FILTER = 0x0001010E
PACKET_FILTER = 0x0001 | 0x0004 | 0x0010 | 0x0020   # directed|broadcast|all-mcast|promisc
PACKET_HDR_LEN = 44


def wrap_packet(eth_frame):
    return struct.pack("<IIII7I", RNDIS_PACKET_MSG, PACKET_HDR_LEN + len(eth_frame),
                       PACKET_HDR_LEN - 8, len(eth_frame), 0, 0, 0, 0, 0, 0, 0) + eth_frame


def unwrap_packets(buf):
    """A single bulk read may hold several PACKET_MSGs back to back."""
    frames, pos = [], 0
    while len(buf) - pos >= PACKET_HDR_LEN:
        msg_type, msg_len, data_off, data_len = struct.unpack_from("<IIII", buf, pos)
        if msg_type != RNDIS_PACKET_MSG or msg_len < PACKET_HDR_LEN:
            break
        start = pos + 8 + data_off
        frames.append(bytes(buf[start:start + data_len]))
        pos += msg_len
    return frames


class RndisError(Exception):
    pass


class RndisLink(object):
    def __init__(self, dev, log=print):
        self.dev = dev
        self.log = log
        self.comm_if = self.data_if = None
        self.int_ep = self.in_ep = self.out_ep = None
        self._req_id = 0
        self._claimed = []
        self._find_interfaces()

    def _find_interfaces(self):
        cfg = self.dev.get_active_configuration() if self._has_config() else None
        if cfg is None:
            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
        comm, data = None, None
        for intf in cfg:
            if intf.bAlternateSetting != 0:
                continue
            cls = intf.bInterfaceClass
            eps = list(intf)
            if comm is None and cls in (0xE0, 0x02, 0xEF) and any(
                    usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR for e in eps):
                comm = intf
            elif data is None and cls == 0x0A:
                data = intf
        if comm is None or data is None:
            raise RndisError("RNDIS interfaces not found on this device")
        self.comm_if = comm.bInterfaceNumber
        self.data_if = data.bInterfaceNumber
        for e in comm:
            if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN:
                self.int_ep = e.bEndpointAddress
        for e in data:
            if usb.util.endpoint_type(e.bmAttributes) != usb.util.ENDPOINT_TYPE_BULK:
                continue
            if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN:
                self.in_ep = e.bEndpointAddress
            else:
                self.out_ep = e.bEndpointAddress
        if self.in_ep is None or self.out_ep is None:
            raise RndisError("RNDIS bulk endpoints not found")

    def _has_config(self):
        try:
            self.dev.get_active_configuration()
            return True
        except usb.core.USBError:
            return False

    def claim(self):
        for ifn in (self.comm_if, self.data_if):
            try:
                if self.dev.is_kernel_driver_active(ifn):
                    self.dev.detach_kernel_driver(ifn)
            except (NotImplementedError, usb.core.USBError):
                pass  # Windows has no kernel-driver concept here; macOS may refuse but claim can still work
            usb.util.claim_interface(self.dev, ifn)
            self._claimed.append(ifn)

    def release(self):
        for ifn in self._claimed:
            try:
                usb.util.release_interface(self.dev, ifn)
            except Exception:
                pass
        self._claimed = []
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    def _command(self, msg, expect):
        self.dev.ctrl_transfer(0x21, 0x00, 0, self.comm_if, msg, timeout=1000)
        if self.int_ep is not None:
            try:
                self.dev.read(self.int_ep, 8, timeout=200)   # "response available", best effort
            except usb.core.USBError:
                pass
        for _ in range(10):
            resp = bytes(self.dev.ctrl_transfer(0xA1, 0x01, 0, self.comm_if, 4096, timeout=1000))
            if len(resp) >= 16:
                rtype, _, _, status = struct.unpack_from("<IIII", resp)
                if rtype == expect:
                    if status != 0:
                        raise RndisError("RNDIS status 0x%08x for 0x%08x" % (status, expect))
                    return resp
        raise RndisError("No RNDIS response for 0x%08x" % expect)

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def initialize(self):
        self._command(struct.pack("<IIIIII", RNDIS_INITIALIZE_MSG, 24, self._next_id(), 1, 0, 0x4000),
                      RNDIS_INITIALIZE_CMPLT)
        value = struct.pack("<I", PACKET_FILTER)
        msg = struct.pack("<IIIIIII", RNDIS_SET_MSG, 28 + len(value), self._next_id(),
                          OID_GEN_CURRENT_PACKET_FILTER, len(value), 20, 0) + value
        self._command(msg, RNDIS_SET_CMPLT)

    def send_frame(self, eth_frame):
        self.dev.write(self.out_ep, wrap_packet(eth_frame), timeout=1000)

    def read_frames(self, timeout_ms=100):
        try:
            buf = self.dev.read(self.in_ep, 65536, timeout=timeout_ms)
        except usb.core.USBTimeoutError:
            return []
        return unwrap_packets(bytes(buf))
