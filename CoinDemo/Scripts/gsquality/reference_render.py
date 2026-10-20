"""
Reference renderer: draws a scan PLY with the standard 3D Gaussian Splatting algorithm (INRIA: EWA projection with
the 0.3 px low-pass, 3 sigma footprint, per pixel front-to-back alpha compositing, alpha clamped to 0.99 and dropped
below 1/255, view dependent colour from the spherical harmonics) from exactly the camera of a DevCapture view, so
its output can be laid next to the Unreal screenshot of the same view.

The rasterizer follows sky-clean-lab/py/render/gsrender.py (plain PyTorch, tile based), extended with spherical
harmonics up to degree 3 and Unreal camera conversion. It is a reimplementation of the reference algorithm, not the
official CUDA rasterizer.

  python reference_render.py <ply> <out.png> x y z yaw pitch [width height hfov]
  (x, y, z in Unreal cm, yaw/pitch in degrees, as in DevCapture -Views=...,cam)
"""

import math
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), ".."))
from rebuild.common import metres_per_unit, read_ply  # noqa: E402

TILE = 16
SH_SIGN = 1.0   # -1 flips the view direction fed to the SH (to test a renderer's convention)
SH_DEGREE = None  # override the scan's degree (e.g. 0 = view independent colour)
C0 = 0.28209479177387814
C1 = 0.4886025119029199
C2 = (1.0925484305920792, -1.0925484305920792, 0.31539156525252005, -1.0925484305920792, 0.5462742152960396)
C3 = (-0.5900435899266435, 2.890611442640554, -0.4570457994644658, 0.3731763325901154, -0.4570457994644658,
      1.445305721320277, -0.5900435899266435)


def sh_colour(d, sh, degree):
    """sh: (n, 3, k) coefficients incl. DC, d: (n, 3) unit directions camera -> splat (PLY space)."""
    x, y, z = d[:, 0:1], d[:, 1:2], d[:, 2:3]
    c = C0 * sh[:, :, 0]
    if degree >= 1:
        c = c - C1 * y * sh[:, :, 1] + C1 * z * sh[:, :, 2] - C1 * x * sh[:, :, 3]
    if degree >= 2:
        xx, yy, zz, xy, yz, xz = x * x, y * y, z * z, x * y, y * z, x * z
        c = (c + C2[0] * xy * sh[:, :, 4] + C2[1] * yz * sh[:, :, 5] + C2[2] * (2 * zz - xx - yy) * sh[:, :, 6]
             + C2[3] * xz * sh[:, :, 7] + C2[4] * (xx - yy) * sh[:, :, 8])
    if degree >= 3:
        c = (c + C3[0] * y * (3 * xx - yy) * sh[:, :, 9] + C3[1] * xy * z * sh[:, :, 10] + C3[2] * y * (4 * zz - xx - yy) * sh[:, :, 11]
             + C3[3] * z * (2 * zz - 3 * xx - 3 * yy) * sh[:, :, 12] + C3[4] * x * (4 * zz - xx - yy) * sh[:, :, 13]
             + C3[5] * z * (xx - yy) * sh[:, :, 14] + C3[6] * x * (xx - 3 * yy) * sh[:, :, 15])
    return torch.clamp(c + 0.5, min=0.0)


def load(path, device="cuda"):
    _, d = read_ply(path)
    names = d.dtype.names
    rest = sorted((n for n in names if n.startswith("f_rest_")), key=lambda n: int(n[7:]))
    k = len(rest) // 3 + 1
    degree = {1: 0, 4: 1, 9: 2, 16: 3}[k]
    f = lambda *cols: torch.from_numpy(np.stack([d[c] for c in cols], 1).astype(np.float32)).to(device)
    sh = torch.zeros(len(d), 3, k, device=device)
    sh[:, :, 0] = f("f_dc_0", "f_dc_1", "f_dc_2")
    if rest:
        # PLY stores the higher coefficients channel-major: R1..Rk-1, G1..Gk-1, B1..Bk-1
        sh[:, :, 1:] = f(*rest).view(len(d), 3, k - 1)
    return {"pos": f("x", "y", "z"), "scl": torch.exp(f("scale_0", "scale_1", "scale_2")), "rot": f("rot_0", "rot_1", "rot_2", "rot_3"),
            "alpha": torch.sigmoid(f("opacity"))[:, 0], "sh": sh, "degree": degree, "n": len(d)}


