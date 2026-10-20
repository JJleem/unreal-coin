"""
Removes splats that render as streaks, haze or floating specks, writing cleaned copies of the scans.

Rules (all measured in Unreal metres, after the stage scale correction, so one threshold fits every scan):

  v1 (every stage)
    * degenerate needles: longest axis > DEGENERATE x the middle one, whatever their opacity
    * faint needles: > NEEDLE_V1 x and opacity < NEEDLE_V1_MAX_OPACITY
    * haze: longest axis > BIG x the scan's median and opacity < BIG_MAX_OPACITY
  v2 (stages listed in V2_STAGES; adds to v1, checked on Hongdae with before/after screenshots, see HANDOFF.md)
    * needles: longest axis > NEEDLE x the middle one and opacity < NEEDLE_MAX_OPACITY. Seen from a game camera these
      are the dark scratches on the road and the torn edges of awnings. Fairly opaque needles are kept: wires,
      poles and railings tend to be.
    * isolated specks: the 8th nearest neighbour farther than ISOLATED metres and than ISOLATED_SIZE x the splat's
      own length. These are the white wisps floating in the sky above rooftops. (Without the size condition the
      rule also took big splats, whose neighbour centres are far by nature, and dark stains appeared on the road.)
    * sky wisps: isolated splats of any size above the top of their column of splats (where SKY_MASS of the
      opacity in a SKY_CELL wide column ends); only sky is behind them, so nothing dark is uncovered. (A plain
      height limit took the upper walls of buildings too and made them see-through.)
  Not removed, on purpose (tried and made things worse):
    * splats below the walkable ground: the road is many faint layers deep, removing them punches black holes
    * large splats in general: road and wall surfaces are made of them
    * more aggressive needle rules (lower ratio, or size based): they erase manholes, cracks and markings

Input:  ../../Scans/<NN>_<Name>/<Name>.ply   (left untouched)
Output: ../SourceAssets/CleanScans/<Name>.ply (same layout; build_scan_stages.py imports these when present)
        generated/<Name>_clean.json           counts per rule

Needs numpy and scipy, so it runs outside Unreal:
  python clean_scans.py [Name ...]     (no names: every scan)
"""

import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Scans"))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "CleanScans"))
GENERATED_DIR = os.path.join(HERE, "generated")
SCALES = {k: v for k, v in json.load(open(os.path.join(HERE, "stage_scale.json"), encoding="utf-8")).items() if not k.startswith("_")}

DEGENERATE = 100.0
NEEDLE_V1 = 20.0
NEEDLE_V1_MAX_OPACITY = 0.15
BIG = 20.0
BIG_MAX_OPACITY = 0.3

V2_STAGES = {"Hongdae"}
NEEDLE = 15.0
NEEDLE_MAX_OPACITY = 0.4
ISOLATED = 0.3          # metres to the 8th nearest neighbour...
ISOLATED_SIZE = 3.0     # ...and at least this many times the splat's own longest axis,
SKY_CELL = 1.0          # ...or any size above the top of the column of splats they stand in: column width,
SKY_MASS = 0.95         # share of the column's opacity below its top,
SKY_MARGIN = 0.5        # and metres above that top


def read_ply(path):
    with open(path, "rb") as f:
        header = b""
        while not header.endswith(b"end_header\n"):
            header += f.readline()
        lines = header.splitlines()
        names = [l.split()[-1].decode() for l in lines if l.startswith(b"property")]
        count = int(next(l for l in lines if l.startswith(b"element vertex")).split()[-1])
        dtype = np.dtype([(n, "<f4") for n in names])
        # read in one go: np.fromfile has returned short reads on the WSL Windows mount
        buffer = f.read(count * dtype.itemsize)
        if len(buffer) != count * dtype.itemsize:
            raise IOError(f"{path}: short read")
        return header, np.frombuffer(buffer, dtype=dtype).copy()


def write_ply(path, header, data):
    old = next(l for l in header.splitlines() if l.startswith(b"element vertex"))
    with open(path, "wb") as f:
        f.write(header.replace(old, b"element vertex %d" % len(data)))
        f.write(data.tobytes())


