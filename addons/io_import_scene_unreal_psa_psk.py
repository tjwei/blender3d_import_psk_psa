# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
# -*- coding: ASCII -*-
bl_info = {
    "name": "Import Unreal Skeleton Mesh (.psk)/Animation Set (.psa)",
    "author": "Darknet, flufy3d, camg188, befzz",
    "version": (2, 5),
    "blender": (2, 70, 0),
    "location": "File > Import > Skeleton Mesh (.psk)/Animation Set (.psa)",
    "description": "Import Skeleleton Mesh/Animation Data",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.5/Py/"
                "Scripts/Import-Export/Unreal_psk_psa",
    "category": "Import-Export",
}

"""
Version': '2.0' ported by Darknet

Unreal Tournament PSK file to Blender mesh converter V1.0
Author: D.M. Sturgeon (camg188 at the elYsium forum), ported by Darknet
Imports a *psk file to a new mesh

-No UV Texutre
-No Weight
-No Armature Bones
-No Material ID
-Export Text Log From Current Location File (Bool )
"""

"""
Version': '2.5+' edited by befzz

+ Animation import fix
+ Code cleaning
+ Much refractoring and improvements

"""

import bpy
import math
import re
import mathutils
from mathutils import Vector,Matrix,Quaternion
from bpy.props import FloatProperty, StringProperty, BoolProperty, CollectionProperty, IntProperty
from struct import unpack,unpack_from


bpy.types.Scene.unrealbonesize = FloatProperty(
    name="Bone Length",
    description="Bone Length from head to tail distance",
    default=0.5, min=0.01, max=10
)

from bpy_extras.io_utils import unpack_list, unpack_face_list


# regex_name = re.compile(b'[^\x00]+')
# def str_from_bytes_decode(in_bytes):
    # match_obj_name =regex_name.match(in_bytes)
    # if match_obj_name is None:
        # print('Can\'t get bone name!')
        # return False
    # return match_obj_name.group().decode(encoding='cp1252', errors='replace')
    
def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode=mode, toggle = False)

def str_from_bytes_decode(in_bytes):
    return in_bytes.rstrip(b'\x00').decode(encoding='cp1252', errors='replace')

class class_md5_bone:
    bone_index = 0
    name = ""
    bindpos = []
    bindmat = []
    origmat = []
    head = []
    tail = []
    scale = []
    parent = None
    parent_name = ""
    parent_index = 0
    blenderbone = None
    roll = 0

    def __init__(self):
        self.bone_index = 0
        self.name = ""
        self.bindpos = [0.0] * 3
        self.scale = [0.0] * 3
        self.head = [0.0] * 3
        self.tail = [0.0] * 3
        self.bindmat = [None] * 3
        for i in range(3):
            self.bindmat[i] = [0.0] * 3
        self.origmat = [None] * 3
        for i in range(3):
            self.origmat[i] = [0.0] * 3
        self.parent = ""
        self.parent_index = 0
        self.blenderbone = None

    def dump(self):
        print ("bone index: ", self.bone_index)
        print ("name: ", self.name)
        print ("bind position: ", self.bindpos)
        print ("bind translation matrix: ", self.bindmat)
        print ("parent: ", self.parent)
        print ("parent index: ", self.parent_index)
        print ("blenderbone: ", self.blenderbone)
        
def select_all(select):
    if select:
        actionString = 'SELECT'
    else:
        actionString = 'DESELECT'

    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action=actionString)

    if bpy.ops.mesh.select_all.poll():
        bpy.ops.mesh.select_all(action=actionString)

    if bpy.ops.pose.select_all.poll():
        bpy.ops.pose.select_all(action=actionString)

def util_ui_show_msg(msg):
    bpy.ops.error.message_popup('INVOKE_DEFAULT', message = msg)
        
PSKPSA_FILE_HEADER = {
    'psk':{'chunk_id':b'ACTRHEAD\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'},
    'psa':{'chunk_id':b'ANIMHEAD\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'}
}
#TODO check chunk flag?
def util_is_header_valid(filename, ftype, chunk_id, chunk_flag):
    if chunk_id != PSKPSA_FILE_HEADER[ftype]['chunk_id']:
        util_ui_show_msg(
            "The selected input file is not a " + ftype +
                        " file (header mismach)"
            "\nExpected: "+str(PSKPSA_FILE_HEADER[ftype]['chunk_id'])+
            "\nPresent: "+str(chunk_id)
        )    
        return False
    return True
    
def util_gen_name_part(filepath):
    '''strip path and extension from path'''
    return re.match(r'.*[/\\]([^/\\]+?)(\..{2,5})?$', filepath).group(1)
    
