"""
Step 2 of the Parking Tower reverse study: numbers that say how good the raw scan is, next to the Hongdae scan.

  python analyze_ply.py            (WSL venv with numpy/scipy/Pillow)

1. Decompresses parking-tower/scene.compressed (2).ply (PlayCanvas compressed PLY) to the standard 3DGS layout in
   SourceAssets/ParkingTower/ParkingTower_raw.ply (skipped when it exists; delete it to redo).
2. Finds the up axis, the floor plane and the scale (metres per unit) from the stall line pitch, the beam clearance
   and a parked car.
3. Computes the same statistics for both scans in metres: opacity, splat size, needles, extent, how much of the
   budget sits in the used area, ground surface density / coverage, splats below the ground, SH energy.
4. Writes Saved/ScanQuality/ParkingTower_ReverseStudy/analysis/{stats.json, stats.txt, *.png}.
"""

import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptcommon as P  # noqa: E402

OUT = os.path.join(P.SHOTS_DIR, "analysis")
REPO = P.REPO
HONGDAE_PLY = os.path.join(REPO, "Scans", "01_Hongdae", "Hongdae.ply")
HONGDAE_COLLISION = os.path.join(REPO, "CoinDemo", "Scripts", "generated", "Hongdae_collision.json")
HONGDAE_MPU = 3.5589744039282993 * 2.0          # stage.json metresPerUnit x stage_scale.json
STALL_WIDTH_M = 2.5                              # Korean standard stall width (2.3 m before 2019 / 2.5 m now)


def pct(a, q=(1, 5, 25, 50, 75, 95, 99)):
    return {str(k): float(v) for k, v in zip(q, np.percentile(a, q))}


def sh_degree(path):
    with open(path, "rb") as f:
        head = f.read(8000).split(b"end_header")[0]
    k = head.count(b"f_rest_")
    return {0: 0, 9: 1, 24: 2, 45: 3}[k]


def load(path, degree):
    cols = ["x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2", "f_dc_0", "f_dc_1", "f_dc_2"]
    cols += [f"f_rest_{i}" for i in range(3 * ((degree + 1) ** 2 - 1))]
    return P.load_columns(path, cols)


def ue_metres(d, mpu, offset_m=(0, 0, 0)):
    return np.stack([d["z"], d["x"], -d["y"]], 1).astype(np.float64) * mpu + np.array(offset_m)


