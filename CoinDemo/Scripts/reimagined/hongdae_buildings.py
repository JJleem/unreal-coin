"""
The three reference buildings of the reimagined Hongdae, built with bkit on the facade lines measured from the scan:

  * SOLB: 4 storeys on the red street's south side, x 11.6-15.6, street face y = -1.3 (wall splats peak there at
    z 2-8 m); red SOLB shop with its box sign standing 0.45 m proud (where the ground floor splats peak, y = -0.5),
    a vape shop's signs on the 2nd floor, white painted brick, grilled windows, a 4th floor balcony
  * BIBIANG: the corner building west of it with its corner cut at 45 degrees (the scan's wall splats run diagonally
    from (7.5, -4.75) to (10.75, -1.5)), x 7.6-11.6; select shop on the corner, beige facade tiles above, tarot cafe
    and hair studio signs (the photo's lettering is unreadable: plausible Hongdae signs)
  * BLUE ELEPHANT / The Coffee Bean: the corner building north of the plaza, footprint x 6.1-14.8, y 9.5-19.5, with
    the openings, bands, awnings and mansard roof measured in zone A (Scripts/rebuild/build_zone.py) rebuilt in depth

Heights: storey lines read off the baked facade photos (face_072.png, face_029.png, face_031.png).
"""

import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

import bkit
from bkit import Facade, obox, wall, band, window, room, storefront, sign_box, blade_sign, letters, downpipe, gas_pipe, \
    conduit_bundle, parapet, railing, cap, tube, cable, blinds, security_grille, shutter_box

KO = "/mnt/c/Windows/Fonts/malgunbd.ttf"
LATIN = "/mnt/c/Windows/Fonts/arialbd.ttf"
SERIF = "/mnt/c/Windows/Fonts/timesbd.ttf"
GOTHIC_LIGHT = "/mnt/c/Windows/Fonts/segoeuil.ttf"

AC = "exterior_aircon_unit/exterior_aircon_unit_1k/StaticMeshes/exterior_aircon_unit"
AC_RUST = "exterior_aircon_unit/exterior_aircon_unit_1k/StaticMeshes/exterior_aircon_unit_rusted"
SHELF_STEEL = "steel_frame_shelves_02/steel_frame_shelves_02_1k/StaticMeshes/steel_frame_shelves_02_1k"
SHELF_WOOD = "wooden_display_shelves_01/wooden_display_shelves_01_1k/StaticMeshes/wooden_display_shelves_01"
REGISTER = "CashRegister_01/CashRegister_01_1k/StaticMeshes/CashRegister_01_body"
BAR_CHAIR = "bar_chair_round_01/bar_chair_round_01_1k/StaticMeshes/bar_chair_round_01_1k"
ROUND_TABLE = "coffee_table_round_01/coffee_table_round_01_1k/StaticMeshes/coffee_table_round_01_1k"
CHAIR = "dining_chair_02/dining_chair_02_1k/StaticMeshes/dining_chair_02_1k"
ARMCHAIR = "modern_arm_chair_01/modern_arm_chair_01_1k/StaticMeshes/modern_arm_chair_01_1k"
PENDANT = "modern_ceiling_lamp_01/modern_ceiling_lamp_01_1k/StaticMeshes/modern_ceiling_lamp_01_1k"
PLANT_BIG = "potted_plant_01/potted_plant_01_1k/StaticMeshes/potted_plant_01_pot"
PLANT_02 = "potted_plant_02/potted_plant_02_1k/StaticMeshes/potted_plant_02_pot"
EXTINGUISHER = "korean_fire_extinguisher_01/korean_fire_extinguisher_01_1k/StaticMeshes/korean_fire_extinguisher_01_1k"
CAMERA = "security_camera_01/security_camera_01_1k/StaticMeshes/security_camera_01_1k"
WALL_LAMP = "industrial_wall_lamp/industrial_wall_lamp_1k/StaticMeshes/industrial_wall_lamp_1k"
CHALKBOARD = "standing_chalkboard_01/standing_chalkboard_01_1k/StaticMeshes/standing_chalkboard_01_1k"
CRATE = "plastic_crate_02/plastic_crate_02_1k/StaticMeshes/plastic_crate_02_1k"
BOX = "cardboard_box_01/cardboard_box_01_1k/StaticMeshes/cardboard_box_01_1k"
LPG = "small_lpg_tank/small_lpg_tank_1k/StaticMeshes/small_lpg_tank_1k"
POWER_BOX = "power_box_01/power_box_01_1k/StaticMeshes/power_box_01_box"
UTILITY_BOX = "utility_box_01/utility_box_01_1k/StaticMeshes/utility_box_01_1k"
TRASHBAG = "trashbag/trashbag_1k/StaticMeshes/trashbag_1k"
SHUTTER_DOOR = "rollershutter_door/rollershutter_door_1k/StaticMeshes/rollershutter_door"

# multi part kit models: every part is placed with the same transform (they share the model's origin)
MULTI = {
    PLANT_BIG: ["potted_plant_01/potted_plant_01_1k/StaticMeshes/potted_plant_01_" + p for p in ("pot", "pebbles", "stem", "leaves")],
    PLANT_02: ["potted_plant_02/potted_plant_02_1k/StaticMeshes/potted_plant_02_" + p for p in ("pot", "dirt", "leaves")],
    REGISTER: [REGISTER, "CashRegister_01/CashRegister_01_1k/StaticMeshes/CashRegister_011_drawer"],
}