def pskimport(infile, bImportmesh, bImportbone, bDebugLogPSK, bImportmultiuvtextures):
    if not bImportbone and not bImportmesh:
        util_ui_show_msg("Nothing to do.\nSet something for import.")
        return False
    file_ext = 'psk'
    DEBUGLOG = bDebugLogPSK
    print ("--------------------------------------------------")
    print ("---------SCRIPT EXECUTING PYTHON IMPORTER---------")
    print ("--------------------------------------------------")
    print (" DEBUG Log:",bDebugLogPSK)
    print (" Importing file:", infile)

    #file may not exist(while running from script)
    try:
        pskfile = open(infile,'rb')
    except IOError:
        util_ui_show_msg('Error while opening file for reading:\n  "'+infile+'"')
        return False
    
    if DEBUGLOG:
        #logpath = infile.lower().replace("."+file_ext, ".txt")
        logpath = infile+".txt"
        print("logpath:",logpath)
        logf = open(logpath,'w')

    def printlog(strdata):
        if (DEBUGLOG):
            logf.write(strdata)

    # using this instead of class to avoid "object.prop" lookup 3x faster.
    chunk_header_id = None
    chunk_header_type = None
    chunk_header_datasize = None
    chunk_header_datacount = None
    #all binary data of chunk for unpack (bytearray)
    chunk_data = None
    
    #=================================================
    #         VChunkHeader Struct
    # ChunkID|TypeFlag|DataSize|DataCount
    # 0      |1       |2       |3
    #=================================================
    # read a header and chunk data to local variables
    def read_chunk():
        nonlocal chunk_header_id,\
                 chunk_header_type,\
                 chunk_header_datasize,\
                 chunk_header_datacount,\
                 chunk_data
        #read header
        (chunk_header_id,
         chunk_header_type,
         chunk_header_datasize,
         chunk_header_datacount) = unpack('20s3i', pskfile.read(32))
        
        # print('HEADER',chunk_header_id, chunk_header_type, chunk_header_datasize, chunk_header_datacount)
        
        # read all chunk data
        chunk_data = pskfile.read(chunk_header_datacount * chunk_header_datasize)

        
    # accept non ".psk" extension(can by supllied by script: bpy.ops.import_scene.psk())
    # should work good with "c:\file.some.model.psk" and "/home/xd/model.psk"
    # remove file extension( "." with 2-5 characters after it and at end of string)
    gen_name_part = util_gen_name_part(infile)
    gen_names = {
        'armature_object':  gen_name_part + '.ao',
        'armature_data':    gen_name_part + '.ad',
            'mesh_object':  gen_name_part + '.mo',
            'mesh_data':    gen_name_part + '.md'
    }
    if bImportmesh:
        mesh_data = bpy.data.meshes.new(gen_names['mesh_data'])
        printlog("New Mesh Data = " + mesh_data.name + "\n")
    
    # read general header (datasize & datacount is zero)
    read_chunk()
    
    # check file header
    if not util_is_header_valid(infile, file_ext, chunk_header_id, chunk_header_type):
        return False
    
    # Performance tips:
    #---------------------------------
    # for X in range(C):
    #    ....
    #
    # is faster then
    #
    # while X < C:
    #      X+=1
    #
    # tested. and proof link:
    # http://stackoverflow.com/questions/11241523/why-does-python-code-run-faster-in-a-function
    #---------------------------------
    # list preallocation is faster too:
    # http://stackoverflow.com/questions/311775/python-create-a-list-with-initial-capacity?answertab=active#tab-top
    #---------------------------------
    # creating many tuples is faster then do the same with list
    # http://stackoverflow.com/questions/3340539/why-is-tuple-faster-than-list
    
    #================================================================================================== 
    # vertex point
    #================================================================================================== 
    #read the PNTS0000 header ( VPoint )
    read_chunk()
    if bImportmesh:
        printlog("Nbr of PNTS0000 records: " + str(chunk_header_datacount) + "\n")

        verts  = [None] * chunk_header_datacount
        # verts2 = [None] * chunk_header_datacount
        
        for counter in range( chunk_header_datacount ):
            (vec_x, vec_y, vec_z) = unpack_from('3f', chunk_data, counter * chunk_header_datasize)
            verts[counter]  = (vec_x, vec_y, vec_z)
            # verts2[counter] = (vec_x, vec_y, vec_z)
            
            printlog(str(vec_x) + "|" + str(vec_y) + "|" + str(vec_z) + "\n")
            
            #Tmsh.vertices.append(NMesh.Vert(indata[0], indata[1], indata[2]))

    #================================================================================================== 
    # UV
    #================================================================================================== 
    # https://github.com/gildor2/UModel/blob/master/Exporters/Psk.h
    # for struct of VVertex
    #
    #read the VTXW0000 header (VVertex)
    read_chunk()
    
    if bImportmesh:
        printlog("Nbr of VTXW0000 records: " + str(chunk_header_datacount)+ "\n")

        UVCoords = [None] * chunk_header_datacount
        #UVCoords record format = [index to PNTS, U coord, v coord]
        printlog("[index to PNTS, U coord, v coord]\n");
        for counter in range( chunk_header_datacount ):
            (point_index,
             u, v,
             material_index) = unpack_from('=IffBxxx', chunk_data, counter * chunk_header_datasize )
            # print(point_index, u, v, material_index)
            UVCoords[counter] = (point_index, u, v)
            printlog(str(point_index) + "|" + str(u) + "|" + str(v) + "\n")

    #================================================================================================== 
    # Face
    #================================================================================================== 
    #read the FACE0000 header
    read_chunk()
    if bImportmesh:
        printlog("Nbr of FACE0000 records: " + str(chunk_header_datacount) + "\n")
        #PSK FACE0000 fields: WdgIdx1|WdgIdx2|WdgIdx3|MatIdx|AuxMatIdx|SmthGrp
        #associate MatIdx to an image, associate SmthGrp to a material
        SGlist = []

        faces = [None] * chunk_header_datacount
        faceuv = [None] * chunk_header_datacount
        facesmooth = []
        printlog("nWdgIdx1|WdgIdx2|WdgIdx3|MatIdx|AuxMatIdx|SmthGrp \n")
        
        # smlist = []
        mat_groups = {}
        
        for counter in range(chunk_header_datacount):
            (vertexA, vertexB, vertexC,
             MatIndex, AuxMatIndex,
             SmoothingGroup
             ) = unpack_from('hhhbbi', chunk_data, counter * chunk_header_datasize)
             
            printlog(str(vertexA)  + "|" + str(vertexB)     + "|" + str(vertexC)+ "|" 
                   + str(MatIndex) + "|" + str(AuxMatIndex) + "|" + str(SmoothingGroup) + "\n")
            # vertex[ABC] is index of 3 points of face
            #
            # UVCoords is(point_index, u, v)
            #             0            1  2
            PNTSA = UVCoords[vertexC][0]
            PNTSB = UVCoords[vertexB][0]
            PNTSC = UVCoords[vertexA][0]
            #print(PNTSA, PNTSB, PNTSC) #face id vertex
            #faces.extend([0, 1, 2, 0])
            faces[counter] = (PNTSA, PNTSB, PNTSC, 0)
            # uv = []
            # u0 = UVCoords[vertexC][1]
            # v0 = UVCoords[vertexC][2]
            # uv.append([u0, 1.0 - v0])
            # u1 = UVCoords[vertexB][1]
            # v1 = UVCoords[vertexB][2]
            # uv.append([u1, 1.0 - v1])
            # u2 = UVCoords[vertexA][1]
            # v2 = UVCoords[vertexA][2]
            # uv.append([u2, 1.0 - v2])
            uv = (
                ( UVCoords[vertexC][1], 1.0 - UVCoords[vertexC][2] ),
                ( UVCoords[vertexB][1], 1.0 - UVCoords[vertexB][2] ),
                ( UVCoords[vertexA][1], 1.0 - UVCoords[vertexA][2] )
            )
            
            faceuv[counter] = (uv, MatIndex, AuxMatIndex, SmoothingGroup)

            if not MatIndex in mat_groups:
                print('mat:', MatIndex)
                mat_groups[MatIndex] = []
            mat_groups[MatIndex].append( uv )

            #collect a list of the smoothing groups
            facesmooth.append(SmoothingGroup)

            # if not indata[5] in smlist:
                # print('SM:',indata[5])
                # smlist.append(indata[5])
                
            if SGlist.count(SmoothingGroup) == 0:
                SGlist.append(SmoothingGroup)
                # print("smooth:", SmoothingGroup)
            #assign a material index to the face
            #Tmsh.faces[-1].materialIndex = SGlist.index(indata[5])
        printlog("Using Materials to represent PSK Smoothing Groups...\n")
        
        for mg in mat_groups:
            print('mat_group,len:',mg,len(mat_groups[mg]))
    
    #================================================================================================== 
    # Material
    #================================================================================================== 
    #read the MATT0000 header
    
    read_chunk()
    if bImportmesh:
        printlog("Nbr of MATT0000 records: " +  str(chunk_header_datacount) + "\n" )
        printlog(" - Not importing any material data now. PSKs are texture wrapped! \n")
        counter = 0

        materials = []
        
        for counter in range(chunk_header_datacount):

            (MaterialNameRaw,
             TextureIndex,
             PolyFlags,
             AuxMaterial,
             AuxFlags,
             LodBias,
             LodStyle ) = unpack_from('64s6i', chunk_data, chunk_header_datasize * counter)
            
            materialname = str_from_bytes_decode( MaterialNameRaw )
            matdata = bpy.data.materials.new(materialname)
            materials.append(matdata)
            mesh_data.materials.append(matdata)
            # print("Mat %i name:" % counter, materialname,TextureIndex,PolyFlags)

    #================================================================================================== 
    # Bones (Armature)
    #================================================================================================== 
    #read the REFSKEL0 header
    read_chunk()

    printlog( "Nbr of REFSKEL0 records: " + str(chunk_header_datacount) + "\n")
    #REFSKEL0 fields - Name|Flgs|NumChld|PrntIdx|Qw|Qx|Qy|Qz|LocX|LocY|LocZ|Lngth|XSize|YSize|ZSize

    md5_bones = []
    bni_dict = {}

    printlog("Name|Flgs|NumChld|PrntIdx|Qx|Qy|Qz|Qw|LocX|LocY|LocZ|Lngth|XSize|YSize|ZSize\n")

    for counter in range( chunk_header_datacount ):
        
        indata = unpack_from('64s3i11f', chunk_data, chunk_header_datasize * counter)
    
        md5_bone = class_md5_bone()
      
        temp_name = str_from_bytes_decode(indata[0])

        printlog(temp_name + "|" + str(indata[1]) + "|" + str(indata[2]) + "|" + str(indata[3]) + "|" +
                 str(indata[4]) + "|" + str(indata[5]) + "|" + str(indata[6]) + "|" + str(indata[7]) + "|" +
                 str(indata[8]) + "|" + str(indata[9]) + "|" + str(indata[10]) + "|" + str(indata[11]) + "|" +
                 str(indata[12]) + "|" + str(indata[13]) + "|" + str(indata[14]) + "\n")
        md5_bone.name = temp_name
        md5_bone.bone_index = counter
        md5_bone.parent_index = indata[3]
        md5_bone.bindpos[0] = indata[8]
        md5_bone.bindpos[1] = indata[9]
        md5_bone.bindpos[2] = indata[10]
        md5_bone.scale[0] = indata[12]
        md5_bone.scale[1] = indata[13]
        md5_bone.scale[2] = indata[14]

        bni_dict[md5_bone.name] = md5_bone.bone_index

        #w,x,y,z
        QuartMat = Quaternion((indata[7], -indata[4], -indata[5], -indata[6])).to_matrix()

        md5_bone.bindmat = QuartMat
        md5_bone.origmat = QuartMat
        
        md5_bone.bindmat = Matrix.Translation(\
                                 Vector((indata[8], indata[9], indata[10]))
                           ) *  md5_bone.bindmat.to_4x4()
        md5_bone.quater = QuartMat.to_4x4()
        md5_bones.append(md5_bone)
        print(counter,temp_name,indata[3])
    
    # root bone must have parent_index = 0 and selfindex = 0
    # sounds like this code little useless, bcs only first bone can be root with this conditions
    for md5_bone in md5_bones:
        if md5_bone.parent_index == 0:
            if md5_bone.bone_index == 0:
                md5_bone.parent = None
                continue
        md5_bone.parent =  md5_bones[md5_bone.parent_index]
        md5_bone.parent_name = md5_bone.parent.name
        md5_bone.bindmat = md5_bone.parent.bindmat * md5_bone.bindmat

    print ("-------------------------")
    print ("----Creating--Armature---")
    print ("-------------------------")

    #================================================================================================
    #Check armature if exist if so create or update or remove all and addnew bone
    #================================================================================================
    
    # obj = None
    # for obj in bpy.context.scene.objects:
        # if type(obj.data) is bpy.types.Armature:
            # armObj = obj
            # break
    
    # force create new armature if need
    if bImportbone:
        armature_data = bpy.data.armatures.new(gen_names['armature_data'])
        armature_obj = bpy.data.objects.new(gen_names['armature_object'], armature_data)

        bpy.context.scene.objects.link(armature_obj)
        #bpy.ops.object.mode_set(mode='OBJECT')

        select_all(False)
        armature_obj.select = True
        
        #set current armature to edit the bone
        bpy.context.scene.objects.active = armature_obj
        
        # TODO: options for axes and x_ray?
        armature_data.show_axes = True
        armature_obj.show_x_ray = True

        # print("creating bone(s)")
        
        #Go to edit mode for the bones
        utils_set_mode('EDIT')
        
        for md5_bone in md5_bones:
            edit_bone = armature_obj.data.edit_bones.new(md5_bone.name)
            edit_bone.use_connect = False
            edit_bone.use_inherit_rotation = True
            edit_bone.use_inherit_scale = True
            edit_bone.use_local_location = True
            # armature_obj.data.edit_bones.active = edit_bone

            if not md5_bone.parent is None:
                edit_bone.parent = armature_obj.data.edit_bones[md5_bone.parent_name]
            
            # rolling and directing bone
            rotmatrix = md5_bone.bindmat.to_3x3().to_4x4()
            
            ####ROT_VARIANT_1_BEGIN
            # tail_end_dir = rotmatrix * Vector((0,0,1))
            # tail_end_up  = rotmatrix * Vector((0,1,0))
            ####ROT_VARIANT_1_END
            
            ####ROT_VARIANT_2_BEGIN
            tail_end_up  = rotmatrix * Vector((0,0,1))
            tail_end_dir = rotmatrix * Vector((1,0,0))
            ####ROT_VARIANT_2_END
            
            tail_end_up.normalize()
            tail_end_dir.normalize()
            
            edit_bone.head = md5_bone.bindmat.translation
            edit_bone.tail = edit_bone.head + tail_end_dir * bpy.context.scene.unrealbonesize
            
            edit_bone.align_roll(tail_end_up)
            
    #bpy.context.scene.update()

    #bpy.ops.object.mode_set(mode='EDIT')
    #==================================================================================================
    #END BONE DATA BUILD
    #==================================================================================================
    if bImportmesh:
        VtxCol = []
        bones_count = len(md5_bones)
        for x in range(bones_count):
            #change the overall darkness of each material in a range between 0.1 and 0.9
            tmpVal = ((float(x) + 1.0) / bones_count * 0.7) + 0.1
            tmpVal = int(tmpVal * 256)
            tmpCol = [tmpVal, tmpVal, tmpVal, 0]
            #Change the color of each material slightly
            if x % 3 == 0:
                if tmpCol[0] < 128:
                    tmpCol[0] += 60
                else:
                    tmpCol[0] -= 60
            if x % 3 == 1:
                if tmpCol[1] < 128:
                    tmpCol[1] += 60
                else:
                    tmpCol[1] -= 60
            if x % 3 == 2:
                if tmpCol[2] < 128:
                    tmpCol[2] += 60
                else:
                    tmpCol[2] -= 60
            #Add the material to the mesh
            VtxCol.append(tmpCol)

    #================================================================================================== 
    # Bone Weight
    #================================================================================================== 
    #read the RAWW0000 header (VRawBoneInfluence)(Weight|PntIdx|BoneIdx)
    read_chunk()

    printlog("Nbr of RAWW0000 records: " + str(chunk_header_datacount) +"\n")

    RWghts = [None] * chunk_header_datacount

    for counter in range(chunk_header_datacount):
        (Weight,
         PointIndex,
         BoneIndex ) = unpack_from('fii', chunk_data, chunk_header_datasize * counter)
         
        RWghts[counter] = (PointIndex, BoneIndex, Weight)
        
        #print("weight:", PointIndex, BoneIndex, Weight)
    #RWghts fields = PntIdx|BoneIdx|Weight
    RWghts.sort( key=lambda wgh: wgh[0])
    printlog("Vertex point and groups count =" + str(len(RWghts)) + "\n")
    printlog("PntIdx|BoneIdx|Weight")
    for vg in RWghts:
        printlog(str(vg[0]) + "|" + str(vg[1]) + "|" + str(vg[2]) + "\n")

    #Tmsh.update_tag()

    #set the Vertex Colors of the faces
    #face.v[n] = RWghts[0]
    #RWghts[1] = index of VtxCol
    """
    for x in range(len(Tmsh.faces)):
        for y in range(len(Tmsh.faces[x].v)):
            #find v in RWghts[n][0]
            findVal = Tmsh.faces[x].v[y].index
            n = 0
            while findVal != RWghts[n][0]:
                n = n + 1
            TmpCol = VtxCol[RWghts[n][1]]
            #check if a vertex has more than one influence
            if n != len(RWghts) - 1:
                if RWghts[n][0] == RWghts[n + 1][0]:
                    #if there is more than one influence, use the one with the greater influence
                    #for simplicity only 2 influences are checked, 2nd and 3rd influences are usually very small
                    if RWghts[n][2] < RWghts[n + 1][2]:
                        TmpCol = VtxCol[RWghts[n + 1][1]]
        Tmsh.faces[x].col.append(NMesh.Col(TmpCol[0], TmpCol[1], TmpCol[2], 0))
    """
    if (DEBUGLOG):
        logf.close()
    #================================================================================================== 
    #Building Mesh
    #================================================================================================== 
    if bImportmesh:
        print("vertex:", len(verts), "faces:", len(faces))

        mesh_data.vertices.add(len(verts))
        mesh_data.tessfaces.add(len(faces))
        mesh_data.vertices.foreach_set("co", unpack_list( verts ))
        mesh_data.tessfaces.foreach_set("vertices_raw", unpack_list( faces ))

        # for face in mesh_data.tessfaces:
            # .use_smooth is True or False - but facesmooth contains an int
            # TODO FIXME still incorrect
            # if facesmooth[face.index] > 0:
                # face.use_smooth = True

        """
        Material setup coding.
        First the mesh has to be create first to get the uv texture setup working.
        -Create material(s) list in the psk pack data from the list.(to do list)
        -Append the material to the from create the mesh object.
        -Create Texture(s)
        -face loop for uv assign and assign material index
        """
        utils_set_mode('OBJECT')

    #===================================================================================================
    #UV Setup
    #===================================================================================================
    if bImportmesh:
        print ("-------------------------")
        print ("-- Creating UV Texture --")
        print ("-------------------------") 

        if bImportmultiuvtextures:
            for countm in range(len(materials)):
                mesh_data.uv_textures.new(name = "psk_uv_map_multi_" + str(countm))

            print("INIT UV TEXTURE...")

            _textcount = 0
            for uv in mesh_data.tessface_uv_textures: # uv texture
                print("UV TEXTURE ID:",_textcount)
                
                for face in mesh_data.tessfaces:# face, uv
                    # faceuv is [] of (f_uv, MatIndex, AuxMatIndex, SmoothingGroup)
                    #                  0     1         2            3
                    # f_uv   is       ((u,v),(u,v),(u,v))
                    if faceuv[face.index][1] == _textcount: #if face index and texture index matches assign it
                        mfaceuv = faceuv[face.index] #face index
                        #assign material to face
                        face.material_index = faceuv[face.index][1]
                        
                        _uv1 = mfaceuv[0][0] #(0,0)
                        _uv2 = mfaceuv[0][1] #(0,0)
                        _uv3 = mfaceuv[0][2] #(0,0)
                        uv.data[face.index].uv1 = Vector((_uv1[0], _uv1[1])) #set them
                        uv.data[face.index].uv2 = Vector((_uv2[0], _uv2[1])) #set them
                        uv.data[face.index].uv3 = Vector((_uv3[0], _uv3[1])) #set them
                    else: #if not match zero them
                        uv.data[face.index].uv1 = Vector((0, 0)) #zero them 
                        uv.data[face.index].uv2 = Vector((0, 0)) #zero them 
                        uv.data[face.index].uv3 = Vector((0, 0)) #zero them 
                    
                _textcount += 1

                #for tex in mesh_data.uv_textures:
                    #print("mesh tex:", dir(tex))
                    #print((tex.name))
                    
        else: #single UV map
            mesh_data.uv_textures.new(name = "psk_uv_map_single")
            uvmap =  mesh_data.tessface_uv_textures[-1]
            print(len(uvmap.data))
            for face in mesh_data.tessfaces:
                face.material_index = faceuv[face.index][1]
                face_uv = faceuv[face.index][0]
                uvmap.data[face.index].uv1 = Vector((face_uv[0][0], face_uv[0][1]))
                uvmap.data[face.index].uv2 = Vector((face_uv[1][0], face_uv[1][1]))
                uvmap.data[face.index].uv3 = Vector((face_uv[2][0], face_uv[2][1]))
        
        mesh_obj = bpy.data.objects.new(gen_names['mesh_object'],mesh_data)
    #===================================================================================================
    #Mesh Vertex Group bone weight
    #===================================================================================================

    if bImportmesh:
        #create bone vertex group #deal with bone id for index number
        for md5_bone in md5_bones:
            # group = mesh_obj.vertex_groups.new(bone.name)
            mesh_obj.vertex_groups.new(md5_bone.name)  
     
        for vgroup in mesh_obj.vertex_groups:
            # print(vgroup.name, ":", vgroup.index) 
            bone_index = bni_dict[vgroup.name]
            for vgp in RWghts:
                # vgp: 0, 1, 2 (vertexId, bone index, weight)
                if vgp[1] == bone_index:
                    vgroup.add((vgp[0],), vgp[2], 'ADD')

        mesh_data.update()
        
        bpy.context.scene.objects.link(mesh_obj)   
        bpy.context.scene.update()

        select_all(False)
        mesh_obj.select = True
        bpy.context.scene.objects.active = mesh_obj
    
        if bImportbone:
            # parenting mesh to armature object
            mesh_obj.parent = armature_obj
            mesh_obj.parent_type = 'OBJECT'
            # add armature modifier
            blender_modifier = mesh_obj.modifiers.new( armature_obj.data.name, type='ARMATURE')
            blender_modifier.show_expanded = False
            blender_modifier.use_vertex_groups = True
            blender_modifier.use_bone_envelopes = False
            blender_modifier.object = armature_obj
        
    utils_set_mode('OBJECT')
    return True
