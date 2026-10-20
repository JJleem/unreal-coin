"""
Builds the reimagined Hongdae's data for Unreal (build_reimagined_level.py):

  * the reference buildings (hongdae_buildings.py) as meshes: SourceAssets/Rebuilt/Hongdae_Reimagined/meshes.json
  * their kit props (Poly Haven models): props.json
  * sign faces drawn with real fonts (signs.py): textures/sign_*.png
  * the material list with the PBR sets and target albedos (tints worked out from each texture's average colour,
    white balanced like zone A so meshes and splats agree): materials.json
  * the scan for the level: zone A's high quality scan (scanned buildings kept) minus every splat inside the rebuilt
    buildings and on their facades, signs and awnings: Hongdae_Reimagined.ply; the share of the scan kept is reported

  python build_reimagined.py
"""

import json
import os
import sys
import time

import numpy as np
import shapely
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from rebuild import meshkit  # noqa: E402
from rebuild.common import OUT_DIR, Scan, write_ply  # noqa: E402
import hongdae_buildings  # noqa: E402
import signs  # noqa: E402

SOURCE = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets"))
OUT = os.path.join(OUT_DIR, "Hongdae_Reimagined")
PH = os.path.join(SOURCE, "PolyHaven", "textures")
ACG = os.path.join(SOURCE, "Textures", "pbr")
CALIBRATION = json.load(open(os.path.join(HERE, "..", "rebuild", "zones", "Hongdae_A_calibration.json")))

