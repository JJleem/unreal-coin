"""
Builds /Game/Stages/Lvl_Hongdae_Reimagined from build_reimagined.py's data:

  * textures (Poly Haven / ambientCG CC0 sets, the drawn sign faces) and one material per surface in
    /Game/Stages/Reimagined: tiling PBR with ambient occlusion and weathering (rain streaks, darker rising damp near
    the ground, read from the walls' UV v = -height), flat PBR colours, sign faces, glass
  * the building meshes (shell with collision, detail without) and the Poly Haven props
  * the level: a copy of Lvl_Hongdae_HighQualityGS (zone A ground, lighting, before/after demo) with the old Blue
    Elephant collision proxy removed, the rebuilt buildings and props added and the scan swapped for the trimmed one;
    plus Lvl_Hongdae_Reimagined_MeshOnly (no splats) to show exactly what is mesh

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import math
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "Rebuilt", "Hongdae_Reimagined"))
FOLDER = "/Game/Stages/Reimagined"
SOURCE_LEVEL = "/Game/Stages/Lvl_Hongdae_HighQualityGS"
LEVEL = "/Game/Stages/Lvl_Hongdae_Reimagined"
EXPOSURE = 0.022
# zone A dimmed the sky light to 0.3 of the stage's (fine for flat ground); the rebuilt buildings cast real sun
# shadows over the street, which came out near black next to the scan's overcast lighting: lift the fill
SKYLIGHT_BOOST = 2.5     # emissive 1 x EXPOSURE reads like the scan's brightest surfaces (see rebuild/build_zone_level.py)

tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
library = unreal.EditorAssetLibrary
_textures = {}


def windows_path(path):
    """build_reimagined.py runs under WSL and writes /mnt/c/... paths."""
    return "C:/" + path[len("/mnt/c/"):] if path.startswith("/mnt/c/") else path


def import_texture(path, kind):
    path = windows_path(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem in _textures:
        return _textures[stem]
    folder = f"{FOLDER}/Textures"
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", f"T_{stem}")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    task.set_editor_property("replace_existing", True)
    tools.import_asset_tasks([task])
    texture = unreal.load_asset(f"{folder}/T_{stem}")
    if kind == "normal":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
    elif kind == "linear":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        texture.set_editor_property("srgb", False)
    elif kind == "sign":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    library.save_loaded_asset(texture)
    _textures[stem] = texture
    return texture


def new_material(name):
    path = f"{FOLDER}/M_{name}"
    if library.does_asset_exist(path):
        library.delete_asset(path)
    material = tools.create_asset(f"M_{name}", FOLDER, unreal.Material, unreal.MaterialFactoryNew())

    def node(cls, x, y, **props):
        e = mel.create_material_expression(material, cls, x, y)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def link(a, b, pin="", out=""):
        mel.connect_material_expressions(a, out, b, pin)

    return material, node, link


def finish(material):
    mel.recompile_material(material)
    library.save_loaded_asset(material)
    return material


def pbr_material(name, spec, grime):
    """Tiling PBR: Colour x Tint x AO, macro variation; with weathering, vertical rain streaks (a grime texture
    stretched 12x along the wall's height) and a darker band up to 0.8 m above the ground (UV v = -height)."""
    material, node, link = new_material(name)
    t = {k: import_texture(v, "normal" if k == "NormalDX" else "color" if k == "Color" else "linear") for k, v in spec["files"].items()}
    coord = node(unreal.MaterialExpressionTextureCoordinate, -1600, 0)
    uv = node(unreal.MaterialExpressionDivide, -1450, 0, const_b=spec["tile"])
    link(coord, uv, "A")
    colour = node(unreal.MaterialExpressionTextureSample, -1100, -300, texture=t["Color"])
    normal = node(unreal.MaterialExpressionTextureSample, -1100, 0, texture=t["NormalDX"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    rough = node(unreal.MaterialExpressionTextureSample, -1100, 300, texture=t["Roughness"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for s in (colour, normal, rough):
        link(uv, s, "UVs")
    base = node(unreal.MaterialExpressionMultiply, -800, -300)
    link(colour, base, "A", "RGB")
    link(node(unreal.MaterialExpressionConstant3Vector, -1000, -450, constant=unreal.LinearColor(*spec["tint"], 1.0)), base, "B")
    if "AmbientOcclusion" in t:
        ao = node(unreal.MaterialExpressionTextureSample, -1100, 600, texture=t["AmbientOcclusion"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        link(uv, ao, "UVs")
        ao_soft = node(unreal.MaterialExpressionLinearInterpolate, -800, 600, const_a=1.0)
        link(ao, ao_soft, "B", "R")
        link(node(unreal.MaterialExpressionConstant, -950, 700, r=0.6), ao_soft, "Alpha")
        with_ao = node(unreal.MaterialExpressionMultiply, -650, -300)
        link(base, with_ao, "A")
        link(ao_soft, with_ao, "B")
        base = with_ao
    # large scale variation over 6 m so repeats don't show
    big = node(unreal.MaterialExpressionDivide, -1450, -700, const_b=6.0)
    link(coord, big, "A")
    macro = node(unreal.MaterialExpressionTextureSample, -1250, -700, texture=grime)
    link(big, macro, "UVs")
    vary = node(unreal.MaterialExpressionLinearInterpolate, -1000, -700, const_a=0.82, const_b=1.1)
    link(macro, vary, "Alpha", "R")
    varied = node(unreal.MaterialExpressionMultiply, -500, -300)
    link(base, varied, "A")
    link(vary, varied, "B")
    base = varied
    if spec["weather"]:
        # rain streaks: grime sampled with u / 2.5 and v / 30 (long vertical runs), darkening up to 30 %
        streak_uv = node(unreal.MaterialExpressionMultiply, -1450, -1000)
        link(coord, streak_uv, "A")
        link(node(unreal.MaterialExpressionConstant2Vector, -1600, -1050, r=0.4, g=0.033), streak_uv, "B")
        streak = node(unreal.MaterialExpressionTextureSample, -1250, -1000, texture=grime)
        link(streak_uv, streak, "UVs")
        streak_mask = node(unreal.MaterialExpressionPower, -1050, -1000, const_exponent=3.0)
        link(streak, streak_mask, "Base", "R")
        streak_dark = node(unreal.MaterialExpressionLinearInterpolate, -850, -1000, const_a=1.0, const_b=0.7)
        link(streak_mask, streak_dark, "Alpha")
        # rising damp / splash: walls carry v = -z, the street is at about z = -2.1 m, so the height above it is
        # 2.1 - v; the band darkens over the lowest 0.9 m
        v = node(unreal.MaterialExpressionComponentMask, -1450, -1250, r=False, g=True, b=False, a=False)
        link(coord, v)
        shifted = node(unreal.MaterialExpressionAdd, -1300, -1250, const_b=-2.1)
        link(v, shifted, "A")
        above = node(unreal.MaterialExpressionMultiply, -1150, -1250, const_b=-1.0 / 0.9)
        link(shifted, above, "A")
        damp = node(unreal.MaterialExpressionSaturate, -1000, -1250)
        link(above, damp)
        damp_dark = node(unreal.MaterialExpressionLinearInterpolate, -850, -1250, const_a=0.72, const_b=1.0)
        link(damp, damp_dark, "Alpha")
        weathered = node(unreal.MaterialExpressionMultiply, -350, -400)
        link(base, weathered, "A")
        link(streak_dark, weathered, "B")
        weathered2 = node(unreal.MaterialExpressionMultiply, -200, -400)
        link(weathered, weathered2, "A")
        link(damp_dark, weathered2, "B")
        base = weathered2
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)
    r = node(unreal.MaterialExpressionMultiply, -500, 300, const_b=spec["rough"])
    link(rough, r, "A", "R")
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -500, 450, r=spec["metallic"]), "", unreal.MaterialProperty.MP_METALLIC)
    return finish(material)


def flat_material(name, spec, grime):
    """Plain coloured surface with a faint grime variation (painted metal, plastic, letters)."""
    material, node, link = new_material(name)
    colour = node(unreal.MaterialExpressionConstant3Vector, -600, -200, constant=unreal.LinearColor(*spec["colour"], 1.0))
    coord = node(unreal.MaterialExpressionTextureCoordinate, -1000, 100)
    uv = node(unreal.MaterialExpressionDivide, -850, 100, const_b=1.5)
    link(coord, uv, "A")
    g = node(unreal.MaterialExpressionTextureSample, -700, 100, texture=grime)
    link(uv, g, "UVs")
    vary = node(unreal.MaterialExpressionLinearInterpolate, -450, 100, const_a=0.85, const_b=1.05)
    link(g, vary, "Alpha", "R")
    base = node(unreal.MaterialExpressionMultiply, -300, -100)
    link(colour, base, "A")
    link(vary, base, "B")
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -300, 250, r=spec["metallic"]), "", unreal.MaterialProperty.MP_METALLIC)
    rough = node(unreal.MaterialExpressionMultiply, -300, 350, const_a=spec["rough"])
    link(vary, rough, "B")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    if spec["emissive"] > 0:
        glow = node(unreal.MaterialExpressionConstant3Vector, -500, 600, constant=unreal.LinearColor(*[c * spec["emissive"] * EXPOSURE for c in spec.get("glow", (1, 1, 1))], 1.0))
        e = node(unreal.MaterialExpressionMultiply, -300, 500)
        link(colour, e, "A")
        link(glow, e, "B")
        mel.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if name == "Blind":
        material.set_editor_property("two_sided", True)
    return finish(material)


def image_material(name, spec):
    """Printed sign face: the drawn image as base colour, glossy acrylic, a little glow (light boxes)."""
    material, node, link = new_material(name)
    tex = import_texture(spec["file"], "sign")
    photo = node(unreal.MaterialExpressionTextureSample, -500, 0, texture=tex)
    lin = node(unreal.MaterialExpressionMultiply, -300, -100, const_b=0.85)
    link(photo, lin, "A", "RGB")
    mel.connect_material_property(lin, "", unreal.MaterialProperty.MP_BASE_COLOR)
    glow = node(unreal.MaterialExpressionMultiply, -300, 150, const_b=spec["emissive"] * EXPOSURE)
    link(photo, glow, "A", "RGB")
    mel.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -300, 300, r=0.3), "", unreal.MaterialProperty.MP_ROUGHNESS)
    return finish(material)