#End of def pskimport#########################

class class_psa_bone:
    name=""
    Transform=None
    parent=None
    
    fcurve_loc_x = None
    fcurve_loc_y = None
    fcurve_loc_z = None
    fcurve_quat_x = None
    fcurve_quat_y = None
    fcurve_quat_z = None
    fcurve_quat_w = None
    
    def __init__(self):
        self.name=""
        self.Transform = None
        self.parent = None

def psaimport(filepath, context, bFilenameAsPrefix = False, bActionsToTrack = False):
    print ("--------------------------------------------------")
    print ("---------SCRIPT EXECUTING PYTHON IMPORTER---------")
    print ("--------------------------------------------------")
    print ("Importing file: ", filepath)
    file_ext = 'psa'
    try:
        psafile = open(filepath, 'rb')
    except IOError:
        util_ui_show_msg('Error while opening file for reading:\n  "'+filepath+'"')
        return False
    
    debug = True
    if (debug):
        # logpath = filepath.lower().replace("."+file_ext, ".txt")
        logpath = filepath+".txt"
        print("logpath:", logpath)
        logf = open(logpath, 'w')
        
    def printlog(strdata):
        if not debug:
            return
        logf.write(strdata)
        
    def printlogplus(name, data):
        if not debug:
            return

        logf.write(str(name) + '\n')
        if isinstance(data, bytes):
            # logf.write(str(bytes.decode(data).strip(bytes.decode(b'\x00'))))
            logf.write( str_from_bytes_decode(data) )
        else:
            logf.write(str(data))
        logf.write('\n')

    def write_log_plus(*args):
        if not debug:
            return
        for arg in args:
            if isinstance(arg, bytes):
                logf.write( str_from_bytes_decode(arg) + '\t')
            else:
                logf.write( str(arg) + '\t' )
        logf.write('\n')

    def write_log_plus_headers():
        write_log_plus(
            'ChunkID ',  chunk_header_id,
            'TypeFlag ', chunk_header_type,
            'DataSize ', chunk_header_datasize,
            'DataCount ',chunk_header_datacount)
        
    #check is there any armature
    armature_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            armature_obj = obj
            break
    if armature_obj is None:
        util_ui_show_msg("No armatures found.\nImport armature from psk file first.")
        if(debug):
            logf.close()
        return False

    chunk_header_id = None
    chunk_header_type = None
    chunk_header_datasize = None
    chunk_header_datacount = None
    chunk_data = None

    def read_chunk():
        nonlocal chunk_header_id,\
                 chunk_header_type,\
                 chunk_header_datasize,\
                 chunk_header_datacount,\
                 chunk_data

        (chunk_header_id,
         chunk_header_type,
         chunk_header_datasize,
         chunk_header_datacount) = unpack('20s3i', psafile.read(32))
        
        chunk_data = psafile.read(chunk_header_datacount * chunk_header_datasize)

    #General Header
    read_chunk()
    write_log_plus_headers()
    if not util_is_header_valid(filepath, file_ext, chunk_header_id, chunk_header_type):
        if(debug):
            logf.close()
        return False
    
    #==============================================================================================
    # Bones (FNamedBoneBinary)
    #==============================================================================================
    read_chunk()
    write_log_plus_headers()
    
    #Bones Data
    BoneIndex2NamePairMap = [None] * chunk_header_datacount
    BoneNotFoundList = []
    #unused
    #printlog("Name|Flgs|NumChld|PrntIdx|Qx|Qy|Qz|Qw|LocX|LocY|LocZ|Length|XSize|YSize|ZSize\n")

    nobonematch = True
    
    for counter in range(chunk_header_datacount):
        indata = unpack_from('64s3i11f', chunk_data, chunk_header_datasize * counter)

        bonename = str_from_bytes_decode(indata[0])
        if bonename in armature_obj.data.bones.keys():
            BoneIndex2NamePairMap[counter] = bonename
            print('find bone', bonename)
            nobonematch = False
        else:
            print('can not find the bone:', bonename)
            BoneNotFoundList.append(counter)

    if nobonematch:
        util_ui_show_msg('No bone was match!\nSkip import!')
        if(debug):
            logf.close()
        return False
    #==============================================================================================
    # Animations (AniminfoBinary)
    #==============================================================================================
    read_chunk()
    write_log_plus_headers()

    Raw_Key_Nums = 0
    Action_List = [None] * chunk_header_datacount
    
    for counter in range(chunk_header_datacount):
        (action_name_raw,        #0
         group_name_raw,         #1
         Totalbones,             #2
         RootInclude,            #3
         KeyCompressionStyle,    #4
         KeyQuotum,              #5
         KeyReduction,           #6
         TrackTime,              #7
         AnimRate,               #8
         StartBone,              #9
         FirstRawFrame,          #10
         NumRawFrames            #11
        ) = unpack_from('64s64s4i3f3i', chunk_data, chunk_header_datasize * counter)
        
        write_log_plus( 'Name',        action_name_raw,
                        'Group',       group_name_raw,
                        'totalbones',  Totalbones,
                        'NumRawFrames',NumRawFrames
                       )
                       
        action_name = str_from_bytes_decode( action_name_raw )
        group_name  = str_from_bytes_decode( group_name_raw  )

        Raw_Key_Nums += Totalbones * NumRawFrames
        Action_List[counter] = ( action_name, group_name, Totalbones, NumRawFrames)


    #==============================================================================================
    #Raw keys (VQuatAnimKey)
    #==============================================================================================
    read_chunk()
    write_log_plus_headers()
    
    
    if(Raw_Key_Nums != chunk_header_datacount):
        util_ui_show_msg(
                'Raw_Key_Nums Inconsistent.'
                '\nData count found: '+chunk_header_datacount+
                '\nRaw_Key_Nums:' + Raw_Key_Nums
                )
        if(debug):
            logf.close()
        return False

    Raw_Key_List = [None] * chunk_header_datacount
    
    for counter in range(chunk_header_datacount):
        ( vec_x,  vec_y,  vec_z,
         quat_x, quat_y, quat_z, quat_w,
         time_until_next
        ) = unpack_from('3f4f1f', chunk_data, chunk_header_datasize * counter)
        
        pos = Vector((vec_x, vec_y, vec_z))
        quat = Quaternion((quat_w, quat_x, quat_y, quat_z))
        
        Raw_Key_List[counter] = (pos, quat, time_until_next)

    #Scale keys Header, Scale keys Data, Curve keys Header, Curve keys Data
    curFilePos = psafile.tell()
    psafile.seek(0, 2)
    endFilePos = psafile.tell()
    if curFilePos == endFilePos:
        print('no Scale keys,Curve keys')
    else:
        print('== FOUND SOMETHING ==')

    #build the animation line
    utils_set_mode('OBJECT')
    
    NeededBoneMatrix = {}
    '''
    if bpy.context.scene.udk_importarmatureselect:
        if len(bpy.context.scene.udkas_list) > 0:
            print("CHECKING ARMATURE...")
            #for bone in bpy.data.objects[ARMATURE_OBJ].pose.bones:
            #for objd in bpy.data.objects:
                #print("NAME:", objd.name, " TYPE:", objd.type)
                #if objd.type == 'ARMARURE':
                    #print(dir(objd))
            armature_list = bpy.context.scene.udkas_list #armature list array
            armature_idx = bpy.context.scene.udkimportarmature_list_idx #armature index selected
            ARMATURE_OBJ = bpy.data.objects[armature_list[armature_idx]].name #object armature
            ARMATURE_DATA = bpy.data.objects[armature_list[armature_idx]].data.name #object data
    '''

    #build tmp pose bone tree
    psa_bones = {}
    for bone in armature_obj.pose.bones:
        psa_bone = class_psa_bone()
        psa_bone.name = bone.name
        psa_bone.Transform = bone.matrix
        if bone.parent != None:
            psa_bone.parent = psa_bones[bone.parent.name]
        else:
            psa_bone.parent = None
        psa_bones[bone.name] = psa_bone

    #print('Started for raw_action in Action_List:')
   
    raw_key_index = 0
    object = armature_obj
    
    ###dev
    def scene_update():
        bpy.context.scene.update()
    
    # unbind meshes, that use this armature
    # because scene.update() calculating its positions
    # but we don't need it - its a big waste of time
    
    armature_modifiers = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        
        for modifier in obj.modifiers:
            if modifier.type != 'ARMATURE':
                continue
            if modifier.object == armature_obj:
                armature_modifiers.append(modifier)
                modifier.object = None
    scene_update()
    
    ####ROT_VARIANT_1_BEGIN
    # mat_pose_rot_fix = Matrix.Rotation(math.pi,4,'Y') * Matrix.Rotation(-math.pi/2,4,'X')
    ####ROT_VARIANT_1_END
    
    ####ROT_VARIANT_2_BEGIN
    mat_pose_rot_fix = Matrix.Rotation(-math.pi/2, 4, 'Z')
    ####ROT_VARIANT_2_END
    
    counter = 0
    gen_name_part = util_gen_name_part(filepath)
    
    armature_obj.animation_data_create()
    
    if bActionsToTrack:
        nla_track = armature_obj.animation_data.nla_tracks.new()
        nla_track.name = gen_name_part
        nla_stripes = nla_track.strips
        nla_track_last_frame = 0
    else:
        is_first_action = True
        first_action = None
        
    for raw_action in Action_List:
        Name = raw_action[0]
        Group = raw_action[1]
        if Group != 'None':
            Name = "(%s) %s" % (Group,Name)
        if bFilenameAsPrefix:
            Name = "(%s) %s" % (gen_name_part, Name)
        Totalbones = raw_action[2]
        NumRawFrames = raw_action[3]
        action = bpy.data.actions.new(name = Name)

        if True:
            counter += 1
            print("Action {0:>3d}/{1:<3d} frames: {2:>4d} {3}".format(
                    counter, len(Action_List), NumRawFrames, Name)
                  )
                
        #create all fcurves(for all bones) for frame
        for pose_bone in armature_obj.pose.bones:
            psa_bone = psa_bones[pose_bone.name]
            
            data_path = pose_bone.path_from_id("rotation_quaternion")
            psa_bone.fcurve_quat_w = action.fcurves.new(data_path, index=0)
            psa_bone.fcurve_quat_x = action.fcurves.new(data_path, index=1)
            psa_bone.fcurve_quat_y = action.fcurves.new(data_path, index=2)
            psa_bone.fcurve_quat_z = action.fcurves.new(data_path, index=3)
        
            data_path = pose_bone.path_from_id("location")
            psa_bone.fcurve_loc_x = action.fcurves.new(data_path, index=0)
            psa_bone.fcurve_loc_y = action.fcurves.new(data_path, index=1)
            psa_bone.fcurve_loc_z = action.fcurves.new(data_path, index=2)
            
        pose_bones = object.pose.bones
        for i in range(NumRawFrames):
        # for i in range(0,5):
            for j in range(Totalbones):
                if j not in BoneNotFoundList:
                    bName = BoneIndex2NamePairMap[j]
                    pbone = psa_bones[bName]
                    pose_bone = pose_bones[bName]
                    
                    pos = Raw_Key_List[raw_key_index][0]
                    quat = Raw_Key_List[raw_key_index][1]
                    
                    # mat = Matrix()
                    quat_c = quat.conjugated()
                    if pbone.parent != None:
                        
                        # matrix for calc's // calc from parent
                        mat = Matrix.Translation(pos) * quat_c.to_matrix().to_4x4() 
                        mat = pbone.parent.Transform * mat 

                        # matrix for posing
                        mat_view = pbone.parent.Transform * Matrix.Translation(pos) 
                        
                        rot = pbone.parent.Transform.to_quaternion() * quat_c
                        rot = rot.to_matrix().to_4x4()
                         
                        pose_bone.matrix = Matrix.Translation(mat_view.translation)*\
                                                     rot * mat_pose_rot_fix
                        
                        # save mat for children calc's
                        pbone.Transform = mat
                    else:
                        #TODO fix needed?
                        mat = Matrix.Translation(pos) * quat.to_matrix().to_4x4()
                        pose_bone.matrix = mat
                        pbone.Transform = mat
                    # update(calc) data (relative coordinates /location & rotation_quaternion/)
                    #bpy.context.scene.update
                    
                    ###dev
                    scene_update()
                    
                    loc = pose_bone.location
                    quat = pose_bone.rotation_quaternion
                    
                    pbone.fcurve_quat_w.keyframe_points.insert(i,quat.w)
                    pbone.fcurve_quat_x.keyframe_points.insert(i,quat.x)
                    pbone.fcurve_quat_y.keyframe_points.insert(i,quat.y)
                    pbone.fcurve_quat_z.keyframe_points.insert(i,quat.z)

                    pbone.fcurve_loc_x.keyframe_points.insert(i,loc.x)
                    pbone.fcurve_loc_y.keyframe_points.insert(i,loc.y)
                    pbone.fcurve_loc_z.keyframe_points.insert(i,loc.z)

                raw_key_index += 1
            
            # for bone in pose_bones:
                #bone.matrix = psa_bones[bone.name].Transform
                # bone.keyframe_insert("rotation_quaternion")
                # bone.keyframe_insert("location")
                
        if bActionsToTrack:
            if nla_track_last_frame == 0:
                nla_stripes.new(Name, 0, action)
            else:
                nla_stripes.new(Name, nla_stripes[-1].frame_end, action)
            nla_track_last_frame += NumRawFrames
        elif is_first_action:
            first_action = action
            is_first_action = False
            
        #break on first animation set
        # break
    
    
    # set to rest position or set to first imported action
    if not bActionsToTrack:
        # for pose_bone in armature_obj.pose.bones:
            # pose_bone.rotation_quaternion = (1,0,0,0)
            # pose_bone.location = (0,0,0)
            
        object.animation_data.action = first_action
    context.scene.frame_set(0)
    ##scene_update()
    

    # bind meshes again (setup modifier)
    for modifier in armature_modifiers:
        modifier.object = armature_obj
        
    if(debug):
        logf.close()
 
