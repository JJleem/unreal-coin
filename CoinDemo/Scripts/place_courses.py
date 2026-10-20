"""
Replaces the holographic course on every built scan stage with the one in generated/<Name>_collision.json, without
rebuilding the stage. Run after changing plan_course() in make_scan_collision.py and rerunning it.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import course_actors  # noqa: E402

GENERATED_DIR = os.path.join(HERE, "generated")

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

for file_name in sorted(os.listdir(GENERATED_DIR)):
    if not file_name.endswith("_collision.json"):
        continue
    name = file_name[:-len("_collision.json")]
    level_path = f"/Game/Stages/Lvl_{name}"
    if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
        continue
    with open(os.path.join(GENERATED_DIR, file_name)) as f:
        data = json.load(f)

    levels.load_level(level_path)
    removed = course_actors.clear_course(actors)
    course_actors.place_course(actors, data.get("course", {}))
    levels.save_current_level()
    unreal.log(f"[Course] {level_path}: replaced {removed} course actors")
