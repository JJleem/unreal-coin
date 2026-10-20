# City kit (scaling the rebuild beyond zone A)

| Script | What it does | Result on Hongdae |
|---|---|---|
| `import_kit.py` | imports the external models (Poly Haven CC0, `SourceAssets/PolyHaven/LICENSE.txt`) into `/Game/CityKit` and catalogues every mesh | 12 models, 176 meshes. No CC0 passenger car exists there; Fab / Quixel need an Epic login this environment doesn't have |
| `scan_survey.py` | damage per 1 m column x exposure to the play path -> priority map and ranked 4 m tiles; pole and vehicle candidates | map works for ranking; **pole detection is unreliable** (one "pole" was in the middle of the road) |
| `auto_zone_plan.py` | writes a zone plan automatically (sidewalks from the ground height step, red pavement, cones, poles) | **sidewalk detection failed**: IoU 0.23 at best against zone A's measured plan (the scan's ground splats are too faint to resolve a 13 cm curb). Sidewalks need a person drawing on the orthophoto, ~15 min per zone |
| `build_world_scan.py` | merges the zones' splat removals into one trimmed scan | A + B: 10 % of the splats replaced, 90 % of the scan kept |
| `build_world_level.py` | `Lvl_Hongdae_World`: HQ level + zone B meshes + kit poles | **worse than the plain scan in zone B** (see below); kept as a test level |

Zone B (x 22-46) was built with this kit in about 30 minutes (vs about a day for zone A by hand), but compared at the
same cameras it looks worse than the untouched scan: at eye height the scanned red street is cleaner and more real
than the tiling road material; the auto paint and the misplaced pole hurt. The recommended level stays
`Lvl_Hongdae_HighQualityGS` (zone A rebuilt, the rest scan).

Lesson for scaling: replace ground only where the survey shows damage on the play path (the intersection's dark
smears), not whole streets; keep the scanned facades; use kit props only where a person confirmed the spot.
