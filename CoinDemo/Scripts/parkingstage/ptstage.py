"""
Shared placement and loading for the Parking Tower stage (Lvl_ParkingTower).

The raw PLY (decompressed by parkingtower/analyze_ply.py) is placed by its Splat Actor:
  local(cm) = (z, x, -y) * 100          (OpenSplat4D import)
  world(cm) = R(rotator) . (local * MPU) + LOCATION
The rotator levels the deck (the scan leans about 0.6 degrees) and turns its long axis onto Unreal X, so the
collision boxes, the course and the camera horizon line up with the garage.
"""

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "parkingtower"))
import ptcommon  # noqa: E402

RAW_PLY = ptcommon.RAW_PLY
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "ParkingStage"))
GENERATED = os.path.normpath(os.path.join(HERE, "..", "generated"))
MPU = 3.8461538   # 2.5 m stalls (parkingtower/README.md)


def rotation_matrix(pitch, yaw, roll):
    """Unreal's FRotationMatrix: rows are the rotated X, Y, Z axes; world = v @ M."""
    p, y, r = (math.radians(a) for a in (pitch, yaw, roll))
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return np.array([
        [cp * cy, cp * sy, sp],
        [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
        [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp],
    ])


def local_cm(d):
    return np.stack([d["z"], d["x"], -d["y"]], 1).astype(np.float64) * 100.0 * MPU


def to_world(local, placement):
    M = rotation_matrix(*placement["rotation"])
    return local @ M + np.asarray(placement["location"])


def load(cols=("x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2", "f_dc_0", "f_dc_1", "f_dc_2")):
    return ptcommon.load_columns(RAW_PLY, list(cols))


class Renderer:
    """The standard 3DGS reference rasterizer (gsquality/reference_render.py) with cameras in the placed frame."""

    def __init__(self, placement, ply=RAW_PLY):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import ref_render  # noqa: E402  (parkingtower/ref_render.py)
        from gsquality import reference_render as rr
        self.rr = rr
        self.base = ref_render.Renderer(ply)
        self.M = rotation_matrix(*placement["rotation"])
        self.loc = np.asarray(placement["location"], np.float64)

    def subset(self, mask):
        """Keeps only these splats (a numpy bool array over the PLY rows) for the next renders."""
        import torch
        s = self.base.s
        sel = torch.from_numpy(np.flatnonzero(mask)).to(s["pos"].device)
        self.s = {k: (v[sel] if torch.is_tensor(v) and v.shape[0] == s["n"] else v) for k, v in s.items()}
        self.s["n"] = len(sel)

    def camera(self, x, y, z, yaw, pitch):
        """World camera -> PLY space eye and rows right, down, forward."""
        to_ply = lambda v: np.array([v[1], -v[2], v[0]])
        eye_local = (np.array([x, y, z]) - self.loc) @ self.M.T
        yr, pr = math.radians(yaw), math.radians(pitch)
        fwd = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), math.sin(pr)])
        right = np.array([-math.sin(yr), math.cos(yr), 0.0])
        up = np.array([-math.sin(pr) * math.cos(yr), -math.sin(pr) * math.sin(yr), math.cos(pr)])
        f, r, u = (to_ply(v @ self.M.T) for v in (fwd, right, up))
        return to_ply(eye_local) / (100.0 * MPU), np.stack([r, -u, f])

    def render(self, x, y, z, yaw, pitch, width, height, hfov):
        eye, Rw = self.camera(x, y, z, yaw, pitch)
        return self.rr.render(getattr(self, "s", self.base.s), eye, Rw, width, height, hfov)
