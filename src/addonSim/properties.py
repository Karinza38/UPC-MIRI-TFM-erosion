import bpy
import bpy.types as types
import bpy.props as props

from . import mw_setup_props

from .utils_dev import DEV


#-------------------------------------------------------------------

# dynamic source options
class MW_gen_source_options:
    all=[
        ('VERT_OWN', "Own Verts", "Use own vertices (also set by default when other options are disabled)"),
        ('VERT_CHILD', "Child Verts", "Use child object vertices"),
        ('PARTICLE_OWN', "Own Particles", "All particle systems of the source object"),
        ('PARTICLE_CHILD', "Child Particles", "All particle systems of the child objects"),
        #('PENCIL', "Pencil", "Annotation Grease Pencil (only touching/inside the volume)"),
    ]
    all_keys = [ k[0] for k in all ]
    default_key = 'PARTICLE_OWN'
    fallback_key = 'VERT_OWN'
    error_key = 'NONE'
    error_option = [ (error_key, "No point found...", f"Options: {all_keys}") ]

def source_update_items(self, context):
    items = [
        t for t in MW_gen_source_options.all
            if t[0] in self.meta_source_enabled
    ]
    if items: return items
    else: return MW_gen_source_options.error_option.copy()


# dynamic naming
def struct_nameOriginal_update(self, context):
    # NOTE:: unused example of having a per instance previous value of a property
    #if self.meta_nameOriginal_prev == self.meta_nameOriginal: return # prev val is also reset on undo tho
    self.meta_nameOriginal_prev = self.meta_nameOriginal_prevRep
    self.meta_nameOriginal_prevRep = self.struct_nameOriginal
    DEV.log_msg(f"struct_nameOriginal: {self.struct_nameOriginal} - prev: {self.meta_nameOriginal_prev}", {"CALLBACK", "CFG", "PREV"})

#-------------------------------------------------------------------

class MW_gen_cfg(types.PropertyGroup):

    # Set all available gen extractions
    meta_source_enabled: props.EnumProperty(
        name="Source all types",
        items=MW_gen_source_options.all.copy(),
        default={ MW_gen_source_options.fallback_key },
        options={'ENUM_FLAG'},
    )

    # Picked extraction method
    source: props.EnumProperty(
        name="Source", description="Available source from where to retrieve points",
        items=source_update_items, # default with numberID doesnt seem to work
        options={'ENUM_FLAG'},
    )
    source_numFound: props.IntProperty(
        name="Found points", description="Number of points found",
    )

    # mod source input points
    source_limit: props.IntProperty(
        name="Limit points", description="Limit the number of input points, 0 for unlimited",
        default=100, min=0, max=10000,
    )
    source_shuffle: props.BoolProperty(
        name="RND order", description="Shuffle input points",
        default=True,
    )
    source_noise: props.FloatProperty(
        name="RND jitter", description="Jitter input point positions",
        default=0.1, min=0.0, max=1.0, precision=2, step=1
    )

    # mod faces container shape
    shape_useConvexHull: props.BoolProperty(
        name="Convex hull", description="Apply convex hull op beforehand",
        default=True,
    )
    shape_useWalls: props.BoolProperty(
        name="Wall planes", description="Keep the object faces as container walls (kind of like boolean op)",
        default=True,
    )
    margin_box_bounds: props.FloatProperty(
        name="Margin BB", description="Additional displacement of the box normal planes.",
        default=0.1, min=0.001, max=1.0, step=1, precision=3
    )
    margin_face_bounds: props.FloatProperty(
        name="Margin F", description="Additional displacement of the face normal planes.",
        default=0.1, min=0.001, max=1.0, step=1, precision=3
    )

    #-------------------------------------------------------------------

    debug_rnd_seed: props.IntProperty(
        name="RND seed", description="Seed the random generator, -1 to unseed it",
        default=64, min=-1,
    )

    debug_precisionWalls: props.IntProperty(
        # OPT:: edit more voro configs? even recompile like with test scripts?
        name="Wall precision", description="Number of decimals used to round and cluster wall planes",
        default=4, min=0, max=10,
    )

    debug_ensure_noDoubles: props.BoolProperty(
        name="Ensure no repeated input points", description="Collapse the input point to a set of unique pointers before building the container",
        default=True,
    )

    debug_flipCellNormals: props.BoolProperty(
        name="Flip final cell normals", description="Seems like they end up reversed due to voro face ordering",
        default=True,
    )

    #-------------------------------------------------------------------

    # mod final fract object name
    struct_namePrefix: props.StringProperty(
        name="Prefix",
        default="MW",
    )
    struct_nameOriginal: props.StringProperty(
        update= struct_nameOriginal_update
    )
    meta_nameOriginal_prevRep: props.StringProperty()
    meta_nameOriginal_prev: props.StringProperty()


#-------------------------------------------------------------------
# IDEA:: min -1 for infinite break condition?

class MW_sim_cfg(types.PropertyGroup):
    step_infiltrations: props.IntProperty(
        name="Number of iters", description="WIP: atm redo each modification",
        default=1, min=1, max=1000,
    )
    step_maxDepth: props.IntProperty(
        name="Number of propagations per iter", description="WIP: atm redo each modification",
        default=10, min=0, max=100,
    )

    step_deg: props.FloatProperty(
        name="Degradation", description="WIP: flat reduction",
        default=0.25, min=0.05, max=0.75, step=1, precision=3
    )

    #-------------------------------------------------------------------

    debug_addSeed: props.IntProperty(
        name="Add random seed",
        default=0, min=0, max=100,
    )

    debug_uniformDeg: props.BoolProperty(
        name="Uniform reduction",
        default=False,
    )

    debug_trace: props.BoolProperty(
        default=True,
    )
    debug_log: props.BoolProperty(
        default=True,
    )

    #-------------------------------------------------------------------

    link_entry_minAlign: props.FloatProperty(
        default=0.1, precision=3
    )
    link_next_minAlign: props.FloatProperty(
        default=0.1, precision=3
    )

    water_baseCost: props.FloatProperty(
        default=0.01, precision=4
    )
    water_linkCost: props.FloatProperty(
        default=0.2, precision=3
    )
    water_minAbsorb_check: props.FloatProperty(
        default=0.3, precision=3
    )
    water_minAbsorb_continueProb: props.FloatProperty(
        default=0.9, precision=3
    )


