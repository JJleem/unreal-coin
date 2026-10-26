"""
The rest of the Hongdae red street, rebuilt for the night version (Lvl_Hongdae_Night): the facades the scan measured
(generated/Hongdae_layout.json) between the start intersection and x = 46 m, plus closing blocks beyond. Shop types,
storey counts and signs follow the baked facade photos (SourceAssets/Rebuilt/Hongdae/face_*.png) where the scan
saw them (Tax-Free shop, Golden Crema, the film tinting shop with Coffee Brown upstairs, the yellow menu board
restaurant, the tiled towers with the pink cosmetics ad across the intersection); where it didn't, plausible Hongdae
night shops (pocha, karaoke, PC bang, convenience store).

Every building comes from one template (street_building) driven by a small config: a ground floor shop with a lit
light box fascia, upper floors with windows (some lit), floor signs, blade signs, AC units, a parapet and a roof.
Each building also records the lights the night level needs: a warm rect light in every shop front (spilling onto
the street) and a coloured point light at every big sign.

Coordinates: Unreal metres in the stage frame (X along the street, Y right, Z up), as in hongdae_buildings.py.
"""

import math
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reimagined"))
import bkit  # noqa: E402
import signs  # noqa: E402
from bkit import Facade, obox, wall, band, window, room, storefront, sign_box, blade_sign, letters, downpipe, \
    conduit_bundle, parapet, cap, blinds, shutter_box, cable  # noqa: E402

KO = signs.KO
KO_LIGHT = signs.KO_LIGHT
LATIN = signs.LATIN
AC = "exterior_aircon_unit/exterior_aircon_unit_1k/StaticMeshes/exterior_aircon_unit"
AC_RUST = "exterior_aircon_unit/exterior_aircon_unit_1k/StaticMeshes/exterior_aircon_unit_rusted"
UTILITY_BOX = "utility_box_01/utility_box_01_1k/StaticMeshes/utility_box_01_1k"
TRASHBAG = "trashbag/trashbag_1k/StaticMeshes/trashbag_1k"
CRATE = "plastic_crate_02/plastic_crate_02_1k/StaticMeshes/plastic_crate_02_1k"
CHAIR = "plastic_monobloc_chair_01/plastic_monobloc_chair_01_1k/StaticMeshes/plastic_monobloc_chair_01_1k"

WARM = (1.0, 0.78, 0.52)
COOL = (0.85, 0.92, 1.0)


class NightBuilding(bkit.Building):
    def __init__(self, name, footprint, ground, top):
        super().__init__(name, footprint, ground, top)
        self.lights = []

    def rect_light(self, F, s, z, d, width, height, color=WARM, intensity=1.0):
        """Rect light inside a shop front at facade position (s, z), d into the building, shining out to the street."""
        x, y, zz = F.p(s, z, d)
        self.lights.append({"type": "rect", "pos": [x, y, zz], "yaw": float(np.degrees(np.arctan2(F.n[1], F.n[0]))),
                            "w": width, "h": height, "color": list(color), "intensity": intensity})

    def point_light(self, F, s, z, d, color, intensity=1.0, radius=6.0):
        x, y, zz = F.p(s, z, d)
        self.lights.append({"type": "point", "pos": [x, y, zz], "color": list(color), "intensity": intensity, "radius": radius})


# --------------------------------------------------------------------------------------------------------- sign faces

