"""
Step 3 (outside Unreal): the playable layout of the Parking Tower stage, in Unreal cm, read by build_parking_stage.py.

  ~/.venvs/gs/bin/python -I plan.py

The deck is 3.3 m from floor to slab (pipes and lights hang lower), so nothing here goes up the way the other
stages' towers and 6 m jump pads do: the player stays on the floor and the course is about running the aisles.
Its look follows the reference video's AR overlay (green outlines on the free stalls, a route line on the floor):
  * coins in free stalls, each outlined in green on the floor with a "주차 가능" caption
  * barrier arms across the aisles at 135-160 cm: too low to walk under, too close to the ceiling to jump over,
    the player slides under them (crouched capsule is 120 cm)
  * a low jump pad over the middle stall block, with a coin at the top of the arc
  * low holographic blocks (up to 1.1 m, so the head stays under the ceiling)
  * an orange breakable cage around one coin, the hidden gem on a block in the far handicap stall
  * a cyan route line with chevrons on the floor, rounded at the corners

Collision: the floor height field, the scanned pillars, cars, rails and walls (hidden, they are visible in the scan),
an invisible boundary with the proximity grid where the deck opens onto ramps or the lobby, and a ceiling.

Writes generated/ParkingTower_stage.json and SourceAssets/ParkingStage/plan.png (ortho overlay).
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

CEILING = 335.0           # underside of the slab is about 331 cm above the floor
WALL_TOP = 345.0
COIN_HEIGHT = 100.0

# playable deck: rectangles that are added, then ones that are cut out (world cm: x0, x1, y0, y1)
DECK_ADD = [(-3600, 3780, -1330, 1500),       # aisles, stall rows and the middle block, out to the rails
            (3780, 4200, 120, 820)]           # the stall bay at the far end, inside its bollards
DECK_CUT = [(-4000, -3040, -2000, -700),      # lit lobby and doorway beside the near stall row (badly captured)
            (3420, 4500, -2000, -760)]        # wall beside the far ramp

START = (-2700.0, -450.0, 0.0)               # near cross aisle, looking up the left aisle like the video's first shot

# coins: x, y, height above the floor; "stall" puts a green AR box on the stall around it
COINS = [
    {"at": (-1150, -450), "note": "left aisle warm-up"},
    {"at": (-940, -1010), "stall": (-1060, -820, -1250, -780), "note": "free stall, left row"},
    {"at": (300, -450), "z": 50, "note": "under the first barrier arm"},
    {"at": (1430, -1010), "stall": (1310, 1560, -1250, -780), "cage": True, "note": "caged stall, left row"},
    {"at": (3420, -280), "z": 210, "note": "on the top block in the far cross aisle"},
    {"at": (4000, 470), "note": "far stall bay"},
    {"at": (3350, 1250), "note": "far right corner"},
    {"at": (1150, 610), "stall": (1060, 1300, 380, 860), "note": "free stall between the cars, middle block"},
    {"at": (500, 1180), "z": 50, "note": "under the right aisle barrier arm"},
    {"at": (-2650, 400), "note": "near cross aisle, after the jump pad"},
    {"at": (-3280, 1060), "stall": (-3540, -3060, 870, 1110), "note": "green EV stall, near row"},
    {"at": (-1250, 1180), "note": "right aisle, before the jump pad"},
]
# jump pad at the end of the right aisle, back over the middle block to the left aisle, coin at the top of the arc
PAD = {"from": (-1650, 1200), "to": (-1650, -450), "arc": 90.0, "coin": (-1650, 380, 200)}
# barrier arms across the aisles: x, y0, y1 (bar 135-160 cm above the floor, a post at one end)
ARMS = [(300, -700, -220), (1800, -700, -220), (500, 930, 1460), (-900, 930, 1460)]
ARM_BOTTOM, ARM_TOP = 135.0, 160.0
# low blocks: centre x, y, top above the floor, size x, y
BLOCKS = [(3400, -700, 40, 120, 120), (3420, -490, 80, 120, 120), (3420, -280, 110, 140, 140),
          (3320, -1080, 90, 90, 90)]        # the last one carries the gem
GEM_BLOCK = 3
# route line on the floor like the reference video's navigation line: polyline of the intended route with rounded
# corners, chevrons along it
ROUTE = [(-2300, -450), (3250, -450), (3350, 300), (3350, 1200), (-1300, 1200)]
CHEVRON_STEP = 160.0
ROUTE_STEP = 50.0
ROUTE_FILLET = 300.0


def load_objects():
    o = json.load(open(os.path.join(S.OUT_DIR, "objects.json")))
    fl = o["floor"]
    fz = np.array(fl["z"])

    def floor_at(x, y):
        return float(ndimage.map_coordinates(fz, [[(x - fl["x0"]) / fl["cell"] - 0.5], [(y - fl["y0"]) / fl["cell"] - 0.5]],
                                             order=1, mode="nearest")[0])
    blocked = np.load(os.path.join(S.OUT_DIR, "blocked.npy"))
    return o, fz, floor_at, blocked


def rect_mask(shape, x0, y0, cell, rects):
    m = np.zeros(shape, bool)
    for a, b, c, d in rects:
        i0, i1 = int(max((a - x0) // cell, 0)), int(min(math.ceil((b - x0) / cell), shape[0]))
        j0, j1 = int(max((c - y0) // cell, 0)), int(min(math.ceil((d - y0) / cell), shape[1]))
        if i1 > i0 and j1 > j0:
            m[i0:i1, j0:j1] = True
    return m


def merge_boxes(mask, x0, y0, cell, z0, z1):
    """Greedy rectangles over a boolean grid: runs along Y, extended along X while the same run repeats."""
    boxes = []
    used = np.zeros_like(mask)
    nx, ny = mask.shape
    for i in range(nx):
        j = 0
        while j < ny:
            if not mask[i, j] or used[i, j]:
                j += 1
                continue
            k = j
            while k + 1 < ny and mask[i, k + 1] and not used[i, k + 1]:
                k += 1
            e = i
            while e + 1 < nx and mask[e + 1, j:k + 1].all() and not used[e + 1, j:k + 1].any():
                e += 1
            used[i:e + 1, j:k + 1] = True
            boxes.append([x0 + i * cell, y0 + j * cell, z0, x0 + (e + 1) * cell, y0 + (k + 1) * cell, z1])
            j = k + 1
    return boxes


def main():
    o, fz, floor_at, blocked = load_objects()
    g = o["grid"]
    x0, y0, cell = g["x0"], g["y0"], g["cell"]
    shape = blocked.shape

    deck = rect_mask(shape, x0, y0, cell, DECK_ADD) & ~rect_mask(shape, x0, y0, cell, DECK_CUT)
    # tiny blobs inside the deck are noise, not obstacles
    lab, n = ndimage.label(blocked, np.ones((3, 3)))
    sizes = ndimage.sum(blocked, lab, range(1, n + 1)) * (cell / 100) ** 2
    small = np.isin(lab, np.flatnonzero(sizes < 0.1) + 1)
    solid = blocked & ~(small & deck)

    ring = ndimage.binary_dilation(deck, np.ones((3, 3)), iterations=10) & ~deck     # 1 m around the deck
    hidden = solid & (ring | deck)                         # real things: pillars, cars, rails, walls
    # open edges: ring cells the player could reach from the deck without passing something solid
    free = (deck | ring) & ~solid
    lab, _ = ndimage.label(free)
    si, sj = int((START[0] - x0) // cell), int((START[1] - y0) // cell)
    boundary = ring & (lab == lab[si, sj])

    zlo = min(fz.min(), 0) - 60.0
    solid_boxes = merge_boxes(hidden, x0, y0, cell, zlo, WALL_TOP)
    boundary_boxes = merge_boxes(boundary, x0, y0, cell, zlo, WALL_TOP)

    # floor height field over the deck and 1.5 m beyond (50 cm cells, corners from the measured floor)
    fl = o["floor"]
    fcell = fl["cell"]
    area = ndimage.binary_dilation(deck, np.ones((3, 3)), iterations=15)
    ii, jj = np.nonzero(area[::5, ::5])                     # 10 cm grid -> 50 cm cells
    cells = set(zip(ii.tolist(), jj.tolist()))
    vid, verts, tris = {}, [], []

    def vert(a, b):
        if (a, b) not in vid:
            x, y = x0 + a * fcell, y0 + b * fcell
            vid[(a, b)] = len(verts)
            verts.append([x, y, round(floor_at(x, y), 1)])
        return vid[(a, b)]
    for a, b in sorted(cells):
        p, q, r, s = vert(a, b), vert(a + 1, b), vert(a + 1, b + 1), vert(a, b + 1)
        tris += [p, q, r, p, r, s]

    # ceiling: one slab over the whole area
    ax = np.nonzero(area.any(1))[0]
    ay = np.nonzero(area.any(0))[0]
    ceiling = [x0 + ax[0] * cell, y0 + ay[0] * cell, CEILING, x0 + (ax[-1] + 1) * cell, y0 + (ay[-1] + 1) * cell, CEILING + 60]

    on_floor = lambda x, y, h: [float(x), float(y), round(floor_at(x, y) + h, 1)]
    coins, stalls, cage = [], [], []
    for c in COINS:
        x, y = c["at"]
        coins.append(on_floor(x, y, c.get("z", COIN_HEIGHT)))
        if "stall" in c:
            a, b, cc, d = c["stall"]
            stalls.append({"center": on_floor((a + b) / 2, (cc + d) / 2, 0), "size": [b - a, d - cc], "coin": len(coins) - 1})
        if c.get("cage"):
            z = floor_at(x, y)
            h, t, top = 115.0, 25.0, 280.0
            for bx in ([x - h, y - h, x + h, y - h + t], [x - h, y + h - t, x + h, y + h],
                       [x - h, y - h + t, x - h + t, y + h - t], [x + h - t, y - h + t, x + h, y + h - t]):
                cage.append([bx[0], bx[1], z - 20, bx[2], bx[3], z + top])

    platforms = []
    for k, (x, y, top, sx, sy) in enumerate(BLOCKS):
        f = floor_at(x, y)
        platforms.append({"center": [x, y, f + top], "size": [sx, sy, top + 30], "color": "cyan"})
    gem_block = BLOCKS[GEM_BLOCK]
    gem = on_floor(gem_block[0], gem_block[1], gem_block[2] + COIN_HEIGHT)

    arms = []
    for x, a, b in ARMS:
        f = floor_at(x, (a + b) / 2)
        arms.append({"bar": [x - 12, a, f + ARM_BOTTOM, x + 12, b, f + ARM_TOP],
                     "post": [x - 20, b - 40, f - 10, x + 20, b, f + ARM_TOP + 10]})

    px, py = PAD["from"]
    tx, ty = PAD["to"]
    pad = {"at": on_floor(px, py, 0), "target": on_floor(tx, ty, 0), "arc": PAD["arc"]}
    coins.append(on_floor(PAD["coin"][0], PAD["coin"][1], PAD["coin"][2]))

    # route line: the polyline with rounded corners, sampled every ROUTE_STEP; chevrons every CHEVRON_STEP along it
    pts = [np.array(ROUTE[0], float)]
    for a, b, c in zip(ROUTE[:-2], ROUTE[1:-1], ROUTE[2:]):
        a, b, c = (np.array(v, float) for v in (a, b, c))
        u, v = (a - b) / np.linalg.norm(a - b), (c - b) / np.linalg.norm(c - b)
        r = min(ROUTE_FILLET, np.linalg.norm(a - b) / 2, np.linalg.norm(c - b) / 2)
        p0, p1 = b + u * r, b + v * r
        for t in np.linspace(0, 1, 9):          # quadratic Bezier through the corner
            pts.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1)
    pts.append(np.array(ROUTE[-1], float))
    route, chevrons = [], []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / ROUTE_STEP)))
        for t in np.arange(n) / n:
            route.append(a + (b - a) * t)
    route.append(pts[-1])
    route = np.array(route)
    along = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(route, axis=0), axis=1))])
    for d in np.arange(CHEVRON_STEP, along[-1], CHEVRON_STEP):
        k = min(int(np.searchsorted(along, d)), len(route) - 1)
        dx, dy = route[min(k + 1, len(route) - 1)] - route[max(k - 1, 0)]
        chevrons.append({"at": on_floor(route[k][0], route[k][1], 2), "yaw": round(math.degrees(math.atan2(dy, dx)), 1)})
    route = [on_floor(x, y, 1) for x, y in route]

    # a point in the splat actor's space and where this placement puts it, checked by the level builder against
    # Unreal's own transform
    pl = json.load(open(os.path.join(S.OUT_DIR, "placement.json")))
    probe = np.array([1000.0, 500.0, 30.0])
    check = {"local": probe.tolist(), "world": (S.to_world(probe[None] * S.MPU, pl)[0]).round(2).tolist()}

    sx, sy, _ = START
    data = {
        "stage": "ParkingTower",
        "placement": pl, "placementCheck": check,
        "ground": {"vertices": verts, "indices": tris},
        "solid": solid_boxes, "boundary": boundary_boxes, "ceiling": ceiling,
        "start": on_floor(sx, sy, 0), "startYaw": 0.0,
        "coins": coins, "stalls": stalls, "cage": cage, "platforms": platforms, "gem": gem,
        "arms": arms, "pad": pad, "route": route, "chevrons": chevrons,
    }
    os.makedirs(S.GENERATED, exist_ok=True)
    json.dump(data, open(os.path.join(S.GENERATED, "ParkingTower_stage.json"), "w"))

    # overlay (ortho: 5 cm/px, X = (1000 - row) * 5, Y = (col - 450) * 5)
    img = Image.open(os.path.join(S.OUT_DIR, "ortho_low.png")).convert("RGB")
    dr = ImageDraw.Draw(img, "RGBA")
    px_ = lambda x, y: ((y / 5) + 450, 1000 - x / 5)

    def rect(b, fill=None, outline=None):
        (c0, r1), (c1, r0) = px_(b[0], b[1]), px_(b[3], b[4]) if len(b) == 6 else px_(b[2], b[3])
        dr.rectangle([min(c0, c1), min(r0, r1), max(c0, c1), max(r0, r1)], fill=fill, outline=outline)
    for b in solid_boxes:
        rect(b, fill=(255, 40, 40, 110))
    for b in boundary_boxes:
        rect(b, fill=(40, 160, 255, 110))
    for s in stalls:
        (x, y, _), (w, h) = s["center"], s["size"]
        rect([x - w / 2, y - h / 2, 0, x + w / 2, y + h / 2, 0], outline=(60, 255, 90, 255))
    for b in cage:
        rect(b, fill=(255, 150, 30, 200))
    for a in arms:
        rect(a["bar"], fill=(255, 30, 60, 230))
        rect(a["post"], fill=(255, 255, 255, 230))
    for p in platforms:
        (x, y, _), (w, h, _) = p["center"], p["size"]
        rect([x - w / 2, y - h / 2, 0, x + w / 2, y + h / 2, 0], fill=(60, 200, 255, 200))
    for c in chevrons:
        x, y, _ = c["at"]
        a = math.radians(c["yaw"])
        tip = px_(x + 40 * math.cos(a), y + 40 * math.sin(a))
        for side in (-1, 1):
            b = a + side * math.radians(140)
            dr.line([tip, px_(x + 40 * math.cos(a) + 70 * math.cos(b), y + 40 * math.sin(a) + 70 * math.sin(b))], fill=(0, 255, 255, 255), width=3)
    for k, (x, y, _) in enumerate(coins, start=1):
        c, r = px_(x, y)
        dr.ellipse([c - 7, r - 7, c + 7, r + 7], fill=(255, 210, 0, 255))
        dr.text((c + 9, r - 6), str(k), fill=(255, 255, 0, 255))
    c, r = px_(gem[0], gem[1])
    dr.ellipse([c - 7, r - 7, c + 7, r + 7], fill=(255, 0, 255, 255))
    c0, r0 = px_(*PAD["from"])
    c1, r1 = px_(*PAD["to"])
    dr.line([c0, r0, c1, r1], fill=(60, 255, 120, 255), width=3)
    dr.ellipse([c0 - 10, r0 - 10, c0 + 10, r0 + 10], outline=(60, 255, 120, 255), width=3)
    c, r = px_(sx, sy)
    dr.ellipse([c - 9, r - 9, c + 9, r + 9], fill=(0, 120, 255, 255))
    img.save(os.path.join(S.OUT_DIR, "plan.png"))
    print(f"{len(solid_boxes)} solid boxes, {len(boundary_boxes)} boundary boxes, {len(tris) // 3} floor triangles, "
          f"{len(coins)} coins, {len(chevrons)} chevrons, floor at start {floor_at(sx, sy):.1f}")


if __name__ == "__main__":
    main()
