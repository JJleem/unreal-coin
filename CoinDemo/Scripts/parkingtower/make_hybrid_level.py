"""
Step 6 of the Parking Tower reverse study, in Unreal: minimal hybrid experiments in the north aisle zone
(prepare_hybrid.py), each saved as its own level next to the raw one. The raw level is only read.

  _E3_FloorUnlit   trimmed scan PT_HybridFloor (zone floor layer + below-floor reflection splats removed) + floor mesh with the
                   floor orthophoto, unlit (inverse ACES x exposure compensation, like Scripts/rebuild)
  _E4_FloorPBR     the same floor as a lit PBR surface (orthophoto base colour, ambientCG Concrete034 normal detail,
                   glossy roughness) + rect lights at the measured ceiling fixtures (shadows on), sun off
  _E5_Hybrid       E4 + the zone's pillars as painted boxes (orange base, grey shaft), scan PT_Hybrid (pillar
                   splats removed too)

Light intensity and the PBR base colour scale are parameters (LIGHT_LUMENS, ALBEDO_SCALE), calibrated against the
splat floor of the raw level from the same camera (see README.md).

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<repo>\\CoinDemo\\Scripts\\parkingtower\\make_hybrid_level.py"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "ParkingTower", "hybrid"))
PBR = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "Textures", "pbr"))
FOLDER = "/Game/Stages/ParkingTower"
BASE_LEVEL = "/Game/Stages/Lvl_ParkingTower_ReverseStudy"
CALIBRATION = os.path.join(HERE, "hybrid_calibration.json")
cal = json.load(open(CALIBRATION)) if os.path.exists(CALIBRATION) else {}
LIGHT_LUMENS = cal.get("light_lumens", 20.0)
ALBEDO_SCALE = cal.get("albedo_scale", 1.0)
SKY_LIGHT = cal.get("sky_light", 0.2)
EXPOSURE_COMPENSATION = 0.022
INVERSE_ACES = ("float3 c = clamp(Color, 0.0, 0.99);\n"
                "float3 A = 2.51 - c * 2.43;\nfloat3 B = 0.03 - c * 0.59;\nfloat3 C = -c * 0.14;\n"
                "return (-B + sqrt(max(B * B - 4.0 * A * C, 0.0))) / (2.0 * A);")

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
library = unreal.EditorAssetLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)


def import_file(path, folder, name, kind=None):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    asset_tools.import_asset_tasks([task])
    asset = unreal.load_asset(f"{folder}/{name}")
    if asset is None:
        raise RuntimeError(f"Failed to import {path}")
    if kind == "normal":
        asset.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        asset.set_editor_property("srgb", False)
    elif kind == "linear":
        asset.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        asset.set_editor_property("srgb", False)
    elif kind == "clamp":
        asset.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        asset.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    if kind:
        library.save_loaded_asset(asset)
    return asset


def new_material(name, unlit=False):
    path = f"{FOLDER}/{name}"
    if library.does_asset_exist(path):
        library.delete_asset(path)
    material = asset_tools.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    if unlit:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)

    def node(cls, x, y, **props):
        e = mel.create_material_expression(material, cls, x, y)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e
    return material, node


def finish(material):
    mel.recompile_material(material)
    library.save_loaded_asset(material)
    return material


def floor_unlit(ortho):
    m, node = new_material("M_PT_FloorUnlit", unlit=True)
    tex = node(unreal.MaterialExpressionTextureSample, -700, 0, texture=ortho)
    inv = node(unreal.MaterialExpressionCustom, -400, 0, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3, code=INVERSE_ACES)
    ci = unreal.CustomInput()
    ci.set_editor_property("input_name", "Color")
    inv.set_editor_property("inputs", [ci])
    mel.connect_material_expressions(tex, "RGB", inv, "Color")
    em = node(unreal.MaterialExpressionMultiply, -150, 0, const_b=EXPOSURE_COMPENSATION)
    mel.connect_material_expressions(inv, "", em, "A")
    mel.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


def world_uv(node, tile_cm):
    wp = node(unreal.MaterialExpressionWorldPosition, -1300, 400)
    xy = node(unreal.MaterialExpressionComponentMask, -1150, 400, r=True, g=True, b=False, a=False)
    mel.connect_material_expressions(wp, "", xy, "")
    uv = node(unreal.MaterialExpressionDivide, -1000, 400, const_b=tile_cm)
    mel.connect_material_expressions(xy, "", uv, "A")
    return uv


def floor_pbr(ortho, normal_tex, rough_tex):
    """Epoxy painted concrete: base colour from the scan's floor (it carries baked light too, a known compromise),
    tiled concrete normal at 15 % strength, roughness 0.2-0.35 from the concrete roughness map."""
    m, node = new_material("M_PT_FloorPBR")
    tex = node(unreal.MaterialExpressionTextureSample, -700, -200, texture=ortho)
    base = node(unreal.MaterialExpressionMultiply, -400, -200, const_b=ALBEDO_SCALE)
    mel.connect_material_expressions(tex, "RGB", base, "A")
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    uv = world_uv(node, 150.0)
    nrm = node(unreal.MaterialExpressionTextureSample, -700, 200, texture=normal_tex, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uv, "", nrm, "UVs")
    flat = node(unreal.MaterialExpressionConstant3Vector, -700, 450, constant=unreal.LinearColor(0, 0, 1, 1))
    soft = node(unreal.MaterialExpressionLinearInterpolate, -400, 250, const_alpha=0.15)
    mel.connect_material_expressions(flat, "", soft, "A")
    mel.connect_material_expressions(nrm, "RGB", soft, "B")
    mel.connect_material_property(soft, "", unreal.MaterialProperty.MP_NORMAL)
    rough = node(unreal.MaterialExpressionTextureSample, -700, 650, texture=rough_tex, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    mel.connect_material_expressions(uv, "", rough, "UVs")
    rr = node(unreal.MaterialExpressionLinearInterpolate, -400, 650, const_a=0.2, const_b=0.35)
    mel.connect_material_expressions(rough, "R", rr, "Alpha")
    mel.connect_material_property(rr, "", unreal.MaterialProperty.MP_ROUGHNESS)
    return finish(m)


def paint(name, colour, rough_tex, normal_tex, roughness=0.5):
    m, node = new_material(name)
    c = node(unreal.MaterialExpressionConstant3Vector, -400, -200, constant=unreal.LinearColor(*colour, 1))
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    uv = world_uv(node, 100.0)
    nrm = node(unreal.MaterialExpressionTextureSample, -700, 200, texture=normal_tex, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uv, "", nrm, "UVs")
    mel.connect_material_property(nrm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -400, 500, r=roughness), "", unreal.MaterialProperty.MP_ROUGHNESS)
    return finish(m)


def build_floor(spec, material):
    name = "SM_PT_Floor"
    path = f"{FOLDER}/{name}"
    if library.does_asset_exist(path):
        library.delete_asset(path)
    mesh = asset_tools.create_asset(name, FOLDER, unreal.StaticMesh, None)
    desc = unreal.StaticMesh.create_static_mesh_description(mesh)
    group = desc.create_polygon_group()
    ids = []
    for p, uv in zip(spec["positions"], spec["uvs"]):
        v = desc.create_vertex()
        desc.set_vertex_position(v, unreal.Vector(*p))
        inst = desc.create_vertex_instance(v)
        desc.set_vertex_instance_uv(inst, unreal.Vector2D(uv[0], uv[1]), 0)
        ids.append(inst)
    idx = spec["indices"]
    for k in range(0, len(idx), 3):
        desc.create_triangle(group, [ids[idx[k]], ids[idx[k + 1]], ids[idx[k + 2]]])
    mesh.set_editor_property("static_materials", [unreal.StaticMaterial(material_interface=material, material_slot_name="Floor")])
    mesh.build_from_static_mesh_descriptions([desc], False, False)
    library.save_loaded_asset(mesh)
    return mesh


def spawn_mesh(mesh, location, rotation, scale, material, label):
    a = actors.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
    a.set_actor_label(label)
    c = a.static_mesh_component
    c.set_static_mesh(mesh)
    c.set_material(0, material)
    a.set_actor_scale3d(scale)
    return a


def make_variant(name, splat, floor_mesh, floor_material, lit, pillars, info, mats):
    levels.load_level(BASE_LEVEL)
    for a in actors.get_all_level_actors():
        if isinstance(a, unreal.ScanSplatActor):
            a.get_splat().set_splat_asset(splat)
        elif lit and isinstance(a, unreal.DirectionalLight):
            a.light_component.set_editor_property("intensity", 0.0)
        elif lit and isinstance(a, unreal.SkyLight):
            a.light_component.set_editor_property("intensity", SKY_LIGHT)
    f = spawn_mesh(floor_mesh, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0), unreal.Vector(1, 1, 1), floor_material, "PT_Floor")
    f.static_mesh_component.set_cast_shadow(False)
    if lit:
        for i, fx in enumerate(info["fixtures"]):
            light = actors.spawn_actor_from_class(unreal.RectLight, unreal.Vector(fx["x"], fx["y"], fx["z"] - 4.0), unreal.Rotator(-90, 0, 0))
            light.set_actor_label(f"PT_Fixture_{i:02d}")
            lc = light.get_component_by_class(unreal.RectLightComponent)
            lc.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
            lc.set_editor_property("intensity", LIGHT_LUMENS)
            lc.set_editor_property("source_width", fx["length"])
            lc.set_editor_property("source_height", 12.0)
            lc.set_editor_property("attenuation_radius", 1500.0)
            lc.set_editor_property("barn_door_angle", 88.0)
            lc.set_editor_property("light_color", unreal.Color(255, 250, 244, 255))
            lc.set_editor_property("cast_shadows", True)
    if pillars:
        cube = unreal.load_asset("/Engine/BasicShapes/Cube")
        for i, pb in enumerate(info["pillars"]):
            s = pb["size"] / 100.0
            for part, z0, z1, mat in (("Base", pb["floor"], pb["orange_top"], mats["orange"]), ("Shaft", pb["orange_top"], pb["top"], mats["grey"])):
                spawn_mesh(cube, unreal.Vector(pb["center"][0], pb["center"][1], (z0 + z1) / 2), unreal.Rotator(0, 0, pb["yaw"]),
                           unreal.Vector(s, s, (z1 - z0) / 100.0), mat, f"PT_Pillar{i:02d}_{part}")
    unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(), f"{BASE_LEVEL}_{name}")
    unreal.log(f"[ParkingHybrid] saved {BASE_LEVEL}_{name}")


def main():
    info = json.load(open(os.path.join(SRC, "hybrid.json")))
    splats = {}
    for name in ("PT_HybridFloor", "PT_Hybrid"):
        if not library.does_asset_exist(f"{FOLDER}/{name}") or os.environ.get("PT_REIMPORT"):
            import_file(os.path.join(SRC, f"{name}.ply"), FOLDER, name)
        splats[name] = unreal.load_asset(f"{FOLDER}/{name}")
        if not splats[name].is_nanite_enabled():
            splats[name].build_nanite_cluster_hierarchy()
            library.save_loaded_asset(splats[name])
    ortho = import_file(os.path.join(SRC, "floor_ortho.png"), f"{FOLDER}/Textures", "T_PT_FloorOrtho", "clamp")
    normal = import_file(os.path.join(PBR, "Concrete034_NormalDX.jpg"), f"{FOLDER}/Textures", "T_PT_Concrete034_N", "normal")
    rough = import_file(os.path.join(PBR, "Concrete034_Roughness.jpg"), f"{FOLDER}/Textures", "T_PT_Concrete034_R", "linear")
    plaster_n = import_file(os.path.join(PBR, "PaintedPlaster017_NormalDX.jpg"), f"{FOLDER}/Textures", "T_PT_Plaster_N", "normal")
    unlit = floor_unlit(ortho)
    pbr = floor_pbr(ortho, normal, rough)
    mats = {"orange": paint("M_PT_PaintOrange", (0.80, 0.16, 0.02), rough, plaster_n, 0.45),
            "grey": paint("M_PT_PaintGrey", (0.16, 0.16, 0.17), rough, plaster_n, 0.6)}
    floor_unlit_mesh = build_floor(info["floor"], unlit)
    make_variant("E3_FloorUnlit", splats["PT_HybridFloor"], floor_unlit_mesh, unlit, False, False, info, mats)
    make_variant("E4_FloorPBR", splats["PT_HybridFloor"], floor_unlit_mesh, pbr, True, False, info, mats)
    make_variant("E5_Hybrid", splats["PT_Hybrid"], floor_unlit_mesh, pbr, True, True, info, mats)


main()
