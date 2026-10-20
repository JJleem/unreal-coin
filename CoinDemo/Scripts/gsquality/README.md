# Splat rendering quality (Hongdae, zone A)

Separates what the renderer loses from what the scan itself lacks, by rendering the same PLY from exactly the same
camera with a reference rasterizer and with Unreal, then measuring the difference.

| Script | What it does |
|---|---|
| `reference_render.py` | standard 3DGS rasterization (INRIA algorithm, PyTorch, SH up to degree 3) from a DevCapture camera |
| `make_gs_only_level.py` | `Lvl_Hongdae_GSOnly`: the stage with only scan, lights, sky, post process |
| `make_hq_level.py` | `Lvl_Hongdae_HighQualityGS` (+ `_ScanOnly`, `_MeshOnly`) with the before/after demo (key B) |
| `OpenSplat4D_CoinDemo.patch` | the plugin changes (the plugin itself is not in this repo); backup of the original in `SourceAssets/OpenSplat4D_backup` |

Findings (view 1, Blue Elephant front, 1600x900, same camera):

* Unreal vs reference before: sharpness (laplacian variance) 79 vs 115, mean abs colour error 0.103, mid tones 0.45 -> 0.35
* FXAA costs about 20 % of the sharpness (79 -> 97 with AA off). TSR keeps it while still and in motion (83 vs 78 for
  FXAA, averaged over a sideways move at 3 m/s), with slight ghosting on small high contrast logos. TSR chosen.
* The composite's inverse ACES fit doesn't match Unreal's tonemapper: splats came out about 20 % darker in the mid
  tones. A measured per channel LUT (`gs.ToneCorrection 1`) fixes it: colour error 0.058, sharpness 106.
* Checked and equal to the reference: projection and 0.3 px low pass, falloff, sorting (device depth), SH direction
  (SH1 matches best, flipped direction worse), premultiplied blending in a 16 bit float target.
* Cluster LOD: forcing the finest level changes sharpness by about 1 %. Not pursued.
* Remaining gap to the reference (106 vs 115) and the glass reflections differ; not explained by the above.
