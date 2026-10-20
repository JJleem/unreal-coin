"""
Spawns the holographic course of a stage: platforms, jump pads, breakable walls, extra coins and the hidden gem.
Shared by build_scan_stages.py (scan stages, course planned by make_scan_collision.py), place_courses.py (respawns
only the course on the built stages) and place_training_coins.py (the hand-made tutorial course).

All values are Unreal centimetres. Course actors get a "Course_" label so they can be found and replaced.
"""

import unreal

LABEL = "Course_"


def vec(p):
    return unreal.Vector(p[0], p[1], p[2])


def make_box(b):
    """[minx, miny, minz, maxx, maxy, maxz] -> unreal.Box"""
    box = unreal.Box()
    box.set_editor_property("min", vec(b[:3]))
    box.set_editor_property("max", vec(b[3:]))
    box.set_editor_property("is_valid", True)
    return box


def clear_course(actors):
    """Removes the course actors placed before."""
    removed = 0
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label().startswith(LABEL):
            actors.destroy_actor(actor)
            removed += 1
    return removed


def place_course(actors, course):
    """course: {"platforms": [[x, y, top z, sx, sy, sz, yaw]], "jumpPads": [[x, y, z, tx, ty, tz]],
    "smashWalls": [[box, ...]], "coins": [[x, y, z]], "gem": [x, y, z] or None}"""
    def spawn(cls, location, name):
        actor = actors.spawn_actor_from_class(cls, location, unreal.Rotator(0, 0, 0))
        if actor is None:
            raise RuntimeError(f"Failed to spawn {cls}")
        actor.set_actor_label(LABEL + name)
        return actor

    for i, (x, y, top, sx, sy, sz, yaw) in enumerate(course.get("platforms", []), start=1):
        platform = spawn(unreal.HoloPlatform, unreal.Vector(x, y, top - sz / 2), f"Platform_{i:02d}")
        platform.set_actor_rotation(unreal.Rotator(0, 0, yaw), False)
        platform.set_look(unreal.Vector(sx, sy, sz), unreal.LinearColor(0.15, 0.7, 1.0, 1.0))

    for i, (x, y, z, tx, ty, tz) in enumerate(course.get("jumpPads", []), start=1):
        # the pad's trigger box is centred 40 cm above the ground
        pad = spawn(unreal.JumpPad, unreal.Vector(x, y, z + 40), f"JumpPad_{i:02d}")
        pad.set_target(unreal.Vector(tx, ty, tz))

    for i, group in enumerate(course.get("smashWalls", []), start=1):
        wall = spawn(unreal.BreakableBarrier, vec(group[0][:3]), f"Wall_{i:02d}")
        wall.set_boxes([make_box(b) for b in group])
        wall.set_always_visible(True)

    for i, coin in enumerate(course.get("coins", []), start=1):
        spawn(unreal.CoinPickup, vec(coin), f"Coin_{i:02d}")

    if course.get("gem"):
        spawn(unreal.GemPickup, vec(course["gem"]), "Gem")

    unreal.log(f"[Course] {len(course.get('platforms', []))} platforms, {len(course.get('jumpPads', []))} jump pads, "
               f"{len(course.get('smashWalls', []))} walls, {len(course.get('coins', []))} coins, gem {bool(course.get('gem'))}")
