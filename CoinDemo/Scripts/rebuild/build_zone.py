"""
Rebuilds one zone of a scan stage as finished game geometry, outside Unreal (see zones/<Stage>_<Zone>.json).

Ground
  * domain: the walkable ground of the zone (collision floor open cells), plus the hand-measured sidewalks
  * road: the domain minus the sidewalks, triangulated on a 0.5 m grid with exact polygon edges, heights from the
    collision floor. Material zones and markings go into a control texture (2.5 cm/px): red pavement beyond
    red_road_from_x, white and yellow paint extracted from the scan's top-down orthophoto
  * sidewalks: raised sidewalk_height above the road with real curb faces
  * manholes: round and square covers at the measured spots
Building (the zone's hero building)
  * modelled storey by storey from measurements on its baked facade photos: storefront cladding, glass with
    frames and mullions, plaster and brick walls, two corrugated awnings, a mansard roof with dormers
  * the shop signs and the poster are cropped from the facade photos (the scan's own imagery); the glass shows the
    facade photo projected onto it (what the scan saw through and on the glass) under a glossy finish; everything
    else is tiling PBR material (CC0, SourceAssets/Textures/pbr)
Scan
  * the splats replaced by the ground (a band around the floor) and by the building are removed

Output in ../../SourceAssets/Rebuilt/<Stage>_<Zone>/: meshes.json, control.png, sign_*.png, <Stage>_<Zone>.ply,
zone.json (placements, counts) and plan.png (what is mesh, what stays scan).

  python build_zone.py Hongdae_A
"""

import json
import os
import sys
import time

import numpy as np
import shapely
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, box as shapely_box
from shapely.ops import unary_union

import meshkit
from common import GENERATED_DIR, OUT_DIR, Scan, ground_grid, load_collision, write_ply

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets"))
CONTROL_RES = 0.025
GROUND_BAND = (-3.0, 0.35)      # splats this far below / above the floor belong to the ground
SIDEWALK_BAND_TOP = 0.5


class Floor:
    """Bilinear height of the collision floor (metres)."""

    def __init__(self, collision):
        self.lo, self.height, _ = ground_grid(collision, 0.5)
        valid = ~np.isnan(self.height)
        idx = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
        self.filled = self.height[idx[0], idx[1]]

    def __call__(self, xy):
        xy = np.atleast_2d(xy)
        g = (xy - self.lo) / 0.5
        i0 = np.clip(np.floor(g[:, 0]).astype(int), 0, self.filled.shape[0] - 2)
        j0 = np.clip(np.floor(g[:, 1]).astype(int), 0, self.filled.shape[1] - 2)
        fx, fy = np.clip(g[:, 0] - i0, 0, 1), np.clip(g[:, 1] - j0, 0, 1)
        h = self.filled
        return ((h[i0, j0] * (1 - fx) + h[i0 + 1, j0] * fx) * (1 - fy) + (h[i0, j0 + 1] * (1 - fx) + h[i0 + 1, j0 + 1] * fx) * fy)


class Surface:
    """The ground of the zone as a smooth height field: the collision floor over the zone, median filtered over
    MEDIAN metres (drops bumps where the ground mesh was draped over kerbs, steps and objects) and then gaussian
    smoothed (no scan noise left in the surface), sampled bilinearly. Real slopes and level changes over more than a
    few metres stay. (A single cubic polynomial couldn't follow them: a third of the zone was more than 9 cm off.)"""

    MEDIAN, SIGMA, CELL = 3.0, 1.0, 0.25

    def __init__(self, floor, region):
        minx, miny, maxx, maxy = region.buffer(3.0).bounds
        self.lo = np.array([minx, miny])
        xs, ys = np.arange(minx, maxx, self.CELL), np.arange(miny, maxy, self.CELL)
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        z = floor(np.column_stack([gx.ravel(), gy.ravel()])).reshape(gx.shape)
        z = ndimage.median_filter(z, size=int(self.MEDIAN / self.CELL))
        self.grid = ndimage.gaussian_filter(z, self.SIGMA / self.CELL)
        inside = shapely.contains_xy(region, gx, gy)
        residual = (floor(np.column_stack([gx[inside], gy[inside]])) - self.grid[inside])
        self.stats = {"p50": float(np.percentile(np.abs(residual), 50)), "p95": float(np.percentile(np.abs(residual), 95)),
                      "max_above": float(residual.max())}

    def __call__(self, xy):
        g = (np.atleast_2d(xy) - self.lo) / self.CELL
        i0 = np.clip(np.floor(g[:, 0]).astype(int), 0, self.grid.shape[0] - 2)
        j0 = np.clip(np.floor(g[:, 1]).astype(int), 0, self.grid.shape[1] - 2)
        fx, fy = np.clip(g[:, 0] - i0, 0, 1), np.clip(g[:, 1] - j0, 0, 1)
        h = self.grid
        return (h[i0, j0] * (1 - fx) + h[i0 + 1, j0] * fx) * (1 - fy) + (h[i0, j0 + 1] * (1 - fx) + h[i0 + 1, j0 + 1] * fx) * fy


def walkable_polygon(name, box):
    """The stage's walkable area (analyze_layout.py) as a smooth polygon, clipped to the zone."""
    layout = json.load(open(os.path.join(GENERATED_DIR, f"{name}_layout.json")))
    lo = np.array(layout["walkable_cells"]["lo"])
    cell = layout["walkable_cells"]["cell"]
    cells = np.array(layout["walkable_cells"]["cells"])
    shape = cells.max(0) + 3
    mask = np.zeros(shape, bool)
    mask[cells[:, 0], cells[:, 1]] = True
    fine = ndimage.zoom(mask.astype(float), 5, order=1) > 0.5
    fine = ndimage.gaussian_filter(fine.astype(float), 2.0) > 0.5
    from skimage import measure
    polys = []
    for ring in measure.find_contours(np.pad(fine, 1).astype(float), 0.5):
        p = Polygon(lo + (ring - 1 + 0.5) * cell / 5).buffer(0)
        if p.area > 1.0:
            polys.append(p)
    area = unary_union(polys).simplify(0.1)
    return area.intersection(shapely_box(box[0], box[2], box[1], box[3]))


