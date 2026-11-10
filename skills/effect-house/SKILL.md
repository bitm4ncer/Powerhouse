---
name: effect-house
description: Use when working on a TikTok Effect House project (.ehproj, main.scene, graph.json, .otextureseq, .animTex, .ts script components, APJS), reading or hand-editing Effect House project files, writing TypeScript script components, debugging visual scripting graphs, or when an Effect House MCP server is involved.
---

# Effect House

TikTok's AR effect editor. Projects are plain files on disk, so an agent can read and edit them directly, but several formats are undocumented and easy to corrupt. This skill records what has been verified by inspection on a real machine, so you do not have to rediscover it.

**Core principle: never guess a format. Every answer below already exists on disk somewhere. Find the ground truth first.**

## The three ground-truth sources

Before writing any Effect House code or editing any project file, read the relevant one.

| What you need | Where it actually is |
|---|---|
| Complete TypeScript API (classes, properties, JSDoc) | `<project>/Library/CompiledScripts/Types/APJS.d.ts` (~630 KB), generated after the editor compiles a project once. Also `PostProcess.d.ts`, `TweenAnimation.d.ts`, `LeaderBoard.d.ts` and others alongside it. |
| Component names and their property wire types | `<install>/Resources/ask-ai/type_registry.json`. Maps editor-facing component names to `apjsClass`, `getComponentString`, and every property with its `wireType`. |
| Every built-in visual scripting node | `<install>/Resources/BuiltinResource/ScriptGraph/**/node.json`, roughly 550 files. Each has full input and output port schemas. |

Install path on Windows: `C:\Users\<user>\AppData\Local\Effect House\`.

A fourth source is often decisive: `%APPDATA%\EffectHouse\Backup\<timestamp>_<n>\` holds complete project snapshots, dozens of them. If you need the exact YAML for a component you have never written, find a backup that already uses it and copy the shape.

```bash
grep -rl "Text2D\|__class: Text" "$APPDATA/EffectHouse/Backup"/*/Assets/main.scene | head
```

## Project layout

```
effect.ehproj              JSON. Name, version, templateID, effectUploadResult, layer names.
Assets/
  main.scene               YAML. All entities, components, transforms.
  main.scene.extra         Editor sidecar.
  Textures/                Imported images, each with a .extra sidecar.
  Animated Textures/       .animTex wrappers with fps and duration.
  Scripts/**/*.ts          User TypeScript components, each with a .ts.extra sidecar.
Graph/
  graph.json               Visual scripting nodes and edges.
  graph.backup
  ScriptTemplate/<Node>/   JS source of every node the graph actually uses.
Library/
  CompiledScripts/         Editor output. Types/APJS.d.ts lives here.
  CacheData, CacheData-lock
EffectSettings/            Physics, resolution, submission settings.
Record/, Icon/
```

## main.scene is YAML, not JSON

```yaml
%YAML 1.1
--- !Scene &1
entities:
  - __class: Entity
    name: !<str> Negativ
    guid: {a: 11694812076081163593, b: 10762037306206190976}
    components:
      - {localId: 2}                    # reference to a --- !Transform &2 document below
      - __class: EffectNode             # inline component
        renderOrder: 2001
--- !Transform &2
localPosition: {x: 0, y: 0, z: 0}
children:
  - {localId: 3}
