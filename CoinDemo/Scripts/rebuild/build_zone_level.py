"""
Brings a rebuilt zone (build_zone.py) into Unreal as the test level /Game/Stages/Lvl_<Stage>_Zone<Zone>.

  * imports the CC0 PBR textures (SourceAssets/Textures/pbr), the control map and the sign crops
  * creates lit materials in /Game/Stages/Rebuilt/Zone: a tiling PBR master, the road (asphalt with red pavement and
    the paint from the control map), glass, signs and manhole covers, plus one instance per surface
  * builds the zone's static meshes with their UVs and collision, imports the trimmed scan
  * copies the stage with the trimmed scan and the meshes into the test level; the stage itself is not changed

  ZONE below, then: UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
# the zone to build: generated/zone_job.txt if present (written by the caller), else zone A
_JOB = os.path.join(HERE, "..", "generated", "zone_job.txt")
ZONE = open(_JOB).read().strip() if os.path.exists(_JOB) else "Hongdae_A"
STAGE, ZONE_LETTER = ZONE.split("_")
SOURCE = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets"))
ZONE_DIR = os.path.join(SOURCE, "Rebuilt", ZONE)
PBR_DIR = os.path.join(SOURCE, "Textures", "pbr")
COMMON = "/Game/Stages/Rebuilt/Zone"
FOLDER = f"/Game/Stages/Rebuilt/{ZONE}"
LEVEL = f"/Game/Stages/Lvl_{STAGE}_Zone{ZONE_LETTER}"

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
library = unreal.EditorAssetLibrary

ROAD_SET = "Road012A"
MACRO_TEXTURE = [None]   # set in main(): the concrete colour texture, used for large scale variation
# linear average of each colour texture, so tints can bring a texture to the scan's average colour
TEXTURE_AVERAGE = {"Road012A": 0.052, "Concrete034": 0.482, "Tiles141": 0.603}
# The stage lights are tuned for the character alone over unlit splats and come out about 9x too bright (and warm,
# from the atmosphere) on lit surfaces whose albedo matches the scan. The zone level scales and white balances them so
# meshes, splats and the character agree; measured by comparing screenshots of the same view (calibration json)
LIGHT_SCALE = 0.11
# Dimming the sun also dims the sky the atmosphere draws behind the scan (deep blue instead of the pale overcast
# the scan was filmed in); its luminance is raised back by the same factor. (Scaling the albedos down instead kept
# the sky but left the meshes grey and flat under the full strength sky light.)
SKY_LUMINANCE = 1.0 / LIGHT_SCALE
# the sky light is dimmed less than the sun: surfaces facing away from the sun (curb faces, awning undersides)
# went black at the sun's factor
SKYLIGHT_SCALE = 0.3
ALBEDO_SCALE = 1.0
LIGHT_COLOR = (1.0, 1.0, 1.0)
PHOTO_EXPOSURE = 0.022   # unlit photo brightness under the stages' manual exposure, as in build_road_layer.py

# surface -> (PBR set, tile size m, tint, metallic, roughness scale, rotate uv)
SURFACES = {
    "Sidewalk": ("Tiles141", 1.5, None, 0.0, 1.0, 0),        # 30 cm pavers, tinted to the scan's sidewalk colour
    "Curb": ("Concrete034", 1.0, (0.85, 0.85, 0.83), 0.0, 1.0, 0),
    "Plaster": ("PaintedPlaster017", 3.0, (0.75, 0.74, 0.72), 0.0, 1.0, 0),
    "Cladding": ("Metal063", 2.0, (0.55, 0.20, 0.15), 0.2, 0.9, 0),
    "Brick": ("Bricks097", 1.6, (0.85, 0.70, 0.64), 0.0, 1.0, 0),
    "Awning": ("CorrugatedSteel009", 1.0, (0.85, 0.85, 0.82), 0.6, 0.8, 1),
    "Roof": ("RoofingTiles014B", 2.0, (0.55, 0.45, 0.42), 0.0, 1.0, 0),
    "Frame": ("Metal046B", 1.0, (0.30, 0.30, 0.30), 0.9, 0.7, 0),
    "Trim": ("Metal063", 2.0, (0.42, 0.42, 0.42), 0.3, 0.8, 0),
    "SignFrame": ("Metal046B", 1.0, (0.12, 0.12, 0.12), 0.8, 0.6, 0),
    "Steel": ("Metal063", 1.5, (0.55, 0.55, 0.55), 0.6, 0.8, 0),
    "SteelDark": ("Metal046B", 1.0, (2.8, 2.8, 2.9), 0.3, 0.8, 0),
    "SteelTread": ("MetalPlates006", 0.8, (3.0, 3.0, 3.0), 0.3, 0.9, 0),
    "Stainless": ("Metal063", 1.0, (1.4, 1.4, 1.45), 0.9, 0.5, 0),
    "ConeOrange": ("PaintedPlaster017", 1.0, (1.0, 0.25, 0.04), 0.0, 0.7, 0),
    "ConeWhite": ("PaintedPlaster017", 1.0, (0.95, 0.95, 0.95), 0.0, 0.6, 0),
    "ConeBlack": ("Metal046B", 1.0, (0.05, 0.05, 0.05), 0.0, 1.0, 0),
    "Grate": ("Grate002", 1.0, (0.9, 0.85, 0.8), 0.7, 1.0, 0),
}


def import_texture(path, folder, name, kind):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    task.set_editor_property("replace_existing", True)
    asset_tools.import_asset_tasks([task])
    texture = unreal.load_asset(f"{folder}/{name}")
    if kind == "normal":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
    elif kind == "linear":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        texture.set_editor_property("srgb", False)
    elif kind == "control":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
        texture.set_editor_property("srgb", False)
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    elif kind == "sign":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    library.save_loaded_asset(texture)
    return texture


def new_material(path, two_sided=False):
    if library.does_asset_exist(path):
        library.delete_asset(path)
    folder, name = path.rsplit("/", 1)
    material = asset_tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("two_sided", two_sided)

    def node(cls, x, y, **props):
        expression = mel.create_material_expression(material, cls, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def link(a, b, pin="", out=""):
        mel.connect_material_expressions(a, out, b, pin)

    return material, node, link


def save(material):
    mel.recompile_material(material)
    library.save_loaded_asset(material)
    return material


def pbr_uv(node, link, x=-1400, y=0, tile_size=None, rotate90=None):
    """UV0 (metres) / TileSize, optionally rotated by 90 degrees (parameters, or constants when given)."""
    uv = node(unreal.MaterialExpressionTextureCoordinate, x, y)
    tile = node(unreal.MaterialExpressionScalarParameter, x, y + 120, parameter_name="TileSize", default_value=1.0) if tile_size is None \
        else node(unreal.MaterialExpressionConstant, x, y + 120, r=tile_size)
    scaled = node(unreal.MaterialExpressionDivide, x + 180, y)
    link(uv, scaled, "A")
    link(tile, scaled, "B")
    swizzle = node(unreal.MaterialExpressionComponentMask, x + 330, y + 80, r=True, g=True, b=False, a=False)
    link(scaled, swizzle)
    u = node(unreal.MaterialExpressionComponentMask, x + 330, y + 160, r=True, g=False, b=False, a=False)
    v = node(unreal.MaterialExpressionComponentMask, x + 330, y + 220, r=False, g=True, b=False, a=False)
    link(scaled, u)
    link(scaled, v)
    swapped = node(unreal.MaterialExpressionAppendVector, x + 480, y + 180)
    link(v, swapped, "A")
    link(u, swapped, "B")
    rotate = node(unreal.MaterialExpressionScalarParameter, x + 480, y + 300, parameter_name="Rotate90", default_value=0.0) if rotate90 is None \
        else node(unreal.MaterialExpressionConstant, x + 480, y + 300, r=float(rotate90))
    result = node(unreal.MaterialExpressionLinearInterpolate, x + 650, y + 100)
    link(swizzle, result, "A")
    link(swapped, result, "B")
    link(rotate, result, "Alpha")
    return result


def pbr_surface(name, t, tile, tint, metallic, rough, rotate):
    """Tiling PBR surface: Color x Tint, NormalDX, Roughness x scale, Metallic. A material of its own per surface
    (textures set on the nodes): parameter overrides on Python-made instances of a shared master rendered with the
    engine's default checker texture in -game runs."""
    material, node, link = new_material(f"{FOLDER}/M_{name}")
    uv = pbr_uv(node, link, tile_size=tile, rotate90=rotate)
    color = node(unreal.MaterialExpressionTextureSample, -500, -200, texture=t["Color"])
    normal = node(unreal.MaterialExpressionTextureSample, -500, 100, texture=t["NormalDX"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    roughness = node(unreal.MaterialExpressionTextureSample, -500, 400, texture=t["Roughness"], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for sample in (color, normal, roughness):
        link(uv, sample, "UVs")
    tint_node = node(unreal.MaterialExpressionConstant3Vector, -300, -350, constant=unreal.LinearColor(*tint, 1.0))
    base = node(unreal.MaterialExpressionMultiply, -150, -250)
    link(color, base, "A", "RGB")
    link(tint_node, base, "B")
    if MACRO_TEXTURE[0] is not None and tile > 0.9 and name not in ("Grate",):
        # large scale variation (grime, wear, patches) from a low frequency sample of a concrete texture over
        # 7 m, so the tiling doesn't show; brightness varies by about +-10 %
        coord = node(unreal.MaterialExpressionTextureCoordinate, -900, -700)
        big = node(unreal.MaterialExpressionDivide, -750, -700, const_b=7.0)
        link(coord, big, "A")
        macro = node(unreal.MaterialExpressionTextureSample, -600, -700, texture=MACRO_TEXTURE[0])
        link(big, macro, "UVs")
        vary = node(unreal.MaterialExpressionLinearInterpolate, -400, -650, const_a=0.78, const_b=1.12)
        link(macro, vary, "Alpha", "R")
        varied = node(unreal.MaterialExpressionMultiply, -50, -300)
        link(base, varied, "A")
        link(vary, varied, "B")
        base = varied
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)
    r = node(unreal.MaterialExpressionMultiply, -150, 450, const_b=rough)
    link(roughness, r, "A", "R")
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -150, 650, r=metallic), "", unreal.MaterialProperty.MP_METALLIC)
    return save(material)


