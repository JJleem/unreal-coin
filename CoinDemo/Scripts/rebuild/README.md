# Stage rebuild pipeline (scan → plan → buildings + trimmed scan)

Rebuilds the street of a scan stage as real geometry, separately from the stage pipeline: it only reads the built
stage and writes new assets under `/Game/Stages/Rebuilt/<Name>/` and the test levels `Lvl_<Name>_Rebuilt` (hybrid)
and `Lvl_<Name>_RebuiltMesh` (meshes only). `build_scan_stages.py` never touches them.

| Step | Script | Where | Output |
|---|---|---|---|
| 1 plan | `analyze_layout.py <Name>` | outside (numpy, scipy, Pillow) | `generated/<Name>_layout.json`, `_plan.svg`, `_plan.png` |
| 2-4 geometry, photos, trimmed scan | `build_geometry.py <Name>` | outside (+ numba) | `SourceAssets/Rebuilt/<Name>/` |
| 5 levels | `build_rebuilt_level.py` (`NAME` at the top) | Unreal editor Python | assets and the two test levels |

Inputs: the cleaned scan (`clean_scans.py`), the collision data (`make_scan_collision.py`) and the built stage.

What is measured and what is assumed:

* measured: walkable area, street centre line, facade lines (dense flat upright splats 3-10 m above the ground),
  openings (cross streets, alleys), roof height per metre (photo rows of solid wall), face photos (the scan's own
  splats composited onto each face from outside, front to back, 1.25 cm per pixel, glass shop fronts included)
* assumed: buildings are boxes with facades parallel to the street axis; depth behind the facade (8 m, less if a
  coin or course piece would end up inside); flat roofs; plain roofs, backs and sides where the scan saw nothing
* not built: facade runs whose photo shows too little wall or mostly leaves (trees); these stay as scan

The model only covers the main street of a scan filmed along one street. Cross streets, trees, cars, people, signs
that stick out and the background stay splats (hybrid). There are no source photos or camera poses for these scans,
so faces can't be textured from photographs; their textures are the scan's colours (degree 0, no view-dependent
reflections).
