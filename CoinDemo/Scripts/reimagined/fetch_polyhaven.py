"""
Downloads the CC0 models and textures the reimagined Hongdae uses from Poly Haven's public API (https://polyhaven.com,
all assets CC0 1.0) into SourceAssets/PolyHaven/<id>/ (models, glTF) and SourceAssets/PolyHaven/textures/<id>/
(2k jpg: colour, DirectX normal, roughness, ambient occlusion), and appends them to SourceAssets/PolyHaven/LICENSE.txt.
Already downloaded assets are skipped.

  python fetch_polyhaven.py
"""

import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "PolyHaven"))

MODELS = {
    # building parts
    "rollershutter_door": "1k", "rollershutter_window_01": "1k", "modular_fire_escape": "1k", "modular_metal_gutter": "1k",
    "modular_pipes": "1k", "modular_airduct_rectangular_01": "1k", "security_camera_01": "1k", "security_light": "1k",
    "industrial_wall_lamp": "1k", "mounted_fluorescent_lights": "1k", "modern_ceiling_lamp_01": "1k",
    # street
    "korean_fire_extinguisher_01": "1k", "korean_public_payphone_01": "1k", "fire_hydrant": "1k", "street_lamp_01": "1k",
    "potted_plant_01": "1k", "potted_plant_02": "1k", "potted_plant_04": "1k", "planter_box_02": "1k",
    "plastic_monobloc_chair_01": "1k", "standing_chalkboard_01": "1k", "cardboard_box_01": "1k", "plastic_crate_02": "1k",
    "WetFloorSign_01": "1k", "small_lpg_tank": "1k",
    # shop interiors seen through the glass
    "steel_frame_shelves_02": "1k", "wooden_display_shelves_01": "1k", "CashRegister_01": "1k", "bar_chair_round_01": "1k",
    "coffee_table_round_01": "1k", "dining_chair_02": "1k", "modern_arm_chair_01": "1k", "CoffeeCart_01": "1k",
}
TEXTURES = [
    "painted_worn_brick", "whitewashed_brick", "white_bricks", "rectangular_facade_tiles", "rectangular_facade_tiles_02",
    "concrete_tile_facade", "exterior_wall_cladding", "painted_plaster_wall", "white_plaster_rough_01", "grey_plaster",
    "granite_tile", "painted_metal_shutter", "box_profile_metal_sheet", "red_brick", "concrete_wall_008", "dirty_concrete",
    "grey_roof_tiles", "metal_plate", "worn_plaster_wall", "beige_wall_001",
]
MAPS = {"Diffuse": "Color", "nor_dx": "NormalDX", "Rough": "Roughness", "AO": "AmbientOcclusion"}


def get(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "CoinDemo asset fetch"})
            with urllib.request.urlopen(request, timeout=120) as response, open(path + ".part", "wb") as f:
                f.write(response.read())
            os.replace(path + ".part", path)
            return
        except OSError:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}")


def files(asset):
    for attempt in range(5):
        try:
            request = urllib.request.Request(f"https://api.polyhaven.com/files/{asset}", headers={"User-Agent": "CoinDemo asset fetch"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except OSError:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"file list failed: {asset}")


fetched = []
for asset, res in MODELS.items():
    entry = files(asset)["gltf"][res]["gltf"]
    folder = os.path.join(ROOT, asset)
    get(entry["url"], os.path.join(folder, os.path.basename(entry["url"])))
    for rel, inc in entry.get("include", {}).items():
        get(inc["url"], os.path.join(folder, rel))
    fetched.append(asset)
    print("model", asset)
for asset in TEXTURES:
    entry = files(asset)
    for key, name in MAPS.items():
        if key in entry:
            get(entry[key]["2k"]["jpg"]["url"], os.path.join(ROOT, "textures", asset, f"{asset}_{name}.jpg"))
    fetched.append(asset)
    print("texture", asset)

license_path = os.path.join(ROOT, "LICENSE.txt")
text = open(license_path).read()
added = [a for a in fetched if a not in text]
if added:
    with open(license_path, "a") as f:
        f.write("\nAdded for the reimagined Hongdae (Scripts/reimagined/fetch_polyhaven.py), CC0 1.0, models 1k glTF, textures 2k jpg:\n"
                + ", ".join(added) + "\n")
print(len(fetched), "assets,", len(added), "new in LICENSE.txt")