class MessageOperator(bpy.types.Operator):
    bl_idname = "error.message_popup"
    bl_label = ""

    message = StringProperty(default='Message')
    lines = []
    def execute(self, context):
        self.lines = self.message.split("\n")
        maxlen = 0
        for line in self.lines:
            if len(line) > maxlen:
                maxlen = len(line)
            print(line)
        # self.lines.append("")
        wm = context.window_manager
        return wm.invoke_popup(self, width=30+6*maxlen, height=400)

    def draw(self, context):
        layout = self.layout
        layout.label("[PSA/PSK Importer]", icon='ANIM')

        for line in self.lines:
            # row = self.layout.row(align=True)
            # row.alignment = 'LEFT'
            layout.label(line)

def getInputFilenamepsk(self, filename, bImportmesh, bImportbone, bDebugLogPSK, bImportmultiuvtextures):
    return pskimport(         filename, bImportmesh, bImportbone, bDebugLogPSK, bImportmultiuvtextures)

def getInputFilenamepsa(self, filename, context, _bFilenameAsPrefix, _bActionsToTrack):
    return psaimport(         filename, context, bFilenameAsPrefix=_bFilenameAsPrefix, bActionsToTrack=_bActionsToTrack)

class IMPORT_OT_psk(bpy.types.Operator):
    '''Load a skeleton mesh psk File'''
    bl_idname = "import_scene.psk"
    bl_label = "Import PSK"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'UNDO'}

    filepath = StringProperty(
            subtype='FILE_PATH',
            )
    filter_glob = StringProperty(
            default="*.psk",
            options={'HIDDEN'},
            )
    bImportmesh = BoolProperty(
            name="Mesh",
            description="Import mesh.",
            default=True,
            )
    bImportbone = BoolProperty(
            name="Bones",
            description="Import bones and create armature.",
            default=True,
            )
    bImportmultiuvtextures = BoolProperty(
            name="Single UV Texture(s)",
            description="Single or Multi uv textures",
            default=True,
            )
    bDebugLogPSK = BoolProperty(
            name="Debug Log.txt",
            description="Log the output of raw format. It will save in "
                        "current file dir. Note this just for testing",
            default=True,
            )
    unrealbonesize = bpy.types.Scene.unrealbonesize
    # FloatProperty(
            # name="Bone Length",
            # description="Bone Length from head to tail distance",
            # default=.5,
            # min=0.01,
            # max=100,
            # )

    def execute(self, context):
        # bpy.types.Scene.unrealbonesize = self.unrealbonesize
        no_errors = getInputFilenamepsk(self, 
                        self.filepath,
                        self.bImportmesh, self.bImportbone, self.bDebugLogPSK,
                        self.bImportmultiuvtextures
                    )
        if not no_errors:
            return {'CANCELLED'}
        else:
            return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

