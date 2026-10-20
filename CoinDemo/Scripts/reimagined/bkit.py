"""
Building kit for the reimagined Hongdae: facade modules that turn a measured facade line into real architecture
(walls with openings and reveals, framed windows with sills and grilles, aluminium shop fronts with doors, rooms behind
the glass, sign boxes, channel letters, blade signs, slab bands, pipes, cables, parapets), written into meshkit meshes.

A facade is a straight line from a to b in plan, as seen from the street: a on the viewer's left, b on the right.
Local coordinates: s along the facade from a (metres), z absolute height, d depth into the building (0 = the wall's
outer face, negative = in front of it). Unreal is left handed (X forward, Y right), so the outward normal of a facade
running along u is n = (-u.y, u.x).

Kit props (Poly Haven models) are not geometry: `Building.place()` records them for the Unreal level script, which
spawns them as Static Mesh actors aligned by their bounds.
"""

import os
import sys

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rebuild import meshkit  # noqa: E402

IMG = meshkit.IMAGE_UVS


class Facade:
    def __init__(self, a, b):
        self.a = np.asarray(a, float)
        self.b = np.asarray(b, float)
        self.length = float(np.linalg.norm(self.b - self.a))
        self.u = (self.b - self.a) / self.length
        self.n = np.array([-self.u[1], self.u[0]])
        self.U = np.array([self.u[0], self.u[1], 0.0])
        self.N = np.array([self.n[0], self.n[1], 0.0])

    def p(self, s, z, d=0.0):
        xy = self.a + self.u * s - self.n * d
        return [float(xy[0]), float(xy[1]), float(z)]

    def xy(self, s, d=0.0):
        return self.a + self.u * s - self.n * d

    def yaw(self):
        """Yaw (degrees) that turns a model's -Y front to face out of this facade."""
        return float(np.degrees(np.arctan2(self.n[1], self.n[0]))) + 90.0


def obox(m, F, s0, s1, z0, z1, d0, d1, mat, skip=(), faces=None):
    """Box in facade coordinates. Faces: front (out, d0 side), back, left (s0), right (s1), top, bottom.
    `faces` maps a face to another material or to (material, uvs) for an image seen from outside."""
    faces = faces or {}
    P = lambda s, z, d: F.p(s, z, d)
    U, N, Z = F.U, F.N, np.array([0.0, 0.0, 1.0])
    quads = {
        "front": ((s0, z0, d0), (s1, z0, d0), (s1, z1, d0), (s0, z1, d0), N),
        "back": ((s1, z0, d1), (s0, z0, d1), (s0, z1, d1), (s1, z1, d1), -N),
        "left": ((s0, z0, d1), (s0, z0, d0), (s0, z1, d0), (s0, z1, d1), -U),
        "right": ((s1, z0, d0), (s1, z0, d1), (s1, z1, d1), (s1, z1, d0), U),
        "top": ((s0, z1, d0), (s1, z1, d0), (s1, z1, d1), (s0, z1, d1), Z),
        "bottom": ((s0, z0, d1), (s1, z0, d1), (s1, z0, d0), (s0, z0, d0), -Z),
    }
    for name, (a, b, c, d, n) in quads.items():
        if name in skip:
            continue
        material, uvs = mat, None
        if name in faces:
            material = faces[name]
            if isinstance(material, tuple):
                material, uvs = material
        m.quad(P(*a), P(*b), P(*c), P(*d), n, material, uvs)


