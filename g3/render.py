"""Turns a decoded frame + picture settings into an RGB image of a given size.

Two paths:
  * affine - framing only (crop, pan, zoom, rotate 180 / mirror): one warp,
    or a plain resize when nothing is changed.
  * lens   - stabilization and/or lens straightening: a remap table built
    through the lens model (see stabilizer.WarpMaps).
"""
import math

import numpy as np

from . import stabilizer as stab

LINES = (1080, 720)


class Picture(object):
    """Picture settings shared between the GUI and worker threads (plain attributes)."""

    def __init__(self):
        self.stab = "off"          # off | low | medium | high | max
        self.smooth = True         # look-ahead smoothing (adds ~0.2 s) vs zero delay
        self.roll = True
        self.lens_fov = 150        # camera lens field of view (degrees)
        self.straighten = False    # rectilinear output
        self.aspect = "auto"       # auto = same as the video
        self.pan = 0.0             # -1..1
        self.zoom = 1.0            # 1..2
        self.rotate180 = False
        self.mirror = False

    def needs_lens(self):
        return (self.stab != "off" or self.straighten) and stab.available()

    def identity(self):
        return (not self.needs_lens() and self.aspect == "auto" and abs(self.pan) < 1e-3 and
                abs(self.zoom - 1.0) < 1e-3 and not self.rotate180 and not self.mirror)


def aspect_ratio(pic, src_w, src_h):
    if pic.aspect == "auto" or pic.aspect not in stab.ASPECTS:
        return src_w / float(src_h)
    return stab.ASPECTS[pic.aspect]


def canvas_size(pic, src_w, src_h, lines=1080):
    """Output size for an output with `lines` on its short side (1080p / 720p)."""
    a = aspect_ratio(pic, src_w, src_h)
    if a >= 1.0:
        h, w = lines, lines * a
    else:
        w, h = lines, lines / a
    return int(round(w)) & ~1, int(round(h)) & ~1


def fit(pic, src_w, src_h, box_w, box_h):
    """Largest canvas with the output aspect that fits in a box (device pixels)."""
    a = aspect_ratio(pic, src_w, src_h)
    if box_w / float(box_h) > a:
        h, w = box_h, box_h * a
    else:
        w, h = box_w, box_w / a
    return max(2, int(w) & ~1), max(2, int(h) & ~1)


def orientation(w, h, rotate180, mirror):
    m = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    if rotate180:
        m = stab.compose(np.array([[-1.0, 0, w], [0, -1.0, h]]), m)
    if mirror:
        m = stab.compose(np.array([[-1.0, 0, w], [0, 1.0, 0]]), m)
    return m


class Renderer(object):
    """Keeps the per-size lens tables between frames (one per consumer thread)."""

    def __init__(self):
        self.maps = stab.WarpMaps()

    def render(self, frame, pic, out_w, out_h, corr=None, zoom=1.0):
        """frame: av.VideoFrame. corr: stabilization rotation (or None). Returns (out_h, out_w, 3) RGB."""
        W, H = frame.width, frame.height
        if pic.identity() and abs(out_w / float(out_h) - W / float(H)) < 0.01:
            return _rgb(frame, out_w, out_h)
        A = stab.output_matrix(W, H, out_w, out_h, orientation(W, H, pic.rotate180, pic.mirror),
                               zoom=zoom * pic.zoom, pan=pic.pan)
        s = math.sqrt(abs(A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0]))
        # shrinking a lot: let swscale shrink first (cheaper, less aliasing)
        r = min(1.0, s * 1.25) if s < 0.8 else 1.0
        sw, sh = max(2, int(W * r) & ~1), max(2, int(H * r) & ~1)
        src = _rgb(frame, sw, sh)
        rx, ry = sw / float(W), sh / float(H)
        if not pic.needs_lens():
            A2 = stab.compose(A, np.array([[1.0 / rx, 0, 0], [0, 1.0 / ry, 0]]))
            return stab.cv2.warpAffine(src, A2, (out_w, out_h), flags=stab.cv2.INTER_LINEAR,
                                       borderMode=stab.cv2.BORDER_REPLICATE)
        mx, my = self.maps.build(W, H, out_w, out_h, A, corr, float(pic.lens_fov),
                                 stab.STRAIGHTEN_FOV if pic.straighten else None)
        if r < 1.0:
            mx = (mx + 0.5) * rx - 0.5
            my = (my + 0.5) * ry - 0.5
        return stab.cv2.remap(src, mx, my, stab.cv2.INTER_LINEAR,
                              borderMode=stab.cv2.BORDER_CONSTANT if pic.straighten else stab.cv2.BORDER_REPLICATE)


def _rgb(frame, w, h):
    if (w, h) == (frame.width, frame.height):
        img = frame.to_ndarray(format="rgb24")
    else:
        img = frame.reformat(width=w, height=h, format="rgb24", interpolation="BILINEAR").to_ndarray()
    return np.ascontiguousarray(img)          # rows may be padded


def gray_small(frame, width=stab.ANALYSIS_W):
    h = max(2, int(round(width * frame.height / float(frame.width))) & ~1)
    return frame.reformat(width=width, height=h, format="gray").to_ndarray()
