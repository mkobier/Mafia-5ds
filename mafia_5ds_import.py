##Author mkobier

import bpy
import bpy_extras
import struct
import mathutils
import bmesh

bl_info = {
    "name": "Mafia character animation importer",
    "author": "Mateusz",
    "version": (1, 0),
    "blender": (4, 0, 1),
    "location": "Top bar",
    "description": "A tool for importing mafia animations.",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}


class Mafia_character_import_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    MapsPath : bpy.props.StringProperty(
        name    = "Maps path",
        subtype = 'DIR_PATH',
        maxlen  = 255
    )
      
    def draw(self, context):
        layout = self.layout
        layout.label(text = "Specify extracted Mafia maps folder")
        layout.prop(self, "MapsPath")


class Mafia_mesh_info:
    def __init__(self):
        self.name = ''
        self.position = [0, 0, 0]
        self.rotation = [0, 0, 0, 0]
        self.scale = [0, 0, 0]
        self.mesh_type = 0
        self.parent_id = 0
        self.global_position = [0, 0, 0]
        self.vertices_position_list = []
        self.is_animated = False
        self.is_bone = False
        self.anim_data = Mafia_animation_data(0, 0)
        self.is_base = False

             
class Mafia_animation_data:
    def __init__(self, name_offset, data_offset):
        self.name_offset = name_offset
        self.data_offset = data_offset
        
        self.has_scale = False
        self.number_of_scale_frames = 0
        self.scale_frame_list = []
        self.scale_matrix = []
        
        self.has_rotation = False
        self.number_of_rotation_frames = 0
        self.rotation_frame_list = []
        self.rotation_quats = []
        self.rotation_matrix = []
        
        self.has_position = False
        self.number_of_position_frames = 0
        self.position_frame_list = []
        self.translation_matrix = []
        
        self.local_matrix = []
        
class Anim_segments_and_names:
    def __init__(self, name_offset, data_offset):
        self.name_offset = name_offset
        self.data_offset = data_offset
        self.name = ''
        self.which_mesh = -1
        self.is_important = True

class Vertex_order:
    def __init__(self, nonWeighted, Weighted, boneID, inverse_transform, table):
        self.nonWeighted = nonWeighted
        self.Weighted = Weighted
        self.boneID = boneID
        self.inverse_transform = inverse_transform
        self.weight_table = table

