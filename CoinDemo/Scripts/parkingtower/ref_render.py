"""
Reference renderer for the Parking Tower study: the standard 3DGS rasterizer of gsquality/reference_render.py
(INRIA algorithm, PyTorch, SH degree 3), with this scan's own placement in Unreal instead of a stage's
metresPerUnit:  UE(cm) = (z, x, -y) * MPU * 100 + ACTOR_OFFSET   (the Splat Actor: scale MPU, location ACTOR_OFFSET).

  python ref_render.py <ply> <out.png> x y z yaw pitch [width height hfov [bg]]      (Unreal cm / degrees, like
                                                                                   DevCapture -Views=...,cam)
  python ref_render.py <ply> <out.png> --viewer px py pz tx ty tz vfov width height [bg]
                                                                                   (PlayCanvas/SuperSplat viewer
                                                                                   camera from settings.json)
bg: background grey 0..1 (default 0 = black, as the Unreal level has a dark ground; SuperSplat's is 0.47).
Also importable: Renderer(ply).render_ue(...) for pose fitting.
"""

import math
import os
import sys

import numpy as np
import torch
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import ptcommon  # noqa: E402
from gsquality import reference_render as rr  # noqa: E402

# Placement of the scan in Lvl_ParkingTower_ReverseStudy (see analyze_ply.py for how it was measured)
MPU = 3.85
ACTOR_OFFSET = np.array([0.0, 0.0, -76.0])


class Renderer:
    def __init__(self, ply, device="cuda", max_degree=3):
        names = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2"] + [f"f_rest_{i}" for i in range(45)] + \
                ["opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
        d = ptcommon.load_columns(ply, names)
        n = len(d["x"])
        f = lambda *cols: torch.from_numpy(np.stack([d[c] for c in cols], 1).astype(np.float32)).to(device)
        sh = torch.zeros(n, 3, 16, device=device)
        sh[:, :, 0] = f("f_dc_0", "f_dc_1", "f_dc_2")
        sh[:, :, 1:] = f(*[f"f_rest_{i}" for i in range(45)]).view(n, 3, 15)
        self.s = {"pos": f("x", "y", "z"), "scl": torch.exp(f("scale_0", "scale_1", "scale_2")),
                  "rot": f("rot_0", "rot_1", "rot_2", "rot_3"), "alpha": torch.sigmoid(f("opacity"))[:, 0],
                  "sh": sh, "degree": max_degree, "n": n}
        del d

    def render_ue(self, x, y, z, yaw, pitch, width, height, hfov):
        p = (np.array([x, y, z]) - ACTOR_OFFSET)
        eye, Rw = rr.ue_camera(p[0], p[1], p[2], yaw, pitch, MPU)
        return rr.render(self.s, eye, Rw, width, height, hfov)

    def render_viewer(self, pos, target, vfov, width, height):
        """PlayCanvas viewer camera: the viewer shows the PLY rotated 180 degrees about Z, so (x, y) flip."""
        to_ply = lambda v: np.array([-v[0], -v[1], v[2]], dtype=np.float64)
        eye, tgt = to_ply(pos), to_ply(target)
        fwd = tgt - eye
        fwd /= np.linalg.norm(fwd)
        up_ply = np.array([0.0, -1.0, 0.0])          # viewer +Y up = PLY -Y
        right = np.cross(fwd, up_ply)
        right /= np.linalg.norm(right)
        down = np.cross(fwd, right)
        Rw = np.stack([right, down, fwd])
        hfov = 2 * math.degrees(math.atan(math.tan(math.radians(vfov) / 2) * width / height))
        return rr.render(self.s, eye, Rw, width, height, hfov)


def to_image(img, alpha, bg=0.0):
    rgb = img + (1 - alpha[..., None]) * bg
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def main():
    ply, out = sys.argv[1], sys.argv[2]
    r = Renderer(ply)
    if sys.argv[3] == "--viewer":
        v = list(map(float, sys.argv[4:11]))
        width, height = int(sys.argv[11]), int(sys.argv[12])
        bg = float(sys.argv[13]) if len(sys.argv) > 13 else 0.0
        img, alpha = r.render_viewer(v[0:3], v[3:6], v[6], width, height)
    else:
        x, y, z, yaw, pitch = map(float, sys.argv[3:8])
        width, height, hfov = (int(sys.argv[8]), int(sys.argv[9]), float(sys.argv[10])) if len(sys.argv) > 10 else (1600, 900, 90.0)
        bg = float(sys.argv[11]) if len(sys.argv) > 11 else 0.0
        img, alpha = r.render_ue(x, y, z, yaw, pitch, width, height, hfov)
    to_image(img, alpha, bg).save(out)
    print(f"{out}: {r.s['n']:,} splats")


if __name__ == "__main__":
    main()
