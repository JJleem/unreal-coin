"""
Places the coins and the tutorial course on the template map (stage 1). Existing coins and course are removed first.

The template map is a 40 x 40 m floor with a raised centre and four raised corner blocks reached by ramps, so the
coins are placed by hand.
(Line traces don't work in a headless editor, which is why this doesn't search the geometry.)

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import course_actors  # noqa: E402

LEVEL = "/Game/ThirdPerson/Lvl_ThirdPerson"
COIN_HEIGHT = 100.0  # coin centre above the surface, cm

# (x, y, surface height) in cm, from the bounds of the map's blocks. Stage 1 is the tutorial, so it only has two
# coins: one down on the open floor and one on a corner block reached by a ramp.
SPOTS = [
    (1000, 1000, 0),      # open floor
    (1650, -1500, 200),   # corner block SM_Cube8
]

# a small version of the scan stages' course, in the open floor between the centre and the corners:
# three climbable columns with the gem on a pillar between them, a jump pad up to a floating platform, and a breakable cage around the
# first coin to teach smashing
COURSE = {
    "platforms": [
        # columns on the floor around (-950, 950), each a ledge climb above the last, and the gem pillar in the middle
        [-770, 950, 100, 180, 180, 120, 0],
        [-894, 1121, 200, 180, 180, 220, 72],
        [-1096, 1056, 300, 180, 180, 320, 144],
        [-950, 950, 480, 140, 140, 500, 0],
        [-1300, -700, 550, 300, 300, 30, 0],    # jump pad platform
    ],
    "jumpPads": [[-850, -850, 0, -1300, -700, 550]],
    "smashWalls": [[[x0, y0, -20, x1, y1, 300]] for x0, y0, x1, y1 in (
        (830, 830, 1170, 860), (830, 1140, 1170, 1170), (830, 860, 860, 1140), (1140, 860, 1170, 1140))],
    "coins": [],
    "gem": [-950, 950, 580],
}

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels.load_level(LEVEL)

for coin in [a for a in actors.get_all_level_actors() if isinstance(a, unreal.CoinPickup)]:
    actors.destroy_actor(coin)
course_actors.clear_course(actors)
course_actors.place_course(actors, COURSE)

for i, (x, y, z) in enumerate(SPOTS, start=1):
    coin = actors.spawn_actor_from_class(unreal.CoinPickup, unreal.Vector(x, y, z + COIN_HEIGHT), unreal.Rotator(0, 0, 0))
    coin.set_actor_label(f"Coin_{i:02d}")

levels.save_current_level()
unreal.log(f"[TrainingCoins] Placed {len(SPOTS)} coins on {LEVEL}")
