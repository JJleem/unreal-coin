"""
Shared helpers of the stage rebuild pipeline (see README.md in this folder).

Coordinates are Unreal metres (X forward, Y right, Z up) after the stage scale correction, the same space
make_scan_collision.py and build_scan_stages.py use: UE = (z, x, -y) x metresPerUnit x stage_scale.json.
"""

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.normpath(os.path.join(HERE, ".."))
SCANS_DIR = os.path.normpath(os.path.join(SCRIPTS_DIR, "..", "..", "Scans"))
GENERATED_DIR = os.path.join(SCRIPTS_DIR, "generated")
CLEAN_DIR = os.path.normpath(os.path.join(SCRIPTS_DIR, "..", "SourceAssets", "CleanScans"))
OUT_DIR = os.path.normpath(os.path.join(SCRIPTS_DIR, "..", "SourceAssets", "Rebuilt"))
SCALES = {k: v for k, v in json.load(open(os.path.join(SCRIPTS_DIR, "stage_scale.json"), encoding="utf-8")).items() if not k.startswith("_")}
SH_C0 = 0.28209479177387814


def scan_folder(name):
    return next(d for d in os.listdir(SCANS_DIR) if d.endswith("_" + name))


def metres_per_unit(name):
    stage = json.load(open(os.path.join(SCANS_DIR, scan_folder(name), "stage.json"), encoding="utf-8"))
    return stage["metresPerUnit"] * SCALES.get(name, 1.0)


def read_ply(path):
    """Returns (header bytes, structured array). Reads in one go: np.fromfile has returned short reads on the WSL
    Windows mount."""
    with open(path, "rb") as f:
        header = b""
        while not header.endswith(b"end_header\n"):
            header += f.readline()
        lines = header.splitlines()
        names = [l.split()[-1].decode() for l in lines if l.startswith(b"property")]
        count = int(next(l for l in lines if l.startswith(b"element vertex")).split()[-1])
        dtype = np.dtype([(n, "<f4") for n in names])
        buffer = f.read(count * dtype.itemsize)
        if len(buffer) != count * dtype.itemsize:
            raise IOError(f"{path}: short read")
        return header, np.frombuffer(buffer, dtype=dtype).copy()


def write_ply(path, header, data):
    old = next(l for l in header.splitlines() if l.startswith(b"element vertex"))
    with open(path, "wb") as f:
        f.write(header.replace(old, b"element vertex %d" % len(data)))
        f.write(data.tobytes())


class Scan:
    """A scan in Unreal metres: positions, opacity, display colour and full 3D covariance per splat."""

    def __init__(self, name, cleaned=True):
        self.name = name
        self.mpu = metres_per_unit(name)
        path = os.path.join(CLEAN_DIR, f"{name}.ply")
        if not cleaned or not os.path.exists(path):
            path = os.path.join(SCANS_DIR, scan_folder(name), f"{name}.ply")
        self.path = path
        self.header, self.data = read_ply(path)
        d = self.data
        self.pos = np.stack([d["z"], d["x"], -d["y"]], 1).astype(np.float64) * self.mpu
        self.opacity = 1.0 / (1.0 + np.exp(-d["opacity"].astype(np.float64)))
        self.colour = np.clip(0.5 + SH_C0 * np.stack([d["f_dc_0"], d["f_dc_1"], d["f_dc_2"]], 1).astype(np.float64), 0.0, 1.0)
        self.scale = np.exp(np.stack([d["scale_0"], d["scale_1"], d["scale_2"]], 1).astype(np.float64)) * self.mpu

    def normals(self, index=None):
        """Unit axis of each splat's smallest scale in Unreal axes (the surface normal of flat splats), and how flat
        the splat is (smallest / middle scale)."""
        d = self.data if index is None else self.data[index]
        q = np.stack([d["rot_0"], d["rot_1"], d["rot_2"], d["rot_3"]], 1).astype(np.float64)
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        w, x, y, z = q.T
        rot = np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], 1),
                        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], 1),
                        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], 1)], 1)
        scale = self.scale if index is None else self.scale[index]
        order = np.argsort(scale, axis=1)
        smallest = rot[np.arange(len(rot)), :, order[:, 0]]
        normal = smallest[:, [2, 0, 1]] * np.array([1.0, 1.0, -1.0])
        flatness = np.take_along_axis(scale, order[:, :1], 1)[:, 0] / np.take_along_axis(scale, order[:, 1:2], 1)[:, 0]
        return normal, flatness

    def covariance(self, index=None):
        """3x3 covariance in Unreal axes (metres^2) for the given splats (all by default)."""
        d = self.data if index is None else self.data[index]
        q = np.stack([d["rot_0"], d["rot_1"], d["rot_2"], d["rot_3"]], 1).astype(np.float64)
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        w, x, y, z = q.T
        rot = np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], 1),
                        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], 1),
                        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], 1)], 1)
        scale2 = (self.scale if index is None else self.scale[index]) ** 2
        cov = np.einsum("nij,nj,nkj->nik", rot, scale2, rot)
        # PLY -> Unreal axes: UE x = ply z, UE y = ply x, UE z = -ply y
        m = np.array([[0, 0, 1], [1, 0, 0], [0, -1, 0]], float)
        return np.einsum("ij,njk,lk->nil", m, cov, m)


def load_collision(name):
    return json.load(open(os.path.join(GENERATED_DIR, f"{name}_collision.json")))


def ground_grid(collision, cell=0.5):
    """The collision floor as a grid: (lo xy, heights[nx, ny] in metres with NaN off the scan, wall mask)."""
    ground = np.array(collision["ground"]["vertices"]) / 100.0
    lo = ground[:, :2].min(0)
    corner = np.round((ground[:, :2] - lo) / cell).astype(int)
    shape = corner.max(0) + 1
    height = np.full(shape, np.nan)
    height[corner[:, 0], corner[:, 1]] = ground[:, 2]
    walls = np.zeros(shape, bool)
    for box in collision["walls"]:
        i0, j0 = np.floor((np.array(box[:2]) / 100.0 - lo) / cell + 0.01).astype(int)
        i1, j1 = np.ceil((np.array(box[3:5]) / 100.0 - lo) / cell - 0.01).astype(int)
        walls[max(i0, 0):max(i1, 0), max(j0, 0):max(j1, 0)] = True
    return lo, height, walls