def road_material(textures, control, info):
    """Asphalt (CC0 PBR) tinted to the scan's colours, red pavement and paint from the control map."""
    material, node, link = new_material(f"{COMMON}/M_ZoneRoad")
    uv = pbr_uv(node, link)
    color = node(unreal.MaterialExpressionTextureSampleParameter2D, -500, -200, parameter_name="Color", texture=textures[ROAD_SET]["Color"])
    normal = node(unreal.MaterialExpressionTextureSampleParameter2D, -500, 100, parameter_name="Normal", texture=textures[ROAD_SET]["NormalDX"],
                  sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    rough = node(unreal.MaterialExpressionTextureSampleParameter2D, -500, 400, parameter_name="Roughness", texture=textures[ROAD_SET]["Roughness"],
                 sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for t in (color, normal, rough):
        link(uv, t, "UVs")

    # control map placed over the zone box by world position (cm)
    world = node(unreal.MaterialExpressionWorldPosition, -1400, 700)
    wxy = node(unreal.MaterialExpressionComponentMask, -1250, 700, r=True, g=True, b=False, a=False)
    link(world, wxy)
    x0, x1, y0, y1 = info["box"]
    origin = node(unreal.MaterialExpressionConstant2Vector, -1250, 800, r=x0 * 100.0, g=y0 * 100.0)
    size = node(unreal.MaterialExpressionConstant2Vector, -1250, 880, r=(x1 - x0) * 100.0, g=(y1 - y0) * 100.0)
    rel = node(unreal.MaterialExpressionSubtract, -1100, 750)
    link(wxy, rel, "A")
    link(origin, rel, "B")
    cuv = node(unreal.MaterialExpressionDivide, -950, 780)
    link(rel, cuv, "A")
    link(size, cuv, "B")
    # the control png is stored [y rows, x columns]: u = x, v = y
    ctrl = node(unreal.MaterialExpressionTextureSampleParameter2D, -800, 780, parameter_name="Control", texture=control,
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    link(cuv, ctrl, "UVs")

    asphalt_tint = node(unreal.MaterialExpressionVectorParameter, -500, -450, parameter_name="AsphaltTint", default_value=unreal.LinearColor(1, 1, 1, 1))
    red_tint = node(unreal.MaterialExpressionVectorParameter, -500, -550, parameter_name="RedTint", default_value=unreal.LinearColor(1.3, 0.8, 0.8, 1))
    tint = node(unreal.MaterialExpressionLinearInterpolate, -300, -500)
    link(asphalt_tint, tint, "A")
    link(red_tint, tint, "B")
    link(ctrl, tint, "Alpha", "R")
    macro = node(unreal.MaterialExpressionLinearInterpolate, -300, -650, const_a=0.75, const_b=1.25)
    link(ctrl, macro, "Alpha", "A")
    tinted = node(unreal.MaterialExpressionMultiply, -250, -400)
    link(tint, tinted, "A")
    link(macro, tinted, "B")
    surface = node(unreal.MaterialExpressionMultiply, -150, -300)
    link(color, surface, "A", "RGB")
    link(tinted, surface, "B")
    white = node(unreal.MaterialExpressionVectorParameter, -150, -600, parameter_name="WhitePaint", default_value=unreal.LinearColor(0.75 * ALBEDO_SCALE, 0.75 * ALBEDO_SCALE, 0.72 * ALBEDO_SCALE, 1))
    yellow = node(unreal.MaterialExpressionVectorParameter, -150, -700, parameter_name="YellowPaint", default_value=unreal.LinearColor(0.75 * ALBEDO_SCALE, 0.5 * ALBEDO_SCALE, 0.08 * ALBEDO_SCALE, 1))
    with_white = node(unreal.MaterialExpressionLinearInterpolate, 50, -400)
    link(surface, with_white, "A")
    link(white, with_white, "B")
    link(ctrl, with_white, "Alpha", "G")
    with_yellow = node(unreal.MaterialExpressionLinearInterpolate, 200, -400)
    link(with_white, with_yellow, "A")
    link(yellow, with_yellow, "B")
    link(ctrl, with_yellow, "Alpha", "B")
    mel.connect_material_property(with_yellow, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # paint is smoother and flatter than the asphalt it lies on
    paint = node(unreal.MaterialExpressionAdd, -300, 900)
    link(ctrl, paint, "A", "G")
    link(ctrl, paint, "B", "B")
    paint_clamped = node(unreal.MaterialExpressionSaturate, -150, 900)
    link(paint, paint_clamped)
    paint_rough = node(unreal.MaterialExpressionConstant, -150, 600, r=0.45)
    r = node(unreal.MaterialExpressionLinearInterpolate, 50, 500)
    link(rough, r, "A", "R")
    link(paint_rough, r, "B")
    link(paint_clamped, r, "Alpha")
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    flat = node(unreal.MaterialExpressionConstant3Vector, -150, 250, constant=unreal.LinearColor(0, 0, 1, 1))
    n = node(unreal.MaterialExpressionLinearInterpolate, 50, 150)
    link(normal, n, "A", "RGB")
    link(flat, n, "B")
    link(paint_clamped, n, "Alpha")
    mel.connect_material_property(n, "", unreal.MaterialProperty.MP_NORMAL)
    return save(material)


def glass_material():
    material, node, link = new_material(f"{COMMON}/M_ZoneGlass")
    base = node(unreal.MaterialExpressionVectorParameter, -300, 0, parameter_name="Color", default_value=unreal.LinearColor(0.002, 0.003, 0.0035, 1))
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -300, 150, r=0.04), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -300, 220, r=1.0), "", unreal.MaterialProperty.MP_SPECULAR)
    return save(material)


def photo_glass_material(name, record, texture):
    """Glass showing the facade photo projected by world position (u along the photo's axis, v down), glossy."""
    material, node, link = new_material(f"{FOLDER}/M_{name}")
    world = node(unreal.MaterialExpressionWorldPosition, -1600, 0)
    wxy = node(unreal.MaterialExpressionComponentMask, -1400, 0, r=True, g=True, b=False, a=False)
    wz = node(unreal.MaterialExpressionComponentMask, -1400, 100, r=False, g=False, b=True, a=False)
    link(world, wxy)
    link(world, wz)
    ox, oy, oz = (c * 100.0 for c in record["origin"])
    su, sv = (c * 100.0 for c in record["size"])
    rel = node(unreal.MaterialExpressionSubtract, -1250, 0)
    link(wxy, rel, "A")
    link(node(unreal.MaterialExpressionConstant2Vector, -1400, 200, r=ox, g=oy), rel, "B")
    along = node(unreal.MaterialExpressionDotProduct, -1100, 0)
    link(rel, along, "A")
    link(node(unreal.MaterialExpressionConstant2Vector, -1250, 200, r=record["u"][0], g=record["u"][1]), along, "B")
    u = node(unreal.MaterialExpressionDivide, -950, 0, const_b=su)
    link(along, u, "A")
    down = node(unreal.MaterialExpressionSubtract, -1100, 150, const_a=oz)
    link(wz, down, "B")
    v = node(unreal.MaterialExpressionDivide, -950, 150, const_b=sv)
    link(down, v, "A")
    uv = node(unreal.MaterialExpressionAppendVector, -800, 80)
    link(u, uv, "A")
    link(v, uv, "B")
    photo = node(unreal.MaterialExpressionTextureSample, -600, 80, texture=texture)
    link(uv, photo, "UVs")
    # what the photo shows (the shop inside, reflections) is already lit: it is emitted like the splats are drawn
    # (same inverse ACES and exposure compensation as the unlit rebuild), the surface itself is dark and glossy
    inverse = node(unreal.MaterialExpressionCustom, -400, 80, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                   code="float3 c = clamp(Color, 0.0, 0.99);\nfloat3 A = 2.51 - c * 2.43;\nfloat3 B = 0.03 - c * 0.59;\nfloat3 C = -c * 0.14;\n"
                        "return (-B + sqrt(max(B * B - 4.0 * A * C, 0.0))) / (2.0 * A);")
    custom_input = unreal.CustomInput()
    custom_input.set_editor_property("input_name", "Color")
    inverse.set_editor_property("inputs", [custom_input])
    link(photo, inverse, "Color", "RGB")
    emissive = node(unreal.MaterialExpressionMultiply, -200, 80, const_b=PHOTO_EXPOSURE)
    link(inverse, emissive, "A")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant3Vector, -200, -60, constant=unreal.LinearColor(0.01, 0.01, 0.01, 1)), "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -400, 250, r=0.12), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -400, 320, r=0.7), "", unreal.MaterialProperty.MP_SPECULAR)
    return save(material)


