import bpy
import bpy.types as types
import bpy.props as props

from .properties_utils import Prop_inspector, copyProps
from .properties_global import MW_global_storage, MW_global_selected

from .utils_dev import DEV

# Access from other modules to constants
class ADDON:
    _bl_info = None
    _bl_name = None
    _bl_loaded = False
    mod_name = __name__
    mod_name_prefs = mod_name.split(".")[0]
    panel_cat = "Dev"

def getPrefs() -> "MW_prefs":
    """ Get addon preferences from blender """
    return bpy.context.preferences.addons[MW_prefs.bl_idname].preferences


#-------------------------------------------------------------------

class MW_dev(types.PropertyGroup):
    """ Toggle some DEV flags in runtime """
    meta_show_props: props.BoolProperty(
        description="Show DEV cfg",
        default=True,
    )

    DEBUG_MODEL : props.BoolProperty(
        default=DEV.DEBUG_MODEL,
        update=lambda self, context: setattr(DEV, "DEBUG_MODEL", self.DEBUG_MODEL),
    )

    logs : props.BoolProperty(
        default=DEV.logs,
        update=lambda self, context: setattr(DEV, "logs", self.logs),
    )
    logs_stats_dt : props.BoolProperty(
        default=DEV.logs_stats_dt,
        update=lambda self, context: setattr(DEV, "logs_stats_dt", self.logs_stats_dt),
    )

    # toggle logging types
    logs_type_skipped : props.StringProperty(
        default= DEV.get_logs_type_skipped(),
        update=lambda self, context: DEV.set_logs_type_skipped(self.logs_type_skipped),
    )
    logs_type_whitelist : props.StringProperty(
        default= DEV.get_logs_type_whitelist(),
        update=lambda self, context: DEV.set_logs_type_whitelist(self.logs_type_whitelist),
    )
    logs_cutmsg : props.IntProperty(
        default=DEV.logs_cutmsg,
        update=lambda self, context: setattr(DEV, "logs_cutmsg", self.logs_cutmsg),
        min=50, max=300
    )

class DM_utils(types.PropertyGroup):
    """ Global prefs for the dm utils (all part of PT) """

    meta_show_info: props.BoolProperty(
        name="Inspect OBJ", description="Show some object info",
        default=False,
    )
    meta_show_full: props.BoolProperty(
        name="full...", description="Show more info",
        default=False,
    )
    meta_scene_info: props.BoolProperty(
        name="Inspect SCENE", description="Show some scene info",
        default=False,
    )
    meta_show_debug: props.BoolProperty(
        name="debug...", description="WIP: Show some debug stuff",
        default=True,
    )

    # filters
    edit_useSelected: props.BoolProperty(
        name="Use selected", description="Show the selected mesh data (NOT UPDATED LIVE)",
        default=True,
    )
    edit_showLimit: props.IntProperty(
        name="limit", description="Max number of items shown per type (blender has a limit size of scrollable UI area)",
        default=20, min=1, max=50,
    )
    edit_indexFilter: props.StringProperty(
        name="Indices", description="Range '2_20' (20 not included). Specifics '2,6,7'. Both '0_10,-1' ('-' for negative indices)",
        default="0_3,-1",
    )

    # edit options
    edit_showVerts: props.BoolProperty(
        name="Show verts...", description="Show long list of verts with its pos",
        default=False,
    )
    edit_showEdges: props.BoolProperty(
        name="Show edges...", description="Show long list of edges with its key (v1, v2)",
        default=False,
    )
    edit_showFaces: props.BoolProperty(
        name="Show faces...", description="Show long list of faces with its verts id / center",
        default=True,
    )
    edit_showFaceCenters: props.BoolProperty(
        name="show center", description="Show face center position instead of vertex indices",
        default=False,
    )

    # toggle visual
    info_showPrecision: props.IntProperty(
        name="decimals", description="Number of decimals shown, will make colum wider.",
        default=2, min=0, max=16,
    )
    info_edit_showWorld: props.BoolProperty(
        name="world", description="Show vertices positions in world space",
        default=False,
    )

    # data
    orphans_collection: props.StringProperty(
        name="", description="E.g. meshes, mats, curves, etc",
        default="meshes, materials, curves",
    )

#-------------------------------------------------------------------