def tube(m, a, b, r, mat, segments=8):
    """Round bar from a to b (pipes, cables, rails)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    axis = b - a
    length = np.linalg.norm(axis)
    if length < 1e-6:
        return
    axis /= length
    side = np.cross(axis, [0, 0, 1.0]) if abs(axis[2]) < 0.95 else np.cross(axis, [1.0, 0, 0])
    side /= np.linalg.norm(side)
    up = np.cross(side, axis)
    angles = np.linspace(0, 2 * np.pi, segments + 1)
    for k in range(segments):
        c0, c1 = np.cos(angles[k]), np.cos(angles[k + 1])
        s0, s1 = np.sin(angles[k]), np.sin(angles[k + 1])
        o0, o1 = side * c0 + up * s0, side * c1 + up * s1
        mid = side * np.cos((angles[k] + angles[k + 1]) / 2) + up * np.sin((angles[k] + angles[k + 1]) / 2)
        u0, u1 = angles[k] * r, angles[k + 1] * r
        m.quad(a + o0 * r, a + o1 * r, b + o1 * r, b + o0 * r, mid, mat, [[u0, 0], [u1, 0], [u1, length], [u0, length]])


def polyline_tube(m, points, r, mat, segments=6):
    for p, q in zip(points[:-1], points[1:]):
        tube(m, p, q, r, mat, segments)


def cable(m, a, b, sag, r, mat, pieces=10):
    """Hanging cable between two points (catenary approximated by a parabola)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = np.linspace(0, 1, pieces + 1)
    points = a[None] + (b - a)[None] * t[:, None]
    points[:, 2] -= sag * 4 * t * (1 - t)
    polyline_tube(m, points, r, mat, 5)


def cap(m, polygon, z, normal_up, mat):
    """Flat horizontal polygon (roofs, slabs), triangulated with its holes."""
    for tri in shapely.constrained_delaunay_triangles(polygon).geoms:
        c = np.asarray(tri.exterior.coords)[:3]
        m.triangle([c[0][0], c[0][1], z], [c[1][0], c[1][1], z], [c[2][0], c[2][1], z], [0, 0, 1 if normal_up else -1], mat)


# ---------------------------------------------------------------------------------------------------------------- walls

def wall(m, F, s0, s1, z0, z1, openings, mat, thickness=0.25, reveal_mat=None, ends=False):
    """Wall face from s0 to s1, z0 to z1 with rectangular openings (s0, s1, z0, z1) cut through it; the reveals (jambs,
    head, sill) run the wall's thickness, so windows sit in real depth."""
    reveal_mat = reveal_mat or mat
    openings = [o for o in openings if o[1] > s0 and o[0] < s1 and o[3] > z0 and o[2] < z1]
    ss = sorted({s0, s1} | {min(max(v, s0), s1) for o in openings for v in o[:2]})
    zs = sorted({z0, z1} | {min(max(v, z0), z1) for o in openings for v in o[2:]})
    for za, zb in zip(zs[:-1], zs[1:]):
        zc = (za + zb) / 2
        run = None
        for sa, sb in zip(ss[:-1], ss[1:]):
            sc = (sa + sb) / 2
            solid = not any(o[0] < sc < o[1] and o[2] < zc < o[3] for o in openings)
            if solid:
                run = [run[0], sb] if run else [sa, sb]
            elif run:
                m.quad(F.p(run[0], za), F.p(run[1], za), F.p(run[1], zb), F.p(run[0], zb), F.N, mat)
                run = None
        if run:
            m.quad(F.p(run[0], za), F.p(run[1], za), F.p(run[1], zb), F.p(run[0], zb), F.N, mat)
    t = thickness
    for o0, o1, oz0, oz1 in openings:
        m.quad(F.p(o0, oz0, 0), F.p(o0, oz0, t), F.p(o0, oz1, t), F.p(o0, oz1, 0), F.U, reveal_mat)
        m.quad(F.p(o1, oz0, t), F.p(o1, oz0, 0), F.p(o1, oz1, 0), F.p(o1, oz1, t), -F.U, reveal_mat)
        m.quad(F.p(o0, oz1, 0), F.p(o1, oz1, 0), F.p(o1, oz1, t), F.p(o0, oz1, t), [0, 0, -1], reveal_mat)
        m.quad(F.p(o0, oz0, t), F.p(o1, oz0, t), F.p(o1, oz0, 0), F.p(o0, oz0, 0), [0, 0, 1], reveal_mat)
    if ends:
        obox(m, F, s0, s1, z0, z1, 0, t, mat, skip=("front", "back", "top", "bottom"))


def band(m, F, s0, s1, z0, z1, protrude, mat, ends=True):
    """Slab edge, cornice or plinth: a strip standing proud of the wall."""
    obox(m, F, s0, s1, z0, z1, -protrude, 0.0, mat, skip=("back",) if ends else ("back", "left", "right"))


# -------------------------------------------------------------------------------------------------------------- windows

