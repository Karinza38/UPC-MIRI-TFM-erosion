import bpy.types as types
from mathutils import Vector, Matrix
INF_FLOAT = float("inf")

from .mw_cont import MW_Container, ERROR_IDX, link_key_t

from . import utils
import networkx as nx
from . import mw_resistance
from .utils_dev import DEV
from .stats import getStats

#-------------------------------------------------------------------

# OPT:: could use a class or an array of props? pyhton already slow so ok class?
# IDEA:: augmented cell class instead of array of props? cont -> cell -> link... less key map indirections
class Link():
    def __init__(self, col: "MW_Links", key_cells: link_key_t, key_faces: tuple[int, int], pos_world:Vector, dir_world:Vector, face_area:float, airLink=False):
        # no directionality but tuple key instead of set
        self.key_cells : link_key_t       = key_cells
        self.key_faces : link_key_t       = key_faces
        self.collection: "MW_Links" = col

        # neighs populated afterwards
        self.neighs_Cell_Cell: list[Link] = list()
        self.neighs_Air_Cell: list[Link] = list()
        self.neighs_error : list[link_key_t] = list()

        # sim props
        self.airLink_initial = airLink
        self.reset()

        # properties in world space?
        # IDEA:: ref to face to draw exaclty at it?
        self.pos = pos_world
        self.dir = dir_world
        self.area = face_area
        self.areaFactor = 1.0

        #self.resistance = 0.5 + 0.5* mw_resistance.get2D(self.pos.x, self.pos.y)
        self.resistance = mw_resistance.get2D(self.pos.x, self.pos.y)

    def __str__(self):
        s = f"k{utils.link_key_to_string(self.key_cells)} a({self.areaFactor:.3f},{self.area:.3f}) life({self.life:.3f},{self.picks})"
        if self.airLink_initial:
            s += f" [AIR-WALL] dir{self.dir.to_tuple(2)}"
        elif self.airLink: s += f" [AIR]"
        return s

    #-------------------------------------------------------------------
    # TODO:: set life etc to trigger reliving links? changing dynamic lists etc

    def degrade(self, deg):
        """ Degrade link life """
        self.picks +=1
        self.life -= deg
        #self.clamp()

    @property
    def life_clamped(self):
        """ Get link life clamped [0,1] """
        return min( max(self.life, 0), 1)

    def clamp(self):
        """ Clamp link life [0,1] """
        self.life = self.life_clamped

    def reset(self, life=1.0):
        """ Reset simulation parameters """
        self.life = life
        self.airLink = self.airLink_initial
        self.picks : int = 0

    #-------------------------------------------------------------------

    def __len__(self):
        return len(self.neighs_Cell_Cell) + len(self.neighs_Air_Cell)

    def setNeighs(self, newNeighsKeys:list[link_key_t]):
        """ Clear and add links """
        self.neighs_Cell_Cell.clear()
        self.neighs_Air_Cell.clear()
        self.neighs_error.clear()
        self.addNeighs(newNeighsKeys)

    def addNeighs(self, newNeighsKeys:list[link_key_t]):
        """ Classify by key and add queried links to the respective neigh list """
        for kn in newNeighsKeys:
            if   kn[0] in ERROR_IDX.all: self.neighs_error.append(kn)
            elif kn[0] < 0                  : self.neighs_Air_Cell.append(self.collection.link_map[kn])
            else                            : self.neighs_Cell_Cell.append(self.collection.link_map[kn])

#-------------------------------------------------------------------