def triangulate(region, cell=0.5):
    """Triangles of a (multi)polygon with exact edges, split on a cell grid so heights can vary inside."""
    tris = []
    minx, miny, maxx, maxy = region.bounds
    for x in np.arange(np.floor(minx / cell) * cell, maxx, cell):
        for y in np.arange(np.floor(miny / cell) * cell, maxy, cell):
            piece = region.intersection(shapely_box(x, y, x + cell, y + cell))
            if piece.is_empty or piece.area < 1e-5:
                continue
            polys = [g for g in getattr(piece, "geoms", [piece]) if g.geom_type == "Polygon" and g.area > 1e-5]
            for poly in polys:
                for t in shapely.constrained_delaunay_triangles(poly).geoms:
                    tri = np.array(t.exterior.coords)[:3]
                    # counter-clockwise seen from above
                    if (tri[1, 0] - tri[0, 0]) * (tri[2, 1] - tri[0, 1]) - (tri[1, 1] - tri[0, 1]) * (tri[2, 0] - tri[0, 0]) < 0:
                        tri = tri[[0, 2, 1]]
                    tris.append(tri)
    return np.array(tris)


def ground_meshes(plan, floor, domain, sidewalks):
    """floor: the smooth fitted Surface. The road blocks the player too, so feet stay on what is drawn."""
    road = domain.difference(unary_union(list(sidewalks.values())))
    road_mesh = meshkit.Mesh("SM_Zone_Road", collision="complex")
    tris = triangulate(road)
    pts, inverse = np.unique(np.round(tris.reshape(-1, 2), 4), axis=0, return_inverse=True)
    z = floor(pts)
    # ccw from above; Unreal's front face normal (c - a) x (b - a) points up for (a, c, b)
    road_mesh.merge_grid(np.column_stack([pts, z + 0.01]), pts, inverse.reshape(-1, 3)[:, [0, 2, 1]], "Road")

    walk_mesh = meshkit.Mesh("SM_Zone_Sidewalks", collision="complex")
    h = plan["sidewalk_height"]
    for name, poly in sidewalks.items():
        tris = triangulate(poly)
        pts, inverse = np.unique(np.round(tris.reshape(-1, 2), 4), axis=0, return_inverse=True)
        walk_mesh.merge_grid(np.column_stack([pts, floor(pts) + h + 0.01]), pts, inverse.reshape(-1, 3)[:, [0, 2, 1]], "Sidewalk")
        # curb: a vertical face down to the road along every edge of the sidewalk
        for ring in [poly.exterior] + list(poly.interiors):
            coords = np.array(ring.coords)
            for a, b in zip(coords[:-1], coords[1:]):
                length = np.linalg.norm(b - a)
                steps = max(1, int(np.ceil(length / 0.5)))
                for k in range(steps):
                    p = a + (b - a) * k / steps
                    q = a + (b - a) * (k + 1) / steps
                    mid = (p + q) / 2
                    normal = np.array([q[1] - p[1], -(q[0] - p[0])]) / max(np.linalg.norm(q - p), 1e-9)
                    if poly.contains(shapely.Point(*(mid + normal * 0.05))):
                        normal = -normal
                    zp, zq = floor(p)[0], floor(q)[0]
                    outward = [normal[0], normal[1], 0.0]
                    walk_mesh.quad([p[0], p[1], zp - 0.05], [q[0], q[1], zq - 0.05], [q[0], q[1], zq + h + 0.01], [p[0], p[1], zp + h + 0.01], outward, "Curb")
                    # rounded top edge of the curb stone: a 4 cm chamfer strip
                    inner_p, inner_q = p - normal * 0.12, q - normal * 0.12
                    walk_mesh.quad([p[0], p[1], zp + h + 0.01], [q[0], q[1], zq + h + 0.01], [inner_q[0], inner_q[1], zq + h + 0.012], [inner_p[0], inner_p[1], zp + h + 0.012], [0, 0, 1], "Curb")

    cover_mesh = meshkit.Mesh("SM_Zone_Manholes")
    for m in plan["manholes"]:
        c = np.array([m["x"], m["y"]])
        z = floor(c)[0] + 0.018
        if m["kind"] == "round":
            n = 24
            ring = [c + m["r"] * np.array([np.cos(a), np.sin(a)]) for a in np.linspace(0, 2 * np.pi, n + 1)[:-1]]
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                uv = lambda p: [(p[0] - c[0]) / (2 * m["r"]) + 0.5, (p[1] - c[1]) / (2 * m["r"]) + 0.5]
                cover_mesh.triangle([c[0], c[1], z], [a[0], a[1], z], [b[0], b[1], z], [0, 0, 1], "ManholeRound",
                                    [uv(c), uv(a), uv(b)])
        else:
            hx, hy = m["sx"] / 2, m["sy"] / 2
            cover_mesh.quad([c[0] - hx, c[1] - hy, z], [c[0] + hx, c[1] - hy, z], [c[0] + hx, c[1] + hy, z], [c[0] - hx, c[1] + hy, z],
                            [0, 0, 1], "ManholeSquare", [[0, 0], [1, 0], [1, 1], [0, 1]])
    return [road_mesh, walk_mesh, cover_mesh], road