def window(m, F, s0, s1, z0, z1, depth=0.12, style="slider", frame="WinFrame", glass="Glass", sill="Sill", grille=None,
           transom=None):
    """Window set `depth` into its opening. Styles: "slider" (Korean aluminium sliding sashes, two overlapping leaves),
    "fixed" (one pane), "grid" (fixed with mullions every ~0.7 m), "casement" (two leaves, middle mullion).
    `transom` (height from the bottom) adds a fixed top light. `grille` = material of a steel security grille."""
    fw, fd = 0.05, 0.07
    d = depth
    # outer frame
    obox(m, F, s0, s1, z1 - fw, z1, d, d + fd, frame, skip=("back",))
    obox(m, F, s0, s1, z0, z0 + fw, d, d + fd, frame, skip=("back",))
    obox(m, F, s0, s0 + fw, z0 + fw, z1 - fw, d, d + fd, frame, skip=("back", "top", "bottom"))
    obox(m, F, s1 - fw, s1, z0 + fw, z1 - fw, d, d + fd, frame, skip=("back", "top", "bottom"))
    top = z1 - fw
    if transom:
        zt = z0 + transom
        obox(m, F, s0 + fw, s1 - fw, zt - 0.025, zt + 0.025, d, d + fd, frame, skip=("back",))
        m.quad(F.p(s0 + fw, zt + 0.025, d + 0.035), F.p(s1 - fw, zt + 0.025, d + 0.035), F.p(s1 - fw, top, d + 0.035),
               F.p(s0 + fw, top, d + 0.035), F.N, glass)
        top = zt - 0.025
    inner0, inner1, bottom = s0 + fw, s1 - fw, z0 + fw
    if style == "slider":
        # two sashes, the right one in front, overlapping by 6 cm in the middle
        mid = (inner0 + inner1) / 2
        for a, b, dd in ((inner0, mid + 0.03, d + 0.045), (mid - 0.03, inner1, d + 0.015)):
            sw = 0.04
            obox(m, F, a, b, top - sw, top, dd, dd + 0.025, frame, skip=("back",))
            obox(m, F, a, b, bottom, bottom + sw, dd, dd + 0.025, frame, skip=("back",))
            obox(m, F, a, a + sw, bottom + sw, top - sw, dd, dd + 0.025, frame, skip=("back", "top", "bottom"))
            obox(m, F, b - sw, b, bottom + sw, top - sw, dd, dd + 0.025, frame, skip=("back", "top", "bottom"))
            m.quad(F.p(a + sw, bottom + sw, dd + 0.012), F.p(b - sw, bottom + sw, dd + 0.012), F.p(b - sw, top - sw, dd + 0.012),
                   F.p(a + sw, top - sw, dd + 0.012), F.N, glass)
    else:
        if style == "grid":
            k = max(1, int(round((inner1 - inner0) / 0.7)))
            cuts = list(np.linspace(inner0, inner1, k + 1)[1:-1])
        elif style == "casement":
            cuts = [(inner0 + inner1) / 2]
        else:
            cuts = []
        for c in cuts:
            obox(m, F, c - 0.025, c + 0.025, bottom, top, d, d + fd, frame, skip=("back", "top", "bottom"))
        m.quad(F.p(inner0, bottom, d + 0.035), F.p(inner1, bottom, d + 0.035), F.p(inner1, top, d + 0.035),
               F.p(inner0, top, d + 0.035), F.N, glass)
    # sill: stone or metal, standing 5 cm proud, with a drip edge
    if sill:
        obox(m, F, s0 - 0.04, s1 + 0.04, z0 - 0.05, z0, -0.06, d, sill, skip=("back",))
    if grille:
        security_grille(m, F, s0, s1, z0, z1, grille)