#-------------------------------------------------------------------

class MW_vis_cfg(types.PropertyGroup):
    from .preferences import getPrefs

    # use prefs editor in the panel but edit the selected root
    nbl_prefsProxy: props.BoolProperty(default=False)

    #-------------------------------------------------------------------

    cell_scale: props.FloatProperty(
        name="Cell scale", description="Reduce some bits to be able to see the links better",
        default=0.75, min=0.25, max=1.0,
        update= lambda self, context: mw_setup_props.cell_scale_update(self)
    )

    cell_color: bpy.props.FloatVectorProperty(
        name="Cell color",
        default=(0.514, 0.396, 0.224, 0.75),
        size=4, min=0, max=1,
        subtype='COLOR',
        update= lambda self, context: mw_setup_props.cell_color_update(self, "cell_color", MW_vis_cfg.getPrefs().names.cells)
    )
    cell_color_air: bpy.props.FloatVectorProperty(
        name="Cell AIR color",
        default=(0, 0.7, 1, 0.05),
        size=4, min=0, max=1,
        subtype='COLOR',
        update= lambda self, context: mw_setup_props.cell_color_update(self, "cell_color_air", MW_vis_cfg.getPrefs().names.cells_air)
    )
    cell_color_core: bpy.props.FloatVectorProperty(
        name="Cell CORE color",
        default=(0.8, 0.294, 0.125, 1.0),
        size=4, min=0, max=1,
        subtype='COLOR',
        update= lambda self, context: mw_setup_props.cell_color_update(self, "cell_color_core", MW_vis_cfg.getPrefs().names.cells_core)
    )

    #-------------------------------------------------------------------

    links_smoothShade: props.BoolProperty(
        name="Link smooth shade",
        default=True,
        update= lambda self, context: mw_setup_props.links_smoothShade_update(self)
    )

    #-------------------------------------------------------------------
    # debug one are non-dynamic, only affects subsequent runs but get written to root too
    # OPT:: most could be easily dynamic but probably not worth it or jus regen all mesh

    debug_links_res: props.IntProperty(
        name="Link mesh resolution", description="Affect the number of faces per tube",
        default=0, min=-1, max=8,
        update= lambda self, context: mw_setup_props.getRoot_checkProxy_None(self, "mw_vis", "debug_links_res")
    )

    #-------------------------------------------------------------------

    links_depth: props.FloatProperty(
        name="Link depth", description="Minimun depth inside faces",
        default=0.15, min=0.01, max=0.4, step=0.05, precision=4,
        update= lambda self, context: mw_setup_props.getRoot_checkProxy_None(self, "mw_vis", "links_depth")
    )
    links_width_base: props.FloatProperty(
        name="Link width base", description="Max link w",
        default=0.05, min=0.01, max=0.2, step=0.05, precision=4,
        update= lambda self, context: mw_setup_props.getRoot_checkProxy_None(self, "mw_vis", "links_width_base")
    )
    links_width_broken: props.FloatProperty(
        name="Link width broken", description="Min link w",
        default=0.005, min=0.001, max=0.01, step=0.05, precision=4,
        update= lambda self, context: mw_setup_props.getRoot_checkProxy_None(self, "mw_vis", "links_width_broken")
    )

    links_width__mode: props.EnumProperty(
        name="Link dynamic width",
        items=(
            ('DISABLED', "Disabled", "No effect on width"),
            ('UNIFORM', "Uniform effect", "Uniform effect on width"),
            ('BINARY', "Binary", "Any differece from full life affects drastically"),
        ),
        default={'UNIFORM'},
        options={'ENUM_FLAG'},
        update= lambda self, context: mw_setup_props.getRoot_checkProxy_None(self, "mw_vis", "links_width__mode")
    )


#-------------------------------------------------------------------
# Blender events

classes = [
    MW_gen_cfg,
    MW_sim_cfg,
    MW_vis_cfg,
]
_name = f"{__name__[14:]}" #\t(...{__file__[-32:]})"

def register():
    DEV.log_msg(f"{_name}", {"ADDON", "INIT", "REG"})

    for cls in classes:
        bpy.utils.register_class(cls)

    # appear as part of default object props
    # NOTE:: only non-default values of property groups get stored in objects memory, there are optimizations

    bpy.types.Object.mw_gen = props.PointerProperty(
        type=MW_gen_cfg,
        name="MW_Generation", description="MW generation properties")

    bpy.types.Object.mw_sim = props.PointerProperty(
        type=MW_sim_cfg,
        name="MW_Simulation", description="MW simulation properties")

    bpy.types.Object.mw_vis = props.PointerProperty(
        type=MW_vis_cfg,
        name="MW_Visualization", description="MW visualization properties")

    # add as scene to overwrite default values (kind of like OP having cfg)
    # NOTE:: affected by undo stack! so better to store in prefs
    #bpy.types.Scene.mw_vis = props.PointerProperty(type=MW_vis_cfg)


def unregister():
    DEV.log_msg(f"{_name}", {"ADDON", "INIT", "UN-REG"})

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    #del bpy.types.Scene.mw_vis


DEV.log_msg(f"{_name}", {"ADDON", "PARSED"})