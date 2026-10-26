"""
Data for the night Hongdae (build_night_level.py): every building of the red street as CG, no scan.

  ~/.venvs/gs/bin/python -I build_night.py

  * buildings: the three reimagined reference buildings (reimagined/hongdae_buildings.py) and the rest of the street
    (night_buildings.py) -> SourceAssets/Rebuilt/Hongdae_Night/meshes.json, props.json
  * sign faces (reimagined/signs.py and night_buildings.make_signs) -> textures/
  * materials.json: the reimagined surfaces plus the new ones, with night emissive strengths (light boxes, LED
    letters, lit rooms bright; unlit rooms dark), in units of the night level's exposure
  * lights.json: shop front rect lights, window rect lights, sign glow point lights of every building
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "reimagined"))
sys.path.insert(0, os.path.join(HERE, ".."))
from rebuild import meshkit  # noqa: E402
from rebuild.common import OUT_DIR  # noqa: E402
import build_reimagined as R  # noqa: E402
import hongdae_buildings  # noqa: E402
import night_buildings  # noqa: E402
import signs  # noqa: E402

OUT = os.path.join(OUT_DIR, "Hongdae_Night")

# new surfaces: (texture set, tile m, target linear albedo, metallic, roughness scale, weathering)
R.PBR.update({
    "PlasterWhite": ("white_plaster_rough_01", 2.0, (0.55, 0.55, 0.53), 0.0, 1.0, True),
    "CladGrey": ("exterior_wall_cladding", 2.0, (0.22, 0.23, 0.24), 0.2, 0.8, True),
    "SidingWhite": ("exterior_wall_cladding", 1.6, (0.55, 0.55, 0.53), 0.1, 0.8, True),
    "PaintGreen": ("painted_plaster_wall", 2.0, (0.04, 0.32, 0.14), 0.0, 0.9, True),
    "PaintPink": ("painted_plaster_wall", 2.0, (0.55, 0.16, 0.30), 0.0, 0.9, True),
    "TileWhite": ("rectangular_facade_tiles_02", 2.0, (0.48, 0.47, 0.45), 0.0, 0.7, True),
    "Shutter": ("painted_metal_shutter", 2.0, (0.30, 0.31, 0.32), 0.4, 0.8, True),
})
# night emissive strengths (units of the level's exposure: 1 reads as full white)
NIGHT_EMISSIVE = {
    "PaintRed": 1.2, "LetterWhite": 3.0, "LetterGold": 1.6, "LetterPurple": 0.6,
    "RoomLight": 8.0, "RoomWall": 0.12, "RoomWallWhite": 0.14, "RoomWallWarm": 0.16, "RoomCeiling": 0.12,
    "RoomFloor": 0.12, "RoomFloorTile": 0.18, "RoomFloorWood": 0.15, "ShopPanel": 0.2, "ShopShelf": 0.15,
}
R.FLAT.update({
    "RoomWallDark": ((0.12, 0.11, 0.10), 0.0, 0.9, 0.0),
    "RoomFloorDark": ((0.08, 0.07, 0.06), 0.0, 0.6, 0.0),
    "TableTop": ((0.5, 0.45, 0.38), 0.0, 0.4, 0.0),
    "StoolRed": ((0.45, 0.03, 0.03), 0.0, 0.5, 0.0),
    "LetterWarm": ((0.95, 0.75, 0.45), 0.0, 0.3, 3.0),
})
SIGN_EMISSIVE = 2.4

# shop fronts and lit windows of the three reference buildings (they were made for the day level)
REFERENCE_LIGHTS = [
    {"type": "rect", "pos": [13.6, -1.0, -0.6], "yaw": 90.0, "w": 3.2, "h": 1.8, "color": [1.0, 0.92, 0.85], "intensity": 1.0},   # SOLB
    {"type": "rect", "pos": [13.6, -1.0, 2.3], "yaw": 90.0, "w": 3.2, "h": 1.0, "color": [1.0, 0.8, 0.55], "intensity": 0.5},     # vape 2F
    {"type": "rect", "pos": [9.3, -2.9, -0.6], "yaw": 135.0, "w": 3.6, "h": 1.8, "color": [1.0, 0.82, 0.6], "intensity": 1.0},    # BIBIANG corner
    {"type": "rect", "pos": [8.0, -7.6, -0.6], "yaw": 180.0, "w": 2.6, "h": 1.8, "color": [1.0, 0.82, 0.6], "intensity": 0.8},    # BIBIANG side
    {"type": "rect", "pos": [9.6, 9.9, -1.4], "yaw": -90.0, "w": 1.6, "h": 1.8, "color": [1.0, 0.95, 0.9], "intensity": 0.8},     # eyewear door
    {"type": "rect", "pos": [6.4, 12.6, -1.4], "yaw": 180.0, "w": 4.6, "h": 1.8, "color": [1.0, 0.95, 0.9], "intensity": 1.0},    # eyewear side
    {"type": "rect", "pos": [10.4, 9.9, 1.9], "yaw": -90.0, "w": 4.0, "h": 1.6, "color": [1.0, 0.75, 0.48], "intensity": 0.9},    # Coffee Bean front
    {"type": "rect", "pos": [6.4, 12.9, 1.9], "yaw": 180.0, "w": 5.6, "h": 1.6, "color": [1.0, 0.75, 0.48], "intensity": 0.9},    # Coffee Bean side
    {"type": "point", "pos": [13.6, 0.4, 0.4], "color": [1.0, 0.25, 0.25], "intensity": 1.0, "radius": 7.0},                     # SOLB box sign
    {"type": "point", "pos": [8.6, -2.0, 0.6], "color": [1.0, 0.8, 0.45], "intensity": 0.6, "radius": 6.0},                       # BIBIANG letters
    {"type": "point", "pos": [9.0, 8.4, 0.5], "color": [0.9, 0.95, 1.0], "intensity": 0.6, "radius": 6.0},                        # BLUE ELEPHANT letters
]


# gameplay inside the rebuilt street (the stage's own course lies west of the intersection, which isn't rebuilt):
# coins along the red street, a jump pad up onto the one storey Tax-Free shop's roof with a coin, the gem hidden
# behind its parapet; invisible walls where the rebuilt part ends
COINS = [(4.0, 2.0), (9.0, 3.2), (13.0, 1.6), (17.4, 4.4), (21.0, 1.2), (24.0, 4.6), (28.0, 2.4), (31.0, -2.6),
         (35.0, 3.4), (39.0, 0.6), (43.0, 3.0), (47.5, 1.2), (52.0, 3.4), (56.0, 1.0)]
PAD = {"at": (16.9, 1.4), "target": (17.1, -4.6, 1.45)}
ROOF_COIN = (17.1, -5.8, 2.45)
GEM = (15.9, -8.7, 2.45)
WALLS = [(-13.4, -12.8, -12.0, 16.0), (58.4, 59.0, -6.0, 12.0), (-13.0, 8.0, -10.9, -10.3), (-13.0, 7.0, 13.4, 14.0)]


def gameplay():
    d = json.load(open(os.path.join(HERE, "..", "generated", "Hongdae_collision.json")))
    v = d["ground"]["vertices"]
    import numpy as np
    g = np.asarray(v, float) / 100.0

    def ground(x, y):
        k = np.argmin((g[:, 0] - x) ** 2 + (g[:, 1] - y) ** 2)
        return float(g[k, 2])
    cm = lambda p: [round(c * 100.0, 1) for c in p]
    coins = [cm((x, y, ground(x, y) + 1.0)) for x, y in COINS] + [cm(ROOF_COIN)]
    px, py = PAD["at"]
    # road beyond zone B (it ends at x = 46): continues the zone's edge heights level along X (the scan's floor
    # beyond is noise), 2 cm under zone B where they overlap
    ext = meshkit.Mesh("SM_Night_RoadExtension", collision="complex")
    xs, ys = np.arange(40.0, 59.6, 1.0), np.arange(-4.5, 9.6, 1.0)
    edge = [ground(45.0, y) - 0.02 for y in ys]
    H = [edge for x in xs]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            a, b = [xs[i], ys[j], H[i][j]], [xs[i + 1], ys[j], H[i + 1][j]]
            c, d_ = [xs[i + 1], ys[j + 1], H[i + 1][j + 1]], [xs[i], ys[j + 1], H[i][j + 1]]
            ext.quad(a, b, c, d_, [0, 0, 1], "NightRoadPlain")
    return {"coins": coins, "gem": cm(GEM), "pad": {"at": cm((px, py, ground(px, py))), "target": cm(PAD["target"])},
            "walls": [[x0 * 100, y0 * 100, -1000.0, x1 * 100, y1 * 100, 3000.0] for x0, x1, y0, y1 in WALLS],
            "extension": ext.to_json()}


def main():
    os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
    sign_files = signs.make_all(os.path.join(OUT, "textures"))
    sign_files.update(night_buildings.make_signs(os.path.join(OUT, "textures")))
    buildings = hongdae_buildings.all_buildings() + night_buildings.all_buildings()
    meshes = [m for b in buildings for m in b.meshes()]
    meshkit.save(meshes, os.path.join(OUT, "meshes.json"))
    props = []
    multi = dict(hongdae_buildings.MULTI)
    for b in buildings:
        for p in b.props:
            props.append(dict(p, building=b.name, parts=multi.get(p["model"], [p["model"]])))
    json.dump(props, open(os.path.join(OUT, "props.json"), "w"), indent=1)

    materials = R.material_list()
    for name, value in NIGHT_EMISSIVE.items():
        if name in materials:
            materials[name]["emissive"] = value
    for name, path in sign_files.items():
        materials[f"Sign_{name}"] = {"kind": "image", "file": path, "emissive": SIGN_EMISSIVE}
    used = {s["material"] for m in meshes for s in m.to_json()["sections"]}
    missing = sorted(used - set(materials))
    if missing:
        raise SystemExit(f"materials missing: {missing}")
    json.dump({k: v for k, v in materials.items() if k in used}, open(os.path.join(OUT, "materials.json"), "w"), indent=1)

    lights = list(REFERENCE_LIGHTS)
    for b in buildings:
        lights += getattr(b, "lights", [])
    json.dump(lights, open(os.path.join(OUT, "lights.json"), "w"), indent=1)
    json.dump(gameplay(), open(os.path.join(OUT, "gameplay.json"), "w"), indent=1)
    tris = sum(len(s["i"]) // 3 for m in meshes for s in m.sections.values())
    print(f"{len(buildings)} buildings, {len(meshes)} meshes, {tris} triangles, {len(props)} props, {len(used)} materials, "
          f"{len(sign_files)} signs, {len(lights)} lights")


if __name__ == "__main__":
    main()
