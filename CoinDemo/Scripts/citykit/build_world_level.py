"""
Builds /Game/Stages/Lvl_Hongdae_World: the high quality level (gsquality/make_hq_level.py, zone A) extended with
zone B's ground meshes, the city kit's utility poles where the scan had poles, and the combined trimmed scan
(citykit/build_world_scan.py). The before/after demo (key B) switches the whole street.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_LEVEL = "/Game/Stages/Lvl_Hongdae_HighQualityGS"
TARGET = "/Game/Stages/Lvl_Hongdae_World"
EXTRA_ZONES = ["Hongdae_B"]
PLY = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "Rebuilt", "Hongdae_World", "Hongdae_World.ply"))
SCAN_ASSET = "/Game/Stages/Rebuilt/Hongdae_World/Hongdae_World_Scan"
KIT = "/Game/CityKit/modular_electricity_poles/modular_electricity_poles_1k/StaticMeshes"

library = unreal.EditorAssetLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# combined scan
folder, name = SCAN_ASSET.rsplit("/", 1)
task = unreal.AssetImportTask()
task.set_editor_property("filename", PLY)
task.set_editor_property("destination_path", folder)
task.set_editor_property("destination_name", name)
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("replace_existing", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
scan = unreal.load_asset(SCAN_ASSET)
scan.build_nanite_cluster_hierarchy()
library.save_loaded_asset(scan)

levels.load_level(SOURCE_LEVEL)
for actor in actors.get_all_level_actors():
    if isinstance(actor, unreal.ScanSplatActor):
        actor.get_splat().set_splat_asset(scan)
    elif isinstance(actor, unreal.BeforeAfterDemo):
        actor.set_editor_property("after_scan", scan)

# the other zones' meshes, with the collision their build gave them
for zone in EXTRA_ZONES:
    specs = json.load(open(os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "Rebuilt", zone, "meshes.json"))))
    for spec in specs:
        mesh = unreal.load_asset(f"/Game/Stages/Rebuilt/{zone}/{spec['name']}")
        if mesh is None:
            continue
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(f"Zone{zone[-1]}_{spec['name']}")
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.static_mesh_component.set_collision_profile_name("BlockAll" if spec["collision"] == "complex" else "NoCollision")
        actor.set_editor_property("tags", ["LitGround"])


def place(mesh_name, x, y, z_bottom, scale=(1.0, 1.0, 1.0), yaw=0.0, label="Kit"):
    """Places a kit piece by its bounds: centred on x, y, its lowest point at z_bottom (all cm)."""
    mesh = unreal.load_asset(f"{KIT}/{mesh_name}")
    box = mesh.get_bounding_box()
    cx, cy = (box.min.x + box.max.x) / 2 * scale[0], (box.min.y + box.max.y) / 2 * scale[1]
    actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x - cx, y - cy, z_bottom - box.min.z * scale[2]),
                                          unreal.Rotator(0, 0, yaw))
    actor.set_actor_label(label)
    actor.static_mesh_component.set_static_mesh(mesh)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    actor.set_editor_property("tags", ["LitGround"])
    return actor


# utility poles: the kit's 6 m wooden pole scaled to a Korean concrete pole (about 35 cm, 10 m) with a transformer
# and a cross arm (an approximation of the real poles, which the scan shows only as blurred columns)
props = json.load(open(os.path.join(HERE, "..", "generated", "Hongdae_world_props.json")))
for i, (x, y, z) in enumerate(props["poles"]):
    x, y, z = x * 100, y * 100, z * 100
    place("preset_01_pole", x, y, z - 20, (2.5, 2.5, 1.7), 0, f"Kit_Pole_{i:02d}")
    place("transformer_01", x + 30, y, z + 620, (1.3, 1.3, 1.3), 0, f"Kit_Transformer_{i:02d}")
    place("support_large_01", x, y, z + 950, (1.4, 1.4, 1.4), 0, f"Kit_CrossArm_{i:02d}")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET)
unreal.log(f"[World] saved {TARGET}: {len(props['poles'])} kit poles")
