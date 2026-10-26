"""
Reconstruction step R4 (outside Unreal): the CG parking deck built from the floor plan (layout.json), in the look of
the Lotte Tower navigation video (a fully modelled Unreal garage): glossy epoxy floor with crisp paint, white columns
with blue sawtooth bands and zone plates, concrete slab and deep beams, linear LED fixtures, red sprinkler mains,
cable trays, signs, wheel stops, covered cars in most stalls.

  ~/.venvs/gs/bin/python -I rebuild_geometry.py

Writes SourceAssets/ParkingStage/rebuild/:
  rebuild.json   meshes (sections of positions / uvs / indices per material, Unreal cm), placements of the shared
                 meshes (columns, fixtures, wheel stops, signs), lights, props
  *.png          generated textures: column faces per zone label, hanging signs, exit sign
build_rebuild_level.py turns it into /Game/Stages/Lvl_ParkingTower_CG.
"""

import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ptstage as S  # noqa: E402

OUT = os.path.join(S.OUT_DIR, "rebuild")
FONT = "C:/Windows/Fonts/malgunbd.ttf"
FONT_WSL = "/mnt/c/Windows/Fonts/malgunbd.ttf"
FONT_LATIN_WSL = "/mnt/c/Windows/Fonts/arialbd.ttf"

PAINT_Z = 0.25                 # paint sits just above the floor
FIXTURE_Z = 268.0              # LED tubes hang just under the beams
BLUE = (28, 104, 178)