class IMPORT_OT_psa(bpy.types.Operator):
    '''Load a skeleton anim psa File'''
    bl_idname = "import_scene.psa"
    bl_label = "Import PSA"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    filepath = StringProperty(
            subtype='FILE_PATH',
            )
    filter_glob = StringProperty(
            default="*.psa",
            options={'HIDDEN'},
            )
    bFilenameAsPrefix = BoolProperty(
            name="Prefix action names",
            description="Use filename as prefix for action names.",
            default=False,
            )
    bActionsToTrack = BoolProperty(
            name="All actions to NLA track",
            description="Add all imported action to new NLAtrack. One by one.",
            default=False,
            )
    def execute(self, context):
        getInputFilenamepsa(self, self.filepath, context, self.bFilenameAsPrefix, self.bActionsToTrack)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

bpy.types.Scene.udk_importpsk = StringProperty(
        name = "Import .psk",
        description = "Skeleton mesh file path for psk",
        default = "")
bpy.types.Scene.udk_importpsa = StringProperty(
        name = "Import .psa",
        description = "Animation Data to Action Set(s) file path for psa",
        default = "")
bpy.types.Scene.udk_importarmatureselect = BoolProperty(
        name = "Armature Selected",
        description = "Select Armature to Import psa animation data",
        default = False)

