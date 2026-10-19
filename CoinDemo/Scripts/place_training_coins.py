"""
Places the coins on the template map (stage 1). Existing coins are removed first.

The template map is a 40 x 40 m floor with a raised centre and four raised corner blocks reached by ramps, so the
coins are placed by hand.
(Line traces don't work in a headless editor, which is why this doesn't search the geometry.)

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import unreal

LEVEL = "/Game/ThirdPerson/Lvl_ThirdPerson"
COIN_HEIGHT = 100.0  # coin centre above the surface, cm

# (x, y, surface height) in cm, from the bounds of the map's blocks. Stage 1 is the tutorial, so it only has two
# coins: one down on the open floor and one on a corner block reached by a ramp.
SPOTS = [
    (1000, 1000, 0),      # open floor
    (1650, -1500, 200),   # corner block SM_Cube8
]

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels.load_level(LEVEL)

for coin in [a for a in actors.get_all_level_actors() if isinstance(a, unreal.CoinPickup)]:
    actors.destroy_actor(coin)

for i, (x, y, z) in enumerate(SPOTS, start=1):
    coin = actors.spawn_actor_from_class(unreal.CoinPickup, unreal.Vector(x, y, z + COIN_HEIGHT), unreal.Rotator(0, 0, 0))
    coin.set_actor_label(f"Coin_{i:02d}")

levels.save_current_level()
unreal.log(f"[TrainingCoins] Placed {len(SPOTS)} coins on {LEVEL}")
