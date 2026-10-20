"""
Re-imports the cleaned scan of a built stage into its existing splat asset, after clean_scans.py changed it.

build_scan_stages.py only re-imports when the source file path changes; when the same file got new contents this
does it, in place, so the stage level keeps pointing at the same asset and nothing else in the level changes
(coins, collision, course, lights). The cluster LODs are rebuilt.

  STAGES below, then: UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "CleanScans"))
STAGES = ["Hongdae"]

for name in STAGES:
    folder = f"/Game/Stages/{name}"
    before = unreal.load_asset(f"{folder}/{name}")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(CLEAN_DIR, f"{name}.ply"))
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.load_asset(f"{folder}/{name}")
    if not asset.build_nanite_cluster_hierarchy():
        raise RuntimeError(f"Failed to build cluster LODs for {name}")
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    unreal.log(f"[Reimport] {folder}/{name}: {asset.get_splat_count() if hasattr(asset, 'get_splat_count') else '?'} splats, "
               f"{asset.get_cluster_count()} clusters, same object as before: {before == asset}")