def control_texture(plan, road, sidewalk_union, out):
    """RGB control map over the zone box: R red pavement, G white paint, B yellow paint (2.5 cm/px)."""
    x0, x1, y0, y1 = plan["box"]
    info = json.load(open(os.path.join(SOURCE, "RoadLayers", f"{plan['stage']}_road.json")))
    ox, oy = [v / 100 for v in info["origin"]]
    sx, sy = [v / 100 for v in info["size"]]
    photo = np.asarray(Image.open(os.path.join(SOURCE, "RoadLayers", f"{plan['stage']}_road.png")).convert("RGB"), float) / 255
    ph, pw, _ = photo.shape
    xs = np.arange(x0, x1, CONTROL_RES) + CONTROL_RES / 2
    ys = np.arange(y0, y1, CONTROL_RES) + CONTROL_RES / 2
    a = photo[((ys - oy) / sy * ph).astype(int)][:, ((xs - ox) / sx * pw).astype(int)]   # [y, x]
    luma = a @ [0.3, 0.59, 0.11]
    saturation = (a.max(2) - a.min(2)) / np.maximum(a.max(2), 1e-3)
    background = ndimage.median_filter(luma, size=41)
    white = (luma - background > 0.14) & (saturation < 0.2)
    yellow = (a[..., 0] - a[..., 2] > 0.18) & (a[..., 1] - a[..., 2] > 0.08) & (luma > 0.3)
    gx, gy = np.meshgrid(xs, ys)
    on_road = shapely.contains_xy(road.buffer(-0.05), gx, gy)
    # paint as vector shapes: every painted mark found in the orthophoto becomes a polygon (a rotated rectangle
    # for bars and lines, a smoothed, simplified outline for arrows and letters), drawn back anti-aliased. No
    # pixel-ragged edges from the scan reach the texture
    paint, shapes = [], []
    from skimage import measure as skmeasure
    height_px, width_px = white.shape
    for colour, mask in (("white", white), ("yellow", yellow)):
        mask = ndimage.binary_closing(mask & on_road, iterations=2)
        canvas = Image.new("L", (width_px * 4, height_px * 4), 0)
        draw = ImageDraw.Draw(canvas)
        for region in skmeasure.regionprops(skmeasure.label(mask)):
            area = region.area * CONTROL_RES ** 2
            if area < 0.03:
                continue
            # road paint is thin: lines, stripes, arrows, letters. Compact bright blobs (litter, a cap, a
            # reflection) are not paint
            thin = region.axis_minor_length * CONTROL_RES < 0.2 or region.axis_major_length > 3.0 * region.axis_minor_length
            if area > 0.06 and not thin and region.solidity > 0.8:
                continue
            points = region.coords[:, ::-1].astype(float)          # (col, row)
            rect = shapely.MultiPoint(points).minimum_rotated_rectangle
            if region.area / max(rect.area, 1) > 0.7 or region.axis_major_length > 4.0 * region.axis_minor_length:
                polygon, kind = rect.buffer(-0.5), "bar"
            else:
                sub = np.pad(region.image, 3).astype(float)
                contour = max(skmeasure.find_contours(ndimage.gaussian_filter(sub, 1.2), 0.5), key=len)
                r0, c0 = region.bbox[:2]
                polygon = shapely.Polygon(np.column_stack([contour[:, 1] + c0 - 3, contour[:, 0] + r0 - 3])).buffer(0)
                polygon, kind = polygon.simplify(0.04 / CONTROL_RES), "glyph"
            if polygon.is_empty:
                continue
            for part in getattr(polygon, "geoms", [polygon]):
                draw.polygon([(x * 4 + 2, y * 4 + 2) for x, y in np.array(part.exterior.coords)], fill=255)
                shapes.append({"colour": colour, "kind": kind,
                               "points": [[round(x0 + (x + 0.5) * CONTROL_RES, 3), round(y0 + (y + 0.5) * CONTROL_RES, 3)]
                                          for x, y in np.array(part.exterior.coords)]})
        layer = np.asarray(canvas.resize((width_px, height_px), Image.BOX), float) / 255
        paint.append(layer)
    with open(os.path.join(out, "paint.json"), "w") as f:
        json.dump(shapes, f)
    red = (gx >= plan["red_road_from_x"]).astype(float)
    red = ndimage.gaussian_filter(red, 1.0)
    # large scale brightness variation of the real road (patches, wear), from the orthophoto: luminance blurred
    # over half a metre relative to its 6 m surroundings. Breaks the tiling texture's repetition with real data
    base = ndimage.gaussian_filter(np.where(paint[0] + paint[1] > 0.1, background, luma), 0.5 / CONTROL_RES)
    surroundings = ndimage.uniform_filter(base, int(6.0 / CONTROL_RES))
    macro = np.clip(0.5 + (base / np.maximum(surroundings, 1e-3) - 1.0) * 1.5, 0.0, 1.0)
    rgba = np.stack([red, paint[0], paint[1], macro], -1)
    Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(os.path.join(out, "control.png"))
    # average scan colour of each ground class, to tint the PBR materials towards the place
    asphalt = on_road & (gx < plan["red_road_from_x"]) & (paint[0] < 0.1)
    redp = on_road & (gx >= plan["red_road_from_x"]) & (paint[0] < 0.1) & (paint[1] < 0.1)
    return {"asphalt": a[asphalt].mean(0).round(3).tolist(), "red": a[redp].mean(0).round(3).tolist(),
            "sidewalk": a[~on_road & shapely.contains_xy(sidewalk_union, gx, gy)].mean(0).round(3).tolist()}


def photo_crop(record, image_path, u0, u1, z0, z1, outward, out_path):
    """Crops world rectangle [u0, u1] x [z0, z1] (u along the photo's u axis, metres from its origin) from a face
    photo, as seen from outside (mirrored when the photo's u runs against the viewer's right)."""
    image = Image.open(image_path)
    w, h = image.size
    su, sv = record["size"]
    top = record["origin"][2]
    box = (int(u0 / su * w), int((top - z1) / sv * h), int(u1 / su * w), int((top - z0) / sv * h))
    crop = image.crop(box)
    right = np.array([outward[1], -outward[0]])
    if np.dot(record["u"], right) < 0:
        crop = ImageOps.mirror(crop)
    crop.save(out_path)


