"""
Reconstruction step R3 (outside Unreal): the floor plan ("도면") of the deck as a parametric drawing, in Unreal cm.

  ~/.venvs/gs/bin/python -I layout.py

The automatic vectorisation of the scan (drawing.py) comes out broken where the scan is noisy, so the plan is
written the way a drafter would: from measurements. Every number below was read off the scan (profiles of the
paint in floor_ortho.png, the solid objects of objects.json); see README.md "재구성". What is regular (the stall
pitch, the column grid) is generated, what is not is listed.

Writes SourceAssets/ParkingStage/layout.json and layout.png (the plan, 2 cm/px, +X up) and layout_check.png
(the plan's paint outlines over the floor ortho).
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

# --- structure ------------------------------------------------------------------------------------------------
COLUMNS_X = [-3105 + 1032.5 * k for k in range(7)]   # column grid: 7 x 3, 10.33 m along the deck
COLUMNS_Y = [-780, -8, 770]
COLUMN = 60                                           # square, cm
SLAB = 330                                            # floor to slab underside
BEAM_DEPTH, BEAM_WIDTH = 55, 50
DECK = {"x0": -3640, "x1": 3780, "y0": -1330, "y1": 1500}   # walls stand on this outline (the scan's rails)
BAY = {"x0": 3780, "x1": 4250, "y0": 20, "y1": 840}           # far stall bay, open to the cross aisle
RAMP = {"x0": 3780, "x1": 4400, "y0": -760, "y1": 20}          # ramp down beside the bay (dark opening)
LOBBY = {"x0": -3640, "x1": -3060, "y0": -1330, "y1": -700}    # lift lobby corner (walled off, a door)

# --- paint ----------------------------------------------------------------------------------------------------
LINE = 12                                             # paint line width
# left stall row (stalls 2.5 m wide along X, 4.9 m deep): lines across it at these X, front line at Y = -766
LEFT_ROW = {"y0": -1250, "y1": -766, "lines_x": [-2950, -2646, -2388, -2098, -1856, -1610, -1358, -1066, -826, -576,
                                                    -330, -86, 204, 454, 704, 944, 1236, 1488, 1732, 1978, 2274,
                                                    2514, 2768, 3064, 3380]}
RED_LEFT = (-3100, 3480, -760, -660)                  # red walkway between the left row and the aisle
# middle block: two columns of stalls back to back, red frame around
ISLAND = {"x0": -2474, "x1": 3160, "y0": -106, "y1": 870, "mid_y": 382,
          "lines_x": [-2092, -1856, -1608, -1358, -1118, -824, -574, -322, -82, 210, 462, 704, 1008, 1244, 1492,
                      1740, 2040, 2276, 2526, 2774, 3014],
          "blue_x": (-2474, -2150)}                    # cross row of blue (accessible) stalls at the near end
RED_ISLAND = (-2590, 3270, -218, 982)                 # the frame: outer rectangle, the stall area is inside it
# near row (across the deck): lines along X at these Y
NEAR_ROW = {"x0": -3568, "x1": -3078, "lines_y": [-506, -280, -38, 258, 500, 734, 1024, 1266], "y0": -600, "y1": 1470}
HANDICAP = [(3072, 3368, -1250, -766), (-2942, -2648, -1250, -766), (-3568, -3078, -600, -292)]
EV = (-3568, -3078, 794, 1470)
BAY_LINES_Y = [270, 508, 750]
CROSSWALKS = [(-2560, -2300, -650, -228), (2990, 3150, -650, -228)]   # zebra: 45 cm bars along X
SPEED_BUMPS = [(206, 450, -660, -218), (206, 450, 982, 1500)]          # yellow/black, 3D
# arrows: centre x, y, yaw (direction of travel), length
ARROWS = [(849, -572, 0, 230), (687, -307, 0, 230), (-1591, -572, 0, 230), (-1757, -314, 180, 230),
          (857, 1071, 0, 230), (686, 1306, 180, 230), (-1588, 1066, 0, 230), (-1755, 1304, 180, 230),
          (2540, -561, 0, 230), (2367, 1193, 180, 230), (-2680, 360, -90, 230), (-2872, 360, 90, 230),
          (3280, 517, 90, 230)]

X1, Y0, CM = 4400.0, -1500.0, 2.0                     # floor_ortho.png


def stalls():
    """Every stall as (x0, x1, y0, y1, kind): kind normal / handicap / ev / bay"""
    out = []
    xs = LEFT_ROW["lines_x"]
    for a, b in zip(xs[:-1], xs[1:]):
        if b - a < 330:
            out.append((a, b, LEFT_ROW["y0"], LEFT_ROW["y1"], "normal"))
    for y0, y1 in ((ISLAND["y0"], ISLAND["mid_y"]), (ISLAND["mid_y"], ISLAND["y1"])):
        xs = ISLAND["lines_x"]
        for a, b in zip(xs[:-1], xs[1:]):
            if b - a < 330:
                out.append((a, b, y0, y1, "normal"))
    ys = NEAR_ROW["lines_y"]
    for a, b in zip(ys[:-1], ys[1:]):
        if b - a < 330:
            out.append((NEAR_ROW["x0"], NEAR_ROW["x1"], a, b, "ev" if a >= EV[2] - 5 else "normal"))
    for a, b in zip(BAY_LINES_Y[:-1], BAY_LINES_Y[1:]):
        out.append((BAY["x0"] + 60, BAY["x1"] - 40, a, b, "bay"))
    for h in HANDICAP:
        out.append((*h, "handicap"))
    out.append((*EV, "ev_area"))
    return out


def paint():
    """Paint shapes as polygons [(x, y)...] with a colour name"""
    shapes = []

    def rect(x0, x1, y0, y1, color):
        shapes.append({"color": color, "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]})

    def hline(x, y0, y1):        # line along Y at fixed X
        rect(x - LINE / 2, x + LINE / 2, y0, y1, "white")

    def vline(y, x0, x1):        # line along X at fixed Y
        rect(x0, x1, y - LINE / 2, y + LINE / 2, "white")

    # coloured areas first, lines on top
    rect(*RED_LEFT, "red")
    x0, x1, y0, y1 = RED_ISLAND
    w = 110
    rect(x0, x1, y0, y0 + w, "red")
    rect(x0, x1, y1 - w, y1, "red")
    rect(x0, x0 + w, y0, y1, "red")
    rect(x1 - w, x1, y0, y1, "red")
    for h in HANDICAP:
        rect(*h, "blue")
    rect(*EV, "green")
    bx = ISLAND["blue_x"]
    # left row
    for x in LEFT_ROW["lines_x"]:
        hline(x, LEFT_ROW["y0"], LEFT_ROW["y1"])
    vline(LEFT_ROW["y1"], LEFT_ROW["lines_x"][0], LEFT_ROW["lines_x"][-1])
    # island: outline, middle line, cross lines; blue stalls at the near end
    for y in (ISLAND["y0"], ISLAND["mid_y"], ISLAND["y1"]):
        vline(y, ISLAND["lines_x"][0], ISLAND["lines_x"][-1])
    for x in ISLAND["lines_x"]:
        hline(x, ISLAND["y0"], ISLAND["y1"])
    for k in range(5):
        y = ISLAND["y0"] + k * (ISLAND["y1"] - ISLAND["y0"]) / 4
        rect(bx[0], bx[1], y - LINE / 2, y + LINE / 2, "blue")
    rect(bx[0] - LINE / 2, bx[0] + LINE / 2, ISLAND["y0"], ISLAND["y1"], "blue")
    # near row
    for y in NEAR_ROW["lines_y"]:
        vline(y, NEAR_ROW["x0"], NEAR_ROW["x1"])
    hline(NEAR_ROW["x1"], NEAR_ROW["y0"], NEAR_ROW["y1"])
    # bay
    for y in BAY_LINES_Y:
        vline(y, BAY["x0"] + 60, BAY["x1"] - 40)
    hline(BAY["x0"] + 60, BAY_LINES_Y[0], BAY_LINES_Y[-1])
    # crosswalks: bars 45 cm wide, 45 cm gaps, running along X across the aisle
    for x0, x1, y0, y1 in CROSSWALKS:
        y = y0 + 20
        while y + 45 <= y1:
            rect(x0, x1, y, y + 45, "white")
            y += 90
    # arrows
    for x, y, yaw, length in ARROWS:
        shapes.append({"color": "white", "poly": arrow(x, y, yaw, length)})
    # handicap symbols are drawn in Unreal as a decal-like quad, only their centres here
    return shapes


def arrow(x, y, yaw, length, shaft=16, head=46, head_len=80):
    pts = [(-length / 2, -shaft / 2), (length / 2 - head_len, -shaft / 2), (length / 2 - head_len, -head / 2),
           (length / 2, 0), (length / 2 - head_len, head / 2), (length / 2 - head_len, shaft / 2), (-length / 2, shaft / 2)]
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in pts]


def wheelstops(stall_list):
    """A rubber stop 90 cm from the back of every normal stall"""
    out = []
    for x0, x1, y0, y1, kind in stall_list:
        if kind not in ("normal", "ev", "handicap", "bay"):
            continue
        if y1 - y0 > x1 - x0:        # deep along Y: back is the side away from the aisle
            back_y = y0 if abs(y0 - LEFT_ROW["y0"]) < 5 else (y1 if y1 <= ISLAND["mid_y"] + 1 and y0 >= ISLAND["y0"] - 1 and y1 == ISLAND["mid_y"] else None)
            if abs(y0 - LEFT_ROW["y0"]) < 5:
                yy = y0 + 90
            elif abs(y1 - ISLAND["mid_y"]) < 1:
                yy = y1 - 90
            elif abs(y0 - ISLAND["mid_y"]) < 1:
                yy = y0 + 90
            else:
                continue
            out.append({"center": [(x0 + x1) / 2, yy], "along": "x"})
        else:                        # near row and bay: deep along X
            xx = x0 + 90 if x0 < 0 else x1 - 90
            out.append({"center": [xx, (y0 + y1) / 2], "along": "y"})
    return out


def to_px(x, y):
    return (y - Y0) / CM, (X1 - x) / CM


def main():
    stall_list = stalls()
    shapes = paint()
    columns = [{"center": [x, y], "size": COLUMN} for x in COLUMNS_X for y in COLUMNS_Y]
    layout = {"deck": DECK, "bay": BAY, "ramp": RAMP, "lobby": LOBBY, "slab": SLAB,
              "beam": {"depth": BEAM_DEPTH, "width": BEAM_WIDTH}, "columns": columns,
              "columns_x": COLUMNS_X, "columns_y": COLUMNS_Y,
              "stalls": [list(s) for s in stall_list], "paint": shapes, "speed_bumps": SPEED_BUMPS,
              "wheelstops": wheelstops(stall_list),
              "aisles": {"left": (-3078, 3160, -660, -218), "right": (-3078, 3160, 982, 1500),
                         "near": (-3078, -2590, -660, 1500), "far": (3160, 3780, -660, 1500)}}
    json.dump(layout, open(os.path.join(S.OUT_DIR, "layout.json"), "w"))

    ortho = Image.open(os.path.join(S.OUT_DIR, "floor_ortho.png")).convert("RGB")
    W, H = ortho.size
    colors = {"white": (236, 236, 232), "red": (128, 42, 40), "blue": (34, 88, 176), "green": (46, 128, 72),
              "yellow": (232, 186, 24)}
    clean = Image.new("RGB", (W, H), (60, 60, 64))
    dr = ImageDraw.Draw(clean)
    P = lambda pts: [to_px(x, y) for x, y in pts]
    d = DECK
    dr.polygon(P([(d["x0"], d["y0"]), (d["x1"], d["y0"]), (d["x1"], d["y1"]), (d["x0"], d["y1"])]), fill=(120, 122, 124))
    b = BAY
    dr.polygon(P([(b["x0"], b["y0"]), (b["x1"], b["y0"]), (b["x1"], b["y1"]), (b["x0"], b["y1"])]), fill=(120, 122, 124))
    for s in shapes:
        dr.polygon(P(s["poly"]), fill=colors[s["color"]])
    for x0, x1, y0, y1 in SPEED_BUMPS:
        k = 0
        y = y0
        while y < y1:
            dr.polygon(P([(x0, y), (x1, y), (x1, min(y + 50, y1)), (x0, min(y + 50, y1))]), fill=(232, 186, 24) if k % 2 == 0 else (30, 30, 30))
            y += 50
            k += 1
    for w in layout["wheelstops"]:
        (cx, cy) = w["center"]
        a, bb = (8, 32) if w["along"] == "x" else (32, 8)
        a, bb = (8, 32) if w["along"] == "x" else (32, 8)
        dr.polygon(P([(cx - a, cy - bb), (cx + a, cy - bb), (cx + a, cy + bb), (cx - a, cy + bb)]), fill=(40, 40, 40))
    for c in columns:
        (cx, cy), h = c["center"], c["size"] / 2
        dr.polygon(P([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]), fill=(240, 240, 240), outline=(20, 20, 20))
    clean.save(os.path.join(S.OUT_DIR, "layout.png"))

    check = ortho.copy()
    dr = ImageDraw.Draw(check)
    for s in shapes:
        dr.polygon(P(s["poly"]), outline=(0, 255, 255))
    for c in columns:
        (cx, cy), h = c["center"], c["size"] / 2
        dr.polygon(P([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]), outline=(255, 255, 0))
    check.save(os.path.join(S.OUT_DIR, "layout_check.png"))
    print(len(stall_list), "stalls,", len(shapes), "paint shapes,", len(layout["wheelstops"]), "wheel stops")


if __name__ == "__main__":
    main()
