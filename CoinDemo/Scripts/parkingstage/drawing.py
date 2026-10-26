"""
Reconstruction step R2 (outside Unreal): the floor plan ("도면") of the deck, read from floor_ortho.png and the
solid objects, as clean vector shapes in Unreal cm. The CG rebuild (build_rebuild.py) draws everything from it.

  ~/.venvs/gs/bin/python -I drawing.py

  lines      white paint lines, snapped to the deck axes: runs of white pixels found with long horizontal and
             vertical openings, merged when collinear
  arrows     white arrows in the aisles: centre, direction (towards the wider head), length; redrawn from a clean
             template so they come out crisp
  areas      red walkway bands, blue handicap stalls, green EV stalls, yellow/black speed bumps: colour masks closed
             and simplified to right-angled polygons
  crosswalks bars of the zebra crossings (dull paint: a weaker contrast threshold inside the two crossings)
  pillars    the 21 scanned columns (objects.json blobs of 0.3-0.8 m2), squared to their measured size
  wheelstops orange-yellow rubber stops at the stall ends

Writes SourceAssets/ParkingStage/drawing.json and drawing.png (the plan drawn clean, 2 cm/px) and
drawing_check.png (the plan's outlines over the floor ortho, to verify against the scan).
"""

import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
CM = 2.0
X1, Y0 = 4400.0, -1500.0          # floor_ortho.png: X = X1 - row * CM, Y = Y0 + col * CM

# where markings are read (world cm): the playable deck and the far stall bay (plan.py's DECK_ADD / DECK_CUT)
READ_ADD = [(-3600, 3780, -1330, 1500), (3780, 4250, 100, 840)]
READ_CUT = [(-4000, -3040, -2000, -700), (3420, 4500, -2000, -760)]
CROSSWALKS = [(-2560, -2300, -660, -230), (3020, 3240, -660, -230)]   # zones searched for zebra bars (world cm)
EV_STALLS = (-3540, -3060, 870, 1470)                                 # green EV stalls, near row (read from the ortho)


def to_world(row, col):
    return X1 - row * CM, Y0 + col * CM


def to_px(x, y):
    return (X1 - x) / CM, (y - Y0) / CM


def rect_mask(shape, rects):
    m = np.zeros(shape, bool)
    for x0, x1, y0, y1 in rects:
        r0, c0 = to_px(x1, y0)
        r1, c1 = to_px(x0, y1)
        m[max(int(r0), 0):max(int(r1), 0), max(int(c0), 0):max(int(c1), 0)] = True
    return m


def runs(mask, horizontal, min_len_px):
    """Axis aligned line rectangles: opening with a long kernel along the axis, one rectangle per component."""
    k = np.ones((1, min_len_px) if horizontal else (min_len_px, 1), np.uint8)
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    out = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        sub = lab[y:y + h, x:x + w] == i
        if horizontal:
            prof = sub.sum(0)                   # thickness along the line
            rows = np.nonzero(sub)[0] + y
            centre, length = np.median(rows), w
            thick = np.median(prof[prof > 0])
            out.append(("h", centre, x, x + w, thick))
        else:
            prof = sub.sum(1)
            cols = np.nonzero(sub)[1] + x
            centre, length = np.median(cols), h
            thick = np.median(prof[prof > 0])
            out.append(("v", centre, y, y + h, thick))
    return out, m.astype(bool)


def merge(segs, gap_px=6, offset_px=3):
    """Joins collinear runs: same axis, centres within offset_px, gap below gap_px."""
    segs = sorted(segs, key=lambda s: (s[0], round(s[1] / offset_px), s[2]))
    out = []
    for s in segs:
        if out and out[-1][0] == s[0] and abs(out[-1][1] - s[1]) <= offset_px and s[2] - out[-1][3] <= gap_px:
            p = out[-1]
            out[-1] = (p[0], (p[1] + s[1]) / 2, p[2], max(p[3], s[3]), max(p[4], s[4]))
        else:
            out.append(s)
    return out


def orthogonal_polygons(mask, close_px, min_area_m2, eps_px=6):
    """Simplified polygons of a colour mask, with their edges snapped to the axes."""
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close_px, close_px), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for c in contours:
        if cv2.contourArea(c) * (CM / 100) ** 2 < min_area_m2:
            continue
        approx = cv2.approxPolyDP(c, eps_px, True)[:, 0, :].astype(float)
        # snap each edge to horizontal or vertical: alternate coordinates shared by neighbours
        pts = approx.copy()
        for k in range(len(pts)):
            a, b = pts[k], pts[(k + 1) % len(pts)]
            if abs(b[0] - a[0]) > abs(b[1] - a[1]):
                y = (a[1] + b[1]) / 2
                pts[k][1] = y
                pts[(k + 1) % len(pts)][1] = y
            else:
                x = (a[0] + b[0]) / 2
                pts[k][0] = x
                pts[(k + 1) % len(pts)][0] = x
        polys.append([list(map(float, to_world(p[1], p[0]))) for p in pts])
    return polys


