"""
Finds the camera of a reference video frame in the scan: renders the raw PLY with the reference rasterizer and
moves the camera (Unreal x, y, z cm, yaw, pitch, horizontal FOV) until the render lines up with the frame.
The video's AR overlays (green stall boxes, cyan path, label boxes) are masked out.

  python fit_pose.py <video> <seconds> <x> <y> <z> <yaw> <pitch> <hfov> [name]
  python fit_pose.py --jobs poses_init.json        (all keyframes; writes video_poses.json + overlays)

Loss: 1 - normalised cross correlation of gradient magnitude + 0.5 x (1 - NCC of the grey image), at 160x90
then 320x180 (Nelder-Mead). A good fit has NCC of gradients around 0.5+; the side by side image is the real check.
"""

import json
import os
import subprocess
import sys

import numpy as np
import torch
from PIL import Image
from scipy.ndimage import binary_dilation, gaussian_filter, sobel
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptcommon as P  # noqa: E402
import ref_render as R  # noqa: E402

OUT = os.path.join(P.SHOTS_DIR, "pose_fit")


def video_frame(video, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (1920, 1080), raw)


def overlay_mask(rgb):
    """True where the frame is the scan (not the AR overlay)."""
    a = rgb.astype(np.float32) / 255
    mx, mn = a.max(2), a.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    g, b, r = a[..., 1], a[..., 2], a[..., 0]
    cyan_green = (sat > 0.35) & (g > r + 0.1) & (mx > 0.35)
    return ~binary_dilation(cyan_green, iterations=3)


def features(img, mask, blur):
    grey = gaussian_filter(img.mean(2), blur)
    grad = np.hypot(sobel(grey, 0), sobel(grey, 1))
    return grey[mask], grad[mask]


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-12))


class Fitter:
    def __init__(self, renderer):
        self.r = renderer

    def render(self, p, w, h):
        img, alpha = self.r.render_ue(p[0], p[1], p[2], p[3], p[4], w, h, p[5])
        return np.clip(img, 0, 1)

    def coarse(self, frame, p0, grid):
        """Grid search at 80x45 over the offsets in grid: {dim index: [offsets]} (other dims fixed)."""
        w, h, blur = 80, 45, 2.0
        tgt = np.asarray(frame.resize((w, h), Image.BILINEAR), dtype=np.float32) / 255
        mask = overlay_mask(np.asarray(frame.resize((w, h), Image.NEAREST)))
        tg, tgr = features(tgt, mask, blur)
        dims = sorted(grid)
        best = (9.0, np.array(p0, dtype=np.float64))
        for combo in np.array(np.meshgrid(*[grid[d] for d in dims], indexing="ij")).reshape(len(dims), -1).T:
            q = np.array(p0, dtype=np.float64)
            for d, o in zip(dims, combo):
                q[d] += o
            g, gr = features(self.render(q, w, h), mask, blur)
            l = (1 - ncc(gr, tgr)) + 0.5 * (1 - ncc(g, tg))
            if l < best[0]:
                best = (l, q)
        return best[1]

    def fit(self, frame, p0, steps=(20.0, 20.0, 8.0, 2.0, 1.5, 4.0), grid=None, grid2=None):
        p = np.array(p0, dtype=np.float64)
        for g in (grid, grid2):
            if g:
                p = self.coarse(frame, p, {int(k): v for k, v in g.items()})
        for (w, h, blur, iters, scale) in ((160, 90, 1.5, 160, 1.0), (320, 180, 1.0, 140, 0.4)):
            tgt = np.asarray(frame.resize((w, h), Image.BILINEAR), dtype=np.float32) / 255
            mask = overlay_mask(np.asarray(frame.resize((w, h), Image.NEAREST)))
            tg, tgr = features(tgt, mask, blur)

            def loss(q):
                if not (40 < q[5] < 130):
                    return 3.0
                img = self.render(q, w, h)
                g, gr = features(img, mask, blur)
                return (1 - ncc(gr, tgr)) + 0.5 * (1 - ncc(g, tg))

            simplex = [p] + [p + np.eye(6)[i] * steps[i] * scale for i in range(6)]
            res = minimize(loss, p, method="Nelder-Mead",
                           options={"initial_simplex": simplex, "maxiter": iters, "xatol": 0.5, "fatol": 1e-4})
            p = res.x
        img = self.render(p, 320, 180)
        tgt = np.asarray(frame.resize((320, 180), Image.BILINEAR), dtype=np.float32) / 255
        mask = overlay_mask(np.asarray(frame.resize((320, 180), Image.NEAREST)))
        g, gr = features(img, mask, 1.0)
        tg, tgr = features(tgt, mask, 1.0)
        return p, {"ncc_grad": ncc(gr, tgr), "ncc_grey": ncc(g, tg), "loss": float(res.fun)}

    def side_by_side(self, frame, p, path):
        img = self.render(p, 640, 360)
        a = Image.fromarray((img * 255).astype(np.uint8))
        b = frame.resize((640, 360), Image.BILINEAR)
        out = Image.new("RGB", (1280, 360))
        out.paste(b, (0, 0))
        out.paste(a, (640, 0))
        out.save(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    video = os.path.join(P.REPO, "parking-tower", "video.mp4")
    r = R.Renderer(R.ptcommon.RAW_PLY)
    fitter = Fitter(r)
    if sys.argv[1] == "--jobs":
        jobs = json.load(open(sys.argv[2]))
    else:
        jobs = [{"name": sys.argv[9] if len(sys.argv) > 9 else "frame", "t": float(sys.argv[2]),
                 "init": list(map(float, sys.argv[3:9]))}]
    result_path = os.path.join(OUT, os.environ.get("POSES_FILE", "video_poses.json"))
    results = json.load(open(result_path)) if os.path.exists(result_path) else {}
    for job in jobs:
        frame = video_frame(video, job["t"])
        # "init_from": start from an earlier keyframe's fitted pose (tracking along a shot), plus optional "delta"
        init = list(results[job["init_from"]]["pose"]) if "init_from" in job else job["init"]
        init = [a + b for a, b in zip(init, job.get("delta", [0] * 6))]
        p, q = fitter.fit(frame, init, grid=job.get("grid"), grid2=job.get("grid2"))
        results[job["name"]] = {"t": job["t"], "pose": [round(float(v), 2) for v in p], **q}
        fitter.side_by_side(frame, p, os.path.join(OUT, f"{job['name']}.jpg"))
        print(job["name"], results[job["name"]], flush=True)
        json.dump(results, open(result_path, "w"), indent=1)


if __name__ == "__main__":
    main()
