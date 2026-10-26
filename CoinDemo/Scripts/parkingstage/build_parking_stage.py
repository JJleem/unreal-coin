"""
Step 4 (editor Python): builds /Game/Stages/Lvl_ParkingTower from generated/ParkingTower_stage.json (plan.py).

  * the raw Parking Tower PLY as delivered (SH degree 3, no cleaning: the drivable area is clean), reusing the
    reverse study's import /Game/Stages/ParkingTower/PT_Raw with its cluster LODs; the actor levels and aligns it
    (placement.json from survey.py)
  * collision: floor height field, scanned pillars / cars / rails / walls (hidden), proximity grid boundary at the
    open edges, ceiling slab
  * the AR course in the reference video's style: thin glowing outlines on the free stalls with a "주차 가능" caption,
    a continuous cyan route line with chevrons on the floor, outlined barrier arms and low blocks, the jump pad,
    the cage, coins and the gem. Clean unlit glow materials (M_AR*), no hologram grid or scan lines
  * a StageView: low, level, narrower camera like the video's driver's eye view
  * render settings of the reverse study's best result (TSR + gs.ToneCorrection 1) through a BeforeAfterDemo actor,
    which applies them while the level plays and restores them after; B switches to the plugin defaults
  * character lighting from above like the deck's ceiling lights, through the scan stages' fixed exposure

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<repo>\\CoinDemo\\Scripts\\parkingstage\\build_parking_stage.py"
"""

import json
import math
import os
import sys

import unreal

if __name__ != "__main__":
    raise RuntimeError("run this file as the script, it imports build_scan_stages which only builds when it is __main__")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import build_scan_stages as B  # noqa: E402

DATA = os.path.normpath(os.path.join(HERE, "..", "generated", "ParkingTower_stage.json"))
PLY = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "ParkingTower", "ParkingTower_raw.ply"))
FOLDER = "/Game/Stages/ParkingTower"
LEVEL = "/Game/Stages/Lvl_ParkingTower"

TONE_GAIN = 1.64          # tone corrected splats come out this much brighter (gsquality), lights follow
SUN_INTENSITY = 0.8 * TONE_GAIN
SKY_INTENSITY = 0.2 * TONE_GAIN
SUN_ROTATION = unreal.Rotator(roll=0.0, pitch=-72.0, yaw=35.0)     # mostly from above, like the ceiling lights
SUN_COLOR = unreal.Color(r=237, g=247, b=255, a=255)                # cool white fluorescent

# AR overlay. Emissive values are tiny because the scan stages run a fixed exposure of +5.5 (x45)
AR_GLOW = f"{FOLDER}/M_ARGlow"            # parameterised (HoloPlatform sets Color, Fill, Intensity)
AR_GLOW_CAGE = f"{FOLDER}/M_ARGlowCage"   # the same for the breakable cage, which sets a 5x higher intensity
COIN_COLOR = unreal.LinearColor(0.42, 0.26, 0.02, 1.0)   # the default gold washes out to pale yellow on this deck
VIEW = {"base_fov": 65.0, "speed_fov": 5.0, "arm_length": 430.0, "socket_offset": unreal.Vector(0, 60, 35),
        "pitch_min": -35.0, "pitch_max": 12.0}
HOLO_BRIGHTNESS = 0.12                     # HoloPlatform intensity = 0.2 x this
LINE_MATERIALS = {                         # name: (colour, emissive scale, opacity)
    "M_AR_Route": ((0.1, 0.72, 1.0), 0.030, 0.55),
    "M_AR_Chevron": ((0.55, 0.92, 1.0), 0.045, 0.95),
    "M_AR_Stall": ((0.2, 1.0, 0.45), 0.035, 0.95),
}
ROUTE_WIDTH = 30.0
CHEVRON_ARM, CHEVRON_WIDTH, CHEVRON_ANGLE = 42.0, 9.0, 50.0
STALL_LINE = 7.0
LABEL_HEIGHT = 150.0