# surface -> (texture set, tile size m, target linear albedo, metallic, roughness scale, weathering)
# Sets: Poly Haven ids (SourceAssets/PolyHaven/textures) or ambientCG sets (SourceAssets/Textures/pbr), both CC0.
PBR = {
    "BrickWhite": ("painted_worn_brick", 1.8, (0.50, 0.49, 0.46), 0.0, 1.0, True),
    "TileBeige": ("rectangular_facade_tiles", 2.0, (0.40, 0.33, 0.25), 0.0, 0.8, True),
    "TileDark": ("concrete_tile_facade", 2.09, (0.055, 0.055, 0.06), 0.0, 0.7, True),
    "Granite": ("granite_tile", 2.3, (0.17, 0.165, 0.16), 0.0, 0.6, True),
    "ConcreteSide": ("concrete_wall_008", 2.71, (0.30, 0.29, 0.27), 0.0, 1.0, True),
    "Coping": ("grey_plaster", 1.0, (0.42, 0.42, 0.40), 0.0, 1.0, False),
    "Trim": ("painted_plaster_wall", 2.0, (0.52, 0.52, 0.50), 0.0, 0.9, False),
    "PlasterCream": ("painted_plaster_wall", 2.0, (0.52, 0.47, 0.38), 0.0, 1.0, True),
    "CladRed": ("Metal063", 2.0, (0.19, 0.06, 0.045), 0.25, 0.8, True),
    "BrickRed": ("red_brick", 1.4, (0.20, 0.09, 0.06), 0.0, 1.0, True),
    "RoofTiles": ("grey_roof_tiles", 3.0, (0.12, 0.10, 0.09), 0.0, 1.0, False),
    "RoofDeck": ("dirty_concrete", 3.0, (0.09, 0.20, 0.12), 0.0, 0.8, False),     # green waterproofing paint
    "Awning": ("box_profile_metal_sheet", 2.0, (0.33, 0.33, 0.32), 0.5, 0.8, False),
    "AwningUnder": ("box_profile_metal_sheet", 2.0, (0.20, 0.20, 0.20), 0.5, 0.9, False),
    "Sill": ("granite_tile", 2.3, (0.30, 0.29, 0.28), 0.0, 0.6, False),
    "DoorSteel": ("painted_metal_shutter", 2.0, (0.20, 0.22, 0.25), 0.3, 0.8, False),
}
# surface -> (linear colour, metallic, roughness, emissive strength in units of the stage exposure)
FLAT = {
    "PanelBlack": ((0.015, 0.015, 0.016), 0.3, 0.35, 0.0),
    "PanelBrown": ((0.05, 0.028, 0.02), 0.2, 0.45, 0.0),
    "PanelCream": ((0.62, 0.57, 0.47), 0.0, 0.4, 0.0),
    "PaintRed": ((0.55, 0.02, 0.025), 0.0, 0.3, 0.6),     # light box: its face glows a little
    "LetterWhite": ((0.85, 0.85, 0.84), 0.0, 0.3, 1.2),
    "LetterPurple": ((0.17, 0.045, 0.27), 0.0, 0.35, 0.2),
    "LetterGold": ((0.80, 0.55, 0.20), 0.35, 0.3, 0.5),    # gold painted acrylic, lit
    "LetterSideGold": ((0.45, 0.30, 0.12), 0.6, 0.4, 0.0),
    "LetterSide": ((0.03, 0.03, 0.03), 0.6, 0.4, 0.0),
    "SignFrame": ((0.03, 0.03, 0.032), 0.7, 0.45, 0.0),
    "WinFrame": ((0.62, 0.62, 0.6), 0.3, 0.4, 0.0),
    "AluDark": ((0.035, 0.035, 0.04), 0.8, 0.35, 0.0),
    "Alu": ((0.5, 0.5, 0.5), 0.9, 0.4, 0.0),
    "Grille": ((0.62, 0.62, 0.6), 0.2, 0.5, 0.0),
    "GrilleDark": ((0.04, 0.04, 0.04), 0.4, 0.5, 0.0),
    "Stainless": ((0.7, 0.7, 0.7), 1.0, 0.25, 0.0),
    "Steel": ((0.33, 0.33, 0.33), 0.8, 0.55, 0.0),
    "Pipe": ((0.5, 0.5, 0.48), 0.0, 0.5, 0.0),
    "GasPipe": ((0.72, 0.5, 0.015), 0.0, 0.45, 0.0),
    "Cable": ((0.012, 0.012, 0.012), 0.0, 0.6, 0.0),
    "PipeTape": ((0.6, 0.6, 0.58), 0.0, 0.7, 0.0),
    "Gutter": ((0.38, 0.38, 0.38), 0.7, 0.5, 0.0),
    "Rail": ((0.06, 0.06, 0.06), 0.6, 0.5, 0.0),
    "MeterBox": ((0.45, 0.45, 0.43), 0.2, 0.5, 0.0),
    "MeterFace": ((0.05, 0.05, 0.05), 0.0, 0.2, 0.0),
    "TankBlue": ((0.04, 0.12, 0.35), 0.0, 0.4, 0.0),
    "Counter": ((0.45, 0.43, 0.4), 0.0, 0.5, 0.0),
    "CounterTop": ((0.04, 0.04, 0.04), 0.0, 0.2, 0.0),
    "CounterGlass": ((0.3, 0.32, 0.33), 0.0, 0.1, 0.0),
    # rooms behind the glass glow faintly (warm, as if lit inside): the level has no interior lights
    "RoomFloor": ((0.25, 0.25, 0.25), 0.0, 0.4, 0.12),
    "RoomFloorTile": ((0.42, 0.41, 0.40), 0.0, 0.3, 0.14),
    "RoomFloorWood": ((0.22, 0.13, 0.07), 0.0, 0.45, 0.2),
    "RoomWall": ((0.45, 0.44, 0.42), 0.0, 0.9, 0.18),
    "RoomWallWhite": ((0.62, 0.62, 0.60), 0.0, 0.9, 0.18),
    "RoomWallWarm": ((0.45, 0.35, 0.25), 0.0, 0.9, 0.25),
    "RoomCeiling": ((0.7, 0.7, 0.7), 0.0, 0.9, 0.2),
    "RoomCeilingDark": ((0.04, 0.04, 0.04), 0.0, 0.9, 0.0),
    "RoomLight": ((1.0, 1.0, 1.0), 0.0, 0.5, 2.5),
    "Blind": ((0.7, 0.68, 0.63), 0.0, 0.8, 0.0),
    "ShopPanel": ((0.55, 0.53, 0.5), 0.0, 0.6, 0.15),
    "ShopShelf": ((0.6, 0.6, 0.6), 0.2, 0.4, 0.1),
    "ProductA": ((0.05, 0.05, 0.06), 0.0, 0.6, 0.0),
    "ProductB": ((0.6, 0.58, 0.55), 0.0, 0.7, 0.05),
    "ProductC": ((0.35, 0.05, 0.05), 0.0, 0.6, 0.0),
    "ProductD": ((0.08, 0.12, 0.3), 0.0, 0.6, 0.0),
    "ProductE": ((0.45, 0.35, 0.22), 0.0, 0.7, 0.0),
    "ProductF": ((0.12, 0.25, 0.15), 0.0, 0.6, 0.0),
}


WARM = (1.0, 0.86, 0.68)   # interior light colour (about 3000 K)


def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def texture_files(set_name):
    folder = os.path.join(PH, set_name)
    if os.path.isdir(folder):
        files = {k: os.path.join(folder, f"{set_name}_{k}.jpg") for k in ("Color", "NormalDX", "Roughness", "AmbientOcclusion")}
        return {k: v for k, v in files.items() if os.path.exists(v)}, "Poly Haven"
    files = {k: os.path.join(ACG, f"{set_name}_{k}.jpg") for k in ("Color", "NormalDX", "Roughness", "AmbientOcclusion")}
    return {k: v for k, v in files.items() if os.path.exists(v)}, "ambientCG"


