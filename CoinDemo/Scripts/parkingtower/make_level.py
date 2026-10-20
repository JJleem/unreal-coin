"""
Builds /Game/Stages/Lvl_ParkingTower_ReverseStudy: the raw Parking Tower PLY only (no meshes), for comparing
renderer settings and the reference video at fixed cameras. Nothing else in the project is touched.

  * imports SourceAssets/ParkingTower/ParkingTower_raw.ply (decompressed by analyze_ply.py) to
    /Game/Stages/ParkingTower/PT_Raw with cluster LODs (reused if it exists)
  * Splat Actor: scale = metres per unit 3.846 (2.5 m stalls), Z offset so the floor at the deck centre is Z = 0,
    no rotation (OpenSplat4D already maps PLY (x, y, z) to Unreal (z, x, -y)); SH degree 3, sorted every frame
  * lights, sky and manual exposure +5.5 exactly like the scan stages (they only light the hidden character;
    splats ignore lights and exposure), a hidden ground box so the parked player doesn't fall

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<repo>\\CoinDemo\\Scripts\\parkingtower\\make_level.py"
"""

import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
PLY = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "ParkingTower", "ParkingTower_raw.ply"))
FOLDER = "/Game/Stages/ParkingTower"
ASSET = f"{FOLDER}/PT_Raw"
LEVEL = "/Game/Stages/Lvl_ParkingTower_ReverseStudy"
MPU = 3.8461538
OFFSET_Z = -76.0
START = unreal.Vector(0.0, -700.0, 100.0)      # driving aisle west of the middle stall block


def import_splat():
    if not unreal.EditorAssetLibrary.does_asset_exist(ASSET):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", PLY)
        task.set_editor_property("destination_path", FOLDER)
        task.set_editor_property("destination_name", "PT_Raw")
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.load_asset(ASSET)
    if asset is None:
        raise RuntimeError(f"[ParkingTower] failed to import {PLY}")
    if not asset.is_nanite_enabled():
        if not asset.build_nanite_cluster_hierarchy():
            raise RuntimeError("[ParkingTower] cluster LOD build failed")
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
    unreal.log(f"[ParkingTower] {ASSET}: {asset.get_cluster_count()} clusters")
    return asset


def spawn(actors, cls, location, rotation=unreal.Rotator(0, 0, 0), label=None):
    actor = actors.spawn_actor_from_class(cls, location, rotation)
    if actor is None:
        raise RuntimeError(f"Failed to spawn {cls}")
    if label:
        actor.set_actor_label(label)
    return actor


def main():
    asset = import_splat()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
        unreal.EditorAssetLibrary.delete_asset(LEVEL)
    if not levels.new_level(LEVEL):
        raise RuntimeError(f"Failed to create {LEVEL}")

    scan = spawn(actors, unreal.ScanSplatActor, unreal.Vector(0, 0, OFFSET_Z), label="Scan_ParkingTower_Raw")
    splat = scan.get_splat()
    splat.set_splat_asset(asset)
    splat.set_editor_property("sh_order", 3)
    splat.set_editor_property("sort_every_nth_frame", 1)
    scan.set_actor_scale3d(unreal.Vector(MPU, MPU, MPU))

    sun = spawn(actors, unreal.DirectionalLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, -50, 30), "Sun")
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_editor_property("intensity", 0.8)
    spawn(actors, unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), label="SkyAtmosphere")
    sky = spawn(actors, unreal.SkyLight, unreal.Vector(0, 0, 0), label="SkyLight")
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("intensity", 0.2)

    post = spawn(actors, unreal.PostProcessVolume, unreal.Vector(0, 0, 0), label="PostProcess")
    post.set_editor_property("unbound", True)
    settings = post.get_editor_property("settings")
    settings.set_editor_property("override_bloom_intensity", True)
    settings.set_editor_property("bloom_intensity", 0.15)
    settings.set_editor_property("override_auto_exposure_method", True)
    settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    settings.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
    settings.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    settings.set_editor_property("override_auto_exposure_bias", True)
    settings.set_editor_property("auto_exposure_bias", 5.5)
    post.set_editor_property("settings", settings)

    # invisible floor under the deck for the (hidden) player
    ground = spawn(actors, unreal.StaticMeshActor, unreal.Vector(0, 0, -60), label="Ground_Collision")
    comp = ground.static_mesh_component
    comp.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    comp.set_collision_profile_name("BlockAll")
    ground.set_actor_scale3d(unreal.Vector(120, 60, 1))
    ground.set_actor_hidden_in_game(True)

    spawn(actors, unreal.PlayerStart, START, unreal.Rotator(0, 0, 0), label="PlayerStart")
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            actor.set_editor_property("kill_z", -5000.0)
    levels.save_current_level()
    unreal.log(f"[ParkingTower] saved {LEVEL}")


main()