def blue_elephant(plan, out, floor):
    """The Blue Elephant corner building: front facing -Y at y = 9.5, side facing -X at x = 6.1."""
    b = plan["building"]
    X0, X1, Y0, Y1 = b["footprint"]
    G = b["ground"]
    m = meshkit.Mesh("SM_Zone_BlueElephant", collision="complex")
    rebuilt = os.path.join(OUT_DIR, plan["stage"])
    front, side = b["front_photo"], b["side_photo"]
    IMG = meshkit.IMAGE_UVS
    crops = []

    def sign(name, record, u0, u1, z0, z1, outward):
        path = os.path.join(out, f"sign_{name}.png")
        photo_crop(record, os.path.join(rebuilt, record["file"]), u0, u1, z0, z1, outward, path)
        crops.append(name)
        return (f"Sign_{name}", IMG)

    fx0 = front["origin"][0]   # front photo u = x - fx0
    sy0 = side["origin"][1]    # side photo u = y - sy0
    T = 0.3                    # facade layer thickness

    # core mass behind the facades (estimated beyond what the photos show)
    m.box(X0 + T, X1, Y0 + T, Y1, G, 8.7, "Plaster", skip=("-Z",))

    # ---- front, ground floor: red cladding, glass door, poster, BLUE ELEPHANT sign
    m.box(X0, 8.7, Y0, Y0 + T, G, 0.0, "Cladding", skip=("-Z",))
    m.box(10.45, 10.9, Y0, Y0 + T, G, 0.0, "Cladding", skip=("-Z",))
    m.box(8.7, 10.45, Y0, Y0 + T, -0.2, 0.0, "Cladding")
    m.box(8.7, 10.45, Y0 + 0.25, Y0 + T, G, -0.2, "GlassFront", skip=("-Z",))
    for x in (8.7, 9.55, 10.39):
        m.box(x, x + 0.06, Y0 + 0.18, Y0 + 0.26, G, -0.2, "Frame", skip=("-Z",))
    m.box(10.9, 12.1, Y0 + 0.05, Y0 + T, -2.45, -0.15, "Cladding", faces={"-Y": sign("poster", front, 10.9 - fx0, 12.1 - fx0, -2.45, -0.15, (0, -1))})
    m.box(10.9, 12.1, Y0, Y0 + T, G, -2.45, "Cladding", skip=("-Z",))
    m.box(10.9, 12.1, Y0, Y0 + T, -0.15, 0.0, "Cladding")
    # the BLUE ELEPHANT sign is a 25 cm deep box with a dark metal frame round its face
    m.box(X0, 12.1, Y0 - 0.25, Y0, 0.04, 0.96, "SignFrame", faces={"-Y": sign("blue_elephant_front", front, X0 - fx0, 12.1 - fx0, 0.04, 0.96, (0, -1))})
    m.box(X0 - 0.02, 12.12, Y0 - 0.27, Y0, 0.0, 0.04, "SignFrame")
    m.box(X0 - 0.02, 12.12, Y0 - 0.27, Y0, 0.96, 1.0, "SignFrame")
    # glass door: frame, two leaves, push bars, threshold
    m.box(8.62, 8.7, Y0 + 0.1, Y0 + 0.3, G, -0.2, "SignFrame", skip=("-Z",))
    m.box(10.45, 10.53, Y0 + 0.1, Y0 + 0.3, G, -0.2, "SignFrame", skip=("-Z",))
    m.box(8.62, 10.53, Y0 + 0.1, Y0 + 0.3, -0.28, -0.2, "SignFrame")
    m.box(8.62, 10.53, Y0 + 0.05, Y0 + 0.3, G - 0.02, G + 0.03, "Steel")
    for x in (9.25, 9.85):
        m.beam([x, Y0 + 0.12, G + 0.95], [x, Y0 + 0.12, G + 1.55], 0.035, 0.035, "Stainless")
    # under the exterior stair: plain plastered wall (the stair is modelled below)
    m.box(12.1, X1, Y0 + 0.2, Y0 + T, G, 1.0, "Plaster", skip=("-Z",))

    # ---- front, 2nd floor: Coffee Bean glass, side window
    m.box(X0, 7.4, Y0, Y0 + T, 1.0, 2.8, "Plaster")
    m.box(11.5, 13.2, Y0, Y0 + T, 1.0, 2.8, "Plaster")
    m.box(14.2, X1, Y0, Y0 + T, 1.0, 2.8, "Plaster")
    m.box(13.2, 14.2, Y0, Y0 + T, 1.0, 1.2, "Plaster")
    m.box(13.2, 14.2, Y0, Y0 + T, 2.6, 2.8, "Plaster")
    m.box(7.4, 11.5, Y0 + 0.25, Y0 + T, 1.0, 2.8, "GlassFront")
    m.box(13.2, 14.2, Y0 + 0.25, Y0 + T, 1.2, 2.6, "GlassFront")
    for x in (7.4, 9.42, 11.44, 13.2, 14.14):
        m.box(x, x + 0.06, Y0 + 0.18, Y0 + 0.26, 1.0, 2.8, "Frame")
    m.box(7.4, 11.5, Y0 + 0.18, Y0 + 0.26, 2.74, 2.8, "Frame")
    # The Coffee Bean sign band
    m.box(X0, 14.2, Y0 - 0.2, Y0 + T, 2.85, 3.85, "Plaster", faces={"-Y": sign("coffee_bean_front", front, X0 - fx0, 14.2 - fx0, 2.85, 3.85, (0, -1))})
    m.box(X0 - 0.03, 14.23, Y0 - 0.23, Y0 + T, 2.8, 2.85, "Trim")
    m.box(X0 - 0.03, 14.23, Y0 - 0.23, Y0 + T, 3.85, 3.9, "Trim")
    m.box(14.2, X1, Y0 - 0.1, Y0 + T, 2.8, 3.9, "Plaster")

    # ---- front, 3rd floor: glass strip with mullions
    m.box(X0, 6.35, Y0, Y0 + T, 3.9, 5.25, "Plaster")
    m.box(14.55, X1, Y0, Y0 + T, 3.9, 5.25, "Plaster")
    m.box(6.35, 14.55, Y0 + 0.25, Y0 + T, 3.9, 5.25, "GlassFront")
    for x in np.arange(6.35, 14.56, 0.684):
        m.box(x, x + 0.06, Y0 + 0.17, Y0 + 0.26, 3.9, 5.25, "Frame")
    m.box(6.35, 14.55, Y0 + 0.17, Y0 + 0.26, 3.9, 3.98, "Frame")
    m.box(6.35, 14.55, Y0 + 0.17, Y0 + 0.26, 5.17, 5.25, "Frame")

    # ---- front, 4th floor: brick with three windows
    windows = [(7.4, 9.2), (9.7, 11.5), (12.0, 13.9)]
    edges = [X0] + [v for w in windows for v in w] + [X1]
    for k in range(0, len(edges), 2):
        m.box(edges[k], edges[k + 1], Y0, Y0 + T, 5.9, 8.0, "Brick")
    for wx0, wx1 in windows:
        m.box(wx0, wx1, Y0, Y0 + T, 5.9, 6.3, "Brick")
        m.box(wx0, wx1, Y0, Y0 + T, 7.6, 8.0, "Brick")
        m.box(wx0, wx1, Y0 + 0.22, Y0 + T, 6.3, 7.6, "GlassFront")
        m.box(wx0 - 0.05, wx1 + 0.05, Y0 - 0.06, Y0 + 0.05, 6.2, 6.3, "Plaster")   # sill
        for x in (wx0, (wx0 + wx1) / 2 - 0.03, wx1 - 0.06):
            m.box(x, x + 0.06, Y0 + 0.14, Y0 + 0.23, 6.3, 7.6, "Frame")
    m.box(X0, X1, Y0, Y0 + T, 5.25, 5.9, "Brick")

    # ---- side (-X), ground floor: storefront glass and the side BLUE ELEPHANT sign
    m.box(X0, X0 + T, Y0, 9.9, G, 0.0, "Cladding", skip=("-Z",))
    m.box(X0, X0 + T, 15.2, Y1, G, 0.0, "Cladding", skip=("-Z",))
    m.box(X0, X0 + T, 9.9, 15.2, -0.2, 0.0, "Cladding")
    m.box(X0, X0 + T, 9.9, 15.2, G, G + 0.15, "Cladding", skip=("-Z",))
    m.box(X0 + 0.25, X0 + T, 9.9, 15.2, G + 0.15, -0.2, "GlassSide")
    for y in np.arange(9.9, 15.21, 1.325):
        m.box(X0 + 0.18, X0 + 0.26, y, y + 0.06, G + 0.15, -0.2, "Frame")
    # the side signs are the same signs as on the front; the scan saw them only at a grazing angle, so the sharper
    # front crops are used (an approximation: lettering and colours match, small wear differences don't)
    m.box(X0 - 0.12, X0, 9.6, 15.2, 0.0, 1.0, "Cladding", faces={"-X": ("Sign_blue_elephant_front", IMG)})
    m.box(X0, X0 + T, 15.2, Y1, 0.0, 1.0, "Cladding")
    m.box(X0, X0 + T, Y0, 9.6, 0.0, 1.0, "Cladding")
    # 2nd floor
    m.box(X0, X0 + T, Y0, 9.9, 1.0, 2.8, "Plaster")
    m.box(X0, X0 + T, 16.0, Y1, 1.0, 2.8, "Plaster")
    m.box(X0 + 0.25, X0 + T, 9.9, 16.0, 1.0, 2.8, "GlassSide")
    for y in (9.9, 11.92, 13.94, 15.94):
        m.box(X0 + 0.18, X0 + 0.26, y, y + 0.06, 1.0, 2.8, "Frame")
    m.box(X0 - 0.2, X0 + T, Y0, 16.6, 2.85, 3.85, "Plaster", faces={"-X": ("Sign_coffee_bean_front", IMG)})
    m.box(X0 - 0.23, X0 + T, Y0 - 0.23, 16.63, 2.8, 2.85, "Trim")
    m.box(X0 - 0.23, X0 + T, Y0 - 0.23, 16.63, 3.85, 3.9, "Trim")
    m.box(X0, X0 + T, 16.6, Y1, 2.8, 3.9, "Plaster")
    # 3rd floor
    m.box(X0, X0 + T, 16.6, Y1, 3.9, 5.25, "Plaster")
    m.box(X0 + 0.25, X0 + T, Y0 + T, 16.6, 3.9, 5.25, "GlassSide")
    for y in np.arange(Y0 + T, 16.61, 0.7):
        m.box(X0 + 0.17, X0 + 0.26, y, y + 0.06, 3.9, 5.25, "Frame")
    m.box(X0 + 0.17, X0 + 0.26, Y0 + T, 16.6, 3.9, 3.98, "Frame")
    m.box(X0 + 0.17, X0 + 0.26, Y0 + T, 16.6, 5.17, 5.25, "Frame")
    # 4th floor
    side_windows = [(10.2, 11.9), (12.6, 14.3), (15.0, 16.7)]
    edges = [Y0] + [v for w in side_windows for v in w] + [Y1]
    for k in range(0, len(edges), 2):
        m.box(X0, X0 + T, edges[k], edges[k + 1], 5.9, 8.0, "Brick")
    for wy0, wy1 in side_windows:
        m.box(X0, X0 + T, wy0, wy1, 5.9, 6.3, "Brick")
        m.box(X0, X0 + T, wy0, wy1, 7.6, 8.0, "Brick")
        m.box(X0 + 0.22, X0 + T, wy0, wy1, 6.3, 7.6, "GlassSide")
        m.box(X0 - 0.06, X0 + 0.05, wy0 - 0.05, wy1 + 0.05, 6.2, 6.3, "Plaster")
        for y in (wy0, (wy0 + wy1) / 2 - 0.03, wy1 - 0.06):
            m.box(X0 + 0.14, X0 + 0.23, y, y + 0.06, 6.3, 7.6, "Frame")
    m.box(X0, X0 + T, Y0, Y1, 5.25, 5.9, "Brick")

    # ---- awnings: corrugated steel sloping out over both street faces
    for top, drop, reach, x_start in ((5.9, 0.6, 0.65, 5.45), (8.7, 0.6, 0.5, 5.6)):
        zt, zb = top, top - drop
        # front (-Y)
        m.quad([x_start, Y0 - reach, zb], [X1, Y0 - reach, zb], [X1, Y0, zt], [x_start, Y0, zt], [0, -0.7, 0.7], "Awning")
        m.quad([x_start, Y0 - reach, zb - 0.04], [X1, Y0 - reach, zb - 0.04], [X1, Y0 - reach, zb], [x_start, Y0 - reach, zb], [0, -1, 0], "Frame")
        m.quad([x_start, Y0 - reach, zb - 0.04], [X1, Y0 - reach, zb - 0.04], [X1, Y0, zt - 0.04], [x_start, Y0, zt - 0.04], [0, 0.3, -1], "Awning")
        # side (-X)
        m.quad([X0 - reach, Y0 - reach, zb], [X0 - reach, Y1, zb], [X0, Y1, zt], [X0, Y0, zt], [-0.7, 0, 0.7], "Awning")
        m.quad([X0 - reach, Y0 - reach, zb - 0.04], [X0 - reach, Y1, zb - 0.04], [X0 - reach, Y1, zb], [X0 - reach, Y0 - reach, zb], [-1, 0, 0], "Frame")
        m.quad([X0 - reach, Y0 - reach, zb - 0.04], [X0 - reach, Y1, zb - 0.04], [X0, Y1, zt - 0.04], [X0, Y0, zt - 0.04], [0.3, 0, -1], "Awning")

    # ---- mansard roof over both street faces, flat top behind (estimated), three dormers on the side
    inset, top = 1.6, 11.8
    a, b_, c, d = [X0, Y0, 8.7], [X1, Y0, 8.7], [X1, Y0 + inset, top], [X0 + inset, Y0 + inset, top]
    m.quad(a, b_, c, d, [0, -0.85, 0.5], "Roof")
    e, f = [X0, Y1, 8.7], [X0 + inset, Y1, top]
    m.quad(a, d, f, e, [-0.85, 0, 0.5], "Roof")
    m.quad(d, c, [X1, Y1, top], f, [0, 0, 1], "Plaster")
    m.quad(b_, [X1, Y1, 8.7], [X1, Y1, top], c, [1, 0, 0], "Plaster")
    m.quad(e, [X1, Y1, 8.7], [X1, Y1, top], f, [0, 1, 0], "Plaster")
    m.box(X0, X1, Y0, Y1, 8.6, 8.7, "Plaster", skip=("-Z",))
    for dy0, dy1 in ((10.6, 12.3), (13.5, 15.1), (16.0, 17.6)):
        dx0, dz0, dz1 = X0 + 0.55, 9.4, 10.9
        m.box(dx0, X0 + inset, dy0, dy1, dz0, dz1, "Plaster", skip=("-Z",))
        m.box(dx0 - 0.02, dx0 + 0.03, dy0 + 0.25, dy1 - 0.25, dz0 + 0.25, dz1 - 0.2, "Glass", skip=("-Z",))
        m.box(dx0 - 0.06, dx0, dy0 + 0.2, dy1 - 0.2, dz0 + 0.2, dz0 + 0.25, "Frame")
        mid = (dy0 + dy1) / 2
        # small gable on top
        m.triangle([dx0 - 0.08, dy0 - 0.08, dz1], [dx0 - 0.08, dy1 + 0.08, dz1], [dx0 - 0.08, mid, dz1 + 0.6], [-1, 0, 0], "Plaster")
        m.quad([dx0 - 0.08, dy0 - 0.08, dz1], [X0 + inset, dy0 - 0.08, dz1], [X0 + inset, mid, dz1 + 0.6], [dx0 - 0.08, mid, dz1 + 0.6], [0, -0.6, 0.8], "Roof")
        m.quad([dx0 - 0.08, dy1 + 0.08, dz1], [X0 + inset, dy1 + 0.08, dz1], [X0 + inset, mid, dz1 + 0.6], [dx0 - 0.08, mid, dz1 + 0.6], [0, 0.6, 0.8], "Roof")
    # ---- structure: slab edges between storeys and a corner pilaster (the bands the photos show)
    for z in (5.25, 8.0):
        m.box(X0 - 0.08, X1, Y0 - 0.08, Y0, z - 0.08, z + 0.06, "Trim", skip=("+Y",))
        m.box(X0 - 0.08, X0, Y0, Y1, z - 0.08, z + 0.06, "Trim", skip=("+X",))
    m.box(X0 - 0.06, X0 + 0.3, Y0 - 0.06, Y0 + 0.3, 3.9, 5.25, "Plaster")
    # gutter along the foot of the mansard
    m.beam([X0 - 0.12, Y0 - 0.12, 8.66], [X1, Y0 - 0.12, 8.66], 0.12, 0.1, "Steel")
    m.beam([X0 - 0.12, Y0 - 0.12, 8.66], [X0 - 0.12, Y1, 8.66], 0.12, 0.1, "Steel")

    # ---- roof: low parapet round the flat top, a water tank and outdoor units (estimated: the scan doesn't see the
    # roof; Seoul low-rise roofs commonly carry these)
    inset, top = 1.6, 11.8
    for x0_, x1_, y0_, y1_ in ((X0 + inset, X1, Y1 - 0.15, Y1), (X1 - 0.15, X1, Y0 + inset, Y1)):
        m.box(x0_, x1_, y0_, y1_, top, top + 0.5, "Plaster", skip=("-Z",))
    m.cylinder((12.6, 17.0), 0.75, top, top + 1.4, "Steel", segments=20)
    for ux, uy in ((10.0, 13.6), (11.2, 13.6)):
        m.box(ux, ux + 0.85, uy, uy + 0.35, top, top + 0.65, "Steel", skip=("-Z",))

    # ---- exterior stair to the 2nd floor (measured: x 12.7-14.6, from the plaza at y 6.0 up to z 1.0 at y 9.0)
    stair(m, plan, floor)
    return m, crops, {"GlassFront": front, "GlassSide": side}


