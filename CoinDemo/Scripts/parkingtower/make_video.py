"""
Step 7: comparison video on one camera path (a straight line, like the reference video's first shot).

  ~/.venvs/gs/bin/python -I make_video.py ref   <x0 y0 z0 yaw0 pitch0> <x1 y1 z1 yaw1 pitch1> <seconds> <hfov>
        renders the reference rasterizer (standard 3DGS = what the reference video was rendered with) along the
        path, 30 fps, 960x540, into Saved/.../video/ref/
  python make_video.py grid <seconds> <hfov> <label=screenshot_prefix> x3   [director_video_seconds]
        2x2 grid: reference rasterizer + three Unreal runs (DevCapture -Fly screenshots <prefix>_fNNN.png,
        1600x900 at 90 degrees, cropped to <hfov> so the framing matches) -> video/comparison.mp4
        Unreal fly frames are spaced by real time, so each run is resampled to 30 fps by its frame count.

Unreal's -Fly interpolates location and rotation linearly from the moment FlyStart is reached; so does this.
"""

import glob
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptcommon as P  # noqa: E402

OUT = os.path.join(P.SHOTS_DIR, "video")
SHOTS = os.path.normpath(os.path.join(HERE, "..", "..", "Saved", "Screenshots"))
W, H = 960, 540
FPS = 30


def font(size):
    for f in ("/mnt/c/Windows/Fonts/malgun.ttf", "/mnt/c/Windows/Fonts/arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def ref(a, b, seconds, hfov):
    import ref_render as R
    os.makedirs(os.path.join(OUT, "ref"), exist_ok=True)
    r = R.Renderer(P.RAW_PLY)
    n = int(round(seconds * FPS))
    for i in range(n):
        t = i / (n - 1)
        p = [a[k] + (b[k] - a[k]) * t for k in range(5)]
        img, alpha = r.render_ue(*p, W, H, hfov)
        R.to_image(img, alpha, 0.0).save(os.path.join(OUT, "ref", f"f{i:03d}.png"))
        print(i, flush=True)


def crop_to_fov(im, hfov):
    w = im.width * math.tan(math.radians(hfov) / 2) / math.tan(math.radians(45))
    h = w * 9 / 16
    box = ((im.width - w) / 2, (im.height - h) / 2, (im.width + w) / 2, (im.height + h) / 2)
    return im.crop(tuple(int(round(v)) for v in box)).resize((W, H), Image.LANCZOS)


def label(im, text):
    d = ImageDraw.Draw(im)
    f = font(22)
    d.rectangle((0, 0, W, 34), fill=(0, 0, 0))
    d.text((10, 5), text, font=f, fill=(255, 230, 80))
    return im


def grid(seconds, hfov, runs, director_seconds=None):
    n = int(round(seconds * FPS))
    ref_frames = sorted(glob.glob(os.path.join(OUT, "ref", "f*.png")))
    sources = [("C 표준 3DGS 래스터라이저 (감독 영상과 같은 방식)", [ref_frames[min(len(ref_frames) - 1, round(i * (len(ref_frames) - 1) / (n - 1)))] for i in range(n)], False)]
    for lab, prefix in runs:
        files = sorted(glob.glob(os.path.join(SHOTS, f"{prefix}_f*.png")))
        print(lab, len(files), "frames")
        sources.append((lab, [files[min(len(files) - 1, round(i * (len(files) - 1) / (n - 1)))] for i in range(n)], True))
    tmp = os.path.join(OUT, "grid")
    os.makedirs(tmp, exist_ok=True)
    for f in glob.glob(os.path.join(tmp, "*.png")):
        os.remove(f)
    for i in range(n):
        canvas = Image.new("RGB", (2 * W, 2 * H))
        for k, (lab, files, crop) in enumerate(sources):
            im = Image.open(files[i]).convert("RGB")
            im = crop_to_fov(im, hfov) if crop else im.resize((W, H))
            canvas.paste(label(im, lab), ((k % 2) * W, (k // 2) * H))
        canvas.save(os.path.join(tmp, f"g{i:03d}.png"))
    out = os.path.join(OUT, "comparison_raw_improved_hybrid.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "g%03d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out], check=True)
    print(out)
    if director_seconds:
        # the director's video next to the reference rasterizer and the improved Unreal run, for its first shot
        m = int(round(director_seconds * FPS))
        video = os.path.join(P.REPO, "parking-tower", "video.mp4")
        dtmp = os.path.join(OUT, "director")
        os.makedirs(dtmp, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.1", "-t", f"{director_seconds}", "-i", video, "-vf", f"fps={FPS},scale={W}:{H}",
                        os.path.join(dtmp, "d%03d.png")], check=True)
        dframes = sorted(glob.glob(os.path.join(dtmp, "d*.png")))
        trio = os.path.join(OUT, "trio")
        os.makedirs(trio, exist_ok=True)
        improved = sources[2]
        for i in range(min(m, len(dframes))):
            canvas = Image.new("RGB", (3 * W, H))
            canvas.paste(label(Image.open(dframes[i]).convert("RGB"), "감독 영상 (video.mp4)"), (0, 0))
            canvas.paste(label(Image.open(sources[0][1][i]).convert("RGB").resize((W, H)), "C 원본 PLY, 표준 3DGS"), (W, 0))
            canvas.paste(label(crop_to_fov(Image.open(improved[1][i]).convert("RGB"), hfov), improved[0]), (2 * W, 0))
            canvas.save(os.path.join(trio, f"t{i:03d}.png"))
        out2 = os.path.join(OUT, "director_vs_rawPLY_vs_unreal.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(trio, "t%03d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out2], check=True)
        print(out2)


if __name__ == "__main__":
    if sys.argv[1] == "ref":
        a = list(map(float, sys.argv[2:7]))
        b = list(map(float, sys.argv[7:12]))
        ref(a, b, float(sys.argv[12]), float(sys.argv[13]))
    else:
        seconds, hfov = float(sys.argv[2]), float(sys.argv[3])
        runs = [a.split("=", 1) for a in sys.argv[4:7]]
        grid(seconds, hfov, runs, float(sys.argv[7]) if len(sys.argv) > 7 else None)