def glass_material(name):
    """Window glass: translucent (the rooms behind are real geometry), reflectivity rising with the viewing angle
    (Fresnel), lit by Lumen's front layer translucency reflections, slightly green tinted."""
    material, node, link = new_material(name)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    fresnel = node(unreal.MaterialExpressionFresnel, -600, 200, exponent=4.0, base_reflect_fraction=0.06)
    opacity = node(unreal.MaterialExpressionLinearInterpolate, -400, 200, const_a=0.32, const_b=0.9)
    link(fresnel, opacity, "Alpha")
    mel.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant3Vector, -400, -100, constant=unreal.LinearColor(0.02, 0.026, 0.026, 1)), "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -400, 0, r=0.03), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -400, 60, r=0.0), "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -400, 120, r=1.0), "", unreal.MaterialProperty.MP_SPECULAR)
    return finish(material)


def build_mesh(spec, materials):
    path = f"{FOLDER}/{spec['name']}"
    if library.does_asset_exist(path):
        library.delete_asset(path)
    mesh = tools.create_asset(spec["name"], FOLDER, unreal.StaticMesh, None)
    desc = unreal.StaticMesh.create_static_mesh_description(mesh)
    slots = []
    for section in spec["sections"]:
        group = desc.create_polygon_group()
        ids = []
        for p, uv in zip(section["positions"], section["uvs"]):
            vertex = desc.create_vertex()
            desc.set_vertex_position(vertex, unreal.Vector(*p))
            instance_id = desc.create_vertex_instance(vertex)
            desc.set_vertex_instance_uv(instance_id, unreal.Vector2D(uv[0], uv[1]), 0)
            ids.append(instance_id)
        idx = section["indices"]
        for k in range(0, len(idx), 3):
            desc.create_triangle(group, [ids[idx[k]], ids[idx[k + 1]], ids[idx[k + 2]]])
        slots.append(unreal.StaticMaterial(material_interface=materials[section["material"]], material_slot_name=section["material"]))
    mesh.set_editor_property("static_materials", slots)
    mesh.build_from_static_mesh_descriptions([desc], False, False)
    body = mesh.get_editor_property("body_setup")
    if body and spec["collision"] == "complex":
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    library.save_loaded_asset(mesh)
    return mesh


