"""
Phases 2-4 of the stage rebuild, outside Unreal: building geometry, face photos and the trimmed scan.

From generated/<Name>_layout.json (analyze_layout.py):
  * buildings: one box per roof step of every facade run: the front at the measured facade line, as high as its
    photo shows solid wall, an estimated depth behind it, a flat roof (the scan doesn't see roofs or backs).
    Runs whose front shows too little wall, or mostly leaves rather than wall, are not built (the scan stays).
  * face photos: for the front of every run and both ends of every box, the splats in a thin slab around the
    face, composited front to back as seen from outside, onto the face -> one texture per face. Ends matter at
    street corners, where a building's shop front faces the cross street. These are the scan's own colours: its
    detail and its blur, nothing added. Faces the scan barely saw stay plain.
  * the trimmed scan for the hybrid: splats inside the boxes and just in front of their fronts are removed;
    everything standing in the street (cars, people, trees, signs that stick out), the openings and the
    background stay splats

Output in ../../SourceAssets/Rebuilt/<Name>/:
  face_NNN.png          face photo, v down from the top, sRGB, resized to power of two sides
  rebuilt.json          boxes, faces (photo placement: origin, u axis, size), splat counts (Unreal cm)
  <Name>_rebuilt.ply    the trimmed scan

  python build_geometry.py Hongdae
"""

import json
import os
import sys
import time

import numpy as np
from numba import njit
from PIL import Image
from scipy import ndimage

from common import GENERATED_DIR, OUT_DIR, Scan, write_ply

RESOLUTION = 0.0125     # photo metres per pixel (finer than a screen pixel at a few metres)
SLAB_FRONT = 0.4        # splats this far outside a face (towards the viewer) are baked into its photo
SLAB_BACK = 8.0         # ...and this far inside it: shop fronts are glass, what is behind them shows
ABOVE_ROOF = 1.0        # a front photo reaches this far above the highest roof
MIN_COVER = 0.25        # photo pixels less covered than this are filled from around them
FULL_COVER = 0.8
WALL_COVER = 0.4        # a photo row at least this covered (in a 1 m column) is wall
SOLID_BELOW = 2.0       # the roof is the highest wall row with this many metres of mostly wall below it,
SOLID_SHARE = 0.6       # ...this share of rows covered
MIN_HEIGHT = 3.0        # lowest building, metres
HEIGHT_TOLERANCE = 1.5  # metres the roof line may wander within one step
MIN_WALL_COVER = 0.35   # fronts showing less wall than this below the roof line are not built; ends less covered stay plain
MIN_WALL_LIKE = 0.3     # share of the front's opacity from flat, upright splats; leaves are neither
ROOF_MARGIN = 0.3       # splats this far above a roof are still replaced


@njit(cache=True)
def composite(pu, pv, inv, radius, opacity, colour, res, width, height, acc, transmittance):
    """Front to back compositing of 2D Gaussians (callers sort them, nearest to the viewer first)."""
    for i in range(pu.shape[0]):
        r = radius[i] / res
        cu = pu[i] / res
        cv = pv[i] / res
        u0 = max(int(cu - r), 0)
        u1 = min(int(cu + r) + 1, width)
        v0 = max(int(cv - r), 0)
        v1 = min(int(cv + r) + 1, height)
        a00 = inv[i, 0]
        a01 = inv[i, 1]
        a11 = inv[i, 2]
        for vv in range(v0, v1):
            dv = (vv + 0.5) * res - pv[i]
            for uu in range(u0, u1):
                t = transmittance[vv, uu]
                if t < 0.003:
                    continue
                du = (uu + 0.5) * res - pu[i]
                e = 0.5 * (a00 * du * du + 2.0 * a01 * du * dv + a11 * dv * dv)
                if e > 4.5:
                    continue
                a = min(opacity[i] * np.exp(-e), 0.99)
                if a < 0.004:
                    continue
                acc[vv, uu, 0] += t * a * colour[i, 0]
                acc[vv, uu, 1] += t * a * colour[i, 1]
                acc[vv, uu, 2] += t * a * colour[i, 2]
                transmittance[vv, uu] = t * (1.0 - a)