def security_grille(m, F, s0, s1, z0, z1, mat, d=-0.09):
    """Korean 방범창: a painted steel frame with vertical bars every 11 cm and two rails, bolted proud of the wall."""
    obox(m, F, s0 - 0.03, s1 + 0.03, z1, z1 + 0.025, d, d + 0.02, mat)
    obox(m, F, s0 - 0.03, s1 + 0.03, z0 - 0.025, z0, d, d + 0.02, mat)
    obox(m, F, s0 - 0.03, s0 - 0.005, z0, z1, d, d + 0.02, mat)
    obox(m, F, s1 + 0.005, s1 + 0.03, z0, z1, d, d + 0.02, mat)
    for z in (z0 + (z1 - z0) * 0.33, z0 + (z1 - z0) * 0.66):
        obox(m, F, s0, s1, z - 0.01, z + 0.01, d, d + 0.015, mat, skip=("back",))
    for s in np.arange(s0 + 0.08, s1 - 0.04, 0.11):
        tube(m, F.p(s, z0, d + 0.01), F.p(s, z1, d + 0.01), 0.007, mat, 5)
    for s, z in ((s0 - 0.02, z0 + 0.1), (s1 + 0.02, z0 + 0.1), (s0 - 0.02, z1 - 0.1), (s1 + 0.02, z1 - 0.1)):
        obox(m, F, s - 0.015, s + 0.015, z - 0.02, z + 0.02, d + 0.02, 0.0, mat, skip=("back",))


def blinds(m, F, s0, s1, z_top, drop, d, mat):
    """Interior roller blind or vertical blind pulled partly down behind the glass."""
    m.quad(F.p(s0, z_top - drop, d), F.p(s1, z_top - drop, d), F.p(s1, z_top, d), F.p(s0, z_top, d), F.N, mat)
    obox(m, F, s0, s1, z_top - drop - 0.03, z_top - drop, d - 0.01, d + 0.01, mat)


def room(m, F, s0, s1, z0, z1, d0, depth, wall="RoomWall", floor="RoomFloor", ceiling="RoomCeiling", light="RoomLight",
         lights=True, spacing=1.6):
    """The room seen through the glass: floor, ceiling, back and side walls, and ceiling light panels."""
    d1 = d0 + depth
    # rooms of two facades of a corner overlap: lift each a hair by its facade so their floors don't z-fight
    z0 += (abs(F.a[0] * 13.7 + F.a[1] * 7.1) % 1.0) * 0.006
    z1 -= (abs(F.a[0] * 5.3 + F.a[1] * 11.9) % 1.0) * 0.006
    m.quad(F.p(s0, z0, d0), F.p(s1, z0, d0), F.p(s1, z0, d1), F.p(s0, z0, d1), [0, 0, 1], floor)
    m.quad(F.p(s0, z1, d1), F.p(s1, z1, d1), F.p(s1, z1, d0), F.p(s0, z1, d0), [0, 0, -1], ceiling)
    m.quad(F.p(s0, z0, d1), F.p(s1, z0, d1), F.p(s1, z1, d1), F.p(s0, z1, d1), F.N, wall)
    m.quad(F.p(s0, z0, d1), F.p(s0, z0, d0), F.p(s0, z1, d0), F.p(s0, z1, d1), F.U, wall)
    m.quad(F.p(s1, z0, d0), F.p(s1, z0, d1), F.p(s1, z1, d1), F.p(s1, z1, d0), -F.U, wall)
    if lights:
        for s in np.arange(s0 + spacing / 2, s1, spacing):
            for d in np.arange(d0 + 0.9, d1 - 0.4, 1.8):
                obox(m, F, s - 0.3, s + 0.3, z1 - 0.03, z1, d - 0.3, d + 0.3, light, skip=("top",))


# ---------------------------------------------------------------------------------------------------------- shop fronts

