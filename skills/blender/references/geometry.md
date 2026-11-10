# Geometry nodes, materials, UV

## Geometry nodes

Create a node group and attach it:

```python
obj = bpy.data.objects["Plane"]
mod = obj.modifiers.new("GN", 'NODES')
ng = bpy.data.node_groups.new("GN_Array", 'GeometryNodeTree')
ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
mod.node_group = ng

nodes, links = ng.nodes, ng.links
gin = nodes.new('NodeGroupInput')
gout = nodes.new('NodeGroupOutput')
# ... build the graph ...
links.new(gin.outputs[0], gout.inputs[0])
```

### Recipes

- **Array:** `GeometryNodeMeshLine` (count, offset) → `GeometryNodeInstanceOnPoints`
  with the source mesh.
- **Scatter:** `DistributePointsOnFaces` → `InstanceOnPoints` (Poisson for
  organic, random for even).
- **Bevel/panel lines:** `GeometryNodeFilletCurve` on a curve, or a Bevel
  modifier for hard-surface.

Keep node graphs in a reference file in the project; do not rebuild the same
graph by hand twice.

## Procedural material

```python
mat = bpy.data.materials.new("Concrete")
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
noise = mat.node_tree.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 18.0
bump = mat.node_tree.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.15
mat.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
mat.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
```

Set base color on `bsdf.inputs['Base Color'].default_value`, roughness on
`bsdf.inputs['Roughness'].default_value`. Never use `mat.diffuse_color` for the
final look.

## UV unwrap

```python
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
bpy.ops.object.mode_set(mode='OBJECT')
```

Check the result with a checker texture before baking or texturing.

## Texture bake (Cycles)

1. Add an image texture node to the material, select it.
2. Set `scene.render.engine = 'CYCLES'`, `scene.cycles.bake_type = 'DIFFUSE'`.
3. `bpy.ops.object.bake(type='DIFFUSE')`.
4. Save the image to disk and reconnect it.

Bake only after UVs are clean; otherwise the result is wasted work.