```

Things that bite:

- Strings carry an explicit `!<str>` tag. Drop it and the file may not load.
- `{localId: N}` points at the `--- !Class &N` document further down the same file. Transforms always live as separate documents, components are usually inline.
- Entity guids are **two unsigned 64-bit integers** `{a, b}`. Asset guids are **dashed UUID strings**. These are different systems, do not mix them.
- Asset references inside the scene look like `{localId: 1, path: <asset-guid>}` or `{localId: 1, path: <guid>--<guid>.png}`. Built-in resources use all-zero guids with a suffix, for example `00000000-0000-0000-0000-000000000009` is the shared render target and `00000000-0000-0000-0000-000000fa0006` is the vignette material.
- Python's `json` module fails on `main.scene`. Read it as text, or use a YAML parser that tolerates the custom tags.

## The .extra sidecar system

Every asset has a `<file>.extra` next to it: a JSON array with one object holding the editor-side guid and import settings. This is what the editor's asset browser reads. **An asset without a correct `.extra` does not exist as far as the editor is concerned.**

Verified `extraType` values:

| extraType | For |
|---|---|
| `ResItemPNGImage` | Imported PNG. Has `resourceFilePath` pointing at the original on disk. |
| `ResItemTextureSequence` | A `.otextureseq` flipbook. |
| `ResItemAnimatedTexture` | A `.animTex`. Its `references` array links to the sequence guid by `propertyName`. |
| `ResItemJSScript` | A user `.ts` script. Carries `isUserScript: true` and `needCompile: true`. |

## Texture sequences take three files

A flipbook named `foo` is:

```
Assets/Textures/foo.otextureseq              zero bytes, just a marker
Assets/Textures/foo.otextureseq.extra        guid + ResItemTextureSequence
Assets/Textures/foo.otextureseq.folder/      0.png 1.png 2.png ... plus folder.ignore
Assets/Animated Textures/foo.animTex         YAML: fps, duration, loopCount, playMode
Assets/Animated Textures/foo.animTex.extra   guid + reference to the sequence guid
```

Frames are numbered from `0.png`, and `duration` must equal `frameCount / fps` or playback drifts. The scene's `ImageRenderer` points at the **animTex** guid, not the sequence guid.

Import order is not guaranteed to match filename order. A sequence imported from `rim01..rim05` can end up stored as `4.png..0.png`. Always check the direction rather than assuming.

## Script components: the good path

Prefer a TypeScript script component over a large visual scripting graph. It is one readable file, it is diffable, and it can do everything the graph can.

```ts
@component()
export class Kontostand extends APJS.BasicScriptComponent {

  @serializeProperty
  @tooltip("Shown in the Effect House inspector.")
  idleText: string = "???";

  @serializeProperty
  @slider(4, 30, 1)
  spinFps: number = 12;

  @serializeProperty
  @tooltip("Drag a scene object in here.")
  label: APJS.SceneObject;

  private txt!: APJS.Text;

  private recordStartCb: (e: APJS.IEvent) => void;

  onInit(): void {
    this.txt = this.label.getComponent("Text") as APJS.Text;
    this.recordStartCb = () => this.startSpin();
    APJS.EventManager.getGlobalEmitter()
      .on(APJS.EventType.RecordStart, this.recordStartCb, this);
  }

  onUpdate(dt: number): void { /* ... */ }

  onDestroy(): void {
    APJS.EventManager.getGlobalEmitter()
      .off(APJS.EventType.RecordStart, this.recordStartCb, this);
  }
}
```

**Lifecycle hooks**, all of them, from `BasicScriptComponent`:
`onInit`, `onStart`, `onUpdate(dt)`, `onLateUpdate(dt)`, `onEvent(e)`, `onEnable`, `onDisable`, `onDestroy`.

**Decorators:** `@component()`, `@serializeProperty`, `@tooltip(text)`, `@slider(min, max, step)`, `@spinBox(min, max, step)`.

**Inspector field types.** Per the editor's own `SerializeProperty` skill, these round-trip:
`number`, `boolean`, `string`, `APJS.Color`, `APJS.Vector2f/3f/4f`, `APJS.Quaternionf`,
`APJS.SceneObject`, `APJS.Transform`, `APJS.Texture`, `APJS.Material`, `APJS.JsonAsset`,
`APJS.AudioAsset`, and exactly two array types: `APJS.SceneObject[]` and `APJS.Texture[]`.

Arrays of primitives such as `string[]` and `number[]` are **not** in the supported set. For a
list of strings or a data table, use `APJS.JsonAsset` and read it with `this.asset?.json ?? {}`.
That also lets a non-programmer edit the data without recompiling anything.

**Component-subclass fields silently fail.** `@serializeProperty cam!: APJS.Camera` (or `Text`,
`Image`, `RigidBody`, any `Component` subclass) appears to wire up and reports success, but the
GUID does not persist and reads back as `null`. Always serialize the host `APJS.SceneObject` and
resolve the component at runtime:

```ts
@serializeProperty private labelObj: APJS.SceneObject;
private label!: APJS.Text;
onStart(): void { this.label = this.labelObj.getComponent("Text") as APJS.Text; }
```

The same trap applies to `APJS.Prefab` for prefabs derived from Screen Image / 2D UI subtrees.
Workaround: keep a hidden template `SceneObject` and `clone()` it at runtime.

**Global events:** `APJS.EventType` contains `RecordStart`, `RecordEnd`, `GlobalRecordStart`, `GlobalRecordEnd`, `Touch`, plus sensor and scene-time events. Subscribe in `onInit`, unsubscribe in `onDestroy`, otherwise handlers survive effect reset and fire twice.

**Visibility:** `sceneObject.setEnabledInHierarchy(bool)`.

**`@serializeProperty` fields are null in `onStart()`.** The editor populates them at scene load,
which happens after `onStart`. Resolving `getComponent` there yields nulls and the script looks
dead. Subscribe to events in `onStart`, but resolve scene references lazily on the first
`onUpdate`, behind a `bereit` / `ready` guard, and call the same guard from any event handler that
can fire before the first frame.

```ts
private ready = false;
onUpdate(dt: number): void { this.ensureReady(); /* ... */ }
private ensureReady(): void {
  if (this.ready) return;
  if (!this.someObject) return;        // editor has not filled it in yet
  this.img = this.someObject.getComponent("Image") as APJS.Image;
  this.ready = true;
}
```

**Serialized values land in main.scene**, not in the `.ts`. A script component appears as `__class: DynamicComponent` with `className: !<str> <script-asset-guid>` and a `properties` map. Scene object references serialize as `{localId: N}`.

The editor compiles `.ts` on open into `Library/CompiledScripts/`. You do not precompile. `tsconfig.json` at the project root uses `experimentalDecorators` and includes `Library/CompiledScripts/Types/**/*.d.ts`.

## Visual scripting graph.json

```
containers[0].graph.nodeList    array of nodes
containers[0].graph.edgeList    array of edges
```

Each node has `inputPorts` and `outputPorts`. A port that is not connected carries its literal in `portValue.value`. Edges reference ports by `sourcePortId` and `targetPortId`, so you must build a port-id to node map before an edge list means anything:

```python
p2n = {}
for i, n in enumerate(nodeList):
    for p in n.get("inputPorts", []) + n.get("outputPorts", []):
        p2n[p["__uniqueId"]] = (i, n["name"], p["portName"], p["type"])