def stair(m, plan, floor):
    """Steel stair with diamond plate treads, channel stringers, stainless railings and a landing."""
    sx0, sx1, y_start, y_land, z_top = 12.75, 14.55, 6.0, 9.0, 1.0
    z_base = float(floor([[(sx0 + sx1) / 2, y_start]])[0]) + plan["sidewalk_height"]
    steps = int(round((z_top - z_base) / 0.185))
    rise, run = (z_top - z_base) / steps, (y_land - y_start) / steps
    for i in range(steps):
        z = z_base + (i + 1) * rise
        y = y_start + i * run
        m.box(sx0, sx1, y, y + run + 0.03, z - 0.04, z, "SteelTread")
        m.box(sx0, sx1, y + run - 0.01, y + run + 0.03, z - rise, z - 0.04, "SteelDark")   # riser plate
    for x in (sx0 - 0.05, sx1 + 0.05):
        m.beam([x, y_start - 0.1, z_base - 0.25], [x, y_land, z_top - 0.12], 0.08, 0.3, "SteelDark")
    m.box(sx0 - 0.1, sx1 + 0.1, y_land, 9.5, z_top - 0.15, z_top, "SteelTread")
    for y in (7.3,):
        z = z_base + (y - y_start) / run * rise
        for x in (sx0 + 0.1, sx1 - 0.1):
            m.box(x - 0.06, x + 0.06, y - 0.06, y + 0.06, z_base - 0.2, z - 0.3, "SteelDark", skip=("-Z",))
    # railings on both sides: posts every ~0.9 m, a handrail and two mid rails following the slope, then level on
    # the landing
    nose = lambda y: z_base + (y - y_start) / run * rise
    for x in (sx0 - 0.03, sx1 + 0.03):
        ys = np.linspace(y_start + 0.05, y_land, max(2, int((y_land - y_start) / 0.9) + 1))
        for y in ys:
            m.beam([x, y, nose(y)], [x, y, nose(y) + 0.95], 0.045, 0.045, "Stainless")
        m.beam([x, 9.47, z_top], [x, 9.47, z_top + 0.95], 0.045, 0.045, "Stainless")
        for h in (0.95, 0.62, 0.3):
            m.beam([x, ys[0], nose(ys[0]) + h], [x, y_land, nose(y_land) + h], 0.045 if h == 0.95 else 0.025, 0.045 if h == 0.95 else 0.025, "Stainless")
            m.beam([x, y_land, z_top + h], [x, 9.47, z_top + h], 0.045 if h == 0.95 else 0.025, 0.045 if h == 0.95 else 0.025, "Stainless")


