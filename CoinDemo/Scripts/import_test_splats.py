"""
Imports extra versions of a scan as separate splat assets, for side-by-side comparisons without touching the stages.

Reads generated/import_jobs.json: [{"ply": "<absolute path>", "asset": "/Game/Stages/Tests/<Name>"}, ...]
Each asset is imported fresh (an existing one is replaced) and gets its cluster LODs built. View one in a stage with
the game's -SplatAsset=<asset path> command line option.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os
import time

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "generated", "import_jobs.json")) as f:
    jobs = json.load(f)

for job in jobs:
    start = time.time()
    folder, name = job["asset"].rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(job["asset"]):
        unreal.EditorAssetLibrary.delete_asset(job["asset"])
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", job["ply"])
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.load_asset(job["asset"])
    if asset is None:
        unreal.log_error(f"[TestSplats] Failed to import {job['ply']}")
        continue
    if not asset.build_nanite_cluster_hierarchy():
        unreal.log_error(f"[TestSplats] Failed to build cluster LODs for {job['asset']}")
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    unreal.log(f"[TestSplats] {job['asset']}: {asset.get_cluster_count()} clusters, {time.time() - start:.0f}s")
