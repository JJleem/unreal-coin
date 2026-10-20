"""
Step 4 stills: for every fitted keyframe of the reference video, the video frame next to the raw PLY drawn by the
reference rasterizer (C) and by Unreal with the CoinDemo settings (B), from the fitted camera.

  ~/.venvs/gs/bin/python -I keyframes.py render         C renders (960x540, fitted FOV) + views.txt for Unreal
  (run Unreal:  -Views=<views.txt> ShotName pt_kf, TSR + gs.ToneCorrection 1)
  python keyframes.py sheet                             trios + metrics against the video frame -> video_match/

Poses: merged from pose_fit/video_poses*.json, keeping per keyframe the fit with the highest gradient NCC.
"""

import glob
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptcommon as P  # noqa: E402

FIT = os.path.join(P.SHOTS_DIR, "pose_fit")
OUT = os.path.join(P.SHOTS_DIR, "video_match")
SHOTS = os.path.normpath(os.path.join(HERE, "..", "..", "Saved", "Screenshots"))
W, H = 960, 540
REJECTED = {"s1_mid"}


def poses():
    best = {}
    for f in glob.glob(os.path.join(FIT, "video_poses*.json")):
        for k, v in json.load(open(f)).items():
            # s1_mid: an early fit that locked onto the wrong pillar bay (checked by eye); NCC < 0.45: not a match
            if k in REJECTED or v["ncc_grad"] < 0.45:
                continue
            if k not in best or v["ncc_grad"] > best[k]["ncc_grad"]:
                best[k] = v
    return dict(sorted(best.items(), key=lambda kv: kv[1]["t"]))


def video_frame(t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", os.path.join(P.REPO, "parking-tower", "video.mp4"), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (1920, 1080), raw).resize((W, H), Image.LANCZOS)


def crop_to_fov(im, hfov):
    w = im.width * math.tan(math.radians(hfov) / 2) / math.tan(math.radians(45))
    h = w * 9 / 16
    box = ((im.width - w) / 2, (im.height - h) / 2, (im.width + w) / 2, (im.height + h) / 2)
    return im.crop(tuple(int(round(v)) for v in box)).resize((W, H), Image.LANCZOS)


def render():
    import ref_render as R
    os.makedirs(OUT, exist_ok=True)
    r = R.Renderer(P.RAW_PLY)
    ps = poses()
    views = []
    for k, v in ps.items():
        p = v["pose"]
        img, alpha = r.render_ue(p[0], p[1], p[2], p[3], p[4], W, H, p[5])
        R.to_image(img, alpha, 0.0).save(os.path.join(OUT, f"kf_{k}_C.png"))
        video_frame(v["t"]).save(os.path.join(OUT, f"kf_{k}_video.png"))
        views.append(f"{p[0]:.0f},{p[1]:.0f},{p[2]:.0f},{p[3]:.2f},{p[4]:.2f},cam")
    open(os.path.join(OUT, "views.txt"), "w").write(";".join(views))
    json.dump(ps, open(os.path.join(OUT, "keyframe_poses.json"), "w"), indent=1)
    print(";".join(views))


def sheet():
    sys.path.insert(0, HERE)
    import compare
    ps = json.load(open(os.path.join(OUT, "keyframe_poses.json")))
    rows = []
    for i, (k, v) in enumerate(ps.items(), start=1):
        ue = os.path.join(SHOTS, f"pt_kf_{i:02d}.png")
        b = crop_to_fov(Image.open(ue).convert("RGB"), v["pose"][5])
        b.save(os.path.join(OUT, f"kf_{k}_B.png"))
        vid = compare.load(os.path.join(OUT, f"kf_{k}_video.png"))
        mc = compare.metrics(compare.load(os.path.join(OUT, f"kf_{k}_C.png")), vid)
        mb = compare.metrics(compare.load(os.path.join(OUT, f"kf_{k}_B.png")), vid)
        rows.append((k, v, mc, mb))
        trio = Image.new("RGB", (3 * W, H))
        for j, suffix in enumerate(("video", "C", "B")):
            trio.paste(Image.open(os.path.join(OUT, f"kf_{k}_{suffix}.png")).convert("RGB"), (j * W, 0))
        trio.save(os.path.join(OUT, f"trio_{k}.jpg"), quality=90)
    with open(os.path.join(OUT, "keyframes.txt"), "w") as f:
        f.write("keyframe t pose(x y z yaw pitch hfov) fitNCC | video vs C: err ssim mid | video vs B: err ssim mid\n")
        for k, v, mc, mb in rows:
            line = (f"{k:10s} {v['t']:5.1f} {v['pose']} ncc {v['ncc_grad']:.2f}/{v['ncc_grey']:.2f} | "
                    f"C {mc['colour_error']:.3f} {mc['ssim']:.2f} x{mc['mid_tone_ratio']:.2f} | B {mb['colour_error']:.3f} {mb['ssim']:.2f} x{mb['mid_tone_ratio']:.2f}")
            f.write(line + "\n")
            print(line)


if __name__ == "__main__":
    {"render": render, "sheet": sheet}[sys.argv[1]]()
