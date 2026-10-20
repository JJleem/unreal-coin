"""
Brings the hybrid road of a scan stage (make_road_layer.py) into Unreal:

  * imports <Name>_road.png as /Game/Stages/<Name>/T_<Name>_Road and the trimmed scan as /Game/Stages/<Name>/<Name>_Hybrid
  * creates the shared material /Game/Stages/Common/M_ScanRoad: unlit, the photo projected from above by world
    position, run through the same inverse ACES curve the splat composite uses, so the mesh and the splats come out
    of the tonemapper with the same colours
  * builds the road mesh SM_<Name>_Road and either
      - TARGET = "test": saves a copy of the stage as /Game/Stages/Lvl_<Name>Hybrid with the hybrid scan and the road
      - TARGET = "stage": changes /Game/Stages/Lvl_<Name> itself (after the test copy looked better)

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
LAYER_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "RoadLayers"))
NAME = "Hongdae"
TARGET = "test"
MATERIAL = "/Game/Stages/Common/M_ScanRoad"

# Brightness of the road against the splats. Unlit emissive goes through the stage's manual exposure, the splat
# composite does not; this factor undoes the exposure, found by matching screenshots (see HANDOFF.md)
EXPOSURE_COMPENSATION = 0.022

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary


def import_file(path, folder, name):
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
    return asset


def road_material():
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL):
        unreal.EditorAssetLibrary.delete_asset(MATERIAL)
    folder, name = MATERIAL.rsplit("/", 1)
    material = asset_tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)

    def node(cls, x, y, **props):
        expression = mel.create_material_expression(material, cls, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    # uv = (world xy - origin) / size
    world = node(unreal.MaterialExpressionWorldPosition, -1200, 0)
    world_xy = node(unreal.MaterialExpressionComponentMask, -1050, 0, r=True, g=True, b=False, a=False)
    mel.connect_material_expressions(world, "", world_xy, "")
    origin = node(unreal.MaterialExpressionVectorParameter, -1200, 150, parameter_name="Origin")
    origin_xy = node(unreal.MaterialExpressionComponentMask, -1050, 150, r=True, g=True, b=False, a=False)
    mel.connect_material_expressions(origin, "", origin_xy, "")
    size = node(unreal.MaterialExpressionVectorParameter, -1200, 300, parameter_name="Size", default_value=unreal.LinearColor(1000, 1000, 0, 0))
    size_xy = node(unreal.MaterialExpressionComponentMask, -1050, 300, r=True, g=True, b=False, a=False)
    mel.connect_material_expressions(size, "", size_xy, "")
    offset = node(unreal.MaterialExpressionSubtract, -900, 50)
    mel.connect_material_expressions(world_xy, "", offset, "A")
    mel.connect_material_expressions(origin_xy, "", offset, "B")
    uv = node(unreal.MaterialExpressionDivide, -750, 100)
    mel.connect_material_expressions(offset, "", uv, "A")
    mel.connect_material_expressions(size_xy, "", uv, "B")

    photo = node(unreal.MaterialExpressionTextureSampleParameter2D, -550, 100, parameter_name="Photo")
    mel.connect_material_expressions(uv, "", photo, "UVs")

    # the splat composite's inverse ACES fit (GaussianSplatComposite.usf), so both go through the tonemapper alike
    inverse = node(unreal.MaterialExpressionCustom, -250, 100, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                   code="float3 c = clamp(Color, 0.0, 0.99);\n"
                        "float3 A = 2.51 - c * 2.43;\nfloat3 B = 0.03 - c * 0.59;\nfloat3 C = -c * 0.14;\n"
                        "return (-B + sqrt(max(B * B - 4.0 * A * C, 0.0))) / (2.0 * A);")
    custom_input = unreal.CustomInput()
    custom_input.set_editor_property("input_name", "Color")
    inverse.set_editor_property("inputs", [custom_input])
    mel.connect_material_expressions(photo, "RGB", inverse, "Color")

    gain = node(unreal.MaterialExpressionScalarParameter, -250, 300, parameter_name="Exposure", default_value=EXPOSURE_COMPENSATION)
    emissive = node(unreal.MaterialExpressionMultiply, -50, 150)
    mel.connect_material_expressions(inverse, "", emissive, "A")
    mel.connect_material_expressions(gain, "", emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def road_mesh(info, package_path, material):
    asset_path = f"{package_path}/SM_{NAME}_Road"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)
    mesh = asset_tools.create_asset(f"SM_{NAME}_Road", package_path, unreal.StaticMesh, None)
    desc = unreal.StaticMesh.create_static_mesh_description(mesh)
    group = desc.create_polygon_group()
    instances = []
    for p in info["vertices"]:
        vertex = desc.create_vertex()
        desc.set_vertex_position(vertex, unreal.Vector(p[0], p[1], p[2]))
        instances.append(desc.create_vertex_instance(vertex))
    v = info["vertices"]
    idx = info["indices"]
    for i in range(0, len(idx), 3):
        a, b, c = idx[i], idx[i + 1], idx[i + 2]
        # front faces up: Unreal's normal is (P2 - P0) x (P1 - P0)
        e1 = [v[c][k] - v[a][k] for k in range(3)]
        e2 = [v[b][k] - v[a][k] for k in range(3)]
        if e1[0] * e2[1] - e1[1] * e2[0] < 0:
            b, c = c, b
        desc.create_triangle(group, [instances[a], instances[b], instances[c]])
    mesh.set_editor_property("static_materials", [unreal.StaticMaterial(material_interface=material)])
    mesh.build_from_static_mesh_descriptions([desc], False, False)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    return mesh


def main():
    with open(os.path.join(LAYER_DIR, f"{NAME}_road.json")) as f:
        info = json.load(f)
    package_path = f"/Game/Stages/{NAME}"

    texture = import_file(os.path.join(LAYER_DIR, f"{NAME}_road.png"), package_path, f"T_{NAME}_Road")
    texture.set_editor_property("srgb", True)
    texture.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
    texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)

    material = road_material()
    instance_path = f"{package_path}/MI_{NAME}_Road"
    if unreal.EditorAssetLibrary.does_asset_exist(instance_path):
        unreal.EditorAssetLibrary.delete_asset(instance_path)
    instance = asset_tools.create_asset(f"MI_{NAME}_Road", package_path, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    instance.set_editor_property("parent", material)
    mel.set_material_instance_vector_parameter_value(instance, "Origin", unreal.LinearColor(info["origin"][0], info["origin"][1], 0, 0))
    mel.set_material_instance_vector_parameter_value(instance, "Size", unreal.LinearColor(info["size"][0], info["size"][1], 0, 0))
    mel.set_material_instance_texture_parameter_value(instance, "Photo", texture)
    unreal.EditorAssetLibrary.save_loaded_asset(instance)

    mesh = road_mesh(info, package_path, instance)

    # the trimmed scan, with the same render settings as the stage's
    splat_job = os.path.join(LAYER_DIR, f"{NAME}_hybrid.ply")
    splat = import_file(splat_job, package_path, f"{NAME}_Hybrid")
    if not splat.is_nanite_enabled():
        splat.build_nanite_cluster_hierarchy()
        unreal.EditorAssetLibrary.save_loaded_asset(splat)

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    levels.load_level(f"/Game/Stages/Lvl_{NAME}")
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label() == "Road":
            actors.destroy_actor(actor)
        elif isinstance(actor, unreal.ScanSplatActor):
            actor.get_splat().set_splat_asset(splat)
    road = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    road.set_actor_label("Road")
    component = road.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("NoCollision")
    component.set_cast_shadow(False)

    if TARGET == "stage":
        levels.save_current_level()
        unreal.log(f"[Road] Updated /Game/Stages/Lvl_{NAME}")
    else:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, f"/Game/Stages/Lvl_{NAME}Hybrid"):
            raise RuntimeError("Failed to save the test level")
        unreal.log(f"[Road] Saved /Game/Stages/Lvl_{NAME}Hybrid ({info['kept']:,} splats, {len(info['indices']) // 3} road triangles)")


main()