def arrows(white, aisle):
    """Arrow components in the aisles: elongated, partly filled (head wider than the shaft)."""
    m = cv2.morphologyEx((white & aisle).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    out, used = [], np.zeros_like(white)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        long_, short = max(w, h) * CM, min(w, h) * CM
        if not (140 <= long_ <= 420 and 20 <= short <= 120 and 0.2 < area / (w * h) < 0.75):
            continue
        sub = lab[y:y + h, x:x + w] == i
        prof = sub.sum(1) if h > w else sub.sum(0)          # width along the arrow
        third = max(len(prof) // 3, 1)
        head_at_start = prof[:third].max() > prof[-third:].max()
        if h > w:   # along X (image rows): row 0 is +X
            yaw = 0.0 if head_at_start else 180.0
        else:       # along Y (image columns): col 0 is -Y
            yaw = -90.0 if head_at_start else 90.0
        cx, cy = to_world(cen[i][1], cen[i][0])
        out.append({"center": [float(cx), float(cy)], "yaw": yaw, "length": float(long_),
                    "head": float(prof.max() * CM)})
        used[y:y + h, x:x + w] |= sub
    return out, used


def main():
    img = np.asarray(Image.open(os.path.join(S.OUT_DIR, "floor_ortho.png")).convert("RGB")).astype(np.float32) / 255
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    lum = img.mean(2)
    sat = img.max(2) - img.min(2)
    bg = cv2.medianBlur((lum * 255).astype(np.uint8), 31).astype(np.float32) / 255
    deck = rect_mask(lum.shape, READ_ADD) & ~rect_mask(lum.shape, READ_CUT)

    white = (lum - bg > 0.12) & (sat < 0.12) & (lum > 0.35) & deck
    yellow = (r > 0.4) & (g > 0.3) & (b < 0.25) & (r - b > 0.22) & (g - b > 0.12) & deck
    blue = (b - r > 0.08) & (b > 0.25) & deck
    red = (r - g > 0.04) & (r - b > 0.04) & (lum < 0.4) & ~yellow & deck
    orange = (r > 0.45) & (g > 0.22) & (g < 0.5) & (b < 0.2) & (r - g > 0.15)

    objects = json.load(open(os.path.join(S.OUT_DIR, "objects.json")))
    pillars = []
    for o in objects["objects"]:
        x0, y0, x1, y1 = o["box"]
        if 0.3 <= o["area"] <= 0.8 and o["fill"] > 0.8 and max(x1 - x0, y1 - y0) < 110:
            cx, cy, size = (x0 + x1) / 2, (y0 + y1) / 2, round(max(x1 - x0, y1 - y0) / 10) * 10
            pillars.append({"center": [cx, cy], "size": size})

    # aisles (no stall grid): where arrows are looked for
    aisle = rect_mask(lum.shape, [(-3000, 3150, -660, -220), (-3000, 3150, 900, 1480), (-2950, -2350, -660, 1480),
                                  (3150, 3780, -660, 1480)])
    arrow_list, arrow_px = arrows(white, aisle)

    segs = []
    lw = white & ~ndimage_dilate(arrow_px, 3)
    for horizontal in (True, False):
        found, _ = runs(lw, horizontal, 25)
        segs += found
    segs = merge(segs)
    lines = []
    for axis, centre, a, b_, thick in segs:
        t = max(thick * CM, 8.0)
        if axis == "h":         # along Y at a fixed X (image row)
            x = X1 - centre * CM
            y0_, y1_ = Y0 + a * CM, Y0 + b_ * CM
            if y1_ - y0_ < 60:
                continue
            lines.append({"a": [x, y0_], "b": [x, y1_], "width": round(t, 1)})
        else:
            y = Y0 + centre * CM
            x0_, x1_ = X1 - b_ * CM, X1 - a * CM
            if x1_ - x0_ < 60:
                continue
            lines.append({"a": [x0_, y], "b": [x1_, y], "width": round(t, 1)})

    # zebra bars: weaker contrast, only inside the known crossings
    zebra = (lum - bg > 0.04) & rect_mask(lum.shape, CROSSWALKS)
    zebra = cv2.morphologyEx(zebra.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(zebra)
    bars = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area * (CM / 100) ** 2 < 0.25:
            continue
        xa, ya = to_world(y + h, x)
        xb, yb = to_world(y, x + w)
        bars.append([float(xa), float(ya), float(xb), float(yb)])

    # wheel stops: orange-yellow rubber, 40-90 cm long
    n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.morphologyEx(orange.astype(np.uint8) & deck.astype(np.uint8),
                                                                        cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)))
    stops = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        long_, short = max(w, h) * CM, min(w, h) * CM
        if 30 <= long_ <= 100 and short <= 30:
            cx, cy = to_world(cen[i][1], cen[i][0])
            stops.append({"center": [float(cx), float(cy)], "along": "x" if h > w else "y"})

    drawing = {
        "lines": lines, "arrows": arrow_list, "crosswalk_bars": bars, "pillars": pillars, "wheelstops": stops,
        "red": orthogonal_polygons(red, 15, 1.0), "blue": orthogonal_polygons(blue, 9, 0.8),
        "yellow": orthogonal_polygons(yellow, 5, 0.25, eps_px=3),
        "ev_stalls": EV_STALLS,
    }
    json.dump(drawing, open(os.path.join(S.OUT_DIR, "drawing.json"), "w"))
    print({k: len(v) for k, v in drawing.items() if isinstance(v, list)})
    render(drawing, lum.shape, img)


def ndimage_dilate(m, it):
    return cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=it).astype(bool)


