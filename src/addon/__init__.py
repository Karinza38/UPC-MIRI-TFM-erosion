bl_info = {
    "name": "_dimateos Cell Fracture",
    "author": "ideasman42, phymec, Sergey Sharybin",
    "version": (0, 2),
    "blender": (2, 80, 0),
    "location": "Viewport Object Menu -> Quick Effects",
    "description": "Fractured Object Creation",
    "warning": "",
    "doc_url": "{BLENDER_MANUAL_URL}/addons/object/cell_fracture.html",
    "category": "Object",
}

# TODO: older version no longer mantained...

# if "bpy" in locals():
#     import importlib
#     importlib.reload(fracture_cell_setup)

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    EnumProperty,
)

from bpy.types import Operator


def main_object(context, collection, obj, level, **kw):
    import random

    # pull out some args
    kw_copy = kw.copy()
    use_recenter = kw_copy.pop("use_recenter")
    use_remove_original = kw_copy.pop("use_remove_original")
    recursion = kw_copy.pop("recursion")
    recursion_source_limit = kw_copy.pop("recursion_source_limit")
    recursion_clamp = kw_copy.pop("recursion_clamp")
    recursion_chance = kw_copy.pop("recursion_chance")
    recursion_chance_select = kw_copy.pop("recursion_chance_select")
    use_island_split = kw_copy.pop("use_island_split")
    use_interior_vgroup = kw_copy.pop("use_interior_vgroup")
    use_sharp_edges = kw_copy.pop("use_sharp_edges")
    use_sharp_edges_apply = kw_copy.pop("use_sharp_edges_apply")

    apply_boolean = kw_copy.pop("apply_boolean")
    new_voro = kw_copy.pop("new_voro")

    scene = context.scene

    if level != 0:
        kw_copy["source_limit"] = recursion_source_limit

    from . import fracture_cell_setup

    # not essential but selection is visual distraction.
    obj.select_set(False)

    if kw_copy["use_debug_redraw"]:
        obj_display_type_prev = obj.display_type
        obj.display_type = 'WIRE'

    objects = fracture_cell_setup.cell_fracture_objects(context, collection, obj, **kw_copy)
    # WIP early exit
    if not objects: return []

    # WIP: apply_boolean just skips it
    if apply_boolean and not new_voro:
        objects = fracture_cell_setup.cell_fracture_boolean(
            context, collection, obj, objects,
            use_island_split=use_island_split,
            use_interior_hide=(use_interior_vgroup or use_sharp_edges),
            apply_boolean=apply_boolean,
            use_debug_redraw=kw_copy["use_debug_redraw"],
            level=level,
        )

    # must apply after boolean.
    if use_recenter:
        bpy.ops.object.origin_set(
            {"selected_editable_objects": objects},
            type='ORIGIN_GEOMETRY',
            center='MEDIAN',
        )

    # ----------
    # Recursion
    if level == 0:
        for level_sub in range(1, recursion + 1):

            objects_recurse_input = [(i, o) for i, o in enumerate(objects)]

            if recursion_chance != 1.0:
                from mathutils import Vector
                if recursion_chance_select == 'RANDOM':
                    random.shuffle(objects_recurse_input)
                elif recursion_chance_select in {'SIZE_MIN', 'SIZE_MAX'}:
                    objects_recurse_input.sort(key=lambda ob_pair: (
                        Vector(ob_pair[1].bound_box[0]) -
                        Vector(ob_pair[1].bound_box[6])
                    ).length_squared)
                    if recursion_chance_select == 'SIZE_MAX':
                        objects_recurse_input.reverse()
                elif recursion_chance_select in {'CURSOR_MIN', 'CURSOR_MAX'}:
                    c = scene.cursor.location.copy()
                    objects_recurse_input.sort(key=lambda ob_pair: (ob_pair[1].location - c).length_squared)
                    if recursion_chance_select == 'CURSOR_MAX':
                        objects_recurse_input.reverse()

                objects_recurse_input[int(recursion_chance * len(objects_recurse_input)):] = []
                objects_recurse_input.sort()

            # reverse index values so we can remove from original list.
            objects_recurse_input.reverse()

            objects_recursive = []
            for i, obj_cell in objects_recurse_input:
                assert(objects[i] is obj_cell)
                objects_recursive += main_object(context, collection, obj_cell, level_sub, **kw)
                if use_remove_original:
                    collection.objects.unlink(obj_cell)
                    del objects[i]
                if recursion_clamp and len(objects) + len(objects_recursive) >= recursion_clamp:
                    break
            objects.extend(objects_recursive)

            if recursion_clamp and len(objects) > recursion_clamp:
                break

    # --------------
    # Level Options
    if level == 0:
        # import pdb; pdb.set_trace()
        if use_interior_vgroup or use_sharp_edges:
            fracture_cell_setup.cell_fracture_interior_handle(
                objects,
                use_interior_vgroup=use_interior_vgroup,
                use_sharp_edges=use_sharp_edges,
                use_sharp_edges_apply=use_sharp_edges_apply,
            )

    if kw_copy["use_debug_redraw"]:
        obj.display_type = obj_display_type_prev

    # testing only!
    # obj.hide = True
    return objects