def common_stats(d, pos_m, mpu, ground_h, core, degree, path):
    """ground_h: height above ground per splat (m) or nan outside the ground's area; core: mask of the used area."""
    op = 1 / (1 + np.exp(-d["opacity"].astype(np.float64)))
    s = np.sort(np.exp(np.stack([d["scale_0"], d["scale_1"], d["scale_2"]], 1).astype(np.float64)) * mpu, 1)
    smax, smid, smin = s[:, 2], s[:, 1], s[:, 0]   # noqa: E501
    aniso = smax / np.maximum(smid, 1e-9)
    n = len(op)
    st = {"file": os.path.basename(path), "file_MB": os.path.getsize(path) / 1e6, "splats": int(n), "sh_degree": degree,
          "metres_per_unit": mpu,
          "opacity_pct": pct(op), "opacity_gt_0.9": float((op > 0.9).mean()), "opacity_lt_0.1": float((op < 0.1).mean()),
          "scale_max_cm_pct": pct(smax * 100), "scale_min_cm_pct": pct(smin * 100),
          "needles_max_over_mid_gt_10": float((aniso > 10).mean()),
          "needles_gt_10_and_longer_than_20cm": float(((aniso > 10) & (smax > 0.2)).mean()),
          "flat_min_over_mid_lt_0.1": float((smin / np.maximum(smid, 1e-9) < 0.1).mean()),
          "extent_1_99_m": [float(v) for v in (np.percentile(pos_m, 99, 0) - np.percentile(pos_m, 1, 0))],
          "extent_all_m": [float(v) for v in (pos_m.max(0) - pos_m.min(0))],
          "core_fraction_of_splats": float(core.mean()), "core_splats": int(core.sum())}
    # ground surface: splats within 20 cm of the ground inside the used area
    g = core & np.isfinite(ground_h)
    band = g & (np.abs(ground_h) < 0.20)
    cell = 0.25
    gx, gy = np.floor(pos_m[g, 0] / cell).astype(np.int64), np.floor(pos_m[g, 1] / cell).astype(np.int64)
    ground_cells = len(set(zip(gx.tolist(), gy.tolist())))
    bx, by = np.floor(pos_m[band, 0] / cell).astype(np.int64), np.floor(pos_m[band, 1] / cell).astype(np.int64)
    key = (bx - bx.min()) * 1000003 + (by - by.min())
    uk, inv = np.unique(key, return_inverse=True)
    opsum = np.bincount(inv, weights=op[band])
    area = ground_cells * cell * cell
    st["ground_area_m2"] = float(area)
    st["ground_splats_per_m2"] = float(band.sum() / max(area, 1e-9))
    st["ground_splat_size_cm_pct"] = pct(smax[band] * 100, (25, 50, 75))
    # holes: each ground splat (seen from above, approximated as round with sigma = sqrt(largest x middle scale))
    # deposits its integrated alpha area (opacity x 2 pi sigma^2) on a 10 cm grid, spread over 16 samples drawn
    # from its gaussian; coverage = 1 - exp(-sum). Cells of the ground area below 0.5 coverage count as thin/holes.
    res = 0.10
    rng = np.random.default_rng(1)
    sig = np.sqrt(smax[band] * smid[band])
    K = 16
    px = pos_m[band, 0][:, None] + rng.normal(size=(band.sum(), K)) * sig[:, None]
    py = pos_m[band, 1][:, None] + rng.normal(size=(band.sum(), K)) * sig[:, None]
    tau = np.repeat(op[band] * 2 * np.pi * sig ** 2 / (res * res) / K, K)
    x0, y0 = pos_m[g, 0].min(), pos_m[g, 1].min()
    W, H = int((pos_m[g, 0].max() - x0) / res) + 1, int((pos_m[g, 1].max() - y0) / res) + 1
    ix, iy = ((px.ravel() - x0) / res).astype(int), ((py.ravel() - y0) / res).astype(int)
    ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    depth = np.zeros((H, W))
    np.add.at(depth, (iy[ok], ix[ok]), tau[ok])
    area_mask = np.zeros((H, W), bool)
    area_mask[((pos_m[g, 1] - y0) / res).astype(int), ((pos_m[g, 0] - x0) / res).astype(int)] = True
    from scipy.ndimage import binary_closing, binary_erosion
    area_mask = binary_erosion(binary_closing(area_mask, iterations=5), iterations=3)
    coverage = 1 - np.exp(-depth)
    st["ground_hole_fraction_cov_lt_0.5"] = float((coverage[area_mask] < 0.5).mean())
    st["ground_coverage_median"] = float(np.median(coverage[area_mask]))
    self_name = os.path.splitext(os.path.basename(path))[0].split(" ")[0].split(".")[0]
    vis = np.where(area_mask, coverage, 0.0)
    Image.fromarray((np.flipud(vis) * 255).astype(np.uint8)).save(os.path.join(OUT, f"ground_coverage_{self_name}.png"))
    st["below_ground_0.3m_fraction_of_core"] = float((g & (ground_h < -0.3)).sum() / max(g.sum(), 1))
    st["below_ground_opacity_weight_fraction"] = float(op[g & (ground_h < -0.3)].sum() / max(op[g].sum(), 1e-9))
    # nearest neighbour spacing inside the used area (subsample)
    idx = np.flatnonzero(core)
    rng = np.random.default_rng(0)
    sub = idx[rng.choice(len(idx), min(len(idx), 400000), replace=False)]
    tree = cKDTree(pos_m[idx])
    dist, _ = tree.query(pos_m[sub], k=2)
    st["core_nn_spacing_cm_pct"] = pct(dist[:, 1] * 100, (25, 50, 75))
    # view dependence: energy of the higher SH bands relative to the base colour (core splats)
    if degree > 0:
        k = (degree + 1) ** 2 - 1
        rest = np.stack([d[f"f_rest_{i}"][core] for i in range(3 * k)], 1).astype(np.float64)
        dc = np.stack([d[f"f_dc_{i}"][core] for i in range(3)], 1).astype(np.float64)
        st["sh_rest_rms"] = float(np.sqrt((rest ** 2).mean()))
        st["sh_rest_over_dc_median"] = float(np.median(np.linalg.norm(rest, axis=1) / np.maximum(np.linalg.norm(dc, axis=1), 1e-6)))
    return st, op, smax


