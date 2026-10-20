"""
Shared helpers for the Parking Tower reverse study (see README.md in this folder).

The source scan is a PlayCanvas / SuperSplat "compressed PLY" (written by ANNX AI EDITOR 1.9.0): splats are grouped in
chunks of 256, each chunk stores min/max of position, log scale and colour, and every splat stores 4 packed uint32
(position 11/10/11 bit, rotation 2+3x10 bit "smallest three", log scale 11/10/11 bit, RGBA 8 bit) plus 45 uint8 SH
coefficients (degree 3). decompress() turns it into the standard INRIA 3DGS float layout that OpenSplat4D imports.
"""

import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SRC_PLY = os.path.join(REPO, "parking-tower", "scene.compressed (2).ply")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "SourceAssets", "ParkingTower"))
RAW_PLY = os.path.join(OUT_DIR, "ParkingTower_raw.ply")
SHOTS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Saved", "ScanQuality", "ParkingTower_ReverseStudy"))
SH_C0 = 0.28209479177387814


def read_all(path):
    with open(path, "rb") as f:
        buf = f.read()   # one read: np.fromfile has returned short reads on the WSL Windows mount
    if len(buf) != os.path.getsize(path):
        raise IOError(f"{path}: short read")
    return buf


def parse_header(buf):
    end = buf.index(b"end_header\n") + len(b"end_header\n")
    elements = []
    for line in buf[:end].decode("ascii", "replace").splitlines():
        p = line.split()
        if p and p[0] == "element":
            elements.append([p[1], int(p[2]), []])
        elif p and p[0] == "property":
            elements[-1][2].append((p[-1], {"float": "<f4", "uint": "<u4", "uchar": "u1"}[p[1]]))
    return end, elements


def unorm(v, bits):
    return (v & ((1 << bits) - 1)).astype(np.float32) / float((1 << bits) - 1)


def decompress(path=SRC_PLY):
    """Returns a dict of standard 3DGS float arrays (PLY space) plus 'chunk' extents."""
    buf = read_all(path)
    off, elements = parse_header(buf)
    arrays = {}
    for name, count, props in elements:
        dt = np.dtype(props)
        arrays[name] = np.frombuffer(buf, dtype=dt, count=count, offset=off)
        off += count * dt.itemsize
    ch, v = arrays["chunk"], arrays["vertex"]
    n = len(v)
    ci = np.arange(n) // 256
    c = {k: ch[k][ci] for k in ch.dtype.names}
    lerp = lambda a, b, t: a + (b - a) * t
    pp = v["packed_position"]
    x = lerp(c["min_x"], c["max_x"], unorm(pp >> 21, 11))
    y = lerp(c["min_y"], c["max_y"], unorm(pp >> 11, 10))
    z = lerp(c["min_z"], c["max_z"], unorm(pp, 11))
    ps = v["packed_scale"]
    s0 = lerp(c["min_scale_x"], c["max_scale_x"], unorm(ps >> 21, 11))
    s1 = lerp(c["min_scale_y"], c["max_scale_y"], unorm(ps >> 11, 10))
    s2 = lerp(c["min_scale_z"], c["max_scale_z"], unorm(ps, 11))
    pr = v["packed_rotation"]
    norm = np.sqrt(2.0)
    a = (unorm(pr >> 20, 10) - 0.5) * norm
    b = (unorm(pr >> 10, 10) - 0.5) * norm
    cc = (unorm(pr, 10) - 0.5) * norm
    m = np.sqrt(np.clip(1.0 - (a * a + b * b + cc * cc), 0, None))
    largest = pr >> 30
    # quaternion with the largest component omitted ("smallest three")
    q = np.zeros((n, 4), np.float32)
    for i in range(4):
        sel = largest == i
        others = [k for k in range(4) if k != i]
        q[sel, i] = m[sel]
        q[sel, others[0]], q[sel, others[1]], q[sel, others[2]] = a[sel], b[sel], cc[sel]
    pc = v["packed_color"]
    r = lerp(c["min_r"], c["max_r"], unorm(pc >> 24, 8))
    g = lerp(c["min_g"], c["max_g"], unorm(pc >> 16, 8))
    bl = lerp(c["min_b"], c["max_b"], unorm(pc >> 8, 8))
    al = unorm(pc, 8)
    with np.errstate(divide="ignore"):
        opacity = np.where(al <= 0, -40.0, np.where(al >= 1, 40.0, -np.log(1.0 / np.clip(al, 1e-7, 1) - 1.0)))
    out = {"x": x, "y": y, "z": z, "f_dc_0": (r - 0.5) / SH_C0, "f_dc_1": (g - 0.5) / SH_C0, "f_dc_2": (bl - 0.5) / SH_C0,
           "opacity": opacity.astype(np.float32), "scale_0": s0, "scale_1": s1, "scale_2": s2,
           # the packed components are in PLY order (rot_0 = w, rot_1..3 = x, y, z), as SuperSplat packs
           # rot_0..rot_3 (checked: the (x, y, z, w) reading draws needle artifacts the thumbnail doesn't have)
           "rot_0": q[:, 0], "rot_1": q[:, 1], "rot_2": q[:, 2], "rot_3": q[:, 3]}
    if "sh" in arrays:
        sh = arrays["sh"]
        for k in sh.dtype.names:
            u = sh[k].astype(np.float32)
            nrm = np.where(u == 0, 0.0, (u + 0.5) / 256.0)
            out[k] = ((nrm - 0.5) * 8.0).astype(np.float32)
    out["_chunks"] = ch
    return out


def write_standard_ply(path, d):
    rest = sorted((k for k in d if k.startswith("f_rest_")), key=lambda k: int(k[7:]))
    names = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2"] + rest + \
            ["opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    n = len(d["x"])
    arr = np.zeros(n, dtype=[(k, "<f4") for k in names])
    for k in names:
        if k in d:
            arr[k] = d[k]
    header = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % n + \
             "".join(f"property float {k}\n" for k in names) + "end_header\n"
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(arr.tobytes())
    return arr


def load_columns(path, cols):
    """Reads only some float columns of a standard PLY (memory mapped, then copied), returns {name: array}."""
    with open(path, "rb") as f:
        head = b""
        while not head.endswith(b"end_header\n"):
            head += f.readline()
    lines = head.splitlines()
    names = [l.split()[-1].decode() for l in lines if l.startswith(b"property")]
    count = int(next(l for l in lines if l.startswith(b"element vertex")).split()[-1])
    mm = np.memmap(path, dtype=np.dtype([(n, "<f4") for n in names]), mode="r", offset=len(head), shape=(count,))
    out = {c: np.array(mm[c]) for c in cols}
    del mm
    return out
