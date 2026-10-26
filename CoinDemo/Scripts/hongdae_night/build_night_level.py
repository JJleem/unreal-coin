"""
Builds /Game/Stages/Lvl_Hongdae_Night: the Hongdae red street at night, all CG (no splats), from build_night.py's data.

  * base: Lvl_Hongdae_World (zone A and zone B ground meshes, utility poles, the stage's coins and course), with the
    scan, its wall and breakable collision, the day lights and the before/after demo removed
  * every building of the street (reimagined/build_reimagined_level.py's material and mesh helpers, night emissive
    values, own asset folder /Game/Stages/HongdaeNight)
  * night lighting: rect lights in the shop fronts and lit windows, coloured point lights at the signs, pole lamps,
    a low moon for the sky gradient, volumetric height fog so the lights glow in the air, manual exposure
  * render settings while the level plays (RenderSettings actor): TSR (no splats here), Lumen front layer
    translucency reflections for the glass

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import math
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reimagined"))
sys.path.insert(0, os.path.join(HERE, ".."))
import build_reimagined_level as RL  # noqa: E402

DATA = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "Rebuilt", "Hongdae_Night"))
BASE_LEVEL = "/Game/Stages/Lvl_Hongdae_World"
LEVEL = "/Game/Stages/Lvl_Hongdae_Night"

# manual exposure: scene luminance x 2^BIAS is what reaches the screen; emissive surfaces are authored in units of
# full white on screen, so their values are multiplied by 1 / 2^BIAS
EXPOSURE_BIAS = -4.3
RL.EXPOSURE = 1.0 / (2.0 ** EXPOSURE_BIAS)
RL.FOLDER = "/Game/Stages/HongdaeNight"
RL.DATA = DATA

# light output, lumens (scaled by each light's own factor)
SHOP_LUMENS = 2400.0
SIGN_LUMENS = 500.0
LAMP_LUMENS = 5000.0
LAMPS = [(3.2, -4.6), (5.8, 5.2), (19.0, 5.3), (26.75, -0.88), (35.62, 1.88), (44.0, 4.6), (47.38, 1.38)]
LAMP_HEIGHT = 6.2           # above the street (about -1.8 m here)
STREET_Z = -1.8
MOON = {"intensity": 2.0, "pitch": -28.0, "yaw": 210.0, "color": unreal.Color(r=170, g=190, b=255, a=255)}
SKY_LIGHT = 1.0
SKY_LUMINANCE = 30.0
FOG = {"density": 0.035, "height_falloff": 0.35, "color": unreal.LinearColor(0.012, 0.016, 0.03, 1.0),
       "volumetric_scattering": 0.6}

# wet road: the zones' asphalt and red pavement (their control maps for paint and red areas), darker and glossier,
# with puddles where a large scale grime texture is high
ZONES = {"Hongdae_A": (-5.0, 24.0, -9.0, 12.0), "Hongdae_B": (22.0, 46.0, -8.0, 12.0)}
ASPHALT_TINT = (1.7, 1.7, 1.75)
RED_TINT = (3.0, 1.15, 1.0)
PUDDLE_SCALE_M = 7.0
PUDDLE_LEVEL = 0.52

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def vec_m(p):
    return unreal.Vector(p[0] * 100.0, p[1] * 100.0, p[2] * 100.0)


def color(rgb):
    return unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0)


def spawn(cls, location, label, rotation=None):
    a = actors.spawn_actor_from_class(cls, location, rotation or unreal.Rotator(0, 0, 0))
    if a is None:
        raise RuntimeError(f"failed to spawn {cls}")
    a.set_actor_label(label)
    return a


def night_road(zone, box, grime):
    """zone None: plain asphalt (no control map), for the road beyond the zones"""
    material, node, link = RL.new_material(f"NightRoad_{zone[-1]}" if zone else "NightRoadPlain")
    common = "/Game/Stages/Rebuilt/Zone"
    tex = {k: unreal.load_asset(f"{common}/Textures/T_Road012A_{k}") for k in ("Color", "NormalDX", "Roughness")}
    if None in tex.values():
        raise RuntimeError("[Night] road textures not found")
    control = unreal.load_asset(f"/Game/Stages/Rebuilt/{zone or 'Hongdae_B'}/T_Control")
    coord = node(unreal.MaterialExpressionTextureCoordinate, -1600, 0)
    uv = node(unreal.MaterialExpressionDivide, -1450, 0, const_b=4.0)
    link(coord, uv, "A")
    colour = node(unreal.MaterialExpressionTextureSample, -1200, -300, texture=tex["Color"])
    normal = node(unreal.MaterialExpressionTextureSample, -1200, 0, texture=tex["NormalDX"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    rough = node(unreal.MaterialExpressionTextureSample, -1200, 300, texture=tex["Roughness"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for t in (colour, normal, rough):
        link(uv, t, "UVs")
    world = node(unreal.MaterialExpressionWorldPosition, -1700, 700)
    wxy = node(unreal.MaterialExpressionComponentMask, -1550, 700, r=True, g=True, b=False, a=False)
    link(world, wxy)
    x0, x1, y0, y1 = box
    rel = node(unreal.MaterialExpressionSubtract, -1400, 700)
    link(wxy, rel, "A")
    link(node(unreal.MaterialExpressionConstant2Vector, -1550, 800, r=x0 * 100.0, g=y0 * 100.0), rel, "B")
    cuv = node(unreal.MaterialExpressionDivide, -1250, 700)
    link(rel, cuv, "A")
    link(node(unreal.MaterialExpressionConstant2Vector, -1400, 820, r=(x1 - x0) * 100.0, g=(y1 - y0) * 100.0), cuv, "B")
    ctrl = node(unreal.MaterialExpressionTextureSample, -1100, 700, texture=control, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    if zone:
        link(cuv, ctrl, "UVs")
    else:
        # sample one plain asphalt texel of the control map (no red, no paint)
        link(node(unreal.MaterialExpressionConstant2Vector, -1250, 600, r=0.02, g=0.02), ctrl, "UVs")
    tint = node(unreal.MaterialExpressionLinearInterpolate, -800, -500)
    link(node(unreal.MaterialExpressionConstant3Vector, -1000, -600, constant=unreal.LinearColor(*ASPHALT_TINT, 1)), tint, "A")
    link(node(unreal.MaterialExpressionConstant3Vector, -1000, -500, constant=unreal.LinearColor(*RED_TINT, 1)), tint, "B")
    link(ctrl, tint, "Alpha", "R")
    surface = node(unreal.MaterialExpressionMultiply, -650, -350)
    link(colour, surface, "A", "RGB")
    link(tint, surface, "B")
    with_white = node(unreal.MaterialExpressionLinearInterpolate, -500, -350)
    link(surface, with_white, "A")
    link(node(unreal.MaterialExpressionConstant3Vector, -650, -500, constant=unreal.LinearColor(0.6, 0.6, 0.58, 1)), with_white, "B")
    link(ctrl, with_white, "Alpha", "G")
    with_yellow = node(unreal.MaterialExpressionLinearInterpolate, -350, -350)
    link(with_white, with_yellow, "A")
    link(node(unreal.MaterialExpressionConstant3Vector, -500, -500, constant=unreal.LinearColor(0.6, 0.4, 0.06, 1)), with_yellow, "B")
    link(ctrl, with_yellow, "Alpha", "B")
    # puddles: grime sampled over PUDDLE_SCALE_M, thresholded with a soft edge
    big = node(unreal.MaterialExpressionDivide, -1250, 1100, const_b=PUDDLE_SCALE_M * 100.0)
    link(wxy, big, "A")
    g = node(unreal.MaterialExpressionTextureSample, -1100, 1100, texture=grime)
    link(big, g, "UVs")
    off = node(unreal.MaterialExpressionSubtract, -950, 1100, const_b=PUDDLE_LEVEL)
    link(g, off, "A", "R")
    sharp = node(unreal.MaterialExpressionMultiply, -800, 1100, const_b=7.0)
    link(off, sharp, "A")
    puddle = node(unreal.MaterialExpressionSaturate, -650, 1100)
    link(sharp, puddle)
    darken = node(unreal.MaterialExpressionLinearInterpolate, -350, -150, const_a=0.62, const_b=0.38)
    link(puddle, darken, "Alpha")
    base = node(unreal.MaterialExpressionMultiply, -200, -300)
    link(with_yellow, base, "A")
    link(darken, base, "B")
    RL.mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    paint = node(unreal.MaterialExpressionAdd, -950, 900)
    link(ctrl, paint, "A", "G")
    link(ctrl, paint, "B", "B")
    paint01 = node(unreal.MaterialExpressionSaturate, -800, 900)
    link(paint, paint01)
    wet_rough = node(unreal.MaterialExpressionMultiply, -800, 300, const_b=0.5)
    link(rough, wet_rough, "A", "R")
    r1 = node(unreal.MaterialExpressionLinearInterpolate, -500, 400, const_b=0.3)
    link(wet_rough, r1, "A")
    link(paint01, r1, "Alpha")
    r2 = node(unreal.MaterialExpressionLinearInterpolate, -350, 400, const_b=0.03)
    link(r1, r2, "A")
    link(puddle, r2, "Alpha")
    RL.mel.connect_material_property(r2, "", unreal.MaterialProperty.MP_ROUGHNESS)
    smooth = node(unreal.MaterialExpressionMax, -500, 200)
    link(paint01, smooth, "A")
    link(puddle, smooth, "B")
    n = node(unreal.MaterialExpressionLinearInterpolate, -350, 100)
    link(normal, n, "A", "RGB")
    link(node(unreal.MaterialExpressionConstant3Vector, -500, 100, constant=unreal.LinearColor(0, 0, 1, 1)), n, "B")
    link(smooth, n, "Alpha")
    RL.mel.connect_material_property(n, "", unreal.MaterialProperty.MP_NORMAL)
    return RL.finish(material)


def wet_roads(grime):
    count = 0
    mats = {zone: night_road(zone, box, grime) for zone, box in ZONES.items()}
    for a in actors.get_all_level_actors():
        if isinstance(a, unreal.StaticMeshActor) and a.static_mesh_component.static_mesh:
            path = a.static_mesh_component.static_mesh.get_path_name()
            for zone, mat in mats.items():
                if path.startswith(f"/Game/Stages/Rebuilt/{zone}/SM_Zone_Road"):
                    a.static_mesh_component.set_material(0, mat)
                    count += 1
    return count


def clean_base():
    """Removes what belongs to the scan version of the stage."""
    removed = 0
    for a in actors.get_all_level_actors():
        label = a.get_actor_label()
        mesh = a.static_mesh_component.static_mesh if isinstance(a, unreal.StaticMeshActor) else None
        if isinstance(a, (unreal.ScanSplatActor, unreal.BeforeAfterDemo, unreal.DirectionalLight, unreal.SkyLight,
                          unreal.SkyAtmosphere, unreal.PostProcessVolume, unreal.ExponentialHeightFog)) \
                or label.startswith("Breakable_") or label.startswith("Walls") or label.startswith("Course_") \
                or isinstance(a, (unreal.CoinPickup, unreal.GemPickup, unreal.HoloPlatform, unreal.JumpPad, unreal.BreakableBarrier)) \
                or (mesh and mesh.get_name() == "SM_Zone_BlueElephant"):
            actors.destroy_actor(a)
            removed += 1
    return removed


def place_gameplay(g):
    for i, c in enumerate(g["coins"], start=1):
        spawn(unreal.CoinPickup, unreal.Vector(*c), f"Coin_{i:02d}")
    spawn(unreal.GemPickup, unreal.Vector(*g["gem"]), "Course_Gem")
    pad = spawn(unreal.JumpPad, unreal.Vector(g["pad"]["at"][0], g["pad"]["at"][1], g["pad"]["at"][2] + 40), "Course_JumpPad")
    pad.set_target(unreal.Vector(*g["pad"]["target"]))
    import build_scan_stages as B      # noqa: E402  (its main only runs as a script)
    verts, tris = B.box_geometry(g["walls"])
    mesh = B.create_collision_mesh("SM_Night_Bounds", RL.FOLDER, verts, tris)
    B.spawn_collision(actors, mesh, "Night_Bounds")


def lights(spec_list):
    count = 0
    for i, L in enumerate(spec_list):
        if L["type"] == "rect":
            a = spawn(unreal.RectLight, vec_m(L["pos"]), f"Night_Shop_{i:03d}", unreal.Rotator(roll=0, pitch=0, yaw=L["yaw"]))
            c = a.get_component_by_class(unreal.RectLightComponent)
            c.set_editor_property("source_width", L["w"] * 100.0)
            c.set_editor_property("source_height", L["h"] * 100.0)
            c.set_editor_property("barn_door_angle", 70.0)
            c.set_editor_property("barn_door_length", 30.0)
            c.set_editor_property("attenuation_radius", 1200.0)
            c.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
            c.set_editor_property("intensity", SHOP_LUMENS * L["intensity"])
            c.set_editor_property("cast_shadows", False)
        else:
            a = spawn(unreal.PointLight, vec_m(L["pos"]), f"Night_Sign_{i:03d}")
            c = a.get_component_by_class(unreal.PointLightComponent)
            c.set_editor_property("attenuation_radius", L.get("radius", 6.0) * 100.0)
            c.set_editor_property("source_radius", 30.0)
            c.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
            c.set_editor_property("intensity", SIGN_LUMENS * L["intensity"])
            c.set_editor_property("cast_shadows", False)
        c.set_editor_property("light_color", unreal.Color(r=int(255 * L["color"][0]), g=int(255 * L["color"][1]),
                                                          b=int(255 * L["color"][2]), a=255))
        c.set_editor_property("volumetric_scattering_intensity", 0.6)
        count += 1
    return count


def lamps():
    model = unreal.load_asset("/Game/CityKit/street_lamp_01/street_lamp_01_1k/StaticMeshes/street_lamp_01_1k")
    for i, (x, y) in enumerate(LAMPS):
        a = spawn(unreal.SpotLight, vec_m((x, y, STREET_Z + LAMP_HEIGHT)), f"Night_Lamp_{i:02d}",
                  unreal.Rotator(roll=0, pitch=-90, yaw=0))
        c = a.get_component_by_class(unreal.SpotLightComponent)
        c.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
        c.set_editor_property("intensity", LAMP_LUMENS)
        c.set_editor_property("outer_cone_angle", 62.0)
        c.set_editor_property("inner_cone_angle", 25.0)
        c.set_editor_property("attenuation_radius", 1600.0)
        c.set_editor_property("source_radius", 15.0)
        c.set_editor_property("light_color", unreal.Color(r=255, g=214, b=160, a=255))
        c.set_editor_property("volumetric_scattering_intensity", 1.0)
        # a lamp head on the existing utility poles; free standing lamps elsewhere
        if model and i in (0, 1, 2, 5):
            m = spawn(unreal.StaticMeshActor, vec_m((x, y, STREET_Z)), f"Night_LampPost_{i:02d}")
            m.static_mesh_component.set_static_mesh(model)
            m.set_actor_scale3d(unreal.Vector(1.6, 1.6, 1.6))


def environment():
    moon = spawn(unreal.DirectionalLight, unreal.Vector(0, 0, 3000), "Moon",
                 unreal.Rotator(roll=0, pitch=MOON["pitch"], yaw=MOON["yaw"]))
    mc = moon.light_component
    mc.set_editor_property("intensity", MOON["intensity"])
    mc.set_editor_property("light_color", MOON["color"])
    mc.set_editor_property("atmosphere_sun_light", True)
    atmosphere = spawn(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), "SkyAtmosphere")
    # city glow: the moonlit atmosphere alone is far below the night exposure, lift the sky itself
    f = SKY_LUMINANCE
    atmosphere.get_component_by_class(unreal.SkyAtmosphereComponent).set_editor_property("sky_luminance_factor", unreal.LinearColor(f * 0.8, f * 0.9, f * 1.2, 1.0))
    sky = spawn(unreal.SkyLight, unreal.Vector(0, 0, 0), "SkyLight")
    sc = sky.light_component
    sc.set_editor_property("real_time_capture", True)
    sc.set_editor_property("intensity", SKY_LIGHT)
    fog = spawn(unreal.ExponentialHeightFog, unreal.Vector(0, 0, STREET_Z * 100), "Fog")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", FOG["density"])
    fc.set_editor_property("fog_height_falloff", FOG["height_falloff"])
    fc.set_editor_property("fog_inscattering_luminance", FOG["color"])
    fc.set_volumetric_fog(True)
    fc.set_editor_property("volumetric_fog_scattering_distribution", FOG["volumetric_scattering"])

    post = spawn(unreal.PostProcessVolume, unreal.Vector(0, 0, 0), "PostProcess")
    post.set_editor_property("unbound", True)
    s = post.get_editor_property("settings")
    for k, v in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL), ("auto_exposure_apply_physical_camera_exposure", False),
                 ("auto_exposure_bias", EXPOSURE_BIAS), ("bloom_intensity", 0.9), ("bloom_threshold", -1.0),
                 ("vignette_intensity", 0.45), ("film_toe", 0.6), ("color_saturation", unreal.Vector4(1.05, 1.05, 1.1, 1.0)),
                 ("local_exposure_highlight_contrast_scale", 0.75), ("local_exposure_shadow_contrast_scale", 0.85)):
        try:
            s.set_editor_property(f"override_{k}", True)
            s.set_editor_property(k, v)
        except Exception as e:      # property names move between engine versions; the rest still applies
            unreal.log_warning(f"[Night] post process {k}: {e}")
    post.set_editor_property("settings", s)

    rs = spawn(unreal.BeforeAfterDemo, unreal.Vector(0, 0, 0), "RenderSettings")
    rs.set_editor_property("demo_controls", False)
    rs.set_editor_property("before_cvars", [])
    rs.set_editor_property("after_cvars", ["r.AntiAliasingMethod=4", "r.Lumen.TranslucencyReflections.FrontLayer.Enable=1",
                                           "r.VolumetricFog.GridPixelSize=8"])


def main():
    specs = json.load(open(os.path.join(DATA, "meshes.json")))
    material_specs = json.load(open(os.path.join(DATA, "materials.json")))
    props = json.load(open(os.path.join(DATA, "props.json")))
    light_specs = json.load(open(os.path.join(DATA, "lights.json")))
    grime = RL.import_texture(os.path.join(DATA, "..", "..", "PolyHaven", "textures", "dirty_concrete", "dirty_concrete_Color.jpg"), "color")

    materials = {}
    for name, spec in material_specs.items():
        kind = spec["kind"]
        materials[name] = (RL.pbr_material(name, spec, grime) if kind == "pbr" else RL.flat_material(name, spec, grime)
                           if kind == "flat" else RL.image_material(name, spec) if kind == "image" else RL.glass_material(name))
    meshes = [(spec, RL.build_mesh(spec, materials)) for spec in specs]

    levels.load_level(BASE_LEVEL)
    removed = clean_base()
    for spec, mesh in meshes:
        a = spawn(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), f"Night_{spec['name']}")
        a.static_mesh_component.set_static_mesh(mesh)
        a.static_mesh_component.set_collision_profile_name("BlockAll" if spec["collision"] == "complex" else "NoCollision")
    count = sum(len(RL.spawn_prop(actors, p)) for p in props)
    roads = wet_roads(grime)
    g = json.load(open(os.path.join(DATA, "gameplay.json")))
    place_gameplay(g)
    plain = night_road(None, (0, 1, 0, 1), grime)
    ext = RL.build_mesh(g["extension"], {"NightRoadPlain": plain})
    a = spawn(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), "Night_RoadExtension")
    a.static_mesh_component.set_static_mesh(ext)
    a.static_mesh_component.set_collision_profile_name("BlockAll")
    n_lights = lights(light_specs)
    lamps()
    environment()

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, LEVEL):
        raise RuntimeError(f"failed to save {LEVEL}")
    unreal.log(f"[Night] saved {LEVEL}: removed {removed} scan actors, {len(meshes)} meshes, {len(materials)} materials, "
               f"{count} prop actors, {n_lights} building lights, {len(LAMPS)} lamps, {roads} wet roads")


main()