def parking():
    if not os.path.exists(P.RAW_PLY):
        os.makedirs(P.OUT_DIR, exist_ok=True)
        P.write_standard_ply(P.RAW_PLY, P.decompress())
    d = load(P.RAW_PLY, 3)
    x, y, z = d["x"].astype(np.float64), d["y"].astype(np.float64), d["z"].astype(np.float64)
    op = 1 / (1 + np.exp(-d["opacity"]))
    geo = {}
    # up axis: the axis with the narrowest spread of the dense part
    spread = [float(np.subtract(*np.percentile(v, [95, 5]))) for v in (x, y, z)]
    geo["spread_5_95_units_xyz"] = spread
    # floor plane: trimmed least squares on the opaque low layer of the deck
    m = (np.abs(x) < 4.5) & (np.abs(z) < 11) & (y > -0.5) & (y < 0.2) & (op > 0.3)
    A = np.stack([x[m], z[m], np.ones(m.sum())], 1)
    w = np.ones(m.sum(), bool)
    for it in range(6):
        c, *_ = np.linalg.lstsq(A[w], y[m][w], rcond=None)
        r = y[m] - A @ c
        w = np.abs(r) < (0.09 if it < 2 else 0.03)
    geo["floor_plane_y_eq_ax_bz_c"] = [float(v) for v in c]
    geo["floor_tilt_deg"] = float(np.degrees(np.arctan(np.hypot(c[0], c[1]))))
    geo["floor_residual_std_units"] = float(r[w].std())
    h = -(y - (c[0] * x + c[1] * z + c[2]))   # height above floor in units (PLY -y is up)
    # deck axis and stall line pitch (left stall row)
    fl = (np.abs(x) < 4.5) & (np.abs(z) < 11) & (np.abs(h) < 0.05) & (op > 0.3)
    p2 = np.stack([x[fl], z[fl]], 1)
    ev, evec = np.linalg.eigh(np.cov((p2 - p2.mean(0)).T))
    ang = np.arctan2(evec[0, 1], evec[1, 1])
    geo["deck_axis_angle_deg"] = float(np.degrees(ang))
    u = x * np.cos(ang) - z * np.sin(ang)
    v = x * np.sin(ang) + z * np.cos(ang)
    col = np.clip(0.5 + P.SH_C0 * np.stack([d["f_dc_0"], d["f_dc_1"], d["f_dc_2"]], 1), 0, 1)
    lines = (np.abs(h) < 0.04) & (u > -3.5) & (u < -2.7) & (col.mean(1) > 0.55) & (op > 0.2) & (np.abs(v) < 10)
    hist, e = np.histogram(v[lines], bins=2000, range=(-10, 10), weights=op[lines])
    hs = gaussian_filter1d(hist, 2)
    pk, _ = find_peaks(hs, distance=15, prominence=hs.max() * 0.15)
    diffs = np.diff(e[pk])
    pitch = float(np.median(diffs[(diffs > 0.5) & (diffs < 0.8)]))
    geo["stall_line_positions_units"] = [round(float(p), 3) for p in e[pk]]
    geo["stall_pitch_units"] = pitch
    mpu = STALL_WIDTH_M / pitch
    geo["metres_per_unit_from_2.5m_stalls"] = mpu
    geo["metres_per_unit_if_2.3m_stalls"] = 2.3 / pitch
    # ceiling layers above the floor and a parked car (white Golf in the middle block)
    ce = (np.abs(u) < 4.0) & (np.abs(v) < 10) & (h > 0.3) & (h < 1.3) & (op > 0.3)
    hh, he = np.histogram(h[ce], bins=100, range=(0.3, 1.3))
    geo["ceiling_layers_units_top3"] = [round(float(he[i]), 3) for i in np.argsort(hh)[-3:]]
    geo["slab_underside_m"] = float(np.percentile(h[ce], 90) * mpu)
    geo["ceiling_fixture_layers_m"] = [round(v * mpu, 2) for v in geo["ceiling_layers_units_top3"]]
    # body of the white Golf (VW Golf Mk7: 4.26 x 1.80 m) between 0.4 and 1.2 m, top view extent
    car = (x > -0.6) & (x < 0.7) & (z > -0.65) & (z < 0.0) & (h > 0.1) & (h < 0.3) & (op > 0.5)
    geo["car_length_m"] = float(np.subtract(*np.percentile(x[car], [99, 1])) * mpu)
    geo["car_width_m"] = float(np.subtract(*np.percentile(z[car], [99, 1])) * mpu)
    # Unreal placement: the floor at the deck centre goes to Z = 0
    geo["ue_actor_offset_z_cm"] = float(c[2] * mpu * 100)   # floor (y = c at x = z = 0) is at UE Z = -c*mpu*100
    pos_m = ue_metres(d, mpu, (0, 0, geo["ue_actor_offset_z_cm"] / 100))
    # the deck is not one plane (one end is ~0.4 m lower than the other relative to the fit), so the ground is a
    # height map: per 1 m cell, the opacity weighted mode of the heights near the plane, median filtered
    gm, ginfo = ground_map(u, v, h * mpu, op)
    geo.update(ginfo)
    ground_h = np.where((np.abs(u) < 4.0) & (v > -11) & (v < 9.2), h * mpu - gm, np.nan)
    core = (np.abs(u) < 4.3) & (v > -11.5) & (v < 9.6) & (ground_h > -2.0) & (ground_h < 4.0) | \
        ((np.abs(u) < 4.3) & (v > -11.5) & (v < 9.6) & (np.abs(h * mpu) < 3.5) & np.isnan(ground_h))
    st, opa, smax = common_stats(d, pos_m, mpu, ground_h, core, 3, P.SRC_PLY)
    st["geometry"] = geo
    st["file_MB_decompressed"] = os.path.getsize(P.RAW_PLY) / 1e6
    # far field: city lights / sky splats outside the building
    far = np.linalg.norm(np.stack([u, v], 1), axis=1) > 25
    st["far_field_fraction"] = float(far.mean())
    maps(d, u, v, h - gm / mpu, col, op, mpu)   # heights above the local ground
    return st