def facades_of(footprint):
    """One Facade per footprint edge, outward normals (the footprint turned clockwise in plan)."""
    poly = orient(Polygon(footprint), -1.0)
    c = np.asarray(poly.exterior.coords)
    return [Facade(c[k], c[k + 1]) for k in range(len(c) - 1)]


def ac_unit(b, F, s, z, rusty=False, bracket="Steel"):
    """Outdoor air conditioner unit on a steel wall bracket (its bottom at z), and the refrigerant pipe up to the
    window above, wrapped in tape."""
    model = AC_RUST if rusty else AC
    xy = F.xy(s, -0.25)
    b.place(model, xy, z, F.yaw())
    for ds in (-0.3, 0.3):
        obox(b.detail, F, s + ds - 0.02, s + ds + 0.02, z - 0.05, z, -0.5, 0.0, bracket)
        tube(b.detail, F.p(s + ds, z - 0.02, -0.45), F.p(s + ds, z - 0.5, -0.01), 0.012, bracket, 5)
    tube(b.detail, F.p(s + 0.45, z + 0.25, -0.12), F.p(s + 0.45, z + 1.3, -0.06), 0.025, "PipeTape", 6)


def gas_meter(b, F, s, z):
    obox(b.detail, F, s - 0.17, s + 0.17, z, z + 0.26, -0.18, 0.0, "MeterBox")
    obox(b.detail, F, s - 0.14, s + 0.14, z + 0.04, z + 0.22, -0.185, -0.18, "MeterFace")


def shop_interior(b, F, s0, s1, z0, d0, depth, kind, seed=0):
    """Fit-out of a shop seen through the glass: wall units with products, garment rails, tables, counters and kit
    furniture."""
    rng = np.random.default_rng(seed + int(abs(F.a[0] * 100 + F.a[1] * 10)))
    span = s1 - s0
    yaw_in = F.yaw() + 180.0     # facing the street
    dt = b.detail
    back = d0 + depth
    if kind == "boutique":
        bkit.display_wall(dt, F, s0 + 0.1, s1 - 0.1, z0, back, rng, height=2.3, shelf=0.42)
        bkit.clothes_rack(dt, F, s0 + 0.4, s0 + 0.4 + min(1.4, span * 0.4), z0, d0 + depth * 0.45, rng)
        if span > 2.5:
            bkit.table_display(dt, F, s1 - 1.6, s1 - 0.5, z0, d0 + depth * 0.3, d0 + depth * 0.3 + 0.8, rng)
        obox(dt, F, s0 + span * 0.5, s0 + span * 0.8, z0, z0 + 0.95, back - 1.6, back - 1.1, "Counter")
        b.place(REGISTER, F.xy(s0 + span * 0.65, back - 1.35), z0 + 0.95, yaw_in, 0.8)
        b.place(PLANT_BIG, F.xy(s0 + 0.45, d0 + 0.6), z0, 0.0)
    elif kind == "vape":
        bkit.display_wall(dt, F, s0 + 0.1, s1 - 0.1, z0, back, rng, height=2.0, shelf=0.3, small=True)
        obox(dt, F, s0 + 0.4, s1 - 0.4, z0, z0 + 0.95, d0 + 1.6, d0 + 2.1, "Counter")
        obox(dt, F, s0 + 0.4, s1 - 0.4, z0 + 0.95, z0 + 0.98, d0 + 1.55, d0 + 2.15, "CounterTop")
    elif kind == "cafe":
        # counter with an espresso machine and grinder, the menu board above it
        obox(dt, F, s0 + 0.3, s0 + 2.6, z0, z0 + 1.0, back - 1.0, back - 0.4, "Counter")
        obox(dt, F, s0 + 0.28, s0 + 2.62, z0 + 1.0, z0 + 1.04, back - 1.02, back - 0.38, "CounterTop")
        obox(dt, F, s0 + 0.5, s0 + 1.2, z0 + 1.04, z0 + 1.45, back - 0.9, back - 0.45, "Stainless")
        obox(dt, F, s0 + 1.4, s0 + 1.6, z0 + 1.04, z0 + 1.5, back - 0.8, back - 0.6, "CounterTop")
        sign_box(dt, F, s0 + 0.6, s0 + 1.6, z0 + 1.6, z0 + 2.3, "Sign_be_menu", depth=0.03, d=back - 0.02)
        for k, s in enumerate(np.arange(s0 + 0.9, s1 - 0.6, 1.6)):
            dd = d0 + 1.2 + (k % 2) * 1.3
            b.place(ROUND_TABLE, F.xy(s, dd), z0, 0.0, 0.62)
            for a in (0, 180):
                off = 0.55 * np.array([np.cos(np.radians(a)), np.sin(np.radians(a))])
                b.place(CHAIR, F.xy(s, dd) + off, z0, a + 90.0)
            b.place(PENDANT, F.xy(s, dd), z0 + 2.35 - 0.95, 0.0)
        b.place(ARMCHAIR, F.xy(s1 - 0.8, d0 + depth - 1.0), z0, yaw_in)
    elif kind == "eyewear":
        bkit.display_wall(dt, F, s0 + 0.1, s1 - 0.1, z0, back, rng, height=2.2, shelf=0.28, small=True)
        for s in (s0 + span * 0.35, s0 + span * 0.7):
            obox(b.detail, F, s - 0.45, s + 0.45, z0, z0 + 0.95, d0 + 1.6, d0 + 2.2, "Counter")
            obox(b.detail, F, s - 0.47, s + 0.47, z0 + 0.95, z0 + 0.99, d0 + 1.58, d0 + 2.22, "CounterGlass")