def props(plan, floor, out):
    """Small street furniture in the zone, at measured spots: traffic cones (orange splats on the scan), the sign
    post with its poster board at the corner, and gutter grates along the curbs."""
    m = meshkit.Mesh("SM_Zone_Props", collision="complex")
    for cx, cy in plan.get("cones", []):
        z = float(floor([[cx, cy]])[0])
        m.box(cx - 0.19, cx + 0.19, cy - 0.19, cy + 0.19, z, z + 0.035, "ConeBlack", skip=("-Z",))
        m.cylinder((cx, cy), (0.15, 0.115), z + 0.035, z + 0.3, "ConeOrange", segments=18, cap=False)
        m.cylinder((cx, cy), (0.117, 0.085), z + 0.3, z + 0.45, "ConeWhite", segments=18, cap=False)
        m.cylinder((cx, cy), (0.087, 0.03), z + 0.45, z + 0.72, "ConeOrange", segments=18)
    post = plan.get("sign_post")
    if post:
        px, py = post["xy"]
        z = float(floor([[px, py]])[0]) + plan["sidewalk_height"]
        m.cylinder((px, py), 0.04, z, z + post["height"], "Steel", segments=12)
        b = post["board"]
        m.box(px - b["w"] / 2, px + b["w"] / 2, py - 0.06, py - 0.04, b["z0"], b["z1"], "Steel",
              faces={"-Y": ("Sign_board", meshkit.IMAGE_UVS)})
    for gx, gy, along in plan.get("grates", []):
        z = float(floor([[gx, gy]])[0]) + 0.006
        hx, hy = (0.45, 0.2) if along == "x" else (0.2, 0.45)
        uvs = [[0, 0], [1, 0], [1, 1], [0, 1]] if along == "x" else [[0, 1], [0, 0], [1, 0], [1, 1]]
        m.quad([gx - hx, gy - hy, z], [gx + hx, gy - hy, z], [gx + hx, gy + hy, z], [gx - hx, gy + hy, z], [0, 0, 1], "Grate", uvs)
    return m


