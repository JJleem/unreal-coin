"""
Tiny mesh builder for the zone rebuild: boxes, quads and triangles with outward normals, per-material sections and
UVs in metres (planar projection per face), written as JSON for build_zone_level.py to turn into Static Meshes.

Coordinates are Unreal metres; the JSON is written in centimetres.
"""

import json

import numpy as np


class Mesh:
    def __init__(self, name, collision="none"):
        self.name = name
        self.collision = collision     # "none", "complex" (blocks the player) or "query" (traces only)
        self.sections = {}             # material -> {"p": [], "uv": [], "i": []}

    def _section(self, material):
        return self.sections.setdefault(material, {"p": [], "uv": [], "i": []})

    @staticmethod
    def _uv(p, n, uv_override=None):
        """Planar UV in metres: horizontal faces use (x, y), walls use (along the wall, -z)."""
        if uv_override is not None:
            return uv_override
        n = np.asarray(n, float)
        if abs(n[2]) > 0.7:
            return [p[0], p[1]]
        t = np.array([-n[1], n[0], 0.0])
        t /= max(np.linalg.norm(t), 1e-9)
        return [float(np.dot(p, t)), -p[2]]

    def triangle(self, a, b, c, outward, material, uvs=None):
        """One triangle facing `outward` (Unreal's front face normal is (c - a) x (b - a))."""
        a, b, c = (np.asarray(v, float) for v in (a, b, c))
        normal = np.cross(c - a, b - a)
        if np.dot(normal, outward) < 0:
            b, c = c, b
            if uvs is not None:
                uvs = [uvs[0], uvs[2], uvs[1]]
        s = self._section(material)
        base = len(s["p"])
        for k, v in enumerate((a, b, c)):
            s["p"].append(v.tolist())
            s["uv"].append(self._uv(v, outward, None if uvs is None else uvs[k]))
        s["i"] += [base, base + 1, base + 2]

    def quad(self, a, b, c, d, outward, material, uvs=None):
        """Quad a-b-c-d (in order around the edge)."""
        self.triangle(a, b, c, outward, material, None if uvs is None else [uvs[0], uvs[1], uvs[2]])
        self.triangle(a, c, d, outward, material, None if uvs is None else [uvs[0], uvs[2], uvs[3]])

    def box(self, x0, x1, y0, y1, z0, z1, material, skip=(), faces=None):
        """Axis aligned box. `faces` maps a face ("-X", "+X", "-Y", "+Y", "-Z", "+Z") to another material
        (or to (material, uvs) for an image mapped onto it); `skip` leaves faces out."""
        faces = faces or {}
        corners = {(i, j, k): (x1 if i else x0, y1 if j else y0, z1 if k else z0) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
        spec = {
            "-X": ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1), (-1, 0, 0)),
            "+X": ((1, 1, 0), (1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 0, 0)),
            "-Y": ((1, 0, 0), (0, 0, 0), (0, 0, 1), (1, 0, 1), (0, -1, 0)),
            "+Y": ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1), (0, 1, 0)),
            "-Z": ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, -1)),
            "+Z": ((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1), (0, 0, 1)),
        }
        for face, (a, b, c, d, n) in spec.items():
            if face in skip:
                continue
            m, uvs = material, None
            if face in faces:
                m = faces[face]
                if isinstance(m, tuple):
                    m, uvs = m
            # quads are listed as seen from outside, bottom left first: image uvs go (0,1) (1,1) (1,0) (0,0)
            self.quad(corners[a], corners[b], corners[c], corners[d], n, m, uvs)

    def beam(self, a, b, width, height, material, up=(0.0, 0.0, 1.0)):
        """A straight bar of rectangular section from point a to point b (rails, stringers, posts)."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        length = np.linalg.norm(d)
        if length < 1e-6:
            return
        d /= length
        side = np.cross(d, up)
        if np.linalg.norm(side) < 1e-6:
            side = np.cross(d, [1.0, 0.0, 0.0])
        side /= np.linalg.norm(side)
        top = np.cross(side, d)
        hw, hh = width / 2, height / 2
        corner = lambda p, s, t: p + side * s * hw + top * t * hh
        ring = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        for k in range(4):
            s0, t0 = ring[k]
            s1, t1 = ring[(k + 1) % 4]
            n = side * (s0 + s1) / 2 + top * (t0 + t1) / 2
            p0, p1 = corner(a, s0, t0), corner(a, s1, t1)
            q0, q1 = corner(b, s0, t0), corner(b, s1, t1)
            self.quad(p0, p1, q1, q0, n, material,
                      [[0, 0], [width, 0], [width, length], [0, length]])
        for end, n in ((a, -d), (b, d)):
            self.quad(*(corner(end, s, t) for s, t in ring), n, material)

    def cylinder(self, centre, radius, z0, z1, material, segments=16, cap=True):
        """Vertical cylinder (poles, tanks, cones with radius as (bottom, top))."""
        r0, r1 = (radius, radius) if np.isscalar(radius) else radius
        cx, cy = centre
        angles = np.linspace(0, 2 * np.pi, segments + 1)
        for k in range(segments):
            a0, a1 = angles[k], angles[k + 1]
            pa0 = [cx + r0 * np.cos(a0), cy + r0 * np.sin(a0), z0]
            pa1 = [cx + r0 * np.cos(a1), cy + r0 * np.sin(a1), z0]
            pb1 = [cx + r1 * np.cos(a1), cy + r1 * np.sin(a1), z1]
            pb0 = [cx + r1 * np.cos(a0), cy + r1 * np.sin(a0), z1]
            mid = (a0 + a1) / 2
            u0, u1 = a0 * max(r0, r1), a1 * max(r0, r1)
            self.quad(pa0, pa1, pb1, pb0, [np.cos(mid), np.sin(mid), (r0 - r1) / max(z1 - z0, 1e-6)], material,
                      [[u0, -z0], [u1, -z0], [u1, -z1], [u0, -z1]])
            if cap and r1 > 1e-4:
                self.triangle([cx, cy, z1], pb0, pb1, [0, 0, 1], material)

    def merge_grid(self, positions, uvs, triangles, material):
        """Adds an indexed mesh (shared vertices, so the normals come out smooth)."""
        s = self._section(material)
        base = len(s["p"])
        s["p"] += np.asarray(positions, float).tolist()
        s["uv"] += np.asarray(uvs, float).tolist()
        s["i"] += (np.asarray(triangles, int) + base).ravel().tolist()

    def to_json(self):
        return {"name": self.name, "collision": self.collision,
                "sections": [{"material": m, "positions": (np.array(s["p"]) * 100.0).round(2).tolist(),
                              "uvs": np.round(s["uv"], 4).tolist(), "indices": s["i"]}
                             for m, s in self.sections.items() if s["i"]]}


IMAGE_UVS = [[0, 1], [1, 1], [1, 0], [0, 0]]


def save(meshes, path):
    with open(path, "w") as f:
        json.dump([m.to_json() for m in meshes], f)
