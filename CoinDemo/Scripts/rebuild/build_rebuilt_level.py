"""
Phase 5 of the stage rebuild, in Unreal: builds the test levels from SourceAssets/Rebuilt/<Name>/ (build_geometry.py).

  /Game/Stages/Rebuilt/<Name>/      facade photos, materials, one mesh per facade (with collision), the trimmed scan
  /Game/Stages/Lvl_<Name>_Rebuilt      the stage with the rebuilt buildings and the trimmed scan (hybrid)
  /Game/Stages/Lvl_<Name>_RebuiltMesh  the same without any splats: buildings and the road layer mesh only

The stage itself (/Game/Stages/Lvl_<Name>) is only read: the test levels are copies with the changes, saved under
new names. build_scan_stages.py never touches /Game/Stages/Rebuilt or these levels.

Materials are unlit, like the splats: the photos already carry the scan's light. They go through the same inverse
ACES curve the splat composite uses and the stage's exposure compensation, so buildings and splats match.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "Hongdae"
SOURCE = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "Rebuilt", NAME))
FOLDER = f"/Game/Stages/Rebuilt/{NAME}"
FACADE_MATERIAL = "/Game/Stages/Rebuilt/M_RebuiltFacade"
PLAIN_MATERIAL = "/Game/Stages/Rebuilt/M_RebuiltPlain"

# same as build_road_layer.py: unlit emissive against the scan stages' manual exposure
EXPOSURE_COMPENSATION = 0.022
INVERSE_ACES = ("float3 c = clamp(Color, 0.0, 0.99);\n"
                "float3 A = 2.51 - c * 2.43;\nfloat3 B = 0.03 - c * 0.59;\nfloat3 C = -c * 0.14;\n"
                "return (-B + sqrt(max(B * B - 4.0 * A * C, 0.0))) / (2.0 * A);")

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
library = unreal.EditorAssetLibrary


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


def new_material(path):
    if library.does_asset_exist(path):
        library.delete_asset(path)
    folder, name = path.rsplit("/", 1)
    material = asset_tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)

    def node(cls, x, y, **props):
        expression = mel.create_material_expression(material, cls, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    return material, node


def finish(material, colour, node):
    """emissive = inverse ACES(colour) x exposure compensation"""
    inverse = node(unreal.MaterialExpressionCustom, -250, 100, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3, code=INVERSE_ACES)
    custom_input = unreal.CustomInput()
    custom_input.set_editor_property("input_name", "Color")
    inverse.set_editor_property("inputs", [custom_input])
    mel.connect_material_expressions(colour, "RGB" if isinstance(colour, unreal.MaterialExpressionTextureSampleParameter2D) else "", inverse, "Color")
    gain = node(unreal.MaterialExpressionScalarParameter, -250, 300, parameter_name="Exposure", default_value=EXPOSURE_COMPENSATION)
    emissive = node(unreal.MaterialExpressionMultiply, -50, 150)
    mel.connect_material_expressions(inverse, "", emissive, "A")
    mel.connect_material_expressions(gain, "", emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(material)
    library.save_loaded_asset(material)
    return material


def facade_material():
    """A face photo projected by world position: u = dot(xy - origin.xy, UAxis.xy) / size.x, v = (origin.z - z) / size.y."""
    material, node = new_material(FACADE_MATERIAL)
    world = node(unreal.MaterialExpressionWorldPosition, -1600, 0)
    origin = node(unreal.MaterialExpressionVectorParameter, -1600, 200, parameter_name="Origin")
    axis = node(unreal.MaterialExpressionVectorParameter, -1600, 400, parameter_name="UAxis", default_value=unreal.LinearColor(1, 0, 0, 0))
    size = node(unreal.MaterialExpressionVectorParameter, -1600, 600, parameter_name="Size", default_value=unreal.LinearColor(100, 100, 0, 0))
    mask = lambda x, y, **c: node(unreal.MaterialExpressionComponentMask, x, y, a=False, **c)
    wxy, wz = mask(-1400, 0, r=True, g=True, b=False), mask(-1400, 80, r=False, g=False, b=True)
    oxy, oz = mask(-1400, 200, r=True, g=True, b=False), mask(-1400, 280, r=False, g=False, b=True)
    axy = mask(-1400, 400, r=True, g=True, b=False)
    sx, sy = mask(-1400, 600, r=True, g=False, b=False), mask(-1400, 680, r=False, g=True, b=False)
    for a, b in ((world, wxy), (world, wz), (origin, oxy), (origin, oz), (axis, axy), (size, sx), (size, sy)):
        mel.connect_material_expressions(a, "", b, "")
    rel = node(unreal.MaterialExpressionSubtract, -1200, 0)
    mel.connect_material_expressions(wxy, "", rel, "A")
    mel.connect_material_expressions(oxy, "", rel, "B")
    along = node(unreal.MaterialExpressionDotProduct, -1050, 0)
    mel.connect_material_expressions(rel, "", along, "A")
    mel.connect_material_expressions(axy, "", along, "B")
    u = node(unreal.MaterialExpressionDivide, -900, 0)
    mel.connect_material_expressions(along, "", u, "A")
    mel.connect_material_expressions(sx, "", u, "B")
    dv = node(unreal.MaterialExpressionSubtract, -1050, 200)
    mel.connect_material_expressions(oz, "", dv, "A")
    mel.connect_material_expressions(wz, "", dv, "B")
    v = node(unreal.MaterialExpressionDivide, -900, 200)
    mel.connect_material_expressions(dv, "", v, "A")
    mel.connect_material_expressions(sy, "", v, "B")
    uv = node(unreal.MaterialExpressionAppendVector, -750, 100)
    mel.connect_material_expressions(u, "", uv, "A")
    mel.connect_material_expressions(v, "", uv, "B")
    photo = node(unreal.MaterialExpressionTextureSampleParameter2D, -550, 100, parameter_name="Photo")
    mel.connect_material_expressions(uv, "", photo, "UVs")
    return finish(material, photo, node)


def plain_material():
    """Roofs, sides and backs: one flat colour (the scan doesn't show them)."""
    material, node = new_material(PLAIN_MATERIAL)
    colour = node(unreal.MaterialExpressionVectorParameter, -550, 100, parameter_name="Color", default_value=unreal.LinearColor(0.45, 0.44, 0.42, 1))
    return finish(material, colour, node)


def instance(path, parent, vectors=None, textures=None):
    if library.does_asset_exist(path):
        library.delete_asset(path)
    folder, name = path.rsplit("/", 1)
    mi = asset_tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", parent)
    for key, value in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(mi, key, value)
    for key, value in (textures or {}).items():
        mel.set_material_instance_texture_parameter_value(mi, key, value)
    library.save_loaded_asset(mi)
    return mi


def facade_mesh(name, boxes, slot_of_face, materials):
    """Boxes as one mesh; every face goes to the section of its photo (slot_of_face) or to the last, plain one."""
    path = f"{FOLDER}/{name}"
    if library.does_asset_exist(path):
        library.delete_asset(path)
    mesh = asset_tools.create_asset(name, FOLDER, unreal.StaticMesh, None)
    desc = unreal.StaticMesh.create_static_mesh_description(mesh)
    groups = [desc.create_polygon_group() for _ in materials]
    for box in boxes:
        lo, hi = box["min"], box["max"]
        corners = [(hi[0] if c & 1 else lo[0], hi[1] if c & 2 else lo[1], hi[2] if c & 4 else lo[2]) for c in range(8)]
        faces = [((0, 4, 6, 2), "-X"), ((1, 3, 7, 5), "+X"), ((0, 1, 5, 4), "-Y"), ((2, 6, 7, 3), "+Y"), ((4, 5, 7, 6), "+Z")]
        for quad, facing in faces:
            ids = []
            for c in quad:
                vertex = desc.create_vertex()
                desc.set_vertex_position(vertex, unreal.Vector(*corners[c]))
                ids.append(desc.create_vertex_instance(vertex))
            face = box["faces"].get(facing)
            group = groups[slot_of_face[face]] if face is not None else groups[-1]
            desc.create_triangle(group, [ids[0], ids[2], ids[1]])
            desc.create_triangle(group, [ids[0], ids[3], ids[2]])
    mesh.set_editor_property("static_materials", [unreal.StaticMaterial(material_interface=m, material_slot_name=f"Slot{i}") for i, m in enumerate(materials)])
    mesh.build_from_static_mesh_descriptions([desc], False, False)
    body = mesh.get_editor_property("body_setup")
    if body:
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    library.save_loaded_asset(mesh)
    return mesh


def main():
    with open(os.path.join(SOURCE, "rebuilt.json")) as f:
        info = json.load(f)
    facade = facade_material()
    plain = plain_material()

    # one material instance per face photo
    face_materials = []
    for index, face in enumerate(info["faces"]):
        texture = import_file(os.path.join(SOURCE, face["file"]), FOLDER, f"T_Face_{index:03d}")
        texture.set_editor_property("srgb", True)
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
        # BC7 keeps the photo's fine detail that the default compression smears
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
        library.save_loaded_asset(texture)
        face_materials.append(instance(f"{FOLDER}/MI_Face_{index:03d}", facade,
                                       {"Origin": unreal.LinearColor(*face["origin"], 0),
                                        "UAxis": unreal.LinearColor(face["u"][0], face["u"][1], 0, 0),
                                        "Size": unreal.LinearColor(face["size"][0], face["size"][1], 0, 0)},
                                       {"Photo": texture}))

    by_facade = {}
    for box in info["boxes"]:
        by_facade.setdefault(box["facade"], []).append(box)
    meshes = []
    for facade_index, boxes in sorted(by_facade.items()):
        used = sorted({f for box in boxes for f in box["faces"].values()})
        slot_of_face = {f: i for i, f in enumerate(used)}
        # roofs, sides and backs a little darker than the lower facade, which is mostly lit shop fronts
        r, g, b = boxes[0]["average"]
        plain_mi = instance(f"{FOLDER}/MI_Plain_{facade_index:02d}", plain, {"Color": unreal.LinearColor(r * 0.6, g * 0.6, b * 0.6, 1)})
        meshes.append(facade_mesh(f"SM_Building_{facade_index:02d}", boxes, slot_of_face, [face_materials[f] for f in used] + [plain_mi]))

    splat = import_file(os.path.join(SOURCE, f"{NAME}_rebuilt.ply"), FOLDER, f"{NAME}_Rebuilt")
    if not splat.is_nanite_enabled():
        splat.build_nanite_cluster_hierarchy()
        library.save_loaded_asset(splat)

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels.load_level(f"/Game/Stages/Lvl_{NAME}")
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.ScanSplatActor):
            actor.get_splat().set_splat_asset(splat)
    for mesh in meshes:
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(f"Rebuilt_{mesh.get_name()}")
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.static_mesh_component.set_collision_profile_name("BlockAll")
        # the scan can't receive shadows: a building shadow would fall only on the character
        actor.static_mesh_component.set_cast_shadow(False)
    if not unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(), f"/Game/Stages/Lvl_{NAME}_Rebuilt"):
        raise RuntimeError("Failed to save the hybrid level")

    # meshes only: no splats, the road layer mesh as the ground
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.ScanSplatActor):
            actors.destroy_actor(actor)
    road = unreal.load_asset(f"/Game/Stages/{NAME}/SM_{NAME}_Road")
    if road:
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label("Rebuilt_Ground")
        actor.static_mesh_component.set_static_mesh(road)
        actor.static_mesh_component.set_collision_profile_name("NoCollision")
    if not unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(), f"/Game/Stages/Lvl_{NAME}_RebuiltMesh"):
        raise RuntimeError("Failed to save the mesh-only level")
    unreal.log(f"[Rebuilt] {len(meshes)} building meshes, {len(info['faces'])} face photos, {info['kept']:,} splats kept; saved Lvl_{NAME}_Rebuilt and Lvl_{NAME}_RebuiltMesh")


main()
