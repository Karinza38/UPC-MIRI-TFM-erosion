import bpy
import bpy.types as types
import bpy.props as props
from mathutils import Vector, Matrix
from math import ceil

from .preferences import getPrefs, ADDON

from . import ui
from . import utils, utils_scene, utils_trans, utils_geo, utils_mat, utils_mesh
from . import utils_mat
from .utils_dev import DEV
from .stats import getStats


# Misc utility operators (dimateos)
#-------------------------------------------------------------------

class _StartRefresh_OT(types.Operator):
    """ Common operator class with start/end messages/stats + controlled refresh """
    bl_idname = "__to_override__"
    """ Op bl_idname must be undercase and one . (and only one)"""

    bl_options = {'INTERNAL'}
    """ Op bl_options INTERNAL supposedly hides the operator from search"""

    def __init__(self, init_log = False) -> None:
        """ Seems like is called before invoke """
        super().__init__()
        # to be configured per class / from outside before execution
        self.invoke_log         = False
        self.refresh_log        = False
        self.init_log           = init_log
        self.start_resetStats   = True
        self.start_resetLog     = False
        self.start_logEmptyLine = True
        self.start_log          = True
        self.start_logStats     = False
        self.end_logEmptyLine   = True
        self.end_log            = False
        self.end_logStats       = True

        if self.init_log:
            DEV.log_msg(f"init ({self.bl_idname})", {'OP_FLOW'})

    #-------------------------------------------------------------------
    # common flow

    def draw(self, context: types.Context):
        """ Runs about 2 times after execution / panel open / mouse over moved """
        #super().draw(context)
        ui.draw_refresh(self, self.layout)

    def invoke(self, context, event):
        """ Runs only once on operator call """
        if self.invoke_log:
            DEV.log_msg(f"invoke ({self.bl_idname})", {'OP_FLOW'})

        # refresh at least once
        self.meta_refresh = True
        return self.execute(context)
        #return super().invoke(context, event)

    def execute(self, context: types.Context):
        """ Runs once and then after every property edit in the edit last action panel """
        # sample flow to be overwritten:
        self.start_op()

        if self.checkRefresh_return():
            return self.end_op_refresh()

        error = False
        if error:
            return self.end_op_error()

        return self.end_op()

    #-------------------------------------------------------------------
    # common refresh handling

    meta_refresh: props.BoolProperty(
        name="Refresh", description="Refresh once on click",
        default=False,
    )
    meta_auto_refresh: props.BoolProperty(
        name="Auto-Refresh", description="Automatic refresh",
        default=True,
    )

    def checkRefresh_cancel(self):
        """ Checks and updates auto/refresh state, returns True when there is no need to continue exec """
        if self.refresh_log:
            DEV.log_msg(f"execute auto_refresh:{self.meta_auto_refresh} refresh:{self.meta_refresh}", {'OP_FLOW'})

        # cancel op exec
        if not self.meta_refresh and not self.meta_auto_refresh:
            return True
        self.meta_refresh = False
        return False

    #-------------------------------------------------------------------
    # common log+stats

    def start_op(self, msg="", skipLog=False, skipStats=False):
        """ Default exit flow at the start of execution """
        stats = getStats()
        if self.start_resetStats and not skipStats:
            stats.reset(log=self.start_resetLog)
        #stats.testStats()
        if self.start_logEmptyLine: print()

        if self.start_log and not skipLog:
            if not msg: msg= f"{self.bl_label}"
            DEV.log_msg_sep()
            DEV.log_msg(f"Op START: {msg} ({self.bl_idname})", {'OP_FLOW'})

        if self.start_logStats: stats.logDt(f"timing: ({self.bl_idname})...")

    def end_op(self, msg="", skipLog=False, retPass=False, cancel= False):
        """ Default exit flow at the end of execution """
        if self.end_log:
            if not msg: msg= f"{self.bl_label}"
            DEV.log_msg(f"Op END: {msg} ({self.bl_idname})", {'OP_FLOW'})

        if self.end_logStats and not skipLog:
            getStats().logFull(f"finished: ({self.bl_idname})...")

        if self.end_logEmptyLine: print()
        if cancel: return {"CANCELLED"}
        return {"FINISHED"} if not retPass else {'PASS_THROUGH'}

    def end_op_error(self, msg = "", skipLog=False, retPass=False):
        """ Default exit flow after an error """
        self.logReport(f"Op FAILED: {msg}", {'ERROR'})
        if not msg: msg= f"failed execution"
        return self.end_op(msg, skipLog, retPass)

    def end_op_refresh(self, msg = "", skipLog=True, retPass=True):
        """ Default exit flow after a cancelled refresh """
        if not msg: msg= f"cancel execution (refresh)"
        return self.end_op(msg, skipLog, retPass)

    def cancel_op(self, msg = "", skipLog=False):
        """ Cancel operator, quit the edit last op window """
        self.logReport(f"Op CANCELLED: {msg}", {'ERROR'})
        if not msg: msg= f"cancel execution"
        return self.end_op(msg, skipLog, cancel=True)

    def logReport(self, msg, rtype = {'WARNING'}):
        """ blender rtype of kind INFO, WARNING or ERROR"""
        # check valid blender type
        if rtype & { "INFO", "WARNING", "ERROR" } == {}:
            DEV.log_msg(f"{msg} (report-FAIL)", rtype)

        else:
            # blender pop up that shows the message
            self.report(rtype, f"{msg}")
            # regular log no need as report also shows up in terminal
            #DEV.log_msg(f"{msg} (report)", rtype)


