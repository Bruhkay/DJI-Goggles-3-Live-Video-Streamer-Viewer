import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from g3 import netstack as ns, protocol as p, rndis  # noqa: E402
from g3.live import LiveView  # noqa: E402
from g3.sinks import RawFileSink  # noqa: E402
from g3.transport import UsbTransport  # noqa: E402
from fake_goggles import FakeGoggles, FakeTransport, FakeRndisLink  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


@pytest.fixture(scope="module")
def h264():
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg not installed")
    d = tempfile.mkdtemp()
    path = os.path.join(d, "src.h264")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=60",
                           "-frames:v", "120", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-profile:v", "high", "-g", "100000",
                           "-x264-params", "keyint=100000:scenecut=0", "-bf", "0", "-f", "h264", path])
    with open(path, "rb") as f:
        return f.read()


def count_frames(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                   "-show_entries", "stream=nb_read_frames,width,height", "-of", "csv=p=0",
                                   "-f", "h264", path]).decode().strip()
    w, h, n = out.split(",")
    return int(w), int(h), int(n)


# ---------------------------------------------------------------- unit tests

def test_outer_header():
    pkt = p.build_outer(0x1234, 7, p.T_HANDSHAKE, p.HANDSHAKE_BODY)
    assert len(pkt) == 48
    assert struct.unpack_from("<H", pkt)[0] == 48 | 0x8000
    x = 0
    for b in pkt[:7]:
        x ^= b
    assert pkt[7] == x
    assert p.parse_outer(pkt) == (7, p.T_HANDSHAKE)


def test_ack_layout():
    s = p.Session()
    a = s.ack(10, 20)
    assert len(a) == 8 + 22
    assert struct.unpack_from("<HH", a, 8) == (10, 20)
    assert a[6] == p.T_ACK


def test_video_fragment_bits_roundtrip():
    for idx in range(64):
        pkt = p.build_video(1, 1, 200, idx, 64, b"x")
        assert p.parse_video(pkt) == (200, idx, 64, b"x")


def test_reassembler_out_of_order_and_wrap():
    r = p.Reassembler()
    out = r.add(5, 255, 1, 2, b"B", now=0) + r.add(4, 255, 0, 2, b"A", now=0)
    assert out == [(b"AB", 4, 5)]
    assert r.add(6, 0, 0, 1, b"C", now=0) == [(b"C", 6, 6)]


def test_reassembler_drops_incomplete_instead_of_merging():
    r = p.Reassembler(max_lag=3)
    r.add(1, 10, 0, 2, b"half", now=0)          # fragment 1 lost
    for fn in range(11, 20):
        r.add(fn, fn, 0, 1, b"x", now=0)
    assert r.dropped == 1
    # frame number 10 comes round again 256 frames later: must not merge with the stale half
    assert r.add(99, 10, 1, 2, b"tail", now=0) == []


def test_split_params_blob():
    blob = b"\x00\x00\x00\x01\x67abc\x00\x00\x00\x01\x68de"
    assert p.nal_types(blob) == [7, 8]


def test_gate_waits_for_idr():
    g = p.KeyframeGate()
    assert g.push(b"\x00\x00\x00\x01\x41p") == []                          # P before anything
    assert g.push(b"\x00\x00\x00\x01\x67s\x00\x00\x00\x01\x68p") == []     # params only
    out = g.push(b"\x65idr")                                               # IDR without start code
    assert out[0].startswith(b"\x00\x00\x00\x01\x67") and out[1] == b"\x00\x00\x00\x01\x65idr"
    assert g.push(b"\x41p") == [b"\x00\x00\x00\x01\x41p"]


def test_netstack_udp_roundtrip_and_checksum():
    frame = ns.build_udp(b"\x11" * 6, b"hello")
    info = ns.parse_frame(frame)
    assert info.payload == b"hello" and info.dst_port == 9003 and info.src_port == 54321
    assert ns.ip_checksum(frame[14:34]) == 0


def test_ip_defragment():
    d = ns.IpDefragmenter()
    assert d.push(b"s", 1, 8, False, b"world") is None
    assert d.push(b"s", 1, 0, True, b"hello123") == b"hello123world"


