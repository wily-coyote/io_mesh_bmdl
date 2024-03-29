import bpy, struct, bmesh, os
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty
from bpy.types import Operator

bl_info = {
    "name": "BRender (.bmdl) import/export",
    "description": "BMDL model importer and exporter for 3D Movie Maker",
    "author": "bpy port by wily-coyote, based on code by Foone (https://github.com/foone/7gen)",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import/Export > BRender",
    "support": 'COMMUNITY',
    "category": "Import-Export"
}

def read_bmdl(context, filepath):
    with open(filepath, "rb") as file:
        magic = file.read(4)
        vertices = []
        faces = []
        if magic == b"\x01\x00\x03\x03":
            counts = struct.unpack("<HH", file.read(4))
            file.read(40)
            for i in range(counts[0]):
                vertices.append([x/655356 for x in struct.unpack("<lllll", file.read(20))])
                file.read(12)
            for i in range(counts[1]):
                faces.append([x for x in struct.unpack("<HHH", file.read(6))])
                file.read(26)
            name = os.path.splitext(os.path.basename(filepath))[0]
            me = bpy.data.meshes.new(name)
            me.from_pydata([x[:3] for x in vertices],[],faces)
            uvs = me.uv_layers.new(name=name)
            ob = bpy.data.objects.new(me.name, me)   
            for loop in me.loops:
                idx = loop.vertex_index
                uv = vertices[idx][3:5]
                uvs.data[loop.index].uv = [x*10 for x in uv]
            bpy.context.scene.collection.objects.link(ob)
        else:
            self.report({"ERROR"}, "This doesn't look like a BRender model")
            return {"CANCELLED"}
    return {'FINISHED'}


def to_bmdl(context, objekt):
    data = b"\x01\x00\x03\x03"
    vertices = []
    faces = []
    bm = bmesh.new()
    if type(objekt) == list:
        for objdata in objekt:
            bm.from_mesh(mesh=objdata)
    elif hasattr(objekt, "type") and objekt.type == "MESH":
        bm.from_mesh(mesh=objekt.data)
    else:
        return None
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.split_edges(bm, edges=bm.edges) # this makes the uvs export ptoperlty
    vertices = [list(x.co) for x in bm.verts]
    vertices = [list(map(lambda x: int((x*10)*65536), x)) for x in vertices]
    faces = [[y.index for y in x.verts] for x in bm.faces]
    data = data + (struct.pack("<HH", len(vertices), len(faces)))
    data = data + (b"\x00"*40)
    for face in bm.faces:
        for loop in face.loops:
            vertices[loop.vert.index] = (vertices[loop.vert.index] + [int((x)*65536) for x in loop[bm.loops.layers.uv[0]].uv]) # i don't like this
    for x in vertices:
        vert = x[:5]
        vert=vert+([0]*(5-len(vert)))
        data = data + (struct.pack("<lllll", *(vert)))
        data = data + (b"\x00"*12)
    for x in faces:
        data = data + (struct.pack("<HHH", *x))
        # data = data + (b"\x00"*26)
        data = data + (b"\x00" * 10)
        data = data + (b"\x01")
        data = data + (b"\x00" * 15)
    bm.free()
    return data

def save_bmdl(context, filepath, selected_only):
    meshes = []
    for obj in context.selected_objects if selected_only == True else scene.objects:
        if obj.type == "MESH":
            meshes.append(obj.data)
    with open(filepath, "wb") as file:
        data = to_bmdl(context, meshes)
        if data:
            file.write(data)
        else:
            return {"CANCELLED"}
    return {'FINISHED'}

def save_bmdl_object(context, filepath, objekt):
    with open(os.path.join(os.path.dirname(filepath), objekt.name+".bmdl"), "wb") as file:
        data = to_bmdl(context, objekt)
        if data:
            file.write(data)
        else:
            return {"CANCELLED"}
    return {'FINISHED'}

class ImportBMDL(Operator, ImportHelper):
    """Load a BRender model"""
    bl_idname = "import_3dmm.brender"  
    bl_label = "Import BRender BMDL"

    filename_ext = ".bmdl"

    filter_glob: StringProperty(
        default="*.bmdl",
        options={'HIDDEN'},
        maxlen=255, 
    )

    files: CollectionProperty(name='Files', type=bpy.types.PropertyGroup)

    def execute(self, context):
        for filepath in self.files:
            if read_bmdl(context, os.path.join(os.path.dirname(self.filepath), filepath.name)) == {'CANCELLED'}:
                return {'CANCELLED'}
        return {'FINISHED'}

class ExportBMDL(Operator, ExportHelper):
    """Save a BRender model"""
    bl_idname = "export_3dmm.brender" 
    bl_label = "Export BRender BMDL"

    filename_ext = ".bmdl"

    filter_glob: StringProperty(
        default="*.bmdl",
        options={'HIDDEN'},
        maxlen=255,
    )

    selected_only: BoolProperty(
        name="Export selected objects",
        description="Only export selected objects",
        default=True,
    )

    separate: BoolProperty(
        name="Export each object separately",
        description="Export each object to separate BMDL files, will ignore file path and use object name",
        default=False,
    )

    def execute(self, context):
        if self.separate:
            objects = []
            for obj in context.selected_objects if self.selected_only == True else context.scene.objects:
                if obj.type == "MESH":
                    objects.append(obj)
            for obj in objects:
                if save_bmdl_object(context, self.filepath, obj) == {'CANCELLED'}:
                    return {'CANCELLED'}
            return {'FINISHED'}
        else:
            return save_bmdl(context, self.filepath, self.selected_only)

def menu_func_import(self, context):
    self.layout.operator(ImportBMDL.bl_idname, text="BRender (.bmdl)")

def menu_func_export(self, context):
    self.layout.operator(ExportBMDL.bl_idname, text="BRender (.bmdl)")

def register():
    bpy.utils.register_class(ImportBMDL)
    bpy.utils.register_class(ExportBMDL)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ImportBMDL)
    bpy.utils.unregister_class(ExportBMDL)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()