#-------------------------------------------------------------------

class Util_spawnIndices_OT(_StartRefresh_OT):
    bl_idname = "dm.util_spawn_indices"
    bl_label = "Spawn mesh indices"
    bl_description = "Spawn named objects at mesh data indices positons"

    # REGISTER + UNDO pops the edit last op window
    bl_options = {"PRESET", 'REGISTER', 'UNDO'}

    def draw(self, context: types.Context):
        super().draw(context)
        self.draw_menu()

    #-------------------------------------------------------------------

    class CONST_NAMES:
        empty = "spawn_Indices"
        verts = "verts_Indices"
        edges = "edges_Indices"
        faces = "faces_Indices"

    use_index_filter: props.BoolProperty(
        name="filter", description="Limit the data spawned with the filter",
        default=True,
    )
    index_filter: props.StringProperty(
        name="idx", description="Range '2_20' (20 not included). Specifics '2,6,7'. Both '0_10,-1' ('-' for negative indices)",
        default="0_100,-1",
    )
    obj_replace: props.BoolProperty(
        name="obj replace", description="Replace existing mesh index indicators",
        default=True,
    )

    # toggles and scale per data
    _prop_showName = props.BoolProperty(name="name", description="Toggle viewport vis of names", default=False)
    _prop_scale = props.FloatProperty(name="s", default=0.25, min=0.01, max=1.0, step=0.5, precision=3)
    verts_gen: props.BoolProperty(name="Verts (octa)", default=True)
    verts_name: _prop_showName
    verts_scale: _prop_scale
    edges_gen: props.BoolProperty(name="Edges (cube)", default=False)
    edges_name: _prop_showName
    edge_scale: _prop_scale
    faces_gen: props.BoolProperty(name="Faces (tetra)", default=True)
    faces_name: _prop_showName
    faces_scale: _prop_scale

    # rendering
    color_alpha: props.FloatProperty(name="color alpha", default=0.5, min=0.1, max=1.0, step=0.5)
    color_useGray: props.BoolProperty( name="grayscale", default=False)
    color_gray: props.FloatProperty(name="white", default=0.5, min=0.0, max=1.0, step=0.5)
    mesh_useShape: props.BoolProperty( name="use mesh shapes", default=True)
    mesh_scale: _prop_scale
    namePrefix: props.StringProperty(
        name="obj prefix", description="Avoid blender adding .001 to repeated objects/meshes",
        default="",
    )

    def draw_menu(self):
        col = self.layout.column()
        #col.enabled = False
        col.scale_y = 0.8
        col.label(text=f"[Overlay>Text info]: see names", icon="QUESTION")
        col.label(text=f"[Overlay>Relationship lines]: hide", icon="QUESTION")
        f1 = 0.5
        f2 = 0.5

        # data
        box = self.layout.box()
        col = box.column()
        row = col.row().split(factor=f1)
        row.prop(self, "verts_gen")
        row.prop(self, "verts_name")
        row.prop(self, "verts_scale")
        row = col.row().split(factor=f1)
        row.prop(self, "edges_gen")
        row.prop(self, "edges_name")
        row.prop(self, "edge_scale")
        row = col.row().split(factor=f1)
        row.prop(self, "faces_gen")
        row.prop(self, "faces_name")
        row.prop(self, "faces_scale")

        # filter
        row = self.layout.row().split(factor=0.8)
        row.prop(self, "index_filter")
        row.prop(self, "use_index_filter")

        # shape
        col = self.layout.column()
        row = col.row().split(factor=f2)
        row.prop(self, "mesh_useShape")
        row.prop(self, "mesh_scale", text="scale")

        # color
        box = self.layout.box()
        col = box.column()
        col.prop(self, "color_alpha")
        row = col.row().split(factor=f2)
        row.prop(self, "color_useGray")
        row.prop(self, "color_gray")

        # ui
        col = self.layout.column()
        row = col.row()
        #row = col.row().split(factor=f2)
        row.alignment = "LEFT"
        row.prop(self, "namePrefix")
        row.prop(self, "obj_replace")


    #-------------------------------------------------------------------

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.data

    def execute(self, context: types.Context):
        self.start_op()
        cancel = self.checkRefresh_cancel()
        if cancel: return self.end_op_refresh()

        obj = context.active_object
        if self.obj_replace:
            child_empty = utils_scene.gen_childReuse(obj, self.CONST_NAMES.empty, context, None, keepTrans=False)
        else: child_empty = utils_scene.get_child(obj, self.CONST_NAMES.empty)

        # optional grayscale common color mat
        gray = utils_mat.COLORS.white * self.color_gray
        gray.w = self.color_alpha
        if self.color_useGray:
            mat_gray = utils_mat.get_colorMat(gray, "spawnIndices_shared")

        # IDEA:: add more info as suffix + rename after delete so no .001 + also applied to some setup

        if self.verts_gen:
            # verts use a red octahedron for rep
            scaleV = Vector([self.verts_scale * self.mesh_scale]*3)
            if self.mesh_useShape:
                mesh = utils_mesh.SHAPES.get_octahedron(f"{self.namePrefix}.vert")
                if self.color_useGray: mat = mat_gray
                else:
                    red = utils_mat.COLORS.red+gray
                    red.w = self.color_alpha
                    mat = utils_mat.get_colorMat(red, "spawnIndices_VERT")
            else:
                mesh= None
                mat = None

            # filter input
            if not self.use_index_filter: verts = obj.data.vertices
            else: verts = utils.get_filtered(obj.data.vertices, self.index_filter)

            # spawn as children
            parent = utils_scene.gen_child(child_empty, self.CONST_NAMES.verts, context, None, keepTrans=False)
            for v in verts:
                name = f"{self.namePrefix}.v{v.index}"
                child = utils_scene.gen_child(parent, name, context, mesh, keepTrans=False)
                child.location = v.co
                child.scale = scaleV
                child.active_material = mat
                child.show_name = self.verts_name
                # orient vert out
                v_rot0: Vector = Vector([0,0,1])
                v_rot1: Vector = v.normal
                child.rotation_mode = "QUATERNION"
                child.rotation_quaternion = v_rot0.rotation_difference(v_rot1)

        if self.edges_gen:
            # edges use a green cuboid  for rep
            scaleV = Vector([self.edge_scale * self.mesh_scale]*3)
            if self.mesh_useShape:
                mesh = utils_mesh.SHAPES.get_cuboid(f"{self.namePrefix}.edge")
                if self.color_useGray: mat = mat_gray
                else:
                    green = utils_mat.COLORS.green+gray
                    green.w = self.color_alpha
                    mat = utils_mat.get_colorMat(green, "spawnIndices_EDGE")
            else:
                mesh= None
                mat = None

            # filter input
            if not self.use_index_filter: edges = obj.data.edges
            else: edges = utils.get_filtered(obj.data.edges, self.index_filter)

            # spawn as children
            parent = utils_scene.gen_child(child_empty, self.CONST_NAMES.edges, context, None, keepTrans=False)
            for e in edges:
                name = f"{self.namePrefix}.e{e.index}"
                child = utils_scene.gen_child(parent, name, context, mesh, keepTrans=False)
                child.location = utils_geo.edge_center(obj.data, e)
                child.scale = scaleV
                child.active_material = mat
                child.show_name = self.edges_name
                # orient edge along
                v_rot0: Vector = Vector([0,0,1])
                v_rot1: Vector = utils_geo.edge_dir(obj.data, e)
                child.rotation_mode = "QUATERNION"
                child.rotation_quaternion = v_rot0.rotation_difference(v_rot1)

        if self.faces_gen:
            # faces use a blue tetrahedron for rep
            scaleV = Vector([self.faces_scale * self.mesh_scale]*3)
            if self.mesh_useShape:
                mesh = utils_mesh.SHAPES.get_tetrahedron(f"{self.namePrefix}.face")
                if self.color_useGray: mat = mat_gray
                else:
                    blue = utils_mat.COLORS.blue+gray
                    blue.w = self.color_alpha
                    mat = utils_mat.get_colorMat(blue, "spawnIndices_FACE")
            else:
                mesh= None
                mat = None

            # filter input
            if not self.use_index_filter: faces = obj.data.polygons
            else: faces = utils.get_filtered(obj.data.polygons, self.index_filter)

            # spawn as children
            parent = utils_scene.gen_child(child_empty, self.CONST_NAMES.faces, context, None, keepTrans=False)
            for f in faces:
                name = f"{self.namePrefix}.f{f.index}"
                child = utils_scene.gen_child(parent, name, context, mesh, keepTrans=False)
                child.location = f.center + f.normal*0.1*scaleV[0]
                child.scale = scaleV
                child.active_material = mat
                child.show_name = self.faces_name
                # orient face out
                v_rot0: Vector = Vector([0,0,1])
                v_rot1: Vector = f.normal
                child.rotation_mode = "QUATERNION"
                child.rotation_quaternion = v_rot0.rotation_difference(v_rot1)

        #bpy.ops.dm.util_delete_meshes()
        return self.end_op()

