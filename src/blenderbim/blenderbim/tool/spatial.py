# BlenderBIM Add-on - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>
#
# This file is part of BlenderBIM Add-on.
#
# BlenderBIM Add-on is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BlenderBIM Add-on is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BlenderBIM Add-on.  If not, see <http://www.gnu.org/licenses/>.

import bpy
import bmesh
import shapely
import ifcopenshell
import blenderbim.core.tool
import blenderbim.core.root
import blenderbim.core.spatial
import blenderbim.core.geometry
import blenderbim.tool as tool
import json
from math import pi
from mathutils import Vector, Matrix
from shapely import Polygon, MultiPolygon

class Spatial(blenderbim.core.tool.Spatial):
    @classmethod
    def can_contain(cls, structure_obj, element_obj):
        structure = tool.Ifc.get_entity(structure_obj)
        element = tool.Ifc.get_entity(element_obj)
        if not structure or not element:
            return False
        if tool.Ifc.get_schema() == "IFC2X3":
            if not structure.is_a("IfcSpatialStructureElement"):
                return False
        else:
            if not structure.is_a("IfcSpatialStructureElement") and not structure.is_a(
                "IfcExternalSpatialStructureElement"
            ):
                return False
        if not hasattr(element, "ContainedInStructure"):
            return False
        return True

    @classmethod
    def can_reference(cls, structure, element):
        if not structure or not element:
            return False
        if tool.Ifc.get_schema() == "IFC2X3":
            if not structure.is_a("IfcSpatialStructureElement"):
                return False
        else:
            if not structure.is_a("IfcSpatialElement"):
                return False
        if not hasattr(element, "ReferencedInStructures"):
            return False
        return True

    @classmethod
    def disable_editing(cls, obj):
        obj.BIMObjectSpatialProperties.is_editing = False

    @classmethod
    def duplicate_object_and_data(cls, obj):
        new_obj = obj.copy()
        if obj.data:
            new_obj.data = obj.data.copy()
        return new_obj

    @classmethod
    def enable_editing(cls, obj):
        obj.BIMObjectSpatialProperties.is_editing = True

    @classmethod
    def get_container(cls, element):
        return ifcopenshell.util.element.get_container(element)

    @classmethod
    def get_decomposed_elements(cls, container):
        return ifcopenshell.util.element.get_decomposition(container)

    @classmethod
    def get_object_matrix(cls, obj):
        return obj.matrix_world

    @classmethod
    def get_relative_object_matrix(cls, target_obj, relative_to_obj):
        return relative_to_obj.matrix_world.inverted() @ target_obj.matrix_world

    @classmethod
    def import_containers(cls, parent=None):
        props = bpy.context.scene.BIMSpatialProperties
        props.containers.clear()

        if not parent:
            parent = tool.Ifc.get().by_type("IfcProject")[0]

        props.active_container_id = parent.id()

        for rel in parent.IsDecomposedBy or []:
            related_objects = []
            for element in rel.RelatedObjects:
                related_objects.append((element, ifcopenshell.util.placement.get_storey_elevation(element)))
            related_objects = sorted(related_objects, key=lambda e: e[1])
            for element in related_objects:
                element = element[0]
                new = props.containers.add()
                new.name = element.Name or "Unnamed"
                new.long_name = element.LongName or ""
                new.has_decomposition = bool(element.IsDecomposedBy)
                new.ifc_definition_id = element.id()
                new.elevation = element[1]

    @classmethod
    def run_root_copy_class(cls, obj=None):
        return blenderbim.core.root.copy_class(tool.Ifc, tool.Collector, tool.Geometry, tool.Root, obj=obj)

    @classmethod
    def run_spatial_assign_container(cls, structure_obj=None, element_obj=None):
        return blenderbim.core.spatial.assign_container(
            tool.Ifc, tool.Collector, tool.Spatial, structure_obj=structure_obj, element_obj=element_obj
        )

    @classmethod
    def select_object(cls, obj):
        obj.select_set(True)

    @classmethod
    def set_active_object(cls, obj):
        bpy.context.view_layer.objects.active = obj
        cls.select_object(obj)

    @classmethod
    def set_relative_object_matrix(cls, target_obj, relative_to_obj, matrix):
        target_obj.matrix_world = relative_to_obj.matrix_world @ matrix

    @classmethod
    def select_products(cls, products, unhide=False):
        bpy.ops.object.select_all(action="DESELECT")
        for product in products:
            obj = tool.Ifc.get_object(product)
            if obj and bpy.context.view_layer.objects.get(obj.name):
                obj.select_set(True)
                if unhide:
                    obj.hide_set(False)

    @classmethod
    def filter_products(cls, products, action):
        objects = [tool.Ifc.get_object(product) for product in products if tool.Ifc.get_object(product)]
        if action == "select":
            [obj.select_set(True) for obj in objects]
        elif action == "isolate":
            [obj.hide_set(False) for obj in objects if bpy.context.view_layer.objects.get(obj.name)]
            [
                obj.hide_set(True)
                for obj in bpy.context.visible_objects
                if not obj in objects and bpy.context.view_layer.objects.get(obj.name)
            ]  # this is slow
        elif action == "unhide":
            [obj.hide_set(False) for obj in objects if bpy.context.view_layer.objects.get(obj.name)]
        elif action == "hide":
            [obj.hide_set(True) for obj in objects if bpy.context.view_layer.objects.get(obj.name)]

    @classmethod
    def deselect_objects(cls):
        [obj.select_set(False) for obj in bpy.context.selected_objects]
        # bpy.ops.object.select_all(action='DESELECT')

    @classmethod
    def show_scene_objects(cls):
        [
            obj.hide_set(False)
            for obj in bpy.data.scenes["Scene"].objects
            if bpy.context.view_layer.objects.get(obj.name)
        ]

    @classmethod
    def get_selected_products(cls):
        for obj in bpy.context.selected_objects:
            entity = tool.Ifc.get_entity(obj)
            if entity and entity.is_a("IfcProduct"):
                yield entity

    @classmethod
    def get_selected_product_types(cls):
        for obj in bpy.context.selected_objects:
            entity = tool.Ifc.get_entity(obj)
            if entity and entity.is_a("IfcTypeProduct"):
                yield entity

    @classmethod
    def copy_xy(cls, src_obj, destination_obj):
        z = src_obj.location[2]
        src_obj.location = (destination_obj.location[0], destination_obj.location[1], z)

    @classmethod
    def load_container_manager(cls):
        cls.props = bpy.context.scene.BIMSpatialManagerProperties
        previous_container_index = cls.props.active_container_index
        cls.props.containers.clear()
        cls.contracted_containers = json.loads(cls.props.contracted_containers)
        cls.props.is_container_update_enabled = False
        parent = tool.Ifc.get().by_type("IfcProject")[0]

        for object in ifcopenshell.util.element.get_parts(parent) or []:
            if object.is_a("IfcSpatialElement") or object.is_a("IfcSpatialStructureElement"):
                cls.create_new_storey_li(object, 0)
        cls.props.is_container_update_enabled = True
        # triggers spatial manager props setup
        cls.props.active_container_index = min(previous_container_index, len(cls.props.containers) - 1)

    @classmethod
    def create_new_storey_li(cls, element, level_index):
        si_conversion = ifcopenshell.util.unit.calculate_unit_scale(tool.Ifc.get())
        new = cls.props.containers.add()
        new.name = element.Name or "Unnamed"
        new.long_name = element.LongName or ""
        new.has_decomposition = bool(element.IsDecomposedBy)
        new.ifc_definition_id = element.id()
        new.elevation = ifcopenshell.util.placement.get_storey_elevation(element) * si_conversion

        new.is_expanded = element.id() not in cls.contracted_containers
        new.level_index = level_index
        if new.has_decomposition:
            new.has_children = True
            if new.is_expanded:
                for related_object in ifcopenshell.util.element.get_parts(element) or []:
                    if related_object.is_a("IfcSpatialElement") or related_object.is_a("IfcSpatialStructureElement"):
                        cls.create_new_storey_li(related_object, level_index + 1)

    @classmethod
    def edit_container_attributes(cls, entity):
        obj = tool.Ifc.get_object(entity)
        blenderbim.core.geometry.edit_object_placement(tool.Ifc, tool.Geometry, tool.Surveyor, obj=obj)
        name = bpy.context.scene.BIMSpatialManagerProperties.container_name
        if name != entity.Name:
            cls.edit_container_name(entity, name)

    @classmethod
    def edit_container_name(cls, container, name):
        tool.Ifc.run("attribute.edit_attributes", product=container, attributes={"Name": name})

    @classmethod
    def get_active_container(cls):
        props = bpy.context.scene.BIMSpatialManagerProperties
        if props.active_container_index < len(props.containers):
            container = tool.Ifc.get().by_id(props.containers[props.active_container_index].ifc_definition_id)
            return container

    @classmethod
    def contract_container(cls, container):
        props = bpy.context.scene.BIMSpatialManagerProperties
        contracted_containers = json.loads(props.contracted_containers)
        contracted_containers.append(container.id())
        props.contracted_containers = json.dumps(contracted_containers)

    @classmethod
    def expand_container(cls, container):
        props = bpy.context.scene.BIMSpatialManagerProperties
        contracted_containers = json.loads(props.contracted_containers)
        contracted_containers.remove(container.id())
        props.contracted_containers = json.dumps(contracted_containers)