def make_signs(out):
    """Sign faces of the night buildings (drawn with real fonts, like reimagined/signs.py). Returns name -> file."""
    os.makedirs(out, exist_ok=True)
    f = {}
    P = lambda n: os.path.join(out, f"sign_{n}.png")
    T = signs.text_face
    f["taxfree"] = T(P("taxfree"), 2.6, 0.75, (205, 25, 45), [("Tax-Free Shop", LATIN, (255, 245, 240), 0.42, 0.5, 0.7, 0.62),
                                                                 ("免税店", signs.ZH, (255, 230, 120), 0.86, 0.5, 0.22, 0.4)], border=(255, 255, 255), seed=21)
    f["crema_cafe"] = T(P("crema_cafe"), 3.0, 0.5, (240, 240, 236), [("GOLDEN CREMA  COFFEE", LATIN, (40, 90, 170), 0.5, 0.52, 0.9, 0.6)], seed=22)
    f["film"] = T(P("film"), 3.6, 0.95, (238, 236, 228), [("필름부착전문점", KO, (205, 30, 50), 0.5, 0.42, 0.92, 0.55),
                                                          ("썬팅 · 시트지 · 유리필름", KO_LIGHT, (30, 60, 160), 0.5, 0.82, 0.7, 0.2)], seed=23)
    f["coffee_brown"] = T(P("coffee_brown"), 3.2, 0.55, (248, 244, 236), [("Coffee Brown", signs.SERIF, (120, 60, 70), 0.5, 0.52, 0.9, 0.7)], seed=24)
    f["yellow_menu"] = T(P("yellow_menu"), 1.4, 1.5, (250, 210, 40), [("닭갈비", KO, (180, 20, 20), 0.5, 0.2, 0.86, 0.22),
                                                                       ("막국수", KO, (180, 20, 20), 0.5, 0.45, 0.86, 0.2),
                                                                       ("24시 영업", KO, (30, 30, 30), 0.5, 0.75, 0.86, 0.16)], border=(200, 30, 20), seed=25)
    f["yellow_blade"] = signs._blade(P("yellow_blade"), 0.55, 2.2, (250, 210, 40), "춘천닭갈비", "1F", (180, 20, 20), (30, 30, 30), 26)
    f["pocha"] = T(P("pocha"), 2.8, 0.7, (20, 20, 24), [("홍대 포차", KO, (255, 120, 40), 0.5, 0.5, 0.9, 0.7)], border=(255, 120, 40), seed=27)
    f["karaoke"] = T(P("karaoke"), 3.2, 0.8, (60, 10, 90), [("코인노래방", KO, (255, 90, 230), 0.5, 0.5, 0.9, 0.66)], border=(80, 220, 255), seed=28)
    f["pcbang"] = T(P("pcbang"), 2.6, 0.7, (10, 30, 60), [("PC방  3F", KO, (80, 220, 255), 0.5, 0.5, 0.9, 0.66)], border=(80, 220, 255), seed=29)
    f["karaoke_blade"] = signs._blade(P("karaoke_blade"), 0.55, 2.4, (60, 10, 90), "노래연습장", "2F", (255, 120, 240), (255, 255, 255), 30)
    f["cvs"] = T(P("cvs"), 4.0, 0.6, (250, 250, 250), [("CU", LATIN, (120, 40, 160), 0.18, 0.5, 0.25, 0.7),
                                                      ("편의점  24H", KO, (40, 170, 60), 0.62, 0.5, 0.6, 0.55)], seed=31)
    f["chicken"] = T(P("chicken"), 3.0, 0.75, (230, 120, 20), [("치킨 & 호프", KO, (255, 255, 255), 0.5, 0.5, 0.9, 0.66)], border=(120, 40, 10), seed=32)
    f["cosme"] = T(P("cosme"), 2.6, 0.6, (240, 90, 140), [("medicube", LATIN, (255, 255, 255), 0.5, 0.5, 0.8, 0.6)], seed=33)
    f["cosme_ad"] = signs.poster(P("cosme_ad"), 2.4, 3.2, (245, 170, 200), (200, 60, 120), "medicube", "AGE-R 부스터 프로", seed=34)
    f["brand"] = T(P("brand"), 2.6, 0.5, (240, 240, 240), [("BRAND MARKET", LATIN, (30, 30, 30), 0.5, 0.52, 0.9, 0.6)], seed=35)
    f["bar"] = T(P("bar"), 2.4, 0.6, (12, 12, 14), [("BAR  LOUNGE", LATIN, (255, 200, 120), 0.5, 0.5, 0.86, 0.6)], border=(255, 200, 120), seed=36)
    f["ramen"] = T(P("ramen"), 2.6, 0.65, (190, 30, 30), [("라멘 · 덮밥", KO, (255, 240, 220), 0.5, 0.5, 0.86, 0.66)], seed=37)
    f["phone"] = T(P("phone"), 2.6, 0.6, (20, 80, 200), [("휴대폰 성지", KO, (255, 255, 255), 0.5, 0.5, 0.86, 0.66)], seed=38)
    f["hair"] = T(P("hair"), 2.4, 0.5, (30, 30, 32), [("HAIR STUDIO  2F", LATIN, (240, 240, 240), 0.5, 0.52, 0.86, 0.6)], seed=39)
    f["dakgalbi"] = T(P("dakgalbi"), 2.8, 0.7, (40, 40, 44), [("고기 굽는 집", KO, (255, 210, 120), 0.5, 0.5, 0.86, 0.66)], border=(255, 210, 120), seed=40)
    f["pub_blade"] = signs._blade(P("pub_blade"), 0.55, 2.2, (12, 12, 14), "칵테일바", "B1", (255, 200, 120), (255, 255, 255), 41)
    f["pc_blade"] = signs._blade(P("pc_blade"), 0.55, 2.4, (10, 30, 60), "PC방", "3F", (80, 220, 255), (255, 255, 255), 42)
    return f