def fill(colour, confidence):
    """Push-pull: blends every pixel with a pyramid average of its confident neighbours by its own confidence."""
    levels = [(colour * confidence[..., None], confidence.astype(np.float64))]
    while min(levels[-1][1].shape) > 2:
        c, w = levels[-1]
        h, wd = (c.shape[0] // 2) * 2, (c.shape[1] // 2) * 2
        c, w = c[:h, :wd], w[:h, :wd]
        levels.append((c[0::2, 0::2] + c[1::2, 0::2] + c[0::2, 1::2] + c[1::2, 1::2],
                       w[0::2, 0::2] + w[1::2, 0::2] + w[0::2, 1::2] + w[1::2, 1::2]))
    filled = levels[-1][0] / np.maximum(levels[-1][1], 1e-9)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)
        up = np.pad(up, ((0, c.shape[0] - up.shape[0]), (0, c.shape[1] - up.shape[1]), (0, 0)), mode="edge")
        up = ndimage.uniform_filter(up, size=(3, 3, 1))
        blend = np.clip(w, 0.0, 1.0)[..., None]
        filled = c / np.maximum(w, 1e-9)[..., None] * blend + up * (1.0 - blend)
    return colour * confidence[..., None] + filled * (1.0 - confidence[..., None])


class Baker:
    """Bakes the scan onto vertical rectangles: origin = top left corner, u axis along the face, outward normal."""

    def __init__(self, scan):
        self.scan = scan
        self.normal, self.flatness = scan.normals()
        self.cov = scan.covariance()

    def bake(self, origin, u_axis, outward, width_m, height_m):
        pos = self.scan.pos
        rel = pos - origin
        u = rel[:, :2] @ u_axis
        v = -rel[:, 2]
        s = rel[:, :2] @ outward   # positive outside the face
        pick = np.flatnonzero((u > -0.5) & (u < width_m + 0.5) & (v > -0.5) & (v < height_m + 0.5) & (s > -SLAB_BACK) & (s < SLAB_FRONT))
        width, height = max(1, int(np.ceil(width_m / RESOLUTION))), max(1, int(np.ceil(height_m / RESOLUTION)))
        axes = np.array([[u_axis[0], u_axis[1], 0.0], [0.0, 0.0, -1.0]])
        c2 = np.einsum("ij,njk,lk->nil", axes, self.cov[pick], axes)
        det = c2[:, 0, 0] * c2[:, 1, 1] - c2[:, 0, 1] ** 2
        inv = np.stack([c2[:, 1, 1], -c2[:, 0, 1], c2[:, 0, 0]], 1) / np.maximum(det, 1e-18)[:, None]
        radius = np.minimum(3.0 * np.sqrt(np.maximum(c2[:, 0, 0], c2[:, 1, 1])), 2.0)
        order = np.argsort(-s[pick])  # outside first: the viewer stands outside
        acc = np.zeros((height, width, 3))
        transmittance = np.ones((height, width))
        composite(u[pick][order], v[pick][order], inv[order], radius[order], self.scan.opacity[pick][order],
                  self.scan.colour[pick][order], RESOLUTION, width, height, acc, transmittance)
        cover = 1.0 - transmittance
        confidence = np.clip((cover - MIN_COVER) / (FULL_COVER - MIN_COVER), 0.0, 1.0)
        image = fill(acc / np.maximum(cover, 1e-9)[..., None], confidence)
        # how much of the face's opacity is wall-like: flat splats standing upright
        mass = self.scan.opacity[pick]
        upright = (self.flatness[pick] < 0.3) & (np.abs(self.normal[pick, 2]) < 0.35)
        wall_like = float(mass[upright].sum() / max(mass.sum(), 1e-9))
        return image, cover, wall_like