#HERE STARTS SPATIAL TOOL

    @classmethod
    def get_union_shape_from_selected_objects(cls):
        selected_objects = bpy.context.selected_objects
        boundary_elements = cls.get_boundary_elements(selected_objects)
        polys = cls.get_polygons(boundary_elements)
        converted_tolerance = cls.get_converted_tolerance(tolerance=0.03)
        union = shapely.ops.unary_union(polys).buffer(converted_tolerance, cap_style=2, join_style=2)
        union = cls.get_purged_inner_holes_poly(union_geom=union, min_area=cls.get_converted_tolerance(tolerance=3))

        return union

    @classmethod
    def get_boundary_elements(cls, selected_objects):
        boundary_elements = []
        for obj in selected_objects:
            subelement = tool.Ifc.get_entity(obj)
            if subelement.is_a("IfcWall") or subelement.is_a("IfcColumn"):
                boundary_elements.append(subelement)
        return boundary_elements

    @classmethod
    def get_polygons(cls, boundary_elements):
        polys = []
        for boundary_element in boundary_elements:
            obj = tool.Ifc.get_object(boundary_element)
            if not obj:
                continue
            points = []
            base = cls.get_obj_base_points(obj)
            for index in ["low_left", "low_right", "high_right", "high_left"]:
                point = base[index]
                points.append(point)

            polys.append(Polygon(points))
        return polys

    @classmethod
    def get_obj_base_points(cls, obj):
        x_values = [(obj.matrix_world @ Vector(v)).x for v in obj.bound_box]
        y_values = [(obj.matrix_world @ Vector(v)).y for v in obj.bound_box]
        return {
            "low_left": (x_values[0], y_values[0]),
            "high_left": (x_values[3], y_values[3]),
            "low_right": (x_values[4], y_values[4]),
            "high_right": (x_values[7], y_values[7]),
        }

    @classmethod
    def get_converted_tolerance(cls, tolerance):
        model = tool.Ifc.get()
        project_unit = ifcopenshell.util.unit.get_project_unit(model, "LENGTHUNIT")
        prefix = getattr(project_unit, "Prefix", None)

        converted_tolerance = ifcopenshell.util.unit.convert(
            value=tolerance,
            from_prefix=None,
            from_unit="METRE",
            to_prefix=prefix,
            to_unit=project_unit.Name,
        )
        return tolerance

    @classmethod
    def get_purged_inner_holes_poly(cls, union_geom, min_area):
        interiors_list = []

        if union_geom.geom_type == "MultiPolygon":
            for poly in union_geom.geoms:
                interiors_list = cls.get_poly_valid_interior_list(
                    poly=poly, min_area=min_area, interiors_list=interiors_list
                )

            new_poly = Polygon(poly.exterior.coords, holes=interiors_list)

        if union_geom.geom_type == "Polygon":
            interiors_list = cls.get_poly_valid_interior_list(
                poly=union_geom, min_area=min_area, interiors_list=interiors_list
            )
            new_poly = Polygon(union_geom.exterior.coords, holes=interiors_list)

        return new_poly

    @classmethod
    def get_poly_valid_interior_list(cls, poly, min_area, interiors_list):
        for interior in poly.interiors:
            p = Polygon(interior)
            if p.area >= min_area:
                interiors_list.append(interior)
        return interiors_list

    @classmethod
    def get_buffered_poly_from_linear_ring(cls, linear_ring):
        poly = Polygon(linear_ring)
        converted_tolerance = cls.get_converted_tolerance(tolerance=0.03)
        poly = poly.buffer(converted_tolerance, single_sided=True, cap_style=2, join_style=2)
        return poly

    @classmethod
    def get_bmesh_from_polygon(cls, poly, h):
        mat = bpy.context.active_object.matrix_world
        bm = bmesh.new()
        bm.verts.index_update()
        bm.edges.index_update()

        mat_invert = mat.inverted()

        new_verts = [bm.verts.new(mat_invert @ Vector([v[0], v[1], 0])) for v in poly.exterior.coords[0:-1]]
        [bm.edges.new((new_verts[i], new_verts[i + 1])) for i in range(len(new_verts) - 1)]
        bm.edges.new((new_verts[len(new_verts) - 1], new_verts[0]))

        bm.verts.index_update()
        bm.edges.index_update()

        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.triangle_fill(bm, edges=bm.edges)
        bmesh.ops.dissolve_limit(bm, angle_limit=pi / 180 * 5, verts=bm.verts, edges=bm.edges)

        if h!=0:
            extrusion = bmesh.ops.extrude_face_region(bm, geom=bm.faces)
            extruded_verts = [g for g in extrusion["geom"] if isinstance(g, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, vec=[0.0, 0.0, h], verts=extruded_verts)

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        return bm

    @classmethod
    def get_named_obj_from_bmesh(cls, name, bmesh):
        mesh = bpy.data.meshes.new(name=name)
        bmesh.to_mesh(mesh)
        bmesh.free()
        obj = bpy.data.objects.new(name, mesh)
        mat = bpy.context.active_object.matrix_world
        obj.matrix_world = mat
        return obj

    @classmethod
    def set_obj_origin_to_bboxcenter(cls, obj):
        mat = obj.matrix_world
        inverted = mat.inverted()
        local_bbox_center = 0.125 * sum((Vector(b) for b in obj.bound_box), Vector())
        global_bbox_center = mat @ local_bbox_center

        oldLoc = obj.location
        newLoc = global_bbox_center
        diff = newLoc - oldLoc
        for vert in obj.data.vertices:
            aux_vector = mat @ vert.co
            aux_vector = aux_vector - diff
            vert.co = inverted @ aux_vector
        obj.location = newLoc

    @classmethod
    def get_active_obj_z(cls):
        x, y, z = bpy.context.active_object.matrix_world.translation.xyz
        return z

    @classmethod
    def get_active_obj_height(cls):
        height = bpy.context.active_object.dimensions.z
        return height

    @classmethod
    def traslate_obj_to_z_location(cls, obj, z):
        if z != 0:
            obj.location = obj.location + Vector((0, 0, z))

    @classmethod
    def link_obj_to_active_collection(cls, obj):
        bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)

    @classmethod
    def get_2d_vertices_from_obj(cls, obj):
        points = []
        vectors = [v.co for v in obj.data.vertices.values()]
        for vector in vectors:
            point = (vector[0], vector[1])
            points.append(point)

        points.append((vectors[0][0], vectors[0][1]))
        return points

    @classmethod
    def assign_swept_area_outer_curve_from_2d_vertices(cls, obj, vertices):
        body = cls.get_body_representation(obj)
        model = tool.Ifc.get()
        extrusion = tool.Model.get_extrusion(body)
        area = extrusion.SweptArea
        old_area = area.OuterCurve

        builder = ifcopenshell.util.shape_builder.ShapeBuilder(model)
        outer_curve = builder.polyline(vertices, closed = True)

        area.OuterCurve = outer_curve
        ifcopenshell.util.element.remove_deep2(tool.Ifc.get(), old_area)

    @classmethod
    def get_body_representation(cls, obj):
        element = tool.Ifc.get_entity(obj)
        model = tool.Ifc.get()
        body = ifcopenshell.util.representation.get_representation(element, "Model", "Body", "MODEL_VIEW")
        return body

    @classmethod
    def assign_ifcspace_class_to_obj(cls, obj):
        bpy.ops.bim.assign_class(obj=obj.name, ifc_class="IfcSpace")

    @classmethod
    def assign_type_to_obj(cls, obj):
        relating_type_id = bpy.context.scene.BIMModelProperties.relating_type_id
        relating_type = tool.Ifc.get().by_id(int(relating_type_id))
        ifc_class = relating_type.is_a()
        instance_class = ifcopenshell.util.type.get_applicable_entities(ifc_class, tool.Ifc.get().schema)[0]
        bpy.ops.bim.assign_class(obj=obj.name, ifc_class=instance_class)
        element = tool.Ifc.get_entity(obj)
        blenderbim.core.type.assign_type(tool.Ifc, tool.Type, element=element, type=relating_type)

    @classmethod
    def assign_container_to_obj(cls, obj):
        active_obj = bpy.context.active_object
        element = tool.Ifc.get_entity(active_obj)
        container = ifcopenshell.util.element.get_container(element)
        container_obj = tool.Ifc.get_object(container)
        blenderbim.core.spatial.assign_container(
            tool.Ifc, tool.Collector, tool.Spatial, structure_obj=container_obj, element_obj=obj
        )

    @classmethod
    def regen_obj_representation(cls, ifc, geometry, obj, body):
        blenderbim.core.geometry.switch_representation(
            ifc,
            geometry,
            obj=obj,
            representation=body,
            should_reload=True,
            is_global=True,
            should_sync_changes_first=False,
        )

    @classmethod
    def toggle_spaces_visibility_wired_and_textured(cls, spaces):
        first_obj = tool.Ifc.get_object(spaces[0])
        if bpy.data.objects[first_obj.name].display_type == "TEXTURED":
            for space in spaces:
                obj = tool.Ifc.get_object(space)
                bpy.data.objects[obj.name].show_wire = True
                bpy.data.objects[obj.name].display_type = "WIRE"
            return

        elif bpy.data.objects[first_obj.name].display_type == "WIRE":
            for space in spaces:
                obj = tool.Ifc.get_object(space)
                bpy.data.objects[obj.name].show_wire = False
                bpy.data.objects[obj.name].display_type = "TEXTURED"
            return