def removal(plan, scan, floor, domain, sidewalks, surface):
    """Splats replaced by the meshes: the ground band over the domain, everything inside the building, its awnings,
    signs and stair, the props; plus a local clean up of the zone (thin streaks, floating specks)."""
    xy = scan.pos[:, :2]
    z = scan.pos[:, 2]
    above = z - floor(xy)
    in_domain = shapely.contains_xy(domain, xy[:, 0], xy[:, 1])
    walk = shapely.contains_xy(unary_union(list(sidewalks.values())), xy[:, 0], xy[:, 1])
    ground = in_domain & (above > GROUND_BAND[0]) & (above < np.where(walk, SIDEWALK_BAND_TOP, GROUND_BAND[1]))
    X0, X1, Y0, Y1 = plan["building"]["footprint"]
    inside = (xy[:, 0] > X0 - 0.15) & (xy[:, 0] < X1 + 0.1) & (xy[:, 1] > Y0 - 0.15) & (xy[:, 1] < Y1 + 0.3) & (z > plan["building"]["ground"] - 0.5) & (z < 13.6)
    # the awnings and signs reach out over the sidewalk
    awnings = (((xy[:, 1] > Y0 - 0.8) & (xy[:, 0] > X0 - 0.8) & (xy[:, 0] < X1 + 0.1)) |
               ((xy[:, 0] > X0 - 0.8) & (xy[:, 1] > Y0 - 0.8) & (xy[:, 1] < Y1 + 0.3))) & (z > 4.8) & (z < 13.6)
    signs = (((xy[:, 1] > Y0 - 0.35) & (xy[:, 0] > X0 - 0.35) & (xy[:, 0] < 12.9)) |
             ((xy[:, 0] > X0 - 0.35) & (xy[:, 1] > Y0 - 0.35) & (xy[:, 1] < 16.6))) & (z > -0.1) & (z < 4.0)
    stair = (xy[:, 0] > 12.5) & (xy[:, 0] < 14.8) & (xy[:, 1] > 5.8) & (xy[:, 1] < 9.6) & (z > -2.6) & (z < 2.2)
    props = np.zeros(len(xy), bool)
    for cx, cy in plan.get("cones", []):
        props |= (np.hypot(xy[:, 0] - cx, xy[:, 1] - cy) < 0.35) & (above < 1.0)
    if plan.get("sign_post"):
        px, py = plan["sign_post"]["xy"]
        props |= (np.hypot(xy[:, 0] - px, xy[:, 1] - py) < 0.55) & (above < 3.2)
    # local clean up inside the zone box (2 m margin): thin faint streaks, and specks floating with nothing near
    x0, x1, y0, y1 = plan["box"]
    near = (xy[:, 0] > x0 - 2) & (xy[:, 0] < x1 + 2) & (xy[:, 1] > y0 - 2) & (xy[:, 1] < y1 + 2)
    scales = np.sort(scan.scale, axis=1)
    # (a stricter rule, ratio > 8 and opacity < 0.5, removed 190k splats and punched holes in the neighbouring
    # facades, so only the clearly thin and faint ones go)
    streak = near & (scales[:, 2] / np.maximum(scales[:, 1], 1e-9) > 12.0) & (scan.opacity < 0.25) & (above > 2.5)
    idx = np.flatnonzero(near & (above > 2.5))
    from scipy.spatial import cKDTree
    distance, _ = cKDTree(scan.pos[idx]).query(scan.pos[idx], k=9, workers=-1)
    speck = np.zeros(len(xy), bool)
    speck[idx] = distance[:, 8] > 0.3
    remove = ground | inside | awnings | signs | stair | props | streak | speck
    counts = {"ground": int(ground.sum()), "building": int((inside | awnings | signs).sum()), "stair": int(stair.sum()),
              "props": int(props.sum()), "streaks": int(streak.sum()), "specks": int(speck.sum())}
    return remove, counts


