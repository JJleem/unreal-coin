"""
Prepares gameplay geometry for the ANNX scans, in Unreal space (centimetres, Z up).

  * ground: the scan's collision mesh with its heights smoothed, so the character doesn't bob on scan noise
  * walls:  the splats are binned into a 2D grid; a cell is blocked when the summed opacity of splats at body height
            above the ground is high (buildings, walls, trees) or when there is no ground under it (edge of the scan).
            Small isolated blobs (people, signs, noise) are dropped, and cells around coins and the start stay open.
  * coins and start: placed on the smoothed ground

Output per stage, read by build_scan_stages.py:
  generated/<Name>_collision.json
  generated/<Name>_collision.png   top-down debug view: grey ground, red walls, orange breakables, yellow coins,
                                   blue start (+X up)

Needs numpy, scipy and Pillow, so it runs outside Unreal:
  python make_scan_collision.py
"""

import json
import os
import struct

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Scans"))
OUT_DIR = os.path.join(HERE, "generated")
SCALES = {k: v for k, v in json.load(open(os.path.join(HERE, "stage_scale.json"), encoding="utf-8")).items() if not k.startswith("_")}

SMOOTH_RADIUS = 2.0         # ground smoothing radius, metres
CELL = 0.5                  # wall grid cell, metres
BAND = (0.5, 2.5)           # body height band above the ground that counts as an obstacle, metres
MIN_OPACITY = 0.02          # scans are built from many faint overlapping splats, so opacity is summed per cell
MAX_SPLAT_SIZE = 1.0        # ignore huge blurry splats, metres
WALL_OPACITY = 10.0         # summed opacity per square metre in the band that makes a wall
MIN_WALL_AREA = 1.5         # blocked blobs smaller than this are dropped, square metres
GROUND_REACH = 1.5          # a cell without a ground vertex this close is off the map, metres
KEEP_CLEAR = 1.5            # radius kept open around coins and the start, metres
WALL_BOTTOM, WALL_TOP = -1.0, 4.0  # wall extent relative to the local ground, metres
BREAKABLE_MAX_AREA = 6.0    # free-standing blobs smaller than this (people, signs, bins) can be smashed, square metres
BREAKABLE_TOP = 2.4         # height of a breakable barrier above the local ground, metres
MAX_STEP_UP = 1.2           # tallest rise between neighbouring cells the player gets up without a ledge, metres
COIN_HEIGHT = 1.0           # coin centre above the ground, metres


def read_ply(path):
    with open(path, "rb") as f:
        header = b""
        while not header.endswith(b"end_header\n"):
            header += f.readline()
        lines = header.splitlines()
        names = [l.split()[-1].decode() for l in lines if l.startswith(b"property")]
        count = int(next(l for l in lines if l.startswith(b"element vertex")).split()[-1])
        return np.fromfile(f, dtype=np.dtype([(n, "<f4") for n in names]), count=count)


def read_glb(path):
    data = open(path, "rb").read()
    json_len, = struct.unpack_from("<I", data, 12)
    gltf = json.loads(data[20:20 + json_len])
    bin_offset = 20 + json_len + 8
    primitive = gltf["meshes"][0]["primitives"][0]

    def accessor(index, dtype, components):
        a = gltf["accessors"][index]
        view = gltf["bufferViews"][a["bufferView"]]
        start = bin_offset + view.get("byteOffset", 0) + a.get("byteOffset", 0)
        return np.frombuffer(data, dtype, a["count"] * components, start)

    positions = accessor(primitive["attributes"]["POSITION"], "<f4", 3).reshape(-1, 3)
    index_dtype = {5121: "<u1", 5123: "<u2", 5125: "<u4"}[gltf["accessors"][primitive["indices"]]["componentType"]]
    return positions, accessor(primitive["indices"], index_dtype, 1)


def to_metres(p, mpu):
    """(N,3) scan coordinates -> Unreal axes in metres (X forward, Y right, Z up), same mapping as OpenSplat4D."""
    p = np.asarray(p, np.float64)
    return np.stack([p[:, 2], p[:, 0], -p[:, 1]], axis=1) * mpu


