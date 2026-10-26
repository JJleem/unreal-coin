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
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import course_actors  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Scans"))
GENERATED_DIR = os.path.join(HERE, "generated")
CLEAN_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "CleanScans"))
STAGES_PATH = "/Game/Stages"

# Capsule half height of the template character, so the player spawns standing on the ground
PLAYER_START_HEIGHT = 100.0

# Splat render settings: degree 1 spherical harmonics keeps multi-million splat scans
# playable (a little less view-dependent shine). Sort every frame: skipping frames makes splats pop while moving
SPLAT_SH_ORDER = 1

# Scans exported with degree 3 spherical harmonics keep it: they render at 250+ fps with cluster LODs
SPLAT_SH_ORDER_OVERRIDE = {"Gwanghwamun": 3, "JejuPier": 3}
SPLAT_SORT_EVERY_NTH_FRAME = 1

# Character lighting in lux / sky light scale, seen through a fixed exposure. The splats ignore exposure, so eye
# adaptation would only brighten or darken the character; manual exposure keeps it matched to the scan
SUN_INTENSITY = 0.8
SKY_INTENSITY = 0.2
EXPOSURE_BIAS = 5.5

# Walls and breakable barriers are drawn with a cyan grid that only shows within a few metres of the player
BARRIER_COLLECTION = "/Game/Stages/Common/MPC_Barrier"
BARRIER_MATERIAL = "/Game/Stages/Common/M_Barrier"
BARRIER_REVEAL_DISTANCE = 260.0
BARRIER_CAMERA_FADE = (60.0, 220.0)  # fade out between these distances from the camera, so a wall the camera is pushed into stays see-through
BARRIER_GRID = 40.0

# Nothing is drawn behind the scans on purpose: their floors and walls are built from many faint splats, so
# whatever is behind shows through. The sky atmosphere's dark ground below the horizon matches what the scans
# were trained against; fog or a colored ground fill tints the whole floor.


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

    # an asset imported from a different file (e.g. before the scan was cleaned) is imported again
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        existing = unreal.load_asset(asset_path)
        if os.path.normcase(os.path.normpath(existing.get_editor_property("source_file_path"))) != os.path.normcase(ply_path):
            unreal.log(f"[ScanStages] {name} was imported from another file, importing {ply_path}")
            unreal.EditorAssetLibrary.delete_asset(asset_path)

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


def spawn_collision(actors, mesh, label, material=None):
    actor = spawn(actors, unreal.StaticMeshActor, unreal.Vector(0, 0, 0), label=label)
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("BlockAll")
    if material:
        component.set_material(0, material)
        component.set_cast_shadow(False)
    else:
        actor.set_actor_hidden_in_game(True)
    return actor