def ground_map(u, v, hm, op, cell_units=0.26):
    """Per splat ground height (m, relative to the floor plane) from a 1 m height map of the deck."""
    from scipy.ndimage import median_filter
    u0, v0 = -4.3, -11.5
    W, H = int(8.6 / cell_units) + 1, int(21.1 / cell_units) + 1
    iu = np.clip(((u - u0) / cell_units).astype(int), 0, W - 1)
    iv = np.clip(((v - v0) / cell_units).astype(int), 0, H - 1)
    nb, lo, hi = 48, -0.8, 0.4
    ib = ((hm - lo) / (hi - lo) * nb).astype(int)
    m = (ib >= 0) & (ib < nb) & (u > u0) & (u < -u0) & (v > v0) & (v < v0 + 21.1)
    hist = np.zeros((H, W, nb))
    np.add.at(hist, (iv[m], iu[m], ib[m]), op[m])
    g = lo + (hist.argmax(2) + 0.5) * (hi - lo) / nb
    g = np.where(hist.max(2) > 0.5, g, np.nan)
    gf = median_filter(np.nan_to_num(g, nan=np.nanmedian(g)), size=5)
    info = {"ground_map_range_m": [float(np.nanpercentile(gf, 2)), float(np.nanpercentile(gf, 98))],
            "ground_map_end_to_end_m": [float(np.nanmedian(gf[:8])), float(np.nanmedian(gf[-12:]))]}
    return gf[iv, iu], info