class Panel_UDKImport(bpy.types.Panel):
    bl_label = "UDK Import"
    bl_idname = "OBJECT_PT_udk_import"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    filepath = StringProperty(
            subtype='FILE_PATH',
            )

    #@classmethod
    #def poll(cls, context):
    #   return context.active_object

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_PSKPath.bl_idname)

        layout.prop(context.scene, "udk_importarmatureselect")
        if bpy.context.scene.udk_importarmatureselect:
            layout.operator(OBJECT_OT_UDKImportArmature.bl_idname)
            layout.template_list("UI_UL_list", "udkimportarmature_list", context.scene, "udkimportarmature_list",
                                 context.scene, "udkimportarmature_list_idx", rows=5)
        layout.operator(OBJECT_OT_PSAPath.bl_idname)

class OBJECT_OT_PSKPath(bpy.types.Operator):
    """Select .psk file path to import for skeleton mesh"""
    bl_idname = "object.pskpath"
    bl_label = "Import PSK Path"

    filepath = StringProperty(
            subtype='FILE_PATH',
            )
    filter_glob = StringProperty(
            default="*.psk",
            options={'HIDDEN'},
            )
    bImportmesh = BoolProperty(
            name="Mesh",
            description="Import mesh.",
            default=True,
            )
    bImportbone = BoolProperty(
            name="Bones",
            description="Import bones.",
            default=True,
            )
    bImportmultiuvtextures = BoolProperty(
            name="Single UV Texture(s)",
            description="Single or Multi uv textures",
            default=True,
            )
    bDebugLogPSK = BoolProperty(
            name="Debug Log.txt",
            description="Log the output of raw format. It will save in " \
                        "current file dir. Note this just for testing",
            default=False,
            )
    unrealbonesize = bpy.types.Scene.unrealbonesize
    # unrealbonesize = FloatProperty(
            # name="Bone Length",
            # description="Bone Length from head to tail distance",
            # default=1,
            # min=0.001,
            # max=1000,
            # )

    def execute(self, context):
        #context.scene.importpskpath = self.properties.filepath
        # bpy.types.Scene.unrealbonesize = self.unrealbonesize
        getInputFilenamepsk(self, self.filepath, self.bImportmesh, self.bImportbone, self.bDebugLogPSK,
                            self.importmultiuvtextures)
        return {'FINISHED'}

    def invoke(self, context, event):
        #bpy.context.window_manager.fileselect_add(self)
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