def storefront(m, F, s0, s1, z0, z1, doors=(), depth=0.18, frame="Alu", glass="Glass", transom=2.35, bay=1.25,
               kick="Alu", handle="Stainless"):
    """Aluminium shop front in an opening: posts every `bay`, a transom with top lights, glass doors with pull
    handles and kick plates. `doors` lists (s_start, width, leaves)."""
    fw, fd = 0.06, 0.12
    d = depth
    zt = min(z0 + transom, z1 - 0.3)
    obox(m, F, s0, s1, z1 - fw, z1, d, d + fd, frame, skip=("back",))
    obox(m, F, s0, s1, z0, z0 + 0.04, d - 0.02, d + fd, frame, skip=("back",))
    obox(m, F, s0, s1, zt - 0.04, zt + 0.04, d, d + fd, frame, skip=("back",))
    door_spans = [(ds, ds + w) for ds, w, _ in doors]
    posts = {s0 + fw / 2, s1 - fw / 2}
    for a, b in door_spans:
        posts |= {a - fw / 2, b + fw / 2}
    # posts between doors: evenly divide each fixed stretch
    edges = sorted([s0] + [v for span in door_spans for v in span] + [s1])
    for a, b in zip(edges[::2], edges[1::2]):
        k = max(1, int(round((b - a) / bay)))
        posts |= set(np.linspace(a, b, k + 1)[1:-1].tolist())
    for p in sorted(posts):
        obox(m, F, p - fw / 2, p + fw / 2, z0 + 0.04, z1 - fw, d, d + fd, frame, skip=("back", "top", "bottom"))
    # glass: fixed panes below the transom outside the doors, top lights above
    m.quad(F.p(s0, zt + 0.04, d + 0.06), F.p(s1, zt + 0.04, d + 0.06), F.p(s1, z1 - fw, d + 0.06), F.p(s0, z1 - fw, d + 0.06), F.N, glass)
    for a, b in zip(edges[::2], edges[1::2]):
        if b - a > 0.05:
            m.quad(F.p(a, z0 + 0.04, d + 0.06), F.p(b, z0 + 0.04, d + 0.06), F.p(b, zt - 0.04, d + 0.06), F.p(a, zt - 0.04, d + 0.06), F.N, glass)
            obox(m, F, a, b, z0 + 0.04, z0 + 0.12, d + 0.02, d + 0.06, kick, skip=("back",))
    for ds, w, leaves in doors:
        leaf = w / leaves
        for k in range(leaves):
            a, b = ds + k * leaf, ds + (k + 1) * leaf
            dd = d + 0.03
            obox(m, F, a, b, zt - 0.04 - 0.1, zt - 0.04, dd, dd + 0.05, frame, skip=("back",))
            obox(m, F, a, b, z0 + 0.04, z0 + 0.22, dd, dd + 0.05, kick, skip=("back",))
            obox(m, F, a, a + 0.06, z0 + 0.22, zt - 0.14, dd, dd + 0.05, frame, skip=("back", "top", "bottom"))
            obox(m, F, b - 0.06, b, z0 + 0.22, zt - 0.14, dd, dd + 0.05, frame, skip=("back", "top", "bottom"))
            m.quad(F.p(a + 0.06, z0 + 0.22, dd + 0.025), F.p(b - 0.06, z0 + 0.22, dd + 0.025), F.p(b - 0.06, zt - 0.14, dd + 0.025),
                   F.p(a + 0.06, zt - 0.14, dd + 0.025), F.N, glass)
            # vertical pull handle on the meeting side, stood off the glass on two arms
            hs = b - 0.16 if (leaves == 1 or k == 0) else a + 0.16
            z_mid = z0 + 1.05
            tube(m, F.p(hs, z_mid - 0.4, dd - 0.07), F.p(hs, z_mid + 0.4, dd - 0.07), 0.016, handle, 8)
            for zz in (z_mid - 0.3, z_mid + 0.3):
                tube(m, F.p(hs, zz, dd - 0.07), F.p(hs, zz, dd), 0.009, handle, 6)
    # threshold
    obox(m, F, s0, s1, z0 - 0.02, z0 + 0.01, -0.05, d + fd, "Stainless", skip=("back",))


def shutter_box(m, F, s0, s1, z0, z1, mat="Alu"):
    """Roller shutter housing above a shop front (most Korean shops close with one at night)."""
    obox(m, F, s0, s1, z0, z1, -0.24, 0.0, mat, skip=("back",))
    for s in (s0 + 0.02, s1 - 0.06):
        obox(m, F, s, s + 0.04, z0 - 2.0, z0, -0.08, 0.0, mat, skip=("back",))


# ---------------------------------------------------------------------------------------------------------------- signs