def sign_material():
    material, node, link = new_material(f"{COMMON}/M_ZoneSign")
    photo = node(unreal.MaterialExpressionTextureSampleParameter2D, -400, 0, parameter_name="Photo")
    base = node(unreal.MaterialExpressionMultiply, -200, 0, const_b=ALBEDO_SCALE)
    link(photo, base, "A", "RGB")
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, -300, 200, r=0.55), "", unreal.MaterialProperty.MP_ROUGHNESS)
    return save(material)


def manhole_material(textures):
    """Cast iron cover: metal PBR with concentric grooves (round) or a grid (square) cut into the normal."""
    material, node, link = new_material(f"{COMMON}/M_ZoneManhole")
    uv = node(unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    color = node(unreal.MaterialExpressionTextureSample, -500, -200, texture=textures["Metal046B"]["Color"])
    link(uv, color, "UVs")
    centred = node(unreal.MaterialExpressionSubtract, -1050, 200, const_b=0.5)
    link(uv, centred, "A")
    radius = node(unreal.MaterialExpressionLength, -900, 200)
    link(centred, radius)
    rings = node(unreal.MaterialExpressionMultiply, -750, 200, const_b=14.0)
    link(radius, rings, "A")
    frac = node(unreal.MaterialExpressionFrac, -600, 200)
    link(rings, frac)
    groove = node(unreal.MaterialExpressionStep, -450, 200, const_y=0.2)  # 1 inside the groove band
    link(frac, groove, "X")
    rim = node(unreal.MaterialExpressionStep, -450, 320, const_x=0.44)    # outer rim ring
    link(radius, rim, "Y")
    dark = node(unreal.MaterialExpressionMax, -300, 260)
    link(groove, dark, "A")
    link(rim, dark, "B")
    shade = node(unreal.MaterialExpressionLinearInterpolate, -150, 0, const_a=1.0, const_b=0.35)
    link(dark, shade, "Alpha")
    tint = node(unreal.MaterialExpressionVectorParameter, -300, -350, parameter_name="Tint", default_value=unreal.LinearColor(1.6 * ALBEDO_SCALE, 1.5 * ALBEDO_SCALE, 1.4 * ALBEDO_SCALE, 1))
    base = node(unreal.MaterialExpressionMultiply, 0, -200)
    link(color, base, "A", "RGB")
    link(tint, base, "B")
    final = node(unreal.MaterialExpressionMultiply, 150, -100)
    link(base, final, "A")
    link(shade, final, "B")
    mel.connect_material_property(final, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, 0, 300, r=0.3), "", unreal.MaterialProperty.MP_METALLIC)
    rough = node(unreal.MaterialExpressionLinearInterpolate, 0, 400, const_a=0.5, const_b=0.8)
    link(dark, rough, "Alpha")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    return save(material)