class Mafia4ds_Character(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    "Import Mafia character"
    bl_idname    = "mafia4ds.import_"
    bl_text      = "First import Mafia character (.4ds)"
    bl_label     = "Import 4ds"
    filename_ext = ".4ds"
    meshes_info = []
    vertex_order = []
    bone_order_sorted = ['back1', 'back2', 'back3', 
                          'l_shoulder', 'l_arm', 'l_elbow', 'l_hand', 'r_shoulder', 'r_arm', 'r_elbow', 'r_hand', 'neck',
                               'l_thigh', 'l_shin', 'l_foot', 'r_thigh', 'r_shin', 'r_foot']
    bone_order_unsorted = []                        
    
    filter_glob : bpy.props.StringProperty(
        default = "*.4ds",
        options = {"HIDDEN"},
        maxlen  = 255
    )

    def Read_string_from_file(self, file):
        length = struct.unpack("B", file.read(1))[0]
        text_coded  = struct.unpack(f"{length}c", file.read(length))
        string = ""
        
        for c in text_coded:
            string += c.decode()
        
        return string
        
        
    def Sort_bones_of_character(self, bones_initial, bones_final):
        current_element = 0
        bones_initial_reversed = list(reversed(bones_initial))
        for i, x in enumerate(bones_initial_reversed):
            if x == 'back1':
                bones_final[current_element] = 'back1'
                bones_final[current_element + 1] = 'back2'
                bones_final[current_element + 2] = 'back3'
                current_element += 3
                
                for y in range(9):
                    y_reversed = 8 - y
                    if bones_initial_reversed[i-3-y_reversed] == 'neck':
                        bones_final[current_element] = 'neck'
                        current_element += 1
                    elif bones_initial_reversed[i-3-y_reversed] == 'r_shoulder':
                        bones_final[current_element] = 'r_shoulder'
                        bones_final[current_element+1] = 'r_arm'
                        bones_final[current_element+2] = 'r_elbow'
                        bones_final[current_element+3] = 'r_hand'
                        current_element += 4
                    elif bones_initial_reversed[i-3-y_reversed] == 'l_shoulder':
                        bones_final[current_element] = 'l_shoulder'
                        bones_final[current_element+1] = 'l_arm'
                        bones_final[current_element+2] = 'l_elbow'
                        bones_final[current_element+3] = 'l_hand'
                        current_element += 4

                        
                
            elif x == 'l_thigh':
                bones_final[current_element] = 'l_thigh'
                bones_final[current_element + 1] = 'l_shin'
                bones_final[current_element + 2] = 'l_foot'
                current_element += 3
            elif x == 'r_thigh':
                bones_final[current_element] = 'r_thigh'
                bones_final[current_element + 1] = 'r_shin'
                bones_final[current_element + 2] = 'r_foot'
                current_element += 3
            
            
    def execute(self, context): 
        with open(self.filepath, "rb") as file:
            image_folder  = bpy.context.preferences.addons[__name__].preferences.MapsPath
            chars  = struct.unpack("4c", file.read(4))
            file_header_4ds = chars[0].decode() + chars[1].decode() + chars[2].decode() + chars[3].decode()
            print(file_header_4ds)
            if file_header_4ds != "4DS\0":
                print('Invalid 4ds file')
                return
            file_version = struct.unpack("H", file.read(2))[0]
            if file_version != 0x1d:
                print(f"Invalid 4DS version {file_version}!")
                return
            timestamp = struct.unpack("Q", file.read(8))[0]
            
            total_materials_number = struct.unpack("H", file.read(2))[0]
            materials = []
            print('Total material number:', total_materials_number)
            
            for _ in range(total_materials_number):
            
                flag_of_material = struct.unpack("I", file.read(4))[0]
                        
                AddEffect       = (flag_of_material & 0x00008000) != 0
                UseAlphaTexture = (flag_of_material & 0x40000000) != 0
                UseEnvTexture   = (flag_of_material & 0x00080000) != 0
                AnimatedDiffuse = (flag_of_material & 0x04000000) != 0

                AmbientColor = struct.unpack("fff", file.read(12))
                DiffuseColor = struct.unpack("fff", file.read(12))
                emission = struct.unpack("fff", file.read(12))
                alpha = struct.unpack("f", file.read(4))[0]
                metallic = 0.0
                
                if UseEnvTexture:
                    metallic            = struct.unpack("f", file.read(4))[0]
                    EnvTexture = self.Read_string_from_file(file).lower()
                
                diffuse = self.Read_string_from_file(file).lower()

                if AddEffect and UseAlphaTexture:
                    AlphaTexture = self.Read_string_from_file(file).lower()
                
                if AnimatedDiffuse:
                    AnimatedFrames  = struct.unpack("I", file.read(4))[0]
                    file.read(2)
                    AnimFrameLength = struct.unpack("I", file.read(4))[0]
                    file.read(8)
                
                material = bpy.data.materials.new(name = diffuse)
                material.use_nodes = True
            
                node  = None
                nodes = material.node_tree.nodes
                
                for node in nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        break
                
                if node is None:
                    return
                    
                node.inputs["Emission Color"].default_value = [ emission[0], emission[1], emission[2], 1.0]
                node.inputs["Alpha"].default_value = alpha
                node.inputs["Metallic"].default_value = metallic
                node.inputs['Specular IOR Level'].default_value = 0.0
                node.inputs["Roughness"].default_value = 0.0
                    
                baseColor      = node.inputs["Base Color"]
                baseColorLinks = baseColor.links
                    
                if len(baseColorLinks) > 0:
                    image      = baseColorLinks[0].from_node.image
                else:
                    image_node      = nodes.new(type="ShaderNodeTexImage")
                    imageColor = image_node.outputs["Color"]
                    
                    links      = material.node_tree.links
                    links.new(imageColor, baseColor)
                
                if len(diffuse) == 0:
                    return
                
                image_location = image_folder + diffuse
                img_data = bpy.data.images.load(filepath = image_location, check_existing = True)
                image_node.image = img_data
                materials.append(material)
            
            print(materials)
            
            
            total_meshes_number = struct.unpack("H", file.read(2))[0]
            print(f'Submeshes number: {total_meshes_number}')
            meshes = []
            self.meshes_info.clear()
            
            for y in range(total_meshes_number):
                self.meshes_info.append(Mafia_mesh_info())
                
                mesh_type = struct.unpack("B", file.read(1))[0]
                visualType  = 0
                renderFlags = 0
                
                if mesh_type == 1:
                    visualType  = struct.unpack("B", file.read(1))[0]
                    renderFlags = struct.unpack("H", file.read(2))[0]
                    print('Visual type:', visualType)
                
                parent_id            = struct.unpack("H", file.read(2))[0] - 1
                location             = struct.unpack("3f", file.read(12))
                scale                = struct.unpack("3f", file.read(12))
                rotation             = struct.unpack("4f", file.read(16))
                
                cullingFlags         = struct.unpack("B", file.read(1))[0]
                name                 = self.Read_string_from_file(file)
                parameters           = self.Read_string_from_file(file)          
                
                
                self.meshes_info[y].name = name
                self.meshes_info[y].mesh_type = mesh_type
                self.meshes_info[y].position = location
                self.meshes_info[y].parent_id = parent_id
                self.meshes_info[y].scale = scale
                self.meshes_info[y].rotation = rotation

                print(name)
                if mesh_type == 10:
                    self.meshes_info[y].is_bone = True
                    self.bone_order_unsorted.append(name)
  
                else:
                    meshData             = bpy.data.meshes.new(name)
                    mesh                 = bpy.data.objects.new(name, meshData)
                
                    bpy.context.collection.objects.link(mesh)
                    meshes.append(mesh)
                
                    
                    mesh.location       = [ location[0], location[2], location[1] ]
                    mesh.scale          = [ scale[0],    scale[2],    scale[1] ]
                    mesh.rotation_euler = mathutils.Quaternion([ rotation[0], rotation[1], rotation[3], rotation[2] ]).to_euler()
                
                if mesh_type == 1:                                  #visual
                    instanceIdx           = struct.unpack("H", file.read(2))[0]
                    
                    if instanceIdx > 0:
                        print('Error')
                        return;
                    
                    meshName = mesh.name
                    LODs_number = struct.unpack("B", file.read(1))[0]
                    
                    for current_LOD in range(LODs_number):
                        LodRatio = struct.unpack("f", file.read(4))[0]
                        bMesh              = bmesh.new()
                        vertices           = bMesh.verts
                        uvs                = []
                        vertexCount        = struct.unpack("H", file.read(2))[0]
                        
                        for vertexIdx in range(vertexCount):
                            position       = struct.unpack("fff", file.read(12))
                            normal         = struct.unpack("fff", file.read(12))
                            uv             = struct.unpack("ff",  file.read(8))
                            
                            vertex         = vertices.new()
                            vertex.co      = [ position[0], position[2], position[1] ]
                            vertex.normal  = [ normal[0],   normal[2],   normal[1] ]
                            uvs.append([ uv[0], -uv[1] ])
                            
                            self.meshes_info[y].vertices_position_list.append([ position[0], position[2], position[1] ])
                        
                        vertices.ensure_lookup_table()
                        
                        # faces
                        faces               = bMesh.faces
                        uvLayer             = bMesh.loops.layers.uv.new()
                        faceGroupCount      = struct.unpack("B", file.read(1))[0]
                        
                        for faceGroupIdx in range(faceGroupCount):
                            faceCount       = struct.unpack("H", file.read(2))[0]
                            
                            mesh.data.materials.append(None)
                            materialSlotIdx = len(mesh.material_slots) - 1
                            materialSlot    = mesh.material_slots[materialSlotIdx]
                            
                            for faceIdx in range(faceCount):
                                vertexIdxs             = struct.unpack("HHH", file.read(2 * 3))
                                vertexIdxsSwap         = [ vertexIdxs[0], vertexIdxs[2], vertexIdxs[1] ]
                                
                                try:
                                    face               = faces.new([ vertices[vertexIdxsSwap[0]], vertices[vertexIdxsSwap[1]], vertices[vertexIdxsSwap[2]] ])
                                except:
                                    print('Error')
                                
                                face.material_index    = materialSlotIdx
                                
                                for loop, vertexIdx in zip(face.loops, vertexIdxsSwap):
                                    loop[uvLayer].uv   = uvs[vertexIdx]
                            
                            materialIdx                = struct.unpack("H", file.read(2))[0]
                            
                            if materialIdx > 0:
                                materialSlot.material = materials[materialIdx - 1]
                        
                        if current_LOD == 0:
                            bMesh.to_mesh(meshData)
                        del bMesh
                        
                        mesh.select_set(True)
                        bpy.ops.object.shade_smooth()                     
                        mesh.select_set(False)
                        
                    if visualType == 2 or visualType==3:   #single mesh
                        print('Single mesh')
                        self.meshes_info[y].is_base = True
                        
                        for current_LOD in range(LODs_number):
                            numBones = struct.unpack("B", file.read(1))[0]
                            print(numBones)
                            nonWeightedVerts = struct.unpack("L", file.read(4))[0]
                            min_max_XYZ = struct.unpack("6f",  file.read(6 * 4))
                            
                            for x in range (numBones):
                                inverse_transform = struct.unpack("16f",  file.read(64))  
                                first_row = [inverse_transform[0], inverse_transform[4], inverse_transform[8], inverse_transform[12]]
                                second_row = [inverse_transform[1], inverse_transform[10], inverse_transform[9], inverse_transform[14]]
                                third_row = [inverse_transform[2], inverse_transform[6], inverse_transform[5], inverse_transform[13]]
                                fourth_row = [inverse_transform[3], inverse_transform[7], inverse_transform[11], inverse_transform[15]]
                                inverse_transform_m = mathutils.Matrix((first_row,  second_row, third_row, fourth_row))
                                non_weighted_vertices = struct.unpack("L", file.read(4))[0]
                                weighted_vertices = struct.unpack("L", file.read(4))[0]
                                boneParentID = struct.unpack("L", file.read(4))[0]   
                                
                                min_max_XYZ = struct.unpack("6f",  file.read(6 * 4))
                                
                                weight_of_vertex = []
                                if weighted_vertices > 0:
                                    weight_of_vertex = struct.unpack (f'{weighted_vertices}f', file.read(4* weighted_vertices))
                                    
                                if current_LOD == 0:
                                    self.vertex_order.append(Vertex_order(non_weighted_vertices, weighted_vertices, boneParentID, inverse_transform_m, weight_of_vertex))
                            
                    if visualType == 3 or visualType==5: # morph
                        print('Morph')
                        number_of_poses = struct.unpack("B", file.read(1))[0]
                        if number_of_poses != 0:
                            number_of_channels = struct.unpack("B", file.read(1))[0]
                            unknown = struct.unpack("B", file.read(1))[0]
                            for m in range(number_of_channels):
                                number_of_morph_vertices = struct.unpack("H", file.read(2))[0]
                                if number_of_morph_vertices !=0:
                                    for a in range(number_of_morph_vertices):
                                        for b in range(number_of_poses):
                                            vertex_morph_info = struct.unpack("6f",  file.read(24))
                                    unknown = struct.unpack("B", file.read(1))[0]
                                    for a in range(number_of_morph_vertices):
                                        vID = struct.unpack("H", file.read(2))[0]
                            unknown = struct.unpack("10f", file.read(10 * 4))   
                            
                    
                elif mesh_type == 6:                                #dummy
                    border_min_max  = struct.unpack("6f", file.read(6 * 4))
                    mesh.select_set(True)
                    mesh.hide_set(True)
                    mesh.hide_render = True
                    mesh.select_set(False)
                
                elif mesh_type == 7:                                #target
                    unknown = struct.unpack("H", file.read(2))[0]
                    number_of_links = struct.unpack("B", file.read(1))[0]
                    for _ in range (number_of_links):
                        unknown2 = struct.unpack("H", file.read(2))[0]
                        
                    mesh.select_set(True)
                    mesh.hide_set(True)
                    mesh.hide_render = True
                    mesh.select_set(False)
                        
                elif mesh_type == 10:                               #bone
             
                    bone_matrix_unused = struct.unpack("16f",  file.read(64))
                    bone_ID = struct.unpack("L", file.read(4))[0]
                
                if parent_id == -1:
                    self.meshes_info[y].global_position = self.meshes_info[y].position
                else:
                    self.meshes_info[y].global_position[0] = self.meshes_info[y].position[0] +  self.meshes_info[parent_id].global_position[0]
                    self.meshes_info[y].global_position[1] = self.meshes_info[y].position[1] +  self.meshes_info[parent_id].global_position[1]
                    self.meshes_info[y].global_position[2] = self.meshes_info[y].position[2] +  self.meshes_info[parent_id].global_position[2]
                
                if mesh_type == 10:
                    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.03, calc_uvs=True, enter_editmode=False, align='WORLD',
                    location=(self.meshes_info[y].global_position[0], self.meshes_info[y].global_position[2], self.meshes_info[y].global_position[1]))
                    
                    sphere = bpy.context.active_object
                    sphere.name = self.meshes_info[y].name
                    sphere.hide_set(True)
                    sphere.hide_render = True
                    sphere.select_set(False)
                
            isAnimated = struct.unpack("B", file.read(1))[0]
        
        self.Sort_bones_of_character(self.bone_order_unsorted, self.bone_order_sorted)
        return {'FINISHED'}