def main(context, **kw):
    import time
    t = time.time()
    objects_context = context.selected_editable_objects

    kw_copy = kw.copy()

    # mass
    mass_mode = kw_copy.pop("mass_mode")
    mass = kw_copy.pop("mass")

    # WIP collection name is more dinamic to avoid having to adjust it
    collection_name = kw_copy.pop("collection_name")
    selected_object_name = context.selected_objects[0].name

    collection = context.collection
    if collection_name:
        collection_current = collection
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            collection = bpy.data.collections.new(collection_name)

            # WIP: always global collection
            #collection_current.children.link(collection)
            bpy.context.scene.collection.children.link(collection)
        del collection_current

    objects = []
    for obj in objects_context:
        if obj.type == 'MESH':
            objects += main_object(context, collection, obj, 0, **kw_copy)

    # WIP early exit
    if not objects: return

    bpy.ops.object.select_all(action='DESELECT')
    for obj_cell in objects:
        obj_cell.select_set(True)

    # FIXME(campbell): we should be able to initialize rigid-body data.
    if mass_mode == 'UNIFORM':
        for obj_cell in objects:
            rb = obj_cell.rigid_body
            if rb is not None:
                rb.mass = mass
    elif mass_mode == 'VOLUME':
        from mathutils import Vector

        def _get_volume(obj_cell):
            def _getObjectBBMinMax():
                min_co = Vector((1000000.0, 1000000.0, 1000000.0))
                max_co = -min_co
                matrix = obj_cell.matrix_world.copy()
                for i in range(0, 8):
                    bb_vec = matrix @ Vector(obj_cell.bound_box[i])
                    min_co[0] = min(bb_vec[0], min_co[0])
                    min_co[1] = min(bb_vec[1], min_co[1])
                    min_co[2] = min(bb_vec[2], min_co[2])
                    max_co[0] = max(bb_vec[0], max_co[0])
                    max_co[1] = max(bb_vec[1], max_co[1])
                    max_co[2] = max(bb_vec[2], max_co[2])
                return (min_co, max_co)

            def _getObjectVolume():
                min_co, max_co = _getObjectBBMinMax()
                x = max_co[0] - min_co[0]
                y = max_co[1] - min_co[1]
                z = max_co[2] - min_co[2]
                volume = x * y * z
                return volume

            return _getObjectVolume()

        obj_volume_ls = [_get_volume(obj_cell) for obj_cell in objects]
        obj_volume_tot = sum(obj_volume_ls)
        if obj_volume_tot > 0.0:
            mass_fac = mass / obj_volume_tot
            for i, obj_cell in enumerate(objects):
                rb = obj_cell.rigid_body
                if rb is not None:
                    rb.mass = obj_volume_ls[i] * mass_fac
    else:
        assert(0)

    print("Done! %d objects in %.4f sec" % (len(objects), time.time() - t))