def maps(d, u, v, h, col, op, mpu):
    """Top-down floor colour, floor coverage (holes) and a side section, in deck axes (u across, v along)."""
    res = 0.02
    ur, vr = (-5.0, 5.0), (-12.5, 10.5)
    W, H = int((ur[1] - ur[0]) / res), int((vr[1] - vr[0]) / res)

    def acc(mask, a, b, ar, br, r):
        Wd, Hd = int((ar[1] - ar[0]) / r), int((br[1] - br[0]) / r)
        ia, ib = ((a - ar[0]) / r).astype(int), ((b - br[0]) / r).astype(int)
        mm = mask & (ia >= 0) & (ia < Wd) & (ib >= 0) & (ib < Hd)
        c = np.zeros((Hd, Wd, 3))
        wsum = np.zeros((Hd, Wd))
        np.add.at(c, (ib[mm], ia[mm]), col[mm] * op[mm, None])
        np.add.at(wsum, (ib[mm], ia[mm]), op[mm])
        return c / np.maximum(wsum, 1e-6)[..., None], wsum

    img, _ = acc(np.abs(h) < 0.03, u, v, ur, vr, res)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "parking_floor_top.png"))
    _, wsum = acc(np.abs(h) < 0.03, u, v, ur, vr, 0.1)
    cov = np.clip(wsum / 3.0, 0, 1)
    Image.fromarray((cov * 255).astype(np.uint8)).resize((cov.shape[1] * 5, cov.shape[0] * 5), Image.NEAREST).save(
        os.path.join(OUT, "parking_floor_coverage.png"))
    img, _ = acc((h > 0.3) & (h < 1.0), u, v, ur, vr, res)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "parking_ceiling_top.png"))
    img, _ = acc(np.abs(u) < 0.4, v, -h, vr, (-1.1, 0.4), 0.01)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "parking_section.png"))


def hongdae():
    deg = sh_degree(HONGDAE_PLY)
    d = load(HONGDAE_PLY, deg)
    pos_m = ue_metres(d, HONGDAE_MPU)
    g = json.load(open(HONGDAE_COLLISION))
    gv = np.array(g["ground"]["vertices"], dtype=np.float64) / 100.0
    interp = LinearNDInterpolator(gv[:, :2], gv[:, 2])
    gz = interp(pos_m[:, 0], pos_m[:, 1])
    ground_h = pos_m[:, 2] - gz
    core = np.isfinite(gz) & (ground_h > -1.0) & (ground_h < 12.0)
    st, _, _ = common_stats(d, pos_m, HONGDAE_MPU, ground_h, core, deg, HONGDAE_PLY)
    st["note"] = "ANNX export: cropped (4.94M -> 4.69M) and SH reduced 3 -> 1 by ANNX; scale x2.0 from stage_scale.json"
    return st


def main():
    os.makedirs(OUT, exist_ok=True)
    result = {"parking": parking(), "hongdae": hongdae()}
    with open(os.path.join(OUT, "stats.json"), "w") as f:
        json.dump(result, f, indent=1)
    keys = [k for k in result["parking"] if k not in ("geometry",)]
    lines = [f"{'metric':45s} {'ParkingTower':>28s} {'Hongdae':>28s}"]
    for k in keys:
        a, b = result["parking"].get(k), result["hongdae"].get(k)
        fmt = lambda v: (json.dumps({kk: round(vv, 3) for kk, vv in v.items()}) if isinstance(v, dict) else
                         (str([round(t, 1) for t in v]) if isinstance(v, list) else (f"{v:.4g}" if isinstance(v, float) else str(v))))
        lines.append(f"{k:45s} {fmt(a):>28s} {fmt(b) if b is not None else '-':>28s}")
    lines.append("")
    lines.append("Parking geometry: " + json.dumps(result["parking"]["geometry"], indent=1))
    open(os.path.join(OUT, "stats.txt"), "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
