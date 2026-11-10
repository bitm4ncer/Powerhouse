# Assets: search, import, scale, place

## Order of preference

1. **Existing scene objects** — reuse before importing.
2. **`search_assets`** — Poly Haven (HDRIs, materials, models), Sketchfab,
   Poly Pizza. Free or CC0 where possible; check the license shown.
3. **`generate_3d`** — one object from text or an image, 1–3 minutes, may cost a
   credit. Ask first. It generates one object, never a scene, ground, or parts to
   assemble.

## Import

Use the `import_asset` tool, not a manual download, so the addon tracks the
source and license. Then:

```python
import bpy
obj = bpy.context.selected_objects[0]
print(obj.name, obj.type)
print("dims:", tuple(round(v, 3) for v in obj.dimensions))
print("bbox world:", [tuple(round(c, 3) for c in (obj.matrix_world @ __import__('mathutils').Vector(v))) for v in obj.bound_box])
```

## Scale to a real size

```python
target_height_m = 1.8
current = obj.dimensions.z
if current > 0:
    obj.scale *= target_height_m / current
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
```

## Place on the ground

```python
from mathutils import Vector
zmin = min((obj.matrix_world @ Vector(v)).z for v in obj.bound_box)
obj.location.z -= zmin
```

## Material sanity check

Many imported assets arrive with textures packed or linked. Check:

```python
for slot in obj.material_slots:
    m = slot.material
    if not m:
        continue
    print(m.name, [n.type for n in m.node_tree.nodes] if m.use_nodes else "no nodes")
```

If textures are missing, ask before replacing them; the original look may be the
point.

## Heavy meshes

Decimate for real-time targets, never for a hero render:

```python
m = obj.modifiers.new("Decimate", 'DECIMATE')
m.ratio = 0.4
```

Tell the user the before/after triangle count.

## Licensing

Record the source and license of every imported asset in the project notes. Do
not ship assets whose license forbids redistribution.
