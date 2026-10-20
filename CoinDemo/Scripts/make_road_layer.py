"""
Hybrid road surface for a scan stage: the walkable ground becomes a textured mesh, and the splats it replaces are
removed from a new copy of the scan.

Why: the scans build the street out of many faint, view-facing splats. From a game camera (lower and at other
angles than the capture camera) they render as dark scratches, light streaks and see-through patches. Seen from
straight above, the same splats give a sharp image of the road (markings, manholes, curbs). So this script

  1. selects the "road layer": splats within a band around the walkable ground (from make_scan_collision.py),
  2. rasterizes them top-down into an orthophoto (Gaussian footprints composited front to back) and fills the
     gaps the capture never saw (directly under the walking path of the camera) with a push-pull fill,
  3. writes the road mesh (the collision height field over the open cells, shrunk away from walls),
  4. writes a copy of the scan without the road-layer splats over the mesh, and without needle splats
     (one axis > NEEDLE x the next, which render as scratches), see clean_scans.py.

The original scan is never modified. build_road_layer.py brings the results into Unreal.

Output (per stage, in ../SourceAssets/RoadLayers/):
  <Name>_road.png         orthophoto, sRGB, +X right, +Y down, origin at the json's "origin"
  <Name>_road.json        texture placement, road mesh (Unreal cm), splat counts
  <Name>_hybrid.ply       the scan without the replaced splats

Needs numpy, scipy, Pillow and numba, so it runs outside Unreal:
  python make_road_layer.py Hongdae
"""

import json
import os
import sys
import time

import numpy as np
from numba import njit
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Scans"))
GENERATED_DIR = os.path.join(HERE, "generated")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "RoadLayers"))
SCALES = {k: v for k, v in json.load(open(os.path.join(HERE, "stage_scale.json"), encoding="utf-8")).items() if not k.startswith("_")}

RESOLUTION = 0.025          # orthophoto metres per pixel
BAND = (-3.0, 0.3)          # road layer: splats this far below / above the walkable ground, metres. The road is
                            # many layers deep (faint splats spread below the surface), so the band reaches down far
MAX_FOOTPRINT = 3.0         # largest splat radius rasterized, metres
CELL = 0.5                  # collision grid cell, metres (make_scan_collision.py)
WALL_MARGIN = 0.25          # the mesh stops this far from wall cells, so building bases keep their splats
NEEDLE = 15.0               # longest / middle axis above this renders as a scratch: removed everywhere
NEEDLE_KEEP_OPACITY = 0.4   # ...unless it is fairly opaque (wires, poles and railings tend to be)
MIN_WEIGHT = 0.3            # orthophoto pixels less covered than this (seen from above) are filled from around them,
FULL_WEIGHT = 0.85          # ...pixels between the two are blended with their surroundings by how well they are covered


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


def covariance_xy(data, mpu):
    """Top-down (Unreal XY) 2x2 covariance of every splat, metres^2. PLY -> Unreal is (z, x, -y) x mpu."""
    q = np.stack([data["rot_0"], data["rot_1"], data["rot_2"], data["rot_3"]], 1).astype(np.float64)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    w, x, y, z = q.T
    rot = np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], 1),
                    np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], 1),
                    np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], 1)], 1)
    scale2 = np.exp(2.0 * np.stack([data["scale_0"], data["scale_1"], data["scale_2"]], 1).astype(np.float64))
    cov = np.einsum("nij,nj,nkj->nik", rot, scale2, rot)
    # Unreal X = PLY z, Unreal Y = PLY x
    return np.stack([np.stack([cov[:, 2, 2], cov[:, 2, 0]], 1), np.stack([cov[:, 0, 2], cov[:, 0, 0]], 1)], 1) * mpu ** 2


@njit(cache=True)
def rasterize(px, py, inv, radius, opacity, colour, res, width, height, acc_colour, transmittance):
    """Composites 2D Gaussians front to back (callers pass them sorted top first), like a camera looking down."""
    for i in range(px.shape[0]):
        r = radius[i] / res
        cx = px[i] / res
        cy = py[i] / res
        x0 = max(int(cx - r), 0)
        x1 = min(int(cx + r) + 1, width)
        y0 = max(int(cy - r), 0)
        y1 = min(int(cy + r) + 1, height)
        a00 = inv[i, 0]
        a01 = inv[i, 1]
        a11 = inv[i, 2]
        for yy in range(y0, y1):
            dy = (yy + 0.5) * res - py[i]
            for xx in range(x0, x1):
                t = transmittance[yy, xx]
                if t < 0.003:
                    continue
                dx = (xx + 0.5) * res - px[i]
                e = 0.5 * (a00 * dx * dx + 2.0 * a01 * dx * dy + a11 * dy * dy)
                if e > 4.5:
                    continue
                a = min(opacity[i] * np.exp(-e), 0.99)
                if a < 0.004:
                    continue
                acc_colour[yy, xx, 0] += t * a * colour[i, 0]
                acc_colour[yy, xx, 1] += t * a * colour[i, 1]
                acc_colour[yy, xx, 2] += t * a * colour[i, 2]
                transmittance[yy, xx] = t * (1.0 - a)