class Util_deleteIndices_OT(_StartRefresh_OT):
    bl_idname = "dm.util_delete_indices"
    bl_label = "Delete spawned indices"
    bl_description = "Instead of Blender 'delete hierarchy' which seems to fail to delete all recusively..."

    # UNDO as part of bl_options will cancel any edit last operation pop up
    bl_options = {'INTERNAL', 'UNDO'}
    _obj:types.Object = None

    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False

        # look for the child
        obj = utils_scene.get_child(context.active_object, Util_spawnIndices_OT.CONST_NAMES.empty)

        Util_deleteIndices_OT._obj = obj
        return obj

    def execute(self, context: types.Context):
        self.start_op()
        obj = Util_deleteIndices_OT._obj
        utils_scene.delete_objectRec(obj, logAmount=True)
        return self.end_op()

#-------------------------------------------------------------------

class Util_deleteOrphanData_OT(_StartRefresh_OT):
    bl_idname = "dm.util_delete_meshes"
    bl_label = "Delete unused meshes"
    bl_description = "Misuse of the API may lead to orphan meshes"
    bl_options = {'INTERNAL'}

    def execute(self, context: types.Context):
        self.start_op()
        collections = getPrefs().dm_prefs.orphans_collection.split(",")
        utils_scene.delete_orphanData(collections, logAmount=True)
        return self.end_op()