def smooth_ground(ground):
    """Removes height spikes with a median, then evens out the rest with a mean, both over SMOOTH_RADIUS.
    Keeps real slopes and stairs but flattens the per-metre scan noise that makes the character bob."""
    xy = ground[:, :2]
    neighbours = []
    for i in range(0, len(ground), 2048):
        d2 = ((xy[i:i + 2048, None, :] - xy[None, :, :]) ** 2).sum(-1)
        neighbours += [np.flatnonzero(row) for row in d2 <= SMOOTH_RADIUS ** 2]

    z = ground[:, 2]
    z = np.array([np.median(z[n]) for n in neighbours])
    z = np.array([z[n].mean() for n in neighbours])
    return np.column_stack([xy, z])


def ground_height_at(ground, points_xy):
    """Height of the nearest ground vertex, and the distance to it."""
    z = np.empty(len(points_xy))
    dist = np.empty(len(points_xy))
    for i in range(0, len(points_xy), 4096):
        d2 = ((points_xy[i:i + 4096, None, :] - ground[None, :, :2]) ** 2).sum(-1)
        j = d2.argmin(1)
        z[i:i + 4096] = ground[j, 2]
        dist[i:i + 4096] = np.sqrt(d2[np.arange(len(j)), j])
    return z, dist


def boxes_of(mask, lo, cell_z, top):
    """Merges runs of cells along Y into boxes [minx, miny, minz, maxx, maxy, maxz] in metres."""
    boxes = []
    nx, ny = mask.shape
    for i in range(nx):
        j = 0
        while j < ny:
            if not mask[i, j]:
                j += 1
                continue
            k = j
            while k + 1 < ny and mask[i, k + 1]:
                k += 1
            z = cell_z[i, j:k + 1]
            boxes.append([lo[0] + i * CELL, lo[1] + j * CELL, z.min() + WALL_BOTTOM,
                          lo[0] + (i + 1) * CELL, lo[1] + (k + 1) * CELL, z.max() + top])
            j = k + 1
    return boxes


def reachable(open_cells, cell_z, start):
    """Cells reachable from start through open neighbours, never stepping up more than MAX_STEP_UP."""
    nx, ny = open_cells.shape
    seen = np.zeros_like(open_cells)
    if not (0 <= start[0] < nx and 0 <= start[1] < ny):
        return seen
    stack = [start]
    seen[start] = True
    while stack:
        i, j = stack.pop()
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny and open_cells[a, b] and not seen[a, b] \
                        and cell_z[a, b] - cell_z[i, j] <= MAX_STEP_UP:
                    seen[a, b] = True
                    stack.append((a, b))
    return seen


