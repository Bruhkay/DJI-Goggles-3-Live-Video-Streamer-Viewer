"""Lens-aware video stabilization for FPV footage (no gyro needed).

FPV shake is almost entirely camera *rotation* seen through a very wide
(fisheye) lens. Shifting the picture cannot undo that: on a fisheye image a
rotation moves the middle and the edges by different amounts, so a shifted
picture "swims" (edges breathe, left and right seem to zoom differently).
So instead, step by step:

  1. Shrink each frame to a small grayscale picture (fast to analyse).
  2. Track ~250 corners from the previous frame into this one.
  3. Turn every point into a viewing direction through the lens model and fit
     the one 3D camera rotation that explains the movement (RANSAC + Kabsch).
  4. Smooth the camera's rotation path:
       smooth mode - centered local-linear fit using a few upcoming frames
                     (~0.2 s delay): follows turns exactly, removes shake.
       zero delay  - adaptive alpha-beta tracker (no delay, a bit less smooth).
  5. Render: for every output pixel take its viewing direction, rotate it by
     the correction, and look it up through the lens. A small zoom hides the
     edges. Optionally the output is a straight (rectilinear) lens instead.

Measured on a synthetic 150-degree FPV flight against the previous
image-shift stabilizer: smooth mode left ~3.5x less shake, ~2.6x less edge
swimming and ~4x less drifting on turns ("tide").
"""
import math
from collections import deque

import numpy as np

try:
    import cv2
except Exception:          # stabilization is optional
    cv2 = None

ANALYSIS_W = 384

# strength -> (zoom used as safety margin, smooth-mode delay in frames, zero-delay filter gain)
PRESETS = {
    "off": None,
    "low": (1.06, 6, 0.30),
    "medium": (1.10, 10, 0.16),
    "high": (1.15, 15, 0.10),
    "max": (1.22, 22, 0.07),
}
LENS_FOVS = (120, 135, 150, 165)       # horizontal field of view choices (degrees)
STRAIGHTEN_FOV = 115.0                 # output field of view when the lens is straightened


def available():
    return cv2 is not None


# ---------------------------------------------------------------------------- lens

class FisheyeModel(object):
    """Equidistant fisheye (radius = f * angle), the usual model for FPV wide-angle cameras."""

    def __init__(self, w, h, fov_deg):
        self.w, self.h, self.fov = w, h, fov_deg
        self.f = (w / 2.0) / math.radians(fov_deg / 2.0)
        self.cx, self.cy = w / 2.0, h / 2.0

    def unproject(self, x, y):
        u, v = (x - self.cx) / self.f, (y - self.cy) / self.f
        th = np.sqrt(u * u + v * v)
        s = np.where(th > 1e-9, np.sin(th) / np.maximum(th, 1e-9), 1.0)
        return np.stack([u * s, v * s, np.cos(th)], -1)

    def project(self, rays):
        x, y, z = rays[..., 0], rays[..., 1], rays[..., 2]
        rxy = np.sqrt(x * x + y * y)
        th = np.arctan2(rxy, z)
        k = np.where(rxy > 1e-12, self.f * th / np.maximum(rxy, 1e-12), self.f)
        return self.cx + x * k, self.cy + y * k


def rect_unproject(x, y, w, h, fov_deg):
    """Rays of a straight (rectilinear) virtual camera - used for lens straightening."""
    f = (w / 2.0) / math.tan(math.radians(fov_deg / 2.0))
    r = np.stack([(x - w / 2.0) / f, (y - h / 2.0) / f, np.ones_like(x)], -1)
    return r / np.linalg.norm(r, axis=-1, keepdims=True)


def kabsch(a, b):
    """Rotation R with R @ a_i ~= b_i (rows are unit vectors)."""
    U, _, Vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    return Vt.T @ np.diag([1.0, 1.0, d]) @ U.T


def rotvec(R):
    return cv2.Rodrigues(R)[0].reshape(3)


def rotmat(v):
    return cv2.Rodrigues(np.asarray(v, dtype=np.float64).reshape(3, 1))[0]


# ---------------------------------------------------------------------------- motion

