"""
Imports the WAV files written by make_sounds.py into /Game/Audio as Sound Waves.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "Sounds"))

tasks = []
for file_name in sorted(os.listdir(SOURCE_DIR)):
    if not file_name.endswith(".wav"):
        continue
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(SOURCE_DIR, file_name))
    task.set_editor_property("destination_path", "/Game/Audio")
    task.set_editor_property("destination_name", "SFX_" + file_name[:-4].capitalize())
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    tasks.append(task)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
for task in tasks:
    unreal.log(f"[Sounds] {task.get_editor_property('destination_name')}: {list(task.get_editor_property('imported_object_paths'))}")
