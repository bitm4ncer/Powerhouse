# Export: GLB, FBX, USDZ, OBJ, print

## Before every export

1. Apply scale (and rotation where the target expects it).
2. Apply modifiers if the format does not support them.
3. Select exactly what should ship; use `use_selection=True`.
4. Verify the result by re-importing it into a fresh scene and checking
   dimensions, materials, and triangle count.

## GLB (web, three.js, Babylon, Godot)

```python
bpy.ops.object.select_all(action='DESELECT')
for name in ["Subject", "Props"]:
    bpy.data.objects[name].select_set(True)
bpy.ops.export_scene.gltf(
    filepath="//export/model.glb",
    export_format='GLB',
    use_selection=True,
    export_apply=True,
    export_yup=True,
)
```

Keep textures packed. Check file size; web targets usually want < 10 MB.

## FBX (Unity, Unreal, Blender round-trip)

```python
bpy.ops.export_scene.fbx(
    filepath="//export/model.fbx",
    use_selection=True,
    apply_scale_options='FBX_SCALE_ALL',
    mesh_smooth_type='FACE',
    bake_anim=True,
)
```

Unity: Y-up, 1 unit = 1 m. Unreal: centimeters on import, keep scale 1 and let
the importer convert.

## USDZ (Apple, AR Quick Look)

Use Blender's USD exporter when the build supports `.usdz`; otherwise export
`.usdc`/`.glb` and convert with `usdzconvert` (Apple) or Reality Converter.
Validate on the target device, not just in Blender.

## OBJ (print, simple exchange)

```python
bpy.ops.wm.obj_export(
    filepath="//export/model.obj",
    export_selected_objects=True,
    export_materials=True,
    apply_modifiers=True,
)
```

## Print files (STL / 3MF)

- Manifold check: no loose geometry, no inverted normals, no self-intersections.
- Wall thickness and minimum feature size depend on the printer; ask.
- STL has no units; state millimeters and scale before export.
- 3MF keeps materials and multiple objects; prefer it when the slicer supports it.

```python
bpy.ops.wm.stl_export(filepath="//export/model.stl", export_selected_objects=True)
```

## Validation

```python
# fresh scene, re-import, compare
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.gltf(filepath="//export/model.glb")
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print("meshes:", len(objs), "tris:", sum(len(o.data.polygons) for o in objs))
print("dims:", [tuple(round(v, 3) for v in o.dimensions) for o in objs])
```

Then `look` at the re-imported scene. A file that imports is not automatically a
file that looks right.