def sign_box(m, F, s0, s1, z0, z1, face, depth=0.2, frame="SignFrame", lip=0.03, d=0.0):
    """Light box sign: a `depth` deep box on the wall, its face an image (`face` material), framed by a lip."""
    obox(m, F, s0, s1, z0, z1, d - depth, d, frame, skip=("back",), faces={"front": (face, IMG)})
    for a, b, c, e in ((s0 - lip, s1 + lip, z1, z1 + lip), (s0 - lip, s1 + lip, z0 - lip, z0)):
        obox(m, F, a, b, c, e, d - depth - 0.015, d, frame, skip=("back",))
    obox(m, F, s0 - lip, s0, z0, z1, d - depth - 0.015, d, frame, skip=("back", "top", "bottom"))
    obox(m, F, s1, s1 + lip, z0, z1, d - depth - 0.015, d, frame, skip=("back", "top", "bottom"))


def blade_sign(m, F, s, z0, z1, faces, out0=0.12, width=0.62, thickness=0.2, frame="SignFrame"):
    """Projecting vertical sign (돌출 간판) at s, standing out of the wall from out0 to out0 + width, with brackets.
    `faces` = (material seen from the +u side, material seen from the -u side)."""
    a, b = -(out0 + width), -out0
    # +u face: its viewer's right is into the wall, so the image's left edge is the outer end
    obox(m, F, s - thickness / 2, s + thickness / 2, z0, z1, a, b, frame, skip=(),
         faces={"right": (faces[0], [[0, 1], [1, 1], [1, 0], [0, 0]]), "left": (faces[1], [[0, 1], [1, 1], [1, 0], [0, 0]])})
    for z in (z0 + 0.15, z1 - 0.15):
        obox(m, F, s - 0.02, s + 0.02, z - 0.02, z + 0.02, b, 0.0, frame)
        obox(m, F, s - 0.06, s + 0.06, z - 0.08, z + 0.08, -0.01, 0.0, frame)


def glyph_polygons(text, font_path, px=360):
    """Outlines of `text` in the font as shapely polygons in em units (height of a capital ~ 1), from a high
    resolution rendering (contours of the coverage mask)."""
    from PIL import Image, ImageDraw, ImageFont
    from skimage import measure

    font = ImageFont.truetype(font_path, px)
    left, top, right, bottom = font.getbbox(text)
    w, h = right - left + 40, bottom - top + 40
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((20 - left, 20 - top), text, font=font, fill=255)
    mask = np.asarray(im, float) / 255.0
    contours = measure.find_contours(np.pad(mask, 1), 0.5)
    rings = []
    for c in contours:
        if len(c) < 8:
            continue
        pts = np.column_stack([c[:, 1] - 1, (h - (c[:, 0] - 1))]) / px
        poly = Polygon(pts).buffer(0)
        if poly.area > 1e-5:
            rings.append(poly.simplify(0.004))
    # nest: a ring inside an odd number of larger rings is a hole of the smallest of them
    rings.sort(key=lambda p: -p.area)
    depth, parent = [], []
    for i, r in enumerate(rings):
        inside = [j for j in range(i) if rings[j].contains(r.representative_point())]
        depth.append(len(inside))
        parent.append(inside[-1] if inside else None)
    polys = []
    for i, r in enumerate(rings):
        if depth[i] % 2:
            continue
        p = r
        for j, hole in enumerate(rings):
            if parent[j] == i and depth[j] % 2:
                p = p.difference(hole)
        polys += list(getattr(p, "geoms", [p]))
    height = (bottom - top) / px
    return [orient(p, 1.0) for p in polys if p.area > 1e-5], (right - left) / px, height


def letters(m, F, text, font_path, s_center, z0, height, depth, d_back, face, side, align="center"):
    """Channel letters: each glyph extruded `depth` out of the surface at d_back, faces and returns separate
    materials (the face usually lit). Text height `height` metres (bounding box of the string)."""
    polys, width, h = glyph_polygons(text, font_path)
    k = height / h
    s_left = s_center - width * k / 2 if align == "center" else s_center
    d0, d1 = d_back - depth, d_back
    for poly in polys:
        to = lambda x, y, d: F.p(s_left + x * k, z0 + y * k, d)
        for tri in shapely.constrained_delaunay_triangles(poly).geoms:
            c = np.asarray(tri.exterior.coords)[:3]
            m.triangle(to(*c[0], d0), to(*c[1], d0), to(*c[2], d0), F.N, face,
                       [[x, -y] for x, y in c])
        for ring in [poly.exterior] + list(poly.interiors):
            pts = np.asarray(ring.coords)
            for p, q in zip(pts[:-1], pts[1:]):
                e = q - p
                # exterior rings run counter clockwise (orient 1.0), holes clockwise: the outward side is to the right
                normal2 = np.array([e[1], -e[0]])
                outward = F.U * normal2[0] + np.array([0, 0, 1.0]) * normal2[1]
                m.quad(to(*p, d0), to(*q, d0), to(*q, d1), to(*p, d1), outward, side)


