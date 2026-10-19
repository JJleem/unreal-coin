"""
Sanity checks for the levels made by build_scan_stages.py: ground mesh has geometry and complex collision,
the splat actor has its asset, and every stage has a PlayerStart and 8 coins.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import unreal

STAGES = ["Hongdae", "Gyeonggijeon", "Gwanghwamun", "JejuPier"]

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
coin_class = unreal.CoinPickup
splat_class = unreal.ScanSplatActor

for name in STAGES:
    mesh = unreal.load_asset(f"/Game/Stages/{name}/SM_{name}_Ground")
    body = mesh.get_editor_property("body_setup")
    bounds = mesh.get_bounding_box()
    unreal.log(f"[Verify] {name} ground: lods={mesh.get_num_lods()} tris={mesh.get_num_triangles(0)} "
               f"collision={body.get_editor_property('collision_trace_flag') if body else None} "
               f"bounds_m=({(bounds.max.x - bounds.min.x) / 100:.0f} x {(bounds.max.y - bounds.min.y) / 100:.0f} x {(bounds.max.z - bounds.min.z) / 100:.1f})")

    levels.load_level(f"/Game/Stages/Lvl_{name}")
    all_actors = actors.get_all_level_actors()
    coins = [a for a in all_actors if isinstance(a, coin_class)]
    starts = [a for a in all_actors if isinstance(a, unreal.PlayerStart)]
    splats = [a for a in all_actors if isinstance(a, splat_class)]
    splat_asset = splats[0].get_splat().get_splat_asset() if splats else None
    unreal.log(f"[Verify] {name} level: coins={len(coins)} starts={len(starts)} splat_asset={splat_asset.get_name() if splat_asset else None} "
               f"splat_scale={splats[0].get_actor_scale3d().x if splats else None:.3f} splat_count={splats[0].get_splat().get_splat_count() if splats else 0}")
