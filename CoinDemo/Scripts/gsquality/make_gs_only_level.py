"""
Test levels for judging the splat rendering alone: /Game/Stages/Lvl_<Name>_GSOnly is a copy of the stage with only
the scan, its lights, post process and sky (no coins, course, barriers or collision visuals).
Optional: SPLAT_ASSET renders another import of the scan in it.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import unreal

NAME = "Hongdae"
KEEP = (unreal.ScanSplatActor, unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere, unreal.PostProcessVolume,
        unreal.PlayerStart, unreal.WorldSettings)

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels.load_level(f"/Game/Stages/Lvl_{NAME}")
removed = 0
for actor in actors.get_all_level_actors():
    if isinstance(actor, KEEP):
        continue
    # keep the invisible ground collision so the parked player doesn't fall
    if actor.get_actor_label() == "Ground_Collision":
        continue
    actors.destroy_actor(actor)
    removed += 1
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.EditorLoadingAndSavingUtils.save_map(world, f"/Game/Stages/Lvl_{NAME}_GSOnly")
unreal.log(f"[GSOnly] saved, removed {removed} actors")
