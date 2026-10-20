"""
Step 6 data (outside Unreal): a selective hybrid for the north aisle that the reference video's first shot drives
along (zone X -1000..3096, Y -1324..-300 Unreal cm). Everything is measured from the raw PLY; nothing is invented
except the PBR micro detail added later in Unreal.

  ~/.venvs/gs/bin/python -I prepare_hybrid.py       (needs torch for the orthophoto)

Writes SourceAssets/ParkingTower/hybrid/:
  floor_ortho.png      top-down image of the floor splats only (reference rasterizer, 1 cm/px, SH degree 0 =
                       view independent colour), so ceiling and cars don't cover the floor
  hybrid.json          floor height field mesh (25 cm grid, from the splats' floor layer), pillar boxes,
                       light fixtures (bright ceiling splats), zone, UV mapping
  PT_HybridFloor.ply   the raw PLY without the zone's floor layer and below-floor (reflection) splats (E3, E4)
  PT_Hybrid.ply        the same, also without the splats inside the replaced pillars (E5)
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
import ptcommon as P  # noqa: E402

OUT = os.path.join(P.OUT_DIR, "hybrid")
MPU = 3.8461538
OFFSET_Z = -76.0
ZONE = {"x0": -1000.0, "x1": 3096.0, "y0": -1324.0, "y1": -300.0}   # 40.96 x 10.24 m
ORTHO_CM_PER_PX = 1.0
DECK_YAW = -3.8          # pillar rows run at this yaw in Unreal (measured from the orange pillar bases)
PILLARS = [(-823, -831), (207, -900), (1237, -968), (2266, -1034), (266, -132), (1296, -201), (2326, -269)]
PILLAR_SIZE = 50.0       # cm, square (surface splats span 39-48 cm; the cladding is a little wider)
PILLAR_ORANGE_TOP = 140.0
PILLAR_TOP = 300.0
FLOOR_REMOVE_ABOVE = 6.0  # cm above the floor: splats lower than this inside the zone are replaced by the mesh


def ue(d):
    return np.stack([d["z"] * MPU * 100, d["x"] * MPU * 100, -d["y"] * MPU * 100 + OFFSET_Z], 1)


def ground_heightmap(pos, op, cell=50.0):
    """Weighted mode of the splat heights around the floor per 50 cm cell over the zone (+2 m margin)."""
    x0, x1, y0, y1 = ZONE["x0"] - 200, ZONE["x1"] + 200, ZONE["y0"] - 200, ZONE["y1"] + 200
    W, H = int((x1 - x0) / cell) + 1, int((y1 - y0) / cell) + 1
    m = (pos[:, 0] > x0) & (pos[:, 0] < x1) & (pos[:, 1] > y0) & (pos[:, 1] < y1) & (pos[:, 2] > -80) & (pos[:, 2] < 60) & (op > 0.2)
    ix, iy = ((pos[m, 0] - x0) / cell).astype(int), ((pos[m, 1] - y0) / cell).astype(int)
    nb = 70
    ib = np.clip(((pos[m, 2] + 80) / 140 * nb).astype(int), 0, nb - 1)
    hist = np.zeros((H, W, nb))
    np.add.at(hist, (iy, ix, ib), op[m])
    hist = ndimage.gaussian_filter1d(hist, 1.0, axis=2)
    g = -80 + (hist.argmax(2) + 0.5) * 140 / nb
    ok = hist.max(2) > 0.3
    g = np.where(ok, g, np.median(g[ok]))
    g = ndimage.gaussian_filter(ndimage.median_filter(g, size=5), 1.0)
    return g, (x0, y0, cell)


def sample(g, frame, x, y):
    x0, y0, cell = frame
    return ndimage.map_coordinates(g, [(np.asarray(y) - y0) / cell - 0.5, (np.asarray(x) - x0) / cell - 0.5], order=1, mode="nearest")


def floor_mesh(g, frame, step=25.0):
    xs = np.arange(ZONE["x0"], ZONE["x1"] + 0.1, step)
    ys = np.arange(ZONE["y0"], ZONE["y1"] + 0.1, step)
    X, Y = np.meshgrid(xs, ys)
    Z = sample(g, frame, X.ravel(), Y.ravel()) + 1.0
    u = (Y.ravel() - ZONE["y0"]) / (ZONE["y1"] - ZONE["y0"])
    v = (ZONE["x1"] - X.ravel()) / (ZONE["x1"] - ZONE["x0"])
    nx, ny = len(xs), len(ys)
    idx = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = j * nx + i, j * nx + i + 1, (j + 1) * nx + i, (j + 1) * nx + i + 1
            # Unreal front faces: (P2 - P0) x (P1 - P0) must point up (+Z)
            idx += [a, c, b, b, c, d]
    return {"positions": np.stack([X.ravel(), Y.ravel(), Z], 1).round(2).tolist(), "uvs": np.stack([u, v], 1).round(5).tolist(), "indices": idx}


def pillar_boxes(g, frame):
    out = []
    for cx, cy in PILLARS:
        floor = float(sample(g, frame, [cx], [cy])[0])
        out.append({"center": [cx, cy], "yaw": DECK_YAW, "size": PILLAR_SIZE, "floor": round(floor, 1),
                    "orange_top": round(floor + PILLAR_ORANGE_TOP, 1), "top": round(floor + PILLAR_TOP, 1)})
    return out


def fixtures(pos, op, col):
    lum = col.mean(1)
    m = (lum > 0.85) & (pos[:, 2] > 190) & (pos[:, 2] < 300) & (op > 0.3) & (pos[:, 0] > ZONE["x0"] - 300) & (pos[:, 0] < ZONE["x1"] + 300) & \
        (pos[:, 1] > ZONE["y0"] - 300) & (pos[:, 1] < ZONE["y1"] + 300)
    res = 10.0
    x0, y0 = ZONE["x0"] - 300, ZONE["y0"] - 300
    ix, iy = ((pos[m, 0] - x0) / res).astype(int), ((pos[m, 1] - y0) / res).astype(int)
    grid = np.zeros((iy.max() + 1, ix.max() + 1))
    np.add.at(grid, (iy, ix), op[m])
    lab, n = ndimage.label(grid > 0.5)
    zs = np.zeros_like(grid)
    np.add.at(zs, (iy, ix), pos[m, 2] * op[m])
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        w = grid[ys, xs].sum()
        length = (xs.max() - xs.min() + 1) * res
        if w < 40 or length < 90:
            continue
        out.append({"x": float(xs.mean() * res + x0 + 5), "y": float(ys.mean() * res + y0 + 5),
                    "z": float(zs[ys, xs].sum() / w), "length": float(min(length, 130.0)), "weight": float(w)})
    return out


def ortho(keep_mask):
    """Top-down near-orthographic render of a subset of splats with the reference rasterizer."""
    import torch
    import ref_render as R
    r = R.Renderer(P.RAW_PLY)
    sel = torch.from_numpy(np.flatnonzero(keep_mask)).cuda()
    s = {k: (v[sel] if torch.is_tensor(v) and v.shape[0] == r.s["n"] else v) for k, v in r.s.items()}
    s["degree"] = 0
    s["n"] = len(sel)
    W = int((ZONE["y1"] - ZONE["y0"]) / ORTHO_CM_PER_PX)
    H = int((ZONE["x1"] - ZONE["x0"]) / ORTHO_CM_PER_PX)
    height = 50000.0                     # 500 m up: perspective error < 0.1 % over the floor's height range
    hfov = math.degrees(2 * math.atan(W * ORTHO_CM_PER_PX / 2 / height))
    cx, cy = (ZONE["x0"] + ZONE["x1"]) / 2, (ZONE["y0"] + ZONE["y1"]) / 2
    p = np.array([cx, cy, height]) - R.ACTOR_OFFSET
    eye, Rw = R.rr.ue_camera(p[0], p[1], p[2], 0.0, -89.999, MPU)
    img, alpha = R.rr.render(s, eye, Rw, W, H, hfov)
    return img, alpha


def main():
    os.makedirs(OUT, exist_ok=True)
    names = ["x", "y", "z", "opacity", "f_dc_0", "f_dc_1", "f_dc_2"]
    d = P.load_columns(P.RAW_PLY, names)
    pos = ue(d)
    op = 1 / (1 + np.exp(-d["opacity"]))
    col = np.clip(0.5 + P.SH_C0 * np.stack([d["f_dc_0"], d["f_dc_1"], d["f_dc_2"]], 1), 0, 1)
    g, frame = ground_heightmap(pos, op)
    h = pos[:, 2] - sample(g, frame, pos[:, 0], pos[:, 1])
    inzone = (pos[:, 0] > ZONE["x0"]) & (pos[:, 0] < ZONE["x1"]) & (pos[:, 1] > ZONE["y0"]) & (pos[:, 1] < ZONE["y1"])

    # splats removed for the hybrid: the zone's floor layer and everything below it (mirror reflection splats)
    remove_floor = inzone & (h < FLOOR_REMOVE_ABOVE)
    remove = remove_floor.copy()
    pillars = pillar_boxes(g, frame)
    a = math.radians(DECK_YAW)
    for pb in pillars:
        dx, dy = pos[:, 0] - pb["center"][0], pos[:, 1] - pb["center"][1]
        u, v = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
        half = pb["size"] / 2 + 6
        remove |= (np.abs(u) < half) & (np.abs(v) < half) & (pos[:, 2] > pb["floor"] - 100) & (pos[:, 2] < pb["top"])

    # floor orthophoto: only the floor layer (+-5 cm), slightly larger than the zone so the edges are complete
    floor_layer = (pos[:, 0] > ZONE["x0"] - 100) & (pos[:, 0] < ZONE["x1"] + 100) & (pos[:, 1] > ZONE["y0"] - 100) & \
        (pos[:, 1] < ZONE["y1"] + 100) & (np.abs(h) < 5.0)
    img, alpha = ortho(floor_layer)
    # where the floor layer is thin (the plain epoxy floor: from above it is mostly translucent, its look comes
    # from stacked and below-floor splats), fill with the locally averaged floor colour (normalised convolution)
    sigma = 25.0
    blur = np.stack([ndimage.gaussian_filter(img[..., c], sigma) for c in range(3)], -1)
    wsum = ndimage.gaussian_filter(alpha, sigma)[..., None]
    local = blur / np.maximum(wsum, 1e-3)
    rgb = img + (1 - alpha[..., None]) * local
    thin = alpha < 0.15
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "floor_ortho.png"))
    Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "floor_ortho_alpha.png"))

    info = {"zone": ZONE, "mpu": MPU, "offset_z": OFFSET_Z, "floor": floor_mesh(g, frame), "pillars": pillars,
            "fixtures": fixtures(pos, op, col), "removed_floor_splats": int(remove_floor.sum()), "removed_splats": int(remove.sum()), "kept_splats": int((~remove).sum()),
            "ortho_alpha_lt_0.15_fraction": float(thin.mean()),
            "floor_mean_srgb": [round(float(v), 4) for v in np.clip(rgb, 0, 1).reshape(-1, 3).mean(0)]}
    json.dump(info, open(os.path.join(OUT, "hybrid.json"), "w"))
    print({k: v for k, v in info.items() if k not in ("floor", "pillars", "fixtures")}, len(info["fixtures"]), "fixtures")

    # trimmed PLY: rows of the standard PLY kept as they are
    buf = P.read_all(P.RAW_PLY)
    end = buf.index(b"end_header\n") + len(b"end_header\n")
    header = buf[:end]
    names_all = [l.split()[-1].decode() for l in header.splitlines() if l.startswith(b"property")]
    data = np.frombuffer(buf, dtype=np.dtype([(n, "<f4") for n in names_all]), offset=end)
    for name, rm in (("PT_HybridFloor.ply", remove_floor), ("PT_Hybrid.ply", remove)):
        kept = data[~rm]
        old = next(l for l in header.splitlines() if l.startswith(b"element vertex"))
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(header.replace(old, b"element vertex %d" % len(kept)))
            f.write(kept.tobytes())
        del kept


if __name__ == "__main__":
    main()
