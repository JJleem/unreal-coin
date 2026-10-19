"""
Builds one playable level per ANNX scan in ../../Scans.

Run make_scan_collision.py first; it writes generated/<Name>_collision.json with the smoothed ground, the walls,
the coins and the start already in Unreal centimetres. For each Scans/<NN>_<Name>/ folder this script:
  1. imports <Name>.ply as an OpenSplat4D Gaussian Splat asset and builds its cluster LODs,
  2. turns the ground and the walls into invisible collision meshes,
  3. creates /Game/Stages/Lvl_<Name> with the splat, the collision, lights, a PlayerStart and the coins.

OpenSplat4D converts splats with UE = (z, x, -y) * 100 on import, the same mapping make_scan_collision.py uses,
so the splat actor only needs a uniform scale of metresPerUnit for everything to line up.

Run headless with the editor closed:
  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Scans"))
GENERATED_DIR = os.path.join(HERE, "generated")
STAGES_PATH = "/Game/Stages"

# Capsule half height of the template character, so the player spawns standing on the ground
PLAYER_START_HEIGHT = 100.0

# Splat render settings: degree 1 spherical harmonics keeps multi-million splat scans
# playable (a little less view-dependent shine). Sort every frame: skipping frames makes splats pop while moving
SPLAT_SH_ORDER = 1
SPLAT_SORT_EVERY_NTH_FRAME = 1

# Character lighting in lux / sky light scale
SUN_INTENSITY = 3.0
SKY_INTENSITY = 0.6


def vec(p):
    return unreal.Vector(p[0], p[1], p[2])


def facing(vertices, tri):
    """Normal of a triangle the way Unreal computes it: (P2 - P0) x (P1 - P0)."""
    p0, p1, p2 = (vertices[i] for i in tri)
    a = [p2[k] - p0[k] for k in range(3)]
    b = [p1[k] - p0[k] for k in range(3)]
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def orient(vertices, tri, direction):
    """Returns the triangle wound so its front faces along direction."""
    n = facing(vertices, tri)
    if n[0] * direction[0] + n[1] * direction[1] + n[2] * direction[2] < 0:
        return (tri[0], tri[2], tri[1])
    return tri


def create_collision_mesh(asset_name, package_path, vertices, triangles):
    """Creates a static mesh with per-triangle collision from vertices in Unreal space."""
    asset_path = f"{package_path}/{asset_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)

    mesh = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, unreal.StaticMesh, None)

    desc = unreal.StaticMesh.create_static_mesh_description(mesh)
    group = desc.create_polygon_group()

    instances = []
    for p in vertices:
        vertex = desc.create_vertex()
        desc.set_vertex_position(vertex, vec(p))
        instances.append(desc.create_vertex_instance(vertex))

    for tri in triangles:
        desc.create_triangle(group, [instances[i] for i in tri])

    mesh.set_editor_property("static_materials", [unreal.StaticMaterial()])
    mesh.build_from_static_mesh_descriptions([desc], False, False)

    # collide against the actual triangles, not a convex hull
    body_setup = mesh.get_editor_property("body_setup")
    if body_setup:
        body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    else:
        unreal.log_warning(f"[ScanStages] {asset_path} has no body setup, collision may be missing")

    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    return mesh


def ground_geometry(ground):
    vertices = ground["vertices"]
    indices = ground["indices"]
    triangles = [orient(vertices, (indices[i], indices[i + 1], indices[i + 2]), (0, 0, 1))
                 for i in range(0, len(indices), 3)]
    return vertices, triangles


def box_geometry(boxes):
    """Vertices and outward facing triangles for axis aligned boxes [minx, miny, minz, maxx, maxy, maxz]."""
    # corners are indexed by bits: x = 1, y = 2, z = 4
    faces = [((0, 2, 3, 1), (0, 0, -1)), ((4, 5, 7, 6), (0, 0, 1)),
             ((0, 1, 5, 4), (0, -1, 0)), ((2, 6, 7, 3), (0, 1, 0)),
             ((0, 4, 6, 2), (-1, 0, 0)), ((1, 3, 7, 5), (1, 0, 0))]
    vertices, triangles = [], []
    for box in boxes:
        base = len(vertices)
        for corner in range(8):
            vertices.append((box[3] if corner & 1 else box[0],
                             box[4] if corner & 2 else box[1],
                             box[5] if corner & 4 else box[2]))
        for (a, b, c, d), outward in faces:
            triangles.append(orient(vertices, (base + a, base + b, base + c), outward))
            triangles.append(orient(vertices, (base + a, base + c, base + d), outward))
    return vertices, triangles


def import_splat(name, ply_path, package_path):
    """Imports the PLY through OpenSplat4D's factory and builds its cluster LODs. Reuses an existing asset."""
    asset_path = f"{package_path}/{name}"
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", ply_path)
        task.set_editor_property("destination_path", package_path)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Failed to import {ply_path}")

    # without the cluster hierarchy every splat is drawn every frame, which multi-million splat scans can't afford
    if not asset.is_nanite_enabled():
        if not asset.build_nanite_cluster_hierarchy():
            raise RuntimeError(f"Failed to build cluster LODs for {asset_path}")
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
        unreal.log(f"[ScanStages] Built cluster LODs for {name}: {asset.get_cluster_count()} clusters")

    return asset