def roof_line(cover, width, height):
    """Per metre, the highest row with solid wall below it (most of the next SOLID_BELOW covered), coming down from
    the top: specks above the roof don't count, nor do windows and doors lower down. Metres below the photo top."""
    band = int(1.0 / RESOLUTION)
    below = int(SOLID_BELOW / RESOLUTION)
    tops = []
    for u0 in range(0, width, band):
        covered = (cover[:, u0:u0 + band].mean(1) > WALL_COVER).astype(float)
        solid = np.convolve(covered, np.ones(below) / below, mode="full")[below - 1:]
        rows = np.flatnonzero(covered.astype(bool) & (solid > SOLID_SHARE))
        tops.append(rows[0] * RESOLUTION if len(rows) else height * RESOLUTION)
    return ndimage.median_filter(np.array(tops), size=3, mode="nearest")


def steps(x0, heights):
    """Roof steps [x0, x1, height] from per-metre heights: runs within HEIGHT_TOLERANCE."""
    result = []
    i = 0
    while i < len(heights):
        j = i
        while j + 1 < len(heights) and abs(heights[j + 1] - np.median(heights[i:j + 1])) < HEIGHT_TOLERANCE:
            j += 1
        result.append([round(x0 + i, 2), round(x0 + j + 1, 2), round(float(np.median(heights[i:j + 1])), 2)])
        i = j + 1
    return result


def save_photo(out, faces, image, record):
    record["file"] = f"face_{len(faces):03d}.png"
    photo = Image.fromarray((np.clip(image, 0, 1) * 255).astype(np.uint8), "RGB")
    # power of two sides (rounded up, not to lose detail) so Unreal makes mip maps; the material places the photo
    # by world position
    pot = lambda n: 1 << max(5, min(12, int(np.ceil(np.log2(max(n, 1))))))
    photo.resize((pot(image.shape[1]), pot(image.shape[0])), Image.LANCZOS).save(os.path.join(out, record["file"]))
    faces.append(record)


