"""
Creates the materials of the game layer drawn over the scans, in /Game/CoinGame/Materials:

  M_Hologram    translucent glowing panel with outlined faces, a world grid and a moving scan line. Everything the
                player can interact with uses it (platforms, jump pads, breakable walls, the ghost, gems), tinted
                per use through the Color / Fill / Intensity parameters, so the game layer reads as one AR overlay
                on top of the photographed places instead of trying to blend in with them.
  M_BlobShadow  soft dark disc under the character. The scans don't receive shadows, so without it the character
                seems to float.
  M_Coin        shiny gold with a little glow, so coins stand out in dim scans.

Run headless with the editor closed:
  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import unreal

FOLDER = "/Game/CoinGame/Materials"

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary


def new_material(name, blend_mode, shading_model, two_sided=False):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    material = asset_tools.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("blend_mode", blend_mode)
    material.set_editor_property("shading_model", shading_model)
    material.set_editor_property("two_sided", two_sided)
    return material


def builder(material):
    def node(cls, x, y, **props):
        expression = mel.create_material_expression(material, cls, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def link(a, b, pin="", out=""):
        mel.connect_material_expressions(a, out, b, pin)

    return node, link


def finish(material):
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    unreal.log(f"[Materials] Saved {material.get_path_name()}")


def hologram():
    material = new_material("M_Hologram", unreal.BlendMode.BLEND_TRANSLUCENT, unreal.MaterialShadingModel.MSM_UNLIT, True)
    # the ghost is a skinned mannequin
    material.set_editor_property("used_with_skeletal_mesh", True)
    node, link = builder(material)

    color = node(unreal.MaterialExpressionVectorParameter, -600, -500, parameter_name="Color", default_value=unreal.LinearColor(0.15, 0.7, 1.0, 1.0))
    fill = node(unreal.MaterialExpressionScalarParameter, -600, -350, parameter_name="Fill", default_value=0.12)
    intensity = node(unreal.MaterialExpressionScalarParameter, -600, -250, parameter_name="Intensity", default_value=2.0)
    line_strength = node(unreal.MaterialExpressionScalarParameter, -600, -150, parameter_name="Lines", default_value=0.9)

    # face outline from the mesh UVs: the engine shapes map 0..1 across every face
    uv = node(unreal.MaterialExpressionTextureCoordinate, -1600, 0)
    uv_centred = node(unreal.MaterialExpressionSubtract, -1450, 0, const_b=0.5)
    link(uv, uv_centred, "A")
    uv_abs = node(unreal.MaterialExpressionAbs, -1300, 0)
    link(uv_centred, uv_abs)
    uv_u = node(unreal.MaterialExpressionComponentMask, -1150, -50, r=True, g=False, b=False, a=False)
    uv_v = node(unreal.MaterialExpressionComponentMask, -1150, 50, r=False, g=True, b=False, a=False)
    link(uv_abs, uv_u)
    link(uv_abs, uv_v)
    uv_max = node(unreal.MaterialExpressionMax, -1000, 0)
    link(uv_u, uv_max, "A")
    link(uv_v, uv_max, "B")
    edge_offset = node(unreal.MaterialExpressionSubtract, -850, 0, const_b=0.465)
    link(uv_max, edge_offset, "A")
    edge_sharp = node(unreal.MaterialExpressionMultiply, -700, 0, const_b=40.0)
    link(edge_offset, edge_sharp, "A")
    edge = node(unreal.MaterialExpressionSaturate, -550, 0)
    link(edge_sharp, edge)

    # faint world grid every 50 cm
    world = node(unreal.MaterialExpressionWorldPosition, -1600, 300)
    cells = node(unreal.MaterialExpressionDivide, -1450, 300, const_b=50.0)
    link(world, cells, "A")
    frac = node(unreal.MaterialExpressionFrac, -1300, 300)
    link(cells, frac)
    centred = node(unreal.MaterialExpressionSubtract, -1150, 300, const_b=0.5)
    link(frac, centred, "A")
    folded = node(unreal.MaterialExpressionAbs, -1000, 300)
    link(centred, folded)
    gx = node(unreal.MaterialExpressionComponentMask, -850, 250, r=True, g=False, b=False, a=False)
    gy = node(unreal.MaterialExpressionComponentMask, -850, 350, r=False, g=True, b=False, a=False)
    link(folded, gx)
    link(folded, gy)
    gmax = node(unreal.MaterialExpressionMax, -700, 300)
    link(gx, gmax, "A")
    link(gy, gmax, "B")
    grid_offset = node(unreal.MaterialExpressionSubtract, -550, 300, const_b=0.46)
    link(gmax, grid_offset, "A")
    grid_sharp = node(unreal.MaterialExpressionMultiply, -400, 300, const_b=25.0)
    link(grid_offset, grid_sharp, "A")
    grid = node(unreal.MaterialExpressionSaturate, -250, 300)
    link(grid_sharp, grid)
    grid_dim = node(unreal.MaterialExpressionMultiply, -100, 300, const_b=0.35)
    link(grid, grid_dim, "A")

    # a bright band scrolling upwards
    world_z = node(unreal.MaterialExpressionComponentMask, -1300, 600, r=False, g=False, b=True, a=False)
    link(world, world_z)
    z_scaled = node(unreal.MaterialExpressionDivide, -1150, 600, const_b=120.0)
    link(world_z, z_scaled, "A")
    time = node(unreal.MaterialExpressionTime, -1300, 750)
    time_scaled = node(unreal.MaterialExpressionMultiply, -1150, 750, const_b=0.6)
    link(time, time_scaled, "A")
    scroll = node(unreal.MaterialExpressionSubtract, -1000, 650)
    link(z_scaled, scroll, "A")
    link(time_scaled, scroll, "B")
    band_frac = node(unreal.MaterialExpressionFrac, -850, 650)
    link(scroll, band_frac)
    band_edge = node(unreal.MaterialExpressionSubtract, -700, 650, const_b=0.85)
    link(band_frac, band_edge, "A")
    band_ramp = node(unreal.MaterialExpressionMultiply, -600, 650, const_b=6.6)
    link(band_edge, band_ramp, "A")
    band_clamped = node(unreal.MaterialExpressionSaturate, -500, 650)
    link(band_ramp, band_clamped)
    band_sq = node(unreal.MaterialExpressionMultiply, -400, 650)
    link(band_clamped, band_sq, "A")
    link(band_clamped, band_sq, "B")
    band = node(unreal.MaterialExpressionMultiply, -300, 650, const_b=0.5)
    link(band_sq, band, "A")

    # glancing angles glow
    fresnel = node(unreal.MaterialExpressionFresnel, -550, 850, exponent=3.0, base_reflect_fraction=0.0)
    fresnel_dim = node(unreal.MaterialExpressionMultiply, -400, 850, const_b=0.5)
    link(fresnel, fresnel_dim, "A")

    # lines = outline * Lines + grid + band + fresnel
    edge_scaled = node(unreal.MaterialExpressionMultiply, -400, 0)
    link(edge, edge_scaled, "A")
    link(line_strength, edge_scaled, "B")
    sum1 = node(unreal.MaterialExpressionAdd, -250, 100)
    link(edge_scaled, sum1, "A")
    link(grid_dim, sum1, "B")
    sum2 = node(unreal.MaterialExpressionAdd, -100, 400)
    link(band, sum2, "A")
    link(fresnel_dim, sum2, "B")
    lines = node(unreal.MaterialExpressionAdd, 50, 200)
    link(sum1, lines, "A")
    link(sum2, lines, "B")

    opacity_sum = node(unreal.MaterialExpressionAdd, 200, 100)
    link(fill, opacity_sum, "A")
    link(lines, opacity_sum, "B")
    opacity = node(unreal.MaterialExpressionSaturate, 350, 100)
    link(opacity_sum, opacity)
    mel.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)

    glow = node(unreal.MaterialExpressionAdd, 200, -200, const_a=1.0)
    link(lines, glow, "B")
    glow_color = node(unreal.MaterialExpressionMultiply, 350, -300)
    link(color, glow_color, "A")
    link(glow, glow_color, "B")
    emissive = node(unreal.MaterialExpressionMultiply, 500, -300)
    link(glow_color, emissive, "A")
    link(intensity, emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    finish(material)


def blob_shadow():
    material = new_material("M_BlobShadow", unreal.BlendMode.BLEND_TRANSLUCENT, unreal.MaterialShadingModel.MSM_UNLIT)
    node, link = builder(material)

    strength = node(unreal.MaterialExpressionScalarParameter, -400, 200, parameter_name="Strength", default_value=0.6)
    uv = node(unreal.MaterialExpressionTextureCoordinate, -1000, 0)
    centre = node(unreal.MaterialExpressionConstant2Vector, -1000, 150, r=0.5, g=0.5)
    distance = node(unreal.MaterialExpressionDistance, -850, 50)
    link(uv, distance, "A")
    link(centre, distance, "B")
    scaled = node(unreal.MaterialExpressionMultiply, -700, 50, const_b=2.0)
    link(distance, scaled, "A")
    clamped = node(unreal.MaterialExpressionSaturate, -550, 50)
    link(scaled, clamped)
    inside = node(unreal.MaterialExpressionOneMinus, -400, 50)
    link(clamped, inside)
    soft = node(unreal.MaterialExpressionMultiply, -250, 50)
    link(inside, soft, "A")
    link(inside, soft, "B")
    opacity = node(unreal.MaterialExpressionMultiply, -100, 100)
    link(soft, opacity, "A")
    link(strength, opacity, "B")
    mel.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)

    black = node(unreal.MaterialExpressionConstant3Vector, -100, -100, constant=unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    mel.connect_material_property(black, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(material)


def coin():
    material = new_material("M_Coin", unreal.BlendMode.BLEND_OPAQUE, unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    node, link = builder(material)

    color = node(unreal.MaterialExpressionVectorParameter, -500, 0, parameter_name="Color", default_value=unreal.LinearColor(1.0, 0.7, 0.05, 1.0))
    glow = node(unreal.MaterialExpressionScalarParameter, -500, 200, parameter_name="Glow", default_value=0.25)
    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    metallic = node(unreal.MaterialExpressionConstant, -300, 100, r=1.0)
    mel.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)
    roughness = node(unreal.MaterialExpressionConstant, -300, 150, r=0.3)
    mel.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    emissive = node(unreal.MaterialExpressionMultiply, -300, 250)
    link(color, emissive, "A")
    link(glow, emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(material)


hologram()
blob_shadow()
coin()
