"""
Imports the city kit's external models (SourceAssets/PolyHaven, CC0, see LICENSE.txt there) into /Game/CityKit/<id>/
and logs every static mesh with its size, so placement code can pick pieces by name.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "PolyHaven"))
OUT = os.path.join(HERE, "..", "generated", "citykit_meshes.json")

tools = unreal.AssetToolsHelpers.get_asset_tools()
catalogue = {}
for model in sorted(os.listdir(SOURCE)):
    folder = os.path.join(SOURCE, model)
    if not os.path.isdir(folder):
        continue
    gltf = next((f for f in os.listdir(folder) if f.endswith(".gltf")), None)
    if not gltf:
        continue
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(folder, gltf))
    task.set_editor_property("destination_path", f"/Game/CityKit/{model}")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    tools.import_asset_tasks([task])
    for path in unreal.EditorAssetLibrary.list_assets(f"/Game/CityKit/{model}", recursive=True):
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.StaticMesh):
            box = asset.get_bounding_box()
            size = [round(box.max.x - box.min.x, 1), round(box.max.y - box.min.y, 1), round(box.max.z - box.min.z, 1)]
            catalogue[path.split(".")[0]] = {"size_cm": size, "min_z": round(box.min.z, 1)}
            unreal.log(f"[Kit] {path.split('.')[0]} {size}")
with open(OUT, "w") as f:
    json.dump(catalogue, f, indent=1)
unreal.log(f"[Kit] {len(catalogue)} meshes")
