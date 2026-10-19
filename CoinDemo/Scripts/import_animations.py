"""
Imports the Quaternius Universal Animation Library packs (CC0) and retargets them onto the UE5 mannequin skeleton.

Source files (not in git, see HANDOFF.md): CoinDemo/SourceAssets/Quaternius/UAL1_Standard.fbx, UAL2_Standard.glb
Result: /Game/Quaternius/<Pack>/...          imported meshes, skeletons and animations
        /Game/Quaternius/Rigs/...            auto-generated IK Rigs and the retargeters
        /Game/Quaternius/Mannequin/<anim>    animations on SK_Mannequin, used by the character

The packs use Unreal-style bone names but only three spine bones, so they can't be imported straight onto
SK_Mannequin. Both skeletons get an auto-generated IK Rig, a retargeter maps the chains and aligns the source
T-pose to the mannequin's pose, and the animations are batch duplicated onto the mannequin.

  UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script="<this file>"
"""

import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "Quaternius"))
ROOT = "/Game/Quaternius"
TARGET_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"
PACKS = [("UAL1", "UAL1_Standard.fbx"), ("UAL2", "UAL2_Standard.glb")]
ROOT_MOTION = ["UAL1_StandardRig_Roll_RM", "UAL2_StandardClimbUp_1m_RM"]

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
registry = unreal.AssetRegistryHelpers.get_asset_registry()


def assets_of(path, class_name):
    return [a for a in registry.get_assets_by_path(path, recursive=True) if str(a.asset_class_path.asset_name) == class_name]


def import_pack(pack, file_name):
    path = f"{ROOT}/{pack}"
    if not assets_of(path, "SkeletalMesh"):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", os.path.join(SOURCE_DIR, file_name))
        task.set_editor_property("destination_path", path)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)
        asset_tools.import_asset_tasks([task])

    meshes = assets_of(path, "SkeletalMesh")
    anims = assets_of(path, "AnimSequence")
    unreal.log(f"[Anims] {pack}: {len(meshes)} meshes, {len(anims)} animations")
    if not meshes:
        raise RuntimeError(f"Import of {file_name} produced no skeletal mesh")
    return unreal.load_asset(str(meshes[0].package_name)), anims


def make_ik_rig(name, mesh):
    path = f"{ROOT}/Rigs/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    rig = asset_tools.create_asset(name, f"{ROOT}/Rigs", unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    controller = unreal.IKRigController.get_controller(rig)
    controller.set_skeletal_mesh(mesh)
    if not controller.apply_auto_generated_retarget_definition():
        raise RuntimeError(f"Could not auto-characterize {mesh.get_name()}")
    unreal.EditorAssetLibrary.save_loaded_asset(rig)
    return rig


def make_retargeter(name, source_rig, source_mesh, target_rig, target_mesh):
    path = f"{ROOT}/Rigs/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    rtg = asset_tools.create_asset(name, f"{ROOT}/Rigs", unreal.IKRetargeter, unreal.IKRetargetFactory())
    c = unreal.IKRetargeterController.get_controller(rtg)
    c.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_rig)
    c.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_rig)
    c.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, source_mesh)
    c.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_mesh)
    c.add_default_ops()
    c.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.SOURCE, source_rig)
    c.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.TARGET, target_rig)
    c.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)

    # the packs are authored from a T-pose, the mannequin from an A-pose: bend the source retarget pose to match
    c.create_retarget_pose("Aligned", unreal.RetargetSourceOrTarget.SOURCE)
    c.auto_align_all_bones(unreal.RetargetSourceOrTarget.SOURCE)
    unreal.EditorAssetLibrary.save_loaded_asset(rtg)
    return rtg


def set_root_motion():
    """Roll and climb move the character with the animation's own root motion."""
    for name in ROOT_MOTION:
        anim = unreal.load_asset(f"{ROOT}/Mannequin/{name}")
        anim.set_editor_property("enable_root_motion", True)
        unreal.log(f"[Anims] root motion on {name}")


def main():
    target_mesh = unreal.load_asset(TARGET_MESH)
    if assets_of(f"{ROOT}/Mannequin", "AnimSequence") and "--force" not in unreal.SystemLibrary.get_command_line():
        unreal.log("[Anims] already retargeted, only updating flags (pass --force to redo)")
        set_root_motion()
        unreal.EditorAssetLibrary.save_directory(ROOT)
        return

    target_rig = make_ik_rig("IK_Quinn", target_mesh)

    out_path = f"{ROOT}/Mannequin"
    for pack, file_name in PACKS:
        source_mesh, anims = import_pack(pack, file_name)
        source_rig = make_ik_rig(f"IK_{pack}", source_mesh)
        rtg = make_retargeter(f"RTG_{pack}_To_Quinn", source_rig, source_mesh, target_rig, target_mesh)

        made = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
            anims, source_mesh, target_mesh, rtg, "", "", "", "", out_path, False, False, True)
        unreal.log(f"[Anims] {pack}: retargeted {len(made)} animations into {out_path}")

    set_root_motion()

    for a in assets_of(out_path, "AnimSequence"):
        unreal.log(f"[Anims] result {a.asset_name}")
    unreal.EditorAssetLibrary.save_directory(ROOT)


main()