def push_pull_fill(colour, confidence):
    """Blends every pixel with a pyramid average of its confident neighbours (push-pull) by its own confidence (0..1):
    unseen pixels are filled, half-seen ones (dark, noisy) pulled towards their surroundings, well seen ones kept."""
    levels = [(colour * confidence[..., None], confidence.astype(np.float64))]
    while min(levels[-1][1].shape) > 2:
        c, w = levels[-1]
        h, wd = (c.shape[0] // 2) * 2, (c.shape[1] // 2) * 2
        c, w = c[:h, :wd], w[:h, :wd]
        c2 = c[0::2, 0::2] + c[1::2, 0::2] + c[0::2, 1::2] + c[1::2, 1::2]
        w2 = w[0::2, 0::2] + w[1::2, 0::2] + w[0::2, 1::2] + w[1::2, 1::2]
        levels.append((c2, w2))
    filled = levels[-1][0] / np.maximum(levels[-1][1], 1e-9)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)
        up = np.pad(up, ((0, c.shape[0] - up.shape[0]), (0, c.shape[1] - up.shape[1]), (0, 0)), mode="edge")
        up = ndimage.uniform_filter(up, size=(3, 3, 1))
        mine = c / np.maximum(w, 1e-9)[..., None]
        blend = np.clip(w, 0.0, 1.0)[..., None]
        filled = mine * blend + up * (1.0 - blend)
    return colour * confidence[..., None] + filled * (1.0 - confidence[..., None])


