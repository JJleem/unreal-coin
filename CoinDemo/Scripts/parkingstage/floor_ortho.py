"""
Reconstruction step R1 (outside Unreal, torch + CUDA): a 2 cm/px top-down image of the deck floor alone, for
reading the floor plan (paint lines, arrows, crosswalks, coloured stalls) in drawing.py.

  ~/.venvs/gs/bin/python -I floor_ortho.py

Only the splats near the floor are drawn (-30..+25 cm around the measured floor, objects.json: the epoxy is built
from several translucent layers, a thinner cut loses lines), with view
independent colour (SH degree 0), so cars, pillars, wheel stops and the reflection splats under the floor don't
cover or tint the markings. Rendered in 20 m tiles and stitched:
  SourceAssets/ParkingStage/floor_ortho.png        X = X1 - row * CM_PER_PX, Y = Y0 + col * CM_PER_PX (+X up)
  SourceAssets/ParkingStage/floor_ortho_alpha.png  coverage
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

CM_PER_PX = 2.0
X0, X1, Y0, Y1 = -3800.0, 4400.0, -1500.0, 1600.0
TILE = 2000.0
LAYER = (-30.0, 25.0)
CAMERA_Z = 300000.0

Image.MAX_IMAGE_PIXELS = None


def main():
    placement = json.load(open(os.path.join(S.OUT_DIR, "placement.json")))
    objects = json.load(open(os.path.join(S.OUT_DIR, "objects.json")))
    fl = objects["floor"]
    fz = np.array(fl["z"])
    world = S.to_world(S.local_cm(S.load(("x", "y", "z"))), placement)
    floor = ndimage.map_coordinates(fz, [(world[:, 0] - fl["x0"]) / fl["cell"] - 0.5, (world[:, 1] - fl["y0"]) / fl["cell"] - 0.5],
                                    order=1, mode="nearest")
    h = world[:, 2] - floor
    keep = (h > LAYER[0]) & (h < LAYER[1]) & (world[:, 0] > X0 - 100) & (world[:, 0] < X1 + 100) & \
           (world[:, 1] > Y0 - 100) & (world[:, 1] < Y1 + 100)
    print(f"floor layer: {keep.sum()} splats")

    renderer = S.Renderer(placement)
    renderer.subset(keep)
    renderer.s["degree"] = 0

    W = int(round((Y1 - Y0) / CM_PER_PX))
    H = int(round((X1 - X0) / CM_PER_PX))
    rgb = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    th = int(round(TILE / CM_PER_PX))
    for r0 in range(0, H, th):
        rows = min(th, H - r0)
        cx = X1 - (r0 + rows / 2) * CM_PER_PX
        cy = (Y0 + Y1) / 2
        hfov = math.degrees(2 * math.atan(W * CM_PER_PX / 2 / CAMERA_Z))
        img, a = renderer.render(cx, cy, CAMERA_Z, 0.0, -89.99, W, rows, hfov)
        rgb[r0:r0 + rows] = img.cpu().numpy() if hasattr(img, "cpu") else img
        alpha[r0:r0 + rows] = a.cpu().numpy() if hasattr(a, "cpu") else a
        print(f"tile rows {r0}-{r0 + rows}")
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(S.OUT_DIR, "floor_ortho.png"))
    Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).save(os.path.join(S.OUT_DIR, "floor_ortho_alpha.png"))


if __name__ == "__main__":
    main()