def arrow_polygon(a):
    """Standard road arrow: shaft + triangular head, along +local x, centred."""
    L, H = a["length"], max(a["head"], 45.0)
    shaft = 15.0
    head_len = min(L * 0.38, 110.0)
    pts = [(-L / 2, -shaft / 2), (L / 2 - head_len, -shaft / 2), (L / 2 - head_len, -H / 2), (L / 2, 0),
           (L / 2 - head_len, H / 2), (L / 2 - head_len, shaft / 2), (-L / 2, shaft / 2)]
    c, s = math.cos(math.radians(a["yaw"])), math.sin(math.radians(a["yaw"]))
    return [(a["center"][0] + x * c - y * s, a["center"][1] + x * s + y * c) for x, y in pts]


def render(d, shape, ortho):
    H, W = shape
    clean = Image.new("RGB", (W, H), (118, 120, 122))
    check = Image.fromarray((np.clip(ortho, 0, 1) * 255).astype(np.uint8))
    for im, outline in ((clean, None), (check, True)):
        dr = ImageDraw.Draw(im)
        P = lambda pts: [(to_px(x, y)[1], to_px(x, y)[0]) for x, y in pts]
        col = lambda c: None if outline else c
        out = lambda c: c if outline else None
        for poly in d["red"]:
            dr.polygon(P(poly), fill=col((120, 40, 38)), outline=out((255, 60, 60)))
        for poly in d["blue"]:
            dr.polygon(P(poly), fill=col((35, 85, 170)), outline=out((80, 140, 255)))
        x0, x1, y0, y1 = d["ev_stalls"]
        dr.polygon(P([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), fill=col((50, 120, 70)), outline=out((80, 255, 120)))
        for poly in d["yellow"]:
            dr.polygon(P(poly), fill=col((230, 180, 20)), outline=out((255, 230, 0)))
        for l in d["lines"]:
            (ax, ay), (bx, by), w = l["a"], l["b"], l["width"]
            if ax == bx:
                pts = [(ax - w / 2, ay), (ax + w / 2, ay), (ax + w / 2, by), (ax - w / 2, by)]
            else:
                pts = [(ax, ay - w / 2), (bx, ay - w / 2), (bx, ay + w / 2), (ax, ay + w / 2)]
            dr.polygon(P(pts), fill=col((235, 235, 230)), outline=out((0, 255, 255)))
        for bar in d["crosswalk_bars"]:
            dr.polygon(P([(bar[0], bar[1]), (bar[2], bar[1]), (bar[2], bar[3]), (bar[0], bar[3])]),
                       fill=col((225, 225, 220)), outline=out((255, 0, 255)))
        for a in d["arrows"]:
            dr.polygon(P(arrow_polygon(a)), fill=col((235, 235, 230)), outline=out((255, 128, 0)))
        for p in d["pillars"]:
            (cx, cy), s = p["center"], p["size"] / 2
            dr.polygon(P([(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s)]),
                       fill=col((200, 200, 200)), outline=out((255, 255, 0)))
        for w in d["wheelstops"]:
            (cx, cy) = w["center"]
            a, b = (30, 8) if w["along"] == "x" else (8, 30)
            dr.polygon(P([(cx - a, cy - b), (cx + a, cy - b), (cx + a, cy + b), (cx - a, cy + b)]),
                       fill=col((40, 40, 40)), outline=out((255, 140, 0)))
    clean.save(os.path.join(S.OUT_DIR, "drawing.png"))
    check.save(os.path.join(S.OUT_DIR, "drawing_check.png"))


if __name__ == "__main__":
    main()