def main(name):
    layout = json.load(open(os.path.join(GENERATED_DIR, f"{name}_layout.json")))
    out = os.path.join(OUT_DIR, name)
    os.makedirs(out, exist_ok=True)
    for old in os.listdir(out):
        if old.endswith(".png"):
            os.remove(os.path.join(out, old))
    start = time.time()
    scan = Scan(name)
    baker = Baker(scan)
    pos = scan.pos
    remove = np.zeros(len(pos), bool)
    boxes, faces, skipped = [], [], []

    for index, facade in enumerate(layout["facades"]):
        side, y = facade["side"], facade["y"]
        x0, x1, depth = facade["x0"], facade["x1"], facade["depth"]
        floor = min(st["floor"] for st in facade["stations"]) - 0.3
        top = max(step[2] for step in facade["heights"]) + floor + 0.3 + ABOVE_ROOF
        outward = np.array([0.0, -side])
        y_far = y + side * depth

        # the front, seen from the street: u along +X
        front_origin = np.array([x0, y, top])
        image, cover, wall_like = baker.bake(front_origin, np.array([1.0, 0.0]), outward, x1 - x0, top - floor)
        height_px, width_px = cover.shape
        below_top = roof_line(cover, width_px, height_px)
        heights = np.maximum((top - floor) - below_top, MIN_HEIGHT)
        rows = (np.arange(height_px)[:, None] * RESOLUTION) >= np.repeat(below_top, int(1.0 / RESOLUTION))[:width_px][None, :]
        wall_cover = float((cover > MIN_COVER)[rows].mean()) if rows.any() else 0.0
        if wall_cover < MIN_WALL_COVER or wall_like < MIN_WALL_LIKE:
            skipped.append({"facade": index, "wallCover": round(wall_cover, 2), "wallLike": round(wall_like, 2)})
            continue
        confidence = np.clip((cover - MIN_COVER) / (FULL_COVER - MIN_COVER), 0.0, 1.0)
        lower = image[height_px // 2:][confidence[height_px // 2:] > 0.5]
        average = (lower.mean(0) if len(lower) else np.array([0.5, 0.5, 0.5])).round(3).tolist()
        front_face = len(faces)
        save_photo(out, faces, image, {"origin": front_origin.tolist(), "u": [1.0, 0.0], "size": [x1 - x0, top - floor],
                                       "coverage": round(wall_cover, 3), "wallLike": round(wall_like, 3), "kind": "front"})

        run_steps = steps(x0, heights)
        for k, (sx0, sx1, step_height) in enumerate(run_steps):
            box_top = floor + step_height
            box = {"facade": index, "min": [sx0, min(y, y_far), floor], "max": [sx1, max(y, y_far), box_top],
                   "front": "+Y" if side < 0 else "-Y", "faces": {"+Y" if side < 0 else "-Y": front_face}, "average": average}
            # the ends: baked from outside where they show above the neighbouring step
            for end, x_end, neighbour in (("-X", sx0, run_steps[k - 1] if k > 0 else None), ("+X", sx1, run_steps[k + 1] if k + 1 < len(run_steps) else None)):
                low = floor + (neighbour[2] if neighbour else 0.0)
                if low >= box_top - 0.5:
                    continue
                direction = np.array([-1.0, 0.0]) if end == "-X" else np.array([1.0, 0.0])
                # u runs from the front towards the back, seen from outside
                u_axis = np.array([0.0, side]) if end == "-X" else np.array([0.0, side])
                origin = np.array([x_end, y, box_top + 0.3])
                end_image, end_cover, _ = baker.bake(origin, u_axis, direction, depth, box_top + 0.3 - floor)
                coverage = float((end_cover > MIN_COVER).mean())
                if coverage >= MIN_WALL_COVER:
                    box["faces"][end] = len(faces)
                    save_photo(out, faces, end_image, {"origin": origin.tolist(), "u": u_axis.tolist(), "size": [depth, box_top + 0.3 - floor],
                                                       "coverage": round(coverage, 3), "kind": "end"})
            boxes.append(box)
            # the box and its photos replace the splats inside it and just in front of it
            d = (pos[:, 1] - y) * side
            remove |= ((pos[:, 0] >= sx0) & (pos[:, 0] <= sx1) & (d > -SLAB_FRONT) & (d < depth) &
                       (pos[:, 2] > floor) & (pos[:, 2] < box_top + ROOF_MARGIN))

    write_ply(os.path.join(out, f"{name}_rebuilt.ply"), scan.header, scan.data[~remove])
    cm = lambda v: [round(c * 100.0, 1) for c in v]
    info = {
        "stage": name,
        "boxes": [dict(b, min=cm(b["min"]), max=cm(b["max"])) for b in boxes],
        "faces": [dict(f, origin=cm(f["origin"]), size=cm(f["size"])) for f in faces],
        "splats": int(len(pos)), "removed": int(remove.sum()), "kept": int((~remove).sum()),
        "scan": os.path.basename(scan.path),
        "skipped": skipped,
    }
    with open(os.path.join(out, "rebuilt.json"), "w") as f:
        json.dump(info, f)
    fronts = [f for f in faces if f["kind"] == "front"]
    print(f"{name}: {len(boxes)} boxes on {len(fronts)} facades ({len(skipped)} not built: too little wall or mostly leaves), "
          f"{len(faces) - len(fronts)} end photos; scan {len(pos):,} -> {info['kept']:,} splats "
          f"({remove.mean() * 100:.1f}% replaced), {time.time() - start:.0f}s")
    for s in skipped:
        print(f"  skipped facade {s['facade']}: wall cover {s['wallCover']}, wall-like {s['wallLike']}")


for stage in sys.argv[1:] or ["Hongdae"]:
    main(stage)