GREEN = unreal.LinearColor(0.2, 1.0, 0.45, 1.0)
CYAN = unreal.LinearColor(0.15, 0.75, 1.0, 1.0)
RED = unreal.LinearColor(1.0, 0.15, 0.12, 1.0)

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def vec(p):
    return unreal.Vector(p[0], p[1], p[2])


def spawn(cls, location, label, yaw=0.0):
    actor = actors.spawn_actor_from_class(cls, vec(location), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        raise RuntimeError(f"Failed to spawn {cls}")
    actor.set_actor_label(label)
    return actor


def holo(label, center, size, color, solid=True, fill=0.18, yaw=0.0):
    p = spawn(unreal.HoloPlatform, center, label, yaw)
    p.set_look(vec(size), color)
    p.set_editor_property("fill", fill)
    p.set_editor_property("brightness", HOLO_BRIGHTNESS)
    p.get_component_by_class(unreal.StaticMeshComponent).set_material(0, unreal.load_asset(AR_GLOW))
    p.set_editor_property("solid", solid)
    return p


def box_holo(label, b, color, solid=True, fill=0.18):
    """[minx, miny, minz, maxx, maxy, maxz] as a holographic block"""
    return holo(label, [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2], [b[3] - b[0], b[4] - b[1], b[5] - b[2]],
                color, solid, fill)


def material_graph(path, build):
    """Creates the material, or clears and rebuilds the graph of an existing one (deleting a material that a
    saved level uses can fail silently)."""
    mel = unreal.MaterialEditingLibrary
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        material = unreal.load_asset(path)
        mel.delete_all_material_expressions(material)
    else:
        folder, name = path.rsplit("/", 1)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)

    def node(cls, x, y, **props):
        e = mel.create_material_expression(material, cls, x, y)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def link(a, b, pin="", out=""):
        mel.connect_material_expressions(a, out, b, pin)
    build(node, link, mel, material)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def make_materials():
    """M_ARGlow: clean glowing panel, a bright outline on every face (from the engine shapes' 0..1 face UVs) and a
    faint fill, no grid or scan line. M_AR_*: flat colour lines for the floor meshes."""
    def glow(node, link, mel, material, gain=1.0):
        color = node(unreal.MaterialExpressionVectorParameter, -500, -300, parameter_name="Color", default_value=CYAN)
        intensity = node(unreal.MaterialExpressionScalarParameter, -500, -150, parameter_name="Intensity", default_value=0.02)
        fill = node(unreal.MaterialExpressionScalarParameter, -500, 100, parameter_name="Fill", default_value=0.12)
        uv = node(unreal.MaterialExpressionTextureCoordinate, -1400, 200)
        centred = node(unreal.MaterialExpressionSubtract, -1250, 200, const_b=0.5)
        link(uv, centred, "A")
        folded = node(unreal.MaterialExpressionAbs, -1100, 200)
        link(centred, folded)
        u = node(unreal.MaterialExpressionComponentMask, -950, 150, r=True, g=False, b=False, a=False)
        v = node(unreal.MaterialExpressionComponentMask, -950, 250, r=False, g=True, b=False, a=False)
        link(folded, u)
        link(folded, v)
        m = node(unreal.MaterialExpressionMax, -800, 200)
        link(u, m, "A")
        link(v, m, "B")
        off = node(unreal.MaterialExpressionSubtract, -650, 200, const_b=0.475)
        link(m, off, "A")
        sharp = node(unreal.MaterialExpressionMultiply, -500, 250, const_b=60.0)
        link(off, sharp, "A")
        edge = node(unreal.MaterialExpressionSaturate, -350, 250)
        link(sharp, edge)
        opacity = node(unreal.MaterialExpressionAdd, -200, 150)
        link(fill, opacity, "A")
        link(edge, opacity, "B")
        clamp = node(unreal.MaterialExpressionSaturate, -50, 150)
        link(opacity, clamp)
        mel.connect_material_property(clamp, "", unreal.MaterialProperty.MP_OPACITY)
        bright = node(unreal.MaterialExpressionLinearInterpolate, -200, -50, const_a=0.5, const_b=1.6)
        link(edge, bright, "Alpha")
        e1 = node(unreal.MaterialExpressionMultiply, -50, -250)
        link(color, e1, "A")
        link(intensity, e1, "B")
        e2 = node(unreal.MaterialExpressionMultiply, 100, -200)
        link(e1, e2, "A")
        link(bright, e2, "B")
        e3 = node(unreal.MaterialExpressionMultiply, 250, -200, const_b=gain)
        link(e2, e3, "A")
        mel.connect_material_property(e3, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    make = {AR_GLOW: glow, AR_GLOW_CAGE: lambda *a: glow(*a, gain=0.12)}
    for name, (rgb, scale, alpha) in LINE_MATERIALS.items():
        def line(node, link, mel, material, rgb=rgb, scale=scale, alpha=alpha):
            c = node(unreal.MaterialExpressionConstant3Vector, -300, -100,
                     constant=unreal.LinearColor(rgb[0] * scale, rgb[1] * scale, rgb[2] * scale, 1.0))
            mel.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
            a = node(unreal.MaterialExpressionConstant, -300, 100, r=alpha)
            mel.connect_material_property(a, "", unreal.MaterialProperty.MP_OPACITY)
        make[f"{FOLDER}/{name}"] = line
    return {path: material_graph(path, build) for path, build in make.items()}


def quad(verts, tris, a, b, c, d):
    base = len(verts)
    verts += [a, b, c, d]
    tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]