#-------------------------------------------------------------------

class Info_printMatrices_OT(types.Operator):
    bl_idname = "dm.info_print_matrices"
    bl_label = "Print obj matrices"
    bl_description = "DEBUG print in the console the matrices etc"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return obj

    def execute(self, context: types.Context):
        obj = bpy.context.active_object
        DEV.log_msg_sep()
        utils_trans.trans_printMatrices(obj)
        return {'FINISHED'}

class Info_printData_OT(types.Operator):
    bl_idname = "dm.info_print_data"
    bl_label = "Print mesh data"
    bl_description = "DEBUG print in the console some mesh data etc"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context: types.Context):
        obj = bpy.context.active_object
        from . import info_mesh
        DEV.log_msg_sep()
        info_mesh.desc_mesh_data(obj.data)
        return {'FINISHED'}

class Info_printQueries_OT(types.Operator):
    bl_idname = "dm.info_print_queries"
    bl_label = "Print mesh queries"
    bl_description = "DEBUG print in the console some mesh queries etc"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context: types.Context):
        obj = bpy.context.active_object
        DEV.log_msg_sep()
        utils_geo.queryLogAll_mesh(obj.data)
        return {'FINISHED'}

class Info_printMappings_OT(types.Operator):
    bl_idname = "dm.info_print_mappings"
    bl_label = "Print mesh mappings"
    bl_description = "DEBUG print in the console mesh mappings life FtoF etc"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context: types.Context):
        obj = bpy.context.active_object
        mappings = utils_geo.get_meshDicts(obj.data)
        DEV.log_msg_sep()
        for key,m in mappings.items():
            print(f"> {key} [{len(m)}] :\n", m)
        print()
        return {'FINISHED'}

