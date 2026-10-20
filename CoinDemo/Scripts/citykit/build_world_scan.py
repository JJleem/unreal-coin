"""
Combines the zones' splat removals (each zone's build_zone.py writes removed_keepbuilding.npy, all from the same
cleaned scan) into one trimmed scan for the world level, and writes the ground height at the kit props.

  python build_world_scan.py Hongdae A B
Output: SourceAssets/Rebuilt/<Stage>_World/<Stage>_World.ply and generated/<Stage>_world_props.json
"""

import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rebuild.common import GENERATED_DIR, OUT_DIR, SCRIPTS_DIR, Scan, ground_grid, load_collision, write_ply  # noqa: E402

name, zones = sys.argv[1], sys.argv[2:]
scan = Scan(name)
removed = np.zeros(scan.data.shape[0], bool)
for zone in zones:
    mask = np.unpackbits(np.load(os.path.join(OUT_DIR, f"{name}_{zone}", "removed_keepbuilding.npy")))[:len(removed)].astype(bool)
    removed |= mask
out = os.path.join(OUT_DIR, f"{name}_World")
os.makedirs(out, exist_ok=True)
write_ply(os.path.join(out, f"{name}_World.ply"), scan.header, scan.data[~removed])

lo, height, _ = ground_grid(load_collision(name), 0.5)
valid = np.argwhere(~np.isnan(height))
tree = cKDTree(valid)
props = {"poles": []}
for zone in zones:
    plan = json.load(open(os.path.join(SCRIPTS_DIR, "rebuild", "zones", f"{name}_{zone}.json")))
    box = plan["box"]
    for x, y in plan.get("kit_poles", []):
        if box[0] <= x <= box[1] and box[2] <= y <= box[3]:
            _, k = tree.query((np.array([x, y]) - lo) / 0.5)
            props["poles"].append([x, y, float(height[valid[k, 0], valid[k, 1]])])
with open(os.path.join(GENERATED_DIR, f"{name}_world_props.json"), "w") as f:
    json.dump(props, f)
print(f"{name} world: {len(removed):,} -> {(~removed).sum():,} splats ({removed.mean() * 100:.1f}% replaced by meshes), {len(props['poles'])} kit poles")