def cov3d(scl, rot):
    w, x, y, z = rot.unbind(1)   # PLY quaternions are (w, x, y, z)
    nrm = torch.rsqrt(w * w + x * x + y * y + z * z + 1e-12)
    w, x, y, z = w * nrm, x * nrm, y * nrm, z * nrm
    R = torch.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y),
                     2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
                     2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], 1).view(-1, 3, 3)
    M = R * scl[:, None, :]
    return M @ M.transpose(1, 2)


def ue_camera(x, y, z, yaw, pitch, mpu):
    """Unreal camera (cm, degrees) -> PLY space eye and rows right, down, forward."""
    to_ply = lambda v: np.array([v[1], -v[2], v[0]])   # PLY (x, y, z) = (UE y, -UE z, UE x) / scale
    eye = to_ply([x, y, z]) / (100.0 * mpu)
    yr, pr = math.radians(yaw), math.radians(pitch)
    forward = to_ply([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), math.sin(pr)])
    right = to_ply([-math.sin(yr), math.cos(yr), 0.0])
    up = to_ply([-math.sin(pr) * math.cos(yr), -math.sin(pr) * math.sin(yr), math.cos(pr)])
    return eye, np.stack([right, -up, forward])


@torch.no_grad()
def render(s, eye, Rw, width, height, hfov, chunk=4096):
    dev = s["pos"].device
    Rw = torch.tensor(Rw, dtype=torch.float32, device=dev)
    c = torch.tensor(eye, dtype=torch.float32, device=dev)
    pc = (s["pos"] - c) @ Rw.T
    zc = pc[:, 2]
    f = 0.5 * width / math.tan(math.radians(hfov) / 2)
    limx, limy = 1.3 * 0.5 * width / f, 1.3 * 0.5 * height / f
    keep = (zc > 0.2 / 7.0) & (pc[:, 0].abs() < limx * zc) & (pc[:, 1].abs() < limy * zc)
    idx = keep.nonzero()[:, 0]
    pc, zc = pc[idx], zc[idx]
    u = f * pc[:, 0] / zc + width / 2
    v = f * pc[:, 1] / zc + height / 2
    cov = cov3d(s["scl"][idx], s["rot"][idx])
    covc = Rw @ cov @ Rw.T
    J = torch.zeros(len(idx), 2, 3, device=dev)
    J[:, 0, 0] = f / zc
    J[:, 0, 2] = -f * pc[:, 0] / (zc * zc)
    J[:, 1, 1] = f / zc
    J[:, 1, 2] = -f * pc[:, 1] / (zc * zc)
    S = J @ covc @ J.transpose(1, 2)
    a, b, d = S[:, 0, 0] + 0.3, S[:, 0, 1], S[:, 1, 1] + 0.3
    det = a * d - b * b
    mid = 0.5 * (a + d)
    lam = mid + torch.sqrt(torch.clamp(mid * mid - det, min=0.1))
    r = 3 * torch.sqrt(lam)
    on = (det > 0) & (u + r > 0) & (u - r < width) & (v + r > 0) & (v - r < height)
    sel = on.nonzero()[:, 0]
    gid, u, v, zc, r = idx[sel], u[sel], v[sel], zc[sel], r[sel]
    conic = torch.stack([d / det, -b / det, a / det], 1)[sel]
    direction = (s["pos"][gid] - c) * SH_SIGN
    direction = direction / direction.norm(dim=1, keepdim=True)
    rgb = sh_colour(direction, s["sh"][gid], s["degree"] if SH_DEGREE is None else SH_DEGREE)
    op = s["alpha"][gid]

    tx, ty = math.ceil(width / TILE), math.ceil(height / TILE)
    x0 = torch.clamp(((u - r) / TILE).floor().long(), 0, tx - 1)
    x1 = torch.clamp(((u + r) / TILE).floor().long(), 0, tx - 1)
    y0 = torch.clamp(((v - r) / TILE).floor().long(), 0, ty - 1)
    y1 = torch.clamp(((v + r) / TILE).floor().long(), 0, ty - 1)
    wx, wy = x1 - x0 + 1, y1 - y0 + 1
    cnt = wx * wy
    order = torch.argsort(zc)
    rep = torch.repeat_interleave(order, cnt[order])
    start = torch.cumsum(cnt[order], 0) - cnt[order]
    k = torch.arange(len(rep), device=dev) - torch.repeat_interleave(start, cnt[order])
    tile = (y0[rep] + k // wx[rep]) * tx + (x0[rep] + k % wx[rep])
    t_sorted, perm = torch.sort(tile, stable=True)
    splat = rep[perm]
    bounds = torch.searchsorted(t_sorted, torch.arange(tx * ty + 1, device=dev)).tolist()
    ly, lx = torch.meshgrid(torch.arange(TILE, device=dev), torch.arange(TILE, device=dev), indexing="ij")
    local = torch.stack([lx.reshape(-1), ly.reshape(-1)], 1).float() + 0.5
    img = torch.zeros(ty * TILE, tx * TILE, 3, device=dev)
    alpha_out = torch.zeros(ty * TILE, tx * TILE, device=dev)
    for t in range(tx * ty):
        lo, hi = bounds[t], bounds[t + 1]
        if lo == hi:
            continue
        ox, oy = (t % tx) * TILE, (t // tx) * TILE
        px = local + torch.tensor([ox, oy], device=dev, dtype=torch.float32)
        T = torch.ones(TILE * TILE, device=dev)
        col = torch.zeros(TILE * TILE, 3, device=dev)
        for c0 in range(lo, hi, chunk):
            ids = splat[c0:min(hi, c0 + chunk)]
            dx = px[None, :, 0] - u[ids, None]
            dy = px[None, :, 1] - v[ids, None]
            cn = conic[ids]
            pw = -0.5 * (cn[:, 0:1] * dx * dx + cn[:, 2:3] * dy * dy) - cn[:, 1:2] * dx * dy
            al = torch.clamp(op[ids, None] * torch.exp(torch.clamp(pw, max=0)), max=0.99)
            al = torch.where(al < 1 / 255, torch.zeros_like(al), al)
            Tc = torch.cumprod(torch.cat([torch.ones(1, TILE * TILE, device=dev), 1 - al[:-1]], 0), 0) * T
            col += (al * Tc).T @ rgb[ids]
            T = Tc[-1] * (1 - al[-1])
            if T.max() < 1e-4:
                break
        img[oy:oy + TILE, ox:ox + TILE] = col.view(TILE, TILE, 3)
        alpha_out[oy:oy + TILE, ox:ox + TILE] = (1 - T).view(TILE, TILE)
    return img[:height, :width].cpu().numpy(), alpha_out[:height, :width].cpu().numpy()


def main():
    ply, out = sys.argv[1], sys.argv[2]
    x, y, z, yaw, pitch = map(float, sys.argv[3:8])
    width, height, hfov = (int(sys.argv[8]), int(sys.argv[9]), float(sys.argv[10])) if len(sys.argv) > 10 else (1600, 900, 90.0)
    name = sys.argv[11] if len(sys.argv) > 11 else "Hongdae"
    global SH_SIGN, SH_DEGREE
    SH_SIGN = float(__import__("os").environ.get("SH_SIGN", "1"))
    SH_DEGREE = int(__import__("os").environ["SH_DEGREE"]) if "SH_DEGREE" in __import__("os").environ else None
    s = load(ply)
    eye, Rw = ue_camera(x, y, z, yaw, pitch, metres_per_unit(name))
    img, alpha = render(s, eye, Rw, width, height, hfov)
    # over a flat sky-ish background, like the Unreal shots' sky
    bg = np.array([0.72, 0.82, 0.9])
    rgb = img + (1 - alpha[..., None]) * bg
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(out)
    print(f"{out}: {s['n']:,} splats, SH degree {s['degree']}")


if __name__ == "__main__":
    main()
