import bpy

#make sure any necessary files are packed before local references are made
bpy.ops.file.pack_all()

for obj in bpy.data.objects:
	obj.make_local
    
bpy.ops.file.pack_all()

bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)