"""
Surveys a scan for the city kit: where the scan is damaged, how much a player sees it, and what stands in the street.

  * damage per 1 m column (0..1): share of the column's opacity carried by splats that render as blur or streaks
    (longest axis > 0.5 m, or needles > 8:1), mixed with how faint the column is overall
  * exposure per column: how close it is to the walkable ground (the play path), 1 at the path, 0 beyond 15 m
  * priority = damage x exposure: what to fix first. Written as a map and a ranked list of 4 m tiles
  * poles: thin vertical splat columns 4-9 m tall standing on the ground (utility and sign poles)
  * vehicles: the collision pass' breakable blobs on the road with car-like size (often half reconstructed)

Output: generated/<Name>_survey.json and generated/<Name>_survey.png (+X up; red damage, green play path,
cyan poles, yellow vehicles).

  python scan_survey.py Hongdae
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rebuild.common import GENERATED_DIR, Scan, ground_grid, load_collision  # noqa: E402

CELL = 1.0


def main(name):
    scan = Scan(name)
    collision = load_collision(name)
    lo, height, walls = ground_grid(collision, 0.5)
    valid = np.argwhere(~np.isnan(height))
    _, k = cKDTree(valid).query((scan.pos[:, :2] - lo) / 0.5)
    above = scan.pos[:, 2] - height[valid[k, 0], valid[k, 1]]

    # damage per column, over what stands 0.3-12 m above the ground
    s = np.sort(scan.scale, 1)
    blur = (s[:, 2] > 0.5) | (s[:, 2] / np.maximum(s[:, 1], 1e-9) > 8.0)
    band = (above > 0.3) & (above < 12.0)
    ij = np.floor((scan.pos[:, :2] - lo) / CELL).astype(int)
    shape = ij.max(0) + 1
    total = np.zeros(shape)
    bad = np.zeros(shape)
    np.add.at(total, (ij[band, 0], ij[band, 1]), scan.opacity[band])
    np.add.at(bad, (ij[band & blur, 0], ij[band & blur, 1]), scan.opacity[band & blur])
    share = bad / np.maximum(total, 1e-6)
    faint = np.clip(1.0 - total / 40.0, 0, 1)   # columns with little substance read as haze
    damage = np.where(total > 1.0, np.clip(0.7 * share + 0.3 * faint, 0, 1), 0.0)

    # exposure: distance to the walkable cells
    walk = np.zeros(shape, bool)
    cells = np.argwhere(~np.isnan(height) & ~walls)
    w_ij = np.floor((lo + (cells + 0.5) * 0.5 - lo) / CELL).astype(int)
    w_ij = w_ij[(w_ij[:, 0] < shape[0]) & (w_ij[:, 1] < shape[1])]
    walk[w_ij[:, 0], w_ij[:, 1]] = True
    distance = ndimage.distance_transform_edt(~walk) * CELL
    exposure = np.clip(1.0 - distance / 15.0, 0, 1)
    priority = damage * exposure

    # 4 m tiles ranked by priority
    t = 4
    tiles = []
    for i in range(0, shape[0], t):
        for j in range(0, shape[1], t):
            p = priority[i:i + t, j:j + t]
            if p.size and p.mean() > 0.05:
                tiles.append({"x": round(float(lo[0] + (i + t / 2) * CELL), 1), "y": round(float(lo[1] + (j + t / 2) * CELL), 1),
                              "priority": round(float(p.mean()), 3), "damage": round(float(damage[i:i + t, j:j + t].mean()), 3)})
    tiles.sort(key=lambda r: -r["priority"])

    # poles: 0.25 m columns with dense, thin, tall vertical splat stacks
    fine = 0.25
    fij = np.floor((scan.pos[:, :2] - lo) / fine).astype(int)
    fshape = fij.max(0) + 1
    upright = (above > 0.5) & (above < 9.0) & (scan.opacity > 0.2) & (s[:, 2] < 0.4)
    levels = np.zeros((fshape[0], fshape[1], 9), bool)
    lv = np.clip(above[upright].astype(int), 0, 8)
    levels[fij[upright, 0], fij[upright, 1], lv] = True
    column = levels.sum(2)
    # a pole is a column filled at most heights whose neighbourhood (1 m) is mostly empty at mid height
    mid = levels[:, :, 3:7].sum(2)
    around = ndimage.uniform_filter(mid.astype(float), size=5) * 25 - mid
    pole_mask = (column >= 6) & (mid >= 3) & (around < 25)
    labels, n = ndimage.label(ndimage.binary_dilation(pole_mask))
    poles = []
    for r in range(1, n + 1):
        cells = np.argwhere(labels == r)
        if len(cells) > 12:
            continue  # too wide for a pole
        c = lo + (cells.mean(0) + 0.5) * fine
        poles.append({"x": round(float(c[0]), 2), "y": round(float(c[1]), 2), "height": float(column[labels == r].max())})

    # vehicles: breakables (small free-standing blobs from make_scan_collision.py) of car size
    vehicles = []
    for group in collision.get("breakables", []):
        b = np.array(group) / 100.0
        x0, y0, x1, y1 = b[:, 0].min(), b[:, 1].min(), b[:, 3].max(), b[:, 4].max()
        lx, ly = x1 - x0, y1 - y0
        if 3.0 <= max(lx, ly) <= 6.5 and 1.4 <= min(lx, ly) <= 2.6:
            vehicles.append({"box": [round(float(v), 2) for v in (x0, y0, x1, y1)]})

    out = {"stage": name, "cell": CELL, "lo": lo.round(3).tolist(), "tiles": tiles[:40], "poles": poles, "vehicles": vehicles,
           "summary": {"damaged_share_on_path": round(float((damage[walk] > 0.5).mean()), 3)}}
    with open(os.path.join(GENERATED_DIR, f"{name}_survey.json"), "w") as f:
        json.dump(out, f, indent=1)

    img = np.zeros((shape[0], shape[1], 3))
    img[..., 0] = damage
    img[..., 1] = walk * 0.35
    img = (np.clip(img, 0, 1) * 255).astype(np.uint8)[::-1]
    im = Image.fromarray(img).resize((shape[1] * 8, shape[0] * 8), Image.NEAREST)
    d = ImageDraw.Draw(im)
    to = lambda x, y: ((y - lo[1]) / CELL * 8, (shape[0] - (x - lo[0]) / CELL) * 8)
    for p in poles:
        cx, cy = to(p["x"], p["y"])
        d.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), outline=(0, 255, 255), width=2)
    for v in vehicles:
        x0, y0, x1, y1 = v["box"]
        (a, b), (c, e) = to(x1, y0), to(x0, y1)
        d.rectangle((a, b, c, e), outline=(255, 230, 0), width=2)
    im.save(os.path.join(GENERATED_DIR, f"{name}_survey.png"))
    print(f"{name}: {len(poles)} poles, {len(vehicles)} vehicles, damaged share of the play path "
          f"{out['summary']['damaged_share_on_path'] * 100:.0f}%, top tiles {[(t['x'], t['y'], t['priority']) for t in tiles[:5]]}")


for stage in sys.argv[1:] or ["Hongdae"]:
    main(stage)