# ------------------------------------------------------------------------------------------------------------- SOLB

def solb():
    G = -1.85
    base = G - 0.6
    levels = [G, 1.3, 3.9, 6.4, 8.8]
    footprint = [(11.6, -1.3), (15.6, -1.3), (15.6, -9.5), (11.6, -9.5)]
    b = bkit.Building("Solb", footprint, G, 9.4)
    F = Facade((11.6, -1.3), (15.6, -1.3))
    E = Facade((15.6, -1.3), (15.6, -9.5))     # east side wall over the one storey Tax-Free shop
    W = 4.0
    sh, dt = b.shell, b.detail

    # ---- ground floor: dark tiled piers, aluminium shop front, the red SOLB box sign
    shop = (0.3, 3.7, G, 0.7)
    wall(sh, F, 0.0, W, base, 1.3, [shop], "TileDark", thickness=0.3)
    storefront(dt, F, 0.3, 3.7, G, 0.7, doors=[(2.35, 1.0, 1)], frame="AluDark")
    room(dt, F, 0.3, 3.7, G, 0.95, 0.3, 6.0, wall="RoomWallWhite", floor="RoomFloorTile", lights=True, spacing=1.1)
    shop_interior(b, F, 0.3, 3.7, G, 0.3, 6.0, "boutique")
    obox(sh, F, -0.05, W + 0.05, 0.7, 1.55, -0.45, 0.0, "PaintRed", skip=("back",))
    obox(sh, F, -0.07, W + 0.07, 1.55, 1.6, -0.47, 0.0, "SignFrame", skip=("back",))
    obox(sh, F, -0.07, W + 0.07, 0.66, 0.7, -0.47, 0.0, "SignFrame", skip=("back",))
    letters(dt, F, "SOLB", LATIN, W / 2, 0.88, 0.48, 0.05, -0.45, "LetterWhite", "LetterSide")
    # downlights under the sign box
    for s in np.arange(0.5, W, 0.9):
        tube(dt, F.p(s, 0.68, -0.3), F.p(s, 0.6, -0.3), 0.035, "Stainless", 8)
    b.place(EXTINGUISHER, F.xy(0.25, -0.15), G, F.yaw())
    b.place(PLANT_02, F.xy(1.6, -0.3), G, 0.0, 0.9)

    # ---- 2nd floor: vape shop, one wide grilled window, three signs
    w2 = (0.6, 2.6, 1.6, 2.8)
    wall(sh, F, 0.0, W, 1.6, 3.9, [w2], "BrickWhite", thickness=0.25)
    window(dt, F, *w2, style="slider", grille="Grille")
    room(dt, F, 0.0, W, 1.3, 3.75, 0.25, 4.5, lights=True, spacing=1.3)   # the vape shop is open
    shop_interior(b, F, 0.3, 3.7, 1.3, 0.3, 4.5, "vape")
    sign_box(dt, F, 0.3, 2.3, 2.98, 3.6, "Sign_solb_vape", depth=0.16)
    sign_box(dt, F, 2.45, 3.55, 3.05, 3.47, "Sign_solb_zero", depth=0.14)
    sign_box(dt, F, 2.9, 3.8, 1.85, 2.4, "Sign_solb_vape_cn", depth=0.12)
    blade_sign(dt, F, 3.85, 2.0, 4.2, ("Sign_solb_blade_a", "Sign_solb_blade_a"), out0=0.15, width=0.62)

    # ---- 3rd floor: two casement windows with grilles, an air conditioner on a bracket
    w3 = [(0.45, 1.65, 4.3, 5.75), (2.35, 3.55, 4.3, 5.75)]
    wall(sh, F, 0.0, W, 3.9, 6.4, w3, "BrickWhite")
    for w in w3:
        window(dt, F, *w, style="casement", transom=1.0, grille="Grille")
    room(dt, F, 0.0, W, 3.9, 6.25, 0.25, 4.0, lights=False)
    blinds(dt, F, 2.45, 3.45, 5.7, 0.6, 0.45, "Blind")
    ac_unit(b, F, 1.05, 3.97)

    # ---- 4th floor: balcony with a railing, three narrow windows
    w4 = [(0.35, 1.15, 6.8, 8.1), (1.6, 2.4, 6.8, 8.1), (2.85, 3.65, 6.8, 8.1)]
    wall(sh, F, 0.0, W, 6.4, 8.8, w4, "BrickWhite")
    for w in w4:
        window(dt, F, *w, style="fixed", transom=0.9, sill=None)
    room(dt, F, 0.0, W, 6.4, 8.65, 0.25, 4.0, lights=False)
    blinds(dt, F, 0.4, 1.1, 8.05, 0.9, 0.42, "Blind")
    obox(sh, F, -0.05, W + 0.05, 6.25, 6.4, -0.7, 0.0, "Trim", skip=("back",))
    railing(dt, F, 0.05, W - 0.05, 6.4, 1.0, "Rail", d=-0.64)
    for s in (0.05, W - 0.05):
        tube(dt, F.p(s, 7.4, -0.64), F.p(s, 7.4, 0.0), 0.02, "Rail", 6)
    b.place(PLANT_02, F.xy(0.7, -0.35), 6.4, 0.0, 0.8)
    b.place(CRATE, F.xy(3.2, -0.3), 6.4, F.yaw())

    # ---- bands, parapet, services
    for z in (3.9, 6.4 - 0.15):
        band(sh, F, -0.04, W + 0.04, z - 0.08, z + 0.07, 0.06, "Trim")
    parapet(sh, F, 0.0, W, 8.8, 0.6, "BrickWhite")
    downpipe(dt, F, W - 0.12, G, 9.3)
    gas_pipe(dt, F, [(0.12, G + 1.1), (0.12, 6.9), (0.6, 6.9)])
    gas_meter(b, F, 0.15, G + 1.2)
    conduit_bundle(dt, F, 0.0, 0.9, 3.75, count=4)
    b.place(CAMERA, F.xy(3.6, -0.1), 0.25, F.yaw())

    # ---- east side wall (seen above the one storey neighbour): rough render, a few small windows, AC units
    side_openings = [(1.2, 2.0, 4.6, 5.4), (4.0, 4.8, 4.6, 5.4), (1.2, 2.0, 7.0, 7.8), (5.5, 6.3, 7.0, 7.8)]
    wall(sh, E, 0.0, 8.2, base, 9.4, side_openings, "ConcreteSide")
    for w in side_openings:
        window(dt, E, *w, style="slider", sill="Sill", grille="GrilleDark")
    for z0, z1 in ((3.9, 6.25), (6.4, 8.65)):
        room(dt, E, 0.0, 8.2, z0, z1, 0.25, 3.0, lights=False)
    ac_unit(b, E, 3.0, 5.6, rusty=True)
    ac_unit(b, E, 6.6, 6.5)
    downpipe(dt, E, 7.9, 3.0, 9.4)
    for k in range(3):
        cable(dt, E.p(0.3, 7.6 - k * 0.12, -0.05), E.p(8.0, 7.0 - k * 0.15, -0.05), 0.35, 0.01, "Cable")
    # back and west walls (mostly hidden by the neighbours)
    Bk = Facade((15.6, -9.5), (11.6, -9.5))
    wall(sh, Bk, 0.0, 4.0, base, 9.4, [], "ConcreteSide")
    Wf = Facade((11.6, -9.5), (11.6, -1.3))
    wall(sh, Wf, 0.0, 8.2, 8.2, 9.4, [], "ConcreteSide")

    # ---- roof: deck, parapets, water tank, outdoor units, stair house
    poly = Polygon(footprint)
    cap(sh, poly, 8.8, True, "RoofDeck")
    parapet(sh, E, 0.0, 8.2, 8.8, 0.6, "ConcreteSide")
    parapet(sh, Bk, 0.0, 4.0, 8.8, 0.6, "ConcreteSide")
    obox(sh, Facade((11.6, -9.5), (15.6, -9.5)), 0.3, 2.7, 8.8, 11.2, -2.6, 0.0, "ConcreteSide", skip=("bottom",))  # stair house
    obox(sh, Facade((11.6, -9.5), (15.6, -9.5)), 0.2, 2.8, 11.2, 11.3, -2.7, 0.1, "Coping")
    b.detail.cylinder((12.9, -4.6), 0.62, 8.8, 10.0, "TankBlue", 20)
    b.detail.cylinder((12.9, -4.6), 0.2, 10.0, 10.12, "TankBlue", 12)
    b.place(AC, (14.6, -3.2), 8.8, 90.0)
    b.place(AC_RUST, (14.6, -4.3), 8.8, 90.0)
    railing(dt, F, 0.0, W, 9.4, 0.5, "Rail", d=0.1, post=1.0, bars=1.0)
    b.removal = {"front": [(F, 0.0, W, G - 0.3, 9.6, 1.0)], "extra": [(E, 0.0, 8.2, 5.9, 10.0, 0.9)]}
    return b


