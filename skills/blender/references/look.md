# Look: camera, lights, render

## Camera

```python
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.location = (6, -6, 4)

# aim at the subject
target = bpy.data.objects["Subject"]
tr = cam.constraints.new('TRACK_TO')
tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'
cam_data.lens = 50
```

## Three-point light

```python
def add_area(name, loc, energy, size=3.0, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy = energy
    d.size = size
    d.color = color
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o

key = add_area("Key", (4, -4, 5), 800)
fill = add_area("Fill", (-5, -3, 3), 250)
rim = add_area("Rim", (0, 5, 4), 500)
```

Point lights at the subject with `TRACK_TO` as above, or use an HDRI world for
even, realistic light.

## World / HDRI

```python
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Strength'].default_value = 0.6
# bg.inputs['Color'].default_value = (0.05, 0.05, 0.06, 1)
```

## Render settings

Read the current engine first; assign inside a try/except that prints valid
identifiers on failure.

```python
scene = bpy.context.scene
print([i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items])
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
except TypeError:
    scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
```

Cycles for final quality (slower), EEVEE for fast previews. Set samples:

```python
if scene.render.engine == 'CYCLES':
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
```

## Render and verify

```python
scene.render.filepath = "//renders/preview.png"
bpy.ops.render.render(write_still=True)
```

Then call `look` on the result. Check: subject in frame, no clipping, light
direction, material response, background.

## Contact sheet

Render several angles by moving the camera and collecting files; assemble with
ImageMagick or ffmpeg outside Blender. Keep the camera move deterministic
(angles, height, distance) so runs are comparable.