def build(name):
    folder = next(d for d in os.listdir(SCANS_DIR) if d.endswith("_" + name))
    stage = json.load(open(os.path.join(SCANS_DIR, folder, "stage.json"), encoding="utf-8"))
    mpu = stage["metresPerUnit"] * SCALES.get(name, 1.0)
    collision = json.load(open(os.path.join(GENERATED_DIR, f"{name}_collision.json")))
    header, data = read_ply(os.path.join(SCANS_DIR, folder, f"{name}.ply"))
    start = time.time()

    # positions in Unreal metres and height above the walkable ground
    pos = np.stack([data["z"], data["x"], -data["y"]], 1).astype(np.float64) * mpu
    ground = np.array(collision["ground"]["vertices"]) / 100.0
    distance, nearest = cKDTree(ground[:, :2]).query(pos[:, :2])
    height = pos[:, 2] - ground[nearest, 2]

    # open cells: ground cells not covered by a wall box, shrunk by the margin
    lo = ground[:, :2].min(0)
    shape = np.round((ground[:, :2].max(0) - lo) / CELL).astype(int)
    has_ground = np.zeros(shape, bool)
    corner = np.round((ground[:, :2] - lo) / CELL).astype(int)
    indices = np.array(collision["ground"]["indices"]).reshape(-1, 3)
    centre = (corner[indices[:, 0]] + corner[indices[:, 1]] + corner[indices[:, 2]]) / 3.0
    has_ground[np.clip(np.floor(centre[:, 0]).astype(int), 0, shape[0] - 1), np.clip(np.floor(centre[:, 1]).astype(int), 0, shape[1] - 1)] = True
    walls = np.zeros(shape, bool)
    for box in collision["walls"]:
        i0, j0 = np.floor((np.array(box[:2]) / 100.0 - lo) / CELL + 0.01).astype(int)
        i1, j1 = np.ceil((np.array(box[3:5]) / 100.0 - lo) / CELL - 0.01).astype(int)
        walls[max(i0, 0):max(i1, 0), max(j0, 0):max(j1, 0)] = True
    road_cells = has_ground & ~ndimage.binary_dilation(walls, iterations=1)
    road_cells = ndimage.binary_opening(road_cells, iterations=1)

    # road layer splats
    cell = np.floor((pos[:, :2] - lo) / CELL).astype(int)
    inside = (cell[:, 0] >= 0) & (cell[:, 0] < shape[0]) & (cell[:, 1] >= 0) & (cell[:, 1] < shape[1])
    # splats are only removed a cell inside the mesh edge: the ones left along the edge draw over it and hide the
    # cell steps of the mesh outline
    removal_cells = ndimage.binary_erosion(road_cells, iterations=1)
    on_road = np.zeros(len(data), bool)
    on_road[inside] = removal_cells[cell[inside, 0], cell[inside, 1]]
    layer = (height > BAND[0]) & (height < BAND[1]) & (distance < 1.0)

    scales = np.sort(np.exp(np.stack([data["scale_0"], data["scale_1"], data["scale_2"]], 1).astype(np.float64)), 1)
    opacity = 1.0 / (1.0 + np.exp(-data["opacity"].astype(np.float64)))
    needle = (scales[:, 2] / np.maximum(scales[:, 1], 1e-12) > NEEDLE) & (opacity < NEEDLE_KEEP_OPACITY)

    # orthophoto of the road layer around the road cells (a little wider, so the mesh edge has real texture)
    near_road = np.zeros(len(data), bool)
    wide = ndimage.binary_dilation(road_cells, iterations=4)
    near_road[inside] = wide[cell[inside, 0], cell[inside, 1]]
    source = layer & near_road & ~needle
    cov = covariance_xy(data[source], mpu)
    det = cov[:, 0, 0] * cov[:, 1, 1] - cov[:, 0, 1] ** 2
    inv = np.stack([cov[:, 1, 1], -cov[:, 0, 1], cov[:, 0, 0]], 1) / np.maximum(det, 1e-18)[:, None]
    radius = np.minimum(3.0 * np.sqrt(np.maximum(cov[:, 0, 0], cov[:, 1, 1])), MAX_FOOTPRINT)
    colour = np.clip(0.5 + 0.28209479 * np.stack([data["f_dc_0"], data["f_dc_1"], data["f_dc_2"]], 1)[source].astype(np.float64), 0.0, 1.0)

    width, height_px = np.ceil(shape * CELL / RESOLUTION).astype(int)
    acc_colour = np.zeros((height_px, width, 3))
    transmittance = np.ones((height_px, width))
    order = np.argsort(-pos[source, 2])
    rasterize((pos[source, 0] - lo[0])[order], (pos[source, 1] - lo[1])[order], inv[order], radius[order],
              opacity[source][order], colour[order], RESOLUTION, width, height_px, acc_colour, transmittance)
    coverage = 1.0 - transmittance
    known = coverage > MIN_WEIGHT
    confidence = np.clip((coverage - MIN_WEIGHT) / (FULL_WEIGHT - MIN_WEIGHT), 0.0, 1.0)
    image = acc_colour / np.maximum(coverage, 1e-9)[..., None]
    image = push_pull_fill(image, confidence)

    # road mesh: the collision height field over the road cells
    keep = road_cells[np.clip(np.floor(centre[:, 0]).astype(int), 0, shape[0] - 1), np.clip(np.floor(centre[:, 1]).astype(int), 0, shape[1] - 1)]
    used = np.unique(indices[keep])
    remap = -np.ones(len(ground), int)
    remap[used] = np.arange(len(used))

    # the hybrid scan: no road layer over the mesh, no needles
    removed = (layer & on_road) | needle
    os.makedirs(OUT_DIR, exist_ok=True)
    write_ply(os.path.join(OUT_DIR, f"{name}_hybrid.ply"), header, data[~removed])
    # power of two sides, so Unreal builds mip maps for it (it skips other sizes)
    photo = Image.fromarray((np.clip(image, 0, 1) * 255).astype(np.uint8), "RGB")
    photo = photo.resize((1 << int(np.log2(width)), 1 << int(np.log2(height_px))), Image.LANCZOS)
    photo.save(os.path.join(OUT_DIR, f"{name}_road.png"))
    seen = known[np.repeat(np.repeat(road_cells.T, int(CELL / RESOLUTION), 0), int(CELL / RESOLUTION), 1)[:height_px, :width]]
    info = {
        "stage": name,
        "origin": (lo * 100.0).round(2).tolist(),
        "size": (np.array([width, height_px]) * RESOLUTION * 100.0).round(2).tolist(),
        "resolution": RESOLUTION,
        "vertices": (ground[used] * 100.0).round(1).tolist(),
        "indices": remap[indices[keep]].ravel().tolist(),
        "splats": int(len(data)),
        "removedRoadLayer": int((layer & on_road & ~needle).sum()),
        "removedNeedles": int(needle.sum()),
        "kept": int((~removed).sum()),
        "roadArea_m2": float(road_cells.sum() * CELL * CELL),
        "orthophotoCoverage": float(seen.mean()),
    }
    with open(os.path.join(OUT_DIR, f"{name}_road.json"), "w") as f:
        json.dump(info, f)
    print(f"{name}: {len(data):,} splats -> kept {info['kept']:,} (road layer {info['removedRoadLayer']:,}, needles "
          f"{info['removedNeedles']:,}), road {info['roadArea_m2']:.0f} m2, photo {width}x{height_px} "
          f"({info['orthophotoCoverage'] * 100:.0f}% seen from above), {time.time() - start:.0f}s")


for stage_name in sys.argv[1:] or ["Hongdae"]:
    build(stage_name)
