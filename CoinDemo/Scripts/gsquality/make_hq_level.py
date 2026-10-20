"""
Builds /Game/Stages/Lvl_Hongdae_HighQualityGS from the zone A test level (Scripts/rebuild): same rebuilt ground,
building, props and trimmed scan, plus

  * a BeforeAfterDemo actor: B switches between the raw ANNX PLY with plugin defaults and the final result, and it
    applies the final render settings (TSR, gs.ToneCorrection) while the level plays
  * lighting rebalanced for tone corrected splats: they come out about 1.64x brighter (linear) than before, so the
    sun and sky light that light the meshes go up by the same factor, the sky luminance compensation down

Variants for the comparisons: _HQ_ScanOnly (meshes hidden), _HQ_MeshOnly (no scan).

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import unreal

SOURCE = "/Game/Stages/Lvl_Hongdae_ZoneA"
TARGET = "/Game/Stages/Lvl_Hongdae_HighQualityGS"
RAW_SCAN = "/Game/Stages/Tests/Hongdae_raw"          # the ANNX PLY as delivered, imported with build_nanite
AFTER_SCAN = "/Game/Stages/Rebuilt/Hongdae_A/Hongdae_A_ScanKeepBuilding"   # the scanned building stays
TONE_GAIN = 1.64        # measured: tone corrected splat mids 0.432 vs 0.345 sRGB -> (0.432 / 0.345) ^ 2.2
ZONE_SUN, ZONE_SKYLIGHT, ZONE_SKY_LUMINANCE = 0.11, 0.3, 1.0 / 0.11   # build_zone_level.py

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels.load_level(SOURCE)

for actor in actors.get_all_level_actors():
    if isinstance(actor, unreal.DirectionalLight):
        light = actor.get_component_by_class(unreal.LightComponentBase)
        light.set_editor_property("intensity", light.get_editor_property("intensity") * TONE_GAIN)
    elif isinstance(actor, unreal.SkyLight):
        light = actor.get_component_by_class(unreal.LightComponentBase)
        light.set_editor_property("intensity", light.get_editor_property("intensity") * TONE_GAIN)
    elif isinstance(actor, unreal.SkyAtmosphere):
        atmosphere = actor.get_component_by_class(unreal.SkyAtmosphereComponent)
        f = ZONE_SKY_LUMINANCE / TONE_GAIN
        atmosphere.set_editor_property("sky_luminance_factor", unreal.LinearColor(f, f, f, 1.0))

# the modelled building only gives collision here: its scan is sharper from the street than the model
for actor in actors.get_all_level_actors():
    if actor.get_actor_label() == "Zone_SM_Zone_BlueElephant":
        actor.set_editor_property("tags", [])
        actor.set_actor_hidden_in_game(True)
    elif isinstance(actor, unreal.ScanSplatActor):
        actor.get_splat().set_splat_asset(unreal.load_asset(AFTER_SCAN))

demo = actors.spawn_actor_from_class(unreal.BeforeAfterDemo, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
demo.set_actor_label("BeforeAfterDemo")
demo.set_editor_property("before_scan", unreal.load_asset(RAW_SCAN))
demo.set_editor_property("after_scan", unreal.load_asset(AFTER_SCAN))
demo.set_editor_property("before_sun_scale", 1.0 / (ZONE_SUN * TONE_GAIN))
demo.set_editor_property("before_sky_light_scale", 1.0 / (ZONE_SKYLIGHT * TONE_GAIN))
demo.set_editor_property("before_sky_luminance", 1.0)
world = editor.get_editor_world()
unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET)

# comparison variants
for actor in actors.get_all_level_actors():
    if actor.get_actor_label().startswith("Zone_"):
        actor.set_actor_hidden_in_game(True)
    elif isinstance(actor, unreal.BeforeAfterDemo):
        actor.set_editor_property("mesh_tag", "ScanOnlyNoMeshes")   # keep the meshes hidden in the after state
unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET + "_ScanOnly")
levels.load_level(TARGET)
for actor in actors.get_all_level_actors():
    if isinstance(actor, unreal.ScanSplatActor):
        actors.destroy_actor(actor)
unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(), TARGET + "_MeshOnly")
unreal.log("[HQ] saved Lvl_Hongdae_HighQualityGS (+ _ScanOnly, _MeshOnly)")