def open_facing(open_cells, position, lo, directions=16, reach=8.0):
    """Unreal yaw (degrees) to start facing: the camera sits behind the character, so prefer the direction with the
    most open space behind, then in front."""
    def free(angle):
        d = np.array([np.cos(angle), np.sin(angle)])
        for step in np.arange(CELL, reach, CELL / 2):
            i, j = ((position + d * step - lo) // CELL).astype(int)
            if not (0 <= i < open_cells.shape[0] and 0 <= j < open_cells.shape[1]) or not open_cells[i, j]:
                return step
        return reach

    angles = np.arange(directions) * 2 * np.pi / directions
    scores = [min(free(a + np.pi), 6.0) + 0.3 * free(a) for a in angles]
    # Unreal yaw is measured from +X towards +Y, which is this same angle
    return float(np.degrees(angles[int(np.argmax(scores))]))


def floor_mesh(has_ground, cell_z, lo):
    """Walkable floor without holes: a height field over the ground cells (grown under the walls' feet),
    with corner heights averaged from the neighbouring cells. Returns (vertices in metres, triangle indices)."""
    cells = ndimage.binary_dilation(has_ground, structure=np.ones((3, 3)), iterations=2)
    nx, ny = cells.shape

    # average the ground heights of the (up to four) ground cells around each corner
    z = np.where(has_ground, cell_z, 0.0)
    w = has_ground.astype(float)
    pad = lambda a: np.pad(a, 1)
    zs, ws = pad(z), pad(w)
    corner_sum = zs[:-1, :-1] + zs[1:, :-1] + zs[:-1, 1:] + zs[1:, 1:]
    corner_w = ws[:-1, :-1] + ws[1:, :-1] + ws[:-1, 1:] + ws[1:, 1:]
    nearest = ndimage.distance_transform_edt(corner_w == 0, return_distances=False, return_indices=True)
    corner_z = np.where(corner_w > 0, corner_sum / np.maximum(corner_w, 1), 0.0)
    corner_z = corner_z[nearest[0], nearest[1]]

    used = np.zeros((nx + 1, ny + 1), bool)
    used[:-1, :-1] |= cells
    used[1:, :-1] |= cells
    used[:-1, 1:] |= cells
    used[1:, 1:] |= cells
    index = -np.ones((nx + 1, ny + 1), int)
    index[used] = np.arange(used.sum())
    ci, cj = np.nonzero(used)
    vertices = np.column_stack([lo[0] + ci * CELL, lo[1] + cj * CELL, corner_z[ci, cj]])

    triangles = []
    for i, j in zip(*np.nonzero(cells)):
        a, b, c, d = index[i, j], index[i + 1, j], index[i + 1, j + 1], index[i, j + 1]
        triangles += [a, b, c, a, c, d]
    return vertices, [int(t) for t in triangles]


def build(folder):
    name = folder.split("_", 1)[1]
    path = os.path.join(SCANS_DIR, folder)
    stage = json.load(open(os.path.join(path, "stage.json"), encoding="utf-8"))
    mpu = stage["metresPerUnit"] * SCALES.get(name, 1.0)

    raw_ground, indices = read_glb(os.path.join(path, f"{name}_collision.glb"))
    raw_ground = to_metres(raw_ground, mpu)
    ground = smooth_ground(raw_ground)

    ply = read_ply(os.path.join(path, f"{name}.ply"))
    opacity = 1.0 / (1.0 + np.exp(-ply["opacity"].astype(np.float64)))
    size = np.exp(np.maximum(np.maximum(ply["scale_0"], ply["scale_1"]), ply["scale_2"])) * mpu
    keep = (opacity > MIN_OPACITY) & (size < MAX_SPLAT_SIZE)
    pts = to_metres(np.stack([ply["x"], ply["y"], ply["z"]], axis=1)[keep], mpu)
    alpha = opacity[keep]

    # grid over the ground footprint plus a margin
    lo = ground[:, :2].min(axis=0) - 2 * CELL
    nx, ny = np.ceil((ground[:, :2].max(axis=0) + 2 * CELL - lo) / CELL).astype(int)
    cx = lo[0] + (np.arange(nx) + 0.5) * CELL
    cy = lo[1] + (np.arange(ny) + 0.5) * CELL
    gx, gy = np.meshgrid(cx, cy, indexing="ij")
    cell_z, cell_dist = ground_height_at(ground, np.column_stack([gx.ravel(), gy.ravel()]))
    cell_z = cell_z.reshape(nx, ny)
    # the scan's ground mesh has holes; fill them so they become walkable floor rather than pits
    has_ground = ndimage.binary_fill_holes((cell_dist <= GROUND_REACH).reshape(nx, ny))

    # summed opacity of splats at body height, per square metre
    ix = ((pts[:, 0] - lo[0]) // CELL).astype(int)
    iy = ((pts[:, 1] - lo[1]) // CELL).astype(int)
    inside = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    ix, iy, alpha = ix[inside], iy[inside], alpha[inside]
    height = pts[inside, 2] - cell_z[ix, iy]
    band = (height > BAND[0]) & (height < BAND[1])
    density = np.zeros((nx, ny))
    np.add.at(density, (ix[band], iy[band]), alpha[band])
    density /= CELL * CELL

    # the scale correction spreads the same splats over a larger area, so the threshold follows it
    walls = density >= WALL_OPACITY / SCALES.get(name, 1.0) ** 2
    labels, n = ndimage.label(walls, structure=np.ones((3, 3)))
    areas = ndimage.sum(walls, labels, range(1, n + 1)) * CELL * CELL
    walls &= np.isin(labels, np.flatnonzero(areas >= MIN_WALL_AREA) + 1)
    blocked = walls | ~has_ground

    # coins and start sit on the smoothed ground and stay reachable
    coins = to_metres(stage["coins"], mpu)
    start = to_metres([stage["start"]], mpu)
    keep_xy = np.vstack([coins, start])[:, :2]
    keep_z, _ = ground_height_at(ground, keep_xy)
    for x, y in keep_xy:
        blocked &= (gx - x) ** 2 + (gy - y) ** 2 > KEEP_CLEAR ** 2

    # small free-standing blobs are often people, signs or noise rather than buildings: the player can smash them.
    # Blobs touching the edge of the scan stay solid so the map stays closed.
    edge = ndimage.binary_dilation(~has_ground, structure=np.ones((3, 3)))
    labels, n = ndimage.label(walls & blocked, structure=np.ones((3, 3)))
    breakables = []
    for blob in range(1, n + 1):
        mask = labels == blob
        if mask.sum() * CELL * CELL < BREAKABLE_MAX_AREA and not (mask & edge).any():
            breakables.append(boxes_of(mask, lo, cell_z, BREAKABLE_TOP))
            blocked &= ~mask

    boxes = boxes_of(blocked, lo, cell_z, WALL_TOP)

    # every coin must be reachable from the start: walk the open cells (breakables count as open, they can be
    # smashed) and move coins that can't be reached to the nearest reachable cell
    open_cells = has_ground & ~blocked
    reach = reachable(open_cells, cell_z, (int((start[0, 0] - lo[0]) // CELL), int((start[0, 1] - lo[1]) // CELL)))
    moved = 0
    for c in range(len(coins)):
        ci, cj = int((coins[c, 0] - lo[0]) // CELL), int((coins[c, 1] - lo[1]) // CELL)
        if not reach[ci, cj]:
            ri, rj = np.nonzero(reach)
            k = np.argmin((ri - ci) ** 2 + (rj - cj) ** 2)
            coins[c, :2] = lo[0] + (ri[k] + 0.5) * CELL, lo[1] + (rj[k] + 0.5) * CELL
            keep_z[c] = cell_z[ri[k], rj[k]]
            moved += 1

    floor_vertices, floor_indices = floor_mesh(has_ground, cell_z, lo)
    start_yaw = open_facing(open_cells, start[0, :2], lo)

    cm = lambda a: (np.asarray(a) * 100.0).round(1).tolist()
    result = {
        "stage": name,
        "metresPerUnit": mpu,
        "ground": {"vertices": cm(floor_vertices), "indices": floor_indices},
        "walls": cm(boxes),
        "breakables": [cm(group) for group in breakables],
        "start": cm([start[0, 0], start[0, 1], keep_z[-1]]),
        "startYaw": start_yaw,
        "coins": cm(np.column_stack([coins[:, :2], keep_z[:-1] + COIN_HEIGHT]))
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{name}_collision.json"), "w") as f:
        json.dump(result, f)

    # debug image
    img = np.zeros((nx, ny, 3), np.uint8)
    img[has_ground] = (90, 90, 90)
    img[blocked] = (200, 40, 40)
    for group in breakables:
        for b in group:
            i0, j0 = int(round((b[0] - lo[0]) / CELL)), int(round((b[1] - lo[1]) / CELL))
            i1, j1 = int(round((b[3] - lo[0]) / CELL)), int(round((b[4] - lo[1]) / CELL))
            img[i0:i1, j0:j1] = (255, 150, 30)
    for (x, y), color in zip(keep_xy, [(255, 210, 0)] * len(coins) + [(0, 160, 255)]):
        i, j = int((x - lo[0]) // CELL), int((y - lo[1]) // CELL)
        img[max(i - 1, 0):i + 2, max(j - 1, 0):j + 2] = color
    Image.fromarray(img[::-1]).resize((ny * 4, nx * 4), Image.NEAREST).save(os.path.join(OUT_DIR, f"{name}_collision.png"))

    walkable = has_ground & ~blocked
    bump_raw = np.percentile(np.abs(raw_ground[:, 2] - np.median(raw_ground[:, 2])), 90)
    bump = np.percentile(np.abs(ground[:, 2] - np.median(ground[:, 2])), 90)
    print(f"{name:13s} scale x{SCALES.get(name, 1.0):.2f}  walkable {walkable.sum() * CELL * CELL:5.0f} m2  "
          f"wall boxes {len(boxes):4d}  breakables {len(breakables):3d}  coins moved {moved}  ground spread (p90) {bump_raw:.2f} m -> {bump:.2f} m")


def main():
    for folder in sorted(d for d in os.listdir(SCANS_DIR) if d[:2].isdigit()):
        build(folder)


main()