class MW_prefs(bpy.types.AddonPreferences):
    bl_idname = ADDON.mod_name_prefs
    """ # NOTE:: __name__ must be exaclty used for addon prefs, so check when deploying without the addon"""

    def draw(self, context):
        """ Draw in preferences panel"""
        # Careful with circulare dependecies, maybe split the class with draw and props
        from .ui import draw_propsToggle
        draw_propsToggle(self, getPrefs().prefs_PT_meta_inspector, self.layout)

    #-------------------------------------------------------------------

    class names:
        original = "original"
        original_copy = original+"_0_"
        original_convex = original+"_1_convex"
        original_dissolve = original+"_2_dissolve"

        source = "source"
        source_points = source+"_points"
        source_wallsBB = source+"_wallsBB"

        cells = "cells"
        cells_air = cells+"_air"
        cells_core = cells+"_core"

        links = "links"
        links_air = links+"_air"

        # TODO:: no more legacy support
        links_legacy = links+"_legacy"
        links_group = "L"

        @classmethod
        def get_MatFormated(cls, name:str):
            """ Add common material suffix """
            return f"{name}_mat"

        @classmethod
        def get_IdFormated(cls, idx:int):
            """ Pad with a certain amount of zeroes to achieve a correct lexicographic order """
            return f"{{:{cls.child_idFormat}}}".format(idx)

        child_idFormat = "04"
        @classmethod
        def set_IdFormated_amount(cls, n:int):
            """ Dynamically adjust based on number of cells """
            from math import ceil
            digits = len(str(n))
            cls.child_idFormat = f"0{digits}"

    #-------------------------------------------------------------------

    # workaround undo/redo system to keep alive the data in memory or not
    def prefs_autoPurge_update(self, context):
        MW_global_storage.enable_autoPurge = self.prefs_autoPurge
        MW_global_storage.purgeFracts()

    prefs_autoPurge: props.BoolProperty(
        name="purge", description="Keep purging on undo/delete/etc",
        default=MW_global_storage.enable_autoPurge_default,
        update= prefs_autoPurge_update
    )

    #-------------------------------------------------------------------

    # edit some DEV params
    dev_PT_meta_cfg: props.PointerProperty(type=MW_dev)
    # dm utils prefs
    dm_prefs: props.PointerProperty(type=DM_utils)

    # meta inspectors for OP props
    prefs_PT_meta_inspector: props.PointerProperty(type=Prop_inspector)
    gen_PT_meta_inspector: props.PointerProperty(type=Prop_inspector)
    vis_PT_meta_inspector: props.PointerProperty(type=Prop_inspector)

    # edit default vis (being in prefs avoids undo stack)
    from .properties import MW_vis_cfg
    mw_vis: props.PointerProperty(type=MW_vis_cfg)
    def mw_vis_newSelected_update(newRoot):
        """ Copy the new config to the prefs to show up in the panel """
        copyProps(newRoot.mw_vis, getPrefs().mw_vis)

    #-------------------------------------------------------------------

    all_PT_meta_show_root: props.BoolProperty(
        name="Root props", description="Show root properties / selected child. Children should have most default values.",
        default=True,
    )

    gen_duplicate_OT_hidePrev: props.BoolProperty(
        name="hide", description="Hide the original fractured object after duplication",
        default=True,
    )

    util_delete_OT_unhideSelect: props.BoolProperty(
        name="unhide", description="Unhide the original object after deletion",
        default=True,
    )


#-------------------------------------------------------------------
# Blender events

classes = [
    MW_dev,
    DM_utils,
    MW_prefs,
]
_name = f"{__name__[14:]}" #\t(...{__file__[-32:]})"

def register():
    DEV.log_msg(f"{_name}", {"ADDON", "INIT", "REG"})

    # Class declaration cannot be dynamic, so could assert afterwards
    #assert(MW_prefs.bl_idname == ADDON._bl_info["name"])
    assert(MW_prefs.bl_idname == ADDON._bl_name)

    for cls in classes:
        bpy.utils.register_class(cls)

    # keeping the pane with visual settings up to date
    getPrefs().mw_vis.nbl_prefsProxy = True
    MW_global_selected.callback_rootChange_actions.append(MW_prefs.mw_vis_newSelected_update)

def unregister():
    DEV.log_msg(f"{_name}", {"ADDON", "INIT", "UN-REG"})

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    MW_global_selected.callback_rootChange_actions.remove(MW_prefs.mw_vis_newSelected_update)

DEV.log_msg(f"{_name}", {"ADDON", "PARSED"})