def instance(path, parent, scalars=None, vectors=None, textures=None):
    if library.does_asset_exist(path):
        library.delete_asset(path)
    folder, name = path.rsplit("/", 1)
    mi = asset_tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", parent)
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(mi, k, v)
    for k, v in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*v, 1.0))
    for k, v in (textures or {}).items():
        mel.set_material_instance_texture_parameter_value(mi, k, v)
    # without this the overrides are saved but the instance keeps rendering with the parent's defaults
    mel.update_material_instance(mi)
    library.save_loaded_asset(mi)
    return mi


def build_mesh(spec, materials):
    path = f"{FOLDER}/{spec['name']}"
    if library.does_asset_exist(path):
        library.delete_asset(path)
    mesh = asset_tools.create_asset(spec["name"], FOLDER, unreal.StaticMesh, None)
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


def main():
    info = json.load(open(os.path.join(ZONE_DIR, "zone.json")))
    specs = json.load(open(os.path.join(ZONE_DIR, "meshes.json")))

    textures = {}
    for file_name in sorted(os.listdir(PBR_DIR)):
        stem = file_name[:-4]
        material_name, kind = stem.rsplit("_", 1)
        if kind not in ("Color", "NormalDX", "Roughness"):
            continue
        textures.setdefault(material_name, {})[kind] = import_texture(
            os.path.join(PBR_DIR, file_name), f"{COMMON}/Textures", f"T_{stem}",
            "normal" if kind == "NormalDX" else "linear" if kind == "Roughness" else "color")
    control = import_texture(os.path.join(ZONE_DIR, "control.png"), FOLDER, "T_Control", "control")
    MACRO_TEXTURE[0] = textures["Concrete034"]["Color"]

    materials = {}
    srgb_to_linear = lambda c: (c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    average = {name: TEXTURE_AVERAGE[name] for name in TEXTURE_AVERAGE}
    to_tint = lambda rgb, set_name: tuple(round(srgb_to_linear(c) / average[set_name], 3) for c in rgb)
    # colour calibration is per stage lighting, measured on zone A
    calibration = json.load(open(os.path.join(HERE, "zones", f"{ZONE.split('_')[0]}_A_calibration.json")))
    balance = lambda rgb, extra=(1.0, 1.0, 1.0): tuple(round(c * w * e * ALBEDO_SCALE, 4) for c, w, e in zip(rgb, calibration["white_balance"], extra))
    for surface, (set_name, tile, tint, metallic, rough, rotate) in SURFACES.items():
        t = textures[set_name]
        if tint is None:
            tint = balance(to_tint(info["tints"]["sidewalk"], set_name), calibration.get("sidewalk", (1, 1, 1)))
        else:
            tint = balance(tint)
        materials[surface] = pbr_surface(surface, t, tile, tint, metallic, rough, rotate)
    # asphalt and red pavement tinted so the texture's average comes out at the scan's average colour
    road = road_material(textures, control, info)
    materials["Road"] = instance(f"{FOLDER}/MI_Road", road, {"TileSize": 4.0},
                                 {"AsphaltTint": balance(to_tint(info["tints"]["asphalt"], ROAD_SET)),
                                  "RedTint": balance(to_tint(info["tints"]["red"], ROAD_SET), calibration["red"])})
    materials["Glass"] = glass_material()
    for name, record in info["glass"].items():
        tex = import_texture(os.path.join(ZONE_DIR, record["file"]), FOLDER, f"T_{name}", "sign")
        materials[name] = photo_glass_material(name, record, tex)
    sign = sign_material()
    for name in info["signs"]:
        tex = import_texture(os.path.join(ZONE_DIR, f"sign_{name}.png"), FOLDER, f"T_Sign_{name}", "sign")
        materials[f"Sign_{name}"] = instance(f"{FOLDER}/MI_Sign_{name}", sign, textures={"Photo": tex})
    manhole = manhole_material(textures)
    materials["ManholeRound"] = manhole
    materials["ManholeSquare"] = instance(f"{FOLDER}/MI_ManholeSquare", manhole)

    meshes = [(spec, build_mesh(spec, materials)) for spec in specs]

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(ZONE_DIR, f"{ZONE}.ply"))
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("destination_name", f"{ZONE}_Scan")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    asset_tools.import_asset_tasks([task])
    splat = unreal.load_asset(f"{FOLDER}/{ZONE}_Scan")
    splat.build_nanite_cluster_hierarchy()
    library.save_loaded_asset(splat)
    # the variant that keeps the scanned building, for the high quality level (Scripts/gsquality)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(ZONE_DIR, f"{ZONE}_KeepBuilding.ply"))
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("destination_name", f"{ZONE}_ScanKeepBuilding")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    asset_tools.import_asset_tasks([task])
    keep = unreal.load_asset(f"{FOLDER}/{ZONE}_ScanKeepBuilding")
    keep.build_nanite_cluster_hierarchy()
    library.save_loaded_asset(keep)

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    levels.load_level(f"/Game/Stages/Lvl_{STAGE}")
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.ScanSplatActor):
            actor.get_splat().set_splat_asset(splat)
        elif isinstance(actor, unreal.SkyAtmosphere):
            atmosphere = actor.get_component_by_class(unreal.SkyAtmosphereComponent)
            atmosphere.set_editor_property("sky_luminance_factor", unreal.LinearColor(SKY_LUMINANCE, SKY_LUMINANCE, SKY_LUMINANCE, 1.0))
        elif isinstance(actor, (unreal.DirectionalLight, unreal.SkyLight)):
            light = actor.get_component_by_class(unreal.LightComponentBase)
            scale = SKYLIGHT_SCALE if isinstance(actor, unreal.SkyLight) else LIGHT_SCALE
            light.set_editor_property("intensity", light.get_editor_property("intensity") * scale)
            r, g, b = (int(c * 255) for c in LIGHT_COLOR)
            light.set_editor_property("light_color", unreal.Color(r=r, g=g, b=b, a=255))
    for spec, mesh in meshes:
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(f"Zone_{spec['name']}")
        component = actor.static_mesh_component
        component.set_static_mesh(mesh)
        component.set_collision_profile_name("BlockAll" if spec["collision"] == "complex" else "NoCollision")
        # real shadows fall on these surfaces: the character's blob shadow steps aside here
        actor.set_editor_property("tags", ["LitGround"])
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, LEVEL):
        raise RuntimeError(f"Failed to save {LEVEL}")
    # the trimmed scan alone: shows exactly which parts are splats
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label().startswith("Zone_"):
            actor.set_actor_hidden_in_game(True)
            actor.static_mesh_component.set_collision_profile_name("NoCollision")
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, f"{LEVEL}_ScanOnly"):
        raise RuntimeError(f"Failed to save {LEVEL}_ScanOnly")
    levels.load_level(LEVEL)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    # the same without the scan: shows exactly which parts are meshes
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.ScanSplatActor):
            actors.destroy_actor(actor)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, f"{LEVEL}_MeshOnly"):
        raise RuntimeError(f"Failed to save {LEVEL}_MeshOnly")
    unreal.log(f"[Zone] Saved {LEVEL}: {len(meshes)} meshes, {len(materials)} materials, scan {info['kept']:,} splats")


main()