def strip(verts, tris, p, q, width, z):
    """Flat strip on the floor from p to q"""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1.0
    ox, oy = -dy / n * width / 2, dx / n * width / 2
    quad(verts, tris, (p[0] + ox, p[1] + oy, z[0]), (q[0] + ox, q[1] + oy, z[1]), (q[0] - ox, q[1] - oy, z[1]), (p[0] - ox, p[1] - oy, z[0]))


def floor_lines(data):
    """Route ribbon, chevrons and stall outlines as three flat meshes 1-2 cm above the floor"""
    route_v, route_t = [], []
    pts = data["route"]
    for k in range(len(pts)):
        # mitred continuous ribbon: offset each point along the averaged normal
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        ox, oy = -dy / n * ROUTE_WIDTH / 2, dx / n * ROUTE_WIDTH / 2
        route_v += [(pts[k][0] + ox, pts[k][1] + oy, pts[k][2]), (pts[k][0] - ox, pts[k][1] - oy, pts[k][2])]
        if k:
            i = 2 * k
            route_t += [(i - 2, i, i + 1), (i - 2, i + 1, i - 1)]
    chev_v, chev_t = [], []
    for ch in data["chevrons"]:
        x, y, z = ch["at"]
        for side in (-1, 1):
            d = math.radians(ch["yaw"] + 180 + side * CHEVRON_ANGLE)
            strip(chev_v, chev_t, (x, y), (x + CHEVRON_ARM * math.cos(d), y + CHEVRON_ARM * math.sin(d)), CHEVRON_WIDTH, (z, z))
    stall_v, stall_t = [], []
    for st in data["stalls"]:
        (x, y, z), (w, h) = st["center"], st["size"]
        w, h, z = w - 24, h - 24, z + 1.5
        corners = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            # extend each side by half the line width so the corners close
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy)
            e = STALL_LINE / 2 / n
            strip(stall_v, stall_t, (a[0] - dx * e, a[1] - dy * e), (b[0] + dx * e, b[1] + dy * e), STALL_LINE, (z, z))
    return {"Route": (route_v, route_t, "M_AR_Route"), "Chevrons": (chev_v, chev_t, "M_AR_Chevron"),
            "Stalls": (stall_v, stall_t, "M_AR_Stall")}