def spawn(actors, cls, location, rotation=unreal.Rotator(0, 0, 0), label=None):
    actor = actors.spawn_actor_from_class(cls, location, rotation)
    if actor is None:
        raise RuntimeError(f"Failed to spawn {cls}")
    if label:
        actor.set_actor_label(label)
    return actor


def spawn_collision(actors, mesh, label):
    actor = spawn(actors, unreal.StaticMeshActor, unreal.Vector(0, 0, 0), label=label)
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("BlockAll")
    actor.set_actor_hidden_in_game(True)
    return actor


def build_stage(folder):
    name = folder.split("_", 1)[1]
    with open(os.path.join(GENERATED_DIR, f"{name}_collision.json")) as f:
        data = json.load(f)

    mpu = data["metresPerUnit"]
    package_path = f"{STAGES_PATH}/{name}"
    level_path = f"{STAGES_PATH}/Lvl_{name}"
    unreal.log(f"[ScanStages] Building {level_path} (1 unit = {mpu:.3f} m)")

    splat_asset = import_splat(name, os.path.join(SCANS_DIR, folder, f"{name}.ply"), package_path)
    ground_mesh = create_collision_mesh(f"SM_{name}_Ground", package_path, *ground_geometry(data["ground"]))
    wall_mesh = create_collision_mesh(f"SM_{name}_Walls", package_path, *box_geometry(data["walls"]))

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    if unreal.EditorAssetLibrary.does_asset_exist(level_path):
        unreal.EditorAssetLibrary.delete_asset(level_path)
    if not levels.new_level(level_path):
        raise RuntimeError(f"Failed to create {level_path}")

    # the scan itself: OpenSplat4D already converted it to centimetres, so scale by metres per unit
    splat_actor = spawn(actors, unreal.ScanSplatActor, unreal.Vector(0, 0, 0), label=f"Scan_{name}")
    splat = splat_actor.get_splat()
    splat.set_splat_asset(splat_asset)
    splat.set_editor_property("sh_order", SPLAT_SH_ORDER)
    splat.set_editor_property("sort_every_nth_frame", SPLAT_SORT_EVERY_NTH_FRAME)
    splat_actor.set_actor_scale3d(unreal.Vector(mpu, mpu, mpu))

    spawn_collision(actors, ground_mesh, "Ground_Collision")
    spawn_collision(actors, wall_mesh, "Wall_Collision")

    # lighting for the character only (the splats carry their own baked color), kept soft so the character
    # sits in the photographed scene instead of glowing white
    sun = spawn(actors, unreal.DirectionalLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, -50, 30), "Sun")
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_editor_property("intensity", SUN_INTENSITY)
    spawn(actors, unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), label="SkyAtmosphere")
    sky = spawn(actors, unreal.SkyLight, unreal.Vector(0, 0, 0), label="SkyLight")
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("intensity", SKY_INTENSITY)

    # little bloom, so the white mannequin doesn't glow against the photographed scene
    post = spawn(actors, unreal.PostProcessVolume, unreal.Vector(0, 0, 0), label="PostProcess")
    post.set_editor_property("unbound", True)
    settings = post.get_editor_property("settings")
    settings.set_editor_property("override_bloom_intensity", True)
    settings.set_editor_property("bloom_intensity", 0.15)
    post.set_editor_property("settings", settings)

    start = data["start"]
    spawn(actors, unreal.PlayerStart, unreal.Vector(start[0], start[1], start[2] + PLAYER_START_HEIGHT), label="PlayerStart")

    for i, coin in enumerate(data["coins"], start=1):
        spawn(actors, unreal.CoinPickup, vec(coin), label=f"Coin_{i:02d}")

    # anything that still slips below the ground respawns at the start (see ACoinDemoCharacter::FellOutOfWorld)
    lowest = min(v[2] for v in data["ground"]["vertices"])
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            actor.set_editor_property("kill_z", lowest - 1000.0)

    levels.save_current_level()
    unreal.log(f"[ScanStages] Saved {level_path}: {len(data['coins'])} coins, {len(data['walls'])} wall boxes")


def main():
    folders = sorted(d for d in os.listdir(SCANS_DIR)
                     if os.path.isdir(os.path.join(SCANS_DIR, d)) and d[:2].isdigit())
    unreal.log(f"[ScanStages] Found {len(folders)} scans in {SCANS_DIR}: {folders}")
    for folder in folders:
        build_stage(folder)


main()
