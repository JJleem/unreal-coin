"""
Step 1 (outside Unreal): measures how to place the Parking Tower scan and maps the deck for level design.

  ~/.venvs/gs/bin/python -I survey.py

  * placement: yaw from the orange pillar rows (onto Unreal X), pitch and roll that make the floor plane level,
    location that puts the deck centre at the origin with the floor at Z = 0  -> SourceAssets/ParkingStage/placement.json
  * maps in the placed frame, 10 cm cells (+X up in the images):
      survey_floor.png      top-down colour of the floor layer
      survey_body.png       summed opacity at body height (30-190 cm above the floor): cars, pillars, walls, rails
      survey_ceiling.png    height of the lowest dense layer above 2 m
      survey_floorz.png     floor height, +-20 cm
    and the arrays in survey.npz for plan.py
"""

import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage, optimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

CELL = 10.0


def colours(d):
    return np.clip(0.5 + 0.28209479 * np.stack([d["f_dc_0"], d["f_dc_1"], d["f_dc_2"]], 1), 0, 1)


def floor_modes(pos, op, cell=50.0, zr=(-150, 150)):
    """Opacity weighted mode of splat heights per cell near the floor; returns cell centres and heights."""
    m = (pos[:, 2] > zr[0]) & (pos[:, 2] < zr[1]) & (op > 0.2)
    lo = pos[m, :2].min(0)
    ij = ((pos[m, :2] - lo) // cell).astype(int)
    nb = int((zr[1] - zr[0]) / 2)
    ib = np.clip(((pos[m, 2] - zr[0]) / 2).astype(int), 0, nb - 1)
    shape = ij.max(0) + 1
    hist = np.zeros((shape[0], shape[1], nb), np.float32)
    np.add.at(hist, (ij[:, 0], ij[:, 1], ib), op[m])
    hist = ndimage.gaussian_filter1d(hist, 1.5, axis=2)
    z = zr[0] + (hist.argmax(2) + 0.5) * 2
    w = hist.max(2)
    gi, gj = np.nonzero(w > 2.0)
    xy = lo + (np.stack([gi, gj], 1) + 0.5) * cell
    return xy, z[gi, gj], w[gi, gj]


def main():
    os.makedirs(S.OUT_DIR, exist_ok=True)
    d = S.load()
    local = S.local_cm(d)
    op = 1 / (1 + np.exp(-d["opacity"].astype(np.float64)))
    col = colours(d)
    size = np.exp(np.max(np.stack([d["scale_0"], d["scale_1"], d["scale_2"]], 1), 1)) * 100 * S.MPU

    # the study's level offset (-76 cm) put the floor near z = 0 in local cm + offset; restrict to the deck core
    core = (np.abs(local[:, 0]) < 4500) & (np.abs(local[:, 1]) < 2000) & (local[:, 2] > -400) & (local[:, 2] < 600)

    # yaw: orange pillar cladding (0.3-1.3 m above the floor), clustered
    orange = core & (col[:, 0] > 0.55) & (col[:, 1] > 0.2) & (col[:, 1] < 0.5) & (col[:, 2] < 0.22) & (op > 0.5) & \
        (local[:, 2] > 76 - 50) & (local[:, 2] < 76 + 130)
    grid = np.zeros((900, 400))
    ij = ((local[orange, :2] + [4500, 2000]) // 10).astype(int)
    np.add.at(grid, (ij[:, 0], ij[:, 1]), 1)
    grid = ndimage.gaussian_filter(grid, 1.5)
    lab, n = ndimage.label(grid > 0.8)
    pillars = []
    for k in range(1, n + 1):
        sl = lab == k
        mass = grid[sl].sum()
        if mass > 30:
            ci, cj = ndimage.center_of_mass(grid, lab, k)
            pillars.append([ci * 10 - 4500 + 5, cj * 10 - 2000 + 5, mass])
    pillars = np.array(pillars)
    print(f"{len(pillars)} orange clusters")

    # rows: group by y after a coarse yaw, fit a common slope
    def row_slope(p):
        best = None
        for deg in np.arange(-8, 8, 0.05):
            a = np.radians(deg)
            v = -p[:, 0] * np.sin(a) + p[:, 1] * np.cos(a)
            hist, _ = np.histogram(v, bins=np.arange(-2000, 2000, 25))
            score = (hist ** 2).sum()
            if best is None or score > best[0]:
                best = (score, deg)
        return best[1]
    deck_deg = row_slope(pillars[:, :2])
    print(f"pillar rows at {deck_deg:.2f} deg")

    # floor plane (local cm) from cell modes over the deck
    xy, z, w = floor_modes(local[core], op[core])
    med = np.median(z)
    keep = np.abs(z - med) < 40
    A = np.column_stack([xy[keep], np.ones(keep.sum())])
    coef = np.linalg.lstsq(A, z[keep], rcond=None)[0]
    for _ in range(3):
        res = z - (np.column_stack([xy, np.ones(len(xy))]) @ coef)
        keep = np.abs(res) < 6
        coef = np.linalg.lstsq(np.column_stack([xy[keep], np.ones(keep.sum())]), z[keep], rcond=None)[0]
    normal = np.array([-coef[0], -coef[1], 1.0])
    normal /= np.linalg.norm(normal)
    print(f"floor plane slope x {coef[0]:.5f} y {coef[1]:.5f} -> tilt {np.degrees(np.arccos(normal[2])):.3f} deg, "
          f"residual std {res[keep].std():.1f} cm over {keep.sum()} cells")

    yaw = -deck_deg

    def err(pr):
        M = S.rotation_matrix(pr[0], yaw, pr[1])
        n = normal @ M
        return n[0] ** 2 + n[1] ** 2
    pr = optimize.minimize(err, [0.0, 0.0], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-14}).x
    rot = [float(pr[0]), float(yaw), float(pr[1])]
    M = S.rotation_matrix(*rot)
    print("rotation pitch/yaw/roll", rot, "normal ->", normal @ M)

    world = local @ M
    # centre of the deck: middle of the pillar grid; floor height: plane at that point
    pc = (np.column_stack([pillars[:, :2], np.full(len(pillars), 76.0)]) @ M)
    centre = (pc[:, :2].min(0) + pc[:, :2].max(0)) / 2
    plane_pts = np.column_stack([xy[keep], xy[keep] @ coef[:2] + coef[2]]) @ M
    floor_z = np.median(plane_pts[:, 2])
    location = [-float(centre[0]), -float(centre[1]), -float(floor_z)]
    placement = {"rotation": rot, "location": location, "mpu": S.MPU,
                 "pillars_world": (pc[:, :2] + location[:2]).round(1).tolist()}
    json.dump(placement, open(os.path.join(S.OUT_DIR, "placement.json"), "w"), indent=1)
    print("location", location)
    world += location

    # maps in the placed frame
    x0, x1, y0, y1 = -5000, 5000, -2500, 2500
    nx, ny = int((x1 - x0) / CELL), int((y1 - y0) / CELL)
    inb = (world[:, 0] > x0) & (world[:, 0] < x1) & (world[:, 1] > y0) & (world[:, 1] < y1) & (world[:, 2] > -300) & (world[:, 2] < 800)
    P, O, C, Z = world[inb], op[inb], col[inb], size[inb]
    i = ((P[:, 0] - x0) // CELL).astype(int)
    j = ((P[:, 1] - y0) // CELL).astype(int)

    # floor height per cell: mode in -40..40 cm
    fl = (P[:, 2] > -40) & (P[:, 2] < 40) & (O > 0.15)
    nb = 40
    hist = np.zeros((nx, ny, nb), np.float32)
    np.add.at(hist, (i[fl], j[fl], np.clip(((P[fl, 2] + 40) / 2).astype(int), 0, nb - 1)), O[fl])
    floorw = hist.sum(2)
    floorz = -40 + (ndimage.gaussian_filter1d(hist, 1.0, axis=2).argmax(2) + 0.5) * 2
    del hist
    floorz_s = ndimage.median_filter(np.where(floorw > 0.5, floorz, 0), 5)

    # floor colour (thin layer, opacity weighted)
    fl2 = (np.abs(P[:, 2] - floorz_s[i, j]) < 6) & (Z < 30)
    rgb = np.zeros((nx, ny, 3))
    wsum = np.zeros((nx, ny))
    for c in range(3):
        np.add.at(rgb[..., c], (i[fl2], j[fl2]), C[fl2, c] * O[fl2])
    np.add.at(wsum, (i[fl2], j[fl2]), O[fl2])
    rgb = rgb / np.maximum(wsum, 1e-6)[..., None]

    # body band occupancy and ceiling
    h = P[:, 2] - floorz_s[i, j]
    band = (h > 30) & (h < 190) & (Z < 100)
    body = np.zeros((nx, ny))
    np.add.at(body, (i[band], j[band]), O[band])
    body /= (CELL / 100) ** 2
    # low obstacles (wheel stops, kerbs): 4-30 cm
    low = (h > 4) & (h < 30) & (Z < 40)
    lowo = np.zeros((nx, ny))
    np.add.at(lowo, (i[low], j[low]), O[low])
    lowo /= (CELL / 100) ** 2
    # ceiling: lowest 10 cm layer above 200 cm with summed opacity > 1
    up = (h > 150) & (h < 450) & (Z < 100) & (O > 0.2)
    cb = 30
    chist = np.zeros((nx, ny, cb), np.float32)
    np.add.at(chist, (i[up], j[up], np.clip(((h[up] - 150) / 10).astype(int), 0, cb - 1)), O[up])
    dense = chist > 0.6
    ceiling = np.where(dense.any(2), 150 + dense.argmax(2) * 10, 450)

    np.savez_compressed(os.path.join(S.OUT_DIR, "survey.npz"), x0=x0, y0=y0, cell=CELL, floorz=floorz_s, floorw=floorw,
                        rgb=rgb.astype(np.float32), wsum=wsum, body=body, low=lowo, ceiling=ceiling)

    def save(name, img):
        Image.fromarray(img[::-1]).save(os.path.join(S.OUT_DIR, name))
    save("survey_floor.png", (np.clip(rgb * np.clip(wsum, 0, 1)[..., None], 0, 1) ** (1 / 1.4) * 255).astype(np.uint8))
    save("survey_body.png", (np.clip(body / 60, 0, 1) * 255).astype(np.uint8))
    save("survey_low.png", (np.clip(lowo / 60, 0, 1) * 255).astype(np.uint8))
    save("survey_ceiling.png", (np.clip((ceiling - 150) / 300, 0, 1) * 255).astype(np.uint8))
    save("survey_floorz.png", (np.clip((floorz_s + 20) / 40, 0, 1) * 255 * (floorw > 0.5)).astype(np.uint8))
    print("floor cells", (floorw > 0.5).sum() * (CELL / 100) ** 2, "m2")


if __name__ == "__main__":
    main()
