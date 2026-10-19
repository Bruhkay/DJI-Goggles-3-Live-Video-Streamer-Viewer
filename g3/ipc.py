"""Tiny framed protocol between the USB helper and the app (localhost TCP).

Each message: 1 byte type, 4 byte big-endian length, payload.
  V  one H.264 unit (Annex-B)
  J  a JSON event: {"type": "state"|"stats"|"log"|"connected"|"error"|"hello", ...}
"""
import json
import socket
import struct
import threading

VIDEO = b"V"
EVENT = b"J"
RAW = b"P"      # a non-video packet from the goggles (telemetry capture)


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return bytes(buf)


def read_message(sock):
    head = recv_exact(sock, 5)
    length = struct.unpack(">I", head[1:])[0]
    return head[:1], recv_exact(sock, length)


class Channel(object):
    def __init__(self, sock):
        self.sock = sock
        self.lock = threading.Lock()
        self.ok = True
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

    def _send(self, kind, payload):
        if not self.ok:
            return
        try:
            with self.lock:
                self.sock.sendall(kind + struct.pack(">I", len(payload)) + payload)
        except OSError:
            self.ok = False

    def video(self, unit):
        self._send(VIDEO, unit)

    def raw(self, t, data):
        self._send(RAW, struct.pack(">d", t) + data)

    def command(self, **fields):
        self._send(EVENT, json.dumps(fields).encode("utf-8"))

    def event(self, kind, **fields):
        fields["type"] = kind
        self._send(EVENT, json.dumps(fields).encode("utf-8"))