class RotationEstimator(object):
    """Frame-to-frame camera rotation (rotation vector, radians), through the lens model."""

    def __init__(self, fov=150.0):
        self.fov = fov
        self.prev = None
        self.prev_pts = None
        self.mask = None
        self.rng = np.random.default_rng(1)

    def reset(self):
        self.prev = None
        self.prev_pts = None

    def _mask(self, shape):
        if self.mask is None or self.mask.shape != shape:
            h, w = shape
            m = np.zeros(shape, np.uint8)
            cv2.ellipse(m, (w // 2, h // 2), (int(w * 0.47), int(h * 0.47)), 0, 0, 360, 255, -1)
            self.mask = m
        return self.mask

    def step(self, gray):
        h, w = gray.shape
        if self.prev is None or self.prev.shape != gray.shape:
            self.prev, self.prev_pts = gray, None
            return np.zeros(3), False
        if self.prev_pts is None or len(self.prev_pts) < 80:
            self.prev_pts = cv2.goodFeaturesToTrack(self.prev, maxCorners=260, qualityLevel=0.01,
                                                    minDistance=7, blockSize=7, mask=self._mask(gray.shape))
        result = (np.zeros(3), False)
        p1 = np.zeros((0, 2), np.float32)
        if self.prev_pts is not None and len(self.prev_pts) >= 12:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(self.prev, gray, self.prev_pts, None,
                                                  winSize=(21, 21), maxLevel=3)
            good = st.reshape(-1) == 1
            p0, p1 = self.prev_pts[good].reshape(-1, 2), nxt[good].reshape(-1, 2)
            if len(p0) >= 12:
                model = FisheyeModel(w, h, self.fov)
                a = model.unproject(p0[:, 0].astype(np.float64), p0[:, 1].astype(np.float64))
                b = model.unproject(p1[:, 0].astype(np.float64), p1[:, 1].astype(np.float64))
                thr = 1.5 / model.f
                best, best_n, n = None, 0, len(a)
                for _ in range(48):
                    idx = self.rng.choice(n, 3, replace=False)
                    R = kabsch(a[idx], b[idx])
                    inl = np.linalg.norm(a @ R.T - b, axis=1) < thr
                    k = int(inl.sum())
                    if k > best_n:
                        best, best_n = inl, k
                if best is not None and best_n >= 10:
                    result = (rotvec(kabsch(a[best], b[best])), True)
                    p1 = p1[best]
        self.prev_pts = p1.reshape(-1, 1, 2).astype(np.float32) if len(p1) >= 80 else None
        self.prev = gray
        return result


def angle_limits(src_w, zoom, fov):
    """How far (radians) the correction may turn the view before borders would show."""
    f = (src_w / 2.0) / math.radians(fov / 2.0)
    m = (1.0 - 1.0 / zoom) / 2.0 * src_w / f
    return np.array([0.8 * m, 0.8 * m, 3.0 * m])


# ---------------------------------------------------------------------------- smoothing

class _Tracker(object):
    """Critically damped alpha-beta filter: follows steady motion without lag."""

    def __init__(self, gain):
        self.set_gain(gain)
        self.p = None
        self.v = None

    def set_gain(self, gain):
        self.a = float(gain)
        self.b = self.a * self.a / (2.0 - self.a)

    def step(self, z, lim):
        if self.p is None:
            self.p, self.v = z.copy(), np.zeros_like(z)
            return np.zeros_like(z)
        pred = self.p + self.v
        r = z - pred
        self.p = pred + self.a * r
        self.v = self.v + self.b * r
        corr = self.p - z
        over = np.abs(corr) > lim
        if over.any():                           # at the margin: follow the camera, never show borders
            corr = np.clip(corr, -lim, lim)
            self.p = np.where(over, z + corr, self.p)
        return corr


class _AdaptiveTracker(_Tracker):
    """Raises the gain only while the camera really changes what it does (turn entry/exit).

    Shake makes the prediction error flip sign frame to frame; a maneuver makes
    it lean one way. |mean error| / mean |error| tells them apart.
    """

    def __init__(self, gain):
        self.mean = self.mabs = None
        _Tracker.__init__(self, gain)

    def set_gain(self, gain):
        self.base = float(gain)
        self.max_gain = max(0.22, self.base * 1.5)
        _Tracker.set_gain(self, gain)

    def step(self, z, lim):
        if self.p is not None:
            r = z - (self.p + self.v)
            if self.mean is None:
                self.mean, self.mabs = np.zeros_like(r), np.abs(r) + 1e-9
            self.mean = 0.8 * self.mean + 0.2 * r
            self.mabs = 0.8 * self.mabs + 0.2 * np.abs(r) + 1e-12
            lean = np.clip((np.abs(self.mean) / self.mabs - 0.5) / 0.4, 0.0, 1.0)
            a = self.base + (self.max_gain - self.base) * lean
            self.a, self.b = a, a * a / (2.0 - a)
        return _Tracker.step(self, z, lim)


class Stabilizer(object):
    """Both modes behind one call: push() a frame + its rotation, get back what to show.

    smooth=True delays frames by the preset's look-ahead; smooth=False returns
    the same frame immediately.
    """

    def __init__(self):
        self.strength = None
        self.smooth = None
        self.roll = True
        self.fov = 150.0
        self.reset()

    def configure(self, strength, smooth, roll, fov):
        if (strength, smooth, fov) != (self.strength, self.smooth, self.fov):
            self.strength, self.smooth, self.fov = strength, smooth, fov
            self.reset()
        self.roll = roll

    def reset(self):
        p = PRESETS.get(self.strength)
        self.zoom, self.delay, gain = (p if p else (1.0, 0, 0.3))
        self.trk = _AdaptiveTracker(gain)
        self.path = np.zeros(3)
        self.hist = deque()
        self.fail = 0

    def flush(self):
        """Drop buffered frames (e.g. after a reconnect)."""
        self.reset()

    def push(self, payload, rv, ok, src_w):
        """Returns (payload, correction rotation vector, zoom), or None while the look-ahead fills."""
        if not ok:
            self.fail += 1
            if self.fail > 6:                    # lost track (cut, black frame): restart smoothing
                self.trk = _AdaptiveTracker(self.trk.base)
                self.path = np.zeros(3)
        else:
            self.fail = 0
        self.path = self.path + np.asarray(rv)
        lim = angle_limits(src_w, self.zoom, self.fov)
        if not self.smooth:
            return payload, self._roll(self.trk.step(self.path, lim)), self.zoom
        self.hist.append((payload, self.path.copy()))
        if len(self.hist) <= self.delay:
            return None
        if len(self.hist) > 2 * self.delay + 1:
            self.hist.popleft()
        paths = np.array([h[1] for h in self.hist])
        center = len(self.hist) - 1 - self.delay
        idx = (np.arange(len(self.hist)) - center).astype(float)
        w = np.exp(-0.5 * (idx / (self.delay / 2.5)) ** 2)
        A = np.stack([np.ones_like(idx), idx], 1) * w[:, None]
        smooth = np.linalg.lstsq(A, paths * w[:, None], rcond=None)[0][0]   # local linear fit: no lag
        payload, path = self.hist[center]
        return payload, self._roll(np.clip(smooth - path, -lim, lim)), self.zoom

    def _roll(self, corr):
        return corr if self.roll else corr * np.array([1.0, 1.0, 0.0])


# ---------------------------------------------------------------------------- rendering maps

class WarpMaps(object):
    """Remap tables (output pixel -> source pixel) through framing, rotation and the lens.

    The mapping is smooth, so it is computed on a coarse grid and interpolated
    up: a couple of milliseconds per frame.
    """

    GRID = 8

    def __init__(self):
        self._rays = {}

    def build(self, src_w, src_h, out_w, out_h, A, corr=None, fov=150.0, straighten=None):
        """A: 2x3 output matrix (virtual camera pixels -> canvas); corr: correction rotation vector."""
        key = (src_w, src_h, out_w, out_h, tuple(np.round(A, 6).ravel()), fov, straighten)
        G = self.GRID
        g = self._rays.get(key)
        if g is None:
            # one extra cell on every side, computed exactly, so interpolation never clamps at the edges
            gw, gh = int(math.ceil(out_w / float(G))) + 2, int(math.ceil(out_h / float(G))) + 2
            qx = (np.arange(gw) + 0.5) * G - 0.5 - G
            qy = (np.arange(gh) + 0.5) * G - 0.5 - G
            QX, QY = np.meshgrid(qx, qy)
            Ai = cv2.invertAffineTransform(A)
            px = Ai[0, 0] * QX + Ai[0, 1] * QY + Ai[0, 2]
            py = Ai[1, 0] * QX + Ai[1, 1] * QY + Ai[1, 2]
            model = FisheyeModel(src_w, src_h, fov)
            rays = rect_unproject(px, py, src_w, src_h, straighten) if straighten else model.unproject(px, py)
            g = (rays, model)
            if len(self._rays) > 8:
                self._rays.pop(next(iter(self._rays)))
            self._rays[key] = g
        rays, model = g
        if corr is not None:
            rays = rays @ rotmat(-np.asarray(corr)).T
        sx, sy = model.project(rays)
        gh, gw = sx.shape
        mx = cv2.resize(sx.astype(np.float32), (gw * G, gh * G), interpolation=cv2.INTER_LINEAR)
        my = cv2.resize(sy.astype(np.float32), (gw * G, gh * G), interpolation=cv2.INTER_LINEAR)
        return mx[G:G + out_h, G:G + out_w], my[G:G + out_h, G:G + out_w]


# ---------------------------------------------------------------------------- framing

ASPECTS = {"16:9": 16 / 9.0, "9:16": 9 / 16.0, "1:1": 1.0, "4:5": 4 / 5.0, "4:3": 4 / 3.0}


def output_matrix(src_w, src_h, out_w, out_h, pre=None, zoom=1.0, pan=0.0):
    """Source pixels -> output canvas pixels (crop to the output aspect, pan, zoom, scale)."""
    a_out = out_w / float(out_h)
    if a_out < src_w / float(src_h):
        crop_h, crop_w = src_h, src_h * a_out
    else:
        crop_w, crop_h = src_w, src_w / a_out
    crop_w /= zoom
    crop_h /= zoom
    free = (src_w - crop_w) / 2.0
    cx = src_w / 2.0 + max(-1.0, min(1.0, pan)) * max(0.0, free)
    cy = src_h / 2.0
    s = out_w / crop_w
    base = np.array([[s, 0.0, out_w / 2.0 - s * cx], [0.0, s, out_h / 2.0 - s * cy]])
    return compose(base, pre) if pre is not None else base


def compose(a, b):
    """a after b, both 2x3."""
    A = np.vstack([a, [0, 0, 1]])
    B = np.vstack([b, [0, 0, 1]])
    return (A @ B)[:2]


def warp(rgb, m, out_w, out_h):
    return cv2.warpAffine(rgb, m, (int(out_w), int(out_h)), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)
