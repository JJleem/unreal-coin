"""
Step 2 (outside Unreal): floor height field and solid objects of the deck, in the placed frame (Unreal cm).

  ~/.venvs/gs/bin/python -I objects.py

Writes SourceAssets/ParkingStage/objects.json and objects.png (ortho with blocked cells and labelled objects):
  floor     50 cm height field over the deck: opacity weighted mode of the splats near the floor, median filtered
            (wheel stops, cars and noise don't lift it), the deck rises and falls about 15 cm end to end
  blocked   10 cm cells with dense splats at body height (30-190 cm above the floor)
  objects   connected blobs of blocked cells: area, box, top height (95th percentile of their splats' heights);
            cars are 4-14 m2 blobs, pillars small square ones
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

# deck rectangle that is mapped (world cm); the playable area inside it is chosen in plan.py
X0, X1, Y0, Y1 = -3800.0, 4400.0, -1400.0, 1650.0
FLOOR_CELL = 50.0
CELL = 10.0
BAND = (30.0, 190.0)
BODY_OPACITY = 120.0      # summed opacity per m2 in the band that makes a 10 cm cell solid


def main():
    pl = json.load(open(os.path.join(S.OUT_DIR, "placement.json")))
    d = S.load()
    w = S.to_world(S.local_cm(d), pl)
    op = 1 / (1 + np.exp(-d["opacity"].astype(np.float64)))
    size = np.exp(np.max(np.stack([d["scale_0"], d["scale_1"], d["scale_2"]], 1), 1)) * 100 * S.MPU
    m = (w[:, 0] > X0) & (w[:, 0] < X1) & (w[:, 1] > Y0) & (w[:, 1] < Y1) & (w[:, 2] > -100) & (w[:, 2] < 400)
    P, O, Z = w[m], op[m], size[m]

    # floor
    fx, fy = int((X1 - X0) / FLOOR_CELL), int((Y1 - Y0) / FLOOR_CELL)
    near = (np.abs(P[:, 2]) < 70) & (O > 0.05) & (Z < 40)
    fi = ((P[near, 0] - X0) // FLOOR_CELL).astype(int)
    fj = ((P[near, 1] - Y0) // FLOOR_CELL).astype(int)
    nb = 70
    hist = np.zeros((fx, fy, nb))
    np.add.at(hist, (fi, fj, np.clip(((P[near, 2] + 70) / 2).astype(int), 0, nb - 1)), O[near])
    hist = ndimage.gaussian_filter1d(hist, 1.0, axis=2)
    fz = -70 + (hist.argmax(2) + 0.5) * 2
    fw = hist.max(2)
    good = fw > 1.0
    fz = np.where(good, fz, np.median(fz[good]))
    fz = ndimage.median_filter(fz, size=7)
    fz = ndimage.gaussian_filter(fz, 1.5)

    def floor_at(x, y):
        return ndimage.map_coordinates(fz, [(np.asarray(x) - X0) / FLOOR_CELL - 0.5, (np.asarray(y) - Y0) / FLOOR_CELL - 0.5],
                                       order=1, mode="nearest")

    # body band density
    h = P[:, 2] - floor_at(P[:, 0], P[:, 1])
    nx, ny = int((X1 - X0) / CELL), int((Y1 - Y0) / CELL)
    band = (h > BAND[0]) & (h < BAND[1]) & (Z < 80)
    i = ((P[band, 0] - X0) // CELL).astype(int)
    j = ((P[band, 1] - Y0) // CELL).astype(int)
    body = np.zeros((nx, ny))
    np.add.at(body, (i, j), O[band])
    body /= (CELL / 100) ** 2
    body = ndimage.gaussian_filter(body, 0.7)
    blocked = body > BODY_OPACITY
    blocked = ndimage.binary_closing(blocked, np.ones((3, 3)))
    blocked = ndimage.binary_opening(blocked, np.ones((2, 2)))

    # objects
    lab, n = ndimage.label(blocked, np.ones((3, 3)))
    hi = ((P[:, 0] - X0) // CELL).astype(int).clip(0, nx - 1)
    hj = ((P[:, 1] - Y0) // CELL).astype(int).clip(0, ny - 1)
    tall = (h > 20) & (h < 330) & (O > 0.3) & (Z < 60)
    obj_of = lab[hi[tall], hj[tall]]
    hts = h[tall]
    objects = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        mask = lab[sl] == k
        area = mask.sum() * (CELL / 100) ** 2
        if area < 0.04:
            continue
        sel = obj_of == k
        top = float(np.percentile(hts[sel], 95)) if sel.sum() > 20 else float("nan")
        box = [X0 + sl[0].start * CELL, Y0 + sl[1].start * CELL, X0 + sl[0].stop * CELL, Y0 + sl[1].stop * CELL]
        objects.append({"id": k, "area": round(float(area), 2), "box": [round(v, 1) for v in box], "top": round(top, 1),
                        "fill": round(float(mask.mean()), 2)})

    out = {"floor": {"x0": X0, "y0": Y0, "cell": FLOOR_CELL, "z": fz.round(1).tolist()},
           "grid": {"x0": X0, "y0": Y0, "cell": CELL, "shape": [nx, ny]}, "objects": objects}
    json.dump(out, open(os.path.join(S.OUT_DIR, "objects.json"), "w"))
    np.save(os.path.join(S.OUT_DIR, "blocked.npy"), blocked)
    np.save(os.path.join(S.OUT_DIR, "labels.npy"), lab)

    # overlay on the ortho (5 cm/px, X = (1000 - row) * 5, Y = (col - 450) * 5)
    ortho = Image.open(os.path.join(S.OUT_DIR, "ortho_low.png")).convert("RGB")
    over = np.array(ortho).astype(np.float32)
    bi, bj = np.nonzero(blocked)
    for di in (0, 1):
        for dj in (0, 1):
            rows = (1000 - (X0 + (bi + 0.5) * CELL) / 5).astype(int) - di
            cols = ((Y0 + (bj + 0.5) * CELL) / 5 + 450).astype(int) + dj
            ok = (rows >= 0) & (rows < over.shape[0]) & (cols >= 0) & (cols < over.shape[1])
            over[rows[ok], cols[ok]] = over[rows[ok], cols[ok]] * 0.4 + np.array([255, 40, 40]) * 0.6
    img = Image.fromarray(over.astype(np.uint8))
    draw = ImageDraw.Draw(img)
    for o in objects:
        if o["area"] < 0.15:
            continue
        r0, r1 = 1000 - o["box"][2] / 5, 1000 - o["box"][0] / 5
        c0, c1 = o["box"][1] / 5 + 450, o["box"][3] / 5 + 450
        draw.rectangle([c0, r0, c1, r1], outline=(255, 255, 0))
        draw.text((c1 + 2, r0), f"{o['id']} {o['area']:.1f} {o['top']:.0f}", fill=(255, 255, 0))
    # grid ticks every 5 m
    for x in range(-35, 45, 5):
        r = 1000 - x * 20
        draw.line([0, r, 12, r], fill=(0, 255, 255))
        draw.text((14, r - 6), f"{x}", fill=(0, 255, 255))
    for y in range(-20, 25, 5):
        c = 450 + y * 20
        draw.line([c, 0, c, 12], fill=(0, 255, 255))
        draw.text((c + 2, 14), f"{y}", fill=(0, 255, 255))
    img.save(os.path.join(S.OUT_DIR, "objects.png"))
    print(len(objects), "objects;", "floor z range", fz.min().round(1), fz.max().round(1))
    for o in sorted(objects, key=lambda o: -o["area"])[:40]:
        print(o)


if __name__ == "__main__":
    main()