def plan_image(plan, domain, sidewalks, road, out):
    x0, x1, y0, y1 = plan["box"]
    px = 30
    w, h = int((y1 - y0) * px), int((x1 - x0) * px)
    to = lambda p: ((p[1] - y0) * px, h - (p[0] - x0) * px)
    im = Image.new("RGB", (w, h), (25, 25, 30))
    d = ImageDraw.Draw(im)
    parts = list(road.geoms) if road.geom_type != "Polygon" else [road]
    for part in parts:
        d.polygon([to(p) for p in part.exterior.coords], fill=(70, 70, 75))
        for hole in part.interiors:
            d.polygon([to(p) for p in hole.coords], fill=(25, 25, 30))
    for poly in sidewalks.values():
        d.polygon([to(p) for p in poly.exterior.coords], fill=(150, 150, 140), outline=(230, 230, 220))
    X0, X1, Y0, Y1 = plan["building"]["footprint"]
    d.rectangle((to([X1, Y0])[0], to([X1, Y0])[1], to([X0, Y1])[0], to([X0, Y1])[1]), fill=(160, 60, 50))
    for m in plan["manholes"]:
        cx, cy = to([m["x"], m["y"]])
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(30, 30, 30), outline=(200, 200, 200))
    d.text((6, 6), "grey: road mesh  light: sidewalk mesh  red: building mesh  dark: still scan", fill=(255, 255, 0))
    im.save(os.path.join(out, "plan.png"))


def main(zone):
    plan = json.load(open(os.path.join(HERE, "zones", f"{zone}.json")))
    out = os.path.join(OUT_DIR, zone)
    os.makedirs(out, exist_ok=True)
    start = time.time()
    collision = load_collision(plan["stage"])
    raw_floor = Floor(collision)
    box = plan["box"]
    zone_box = shapely_box(box[0], box[2], box[1], box[3])
    footprint = plan["building"]["footprint"]
    building = shapely_box(footprint[0], footprint[2], footprint[1], footprint[3])
    sidewalks = {k: Polygon(v).buffer(0).intersection(zone_box).difference(building) for k, v in plan["sidewalks"].items()}
    blocked = unary_union([building] + [Polygon(v) for k, v in plan.get("scan_buildings", {}).items() if not k.startswith("_")])
    domain = unary_union([walkable_polygon(plan["stage"], box)] + list(sidewalks.values())).difference(blocked)
    # drop slivers left between the walkable outline and the sidewalks
    domain = unary_union([g for g in getattr(domain, "geoms", [domain]) if g.area > 2.0]).buffer(0.05).buffer(-0.05)
    # the two outer corners are only measured roughly: keep them to the walkable ground
    for k in ("south_west_corner", "south_east_corner"):
        sidewalks[k] = sidewalks[k].intersection(walkable_polygon(plan["stage"], box))
    sidewalks = {k: (max(v.geoms, key=lambda g: g.area) if v.geom_type != "Polygon" else v) for k, v in sidewalks.items() if not v.is_empty}

    floor = Surface(raw_floor, domain)
    print(f"  smoothed ground: collision floor differs by p50 {floor.stats['p50'] * 100:.1f} cm, p95 {floor.stats['p95'] * 100:.1f} cm, "
          f"at most {floor.stats['max_above'] * 100:.0f} cm above")
    meshes, road = ground_meshes(plan, floor, domain, sidewalks)
    tints = control_texture(plan, road, unary_union(list(sidewalks.values())), out)
    hero, crops, glass_photos = blue_elephant(plan, out, floor)
    board = plan.get("sign_post", {}).get("board")
    if board:
        b = plan["building"]["front_photo"]
        photo_crop(b, os.path.join(OUT_DIR, plan["stage"], b["file"]), board["u0"], board["u1"], board["z0"], board["z1"], (0, -1),
                   os.path.join(out, "sign_board.png"))
        crops.append("board")
    meshes.append(props(plan, floor, out))
    for record in glass_photos.values():
        Image.open(os.path.join(OUT_DIR, plan["stage"], record["file"])).save(os.path.join(out, record["file"]))
    meshes.append(hero)
    meshkit.save(meshes, os.path.join(out, "meshes.json"))

    scan = Scan(plan["stage"])
    remove, counts = removal(plan, scan, raw_floor, domain, sidewalks, floor)
    write_ply(os.path.join(out, f"{zone}.ply"), scan.header, scan.data[~remove])
    plan_image(plan, domain, sidewalks, road, out)
    info = {"zone": zone, "box": box, "tints": tints, "signs": crops, "glass": glass_photos, "splats": int(len(remove)), "removed": counts,
            "kept": int((~remove).sum()), "areas": {"road": round(road.area, 1), "sidewalks": round(sum(s.area for s in sidewalks.values()), 1)},
            "triangles": {m.name: sum(len(s["i"]) // 3 for s in m.sections.values()) for m in meshes}}
    with open(os.path.join(out, "zone.json"), "w") as f:
        json.dump(info, f, indent=1)
    print(f"{zone}: road {info['areas']['road']} m2, sidewalks {info['areas']['sidewalks']} m2, triangles {info['triangles']}, "
          f"splats {len(remove):,} -> {info['kept']:,} {counts}, "
          f"tints {tints}, {time.time() - start:.0f}s")


for zone_name in sys.argv[1:] or ["Hongdae_A"]:
    main(zone_name)