def test_rndis_multi_packet_unwrap():
    blob = rndis.wrap_packet(b"a" * 60) + rndis.wrap_packet(b"b" * 61)
    assert rndis.unwrap_packets(blob) == [b"a" * 60, b"b" * 61]


# ---------------------------------------------------------------- end to end

class StepClock(object):
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.005
        return self.t


def run_live(transport, goggles, path, max_seconds=30):
    sink = RawFileSink(path)
    lv = LiveView(transport, [sink], log=lambda *a: None, clock=StepClock())
    orig = transport.recv

    def recv(timeout):
        if goggles.done():
            lv.stop()
        return orig(timeout)
    transport.recv = recv
    lv.run(max_seconds=max_seconds)
    sink.close()
    return lv


def test_end_to_end_udp_level(h264, tmp_path):
    g = FakeGoggles(h264)
    out = str(tmp_path / "out.h264")
    lv = run_live(FakeTransport(g), g, out)
    assert g.handshakes >= 1 and len(g.acks) > 100
    assert lv.state == "live"
    assert count_frames(out) == (640, 360, 120)


def test_end_to_end_through_usb_rndis_stack(h264, tmp_path):
    g = FakeGoggles(h264, reorder=True)
    t = UsbTransport(log=lambda *a: None)
    t.link = FakeRndisLink(g)
    t._thread = threading.Thread(target=t._reader, daemon=True)
    t._thread.start()
    t._resolve_mac()
    assert t.goggles_mac == bytes.fromhex("ca3cb48d51c3")
    out = str(tmp_path / "usb.h264")
    run_live(t, g, out)
    t._stop.set()
    assert count_frames(out) == (640, 360, 120)


def test_packet_loss_does_not_crash(h264, tmp_path):
    g = FakeGoggles(h264, loss=0.03, frag_size=200, seed=3)
    out = str(tmp_path / "lossy.h264")
    lv = run_live(FakeTransport(g), g, out)
    assert lv.reasm.dropped > 0
    w, h, n = count_frames(out)
    assert (w, h) == (640, 360) and n > 40


# ---------------------------------------------------------------- stabilizer

def test_lens_maps_identity():
    import numpy as np
    from g3 import stabilizer as S
    A = S.output_matrix(640, 360, 640, 360)
    mx, my = S.WarpMaps().build(640, 360, 640, 360, A, None, 150.0)
    ys, xs = np.mgrid[0:360, 0:640]
    assert np.abs(mx - xs).max() < 0.6 and np.abs(my - ys).max() < 0.6


def test_rotation_estimate_matches_true_rotation():
    import numpy as np, cv2
    from g3 import stabilizer as S
    rng = np.random.default_rng(0)
    tex = cv2.GaussianBlur((rng.random((216, 384)) * 255).astype(np.uint8), (0, 0), 1.2)
    model = S.FisheyeModel(384, 216, 150.0)
    ys, xs = np.mgrid[0:216, 0:384].astype(np.float64)
    true = np.array([0.01, -0.008, 0.012])
    rays = model.unproject(xs, ys) @ S.rotmat(-true).T          # the next frame sees the world turned
    sx, sy = model.project(rays)
    moved = cv2.remap(tex, sx.astype(np.float32), sy.astype(np.float32), cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_REFLECT)
    est = S.RotationEstimator(150.0)
    est.step(tex)
    rv, ok = est.step(moved)
    assert ok and np.abs(np.abs(rv) - np.abs(true)).max() < 0.003


def test_smooth_stabilizer_delays_and_limits():
    import numpy as np
    from g3 import stabilizer as S
    st = S.Stabilizer()
    st.configure("high", True, True, 150.0)
    outs = [st.push(i, np.array([0.002, 0.0, 0.0]) + (0.01 if i % 2 else -0.01), True, 1920) for i in range(60)]
    got = [o for o in outs if o is not None]
    assert got[0][0] == 0 and len(got) == 60 - st.delay
    lim = S.angle_limits(1920, st.zoom, 150.0)
    assert all(np.all(np.abs(c) <= lim + 1e-9) for _, c, _ in got)