def spawn_prop(actors, prop):
    """Spawns every part of a kit model with one transform: the first part's bounds bottom centre (or centre) lands
    on the prop's point after scale and yaw."""
    meshes = [unreal.load_asset(f"/Game/CityKit/{p}") for p in prop["parts"]]
    if meshes[0] is None:
        unreal.log_warning(f"[Reimagined] missing kit mesh {prop['parts'][0]}")
        return []
    box = meshes[0].get_bounding_box()
    s = prop["scale"]
    cx, cy = (box.min.x + box.max.x) / 2 * s, (box.min.y + box.max.y) / 2 * s
    cz = box.min.z * s if prop["anchor"] == "bottom" else (box.min.z + box.max.z) / 2 * s
    yaw = math.radians(prop["yaw"])
    rx, ry = cx * math.cos(yaw) - cy * math.sin(yaw), cx * math.sin(yaw) + cy * math.cos(yaw)
    location = unreal.Vector(prop["x"] * 100 - rx, prop["y"] * 100 - ry, prop["z"] * 100 - cz)
    spawned = []
    for mesh in meshes:
        if mesh is None:
            continue
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, location, unreal.Rotator(0, 0, prop["yaw"]))
        actor.set_actor_label(f"Kit_{prop['building']}_{mesh.get_name()}")
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.set_actor_scale3d(unreal.Vector(s, s, s))
        actor.static_mesh_component.set_collision_profile_name("BlockAll" if prop["collision"] else "NoCollision")
        actor.set_editor_property("tags", ["LitGround", "Reimagined"])
        spawned.append(actor)
    return spawned


