# unreal-coin

Unreal Engine 5.8 third-person coin race whose stages are real-world 3D Gaussian Splatting scans of Seoul, Jeonju
and Jeju, with a holographic obstacle course laid over each one: climbable column towers, jump pads, floating
platforms, breakable walls and a hidden gem. Collect every coin to move on; beat the medal times, chain coins into
combos and race the ghost of your best run. Title screen, stage select, settings and pause menu included.

This repository holds the code, scripts, config and docs only. The scans, the Unreal content (`.uasset`, `.umap`)
and the OpenSplat4D plugin are not included; see [HANDOFF.md](HANDOFF.md) (Korean) for how everything is built,
including how the PLY scans are turned into playable stages.

| Path | What it is |
|---|---|
| `CoinDemo/Source/CoinDemo/CoinGame/` | Game code: coins, course actors, ghost, menus, HUD, game feel, scan actor |
| `CoinDemo/Source/CoinDemo/CoinDemoGameMode.*` | Stage list and progression |
| `CoinDemo/Scripts/make_scan_collision.py` | Scan → ground, walls, coin positions and the holographic course (numpy) |
| `CoinDemo/Scripts/build_scan_stages.py` | Builds the stage levels inside Unreal (editor Python) |
| `HANDOFF.md` | Full project notes |
