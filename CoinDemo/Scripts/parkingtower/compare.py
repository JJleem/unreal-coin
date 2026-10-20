"""
Measures images of the same camera against a reference image and lays them side by side.

  python compare.py <out_prefix> <reference.png> <label=img.png> [label=img.png ...]

Per image: sharpness (variance of the Laplacian of the grey image, central 80 %), mean absolute colour error and
SSIM against the reference, mid-tone ratio (mean grey of the image / reference over pixels whose reference grey is
0.25-0.75; < 1 = darker mid tones). Writes <out_prefix>.json and <out_prefix>.jpg (reference first).
"""

import json
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.metrics import structural_similarity


def load(path, size=None):
    im = Image.open(path).convert("RGB")
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return np.asarray(im, dtype=np.float64) / 255


def central(a):
    h, w = a.shape[:2]
    return a[int(h * 0.1):int(h * 0.9), int(w * 0.1):int(w * 0.9)]


def metrics(img, ref):
    g, gr = img.mean(2), ref.mean(2)
    mid = (gr > 0.25) & (gr < 0.75)
    return {"sharpness": float(ndimage.laplace(central(g) * 255).var()),
            "colour_error": float(np.abs(img - ref).mean()),
            "ssim": float(structural_similarity(g, gr, data_range=1.0)),
            "mid_tone_ratio": float(g[mid].mean() / max(gr[mid].mean(), 1e-6)),
            "mean_rgb": [round(float(v), 3) for v in img.reshape(-1, 3).mean(0)]}


def main():
    out, ref_path, items = sys.argv[1], sys.argv[2], [a.split("=", 1) for a in sys.argv[3:]]
    ref = load(ref_path)
    size = (ref.shape[1], ref.shape[0])
    result = {"reference": {"file": ref_path, **metrics(ref, ref)}}
    tiles = [("reference", ref)]
    for label, path in items:
        img = load(path, size)
        result[label] = {"file": path, **metrics(img, ref)}
        tiles.append((label, img))
    json.dump(result, open(out + ".json", "w"), indent=1)
    w = 800
    h = int(size[1] * w / size[0])
    sheet = Image.new("RGB", (w * len(tiles), h))
    for i, (label, a) in enumerate(tiles):
        im = Image.fromarray((a * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        m = result[label]
        d.rectangle((0, 0, w, 20), fill=(0, 0, 0))
        d.text((5, 4), f"{label}  sharp {m['sharpness']:.0f}  err {m['colour_error']:.3f}  ssim {m['ssim']:.2f}  mid x{m['mid_tone_ratio']:.2f}",
               fill=(255, 255, 0))
        sheet.paste(im, (i * w, 0))
    sheet.save(out + ".jpg", quality=92)
    for label, m in result.items():
        print(f"{label:22s} sharp {m['sharpness']:7.1f}  err {m['colour_error']:.3f}  ssim {m['ssim']:.3f}  mid x{m['mid_tone_ratio']:.3f}")


if __name__ == "__main__":
    main()