SIGN_COLOUR = {   # glow colour of each sign face (point light in front of it)
    "taxfree": (1.0, 0.25, 0.3), "crema_cafe": (0.85, 0.9, 1.0), "film": (1.0, 0.95, 0.9), "coffee_brown": (1.0, 0.92, 0.82),
    "yellow_menu": (1.0, 0.8, 0.25), "yellow_blade": (1.0, 0.8, 0.25), "pocha": (1.0, 0.5, 0.2), "karaoke": (0.9, 0.35, 1.0),
    "pcbang": (0.35, 0.85, 1.0), "karaoke_blade": (0.9, 0.35, 1.0), "cvs": (0.9, 0.95, 1.0), "chicken": (1.0, 0.6, 0.15),
    "cosme": (1.0, 0.45, 0.65), "cosme_ad": (1.0, 0.6, 0.75), "brand": (0.95, 0.95, 0.95), "bar": (1.0, 0.75, 0.45),
    "ramen": (1.0, 0.3, 0.25), "phone": (0.3, 0.55, 1.0), "hair": (0.9, 0.9, 0.9), "dakgalbi": (1.0, 0.8, 0.5),
    "pub_blade": (1.0, 0.75, 0.45), "pc_blade": (0.35, 0.85, 1.0),
}


# ----------------------------------------------------------------------------------------------------------- template