```

Port `type` is `CONTROL` (execution pulses) or `DATA`. Reading the two separately makes an unfamiliar graph legible in one pass.

`Set Component Property` nodes are `__class: PropertyNode` and carry the target outside the ports: `property`, `extraType`, `pinObjectGuid`, and a `pinData` block with the display name.

Graphs accumulate dead nodes: nodes whose `Enter` port is unconnected never execute. Check before assuming a node matters.

## Known gotchas

**Close the editor before hand-editing.** Effect House holds `Library/CacheData-lock` and writes the project back on save. Edits made while it is open get silently overwritten.

**Component name mismatch.** The editor calls it Text, `type_registry.json` keys it `Text2D`, the scene writes `__class: Text`, and code calls `getComponent("Text")`. Property names differ too: the editor's `input` is `text` in APJS. Check `apjsClass` and `apjsAccessor` in the registry.

**Text components are large in YAML.** A single `Text` entity pulls in a `letters` array, plus `activeTextStyle`, `typeSettingParam`, `canvas` and `globalBackground` as separate YAML documents. Hand-authoring one is the most error-prone edit in a scene file. Prefer creating it in the editor, or copy a whole entity from a backup project.

**Effect House cannot use custom fonts. At all.** This is the single biggest constraint on any
brand work, and it is not stated anywhere obvious. Four independent confirmations:

- `import_source` rejects `.ttf` and `.otf` ("the engine rejected ... without a specific reason"),
  for untouched system fonts as well as generated ones.
- `type_registry.json` has **no** `Font` resource type. The full list is texture variants plus
  `ArtTextAsset`. Nothing else.
- `Text2D` has no font-asset slot. Its `fontType` is a `String` constrained to a fixed dropdown,
  defined in `Resources/ask-ai/schemas/component_schemas.json` under `"property": "fontType"`.
- The Asset Library has no font category (only makeup, filter, screen, accessory, sticker,
  character).

The 19 built-in faces are: Classic (TikTok Display Medium), Bold, Heavy, Serene, Oblique,
Elegance (Cormorant Garamond), Serif (Libre Baskerville), Vintage (Crimson Text), Retro,
Postcard, Script, Handwriting, Freehand (Caveat), Typewriter, Telegraph, Comic Sans, Luxury
(Arapey), Lite (Neon), Curious Cat. Classic is the neutral grotesque and the closest thing to a
generic corporate sans.

**Consequence for brand work:** if the effect must render text in a corporate typeface, runtime
`Text2D` is not an option. Bake the strings into images or a texture sequence outside the editor
(ImageMagick plus the real font), import the PNGs, and swap textures from an APJS script. You
still get code-driven values: keep the strings in a JSON file, generate the PNGs from it, and
wire the results into `APJS.Texture[]` inspector arrays, which **are** serializable. `ArtTextAsset`
does not help either: those are curated stylized presets, import-only, not your typeface.

**Corporate fonts also ship minimal glyph sets**, which matters for the bake path. Verify before
promising a character:

```python
from fontTools.ttLib import TTFont
cmap = TTFont(path).getBestCmap()
print(0x2076 in cmap)   # superscript six
```

A real case: `SparkasseHead_Rg.ttf` has 334 glyphs, includes `¹ ² ³` (Latin-1) and `∞` and `€`, but is missing `⁰ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹` (the U+2070 block). Missing superscripts can be synthesised into a copy of the font with fontTools by scaling the normal digit glyph and raising it, then mapping it to the missing codepoint.

**effect.ehproj carries stale state.** A project forked from a template keeps `templateID`, `templateName`, and `effectUploadResult` pointing at the previous upload. Clear those for a new effect.

**`.vscode/settings.json`** in Effect House projects hides generated noise (`main.scene`, `Graph/`, `**/*.extra`, `Library/CompiledScripts/{Editor,Src,Out}`). Useful pattern, but remember those hidden files are exactly the ones an agent needs to read.

## The `tteh` MCP server: reach it even when it is not wired into your session

**This is the single most useful thing in this skill. Check for it before falling back to hand-editing files.**

Effect House ships its own automation server. While the editor is running it listens on
`http://localhost:<port>/mcp?agent=claude` and identifies itself as `serverInfo.name == "tteh"`.
The observed default port is **9100**. Config template with the port placeholder:
`<install>/Resources/ask-ai/workspace/.mcp.json`.

The editor's own "Ask AI" panel is just a terminal that runs a CLI agent (`opencode`, `claude`,
`codex`, or `cursor`, per `Resources/ask-ai/default_agents.json`) against that server. So "Ask AI
shows Connected" does **not** mean your session has the tools. It means the server is up.

You do not need the panel, and you do not need to restart your session to add an MCP entry.
Speak JSON-RPC to it over HTTP directly:

```python
import json, urllib.request
URL = "http://localhost:9100/mcp?agent=claude"
H = {"Content-Type": "application/json",
     "Accept": "application/json, text/event-stream",
     "X-TTEH-Agent": "claude"}

def rpc(method, params, timeout=180):
    req = urllib.request.Request(
        URL, data=json.dumps({"jsonrpc": "2.0", "id": 1,
                              "method": method, "params": params}).encode(),
        headers=H, method="POST")
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    lines = [l[6:] for l in raw.splitlines() if l.startswith("data: ")]
    return json.loads(lines[-1] if lines else raw)

rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "probe", "version": "1"}})
rpc("tools/call", {"name": "describe_project", "arguments": {}})
```

Responses come back as SSE (`event: message` / `data: {...}`), so take the last `data:` line.
No session header is required. Discover the port from the Effect House process rather than
hardcoding it, and give the probe a short timeout since the editor listens on other ports too:

```powershell
$p = Get-Process | Where-Object { $_.ProcessName -eq 'Effect House' }
Get-NetTCPConnection -State Listen |
  Where-Object { $p.Id -contains $_.OwningProcess -and $_.LocalAddress -eq '127.0.0.1' } |
  Select-Object -ExpandProperty LocalPort
```

**32 tools**, grouped by what they are for:

| Purpose | Tools |
|---|---|
| Orient | `describe_project`, `get_scene`, `get_scene_view`, `list_resources`, `inspect`, `project_status` |
| Read | `read_script`, `read_visual_scripting_graph`, `preview_asset`, `get_script_logs`, `get_changes` |
| Edit | `edit_by_dsl`, `apply_template`, `save_project`, `create_project`, `open_project` |
| Verify | `capture_preview`, `interact_by_dsl`, `set_preview_video`, `list_preview_videos` |
| Knowledge | `query_knowledge`, `search_game_design`, `search_library`, `trending_effects` |
| Assets | `generate_image`, `generate_gif`, `query_gif_task`, `cancel_gif_task` |
| Handoff | `save_plan`, `get_handoff_context`, `log` |

`capture_preview` and `interact_by_dsl` matter most: they let you drive the live preview,
including the record lifecycle, and look at the result. Never claim an effect works without them.

The DSL used by `edit_by_dsl` is documented in
`<install>/Resources/ask-ai/workspace/EDIT_DSL_REFERENCE.md`.

**Read the editor's own skill library first.** `<install>/Resources/ask-ai/workspace/skills/`
holds 50+ skills written by the Effect House team (`SerializeProperty`, `Lifecycle`, `IEvent`,
`Timing`, `Touch`, `UIComponents`, `ScreenTransform`, `ScriptDebug`, `VisualScriptingGraph`,
`GraphToApjsPorting`, `Randomizer`, `Physics2D`, and more), plus a 64 KB `AGENTS.md` and a
`catalog.json`. These are authoritative and they contradict guesswork. Consult them before
designing anything.

Traces the MCP leaves in a project root: `outputs/mcp/` (screenshots, generated images) and
`.ai-context.json` (`searchedAssets`, `annotations`, `config.allow_interact`).

**Graph projects are read-only to the MCP.** `describe_project` flags any project containing a
visual scripting graph as "legacy, READ-ONLY — never generate or modify the graph". The
sanctioned paths are: add an APJS script that co-exists with the graph, or port the graph to
APJS entirely. See the editor's `VisualScriptingGraph` and `GraphToApjsPorting` skills.

**Editing over the MCP mutates the user's open project.** Reads are safe. Before `edit_by_dsl`,
`save_project`, `create_project`, or `open_project`, confirm with the user, and check
`project_status` for unsaved changes first.

## Driving the MCP: the traps that cost real time

**`capture_preview` screenshots too early.** It reloads the scene and grabs a frame before the
first `onUpdate` runs, so anything a script sets up lazily is still missing. The card shows its
authored texture, effects sit at their editor defaults, objects the script hides are visible, and
the build looks broken when it is not. Split the verification into **two separate MCP calls** so
real time passes between them:

```
interact_by_dsl [{reset_preview}]     # call 1
interact_by_dsl [{screenshot}]        # call 2, seconds later
```

`wait` would be neater but it is gated (see below); two calls are not.

**Interactive preview commands are gated.** `touch`, `drag`, `wait`, `start_preview_record`,
`stop_preview_record`, pause/resume and transport all require `config.allow_interact: true` in the
project's `.ai-context.json`, which defaults to false. `screenshot` and `reset_preview` always
work. Do not flip the flag yourself; ask the user. Documented fallback for a state you cannot
trigger: add a temporary `@serializeProperty` test field that forces the state, flip it with
`set_component` (no recompile needed), screenshot, then remove the field.

**Built-in objects do not start neutral.** `add_builtin_object("Vignette")` arrives with
`power: 1`, `"Lens Flare"` with `intensity: 0.5`, and `"Filter"` in LUT mode with a LUT already
assigned. Reset them explicitly, or the idle state ships with effects on. For `Filter`, switch to
colour correction: `{lutEnabled: false, colorCorrEnabled: true, saturation: 0}`.

**`edit_by_dsl` cannot reach PostProcess sub-effect parameters.** The DSL exposes only
`postProcessList` on a `PostProcess` component; `pVignettePower`, `vignette.power` and every
variant are rejected as unknown properties. Those live at runtime only:

```ts
const pp = obj.getComponent("PostProcess") as any;
pp.vignette.power = 1.4;              // Vignette: power, contrast
pp.lensFlare.intensity = 0.8;         // LensFlare: intensity, position
pp.lensFlare.position = new APJS.Vector2f(0.7, 0.9);
```

One built-in object per effect. Adding names to `postProcessList` after creation leaves the new
sub-effect accessors null and every assignment silently no-ops.

**Not every component has a TypeScript type.** `APJS.FilterV2` does not exist and fails compilation
with TS2694; the component string `"FilterV2"` still works with `getComponent`. `Vignette` and
`LensFlare` are typed, but in `PostProcess.d.ts`, not `APJS.d.ts`. When a type is missing, hold the
result as `any` rather than inventing a name.

**Fail-fast batches hide later work.** One rejected command skips every command after it in the
same `edit_by_dsl` call, while the ones before it stay applied. Check `failed` and per-command
`status` on every response, and re-send only the failed remainder, never the whole batch.

**Shells mangle JSON arguments.** Backslash-heavy Windows paths passed inline through a shell lose
an escape level and break `json.loads`. Write the arguments to a file and read them from there, and
prefer forward slashes in paths — the server accepts them everywhere.

**Backups rotate.** `%APPDATA%/EffectHouse/Backup/` keeps a fixed number of snapshots and drops the
oldest. A project you read there may be gone an hour later, so copy anything you need as reference
rather than pointing at it twice.

## Checklist for hand-editing a project

1. Confirm Effect House is closed.
2. Copy the whole project folder as a backup.
3. Read `Library/CompiledScripts/Types/APJS.d.ts` for any API you touch.
4. Find an existing example of the exact structure, in this project or in a `Backup/` snapshot, before writing new YAML or JSON.
5. Keep asset guids and entity guids straight.
6. Every new asset needs its `.extra`.
7. Open the project in the editor and verify before claiming it works.