# ---------------------------------------------------------------------------------------------------------- BIBIANG

def bibiang():
    G = -2.1
    base = G - 0.7
    footprint = [(7.6, -11.0), (7.6, -4.65), (10.9, -1.35), (11.6, -1.35), (11.6, -11.0)]
    b = bkit.Building("Bibiang", footprint, G, 9.6)
    S = Facade((7.6, -11.0), (7.6, -4.65))      # west side, along the cross street
    C = Facade((7.6, -4.65), (10.9, -1.35))     # cut corner facing the intersection
    N = Facade((10.9, -1.35), (11.6, -1.35))    # short piece on the red street
    sh, dt = b.shell, b.detail
    LS, LC = S.length, C.length

    # ---- ground floor: select shop wrapping the corner, the stair entrance on the side
    corner_shop = (0.25, LC - 0.25, G, 0.75)
    wall(sh, C, 0.0, LC, base, 1.4, [corner_shop], "Granite", thickness=0.3)
    storefront(dt, C, *corner_shop, doors=[(LC / 2 - 0.85, 1.7, 2)], frame="AluDark")
    room(dt, C, 0.25, LC - 0.25, G, 1.05, 0.3, 5.0, wall="RoomWallWarm", floor="RoomFloorWood", spacing=1.2)
    shop_interior(b, C, 0.25, LC - 0.25, G, 0.3, 5.0, "boutique")
    side_shop = (3.6, LS - 0.25, G, 0.75)
    stair_door = (1.2, 2.25, G, G + 2.2)
    wall(sh, S, 0.0, LS, base, 1.4, [side_shop, stair_door], "Granite", thickness=0.3)
    storefront(dt, S, *side_shop, doors=[], frame="AluDark")
    room(dt, S, 3.6, LS - 0.25, G, 1.05, 0.3, 3.5, wall="RoomWallWarm", floor="RoomFloorWood", spacing=1.2)
    shop_interior(b, S, 3.6, LS - 0.25, G, 0.3, 3.5, "boutique")
    # the stair door: a steel door with a small wired glass window, the stair hall lit behind it
    obox(dt, S, 1.2, 2.25, G, G + 2.2, 0.22, 0.27, "DoorSteel", skip=("back",))
    obox(dt, S, 1.5, 1.95, G + 1.3, G + 1.9, 0.215, 0.22, "Glass")
    tube(dt, S.p(1.35, G + 0.95, 0.18), S.p(1.35, G + 1.1, 0.18), 0.02, "Stainless", 6)
    wall(sh, N, 0.0, N.length, base, 1.4, [], "Granite", thickness=0.3)
    # BIBIANG fascia: black panel with gold channel letters, round the corner
    for F_, s0, s1 in ((C, -0.05, LC + 0.05), (S, 3.4, LS + 0.02)):
        obox(sh, F_, s0, s1, 0.75, 1.4, -0.22, 0.0, "PanelBlack", skip=("back",))
    letters(dt, C, "BIBIANG", SERIF, LC / 2, 0.86, 0.42, 0.04, -0.22, "LetterGold", "LetterSideGold")
    letters(dt, S, "BIBIANG", SERIF, (3.4 + LS) / 2, 0.92, 0.32, 0.04, -0.22, "LetterGold", "LetterSideGold")
    sign_box(dt, C, 0.35, 0.95, G + 0.35, G + 1.85, "Sign_bibiang_poster", depth=0.04, d=0.12)
    sign_box(dt, S, 2.45, 2.87, G + 1.2, G + 1.5, "Sign_notice_rent", depth=0.005)
    b.place(PLANT_BIG, C.xy(0.6, -0.4), G, 0.0)
    b.place(PLANT_BIG, C.xy(LC - 0.6, -0.4), G, 40.0)

    # ---- upper floors: beige facade tiles, sliding windows with white grilles, slab bands
    tiers = [(1.4, 4.0), (4.0, 6.6), (6.6, 9.0)]
    for k, (z0, z1) in enumerate(tiers):
        wc = [(0.55, 1.95, z0 + 0.5, z0 + 1.85), (2.7, 4.1, z0 + 0.5, z0 + 1.85)]
        ws = [(1.1, 2.5, z0 + 0.5, z0 + 1.85), (3.6, 5.0, z0 + 0.5, z0 + 1.85)]
        wall(sh, C, 0.0, LC, z0, z1, wc, "TileBeige")
        wall(sh, S, 0.0, LS, z0, z1, ws, "TileBeige")
        wall(sh, N, 0.0, N.length, z0, z1, [], "TileBeige")
        for w in wc:
            window(dt, C, *w, style="slider", grille="Grille" if k < 2 else None)
        for w in ws:
            window(dt, S, *w, style="slider", grille="Grille" if k == 0 else None)
        room(dt, C, 0.0, LC, z0, z1 - 0.15, 0.25, 4.0, wall="RoomWallWarm", lights=(k == 0), spacing=1.5)
        room(dt, S, 0.0, LS, z0, z1 - 0.15, 0.25, 3.5, lights=False)
        for F_, a, c in ((C, -0.04, LC + 0.04), (S, -0.04, LS + 0.04), (N, -0.04, N.length)):
            band(sh, F_, a, c, z1 - 0.1, z1 + 0.06, 0.05, "Coping")
    blinds(dt, C, 2.8, 4.0, 6.3, 0.7, 0.45, "Blind")
    blinds(dt, S, 1.2, 2.4, 8.4, 1.0, 0.45, "Blind")
    # tarot cafe (2nd floor): its sign over the corner windows, a blade sign at the corner
    sign_box(dt, C, 0.5, 4.17, 3.35, 3.9, "Sign_bibiang_tarot", depth=0.12)
    blade_sign(dt, N, 0.35, 1.7, 4.1, ("Sign_bibiang_blade", "Sign_bibiang_blade"), out0=0.1, width=0.55)
    sign_box(dt, S, 0.9, 3.3, 8.45, 8.95, "Sign_bibiang_hair", depth=0.12)
    # AC units hung under the side windows, the gas pipe and meter by the stair door
    ac_unit(b, S, 4.3, 4.05)
    ac_unit(b, S, 1.8, 6.65, rusty=True)
    gas_pipe(dt, S, [(0.15, G + 1.0), (0.15, 6.8), (0.6, 6.8)])
    gas_meter(b, S, 0.45, G + 1.1)
    downpipe(dt, S, 0.35, G, 9.5)
    conduit_bundle(dt, C, 0.0, LC, 1.48, count=3)
    b.place(CAMERA, C.xy(LC - 0.25, -0.1), 0.95 + 0.5, C.yaw())
    b.place(UTILITY_BOX, S.xy(0.75, -0.3), G, S.yaw())

    # ---- roof
    cap(sh, Polygon(footprint), 9.0, True, "RoofDeck")
    for F_, L in ((S, LS), (C, LC), (N, N.length)):
        parapet(sh, F_, 0.0, L, 9.0, 0.6, "TileBeige")
    Bk = Facade((11.6, -11.0), (7.6, -11.0))
    wall(sh, Bk, 0.0, 4.0, base, 9.6, [], "ConcreteSide")
    parapet(sh, Bk, 0.0, 4.0, 9.0, 0.6, "ConcreteSide")
    obox(sh, Bk, 0.4, 3.0, 9.0, 11.3, 0.0, 2.6, "ConcreteSide", skip=("bottom",))
    obox(sh, Bk, 0.3, 3.1, 11.3, 11.4, -0.1, 2.7, "Coping")
    b.detail.cylinder((9.2, -7.4), 0.55, 9.0, 10.1, "TankBlue", 20)
    b.detail.cylinder((9.2, -7.4), 0.18, 10.1, 10.22, "TankBlue", 12)
    b.place(AC, (10.6, -5.0), 9.0, 45.0)
    b.removal = {"front": [(S, 0.0, LS, G - 0.3, 9.8, 1.1), (C, 0.0, LC, G - 0.3, 9.8, 1.1), (N, 0.0, N.length, G - 0.3, 9.8, 1.0)],
                 "extra": []}
    return b