def material_list():
    materials = {}
    # half of zone A's white balance: its tints matched scan colours, these targets are real albedos (the full
    # balance turned whites lavender)
    balance = np.array(CALIBRATION["white_balance"]) ** 0.5
    for name, (set_name, tile, albedo, metallic, rough, weather) in PBR.items():
        files, source = texture_files(set_name)
        avg = srgb_to_linear(np.asarray(Image.open(files["Color"]).convert("RGB").resize((256, 256)), float) / 255).reshape(-1, 3).mean(0)
        tint = np.asarray(albedo) / np.maximum(avg, 1e-3) * balance
        materials[name] = {"kind": "pbr", "set": set_name, "source": source, "files": files, "tile": tile,
                           "tint": tint.round(4).tolist(), "metallic": metallic, "rough": rough, "weather": weather}
    for name, (colour, metallic, rough, emissive) in FLAT.items():
        glow = WARM if name.startswith("Room") and name != "RoomLight" else (1.0, 1.0, 1.0)
        materials[name] = {"kind": "flat", "colour": (np.asarray(colour) * balance).round(4).tolist(), "metallic": metallic,
                           "rough": rough, "emissive": emissive, "glow": list(glow)}
    materials["Glass"] = {"kind": "glass"}
    return materials


def removal_mask(scan, buildings):
    """Splats inside the rebuilt buildings and on their facades (walls, signs, awnings standing out to `reach`)."""
    xy, z = scan.pos[:, :2], scan.pos[:, 2]
    remove = np.zeros(len(z), bool)
    for b in buildings:
        inside = shapely.contains_xy(b.footprint.buffer(0.15), xy[:, 0], xy[:, 1]) & (z > b.ground - 1.5) & (z < b.top + 2.0)
        remove |= inside
        for F, s0, s1, z0, z1, reach in b.removal["front"] + b.removal["extra"]:
            rel = xy - F.a
            s = rel @ F.u
            d = -(rel @ F.n)
            remove |= (s > s0 - 0.25) & (s < s1 + 0.25) & (d > -reach) & (d < 0.4) & (z > z0) & (z < z1)
    return remove


def main():
    t0 = time.time()
    os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
    sign_files = signs.make_all(os.path.join(OUT, "textures"))
    buildings = hongdae_buildings.all_buildings()
    meshes = [m for b in buildings for m in b.meshes()]
    meshkit.save(meshes, os.path.join(OUT, "meshes.json"))
    props = []
    for b in buildings:
        for p in b.props:
            parts = hongdae_buildings.MULTI.get(p["model"], [p["model"]])
            props.append(dict(p, building=b.name, parts=parts))
    with open(os.path.join(OUT, "props.json"), "w") as f:
        json.dump(props, f, indent=1)

    materials = material_list()
    for name, path in sign_files.items():
        materials[f"Sign_{name}"] = {"kind": "image", "file": path, "emissive": 0.25}
    used = {s["material"] for m in meshes for s in m.to_json()["sections"]}
    missing = sorted(used - set(materials))
    if missing:
        raise SystemExit(f"materials missing: {missing}")
    with open(os.path.join(OUT, "materials.json"), "w") as f:
        json.dump({k: v for k, v in materials.items() if k in used}, f, indent=1)

    scan = Scan("Hongdae")
    zone_a = np.unpackbits(np.load(os.path.join(OUT_DIR, "Hongdae_A", "removed_keepbuilding.npy")))[:len(scan.opacity)].astype(bool)
    rebuilt = removal_mask(scan, buildings)
    keep = ~(zone_a | rebuilt)
    write_ply(os.path.join(OUT, "Hongdae_Reimagined.ply"), scan.header, scan.data[keep])

    stats = {
        "buildings": {b.name: {"triangles": {m.name: sum(len(s["i"]) // 3 for s in m.sections.values()) for m in b.meshes()},
                               "props": len(b.props), "splats_removed": int((removal_mask(scan, [b]) & ~zone_a).sum())}
                      for b in buildings},
        "materials": len(used), "signs": len(sign_files),
        "scan": {"cleaned": int(len(keep)), "zone_a_removed": int(zone_a.sum()), "buildings_removed": int((rebuilt & ~zone_a).sum()),
                 "kept": int(keep.sum())},
    }
    with open(os.path.join(OUT, "reimagined.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats, indent=1))
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
