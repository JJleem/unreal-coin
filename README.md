# unreal-coin

Unreal Engine 5.8 third-person coin collecting demo whose stages are real-world 3D Gaussian Splatting scans.
Collect every coin in a stage to move on to the next one.

This repository holds the code, scripts, config and docs only. The scans, the Unreal content (`.uasset`, `.umap`)
and the OpenSplat4D plugin are not included; see [HANDOFF.md](HANDOFF.md) (Korean) for how everything is built,
including how the PLY scans are turned into playable stages.

| Path | What it is |
|---|---|
| `CoinDemo/Source/CoinDemo/CoinGame/` | Game code: coins, HUD, scan actor |
| `CoinDemo/Source/CoinDemo/CoinDemoGameMode.*` | Stage list and progression |
| `CoinDemo/Scripts/make_scan_collision.py` | Scan → ground, walls, coin positions (numpy) |
| `CoinDemo/Scripts/build_scan_stages.py` | Builds the stage levels inside Unreal (editor Python) |
| `HANDOFF.md` | Full project notes |