class MW_Links():

    def __init__(self, cont: MW_Container):
        stats = getStats()
        self.initialized = False
        """ Set to true after succesfully computed the link map """

        self.cells_graph = nx.Graph()
        """ Graph connecting the cells to find connected components """
        self.comps = []
        """ List of sets with connected components cells id """
        self.cells_graph.add_nodes_from(cont.foundId)

        self.link_map: dict[link_key_t, Link] = dict()
        """ Static global link map storage, indexed by key with no repetitions """

        self.external : list[Link] = list()
        """ Dynamic list of external links: AIR to CELL, mainly used as entry points in the simulation """
        self.internal : list[Link] = list()
        """ Dynamic list of internal links: CELL to CELL, mainly used for rendering of the links """

        # TODO:: accumulate pos and area to calculate relative ones later? atm informative
        # OPT:: maybe voro++ face area is faster?
        self.min_pos = Vector([INF_FLOAT]*3)
        self.max_pos = Vector([-INF_FLOAT]*3)
        self.min_area = INF_FLOAT
        self.max_area = -INF_FLOAT
        self.avg_area = 0

        # key is always sorted numerically -> negative walls id go at the beginning
        def getKey_swap(k1,k2) -> tuple[link_key_t,bool]:
            swap = k1 > k2
            key = (k1, k2) if not swap else (k2, k1)
            return key,swap
        def getKey(k1,k2, swap) -> link_key_t:
            key = (k1, k2) if not swap else (k2, k1)
            return key

        # FIRST loop to build the global dictionaries
        for idx_cell in cont.foundId:

            # XXX:: data to calculate global pos here or leave for links to do?
            obj        = cont.cells_objs[idx_cell]
            me         = cont.cells_meshes[idx_cell]
            m_toWorld  = utils.get_worldMatrix_unscaled(obj, update=True)
            mn_toWorld = utils.get_normalMatrix(m_toWorld)

            # iterate all faces including asymmetry placeholders (missing cells already ignored with cont_foundId)
            for idx_face, idx_neighCell in enumerate(cont.neighs[idx_cell]):

                # skip asymmetric (already prefilled keys_perCell)
                if idx_neighCell in ERROR_IDX.all:
                    continue

                # get world props
                face: types.MeshPolygon = me.polygons[idx_face]
                pos = m_toWorld @ face.center
                if DEV.DEBUG_COMPS and abs(pos.x) < 0.5: continue
                normal = mn_toWorld @ face.normal
                area = face.area
                # NOTE:: rotated normals may potentially have a length of 1.0 +- 1e-8 but not worth normalizing
                #DEV.log_msg(f"face.normal {face.normal} (l: {face.normal.length}) -> world {normal} (l: {normal.length})", cut=False)

                # check min/max
                if self.min_pos.x > pos.x: self.min_pos.x = pos.x
                elif self.max_pos.x < pos.x: self.max_pos.x = pos.x
                if self.min_pos.y > pos.y: self.min_pos.y = pos.y
                elif self.max_pos.y < pos.y: self.max_pos.y = pos.y
                if self.min_pos.z > pos.z: self.min_pos.z = pos.z
                elif self.max_pos.z < pos.z: self.max_pos.z = pos.z
                # area too
                self.avg_area += area
                if self.min_area > area: self.min_area = area
                elif self.max_area < area: self.max_area = area

                # link to a wall, wont be repeated
                if idx_neighCell < 0:
                    key = (idx_neighCell, idx_cell)
                    key_faces = (idx_neighCell, idx_face)
                    l = Link(self, key, key_faces, pos, normal, area, airLink=True)

                    # add to mappings per wall and cell
                    self.link_map[key] = l
                    self.external.append(l)
                    cont.keys_perWall[idx_neighCell].append(key)
                    cont.keys_perCell[idx_cell][idx_face] = key
                    continue

                # check unique links between cells
                # XXX:: key does not include faces, convex cells so expected only one face conected between cells
                key,swap = getKey_swap(idx_cell, idx_neighCell)
                key_rep = key in self.link_map
                if key_rep:
                    continue

                # build the link
                idx_neighFace = cont.neighs_faces[idx_cell][idx_face]
                key_faces = getKey(idx_face, idx_neighFace, swap)
                l = Link(self, key, key_faces, pos, normal, area)

                # add to mappings for both per cells
                self.link_map[key] = l
                self.internal.append(l)
                cont.keys_perCell[idx_cell][idx_face] = key
                cont.keys_perCell[idx_neighCell][idx_neighFace] = key

                # add to graph
                self.cells_graph.add_edge(*key)

        self.avg_area /= float(len(self.link_map))

        stats.logDt(f"created link map")
        DEV.log_msg(f"Pos limits: {utils.vec3_to_string(self.min_pos)}, {utils.vec3_to_string(self.max_pos)}"
                    f" | Area limits: ({self.min_area:.2f},{self.max_area:.2f}) avg:{self.avg_area:.2f}",
                    {"CALC", "LINKS", "LIMITS"}, cut=False)

        # SECOND loop to aggregate the links neighbours, only need to iterate cont_foundId
        for idx_cell in cont.foundId:
            keys_perFace = cont.keys_perCell[idx_cell]
            for idx_face,key in enumerate(keys_perFace):
                # skip possible asymmetries
                if key[0] in ERROR_IDX.all:
                    continue

                # retrieve valid link
                l = self.link_map[key]
                #DEV.log_msg(f"l {l.key_cells} {l.key_cells}")

                # avoid recalculating link neighs (and duplicating them)
                if len(l):
                    continue

                # calculate area factor relative to avg area
                l.areaFactor = l.area / self.avg_area

                # walls only add local faces from the same cell
                if l.airLink:
                    w_neighs = cont.cells_meshes_FtoF[idx_cell][idx_face]
                    w_neighs = [ keys_perFace[f] for f in w_neighs ]
                    l.addNeighs(w_neighs)
                    continue

                # extract idx and geometry faces neighs
                c1, c2 = l.key_cells
                f1, f2 = l.key_faces
                m1_neighs = cont.cells_meshes_FtoF[c1]
                m2_neighs = cont.cells_meshes_FtoF[c2]
                f1_neighs = m1_neighs[f1]
                f2_neighs = m2_neighs[f2]

                # the key is sorted, so query the keys per cell per each one
                c1_keys = cont.keys_perCell[c1]
                c2_keys = cont.keys_perCell[c2]
                c1_neighs = [ c1_keys[f] for f in f1_neighs ]
                c2_neighs = [ c2_keys[f] for f in f2_neighs ]
                l.setNeighs(c1_neighs + c2_neighs)

        stats.logDt("aggregated link neighbours")

        self.comps = list(nx.connected_components(self.cells_graph))
        stats.logDt(f"calculated components: {len(self.comps)}")

        logType = {"CALC", "LINKS"}
        if not self.link_map: logType |= {"ERROR"}
        DEV.log_msg(f"Found {len(self.link_map)} links: {len(self.external)} external | {len(self.internal)} internal", logType)
        self.initialized = True