def clean(folder):
    name = folder.split("_", 1)[1]
    stage = json.load(open(os.path.join(SCANS_DIR, folder, "stage.json"), encoding="utf-8"))
    mpu = stage["metresPerUnit"] * SCALES.get(name, 1.0)
    header, data = read_ply(os.path.join(SCANS_DIR, folder, f"{name}.ply"))

    scales = np.sort(np.exp(np.stack([data["scale_0"], data["scale_1"], data["scale_2"]], axis=1).astype(np.float64)), axis=1)
    opacity = 1.0 / (1.0 + np.exp(-data["opacity"].astype(np.float64)))
    needle = scales[:, 2] / np.maximum(scales[:, 1], 1e-12)
    size = scales[:, 2] / np.median(scales[:, 2])

    rules = {
        "degenerate": needle > DEGENERATE,
        "faint needle": (needle > NEEDLE_V1) & (opacity < NEEDLE_V1_MAX_OPACITY),
        "haze": (size > BIG) & (opacity < BIG_MAX_OPACITY),
    }
    if name in V2_STAGES:
        position = np.stack([data["x"], data["y"], data["z"]], axis=1).astype(np.float64) * mpu
        neighbour, _ = cKDTree(position).query(position, k=9, workers=-1)
        rules["needle"] = (needle > NEEDLE) & (opacity < NEEDLE_MAX_OPACITY)
        # only splats small next to the gap around them: big splats have far away neighbour centres by nature, and
        # removing them uncovers dark layers underneath
        rules["isolated"] = (neighbour[:, 8] > ISOLATED) & (scales[:, 2] * mpu * ISOLATED_SIZE < neighbour[:, 8])
        # above the top of whatever stands at a spot only sky is behind, so isolated splats of any size can go
        # there (the wisps over rooftops). The top is where most of the opacity in a SKY_CELL column ends; walls
        # below it are left alone, their big sparse splats look isolated too
        unreal = np.stack([position[:, 2], position[:, 0], -position[:, 1]], axis=1)
        column = np.floor(unreal[:, :2] / SKY_CELL).astype(np.int64)
        key = (column[:, 0] - column[:, 0].min()) * (column[:, 1].max() - column[:, 1].min() + 1) + (column[:, 1] - column[:, 1].min())
        order = np.lexsort((unreal[:, 2], key))
        sorted_key = key[order]
        mass = np.cumsum(opacity[order])
        starts = np.flatnonzero(np.r_[True, sorted_key[1:] != sorted_key[:-1]])
        ends = np.r_[starts[1:], len(order)]
        base = np.r_[0.0, mass[ends[:-1] - 1]]
        total = mass[ends - 1] - base
        top = np.empty(len(starts))
        for c, (start, end) in enumerate(zip(starts, ends)):
            top[c] = unreal[order[start + np.searchsorted(mass[start:end] - base[c], SKY_MASS * total[c])], 2] if end > start else 0.0
        column_top = np.empty(len(data))
        column_top[order] = np.repeat(top, ends - starts)
        rules["sky wisp"] = (neighbour[:, 8] > ISOLATED) & (unreal[:, 2] > column_top + SKY_MARGIN)

    drop = np.zeros(len(data), bool)
    for mask in rules.values():
        drop |= mask

    os.makedirs(OUT_DIR, exist_ok=True)
    write_ply(os.path.join(OUT_DIR, f"{name}.ply"), header, data[~drop])
    report = {"stage": name, "rules": "v2" if name in V2_STAGES else "v1", "splats": int(len(data)),
              "kept": int((~drop).sum()), "removedPercent": round(float(drop.mean() * 100), 2),
              "perRule": {rule: int(mask.sum()) for rule, mask in rules.items()}}
    os.makedirs(GENERATED_DIR, exist_ok=True)
    with open(os.path.join(GENERATED_DIR, f"{name}_clean.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(f"{name:13s} {report['rules']}  kept {report['kept']:>9,} of {len(data):>9,}  removed {report['removedPercent']:5.2f}%  "
          + ", ".join(f"{rule} {count:,}" for rule, count in report["perRule"].items()))


def main():
    folders = sorted(d for d in os.listdir(SCANS_DIR) if d[:2].isdigit())
    names = sys.argv[1:]
    for folder in folders:
        if not names or folder.split("_", 1)[1] in names:
            clean(folder)


main()
