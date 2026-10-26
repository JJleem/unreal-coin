"""
Step 1b (outside Unreal, needs torch + CUDA): top-down view of the placed deck for level design and the debug overlays.

  ~/.venvs/gs/bin/python -I ortho.py

Renders the splats below 2.1 m (the ceiling would cover the floor) with the standard 3DGS reference rasterizer from
3 km up, 5 cm/px over X -50..50 m, Y -22.5..22.5 m: SourceAssets/ParkingStage/ortho_low.png.
Pixel (col, row) is X = (1000 - row) * 5, Y = (col - 450) * 5 in Unreal cm (+X up).
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

CM_PER_PX = 5.0
WIDTH, HEIGHT = 900, 2000
CUT_Z = 210.0
CAMERA_Z = 300000.0


def main():
    placement = json.load(open(os.path.join(S.OUT_DIR, "placement.json")))
    renderer = S.Renderer(placement)
    world = S.to_world(S.local_cm(S.load(("x", "y", "z"))), placement)
    renderer.subset(world[:, 2] < CUT_Z)
    hfov = math.degrees(2 * math.atan(WIDTH * CM_PER_PX / 2 / CAMERA_Z))
    img, _ = renderer.render(0, 0, CAMERA_Z, 0.0, -89.99, WIDTH, HEIGHT, hfov)
    img = img.cpu().numpy() if hasattr(img, "cpu") else img
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(S.OUT_DIR, "ortho_low.png"))


if __name__ == "__main__":
    main()