class Info_printAPI_OT(types.Operator):
    bl_idname = "dm.info_print_api"
    bl_label = "Print mesh API"
    bl_description = "DEBUG print in the console some mesh API etc"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context: types.Context):
        obj = bpy.context.active_object
        from . import info_mesh
        DEV.log_msg_sep()
        info_mesh.desc_mesh_inspect(obj.data)
        return {'FINISHED'}

#-------------------------------------------------------------------

class Debug_testColors_OT(types.Operator):
    bl_idname = "dm.debug_test_colors"
    bl_label = "DEBUG: test color props"
    bl_description = "Add a bunch of mesh and color properties"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context: types.Context):
        obj = bpy.context.active_object
        utils_mat.gen_test_colors(obj, obj.data, 0.5, "mat")
        return {'FINISHED'}

class Debug_testCode_OT(types.Operator):
    """ Test some code before creating new operators...
        # NOTE:: could go to script files, but this tests the exact same environment the extension has after loading the modules
    """
    bl_idname = "dm.debug_test_code"
    bl_label = "DEBUG: addGradient"
    bl_description = "Run TMP test code"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context: types.Context):
        #self.resistField(context)
        #self.particleSystem(context)
        self.addGradient(context)
        return {'FINISHED'}

    def particleSystem(self, context: types.Context):
        obj = context.active_object
        if not obj:
            return

        mod = obj.modifiers.new("ParticleSystem", 'PARTICLE_SYSTEM')
        system : types.ParticleSystem = obj.particle_systems[-1]

        # Seed it
        system.seed = 0

        # Config
        cfg : types.ParticleSettings = obj.particle_systems[-1].settings
        cfg.type = 'EMITTER'
        cfg.count = 5000 # high enough
        cfg.lifetime = 0
        cfg.render_type = 'HALO'
        #cfg.particle_size = 0.01

        # see distribution but lags the scene tho
        #cfg.show_unborn = True

        # Source
        cfg.emit_from = "VOLUME"
        ## random
        #cfg.distribution = "RAND"
        #cfg.use_emit_random = True
        #cfg.use_even_distribution = True
        # grid? whatever is used many end up outside
        cfg.distribution = "GRID"
        bb, bb_center, bb_radius = utils_trans.get_bb_data(obj, worldSpace=True)
        cfg.grid_resolution = ceil(bb_radius) *5
        cfg.grid_random = 0

    def resistField(self, context: types.Context):
        side = 12
        sideResV = 100
        name = "TestGrid"
        trans = Matrix.Translation(Vector([0,4,0]))

        # Create a new grid mesh
        from . import sv_geom_primitives
        mesh = bpy.data.meshes.new(name)
        verts, edges, faces = sv_geom_primitives.grid(side,side,sideResV,sideResV)
        utils_trans.transform_points(verts, trans)
        mesh.from_pydata(verts, edges, faces)
        obj = bpy.data.objects.new(name, mesh)
        context.scene.collection.objects.link(obj)

        from . import mw_resistance
        rest_colors = [ mw_resistance.get2D_color4D(v.co.x, v.co.y) for v in mesh.vertices ]
        utils_mat.gen_meshAttr(mesh, rest_colors, 1, "FLOAT_COLOR", "POINT", "resistance")

    def addGradient(self, context: types.Context):
        # Add UV coordinates
        obj = context.active_object
        if not obj and obj.type != "MESH":
            return

        # Clean UV and generate a new one
        mesh: types.Mesh = obj.data
        utils_mat.delete_meshUV(mesh)
        uv = utils_mat.gen_meshUV(mesh, [Vector([0.0, 0.9])], name="UV_life") # [Vector([0.2, 0.2]), Vector([0.5, 0.5]), Vector([0.8, 0.8])]

        # Create a new image
        width = 256
        height = 256
        image = bpy.data.images.new(name="RedGradient", width=width, height=height)

        # Create a NumPy array to store the image data
        import numpy as np
        pixels = np.empty(width * height * 4, dtype=np.float32)
        for y in range(height):
            for x in range(width):
                # Calculate the red value based on the Y position (top to bottom gradient)
                red = y / (height - 1)
                # Set the pixel values (RGBA)
                index = (y * width + x) * 4
                pixels[index] = red
                pixels[index + 1] = 0.0
                pixels[index + 2] = 0.0
                pixels[index + 3] = 1.0

        # Flatten the NumPy array and assign it to the image
        image.pixels = pixels.tolist()

        # Create a new material and add it
        mat = bpy.data.materials.new(name="GradientMaterial")
        obj.active_material = mat

        # Cfg default nodes
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        for node in nodes: nodes.remove(node)

        # Add a ShaderNodeTexImage node
        texture_node = nodes.new(type='ShaderNodeTexImage')
        texture_node.location = (0, 0)
        texture_node.image = image

        # Add an Input node for UV coordinates
        uv_map_node = nodes.new(type='ShaderNodeUVMap')
        uv_map_node.location = (-200, 0)
        uv_map_node.uv_map = "UVMap"  # Replace with the name of your UV map if needed

        # Add an Output node
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (400, 0)

        # Connect the nodes
        mat.node_tree.links.new(uv_map_node.outputs['UV'], texture_node.inputs['Vector'])
        mat.node_tree.links.new(texture_node.outputs['Color'], output_node.inputs['Surface'])


#-------------------------------------------------------------------
# Blender events

util_classes_op = [
    Util_spawnIndices_OT,
    Util_deleteIndices_OT,

    Util_deleteOrphanData_OT,

    Info_printMatrices_OT,
    Info_printData_OT,
    Info_printQueries_OT,
    Info_printMappings_OT,
    Info_printAPI_OT,

    Debug_testColors_OT,
    Debug_testCode_OT,
]