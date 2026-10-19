"""
Removes splats that render as streaks or haze, writing cleaned copies of the scans.

Some scans carry many needle-shaped splats (one axis far longer than the other two). Seen from a game camera
they show up as dark scratches on the road and torn edges on buildings; Gwanghwamun has about 15% of them, some
with a zero-width axis. Real thin objects (wires, railings) are needles too, so faint ones are the target:

  * degenerate needles (longest axis > DEGENERATE x the middle one), whatever their opacity
  * needles (> NEEDLE x) that are faint (opacity < NEEDLE_MAX_OPACITY)
  * oversized splats (> BIG x the median size) that are faint (opacity < BIG_MAX_OPACITY): floating haze

Input:  ../../Scans/<NN>_<Name>/<Name>.ply   (left untouched)
Output: ../SourceAssets/CleanScans/<Name>.ply (same layout; build_scan_stages.py imports these when present)

Needs numpy, so it runs outside Unreal:
  python clean_scans.py
"""

import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Scans"))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "CleanScans"))

DEGENERATE = 100.0
NEEDLE = 20.0
NEEDLE_MAX_OPACITY = 0.15
BIG = 20.0
BIG_MAX_OPACITY = 0.3


def read_ply(path):
    with open(path, "rb") as f:
        header = b""
        while not header.endswith(b"end_header\n"):
            header += f.readline()
        lines = header.splitlines()
        names = [l.split()[-1].decode() for l in lines if l.startswith(b"property")]
        count = int(next(l for l in lines if l.startswith(b"element vertex")).split()[-1])
        data = np.fromfile(f, dtype=np.dtype([(n, "<f4") for n in names]), count=count)
    return header, data


def write_ply(path, header, data):
    old = next(l for l in header.splitlines() if l.startswith(b"element vertex"))
    header = header.replace(old, b"element vertex %d" % len(data))
    with open(path, "wb") as f:
        f.write(header)
        data.tofile(f)


def clean(folder):
    name = folder.split("_", 1)[1]
    header, data = read_ply(os.path.join(SCANS_DIR, folder, f"{name}.ply"))

    scales = np.sort(np.exp(np.stack([data["scale_0"], data["scale_1"], data["scale_2"]], axis=1).astype(np.float64)), axis=1)
    opacity = 1.0 / (1.0 + np.exp(-data["opacity"].astype(np.float64)))
    needle = scales[:, 2] / np.maximum(scales[:, 1], 1e-12)
    size = scales[:, 2] / np.median(scales[:, 2])

    degenerate = needle > DEGENERATE
    faint_needle = (needle > NEEDLE) & (opacity < NEEDLE_MAX_OPACITY)
    haze = (size > BIG) & (opacity < BIG_MAX_OPACITY)
    drop = degenerate | faint_needle | haze

    os.makedirs(OUT_DIR, exist_ok=True)
    write_ply(os.path.join(OUT_DIR, f"{name}.ply"), header, data[~drop])
    print(f"{name:13s} kept {(~drop).sum():>9,} of {len(data):>9,}  removed {drop.mean() * 100:5.2f}%  "
          f"(degenerate {degenerate.sum():,}, faint needles {faint_needle.sum():,}, haze {haze.sum():,})")


def main():
    for folder in sorted(d for d in os.listdir(SCANS_DIR) if d[:2].isdigit()):
        clean(folder)


main()
