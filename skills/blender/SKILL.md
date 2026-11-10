---
name: blender
description: Build, edit, light, animate, and export 3D scenes in the user's live Blender through the Blender MCP. Use for modeling, scene cleanup, asset import (Poly Haven, Sketchfab, Poly Pizza), materials and shader nodes, lighting and camera setups, geometry nodes, renders and contact sheets, animation, and GLB/FBX/USDZ export. Trigger on "Blender", "3D model", "render", "scene", "GLB", "FBX", "USDZ", "geometry nodes", "material".
---

# Blender

You are driving someone else's live Blender through the Blender MCP, not a
throwaway headless process. Every change is visible to the user immediately.

## Before touching anything

1. `get_addon_status` — is the addon connected?
2. `get_scene_info` — objects, collections, active object, render engine.
3. State the plan in one or two sentences: what changes, what stays, how you
   will verify it.

If the scene contains work you did not create, ask before deleting, joining, or
overwriting objects. Save first when the change is destructive:

```python
bpy.ops.wm.save_mainfile()
```

## Hard rules

- **Look up shader nodes by type, never by name.** Names are localized:
  `next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")`.
- **Never hardcode enum identifiers.** Read them, then assign inside
  `try/except TypeError` and print the valid values when it fails:
  `[i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]`.
- **Material color goes on the shader node input**, not `material.diffuse_color`
  (that is viewport-only).
- **Verify visually with `look` after every visual change.** A successful
  `execute_blender_code` is not proof that the result looks right.
- **Keep code blocks small and idempotent.** One intent per call, print a compact
  result (`len(objects)`, `object.name`, bounding box), so the next step can
  decide without a full scene dump.
- **Units are meters.** 1 Blender unit = 1 m. Apply scale before export.
- **Imported assets arrive at arbitrary scale.** Use the reported
  `world_bounding_box`, scale to the intended real size, and place the lowest
  point on the ground.
- **`generate_3d` costs the user a credit.** Ask before using it, and generate
  one object, never a whole scene.

## Workflow

1. **Inspect** — scene, object dimensions, materials, existing camera/lights.
2. **Plan** — objects to add or edit, materials, camera, lights, output format.
3. **Build in small steps** — geometry, then materials, then camera/light.
4. **Look** — render a preview or viewport screenshot and check it.
5. **Refine** — fix what the look exposed; do not stack more changes blindly.
6. **Deliver** — render and/or export, then validate by re-importing.

## References

- [`references/scene.md`](references/scene.md) — inspect, clean, organize, transform
- [`references/assets.md`](references/assets.md) — search, import, scale, place
- [`references/look.md`](references/look.md) — camera, lights, render settings
- [`references/geometry.md`](references/geometry.md) — geometry nodes, materials, UV
- [`references/export.md`](references/export.md) — GLB, FBX, USDZ, OBJ, print files

## When the addon is not running

Tell the user to open Blender with the Blender MCP addon enabled. Do not fake a
result and do not start a separate headless Blender unless the user asks for it.