# ------------------------------------------------------------------------------------------------------ BLUE ELEPHANT

def blue_elephant():
    G = -2.6
    X0, X1, Y0, Y1 = 6.1, 14.8, 9.5, 19.5
    footprint = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    b = bkit.Building("BlueElephant", footprint, -2.3, 12.4)
    F = Facade((X1, Y0), (X0, Y0))     # front on the plaza, facing -Y: s = 14.8 - x
    S = Facade((X0, Y0), (X0, Y1))     # side on the street, facing -X: s = y - 9.5
    sh, dt = b.shell, b.detail
    fs = lambda x: X1 - x
    ss = lambda y: y - Y0
    T = 0.3

    # ---- ground floor (z -2.6 .. 0): red brown metal cladding, the eyewear shop
    door = (fs(10.45), fs(8.7), G, -0.2)
    poster = (fs(12.1), fs(10.9), -2.45, -0.15)
    wall(sh, F, 0.0, fs(X0), G - 0.4, 0.0, [door], "CladRed", thickness=T)
    storefront(dt, F, *door, doors=[(door[0] + 0.05, door[1] - door[0] - 0.1, 2)], frame="AluDark", transom=2.0)
    room(dt, F, door[0], door[1], G, 0.0, 0.3, 5.0, wall="RoomWallWhite", floor="RoomFloorTile", spacing=0.9)
    sign_box(dt, F, poster[0] + 0.05, poster[1] - 0.05, -2.3, -0.3, "Sign_be_poster", depth=0.05)
    side_glass = (ss(9.9), ss(15.2), G + 0.15, -0.2)
    wall(sh, S, 0.0, ss(Y1), G - 0.4, 0.0, [side_glass], "CladRed", thickness=T)
    storefront(dt, S, *side_glass, doors=[], frame="AluDark", bay=1.33, transom=1.9)
    room(dt, S, side_glass[0], side_glass[1], G, 0.0, 0.3, 5.5, wall="RoomWallWhite", floor="RoomFloorTile", spacing=1.0)
    shop_interior(b, S, side_glass[0], side_glass[1], G, 0.3, 5.5, "eyewear")
    # BLUE ELEPHANT: white channel letters on a dark brown panel, front and side
    obox(sh, F, fs(12.1), fs(X0) + 0.25, 0.04, 0.96, -0.25, 0.0, "PanelBrown", skip=("back",))
    letters(dt, F, "BLUE ELEPHANT", LATIN, (fs(12.1) + fs(X0)) / 2, 0.28, 0.42, 0.05, -0.25, "LetterWhite", "LetterSide")
    obox(sh, S, -0.25, ss(15.2), 0.0, 1.0, -0.12, 0.0, "PanelBrown", skip=("back",))
    letters(dt, S, "BLUE ELEPHANT", LATIN, (ss(9.6) + ss(15.2)) / 2, 0.3, 0.4, 0.05, -0.12, "LetterWhite", "LetterSide")
    obox(sh, S, ss(15.2), ss(Y1), 0.0, 1.0, 0.0, 0.05, "CladRed", skip=("back",))
    obox(sh, F, 0.0, fs(12.1), 0.0, 1.0, 0.0, 0.05, "PlasterCream", skip=("back",))
    b.place(PLANT_BIG, F.xy(fs(10.8), -0.4), G + 0.3, 0.0)

    # ---- 2nd floor (0 .. 2.8): The Coffee Bean behind full height glass
    cb_front = (fs(11.5), fs(7.4), 1.0, 2.8)
    cb_side_window = (fs(14.2), fs(13.2), 1.2, 2.6)
    wall(sh, F, 0.0, fs(X0), 0.0, 2.85, [cb_front, cb_side_window], "PlasterCream", thickness=T)
    window(dt, F, *cb_front, style="grid", depth=0.1, sill=None, frame="AluDark")
    window(dt, F, *cb_side_window, style="fixed", depth=0.12, frame="AluDark")
    cb_side = (ss(9.9), ss(16.0), 1.0, 2.8)
    wall(sh, S, 0.0, ss(Y1), 0.0, 2.85, [cb_side], "PlasterCream", thickness=T)
    window(dt, S, *cb_side, style="grid", depth=0.1, sill=None, frame="AluDark")
    room(dt, F, 0.0, fs(X0), 0.0, 2.8, 0.3, 9.4, wall="RoomWallWarm", floor="RoomFloorWood", ceiling="RoomCeilingDark", lights=False)
    shop_interior(b, F, cb_front[0], cb_front[1], 0.0, 0.3, 5.0, "cafe")
    shop_interior(b, S, cb_side[0], cb_side[1], 0.0, 0.3, 5.0, "cafe")
    # The Coffee Bean band: cream panel with purple letters and the logo disc, front and side
    obox(sh, F, fs(14.2), fs(X0) + 0.2, 2.85, 3.85, -0.2, 0.0, "PanelCream", skip=("back",))
    obox(sh, S, -0.2, ss(16.6), 2.85, 3.85, -0.2, 0.0, "PanelCream", skip=("back",))
    for F_, a, c in ((F, fs(14.2) - 0.03, fs(X0) + 0.23), (S, -0.23, ss(16.6) + 0.03)):
        for z in (2.8, 3.85):
            obox(sh, F_, a, c, z, z + 0.05, -0.23, 0.0, "Trim", skip=("back",))
    letters(dt, F, "The Coffee Bean", SERIF, (fs(14.2) + fs(X0)) / 2 - 0.5, 3.12, 0.5, 0.04, -0.2, "LetterPurple", "LetterSide")
    sign_box(dt, F, fs(7.3), fs(6.5), 2.95, 3.75, "Sign_cbtl_logo", depth=0.04, d=-0.2)
    letters(dt, S, "The Coffee Bean", SERIF, ss(13.0), 3.12, 0.5, 0.04, -0.2, "LetterPurple", "LetterSide")
    obox(sh, F, fs(X0) + 0.2, fs(X0) + 0.3, 2.85, 3.9, -0.1, 0.0, "PlasterCream")

    # ---- 3rd floor (3.9 .. 5.25 glass strip, brick band to 5.9)
    strip_f = (fs(14.55), fs(6.35), 3.95, 5.25)
    strip_s = (ss(Y0 + T), ss(16.6), 3.95, 5.25)
    wall(sh, F, 0.0, fs(X0), 3.9, 5.25, [strip_f], "PlasterCream")
    wall(sh, S, 0.0, ss(Y1), 3.9, 5.25, [strip_s], "PlasterCream")
    window(dt, F, *strip_f, style="grid", sill=None, frame="AluDark")
    window(dt, S, *strip_s, style="grid", sill=None, frame="AluDark")
    room(dt, F, 0.0, fs(X0), 3.9, 5.25, 0.3, 4.5, lights=False)
    room(dt, S, 0.0, ss(16.6), 3.9, 5.25, 0.3, 4.5, lights=False)
    blinds(dt, F, fs(12.0), fs(9.5), 5.2, 0.55, 0.45, "Blind")
    wall(sh, F, 0.0, fs(X0), 5.25, 5.9, [], "BrickRed")
    wall(sh, S, 0.0, ss(Y1), 5.25, 5.9, [], "BrickRed")

    # ---- 4th floor (5.9 .. 8.0): brick with three windows on each face
    wf = [(fs(13.9), fs(12.0), 6.3, 7.6), (fs(11.5), fs(9.7), 6.3, 7.6), (fs(9.2), fs(7.4), 6.3, 7.6)]
    wsd = [(ss(10.2), ss(11.9), 6.3, 7.6), (ss(12.6), ss(14.3), 6.3, 7.6), (ss(15.0), ss(16.7), 6.3, 7.6)]
    wall(sh, F, 0.0, fs(X0), 5.9, 8.7, wf, "BrickRed")
    wall(sh, S, 0.0, ss(Y1), 5.9, 8.7, wsd, "BrickRed")
    for w in wf:
        window(dt, F, *w, style="casement", transom=0.95, frame="WinFrame")
    for w in wsd:
        window(dt, S, *w, style="casement", transom=0.95, frame="WinFrame")
    room(dt, F, 0.0, fs(X0), 5.9, 8.55, 0.3, 4.0, wall="RoomWallWarm", lights=False)
    room(dt, S, 0.0, ss(Y1), 5.9, 8.55, 0.3, 4.0, wall="RoomWallWarm", lights=False)
    blinds(dt, S, ss(12.6), ss(14.3), 7.55, 0.5, 0.42, "Blind")
    for F_, L in ((F, fs(X0)), (S, ss(Y1))):
        for z in (5.25, 8.0):
            band(sh, F_, -0.08, L, z - 0.08, z + 0.06, 0.08, "Trim")

    # ---- awnings: corrugated steel over both faces (5.9 and 8.7)
    for top, drop, reach in ((5.9, 0.6, 0.65), (8.7, 0.6, 0.5)):
        for F_, a, c in ((F, 0.0, fs(X0) + reach), (S, -reach, ss(Y1))):
            p0, p1 = F_.p(a, top - drop, -reach), F_.p(c, top - drop, -reach)
            q0, q1 = F_.p(a, top, 0.0), F_.p(c, top, 0.0)
            sh.quad(p0, p1, q1, q0, F_.N * 0.7 + np.array([0, 0, 0.7]), "Awning")
            sh.quad(p0, p1, q1, q0, -(F_.N * 0.3) - np.array([0, 0, 1.0]), "AwningUnder")
            obox(sh, F_, a, c, top - drop - 0.06, top - drop, -reach - 0.03, -reach + 0.02, "Steel")

    # ---- mansard roof, dormers, gutter, rooftop
    inset, top = 1.6, 11.8
    a, b_, c, d = [X0, Y0, 8.7], [X1, Y0, 8.7], [X1, Y0 + inset, top], [X0 + inset, Y0 + inset, top]
    sh.quad(a, b_, c, d, [0, -0.85, 0.5], "RoofTiles")
    e, f = [X0, Y1, 8.7], [X0 + inset, Y1, top]
    sh.quad(a, d, f, e, [-0.85, 0, 0.5], "RoofTiles")
    sh.quad(d, c, [X1, Y1, top], f, [0, 0, 1], "RoofDeck")
    sh.quad(b_, [X1, Y1, 8.7], [X1, Y1, top], c, [1, 0, 0], "ConcreteSide")
    sh.quad(e, [X1, Y1, 8.7], [X1, Y1, top], f, [0, 1, 0], "ConcreteSide")
    for dy0, dy1 in ((10.6, 12.3), (13.5, 15.1), (16.0, 17.6)):
        dx0, dz0, dz1 = X0 + 0.55, 9.4, 10.9
        sh.box(dx0, X0 + inset, dy0, dy1, dz0, dz1, "PlasterCream", skip=("-Z",))
        D = Facade((dx0, dy0), (dx0, dy1))
        window(dt, D, 0.25, dy1 - dy0 - 0.25, dz0 + 0.25, dz1 - 0.2, style="casement", depth=0.0, frame="WinFrame", sill="Sill")
        mid = (dy0 + dy1) / 2
        sh.triangle([dx0 - 0.08, dy0 - 0.08, dz1], [dx0 - 0.08, dy1 + 0.08, dz1], [dx0 - 0.08, mid, dz1 + 0.6], [-1, 0, 0], "PlasterCream")
        sh.quad([dx0 - 0.08, dy0 - 0.08, dz1], [X0 + inset, dy0 - 0.08, dz1], [X0 + inset, mid, dz1 + 0.6], [dx0 - 0.08, mid, dz1 + 0.6], [0, -0.6, 0.8], "RoofTiles")
        sh.quad([dx0 - 0.08, dy1 + 0.08, dz1], [X0 + inset, dy1 + 0.08, dz1], [X0 + inset, mid, dz1 + 0.6], [dx0 - 0.08, mid, dz1 + 0.6], [0, 0.6, 0.8], "RoofTiles")
    tube(dt, [X0 - 0.12, Y0 - 0.12, 8.66], [X1, Y0 - 0.12, 8.66], 0.07, "Gutter", 10)
    tube(dt, [X0 - 0.12, Y0 - 0.12, 8.66], [X0 - 0.12, Y1, 8.66], 0.07, "Gutter", 10)
    tube(dt, [X0 - 0.12, Y0 - 0.12, 8.66], [X0 - 0.12, Y0 - 0.12, 6.0], 0.05, "Gutter", 10)
    for x0_, x1_, y0_, y1_ in ((X0 + inset, X1, Y1 - 0.15, Y1), (X1 - 0.15, X1, Y0 + inset, Y1)):
        sh.box(x0_, x1_, y0_, y1_, top, top + 0.5, "ConcreteSide", skip=("-Z",))
    dt.cylinder((12.6, 17.0), 0.75, top, top + 1.4, "TankBlue", segments=20)
    dt.cylinder((12.6, 17.0), 0.22, top + 1.4, top + 1.55, "TankBlue", segments=12)
    b.place(AC, (10.0, 13.9), top, 0.0)
    b.place(AC_RUST, (11.2, 13.9), top, 0.0)
    # services on the side face: downpipe, gas pipe and meter, cables to the pole across the street
    downpipe(dt, S, ss(Y1) - 0.2, G, 8.6)
    gas_pipe(dt, S, [(ss(18.6), G + 1.0), (ss(18.6), 5.6), (ss(17.6), 5.6)])
    gas_meter(b, S, ss(18.9), G + 1.1)
    conduit_bundle(dt, S, ss(16.6), ss(Y1), 1.05, count=4)
    b.place(CAMERA, S.xy(0.4, -0.1), 1.3, S.yaw())
    b.place(WALL_LAMP, F.xy(fs(12.5), -0.05), 0.3, F.yaw())
    b.place(CHALKBOARD, F.xy(fs(12.9), -1.1), -2.12, F.yaw() + 15.0, 0.8)
    b.removal = {"front": [(F, 0.0, fs(X0), G - 0.3, 13.0, 1.2), (S, 0.0, ss(Y1), G - 0.3, 13.0, 1.2)], "extra": []}
    return b


def all_buildings():
    return [solb(), bibiang(), blue_elephant()]