class UDKImportArmaturePG(bpy.types.PropertyGroup):
    #boolean = BoolProperty(default=False)
    string = StringProperty()
    bexport = BoolProperty(default=False, name="Export", options={"HIDDEN"},
                           description = "This will be ignore when exported")
    bselect = BoolProperty(default=False, name="Select", options={"HIDDEN"},
                           description = "This will be ignore when exported")
    otype = StringProperty(name="Type",description = "This will be ignore when exported")

bpy.utils.register_class(UDKImportArmaturePG)
bpy.types.Scene.udkimportarmature_list = CollectionProperty(type=UDKImportArmaturePG)
bpy.types.Scene.udkimportarmature_list_idx = IntProperty()

class OBJECT_OT_PSAPath(bpy.types.Operator):
    """Select .psa file path to import for animation data"""
    bl_idname = "object.psapath"
    bl_label = "Import PSA Path"

    filepath = StringProperty(
            name="PSA File Path",
            description="Filepath used for importing the PSA file",
            maxlen=1024,
            default=""
            )
    filter_glob = StringProperty(
            default="*.psa",
            options={'HIDDEN'},
            )
    bFilenameAsPrefix = BoolProperty(
            name="Prefix action names",
            description="Use filename as prefix for action names.\nAsd",
            default=False
            )
    def execute(self, context):
        #context.scene.importpsapath = self.properties.filepath
        getInputFilenamepsa(self,self.filepath,context)
        return {'FINISHED'}

    def invoke(self, context, event):
        bpy.context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class OBJECT_OT_UDKImportArmature(bpy.types.Operator):
    """This will update the filter of the mesh and armature"""
    bl_idname = "object.udkimportarmature"
    bl_label = "Update Armature"

    def execute(self, context):
        my_objlist = bpy.context.scene.udkimportarmature_list
        objectl = []
        for objarm in bpy.context.scene.objects:#list and filter only mesh and armature
            if objarm.type == 'ARMATURE':
                objectl.append(objarm)
        for _objd in objectl:#check if list has in udk list
            bfound_obj = False
            for _obj in my_objlist:
                if _obj.name == _objd.name and _obj.otype == _objd.type:
                    _obj.bselect = _objd.select
                    bfound_obj = True
                    break
            if bfound_obj == False:
                #print("ADD ARMATURE...")
                my_item = my_objlist.add()
                my_item.name = _objd.name
                my_item.bselect = _objd.select
                my_item.otype = _objd.type
        removeobject = []
        for _udkobj in my_objlist:
            bfound_objv = False
            for _objd in bpy.context.scene.objects: #check if there no existing object from sense to remove it
                if _udkobj.name == _objd.name and _udkobj.otype == _objd.type:
                    bfound_objv = True
                    break
            if bfound_objv == False:
                removeobject.append(_udkobj)
        #print("remove check...")
        for _item in removeobject: #loop remove object from udk list object
            count = 0
            for _obj in my_objlist:
                if _obj.name == _item.name and _obj.otype == _item.otype:
                    my_objlist.remove(count)
                    break
                count += 1
        return{'FINISHED'}

class OBJECT_OT_UDKImportA(bpy.types.Operator):
    """This will update the filter of the mesh and armature"""
    bl_idname = "object.udkimporta"
    bl_label = "Update Armature"

    def execute(self, context):
        for objd in bpy.data.objects:
            print("NAME:",objd.name," TYPE:",objd.type)
            if objd.type == "ARMATURE":
                #print(dir(objd))
                print((objd.data.name))
        return{'FINISHED'}

def menu_func(self, context):
    self.layout.operator(IMPORT_OT_psk.bl_idname, text="Skeleton Mesh (.psk)")
    self.layout.operator(IMPORT_OT_psa.bl_idname, text="Skeleton Anim (.psa)")

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_func)

if __name__ == "__main__":
    register()
