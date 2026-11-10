# Scene: inspect, clean, organize

## Inspect

```python
import bpy
print("engine:", bpy.context.scene.render.engine)
for o in bpy.data.objects:
    print(o.name, o.type, tuple(round(v, 3) for v in o.dimensions),
          "parent:", o.parent.name if o.parent else None)
```

Use `get_scene_info` first; use Python when you need dimensions, modifiers,
materials, or collection membership in one pass.

## Organize

```python
col = bpy.data.collections.get("Props") or bpy.data.collections.new("Props")
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)

obj = bpy.data.objects["Cube"]
for c in list(obj.users_collection):
    c.objects.unlink(obj)
col.objects.link(obj)
```

## Apply transforms (before export or boolean work)

```python
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
```

## Origin and placement

```python
# origin to geometry center, then sit on the ground
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
zmin = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
obj.location.z -= zmin
```

## Clean up

```python
# purge orphan data (meshes, materials, images with no users)
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
```

Never `bpy.ops.object.delete()` on a selection you did not create yourself.
Name the objects explicitly and confirm with the user first.

## Duplicate and instance

```python
src = bpy.data.objects["Chair"]
dup = src.copy()
dup.data = src.data.copy()          # real copy
bpy.context.scene.collection.objects.link(dup)
dup.location.x += 1.2
```

Use `dup.data = src.data` (shared mesh) for instances when memory matters.

## Modifiers

```python
m = obj.modifiers.new("Bevel", 'BEVEL')
m.width = 0.02
m.segments = 3
```

Apply modifiers before export when the target format does not support them.