class Mafia5ds_Importer(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    "Import Mafia animation"
    bl_idname    = "mafia5ds.import_"
    bl_text      = "Next import animation (.5ds)"
    bl_label     = "Import 5ds"
    filename_ext = ".5ds"
    
    filter_glob : bpy.props.StringProperty(
        default = "*.5ds",
        options = {"HIDDEN"},
        maxlen  = 255
    )
    
    def find_base(self):
        meshes_structure = Mafia4ds_Character.meshes_info
        for i, x in enumerate(meshes_structure):
            if x.is_base == True:
                return i
        return 0
            
    
    def restore_data_to_default(self, meshes_structure):
        for x in meshes_structure:
            x.anim_data = Mafia_animation_data(0, 0)
            if x.name == 'base':
                v = bpy.data.objects['base'].data.vertices
                for which_vertex, y in enumerate(v):
                    y.co = x.vertices_position_list[which_vertex]
    
    def read_frames_data(self, anim_segments_and_names, meshes_structure, number_of_frames, file):
        for x in anim_segments_and_names:
            print('Name of bone:', x.name)
            current_anim = meshes_structure[x.which_mesh].anim_data
            current_anim.local_matrix = [None] *  number_of_frames
            
            file.seek(x.data_offset + 18, 0)
            flags = struct.unpack("I", file.read(4))[0]
            print(meshes_structure[x.which_mesh].name, 'Flag:', flags)
            if (flags & 4) != 0:     #rotation
                current_anim.has_rotation = True
                current_anim.number_of_rotation_frames = struct.unpack("H", file.read(2))[0]
                current_anim.rotation_frame_list = struct.unpack (f'{current_anim.number_of_rotation_frames}H', file.read(2* current_anim.number_of_rotation_frames))
                print(current_anim.number_of_rotation_frames, current_anim.rotation_frame_list)
                current_anim.rotation_quats = [None] * number_of_frames
                current_anim.rotation_matrix = [None] * number_of_frames
                
                if (current_anim.number_of_rotation_frames & 1) == 0: 
                    empty_frame = struct.unpack("H", file.read(2))[0]
                    
                for y in range(current_anim.number_of_rotation_frames):
                    quat_1 = struct.unpack("f", file.read(4))[0]
                    quat_2 = struct.unpack("f", file.read(4))[0]
                    quat_3 = struct.unpack("f", file.read(4))[0]
                    quat_4 = struct.unpack("f", file.read(4))[0]
                    combined_quat = mathutils.Quaternion([ quat_1, quat_2, quat_4, quat_3])
                    current_anim.rotation_quats[current_anim.rotation_frame_list[y]] = combined_quat
                    #current_anim.rotation_matrix[current_anim.rotation_frame_list[y]] = combined_quat.to_matrix().to_4x4()
                
            if (flags & 2) != 0:    #position
                current_anim.has_position = True
                current_anim.number_of_position_frames = struct.unpack("H", file.read(2))[0]
                current_anim.position_frame_list = struct.unpack (f'{current_anim.number_of_position_frames}H', file.read(2* current_anim.number_of_position_frames))
                print(current_anim.number_of_position_frames, current_anim.position_frame_list)
                
                current_anim.translation_matrix = [None] *  number_of_frames
                
                if (current_anim.number_of_position_frames & 1) == 0: 
                    empty_frame = struct.unpack("H", file.read(2))[0]
                
                for y in range(current_anim.number_of_position_frames):
                    position_x = struct.unpack("f", file.read(4))[0]
                    position_y = struct.unpack("f", file.read(4))[0]
                    position_z = struct.unpack("f", file.read(4))[0]
                    position_vector = mathutils.Vector((position_x, position_z, position_y))
                    current_anim.translation_matrix[current_anim.position_frame_list[y]] = mathutils.Matrix.Translation(position_vector)
                    
                
            if (flags & 8) != 0:    #scale
                current_anim.scale = True
                current_anim.number_of_scale_frames = struct.unpack("H", file.read(2))[0]
                current_anim.scale_frame_list = struct.unpack (f'{current_anim.number_of_scale_frames}H', file.read(2* current_anim.number_of_scale_frames))
                print(current_anim.number_of_scale_frames, current_anim.scale_frame_list)
                
                if (current_anim.number_of_scale_frames & 1) == 0: 
                    empty_frame = struct.unpack("H", file.read(2))[0]
                
                for y in range(current_anim.number_of_scale_frames):
                    scale_x = struct.unpack("f", file.read(4))[0]
                    scale_y = struct.unpack("f", file.read(4))[0]
                    scale_z = struct.unpack("f", file.read(4))[0]
                    matrix_scale = mathutils.Matrix.Identity(4)
                    matrix_scale[0][0] = scale_x
                    matrix_scale[1][1] = scale_y
                    matrix_scale[2][2] = scale_z  
                    current_anim.scale_matrix.append(matrix_scale)
    
    def interpolate_list(self, inter_list):
        for i in range(len(inter_list)):
            if inter_list[i] is None:
                # Find the nearest non-None neighbors
                left, right = i - 1, i + 1
                while inter_list[right] is None:
                    right += 1  
                
                y1_y0 = inter_list[right] - inter_list[left]
                x1_x0 = right - left
                inter_list[i] = y1_y0 / x1_x0 + inter_list[left]
    
    def interpolate(self, anim_segments_and_names, meshes_structure, number_of_frames):
        print('Interpolation of translation matrix')
        for x in anim_segments_and_names:
            current_anim = meshes_structure[x.which_mesh].anim_data
            if current_anim.has_position == True:
                #interpolate translation
                x_position = []
                y_position = []
                z_position = []  
                for i, matrix in enumerate(current_anim.translation_matrix):
                    if matrix is not None:  
                        x_position.append(matrix[0][3])
                        y_position.append(matrix[1][3])
                        z_position.append(matrix[2][3])
                    else:
                        x_position.append(None)
                        y_position.append(None)
                        z_position.append(None)
                        
                self.interpolate_list(x_position)
                self.interpolate_list(y_position)
                self.interpolate_list(z_position)
                
                for i in range(len(current_anim.translation_matrix)):
                    if current_anim.translation_matrix[i] is None:
                        current_anim.translation_matrix[i] = mathutils.Matrix.Translation(mathutils.Vector((x_position[i], y_position[i], z_position[i])))
            
            
            #interpolate rotation
            if current_anim.has_rotation == True:
                for i in range(len(current_anim.rotation_quats)):
                    if current_anim.rotation_quats[i] is None:
                        # Find the nearest non-None neighbors
                        left, right = i - 1, i + 1
                        while current_anim.rotation_quats[right] is None:
                            right += 1
                            
                        factor = 1 / (right - left)
                        current_anim.rotation_quats[i] = current_anim.rotation_quats[left].slerp(current_anim.rotation_quats[right], factor)
                 
                for i in range(len(current_anim.rotation_quats)):

                    current_anim.rotation_matrix[i] = current_anim.rotation_quats[i].to_matrix().to_4x4()
            
    def set_bones_position(self, anim_segments_and_names, meshes_structure, base_number):
    #setting bones in blender
        for x in anim_segments_and_names:
            if x.is_important == False:
                continue
            
            print(x.name)
            scene = bpy.context.scene
            obj = scene.objects.get(x.name)
            obj.rotation_mode = 'QUATERNION'
            
            current_anim = meshes_structure[x.which_mesh].anim_data
            current_mesh = meshes_structure[x.which_mesh]
            
            for i in range(len(current_anim.local_matrix)):
                local_m = mathutils.Matrix.Translation((current_mesh.position[0], current_mesh.position[2], current_mesh.position[1]))
                if current_anim.has_position == True:
                    local_m = current_anim.translation_matrix[i]
                if current_anim.has_rotation == True:
                    print(current_mesh.name, current_anim.rotation_matrix[i])
                    local_m = local_m @ current_anim.rotation_matrix[i]
                #begin of scale
                matrix_scale = mathutils.Matrix.Identity(4)
                matrix_scale[0][0] = current_mesh.scale[0]
                matrix_scale[1][1] = current_mesh.scale[2]
                matrix_scale[2][2] = current_mesh.scale[1] 
                #print(x.name, local_m)
                local_m = local_m @ matrix_scale
                # end of scale
                
                parent_mesh = meshes_structure[current_mesh.parent_id]
                if parent_mesh.is_bone == True:
                    parent_matrix = mathutils.Matrix.Identity(4)
                    
                    if len(parent_mesh.anim_data.local_matrix) > 0:
                        parent_matrix = parent_mesh.anim_data.local_matrix[i]
                        
                    local_m = parent_matrix @ local_m
                
                current_anim.local_matrix[i] = local_m    
                
                if current_mesh.name != 'base':
                    print('base number', base_number)
                    base_local_matrix = mathutils.Matrix.Translation((meshes_structure[base_number].position[0], meshes_structure[base_number].position[2], meshes_structure[base_number].position[1]))
                    
                    if len(meshes_structure[base_number].anim_data.local_matrix) > 0:
                        base_local_matrix = meshes_structure[base_number].anim_data.local_matrix[i]
                        
                    local_m =  base_local_matrix @ local_m
                    

                position_from_matrix = local_m.to_translation()
                rotation_from_matrix = local_m.to_quaternion()
                
                
                obj.location = position_from_matrix
                obj.rotation_quaternion = rotation_from_matrix
                
                
                obj.keyframe_insert(data_path="location", frame=i)
                obj.keyframe_insert(data_path="rotation_quaternion", frame=i)
    
    def animate_vertices(self, meshes_structure, vertex_order):
        bone_order = Mafia4ds_Character.bone_order_sorted            
        which_vertex = 0
        v = bpy.data.objects['base'].data.vertices
        base001 = bpy.data.objects['base']
        for x, bone_name in zip(vertex_order, bone_order):
            print(x.nonWeighted, x.Weighted, x.boneID, bone_name)
            for search in meshes_structure:
                if search.name == bone_name:
                    parent_mesh = meshes_structure[search.parent_id]
                    
                    for i, name in enumerate(bone_order):
                        if name == parent_mesh.name:
                            break
                    vertex_order_parent = vertex_order[i]
                    
                    parent_anim = parent_mesh.anim_data                  
                    search_anim = search.anim_data
                    
                    vg = base001.vertex_groups.new(name=search.name)
                    
                    if x.nonWeighted > 0:
                        for _ in range (x.nonWeighted):
                         vg.add([which_vertex], 1.0, 'ADD')
                         actual_vertex = v[which_vertex]
                         old_coordinate = actual_vertex.co.to_4d()
                         for j, bone_matrix in enumerate(search_anim.local_matrix): 
                            bone_shift = bone_matrix @ x.inverse_transform
                            actual_vertex.co = (bone_shift @ old_coordinate).to_3d()
                            actual_vertex.keyframe_insert("co", frame = j) 

                         which_vertex += 1
                         
                    if x.Weighted > 0:
                        for n in range (x.Weighted):
                         vg.add([which_vertex], 1.0, 'ADD')
                         vertex_weight = x.weight_table[n]
                         actual_vertex = v[which_vertex]
                         old_coordinate = actual_vertex.co.to_4d()  
                         
                         for j, (bone_current, bone_parent) in enumerate(zip(search_anim.local_matrix, parent_anim.local_matrix)): 
                            bone_shift_current = bone_current @ x.inverse_transform
                            bone_shift_parent = mathutils.Matrix.Identity(4)
                            
                            if x.boneID != 0:
                                bone_shift_parent = bone_parent @ vertex_order_parent.inverse_transform   

                            
                            change_vector_current = (bone_shift_current @ old_coordinate).to_3d() * vertex_weight
                            change_vector_parent = (bone_shift_parent @ old_coordinate).to_3d() * (1 - vertex_weight)
                            
                            actual_vertex.co = change_vector_current + change_vector_parent
                            actual_vertex.keyframe_insert("co", frame = j)
                            
                         which_vertex += 1
    
    def execute(self, context): 
        with open(self.filepath, "rb") as file:
            print('Opened file with success')
            early_chars  = struct.unpack("cccc", file.read(4))
            mafia_5ds_header = early_chars[0].decode() + early_chars[1].decode() + early_chars[2].decode() + early_chars[3].decode()
            print('File header:', mafia_5ds_header)
            if mafia_5ds_header != "5DS\0":
                print('Invalid 5ds file')
                return
            print('Valid 5ds file')
            file_version = struct.unpack("H", file.read(2))[0]
            if file_version != 20:
                print(f"Invalid 5DS version")
                return
            print('Valid 5ds file version')
            timestamp = struct.unpack("Q", file.read(8))[0]
            datasize = struct.unpack("I", file.read(4))[0]
            number_of_nodes = struct.unpack("H", file.read(2))[0]
            number_of_frames = struct.unpack("H", file.read(2))[0] + 1
            print(f'Ilosc nodow: {number_of_nodes}')
            print(f'Ilosc frames: {number_of_frames}')
            anim_segments_and_names = []
            meshes_structure = Mafia4ds_Character.meshes_info
            vertex_order = Mafia4ds_Character.vertex_order
            
            base_number = self.find_base()
            
            #Remove object animation data if has any
            selected_objects = bpy.context.scene.objects
            for obj in selected_objects:
                v = obj.data
                v.animation_data_clear()
                obj.animation_data_clear()
                
            #Restore object data from beginning
            self.restore_data_to_default(meshes_structure)
            
            for x in range (number_of_nodes):
                name_offset = struct.unpack("I", file.read(4))[0]
                data_offset = struct.unpack("I", file.read(4))[0]
                anim_segments_and_names.append(Anim_segments_and_names(name_offset, data_offset))
                
            for x in anim_segments_and_names:
                file.seek(x.name_offset + 18, 0)   #18 - header size
                name_of_bone = ""
                while 1:
                    char  = struct.unpack("c", file.read(1))[0]
                    if char[0] == 0: break
                    name_of_bone += char.decode()
                    
                print(name_of_bone)
                x.name = name_of_bone
                for i, y in enumerate(meshes_structure):
                    if name_of_bone == y.name:
                        x.which_mesh = i
                        #set non-important flag for objects like blnd
                        if y.is_bone == True or y.is_base == True:
                            x.is_important = True
                        else:
                            x.is_important = False
                        break
                
            #read frames data
            self.read_frames_data(anim_segments_and_names, meshes_structure, number_of_frames, file)
            
            #interpolate empty frames data
            self.interpolate(anim_segments_and_names, meshes_structure, number_of_frames)
                
            #set bone position
            self.set_bones_position(anim_segments_and_names, meshes_structure, base_number)
                    
            #animate vertices
            self.animate_vertices(meshes_structure, vertex_order)
                            
            bpy.context.scene.frame_start = 0
            bpy.context.scene.frame_end = number_of_frames - 1
            return {'FINISHED'}

class TOPBAR_MT_Mafia(bpy.types.Menu):
    bl_label = "Mafia Animations Importer"

    def draw(self, context):
        layout = self.layout
        layout.operator(Mafia4ds_Character.bl_idname, text = Mafia4ds_Character.bl_text)
        layout.operator(Mafia5ds_Importer.bl_idname, text = Mafia5ds_Importer.bl_text)
        
    def menu_draw(self, context):
        self.layout.menu("TOPBAR_MT_Mafia")


mafia_5ds_classes = (Mafia4ds_Character, Mafia5ds_Importer, TOPBAR_MT_Mafia, Mafia_character_import_preferences)


def register():
    for cls in mafia_5ds_classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.append(TOPBAR_MT_Mafia.menu_draw)



def unregister():
    for cls in mafia_5ds_classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.remove(TOPBAR_MT_Mafia.menu_draw)



if __name__ == "__main__":
    register()