# --------------------------------------------------------------------------------------------------------- services

def downpipe(m, F, s, z0, z1, mat="Pipe", r=0.045, off=0.08):
    """Rain water downpipe with wall brackets every 1.5 m and a shoe at the bottom."""
    c0, c1 = F.p(s, z0 + 0.15, -off), F.p(s, z1, -off)
    tube(m, c0, c1, r, mat, 10)
    tube(m, F.p(s, z0 + 0.15, -off), F.xy(s, -off - 0.18).tolist() + [z0 + 0.03], r, mat, 10)
    for z in np.arange(z0 + 0.8, z1, 1.5):
        obox(m, F, s - r - 0.01, s + r + 0.01, z - 0.02, z + 0.02, -off - r - 0.01, 0.0, mat)


def gas_pipe(m, F, points, mat="GasPipe", r=0.022, off=0.06):
    """The yellow gas pipe that runs over most Korean facades: (s, z) points along the wall, with clips."""
    pts = [F.p(s, z, -off) for s, z in points]
    polyline_tube(m, pts, r, mat, 8)
    for (s, z), (s2, z2) in zip(points[:-1], points[1:]):
        n = max(1, int(np.hypot(s2 - s, z2 - z) / 0.9))
        for t in np.linspace(0, 1, n + 1)[1:-1]:
            ss, zz = s + (s2 - s) * t, z + (z2 - z) * t
            obox(m, F, ss - 0.015, ss + 0.015, zz - 0.03, zz + 0.03, -off, 0.0, "Steel")


def conduit_bundle(m, F, s0, s1, z, mat="Cable", count=3, off=0.05):
    """Cables clipped along a wall (telecom lines entering a building)."""
    for k in range(count):
        tube(m, F.p(s0, z + k * 0.03, -off - 0.01 * k), F.p(s1, z + k * 0.03, -off - 0.01 * k), 0.008, mat, 5)


# ------------------------------------------------------------------------------------------------------------- roofs

def parapet(m, F, s0, s1, z, height, mat, coping="Coping", t=0.2):
    obox(m, F, s0, s1, z, z + height, 0.0, t, mat, skip=("bottom",))
    obox(m, F, s0 - 0.03, s1 + 0.03, z + height, z + height + 0.05, -0.04, t + 0.04, coping)


def railing(m, F, s0, s1, z, height=1.0, mat="Rail", d=-0.05, post=1.2, bars=0.12):
    """Steel railing: top rail, bottom rail, posts and balusters."""
    tube(m, F.p(s0, z + height, d), F.p(s1, z + height, d), 0.025, mat, 8)
    tube(m, F.p(s0, z + 0.1, d), F.p(s1, z + 0.1, d), 0.015, mat, 6)
    for s in np.arange(s0, s1 + 1e-6, (s1 - s0) / max(1, round((s1 - s0) / post))):
        tube(m, F.p(s, z, d), F.p(s, z + height, d), 0.022, mat, 8)
    for s in np.arange(s0 + bars, s1, bars):
        tube(m, F.p(s, z + 0.1, d), F.p(s, z + height, d), 0.008, mat, 5)


# ------------------------------------------------------------------------------------------------------- shop fit-out

PRODUCTS = ["ProductA", "ProductB", "ProductC", "ProductD", "ProductE", "ProductF"]