def street_building(c):
    """c: name, side "N" / "S", x0, x1, y (street face), G (ground), depth, floors [storey heights], walls
    (ground material, upper material), shop {kind, sign, open, frame, wall, floor}, uppers [{windows, style, lit,
    sign, grille}], optional blade (s, tex, floor), letters, roof extras."""
    name, side, G = c["name"], c["side"], c["G"]
    depth = c.get("depth", 9.0)
    if side in ("S", "N"):
        x0, x1, y = c["x0"], c["x1"], c["y"]
        a, b = ((x0, y), (x1, y)) if side == "S" else ((x1, y), (x0, y))
    else:
        # street ends: "E" faces -X (closing the street ahead), "W" faces +X
        x, y0, y1 = c["x"], c["y0"], c["y1"]
        a, b = ((x, y0), (x, y1)) if side == "E" else ((x, y1), (x, y0))
    F = Facade(a, b)
    W = F.length
    back = [F.a - F.n * depth, F.b - F.n * depth]
    footprint = [tuple(F.a), tuple(F.b), tuple(back[1]), tuple(back[0])]
    floors = c["floors"]
    levels = [G]
    for h in floors:
        levels.append(levels[-1] + h)
    top = levels[-1]
    bld = NightBuilding(c["name"], footprint, G, top + 0.6)
    sh, dt = bld.shell, bld.detail
    rng = np.random.default_rng(zlib.crc32(name.encode()))      # same building every run (hash() is salted)
    gmat, umat = c["walls"]
    base = G - 0.6

    # ---- ground floor shop
    shop = c["shop"]
    z1 = levels[1]
    open_top = G + min(2.7, floors[0] - 0.7)
    m = 0.35 if W > 3 else 0.2
    opening = (m, W - m, G, open_top)
    wall(sh, F, 0.0, W, base, z1, [opening], gmat, thickness=0.3)
    if shop.get("open", True):
        doors = [(W * 0.62, 1.0, 1)] if W > 3.2 else [(m + 0.1, 0.9, 1)]
        storefront(dt, F, *opening, doors=doors, frame=shop.get("frame", "AluDark"), transom=min(2.3, open_top - G - 0.3))
        room(dt, F, m, W - m, G, open_top + 0.2, 0.3, min(6.0, depth - 0.8), wall=shop.get("wall", "RoomWallWhite"),
             floor=shop.get("floor", "RoomFloorTile"), spacing=1.1)
        kind = shop.get("kind")
        if kind:
            _fit_out(bld, F, m, W - m, G, depth, kind, rng)
        bld.rect_light(F, W / 2, G + 1.6, 1.2, W - 2 * m - 0.3, 1.8, shop.get("light", WARM), shop.get("light_power", 1.0))
    else:
        # closed: a lowered roller shutter (painted, a little graffiti in the texture of the shutter material)
        obox(dt, F, *opening[:2], G, open_top, 0.05, 0.1, "Shutter", skip=("back",))
        shutter_box(dt, F, opening[0] - 0.05, opening[1] + 0.05, open_top, open_top + 0.35)
    # fascia light box over the shop
    if shop.get("sign"):
        sz0 = open_top + 0.12
        sz1 = min(z1 - 0.1, sz0 + shop.get("sign_h", 0.75))
        sign_box(dt, F, 0.15, W - 0.15, sz0, sz1, f"Sign_{shop['sign']}", depth=0.22)
        bld.point_light(F, W / 2, (sz0 + sz1) / 2 - 0.4, -1.6, SIGN_COLOUR[shop["sign"]], 1.0, radius=7.0)

    # ---- upper floors
    for k, up in enumerate(c.get("uppers", [])):
        za, zb = levels[k + 1], levels[k + 2]
        n = up.get("windows", max(1, int(W // 2.2)))
        ww = up.get("width", min(1.6, (W - 0.8) / n - 0.5))
        wh = up.get("height", min(1.6, zb - za - 1.1))
        wz0 = za + up.get("sill", 0.85)
        gap = (W - n * ww) / (n + 1)
        wins = [(gap + i * (ww + gap), gap + i * (ww + gap) + ww, wz0, wz0 + wh) for i in range(n)]
        if up.get("strip"):
            wins = [(0.35, W - 0.35, za + 0.35, zb - 0.45)]
        wall(sh, F, 0.0, W, za, zb, wins, up.get("wall", umat))
        lit = rng.random() < up.get("lit", 0.6)
        for w in wins:
            window(dt, F, *w, style=up.get("style", "slider"), grille=up.get("grille"), frame=up.get("frame", "WinFrame"))
        room(dt, F, 0.0, W, za, zb - 0.15, 0.25, min(4.5, depth - 0.5), wall="RoomWallWarm" if lit else "RoomWallDark",
             floor="RoomFloorWood" if lit else "RoomFloorDark", ceiling="RoomCeiling" if lit else "RoomCeilingDark",
             lights=lit, spacing=1.4)
        if lit:
            for w in wins:
                if rng.random() < 0.35:
                    blinds(dt, F, w[0] + 0.05, w[1] - 0.05, w[3] - 0.05, rng.uniform(0.3, 0.9), 0.42, "Blind")
            bld.rect_light(F, W / 2, wz0 + wh / 2, 0.8, max(0.8, W - 1.0), wh, up.get("light", WARM), 0.35)
        if up.get("sign"):
            s0, s1 = up.get("sign_span", (0.3, W - 0.3))
            zs0 = wz0 + wh + 0.12
            zs1 = min(zb - 0.08, zs0 + up.get("sign_h", 0.55))
            if zs1 - zs0 > 0.25:
                sign_box(dt, F, s0, s1, zs0, zs1, f"Sign_{up['sign']}", depth=0.16)
                bld.point_light(F, (s0 + s1) / 2, (zs0 + zs1) / 2, -1.2, SIGN_COLOUR[up["sign"]], 0.6, radius=5.0)
        if up.get("ac") and not up.get("strip"):
            s = wins[0][1] + 0.6 if len(wins) > 1 else W - 0.6
            bld.place(AC if rng.random() < 0.6 else AC_RUST, F.xy(min(s, W - 0.5), -0.25), za + 0.05, F.yaw())
        band(sh, F, -0.04, W + 0.04, za - 0.07, za + 0.07, 0.05, up.get("band", "Trim"))

    # blade sign
    if c.get("blade"):
        s, tex, z0 = c["blade"]
        blade_sign(dt, F, s, z0, z0 + 2.3, (f"Sign_{tex}", f"Sign_{tex}"), out0=0.12, width=0.58)
        bld.point_light(F, s, z0 + 1.1, -1.0, SIGN_COLOUR[tex], 0.5, radius=4.0)
    # channel letters (lit LED letters)
    if c.get("letters"):
        text, font, s, z, h, mat = c["letters"]
        letters(dt, F, text, font, s, z, h, 0.06, -0.06, mat, "LetterSide")
    # big wall ad
    if c.get("ad"):
        s0, s1, z0, z1, tex = c["ad"]
        sign_box(dt, F, s0, s1, z0, z1, f"Sign_{tex}", depth=0.12)
        bld.point_light(F, (s0 + s1) / 2, (z0 + z1) / 2, -2.0, SIGN_COLOUR[tex], 0.8, radius=8.0)

    # big ad on an exposed side wall (where the neighbour is set back or lower)
    if c.get("side_ad"):
        k, s0, s1, z0, z1, tex = c["side_ad"]
        S = Facade(*(((back[0], F.a), (F.b, back[1]))[k]))
        sign_box(dt, S, s0, s1, z0, z1, f"Sign_{tex}", depth=0.15)
        bld.point_light(S, (s0 + s1) / 2, (z0 + z1) / 2, -2.5, SIGN_COLOUR[tex], 1.0, radius=9.0)
    # ---- sides (small windows on the upper floors, some lit: they show where a neighbour is lower), back, roof
    for side_no, (P0, P1) in enumerate(((back[0], F.a), (F.b, back[1]), (back[1], back[0]))):
        S = Facade(P0, P1)
        wins = []
        if side_no < 2 and len(levels) > 2:
            for za, zb in zip(levels[1:-1], levels[2:]):
                for s in (S.length * 0.3, S.length * 0.7):
                    wins.append((s - 0.45, s + 0.45, za + 0.9, za + 2.0))
        wall(sh, S, 0.0, S.length, base, top, wins, c.get("side_wall", "ConcreteSide"))
        for w in wins:
            lit = rng.random() < 0.45
            window(dt, S, *w, style="slider", grille="GrilleDark" if rng.random() < 0.5 else None)
            room(dt, S, w[0] - 0.2, w[1] + 0.2, w[2] - 0.9, w[3] + 0.5, 0.25, 2.0, wall="RoomWallWarm" if lit else "RoomWallDark",
                 floor="RoomFloorWood" if lit else "RoomFloorDark", ceiling="RoomCeiling" if lit else "RoomCeilingDark",
                 lights=lit, spacing=1.2)
    parapet(sh, F, 0.0, W, top, 0.7, umat)
    cap(sh, bkit.Polygon(footprint), top, True, "RoofDeck")
    downpipe(dt, F, W - 0.15, G, top + 0.5)
    conduit_bundle(dt, F, 0.0, W, levels[1] - 0.15, count=3)
    if rng.random() < 0.6:
        bld.place(TRASHBAG, F.xy(rng.uniform(0.3, W - 0.3), -0.35), G, rng.uniform(0, 360))
    bld.removal = {"front": [], "extra": []}
    return bld


def _fit_out(b, F, s0, s1, z0, depth, kind, rng):
    """Shop contents seen through the glass (bkit fixtures, kept simple)."""
    dt = b.detail
    d0, back = 0.3, min(6.0, depth - 0.8) + 0.3
    if kind in ("boutique", "cosme", "phone", "cvs"):
        bkit.display_wall(dt, F, s0 + 0.1, s1 - 0.1, z0, back, rng, height=2.2, shelf=0.36 if kind != "cvs" else 0.3, small=kind != "boutique")
        if kind == "cvs":
            for d in (2.0, 3.6):
                obox(dt, F, s0 + 0.6, s1 - 0.6, z0, z0 + 1.5, d, d + 0.5, "ShopShelf")
                obox(dt, F, s0 + 0.6, s1 - 0.6, z0 + 0.4, z0 + 1.4, d - 0.01, d, "ProductB")
        elif kind == "boutique":
            bkit.clothes_rack(dt, F, s0 + 0.4, s0 + 0.4 + min(1.4, (s1 - s0) * 0.4), z0, d0 + 2.0, rng)
        obox(dt, F, s0 + (s1 - s0) * 0.55, s0 + (s1 - s0) * 0.85, z0, z0 + 0.95, back - 1.5, back - 1.0, "Counter")
    elif kind in ("pocha", "restaurant", "chicken"):
        for k, s in enumerate(np.arange(s0 + 0.8, s1 - 0.5, 1.5)):
            dd = d0 + 1.3 + (k % 2) * 1.6
            obox(dt, F, s - 0.45, s + 0.45, z0 + 0.7, z0 + 0.74, dd - 0.35, dd + 0.35, "TableTop")
            obox(dt, F, s - 0.04, s + 0.04, z0, z0 + 0.7, dd - 0.04, dd + 0.04, "Steel")
            for off in (-0.6, 0.6):
                obox(dt, F, s - 0.18, s + 0.18, z0, z0 + 0.42, dd + off - 0.15, dd + off + 0.15, "StoolRed")
        obox(dt, F, s0 + 0.2, s1 - 0.2, z0, z0 + 1.0, back - 0.9, back - 0.3, "Counter")
    elif kind == "cafe":
        obox(dt, F, s0 + 0.3, s0 + 2.4, z0, z0 + 1.0, back - 1.0, back - 0.4, "Counter")
        obox(dt, F, s0 + 0.28, s0 + 2.42, z0 + 1.0, z0 + 1.04, back - 1.02, back - 0.38, "CounterTop")
        for k, s in enumerate(np.arange(s0 + 0.9, s1 - 0.6, 1.6)):
            obox(dt, F, s - 0.35, s + 0.35, z0 + 0.72, z0 + 0.75, d0 + 1.0, d0 + 1.7, "TableTop")
            obox(dt, F, s - 0.03, s + 0.03, z0, z0 + 0.72, d0 + 1.32, d0 + 1.38, "Steel")


# ------------------------------------------------------------------------------------------------------------ the street

def configs():
    U = dict(windows=2, style="slider", lit=0.65, ac=True)
    return [
        # ---- south side, east of SOLB (street face y = -1.3 like SOLB's)
        dict(name="TaxFree", side="S", x0=15.6, x1=18.6, y=-1.3, G=-1.85, depth=8.0, floors=[3.3],
             walls=("TileDark", "ConcreteSide"), shop=dict(sign="taxfree", open=False, sign_h=0.7), uppers=[]),
        dict(name="GoldenCrema", side="S", x0=18.6, x1=25.25, y=-0.6, G=-1.82, depth=10.0, floors=[3.4, 2.7, 2.7, 2.7],
             walls=("PlasterWhite", "CladGrey"),
             shop=dict(kind="cafe", sign="crema_cafe", sign_h=0.5, wall="RoomWallWarm", floor="RoomFloorWood"),
             uppers=[dict(windows=2, width=2.0, height=1.9, style="grid", frame="AluDark", lit=0.9),
                     dict(windows=2, width=2.0, height=1.9, style="grid", frame="AluDark", lit=0.7),
                     dict(windows=2, width=2.0, height=1.9, style="grid", frame="AluDark", lit=0.4)],
             letters=("GOLDEN CREMA", LATIN, 4.6, 7.25, 0.34, "LetterWarm")),
        dict(name="Pocha", side="S", x0=25.25, x1=28.25, y=-0.4, G=-1.76, depth=8.0, floors=[3.2, 2.7, 2.7],
             walls=("BrickRed", "BrickRed"), shop=dict(kind="pocha", sign="pocha", light=(1.0, 0.7, 0.45)),
             uppers=[dict(windows=1, width=1.4, lit=0.5, ac=True), dict(windows=1, width=1.4, lit=0.6)],
             side_ad=(1, 0.6, 3.4, 1.9, 6.4, "cosme_ad")),
        dict(name="CVS", side="S", x0=28.6, x1=34.4, y=-4.2, G=-1.31, depth=9.0, floors=[3.5, 2.8],
             walls=("PlasterWhite", "PlasterWhite"), shop=dict(kind="cvs", sign="cvs", sign_h=0.6, light=COOL, light_power=1.6),
             uppers=[dict(windows=2, width=1.6, lit=0.3, sign="hair", sign_h=0.45, ac=True)]),
        dict(name="Chicken", side="S", x0=34.4, x1=40.0, y=-2.5, G=-1.4, depth=9.0, floors=[3.3, 2.8, 2.8],
             walls=("TileBeige", "TileBeige"), shop=dict(kind="chicken", sign="chicken"),
             uppers=[dict(U, sign="karaoke"), dict(U, lit=0.5)], blade=(5.2, "karaoke_blade", 1.6)),
        dict(name="Ramen", side="S", x0=40.0, x1=46.0, y=-2.5, G=-1.3, depth=9.0, floors=[3.3, 2.8, 2.8, 2.8],
             walls=("Granite", "BrickWhite"), shop=dict(kind="restaurant", sign="ramen"),
             uppers=[dict(U, sign="pcbang"), dict(U), dict(U, lit=0.4)], blade=(0.4, "pc_blade", 4.2)),
        # ---- north side, east of the Blue Elephant (street face y = 5.75, faces -Y)
        dict(name="GreenShop", side="N", x0=14.8, x1=17.0, y=5.75, G=-1.95, depth=6.0, floors=[3.3],
             walls=("PaintGreen", "PaintGreen"), shop=dict(kind="boutique", sign=None), uppers=[]),
        dict(name="FilmShop", side="N", x0=17.0, x1=21.6, y=5.75, G=-1.95, depth=9.0, floors=[3.4, 3.2],
             walls=("SidingWhite", "SidingWhite"), shop=dict(kind="boutique", sign="film", sign_h=0.95, wall="RoomWallWhite"),
             uppers=[dict(windows=1, width=2.6, height=1.9, style="grid", frame="AluDark", lit=1.0, sign="coffee_brown",
                          sign_h=0.55, light=(1.0, 0.75, 0.5))]),
        dict(name="YellowMenu", side="N", x0=21.6, x1=25.25, y=5.75, G=-1.95, depth=9.0, floors=[3.3, 2.8, 2.8],
             walls=("ConcreteSide", "BrickWhite"), shop=dict(kind="restaurant", sign="dakgalbi"),
             uppers=[dict(U), dict(U, lit=0.4)], blade=(0.35, "yellow_blade", 0.4), ad=(0.5, 1.9, -1.4, 0.1, "yellow_menu")),
        dict(name="NorthTall", side="N", x0=25.25, x1=31.25, y=7.4, G=-1.95, depth=10.0, floors=[3.4, 3.0, 3.0, 3.0],
             walls=("Granite", "TileBeige"), shop=dict(kind="phone", sign="phone", light=COOL),
             uppers=[dict(U, windows=3, sign="karaoke"), dict(U, windows=3), dict(U, windows=3, lit=0.3)],
             blade=(0.4, "karaoke_blade", 4.0)),
        dict(name="Bar", side="N", x0=31.25, x1=36.0, y=4.6, G=-1.35, depth=9.0, floors=[3.3, 2.8],
             walls=("TileDark", "BrickRed"), shop=dict(kind="pocha", sign="bar", light=(1.0, 0.62, 0.35), light_power=0.7),
             uppers=[dict(U, windows=2)], blade=(0.35, "pub_blade", 3.6)),
        dict(name="Brand", side="N", x0=36.0, x1=41.25, y=4.3, G=-1.4, depth=9.0, floors=[3.4, 3.0, 3.0],
             walls=("PlasterWhite", "CladGrey"), shop=dict(kind="boutique", sign="brand"),
             uppers=[dict(U, style="grid", frame="AluDark"), dict(U, style="grid", frame="AluDark", lit=0.5)]),
        dict(name="NorthEnd", side="N", x0=41.25, x1=46.5, y=5.3, G=-1.25, depth=9.0, floors=[3.3, 2.8, 2.8, 2.8],
             walls=("TileDark", "BrickWhite"), shop=dict(kind="cafe", sign="coffee_brown"),
             uppers=[dict(U), dict(U, sign="hair"), dict(U, lit=0.3)]),
        # ---- across the intersection (west): the tiled towers with the cosmetics ad, low shops on the south corner
        dict(name="Cosme", side="N", x0=-5.75, x1=-0.75, y=6.5, G=-1.69, depth=10.0, floors=[3.6, 3.0, 3.0, 3.0],
             walls=("PaintPink", "TileWhite"), shop=dict(kind="cosme", sign="cosme", light=(1.0, 0.85, 0.9)),
             uppers=[dict(U, windows=2), dict(U, windows=2), dict(U, windows=2, lit=0.4)], ad=(0.6, 3.0, 1.9, 5.1, "cosme_ad")),
        dict(name="WestTall", side="N", x0=-12.75, x1=-5.75, y=5.75, G=-1.68, depth=10.0, floors=[3.6, 3.0, 3.0, 3.0, 3.0],
             walls=("Granite", "TileWhite"), shop=dict(kind="boutique", sign="brand"),
             uppers=[dict(U, windows=3), dict(U, windows=3, sign="hair"), dict(U, windows=3), dict(U, windows=3, lit=0.3)]),
        dict(name="SouthCorner", side="S", x0=-8.75, x1=-2.75, y=-5.0, G=-1.1, depth=8.0, floors=[3.3, 2.8],
             walls=("BrickWhite", "BrickWhite"), shop=dict(kind="pocha", sign="chicken"),
             uppers=[dict(U, windows=2)]),
        dict(name="SouthCorner2", side="S", x0=-2.75, x1=2.25, y=-3.6, G=-1.95, depth=8.0, floors=[3.3, 2.8, 2.8],
             walls=("TileDark", "TileBeige"), shop=dict(kind="phone", sign="phone", light=COOL),
             uppers=[dict(U, windows=2, sign="pcbang"), dict(U, windows=2)]),
        # ---- closing blocks beyond the measured street (x 46-58)
        dict(name="FarSouth", side="S", x0=46.0, x1=58.0, y=-2.0, G=-1.2, depth=10.0, floors=[3.4, 3.0, 3.0],
             walls=("TileDark", "ConcreteSide"), shop=dict(kind="restaurant", sign="dakgalbi"),
             uppers=[dict(U, windows=4, sign="karaoke"), dict(U, windows=4, lit=0.5)]),
        dict(name="FarNorth", side="N", x0=46.5, x1=58.0, y=6.0, G=-1.1, depth=10.0, floors=[3.4, 3.0, 3.0, 3.0],
             walls=("Granite", "TileBeige"), shop=dict(kind="cvs", sign="cvs", light=COOL, light_power=1.4),
             uppers=[dict(U, windows=4, sign="pcbang"), dict(U, windows=4), dict(U, windows=4, lit=0.3)]),
    ]


def closing_configs():
    """Blocks closing the views out of the rebuilt part: the street end, beyond the intersection, the cross street."""
    U = dict(windows=3, style="slider", lit=0.55, ac=True)
    return [
        dict(name="EndEast", side="E", x=58.6, y0=-3.0, y1=7.5, G=-1.1, depth=8.0, floors=[3.4, 3.0, 3.0, 3.0, 3.0],
             walls=("TileDark", "TileBeige"), shop=dict(kind="chicken", sign="chicken"),
             uppers=[dict(U, sign="karaoke"), dict(U), dict(U, sign="pcbang"), dict(U, lit=0.3)], blade=(0.5, "karaoke_blade", 4.2)),
        dict(name="EndWest", side="W", x=-12.9, y0=-6.0, y1=5.6, G=-1.6, depth=8.0, floors=[3.5, 3.0, 3.0, 3.0],
             walls=("Granite", "BrickWhite"), shop=dict(kind="cvs", sign="cvs", light=COOL, light_power=1.4),
             uppers=[dict(U, sign="hair"), dict(U), dict(U, lit=0.4)]),
        dict(name="CrossNorth", side="N", x0=-0.75, x1=6.1, y=13.0, G=-2.3, depth=8.0, floors=[3.4, 3.0, 3.0],
             walls=("TileWhite", "TileWhite"), shop=dict(kind="cafe", sign="crema_cafe", sign_h=0.5),
             uppers=[dict(U, windows=2, sign="bar"), dict(U, windows=2)]),
        dict(name="CrossSouth", side="S", x0=2.25, x1=7.6, y=-10.0, G=-1.6, depth=8.0, floors=[3.4, 3.0],
             walls=("BrickRed", "ConcreteSide"), shop=dict(kind="restaurant", sign="ramen"),
             uppers=[dict(U, windows=2)]),
    ]


def all_buildings():
    return [street_building(c) for c in configs() + closing_configs()]