def import_splat():
    asset_path = f"{FOLDER}/PT_Raw"
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", PLY)
        task.set_editor_property("destination_path", FOLDER)
        task.set_editor_property("destination_name", "PT_Raw")
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"[Parking] failed to import {PLY}")
    if not asset.is_nanite_enabled():
        if not asset.build_nanite_cluster_hierarchy():
            raise RuntimeError("[Parking] cluster LOD build failed")
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return asset


def main():
    data = json.load(open(DATA))
    asset = import_splat()
    materials = make_materials()
    ground = B.create_collision_mesh("SM_Parking_Ground", FOLDER, *B.ground_geometry(data["ground"]))
    solid = B.create_collision_mesh("SM_Parking_Solid", FOLDER, *B.box_geometry(data["solid"] + [data["ceiling"]]))
    boundary = B.create_collision_mesh("SM_Parking_Boundary", FOLDER, *B.box_geometry(data["boundary"]))

    if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
        unreal.EditorAssetLibrary.delete_asset(LEVEL)
    if not levels.new_level(LEVEL):
        raise RuntimeError(f"Failed to create {LEVEL}")

    # the scan, levelled and turned so the deck runs along X
    pl = data["placement"]
    pitch, yaw, roll = pl["rotation"]
    scan = actors.spawn_actor_from_class(unreal.ScanSplatActor, vec(pl["location"]), unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw))
    scan.set_actor_label("Scan_ParkingTower")
    splat = scan.get_splat()
    splat.set_splat_asset(asset)
    splat.set_editor_property("sh_order", 3)
    splat.set_editor_property("sort_every_nth_frame", 1)
    scan.set_actor_scale3d(unreal.Vector(pl["mpu"], pl["mpu"], pl["mpu"]))

    check = data["placementCheck"]
    got = scan.get_actor_transform().transform_location(vec(check["local"]))
    err = math.dist([got.x, got.y, got.z], check["world"])
    unreal.log(f"[Parking] placement check: unreal {got.x:.1f} {got.y:.1f} {got.z:.1f} vs plan {check['world']} -> {err:.2f} cm")
    if err > 2.0:
        raise RuntimeError("[Parking] the actor transform doesn't match plan.py's placement")

    B.spawn_collision(actors, ground, "Ground_Collision")
    B.spawn_collision(actors, solid, "Solid_Collision")
    B.spawn_collision(actors, boundary, "Boundary", unreal.load_asset(B.BARRIER_MATERIAL))

    # lighting for the character only (the splats carry the deck's own light)
    sun = spawn(unreal.DirectionalLight, [0, 0, 1000], "Sun")
    sun.set_actor_rotation(SUN_ROTATION, False)
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_editor_property("intensity", SUN_INTENSITY)
    sun.light_component.set_editor_property("light_color", SUN_COLOR)
    spawn(unreal.SkyAtmosphere, [0, 0, 0], "SkyAtmosphere")
    sky = spawn(unreal.SkyLight, [0, 0, 0], "SkyLight")
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("intensity", SKY_INTENSITY)

    post = spawn(unreal.PostProcessVolume, [0, 0, 0], "PostProcess")
    post.set_editor_property("unbound", True)
    settings = post.get_editor_property("settings")
    settings.set_editor_property("override_bloom_intensity", True)
    settings.set_editor_property("bloom_intensity", 0.15)
    settings.set_editor_property("override_auto_exposure_method", True)
    settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    settings.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
    settings.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    settings.set_editor_property("override_auto_exposure_bias", True)
    settings.set_editor_property("auto_exposure_bias", B.EXPOSURE_BIAS)
    post.set_editor_property("settings", settings)

    demo = spawn(unreal.BeforeAfterDemo, [0, 0, 0], "RenderSettings")
    demo.set_editor_property("before_scan", asset)
    demo.set_editor_property("after_scan", asset)
    demo.set_editor_property("before_sun_scale", 1.0 / TONE_GAIN)
    demo.set_editor_property("before_sky_light_scale", 1.0 / TONE_GAIN)
    demo.set_editor_property("demo_controls", False)

    start = data["start"]
    spawn(unreal.PlayerStart, [start[0], start[1], start[2] + B.PLAYER_START_HEIGHT], "PlayerStart", data["startYaw"])

    # camera framing like the video's driver's eye view
    view = spawn(unreal.StageView, [0, 0, 0], "StageView")
    for k, v in VIEW.items():
        view.set_editor_property(k, v)

    # the AR course
    for name, (verts, tris, material) in floor_lines(data).items():
        mesh = B.create_collision_mesh(f"SM_AR_{name}", FOLDER, verts, tris)
        actor = spawn(unreal.StaticMeshActor, [0, 0, 0], f"Course_AR_{name}")
        comp = actor.static_mesh_component
        comp.set_static_mesh(mesh)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_cast_shadow(False)
        comp.set_material(0, materials[f"{FOLDER}/{material}"])
    for i, a in enumerate(data["arms"], start=1):
        box_holo(f"Course_Arm_{i:02d}", a["bar"], RED, fill=0.3)
        b = a["bar"]
        label = spawn(unreal.ARLabel, [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[5] + 45], f"Course_ArmLabel_{i:02d}")
        label.set_editor_property("text", "슬라이딩")
        label.set_editor_property("color", unreal.LinearColor(1.0, 0.35, 0.3, 1.0))
        label.set_editor_property("max_distance", 1500.0)
    for i, p in enumerate(data["platforms"], start=1):
        c, sz = p["center"], p["size"]
        holo(f"Course_Block_{i:02d}", [c[0], c[1], c[2] - sz[2] / 2], sz, CYAN, fill=0.1)
    if data["cage"]:
        wall = spawn(unreal.BreakableBarrier, data["cage"][0][:3], "Course_Cage")
        boxes = []
        for b in data["cage"]:
            box = unreal.Box()
            box.set_editor_property("min", vec(b[:3]))
            box.set_editor_property("max", vec(b[3:]))
            box.set_editor_property("is_valid", True)
            boxes.append(box)
        wall.set_editor_property("visible_material", materials[AR_GLOW_CAGE])
        wall.set_boxes(boxes)
        wall.set_always_visible(True)
    pad = data["pad"]
    jp = spawn(unreal.JumpPad, [pad["at"][0], pad["at"][1], pad["at"][2] + 40], "Course_JumpPad")
    jp.set_target(vec(pad["target"]))
    jp.set_editor_property("arc_height", pad["arc"])
    # its light beam is 8 m tall for open-air stages; keep it under the slab
    for comp in jp.get_components_by_class(unreal.StaticMeshComponent):
        if comp.get_name() == "Beam":
            comp.set_relative_location(unreal.Vector(0, 0, 120), False, False)
            comp.set_relative_scale3d(unreal.Vector(1.2, 1.2, 2.6))
    coins = [spawn(unreal.CoinPickup, c, f"Coin_{i:02d}") for i, c in enumerate(data["coins"], start=1)]
    for coin in coins:
        coin.set_editor_property("coin_color", COIN_COLOR)
    for i, st in enumerate(data["stalls"], start=1):
        x, y, z = st["center"]
        label = spawn(unreal.ARLabel, [x, y, z + LABEL_HEIGHT], f"Course_StallLabel_{i:02d}")
        label.set_editor_property("hide_when_gone", coins[st["coin"]])
    spawn(unreal.GemPickup, data["gem"], "Course_Gem")

    lowest = min(v[2] for v in data["ground"]["vertices"])
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            actor.set_editor_property("kill_z", lowest - 1000.0)

    levels.save_current_level()
    unreal.log(f"[Parking] saved {LEVEL}: {len(data['coins'])} coins, {len(data['solid'])} solid boxes, "
               f"{len(data['boundary'])} boundary boxes")


main()