def main():
    specs = json.load(open(os.path.join(DATA, "meshes.json")))
    material_specs = json.load(open(os.path.join(DATA, "materials.json")))
    props = json.load(open(os.path.join(DATA, "props.json")))
    grime = import_texture(os.path.join(os.path.dirname(DATA), "..", "PolyHaven", "textures", "dirty_concrete", "dirty_concrete_Color.jpg"), "color")

    materials = {}
    for name, spec in material_specs.items():
        if spec["kind"] == "pbr":
            materials[name] = pbr_material(name, spec, grime)
        elif spec["kind"] == "flat":
            materials[name] = flat_material(name, spec, grime)
        elif spec["kind"] == "image":
            materials[name] = image_material(name, spec)
        elif spec["kind"] == "glass":
            materials[name] = glass_material(name)
    meshes = [(spec, build_mesh(spec, materials)) for spec in specs]

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(DATA, "Hongdae_Reimagined.ply"))
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("destination_name", "Hongdae_Reimagined_Scan")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    tools.import_asset_tasks([task])
    scan = unreal.load_asset(f"{FOLDER}/Hongdae_Reimagined_Scan")
    scan.build_nanite_cluster_hierarchy()
    library.save_loaded_asset(scan)

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    levels.load_level(SOURCE_LEVEL)
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.ScanSplatActor):
            actor.get_splat().set_splat_asset(scan)
        elif isinstance(actor, unreal.BeforeAfterDemo):
            actor.set_editor_property("after_scan", scan)
            after = list(actor.get_editor_property("after_cvars"))
            for cvar in ("r.Lumen.TranslucencyReflections.FrontLayer.Enable=1",):
                if cvar not in after:
                    after.append(cvar)
            actor.set_editor_property("after_cvars", after)
        elif isinstance(actor, unreal.SkyLight):
            light = actor.get_component_by_class(unreal.SkyLightComponent)
            light.set_editor_property("intensity", light.get_editor_property("intensity") * SKYLIGHT_BOOST)
        elif isinstance(actor, unreal.StaticMeshActor):
            mesh = actor.static_mesh_component.static_mesh
            # the hidden collision proxy of the old Blue Elephant model: the rebuilt building replaces it
            if mesh and mesh.get_name() == "SM_Zone_BlueElephant":
                actors.destroy_actor(actor)
    for spec, mesh in meshes:
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(f"Reimagined_{spec['name']}")
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.static_mesh_component.set_collision_profile_name("BlockAll" if spec["collision"] == "complex" else "NoCollision")
        actor.set_editor_property("tags", ["LitGround", "Reimagined"])
    count = sum(len(spawn_prop(actors, p)) for p in props)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, LEVEL):
        raise RuntimeError(f"failed to save {LEVEL}")
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.ScanSplatActor):
            actors.destroy_actor(actor)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, f"{LEVEL}_MeshOnly"):
        raise RuntimeError(f"failed to save {LEVEL}_MeshOnly")
    unreal.log(f"[Reimagined] saved {LEVEL}: {len(meshes)} meshes, {len(materials)} materials, {count} prop actors")


# hongdae_night/build_night_level.py imports this file for its material and mesh helpers
if __name__ == "__main__":
    main()
