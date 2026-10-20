"""
Creates /Game/Stages/Lvl_Title, the title screen backdrop: a copy of a built scan stage without its coins, gem and
player start camera clutter. ACoinDemoGameMode recognises it by name, spawns no player and circles a camera
around its player start. Run after build_scan_stages.py and place_courses.py.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import unreal

SOURCE = "/Game/Stages/Lvl_Gwanghwamun"
TITLE = "/Game/Stages/Lvl_Title"

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels.load_level(SOURCE)
removed = 0
for actor in actors.get_all_level_actors():
    if isinstance(actor, (unreal.CoinPickup, unreal.GemPickup)):
        actors.destroy_actor(actor)
        removed += 1

# save the edited copy under the new name; the source stage stays as it was on disk
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not unreal.EditorLoadingAndSavingUtils.save_map(world, TITLE):
    raise RuntimeError(f"Failed to save {TITLE}")
unreal.log(f"[Title] Saved {TITLE}, removed {removed} pickups")