class FractureCell(Operator):
    bl_idname = "object.add_fracture_cell_objects_dimateos"
    bl_label = "Cell fracture selected mesh objects __dimateos"
    bl_options = {'PRESET', 'REGISTER', 'UNDO'}

    # -------------------------------------------------------------------------
    # Source Options
    source: EnumProperty(
        name="Source",
        items=(
            ('VERT_OWN', "Own Verts", "Use own vertices"),
            ('VERT_CHILD', "Child Verts", "Use child object vertices"),
            ('PARTICLE_OWN', "Own Particles", (
                "All particle systems of the "
                "source object"
            )),
            ('PARTICLE_CHILD', "Child Particles", (
                "All particle systems of the "
                "child objects"
            )),
            ('PENCIL', "Annotation Pencil", "Annotation Grease Pencil."),
        ),
        options={'ENUM_FLAG'},
        default={'PARTICLE_OWN'},
    )

    source_limit: IntProperty(
        name="Source Limit",
        description="Limit the number of input points, 0 for unlimited",
        min=0, max=5000,
        default=100,
    )

    source_noise: FloatProperty(
        name="Noise",
        description="Randomize point distribution",
        min=0.0, max=1.0,
        default=0.0,
    )

    cell_scale: FloatVectorProperty(
        name="Scale",
        description="Scale Cell Shape",
        size=3,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0),
    )

    # -------------------------------------------------------------------------
    # Recursion

    recursion: IntProperty(
        name="Recursion",
        description="Break shards recursively",
        min=0, max=5000,
        default=0,
    )

    recursion_source_limit: IntProperty(
        name="Source Limit",
        description="Limit the number of input points, 0 for unlimited (applies to recursion only)",
        min=0, max=5000,
        default=8,
    )

    recursion_clamp: IntProperty(
        name="Clamp Recursion",
        description=(
            "Finish recursion when this number of objects is reached "
            "(prevents recursing for extended periods of time), zero disables"
        ),
        min=0, max=10000,
        default=250,
    )

    recursion_chance: FloatProperty(
        name="Random Factor",
        description="Likelihood of recursion",
        min=0.0, max=1.0,
        default=0.25,
    )

    recursion_chance_select: EnumProperty(
        name="Recurse Over",
        items=(
            ('RANDOM', "Random", ""),
            ('SIZE_MIN', "Small", "Recursively subdivide smaller objects"),
            ('SIZE_MAX', "Big", "Recursively subdivide bigger objects"),
            ('CURSOR_MIN', "Cursor Close", "Recursively subdivide objects closer to the cursor"),
            ('CURSOR_MAX', "Cursor Far", "Recursively subdivide objects farther from the cursor"),
        ),
        default='SIZE_MIN',
    )

    # -------------------------------------------------------------------------
    # Mesh Data Options

    use_smooth_faces: BoolProperty(
        name="Smooth Interior",
        description="Smooth Faces of inner side",
        default=False,
    )

    use_sharp_edges: BoolProperty(
        name="Sharp Edges",
        description="Set sharp edges when disabled",
        default=True,
    )

    use_sharp_edges_apply: BoolProperty(
        name="Apply Split Edge",
        description="Split sharp hard edges",
        default=True,
    )

    use_data_match: BoolProperty(
        name="Match Data",
        description="Match original mesh materials and data layers",
        default=True,
    )

    use_island_split: BoolProperty(
        name="Split Islands",
        description="Split disconnected meshes",
        default=True,
    )

    margin_cell: FloatProperty(
        name="Margin cell (unused?)",
        description="Gaps for the fracture between cells (gives more stable physics)",
        min=0.0, max=1.0,
        default=0.001,
    )
    margin_bounds: FloatProperty(
        name="Margin bounds",
        description="Additional displacement of the face normal planes",
        min=0.0, max=1.0,
        default=0.05,
    )

    material_index: IntProperty(
        name="Material",
        description="Material index for interior faces",
        default=0,
    )

    use_interior_vgroup: BoolProperty(
        name="Interior VGroup",
        description="Create a vertex group for interior verts",
        default=False,
    )

    # -------------------------------------------------------------------------
    # Physics Options

    mass_mode: EnumProperty(
        name="Mass Mode",
        items=(
            ('VOLUME', "Volume", "Objects get part of specified mass based on their volume"),
            ('UNIFORM', "Uniform", "All objects get the specified mass"),
        ),
        default='VOLUME',
    )

    mass: FloatProperty(
        name="Mass",
        description="Mass to give created objects",
        min=0.001, max=1000.0,
        default=1.0,
    )

    # -------------------------------------------------------------------------
    # Object Options

    use_recenter: BoolProperty(
        name="Recenter",
        description="Recalculate the center points after splitting",
        default=True,
    )

    use_remove_original: BoolProperty(
        name="Remove Original -> mid recursive parents",
        description="Removes the parents used to create the shatter -> More like the intermidiate recursive parents",
        default=True,
    )

    # -------------------------------------------------------------------------
    # Scene Options
    #
    # .. different from object options in that this controls how the objects
    #    are setup in the scene.

    collection_name: StringProperty(
        name="Collection",
        description=(
            "Create objects in a collection "
            "(use existing or create new)"
        ),
        default="_fracture",
    )

    # -------------------------------------------------------------------------
    # Debug
    new_voro: BoolProperty(
        name="Use new method with voro++",
        default=True,
    )

    use_debug_points: BoolProperty(
        name="Debug Points",
        description="Create mesh data showing the points used for fracture",
        default=True,
    )

    use_debug_redraw: BoolProperty(
        name="Show Progress Realtime",
        description="Redraw as fracture is done",
        default=False,
    )

    apply_boolean: BoolProperty(
        name="Apply Boolean mod (old method)",
        default=False,
    )

    # -------------------------------------------------------------------------
    # blender ops

    def execute(self, context):
        keywords = self.as_keywords()  # ignore=("blah",)

        main(context, **keywords)

        return {'FINISHED'}

    def invoke(self, context, event):
        # print(self.recursion_chance_select)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        col.label(text="Point Source")
        rowsub = col.row()
        rowsub.prop(self, "source")
        rowsub = col.row()
        rowsub.prop(self, "source_limit")
        rowsub.prop(self, "source_noise")
        rowsub = col.row()
        rowsub.prop(self, "cell_scale")

        #box = layout.box()
        #col = box.column()
        #col.label(text="Recursive Shatter")
        #rowsub = col.row(align=True)
        #rowsub.prop(self, "recursion")
        #rowsub.prop(self, "recursion_source_limit")
        #rowsub.prop(self, "recursion_clamp")
        #rowsub = col.row()
        #rowsub.prop(self, "recursion_chance")
        #rowsub.prop(self, "recursion_chance_select", expand=True)

        #box = layout.box()
        #col = box.column()
        #col.label(text="Mesh Data")
        #rowsub = col.row()
        #rowsub.prop(self, "use_smooth_faces")
        #rowsub.prop(self, "use_sharp_edges")
        #rowsub.prop(self, "use_sharp_edges_apply")
        #rowsub.prop(self, "use_data_match")
        #rowsub = col.row()

        # on same row for even layout but in fact are not all that related
        rowsub.prop(self, "material_index")
        rowsub.prop(self, "use_interior_vgroup")

        # could be own section, control how we subdiv
        rowsub.prop(self, "use_island_split")

        box = layout.box()
        col = box.column()
        col.label(text="Margins")
        rowsub = col.row(align=True)
        rowsub.prop(self, "margin_bounds")
        rowsub.prop(self, "margin_cell")

        #box = layout.box()
        #col = box.column()
        #col.label(text="Physics")
        #rowsub = col.row(align=True)
        #rowsub.prop(self, "mass_mode")
        #rowsub.prop(self, "mass")

        box = layout.box()
        col = box.column()
        col.label(text="Object")
        rowsub = col.row(align=True)
        rowsub.prop(self, "use_recenter")
        rowsub = col.row(align=True)
        rowsub.prop(self, "use_remove_original")

        box = layout.box()
        col = box.column()
        col.label(text="Scene")
        rowsub = col.row(align=True)
        rowsub.prop(self, "collection_name")

        box = layout.box()
        col = box.column()
        col.label(text="Debug")
        rowsub = col.row(align=True)
        rowsub.prop(self, "new_voro")
        #rowsub.prop(self, "use_debug_redraw")
        rowsub.prop(self, "apply_boolean")
        rowsub.prop(self, "use_debug_points")


def menu_func(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("object.add_fracture_cell_objects_dimateos", text="Cell Fracture _dimateos")


def register():
    print("register frac")
    bpy.utils.register_class(FractureCell)
    bpy.types.VIEW3D_MT_object_quick_effects.append(menu_func)


def unregister():
    print("unregister frac")
    bpy.utils.unregister_class(FractureCell)
    bpy.types.VIEW3D_MT_object_quick_effects.remove(menu_func)


if __name__ == "__main__":
    register()