class Mesh:
    """Sections of triangles per material, with hard edges (every face has its own vertices)."""

    def __init__(self, name, collision="none"):
        self.name, self.collision, self.sections = name, collision, {}

    def section(self, material):
        return self.sections.setdefault(material, {"material": material, "positions": [], "uvs": [], "indices": []})

    def quad(self, material, pts, uvs):
        s = self.section(material)
        base = len(s["positions"])
        s["positions"] += [[round(c, 2) for c in p] for p in pts]
        s["uvs"] += [[round(c, 4) for c in uv] for uv in uvs]
        # Unreal front faces: (P2 - P0) x (P1 - P0) points out; quads come counter-clockwise seen from outside
        s["indices"] += [base, base + 2, base + 1, base, base + 3, base + 2]

    def tri_fan(self, material, pts, uvs, tris):
        s = self.section(material)
        base = len(s["positions"])
        s["positions"] += [[round(c, 2) for c in p] for p in pts]
        s["uvs"] += [[round(c, 4) for c in uv] for uv in uvs]
        for a, b, c in tris:
            s["indices"] += [base + a, base + c, base + b]

    def box(self, material, x0, x1, y0, y1, z0, z1, tile=100.0, faces="tbnsew", unit_uv=False):
        """Axis aligned box. UVs in world units / tile (u along the face, v down the height), or 0..1 per face."""
        def uv(a, b, w, h):
            return [(0, 0), (1, 0), (1, 1), (0, 1)] if unit_uv else [(a / tile, b / tile), ((a + w) / tile, b / tile),
                                                                   ((a + w) / tile, (b + h) / tile), (a / tile, (b + h) / tile)]
        if "t" in faces:
            self.quad(material, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], uv(x0, y0, x1 - x0, y1 - y0))
        if "b" in faces:
            self.quad(material, [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], uv(x0, y0, x1 - x0, y1 - y0))
        # sides: u along the face seen from outside, v from the top down
        if "s" in faces:   # -Y face
            self.quad(material, [(x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1)][::-1][::-1],
                      [])  if False else None
            self.quad(material, [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)][::-1],
                      uv(x0, -z1, x1 - x0, z1 - z0)[::-1])
        if "n" in faces:   # +Y face
            self.quad(material, [(x1, y1, z1), (x0, y1, z1), (x0, y1, z0), (x1, y1, z0)][::-1],
                      uv(-x1, -z1, x1 - x0, z1 - z0)[::-1])
        if "w" in faces:   # -X face
            self.quad(material, [(x0, y1, z1), (x0, y0, z1), (x0, y0, z0), (x0, y1, z0)][::-1],
                      uv(-y1, -z1, y1 - y0, z1 - z0)[::-1])
        if "e" in faces:   # +X face
            self.quad(material, [(x1, y0, z1), (x1, y1, z1), (x1, y1, z0), (x1, y0, z0)][::-1],
                      uv(y0, -z1, y1 - y0, z1 - z0)[::-1])

    def polygon(self, material, poly, z, tile=100.0):
        """Flat polygon facing up (ear clipping, any simple polygon)"""
        pts = [(x, y) for x, y in poly]
        if area2(pts) < 0:
            pts = pts[::-1]
        tris = earclip(pts)
        self.tri_fan(material, [(x, y, z) for x, y in pts], [(x / tile, y / tile) for x, y in pts], tris)

    def cylinder(self, material, a, b, r, seg=10):
        """Along X or Y between points a and b (x, y, z)"""
        ax = 0 if abs(b[0] - a[0]) > abs(b[1] - a[1]) else 1
        L = abs(b[ax] - a[ax])
        for k in range(seg):
            t0, t1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg

            def ring(t, end):
                p = list(a if end == 0 else b)
                off = (math.cos(t) * r, math.sin(t) * r)
                if ax == 0:
                    p[1] += off[0]
                    p[2] += off[1]
                else:
                    p[0] += off[0]
                    p[2] += off[1]
                return tuple(p)
            pts = [ring(t0, 0), ring(t1, 0), ring(t1, 1), ring(t0, 1)]
            if ax == 1:
                pts = pts[::-1]
            self.quad(material, pts, [(k / seg, 0), ((k + 1) / seg, 0), ((k + 1) / seg, L / 100), (k / seg, L / 100)])

    def to_json(self):
        return {"name": self.name, "collision": self.collision, "sections": list(self.sections.values())}


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def earclip(pts):
    idx = list(range(len(pts)))
    tris = []

    def inside(p, a, b, c):
        def s(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


# --- textures ---------------------------------------------------------------------------------------------------
def font(size, latin=False):
    return ImageFont.truetype(FONT_LATIN_WSL if latin else FONT_WSL, size)


def column_texture(label, path):
    """One face of a column, 70 cm x 330 cm (u across, v from the top): white paint over concrete, blue sawtooth
    bands down both edges, a blue zone plate, yellow/black guard at the foot."""
    W, H = 512, 2048
    px = lambda cm: int(cm / 330.0 * H)
    rng = random.Random(hash(label) & 0xffff)
    img = Image.new("RGB", (W, H), (236, 236, 232))
    # faint concrete mottling
    noise = Image.effect_noise((W // 8, H // 8), 18).resize((W, H), Image.BICUBIC)
    img = Image.composite(Image.new("RGB", (W, H), (222, 222, 218)), img, noise.point(lambda v: max(0, v - 120)))
    d = ImageDraw.Draw(img)
    # sawtooth bands: right triangles stacked down both edges, from 60 cm to 300 cm
    band, tooth = 70, 64
    for edge in (0, W):
        y = px(30)
        while y + tooth <= px(270):
            if edge == 0:
                d.polygon([(0, y), (band, y + tooth / 2), (0, y + tooth)], fill=BLUE)
            else:
                d.polygon([(W, y), (W - band, y + tooth / 2), (W, y + tooth)], fill=BLUE)
            y += tooth
    # zone plate: blue panel with the label in white, 120-175 cm below the slab
    top, bottom = px(95), px(155)
    d.rounded_rectangle([96, top, W - 96, bottom], radius=14, fill=BLUE)
    f = font(int((bottom - top) * 0.62), latin=True)
    tw, th = d.textbbox((0, 0), label, font=f)[2:]
    d.text(((W - tw) / 2, top + (bottom - top - th) / 2 - 8), label, fill=(255, 255, 255), font=f)
    # level marker under the plate
    f2 = font(46)
    t2 = "4F"
    tw2 = d.textbbox((0, 0), t2, font=f2)[2]
    d.text(((W - tw2) / 2, bottom + 18), t2, fill=BLUE, font=f2)
    # yellow / black guard at the foot (0-90 cm)
    g0 = px(240)
    stripe = 56
    for k in range(-H, W + H, stripe * 2):
        d.polygon([(k, H), (k + stripe, H), (k + stripe + (H - g0), g0), (k + (H - g0), g0)], fill=(236, 186, 20))
    d.rectangle([0, g0, W, H], outline=None)
    guard = img.crop((0, g0, W, H))
    gd = ImageDraw.Draw(guard)
    for k in range(-400, W + 400, stripe * 2):
        gd.polygon([(k, guard.height), (k + stripe, guard.height), (k + stripe + guard.height, 0), (k + guard.height, 0)], fill=(25, 25, 25))
    img.paste(guard, (0, g0))
    # grime at the very bottom
    grime = Image.new("L", (W, H), 0)
    ImageDraw.Draw(grime).rectangle([0, H - px(8), W, H], fill=90)
    grime = grime.filter(ImageFilter.GaussianBlur(10))
    img = Image.composite(Image.new("RGB", (W, H), (60, 58, 55)), img, grime)
    img.save(path)


def sign_texture(path, lines, w=1600, h=400, bg=(18, 26, 38), fg=(255, 255, 255), icon="P"):
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    s = int(h * 0.62)
    if icon:
        d.rounded_rectangle([40, (h - s) // 2, 40 + s, (h + s) // 2], radius=24, fill=BLUE)
        f = font(int(s * 0.8), latin=True)
        tw, th = d.textbbox((0, 0), icon, font=f)[2:]
        d.text((40 + (s - tw) / 2, (h - s) / 2 + (s - th) / 2 - s * 0.08), icon, fill=(255, 255, 255), font=f)
    x = 80 + s if icon else 60
    big, small = lines
    d.text((x, h * 0.16), big, fill=fg, font=font(int(h * 0.36)))
    d.text((x, h * 0.6), small, fill=(170, 186, 204), font=font(int(h * 0.2), latin=True))
    img.save(path)


def exit_texture(path, w=512, h=256):
    img = Image.new("RGB", (w, h), (20, 170, 80))
    d = ImageDraw.Draw(img)
    # running figure (simple) and door
    d.rectangle([w * 0.62, h * 0.18, w * 0.86, h * 0.82], outline=(255, 255, 255), width=10)
    cx, cy = w * 0.38, h * 0.5
    d.ellipse([cx - 18, cy - 92, cx + 18, cy - 56], fill=(255, 255, 255))
    for a, b in (((cx, cy - 50), (cx - 10, cy + 20)), ((cx - 10, cy + 20), (cx - 60, cy + 80)), ((cx - 10, cy + 20), (cx + 40, cy + 82)),
                 ((cx, cy - 40), (cx + 50, cy - 10)), ((cx, cy - 40), (cx - 50, cy - 20))):
        d.line([a, b], fill=(255, 255, 255), width=18)
    d.text((24, 16), "비상구", fill=(255, 255, 255), font=font(40))
    img.save(path)


# --- geometry -----------------------------------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    L = json.load(open(os.path.join(S.OUT_DIR, "layout.json")))
    deck, bay, ramp, lobby = L["deck"], L["bay"], L["ramp"], L["lobby"]
    slab, beam = L["slab"], L["beam"]
    meshes, placements, lights, props, textures = [], [], [], [], {}

    # floor slab (deck + bay), walkable
    floor = Mesh("SM_PT_Floor", "complex")
    floor.box("Floor", deck["x0"] - 30, deck["x1"], deck["y0"] - 30, deck["y1"] + 30, -40, 0, faces="t")
    floor.box("Floor", bay["x0"], bay["x1"] + 30, bay["y0"], bay["y1"], -40, 0, faces="t")
    meshes.append(floor)

    # paint
    paint = Mesh("SM_PT_Paint")
    colors = {"white": "PaintWhite", "red": "PaintRed", "blue": "PaintBlue", "green": "PaintGreen", "yellow": "PaintYellow"}
    order = {"red": 0, "green": 0, "blue": 1, "white": 2, "yellow": 2}
    for shp in sorted(L["paint"], key=lambda s: order[s["color"]]):
        paint.polygon(colors[shp["color"]], shp["poly"], PAINT_Z + 0.08 * order[shp["color"]])
    for x0, x1, y0, y1 in L["speed_bumps"]:
        y, k = y0, 0
        while y < y1 - 1:
            paint.polygon("PaintYellow" if k % 2 == 0 else "PaintBlack", [(x0, y), (x1, y), (x1, min(y + 50, y1)), (x0, min(y + 50, y1))], PAINT_Z + 0.2)
            y += 50
            k += 1
    meshes.append(paint)

    # slab, beams (one grid: main beams on the column rows along X, cross beams on the column lines along Y)
    ceiling = Mesh("SM_PT_Ceiling", "complex")
    ceiling.box("Ceiling", deck["x0"] - 30, bay["x1"] + 30, deck["y0"] - 30, deck["y1"] + 30, slab, slab + 40, faces="b")
    bz = slab - beam["depth"]
    for y in L["columns_y"]:
        ceiling.box("Ceiling", deck["x0"], deck["x1"], y - beam["width"] / 2, y + beam["width"] / 2, bz, slab, faces="bns")
    for x in L["columns_x"]:
        ceiling.box("Ceiling", x - beam["width"] / 2, x + beam["width"] / 2, deck["y0"], deck["y1"], bz, slab, faces="bew")
    # edge beams along the walls
    ceiling.box("Ceiling", deck["x0"], deck["x1"], deck["y0"], deck["y0"] + 40, bz, slab, faces="bn")
    ceiling.box("Ceiling", deck["x0"], deck["x1"], deck["y1"] - 40, deck["y1"], bz, slab, faces="bs")
    meshes.append(ceiling)

    # walls: concrete, 25 cm thick, with the openings onto the ramp and the bay
    walls = Mesh("SM_PT_Walls", "complex")
    t = 25
    H = slab + 40
    walls.box("Wall", deck["x0"], deck["x1"], deck["y0"] - t, deck["y0"], -40, H, faces="n")
    walls.box("Wall", deck["x0"], deck["x1"], deck["y1"], deck["y1"] + t, -40, H, faces="s")
    walls.box("Wall", deck["x0"] - t, deck["x0"], deck["y0"], deck["y1"], -40, H, faces="e")
    walls.box("Wall", deck["x1"], deck["x1"] + t, deck["y0"], ramp["y0"], -40, H, faces="w")
    walls.box("Wall", deck["x1"], deck["x1"] + t, bay["y1"], deck["y1"], -40, H, faces="w")
    # bay: back and side walls, a short pier between bay and ramp
    walls.box("Wall", bay["x1"], bay["x1"] + t, bay["y0"], bay["y1"], -40, H, faces="w")
    walls.box("Wall", bay["x0"], bay["x1"], bay["y1"], bay["y1"] + t, -40, H, faces="s")
    walls.box("Wall", bay["x0"], bay["x1"], bay["y0"] - t, bay["y0"], -40, H, faces="ns")
    # lift lobby corner: two walls with a door
    walls.box("Wall", lobby["x1"], lobby["x1"] + t, lobby["y0"], lobby["y1"], -40, H, faces="we")
    walls.box("Wall", lobby["x0"], lobby["x1"] + t, lobby["y1"], lobby["y1"] + t, -40, H, faces="ns")
    meshes.append(walls)
    # dark skirting along the walls (10 cm), separate material
    skirt = Mesh("SM_PT_Skirting")
    for x0, x1, y0, y1 in ((deck["x0"], deck["x1"], deck["y0"], deck["y0"] + 2), (deck["x0"], deck["x1"], deck["y1"] - 2, deck["y1"]),
                           (deck["x0"], deck["x0"] + 2, deck["y0"], deck["y1"])):
        skirt.box("Skirting", x0, x1, y0, y1, 0, 12)
    meshes.append(skirt)

    # ramp down beside the bay: sloping floor into the dark, side walls with red chevrons, its own ceiling
    ramp_mesh = Mesh("SM_PT_Ramp")
    drop = 160
    x0, x1, y0, y1 = ramp["x0"], ramp["x1"] + 600, ramp["y0"], ramp["y1"]
    ramp_mesh.quad("Floor", [(x0, y0, 0), (x1, y0, -drop - 180), (x1, y1, -drop - 180), (x0, y1, 0)][::-1],
                   [(0, 0), (0, 10), (8, 10), (8, 0)][::-1])
    ramp_mesh.box("Wall", x0, x1, y0 - t, y0, -drop - 200, H, faces="n")
    ramp_mesh.box("Wall", x0, x1, y1, y1 + t, -drop - 200, H, faces="s")
    ramp_mesh.box("Ceiling", x0, x1, y0, y1, slab, slab + 40, faces="b")
    ramp_mesh.box("Black", x1, x1 + 10, y0, y1, -drop - 200, H, faces="w")
    meshes.append(ramp_mesh)

    # shared meshes placed many times
    col = Mesh("SM_PT_Column")
    c = L["columns"][0]["size"]
    col.box("Column", -c / 2, c / 2, -c / 2, c / 2, 0, slab - beam["depth"], faces="nsew", unit_uv=True)
    meshes.append(col)
    rows = "ABC"
    for i, x in enumerate(L["columns_x"]):
        for j, y in enumerate(L["columns_y"]):
            label = f"{rows[j]}{i + 1}"
            path = os.path.join(OUT, f"T_Column_{label}.png")
            column_texture(label, path)
            textures[f"Column_{label}"] = path
            placements.append({"mesh": "SM_PT_Column", "at": [x, y, 0], "yaw": 0, "material": f"Column_{label}", "collision": True})

    stop = Mesh("SM_PT_WheelStop")
    stop.box("Rubber", -8, 8, -30, -18, 0, 10)
    stop.box("RubberYellow", -8, 8, -18, -10, 0, 10)
    stop.box("Rubber", -8, 8, -10, 10, 0, 10)
    stop.box("RubberYellow", -8, 8, 10, 18, 0, 10)
    stop.box("Rubber", -8, 8, 18, 30, 0, 10)
    meshes.append(stop)
    for w in L["wheelstops"]:
        placements.append({"mesh": "SM_PT_WheelStop", "at": [*w["center"], 0], "yaw": 0 if w["along"] == "x" else 90, "collision": False})

    fixture = Mesh("SM_PT_Fixture")
    fixture.box("FixtureBody", -62, 62, -6, 6, 4, 9)
    fixture.box("LED", -60, 60, -4, 4, 2, 4, faces="b")
    fixture.box("FixtureBody", -1, 1, -1, 1, 9, slab - FIXTURE_Z, faces="nsew")
    meshes.append(fixture)
    # fixtures: three per column bay along X, over the lanes; the light comes from a rect light at each one
    lanes = [-1010, -440, 140, 620, 1240]
    xs = []
    for i in range(len(L["columns_x"]) - 1):
        for f in (1 / 6, 3 / 6, 5 / 6):
            xs.append(L["columns_x"][i] + (L["columns_x"][i + 1] - L["columns_x"][i]) * f)
    xs += [L["columns_x"][0] - 260, L["columns_x"][-1] + 300]
    for y in lanes:
        for x in xs:
            placements.append({"mesh": "SM_PT_Fixture", "at": [x, y, FIXTURE_Z], "yaw": 90, "collision": False})
            lights.append({"at": [x, y, FIXTURE_Z + 1], "yaw": 90, "length": 120, "width": 8})
    for y in (-1010, -440, 140, 620, 1240):
        for x in (-3360, -3330 + 0):
            pass
    # near cross aisle and far bay
    for y in (-450, 150, 650, 1150):
        placements.append({"mesh": "SM_PT_Fixture", "at": [-2830, y, FIXTURE_Z], "yaw": 0, "collision": False})
        lights.append({"at": [-2830, y, FIXTURE_Z + 1], "yaw": 0, "length": 120, "width": 8})
        placements.append({"mesh": "SM_PT_Fixture", "at": [3470, y, FIXTURE_Z], "yaw": 0, "collision": False})
        lights.append({"at": [3470, y, FIXTURE_Z + 1], "yaw": 0, "length": 120, "width": 8})
    placements.append({"mesh": "SM_PT_Fixture", "at": [4010, 430, FIXTURE_Z], "yaw": 90, "collision": False})
    lights.append({"at": [4010, 430, FIXTURE_Z + 1], "yaw": 90, "length": 120, "width": 8})

    # services under the slab: red sprinkler mains, grey cable tray, thin branch pipes
    services = Mesh("SM_PT_Services")
    for y in (-600, 1080):
        services.cylinder("PipeRed", (deck["x0"] + 40, y, 262), (deck["x1"] - 40, y, 262), 7, 12)
        for x in L["columns_x"]:
            services.box("Hanger", x + 300 - 1, x + 300 + 1, y - 1, y + 1, 262, slab, faces="nsew")
    for x in L["columns_x"][:-1]:
        services.cylinder("PipeRed", (x + 516, deck["y0"] + 60, 300), (x + 516, deck["y1"] - 60, 300), 3, 8)
    services.box("Tray", deck["x0"] + 40, deck["x1"] - 40, 360 - 20, 360 + 20, 290, 296)
    services.box("Tray", deck["x0"] + 40, deck["x1"] - 40, 360 - 21, 360 - 19, 290, 302, faces="nsew")
    services.box("Tray", deck["x0"] + 40, deck["x1"] - 40, 360 + 19, 360 + 21, 290, 302, faces="nsew")
    meshes.append(services)

    # signs: hanging boards over the aisles, exit signs over the lobby door and at the far end
    sign = Mesh("SM_PT_SignBoard")
    sign.box("SignFrame", -100, 100, -4, 4, -50, 0, faces="tbew")
    sign.box("SignFace", -100, 100, -4, 4, -50, 0, faces="ns", unit_uv=True)
    sign.box("SignFrame", -70, -68, -1, 1, 0, 40, faces="nsew")
    sign.box("SignFrame", 68, 70, -1, 1, 0, 40, faces="nsew")
    meshes.append(sign)
    sign_texture(os.path.join(OUT, "T_Sign_Level.png"), ("4층 주차장", "4F  PARKING"))
    textures["Sign_Level"] = os.path.join(OUT, "T_Sign_Level.png")
    for x, y, yaw in ((-1560, -440, 90), (1540, 1240, 90), (2600, -440, 90), (-2830, 400, 0)):
        placements.append({"mesh": "SM_PT_SignBoard", "at": [x, y, 285], "yaw": yaw, "material": "Sign_Level", "collision": False})
    ex = Mesh("SM_PT_Exit")
    ex.box("ExitBody", -20, 20, -5, 5, 0, 20, faces="tbew")
    ex.box("ExitFace", -20, 20, -5, 5, 0, 20, faces="ns", unit_uv=True)
    meshes.append(ex)
    exit_texture(os.path.join(OUT, "T_Exit.png"))
    textures["Exit"] = os.path.join(OUT, "T_Exit.png")
    placements.append({"mesh": "SM_PT_Exit", "at": [-3350, lobby["y1"] + 30, 240], "yaw": 0, "material": "Exit", "collision": False})
    placements.append({"mesh": "SM_PT_Exit", "at": [deck["x1"] - 10, -1050, 240], "yaw": 90, "material": "Exit", "collision": False})

    # lobby door: a steel door leaf in the lobby wall
    door = Mesh("SM_PT_Door")
    door.box("Door", -60, 60, -2, 2, 0, 215)
    door.box("SignFrame", -66, 66, -3, 3, 215, 222)
    meshes.append(door)
    placements.append({"mesh": "SM_PT_Door", "at": [-3350, lobby["y1"] + t + 2, 0], "yaw": 0, "collision": False})

    # props: covered cars in most stalls (kept free: the stalls with coins), extinguishers at columns, cameras
    stage = json.load(open(os.path.join(S.GENERATED, "ParkingTower_stage.json")))
    coin_xy = [c[:2] for c in stage["coins"]] + [stage["gem"][:2]]
    keep_free = lambda s: any(s[0] - 40 <= x <= s[1] + 40 and s[2] - 40 <= y <= s[3] + 40 for x, y in coin_xy)
    rng = random.Random(7)
    car_parts = ["covered_car", "covered_car_wheel_01", "covered_car_wheel_02", "covered_car_wheel_03", "covered_car_wheel_04"]
    for x0, x1, y0, y1, kind in L["stalls"]:
        if kind not in ("normal", "bay") or keep_free((x0, x1, y0, y1)) or rng.random() < 0.28:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        deep_y = (y1 - y0) > (x1 - x0)
        # the model is 4.38 m long along its Y; facing out of the stall, a little jitter
        yaw = (0 if deep_y else 90) + (180 if rng.random() < 0.5 else 0) + rng.uniform(-2.5, 2.5)
        props.append({"meshes": [f"/Game/CityKit/covered_car/covered_car_1k/StaticMeshes/{p}" for p in car_parts],
                      "at": [cx + rng.uniform(-8, 8), cy + rng.uniform(-8, 8), 0], "yaw": yaw, "collision": True,
                      "box": [x0 + 30, x1 - 30, y0 + 30, y1 - 30, 0, 150]})
    for i, x in enumerate(L["columns_x"]):
        if i % 2 == 0:
            props.append({"meshes": ["/Game/CityKit/korean_fire_extinguisher_01/korean_fire_extinguisher_01_1k/StaticMeshes/korean_fire_extinguisher_01_1k"],
                          "at": [x + 52, -780 + 20, 0], "yaw": 90, "collision": False})
    data = {"meshes": [m.to_json() for m in meshes], "placements": placements, "lights": lights, "props": props,
            "textures": textures, "slab": slab, "deck": deck, "bay": bay, "ramp": ramp}
    json.dump(data, open(os.path.join(OUT, "rebuild.json"), "w"))
    print(f"{len(meshes)} meshes, {len(placements)} placements, {len(lights)} lights, {len(props)} props, "
          f"{sum(len(s['indices']) // 3 for m in meshes for s in m.sections.values())} triangles")


if __name__ == "__main__":
    main()
