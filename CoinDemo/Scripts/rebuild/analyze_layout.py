"""
Phase 1 of the stage rebuild: an approximate floor plan of the street canyon, from the scan.

The scan was filmed walking along one street, so what it captures well is that street's two walls of shop fronts.
The plan models exactly that, and leaves the rest to the scan:

  * walkable area: the collision floor's open cells reachable from the start         [measured]
  * centre line of the main street, per metre along its axis                           [measured]
  * facade lines: walking out from the centre line, where wall-like splats (flat, facing sideways, 3-10 m up:
    above cars, people and awnings, and not tree crowns) first get dense. Per metre and side, then made
    piecewise straight (runs of near equal offset), parallel to the street axis            [measured]
  * openings: no wall within reach (cross streets, alleys, the ends of the capture): kept as scan [measured]
  * facade height per metre: where most of the opacity behind the facade line ends   [measured, rough]
  * building depth behind the facade: not in the scan                                  [estimated: DEPTH]

Output: generated/<Name>_layout.json (Unreal metres) and generated/<Name>_plan.svg / _plan.png (+X up).

  python analyze_layout.py Hongdae
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

from common import GENERATED_DIR, Scan, ground_grid, load_collision

CELL = 0.5              # collision grid, metres
FINE = 0.25             # facade search grid, metres
STEP = 1.0              # facade profile step along the street, metres
WALL_BAND = (3.0, 10.0) # height band whose wall-like splats mark the facades, metres above the ground
WALL_DENSITY = 25.0     # summed opacity per square metre of wall-like splats in that band that makes a wall
REACH = 18.0            # farthest a facade can be from the centre line, metres
RUN_TOLERANCE = 0.6     # metres a facade may wander and still be one straight run
MIN_RUN = 2.0           # shorter runs merge into a neighbour, metres
BEHIND = (-0.3, 3.0)    # splats this far behind the facade line count for its height
SKY_MASS = 0.95
MIN_MASS = 3.0
HEIGHT_TOLERANCE = 1.5  # metres the roof line may wander within one height step
DEPTH = 8.0             # assumed building depth, metres (not captured), shortened to keep coins outside
MIN_DEPTH = 1.5         # facades with a coin or course piece closer behind them are dropped


def walkable_area(collision, lo, height, walls):
    open_cells = ~np.isnan(height) & ~walls
    start = np.floor((np.array(collision["start"][:2]) / 100.0 - lo) / CELL).astype(int)
    labels, _ = ndimage.label(open_cells)
    area = labels == labels[start[0], start[1]]
    return ndimage.binary_closing(area, iterations=2) & ~np.isnan(height)


def wall_density(scan, lo, height, shape):
    valid = np.argwhere(~np.isnan(height))
    _, k = cKDTree(valid).query((scan.pos[:, :2] - lo) / CELL)
    above = scan.pos[:, 2] - height[valid[k, 0], valid[k, 1]]
    normal, flatness = scan.normals()
    wall_like = (above > WALL_BAND[0]) & (above < WALL_BAND[1]) & (flatness < 0.3) & (np.abs(normal[:, 2]) < 0.35)
    ij = np.floor((scan.pos[wall_like, :2] - lo) / FINE).astype(int)
    ok = (ij >= 0).all(1) & (ij[:, 0] < shape[0]) & (ij[:, 1] < shape[1])
    density = np.zeros(shape)
    np.add.at(density, (ij[ok, 0], ij[ok, 1]), scan.opacity[wall_like][ok])
    return ndimage.gaussian_filter(density / FINE ** 2, 1.0)


def runs(xs, offsets):
    """Splits a per-metre facade offset profile (NaN = opening) into straight runs [x0, x1, offset]."""
    result = []
    i = 0
    while i < len(xs):
        if np.isnan(offsets[i]):
            i += 1
            continue
        j = i
        while j + 1 < len(xs) and not np.isnan(offsets[j + 1]) and abs(offsets[j + 1] - np.median(offsets[i:j + 1])) < RUN_TOLERANCE:
            j += 1
        result.append([xs[i] - STEP / 2, xs[j] + STEP / 2, float(np.median(offsets[i:j + 1]))])
        i = j + 1
    # short runs take the offset of the longer neighbour they touch (or go), then equal neighbours merge
    changed = True
    while changed:
        changed = False
        for k, (x0, x1, _) in enumerate(result):
            if x1 - x0 >= MIN_RUN:
                continue
            touching = [n for n in (k - 1, k + 1) if 0 <= n < len(result) and
                        (abs(result[n][1] - x0) < 1e-6 or abs(result[n][0] - x1) < 1e-6)]
            if touching:
                result[k][2] = result[max(touching, key=lambda n: result[n][1] - result[n][0])][2]
            else:
                result.pop(k)
            changed = True
            break
        merged = []
        for r in result:
            if merged and abs(merged[-1][1] - r[0]) < 1e-6 and abs(merged[-1][2] - r[2]) < 1e-6:
                merged[-1][1] = r[1]
            else:
                merged.append(r)
        result = merged
    return result


def height_steps(stations):
    """Roof line as steps [x0, x1, top]: runs of stations within HEIGHT_TOLERANCE, gaps filled from neighbours."""
    known = [st for st in stations if st["top"] is not None]
    if not known:
        return []
    xs = np.array([st["x"] for st in stations])
    tops = np.interp(xs, [st["x"] for st in known], [st["top"] for st in known])
    steps = []
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and abs(tops[j + 1] - np.median(tops[i:j + 1])) < HEIGHT_TOLERANCE:
            j += 1
        steps.append([round(float(xs[i] - STEP / 2), 2), round(float(xs[j] + STEP / 2), 2), round(float(np.median(tops[i:j + 1])), 2)])
        i = j + 1
    return steps


def main(name):
    collision = load_collision(name)
    lo, height, walls = ground_grid(collision, CELL)
    area = walkable_area(collision, lo, height, walls)
    scan = Scan(name)
    shape = np.ceil(np.array(height.shape) * CELL / FINE).astype(int)
    density = wall_density(scan, lo, height, shape)
    valid = np.argwhere(~np.isnan(height))
    ground_tree = cKDTree(valid)

    # the main street runs along X: its centre line from the walkable cells near the start's line
    start = np.array(collision["start"][:2]) / 100.0
    cells = np.argwhere(area)
    cell_xy = lo + (cells + 0.5) * CELL
    xs = np.arange(cell_xy[:, 0].min() + STEP / 2, cell_xy[:, 0].max(), STEP)
    centre = np.full(len(xs), np.nan)
    for k, x in enumerate(xs):
        row = cell_xy[(np.abs(cell_xy[:, 0] - x) < STEP / 2) & (np.abs(cell_xy[:, 1] - start[1]) < 10.0)]
        if len(row):
            centre[k] = np.median(row[:, 1])
    known = ~np.isnan(centre)
    centre = np.interp(xs, xs[known], ndimage.median_filter(centre[known], 9))

    course = collision.get("course", {})
    items = [np.array(p[:2]) / 100.0 for p in collision["coins"] + [collision["start"]] + course.get("coins", []) +
             [p[:3] for p in course.get("platforms", [])] + [p[:3] for p in course.get("jumpPads", [])] +
             [g[0][:3] for g in course.get("smashWalls", [])] + ([course["gem"]] if course.get("gem") else [])]
    facades, profiles = [], {}
    tree = cKDTree(scan.pos[:, :2])
    for side in (+1, -1):
        offsets = np.full(len(xs), np.nan)
        for k, (x, c) in enumerate(zip(xs, centre)):
            i = int((x - lo[0]) / FINE)
            for y in np.arange(0.0, REACH, FINE):
                j = int((c + side * y - lo[1]) / FINE)
                if not (0 <= i < shape[0] and 0 <= j < shape[1]):
                    break
                if density[i, j] > WALL_DENSITY:
                    offsets[k] = c + side * y  # absolute Y of the facade
                    break
        profiles[side] = offsets
        for x0, x1, y in runs(xs, offsets):
            # height samples every metre along the run, from the splats just behind it
            stations = []
            for x in np.arange(x0 + STEP / 2, x1, STEP):
                near = np.array(tree.query_ball_point([x, y + side * 1.5], r=2.0), int)
                rel = scan.pos[near, :2] - [x, y]
                u, d = rel[:, 0], rel[:, 1] * side
                _, g = ground_tree.query(([x, y] - lo) / CELL)
                floor = float(height[valid[g, 0], valid[g, 1]])
                z = scan.pos[near, 2] - floor
                pick = (np.abs(u) < STEP / 2) & (d > BEHIND[0]) & (d < BEHIND[1]) & (z > 0.0) & (z < 60.0)
                mass = scan.opacity[near][pick]
                top = None
                if mass.sum() >= MIN_MASS:
                    order = np.argsort(z[pick])
                    cumulative = np.cumsum(mass[order])
                    top = round(float(z[pick][order][np.searchsorted(cumulative, SKY_MASS * cumulative[-1])]), 2)
                stations.append({"x": round(float(x), 2), "floor": round(floor, 2), "top": top, "mass": round(float(mass.sum()), 1)})
            # the buildings get collision: they may not swallow a coin, the start or a course piece
            depth = DEPTH
            for p in items:
                along = x0 - 0.5 <= p[0] <= x1 + 0.5
                behind = (p[1] - y) * side
                if along and -0.5 < behind < depth + 1.0:
                    depth = min(depth, behind - 1.0)
            if depth < MIN_DEPTH:
                continue  # something to reach stands right behind this line: not a closed building front
            facades.append({"side": side, "x0": round(float(x0), 2), "x1": round(float(x1), 2), "y": round(float(y), 3),
                            "depth": round(float(depth), 2), "stations": stations, "heights": height_steps(stations)})

    tops = [st["top"] for f in facades for st in f["stations"] if st["top"] is not None]
    total = sum(f["x1"] - f["x0"] for f in facades)
    print(f"{name}: street {xs[0]:.0f}..{xs[-1]:.0f} m along X, {len(facades)} facade runs ({total:.0f} m), "
          f"heights {np.percentile(tops, 10):.1f}-{np.percentile(tops, 90):.1f} m (p10-p90), "
          f"{int(np.isnan(profiles[1]).sum() + np.isnan(profiles[-1]).sum())} of {2 * len(xs)} side-metres open")

    layout = {
        "stage": name,
        "units": "metres, Unreal axes (X along the street, Z up), heights above the collision floor",
        "provenance": {
            "centre": "measured: median of the walkable cells along the street",
            "facades": "measured: first dense wall-like splats 3-10 m up, then straightened (piecewise, parallel to X)",
            "openings": "measured: no wall within reach; left to the scan",
            "heights": "measured, rough: top of the opacity behind the facade (null = too little seen)",
            "depth": f"estimated: up to {DEPTH} m (not captured), shortened so no coin or course piece ends up inside",
            "roofs, backs, sides": "estimated: flat roofs, plain walls",
        },
        "axis": "X",
        "centre": {"x": xs.round(2).tolist(), "y": centre.round(3).tolist()},
        "facades": facades,
        "depth": DEPTH,
        "walkable_cells": {"lo": lo.round(3).tolist(), "cell": CELL, "cells": cells.tolist()},
        "start": collision["start"],
        "coins": collision["coins"],
    }
    with open(os.path.join(GENERATED_DIR, f"{name}_layout.json"), "w") as f:
        json.dump(layout, f)
    draw_plan(name, layout, lo, height.shape, area)


def draw_plan(name, layout, lo, shape, area):
    """SVG (editable) and PNG plan, +X up: walkable grey, facades coloured by height, centre line dashed."""
    px = 8.0
    w, h = shape[1] * CELL * px, shape[0] * CELL * px
    to = lambda x, y: ((y - lo[1]) * px, h - (x - lo[0]) * px)

    def colour(top):
        t = min(top / 25.0, 1.0)
        return (int(255 * t), int(80 + 120 * (1 - t)), int(255 * (1 - t)))

    image = Image.new("RGB", (int(w), int(h)), (27, 27, 31))
    draw = ImageDraw.Draw(image)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" style="background:#1b1b1f">',
           f'<!-- {name} street plan from the scan. grey: walkable (measured). lines: facades coloured by height '
           f'(blue low, red 25 m+), tinted boxes: building depth (estimated). dashed: centre line. yellow: coins. +X is up. -->']
    for i, j in np.argwhere(area):
        x, y = lo + np.array([i, j]) * CELL
        (x1, y1), (x2, y2) = to(x + CELL, y), to(x, y + CELL)
        draw.rectangle((x1, y1, x2, y2), fill=(58, 58, 66))
        svg.append(f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{x2 - x1:.1f}" height="{y2 - y1:.1f}" fill="#3a3a42"/>')
    pts = [to(x, y) for x, y in zip(layout["centre"]["x"], layout["centre"]["y"])]
    draw.line(pts, fill=(120, 120, 120), width=1)
    svg.append('<polyline points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '" fill="none" stroke="#777" stroke-dasharray="4 4"/>')
    for f in layout["facades"]:
        for x0, x1, top in f["heights"]:
            c = colour(top)
            hexc = "#%02x%02x%02x" % c
            (ax, ay), (bx, by) = to(x1, f["y"]), to(x0, f["y"] + f["side"] * f["depth"])
            draw.rectangle((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)), fill=(c[0] // 4 + 40, c[1] // 4 + 30, c[2] // 4 + 30))
            draw.line([to(x0, f["y"]), to(x1, f["y"])], fill=c, width=4)
            svg.append(f'<rect x="{min(ax, bx):.1f}" y="{min(ay, by):.1f}" width="{abs(bx - ax):.1f}" height="{abs(by - ay):.1f}" fill="{hexc}" fill-opacity="0.25"/>')
            (lx1, ly1), (lx2, ly2) = to(x0, f["y"]), to(x1, f["y"])
            svg.append(f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" x2="{lx2:.1f}" y2="{ly2:.1f}" stroke="{hexc}" stroke-width="4"><title>{top:.1f} m</title></line>')
    for c in layout["coins"]:
        x, y = to(c[0] / 100.0, c[1] / 100.0)
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 210, 31))
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ffd21f"/>')
    svg.append("</svg>")
    with open(os.path.join(GENERATED_DIR, f"{name}_plan.svg"), "w") as f:
        f.write("\n".join(svg))
    image.save(os.path.join(GENERATED_DIR, f"{name}_plan.png"))


for stage in sys.argv[1:] or ["Hongdae"]:
    main(stage)