def barrier_material():
    """Translucent cyan grid whose opacity fades in as the player (MPC_Barrier.PlayerPosition) gets close."""
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    mel = unreal.MaterialEditingLibrary

    if unreal.EditorAssetLibrary.does_asset_exist(BARRIER_COLLECTION):
        collection = unreal.load_asset(BARRIER_COLLECTION)
    else:
        folder, name = BARRIER_COLLECTION.rsplit("/", 1)
        collection = asset_tools.create_asset(name, folder, unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
        param = unreal.CollectionVectorParameter()
        param.set_editor_property("parameter_name", "PlayerPosition")
        collection.set_editor_property("vector_parameters", [param])
        unreal.EditorAssetLibrary.save_loaded_asset(collection)

    if unreal.EditorAssetLibrary.does_asset_exist(BARRIER_MATERIAL):
        unreal.EditorAssetLibrary.delete_asset(BARRIER_MATERIAL)
    folder, name = BARRIER_MATERIAL.rsplit("/", 1)
    material = asset_tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)

    def node(cls, x, y, **props):
        expression = mel.create_material_expression(material, cls, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def link(a, b, pin="", out=""):
        mel.connect_material_expressions(a, out, b, pin)

    world = node(unreal.MaterialExpressionWorldPosition, -1400, 0)
    player = node(unreal.MaterialExpressionCollectionParameter, -1400, 300, collection=collection, parameter_name="PlayerPosition")
    player_xyz = node(unreal.MaterialExpressionComponentMask, -1200, 300, r=True, g=True, b=True, a=False)
    link(player, player_xyz)

    # proximity: (1 - saturate(distance / reveal))^2
    distance = node(unreal.MaterialExpressionDistance, -1000, 200)
    link(world, distance, "A")
    link(player_xyz, distance, "B")
    scaled = node(unreal.MaterialExpressionDivide, -850, 200, const_b=BARRIER_REVEAL_DISTANCE)
    link(distance, scaled, "A")
    clamped = node(unreal.MaterialExpressionSaturate, -700, 200)
    link(scaled, clamped)
    near = node(unreal.MaterialExpressionOneMinus, -550, 200)
    link(clamped, near)
    falloff = node(unreal.MaterialExpressionMultiply, -400, 200)
    link(near, falloff, "A")
    link(near, falloff, "B")

    # grid lines every BARRIER_GRID cm on all three axes
    cells = node(unreal.MaterialExpressionDivide, -1200, -200, const_b=BARRIER_GRID)
    link(world, cells, "A")
    frac = node(unreal.MaterialExpressionFrac, -1050, -200)
    link(cells, frac)
    centred = node(unreal.MaterialExpressionSubtract, -900, -200, const_b=0.5)
    link(frac, centred, "A")
    folded = node(unreal.MaterialExpressionAbs, -750, -200)
    link(centred, folded)
    channels = [node(unreal.MaterialExpressionComponentMask, -600, -300 + i * 100, r=i == 0, g=i == 1, b=i == 2, a=False) for i in range(3)]
    for channel in channels:
        link(folded, channel)
    max_xy = node(unreal.MaterialExpressionMax, -450, -250)
    link(channels[0], max_xy, "A")
    link(channels[1], max_xy, "B")
    max_xyz = node(unreal.MaterialExpressionMax, -300, -200)
    link(max_xy, max_xyz, "A")
    link(channels[2], max_xyz, "B")
    edge = node(unreal.MaterialExpressionSubtract, -150, -200, const_b=0.44)
    link(max_xyz, edge, "A")
    sharpen = node(unreal.MaterialExpressionMultiply, 0, -200, const_b=16.0)
    link(edge, sharpen, "A")
    line = node(unreal.MaterialExpressionSaturate, 150, -200)
    link(sharpen, line)

    # opacity: faint fill plus bright lines, all scaled by proximity
    lit = node(unreal.MaterialExpressionLinearInterpolate, 300, 0, const_a=0.0, const_b=0.22)
    link(line, lit, "Alpha")
    opacity = node(unreal.MaterialExpressionMultiply, 450, 100)
    link(lit, opacity, "A")
    link(falloff, opacity, "B")

    # and away from the camera
    depth = node(unreal.MaterialExpressionPixelDepth, 300, 300)
    depth_offset = node(unreal.MaterialExpressionSubtract, 450, 300, const_b=BARRIER_CAMERA_FADE[0])
    link(depth, depth_offset, "A")
    depth_scaled = node(unreal.MaterialExpressionDivide, 600, 300, const_b=BARRIER_CAMERA_FADE[1] - BARRIER_CAMERA_FADE[0])
    link(depth_offset, depth_scaled, "A")
    depth_fade = node(unreal.MaterialExpressionSaturate, 750, 300)
    link(depth_scaled, depth_fade)
    faded = node(unreal.MaterialExpressionMultiply, 900, 150)
    link(opacity, faded, "A")
    link(depth_fade, faded, "B")
    mel.connect_material_property(faded, "", unreal.MaterialProperty.MP_OPACITY)

    color = node(unreal.MaterialExpressionConstant3Vector, 300, -350, constant=unreal.LinearColor(0.15, 0.55, 1.0, 1.0))
    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def build_stage(folder):
    name = folder.split("_", 1)[1]
    with open(os.path.join(GENERATED_DIR, f"{name}_collision.json")) as f:
        data = json.load(f)

    mpu = data["metresPerUnit"]
    package_path = f"{STAGES_PATH}/{name}"
    level_path = f"{STAGES_PATH}/Lvl_{name}"
    unreal.log(f"[ScanStages] Building {level_path} (1 unit = {mpu:.3f} m)")

    # clean_scans.py writes copies without streak and haze splats; prefer them
    ply_path = os.path.join(CLEAN_DIR, f"{name}.ply")
    if not os.path.exists(ply_path):
        ply_path = os.path.join(SCANS_DIR, folder, f"{name}.ply")
    splat_asset = import_splat(name, os.path.normpath(ply_path), package_path)
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
    splat.set_editor_property("sh_order", SPLAT_SH_ORDER_OVERRIDE.get(name, SPLAT_SH_ORDER))
    splat.set_editor_property("sort_every_nth_frame", SPLAT_SORT_EVERY_NTH_FRAME)
    splat_actor.set_actor_scale3d(unreal.Vector(mpu, mpu, mpu))

    spawn_collision(actors, ground_mesh, "Ground_Collision")
    barrier = barrier_material()
    spawn_collision(actors, wall_mesh, "Walls", barrier)

    # small free-standing obstacles can be smashed by running, rolling or sliding into them
    for i, group in enumerate(data.get("breakables", []), start=1):
        actor = spawn(actors, unreal.BreakableBarrier, vec(group[0][:3]), label=f"Breakable_{i:02d}")
        actor.set_boxes([course_actors.make_box(b) for b in group])

    # lighting for the character only (the splats carry their own baked color), kept soft so the character
    # sits in the photographed scene instead of glowing white
    sun = spawn(actors, unreal.DirectionalLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, -50, 30), "Sun")
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_editor_property("intensity", SUN_INTENSITY)
    spawn(actors, unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), label="SkyAtmosphere")
    sky = spawn(actors, unreal.SkyLight, unreal.Vector(0, 0, 0), label="SkyLight")
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("intensity", SKY_INTENSITY)

    # little bloom and a fixed exposure, so the character doesn't glow against the photographed scene
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
    settings.set_editor_property("auto_exposure_bias", EXPOSURE_BIAS)
    post.set_editor_property("settings", settings)

    start = data["start"]
    spawn(actors, unreal.PlayerStart, unreal.Vector(start[0], start[1], start[2] + PLAYER_START_HEIGHT),
          unreal.Rotator(0, 0, data.get("startYaw", 0.0)), label="PlayerStart")

    for i, coin in enumerate(data["coins"], start=1):
        spawn(actors, unreal.CoinPickup, vec(coin), label=f"Coin_{i:02d}")

    # the holographic course: platforms, jump pad, breakable cage, extra coins and the hidden gem
    course_actors.place_course(actors, data.get("course", {}))

    # anything that still slips below the ground respawns at the start (see ACoinDemoCharacter::FellOutOfWorld)
    lowest = min(v[2] for v in data["ground"]["vertices"])
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            actor.set_editor_property("kill_z", lowest - 1000.0)

    levels.save_current_level()
    unreal.log(f"[ScanStages] Saved {level_path}: {len(data['coins'])} coins, {len(data['walls'])} wall boxes, "
               f"{len(data.get('breakables', []))} breakables")


def main():
    folders = sorted(d for d in os.listdir(SCANS_DIR)
                     if os.path.isdir(os.path.join(SCANS_DIR, d)) and d[:2].isdigit())
    unreal.log(f"[ScanStages] Found {len(folders)} scans in {SCANS_DIR}: {folders}")
    for folder in folders:
        build_stage(folder)


# imported by parkingstage/build_parking_stage.py for its helpers
if __name__ == "__main__":
    main()
