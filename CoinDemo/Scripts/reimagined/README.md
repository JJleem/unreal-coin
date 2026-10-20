# Reimagined Hongdae (rebuilt buildings over the scan)

`Lvl_Hongdae_Reimagined` = `Lvl_Hongdae_HighQualityGS` (zone A ground, tone correction, TSR, key B before/after)
+ three reference buildings rebuilt as real architecture + the scan with their splats removed.

| Script | Does |
|---|---|
| `fetch_polyhaven.py` | downloads the CC0 models / 2k textures (Poly Haven API) into `SourceAssets/PolyHaven`, logs them in its `LICENSE.txt` |
| `bkit.py` | building kit: facades (a→b seen from the street), walls with openings and reveals, windows (sliding / casement / grid, frames, sills, 방범창 grilles), shop fronts with doors and handles, rooms behind the glass, sign boxes, blade signs, extruded channel letters from TrueType fonts, bands, parapets, railings, downpipes, gas pipes, cables, shop fit-out (display walls, garment rails, tables) |
| `signs.py` | sign faces drawn with real fonts (Malgun Gothic, Arial, YaHei) with light wear |
| `hongdae_buildings.py` | SOLB, BIBIANG (cut corner), BLUE ELEPHANT / The Coffee Bean, on facade lines measured from the scan (wall splat peaks, baked facade photos) |
| `build_reimagined.py` (WSL) | meshes.json, props.json, materials.json (tints from texture averages to target albedos), sign textures, the trimmed scan |
| `build_reimagined_level.py` (Unreal) | materials (PBR + AO + rain streaks + rising damp, flat, sign, translucent glass), meshes, Poly Haven props, the level and `_MeshOnly` |

Run: `python build_reimagined.py`, then `UnrealEditor-Cmd ... -run=pythonscript -script=Scripts\reimagined\build_reimagined_level.py`.

Numbers (2026-10-20): 3 buildings, 6 meshes (~20k triangles), 76 materials, 76 kit prop actors, 13 drawn signs;
scan 4,390,703 cleaned splats → 3,692,856 kept (zone A ground 242,825 and the three buildings 455,022 removed).
FPS (RTX 5080, 1600x900, fixed views): final 127-153, mesh only 130-158, previous zone A 142-172, raw 108-140;
character play 117.

Lighting notes: the full zone A white balance (blue x1.49) made real albedos lavender, half of it is used; the sky light
is raised 2.5x over zone A so the new buildings' sun shadows on the street aren't black; rooms behind the glass glow
faintly (emissive) because Lumen amplifies emissive in closed rooms, values are low (0.12-0.25 x exposure).

Not done / limits: only these three buildings; the rest of the street is scan. Interiors are simple fit-outs. Edges are
not bevelled, no decals of dirt beyond the material weathering. No CC0 cars exist (Fab/Quixel need a login).