def display_wall(m, F, s0, s1, z0, d_back, rng, height=2.2, shelf=0.36, depth=0.32, small=False):
    """Shop wall unit against the back wall: a back panel, shelves every `shelf` m and products in mixed colours and
    sizes (shoe boxes, folded clothes, or small items such as glasses with `small`)."""
    obox(m, F, s0, s1, z0, z0 + height, d_back - 0.03, d_back, "ShopPanel", skip=("back",))
    for z in np.arange(z0 + 0.25, z0 + height - 0.1, shelf):
        obox(m, F, s0, s1, z - 0.02, z, d_back - depth, d_back - 0.03, "ShopShelf", skip=("back",))
        s = s0 + 0.05
        while s < s1 - 0.1:
            w = rng.uniform(0.05, 0.1) if small else rng.uniform(0.18, 0.34)
            h = rng.uniform(0.03, 0.06) if small else rng.uniform(0.1, min(0.3, shelf - 0.05))
            dd = rng.uniform(0.04, 0.08) if small else rng.uniform(0.18, depth - 0.04)
            if rng.random() < 0.85 and s + w < s1 - 0.03:
                obox(m, F, s, s + w, z, z + h, d_back - 0.03 - dd - (0.1 if small else 0.0), d_back - 0.03 - (0.1 if small else 0.0),
                     PRODUCTS[rng.integers(len(PRODUCTS))], skip=("back", "bottom"))
            s += w + (rng.uniform(0.06, 0.12) if small else rng.uniform(0.01, 0.05))
    obox(m, F, s0, s1, z0 + height - 0.12, z0 + height, d_back - depth - 0.02, d_back, "ShopPanel", skip=("back",))


def clothes_rack(m, F, s0, s1, z0, d, rng):
    """Garment rail: two posts, a rail and 10-16 garments hung across it in mixed colours."""
    top = z0 + 1.45
    for s in (s0, s1):
        tube(m, F.p(s, z0, d), F.p(s, top, d), 0.015, "Stainless", 6)
        obox(m, F, s - 0.2, s + 0.2, z0, z0 + 0.03, d - 0.03, d + 0.03, "Stainless")
    tube(m, F.p(s0, top, d), F.p(s1, top, d), 0.013, "Stainless", 6)
    s = s0 + 0.06
    while s < s1 - 0.06:
        length = rng.uniform(0.6, 1.0)
        obox(m, F, s, s + 0.035, top - 0.04 - length, top - 0.04, d - 0.24, d + 0.24, PRODUCTS[rng.integers(len(PRODUCTS))])
        s += rng.uniform(0.06, 0.1)


def table_display(m, F, s0, s1, z0, d0, d1, rng):
    """Low display table with stacks of folded clothes."""
    obox(m, F, s0, s1, z0, z0 + 0.75, d0, d1, "Counter", skip=("bottom",))
    for k in range(int((s1 - s0) / 0.32)):
        a = s0 + 0.05 + k * 0.32
        for j in range(2):
            dd = d0 + 0.08 + j * (d1 - d0) / 2
            top = z0 + 0.75 + rng.integers(2, 6) * 0.03
            obox(m, F, a, a + 0.26, z0 + 0.75, top, dd, dd + (d1 - d0) / 2 - 0.12, PRODUCTS[rng.integers(len(PRODUCTS))], skip=("bottom",))


# ------------------------------------------------------------------------------------------------------------ building

class Building:
    """Collects one building's meshes (one mesh per material group is unnecessary: meshkit keeps sections per
    material), its kit props, the footprint for splat removal and the facades for reporting."""

    def __init__(self, name, footprint, ground, top):
        self.name = name
        self.footprint = Polygon(footprint)
        self.ground = ground
        self.top = top
        self.shell = meshkit.Mesh(f"SM_{name}", collision="complex")      # walls, floors, roof: the player collides
        self.detail = meshkit.Mesh(f"SM_{name}_Detail", collision="none")  # windows, signs, pipes, interiors
        self.props = []

    def place(self, model, xy, z, yaw=0.0, scale=1.0, anchor="bottom", collision=False):
        """Kit model at plan position xy, its bounds' bottom (or centre, anchor="centre") at height z."""
        self.props.append({"model": model, "x": float(xy[0]), "y": float(xy[1]), "z": float(z), "yaw": float(yaw),
                           "scale": float(scale), "anchor": anchor, "collision": collision})

    def meshes(self):
        return [self.shell, self.detail]
