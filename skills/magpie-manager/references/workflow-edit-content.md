# Workflow — Edit Page Content

Day-to-day content editing on existing pages. The bread and butter.

---

## Decision tree — Direct edit vs CLI

```
What's the edit?
├─ Single text/field change inside a block ───────────→ Direct .txt edit
├─ Toggle a flag (css_toggle, builder_active, etc.) ──→ Direct .txt edit
├─ Change a top-level page field (Seo-*, etc.) ───────→ Direct .txt edit
├─ Add a new block to existing column ────────────────→ CLI: get-builder + modify + update-builder
├─ Add a new section ─────────────────────────────────→ CLI: append-section
├─ Reorder sections within a page ────────────────────→ CLI: get-builder + reorder array + update-builder
├─ Delete a block from existing column ───────────────→ Direct edit (with backup) OR CLI rebuild
├─ Delete an entire section ──────────────────────────→ CLI: get-builder + remove from array + update-builder
└─ Major restructure (>3 changes) ────────────────────→ CLI: update-builder with full new content
```

---

## Pattern: Change text inside an existing block

1. Read the page's `.txt`. The `Builder-content` line is one big JSON.
2. Find the unique text snippet you want to change.
3. Use Edit tool with enough surrounding JSON to make the match unique.

Example — change a text block's content:

```
old_string: '"text":"# Retail & Product Design","text_align":"left"'
new_string: '"text":"# Retail Design","text_align":"left"'
```

If the same text appears multiple times, include the block's `id` for uniqueness:
```
old_string: '"text":"# Title","text_align":"left","text_width":100,"horizontal_shift":0,"text_size_override":"","custom_text_size":"","text_color":null,"top_spacing":"0px","bottom_spacing":"0px","custom_class":"display-xl","custom_id":""},"id":"568c8aef-91ee-448d-a84e-7ad5ac2a4495"'
```

---

## Pattern: Toggle a flag

```
old_string: "Page-css-toggle: false"
new_string: "Page-css-toggle: true"
```
If multiple toggles share the same value, include the preceding field for context:
```
old_string: "Page-custom-js:\n\n// js code\n\n----\n\nPage-js-toggle: false"
new_string: "Page-custom-js:\n\n// js code\n\n----\n\nPage-js-toggle: true"
```

---

## Pattern: Update a top-level page field

For empty fields, the `.txt` has `Field-Name: ` (with trailing space) then `----`:

```
old_string: "Seo-title: \n\n----"
new_string: "Seo-title: My Custom Title for Search\n\n----"
```

For non-empty fields, just match the existing value:
```
old_string: "Content-width: 100"
new_string: "Content-width: 80"
```

---

## Pattern: Add a new section

1. Construct section JSON, save to `.tmp/section.json`
2. Validate:
   ```bash
   $PHP $CLI validate --section=@.tmp/section.json
   ```
3. Append:
   ```bash
   $PHP $CLI append-section --page=home --section=@.tmp/section.json
   ```

The new section goes at the end. If you need it in the middle, do a get-builder + reorder + update-builder instead.

---

## Pattern: Add a block to an existing column

There's no `append-block` CLI command. Two approaches:

### A — CLI rebuild (safe)
```bash
# 1. Backup
$PHP $CLI get-builder --page=home > .tmp/home-backup.json

# 2. Manipulate (Python example — adjust paths)
python -c "
import json
data = json.load(open('.tmp/home-backup.json'))
sections = json.loads(data['raw'])
new_block = {
    'type': 'text',
    'content': { 'text': 'New paragraph', 'text_align': 'left' },
    'isHidden': False
}
# Append to section 2's first column
sections[1]['columns'][0]['blocks'].append(new_block)
open('.tmp/modified.json', 'w').write(json.dumps(sections))
"

# 3. Update
$PHP $CLI update-builder --page=home --content=@.tmp/modified.json
```

### B — Direct edit (surgical, riskier)
Find the closing `]` of the target column's `blocks` array. Insert the new block JSON before that `]`. Use Edit tool with unique surrounding context.

```
old_string: '...end of last block JSON in column...},"id":"<column-uuid>","width":"1/1"'
new_string: '...end of last block JSON in column...,{"content":{"text":"New para"},"type":"text","isHidden":false}],"id":"<column-uuid>","width":"1/1"'
```

(Note: ensure you correctly include the closing `]` of the array — exact diff depends on the existing JSON.)

Use A for >1 change, B for trivial single-block additions.

---

## Pattern: Reorder blocks within a column

CLI rebuild approach. Direct-edit reordering inside a long JSON string is too error-prone.

```bash
$PHP $CLI get-builder --page=home > .tmp/home-backup.json
python -c "
import json
data = json.load(open('.tmp/home-backup.json'))
sections = json.loads(data['raw'])
# Reorder section 0's first column's blocks: swap [0] and [2]
blocks = sections[0]['columns'][0]['blocks']
blocks[0], blocks[2] = blocks[2], blocks[0]
sections[0]['columns'][0]['blocks'] = blocks
open('.tmp/modified.json', 'w').write(json.dumps(sections))
"
$PHP $CLI update-builder --page=home --content=@.tmp/modified.json
```

---

## Pattern: Delete a block

### Safest: CLI rebuild
```bash
$PHP $CLI get-builder --page=home > .tmp/home-backup.json
python -c "
import json
data = json.load(open('.tmp/home-backup.json'))
sections = json.loads(data['raw'])
# Remove block with id 'xxxx-...' from section 1, column 0
sections[1]['columns'][0]['blocks'] = [
    b for b in sections[1]['columns'][0]['blocks'] if b.get('id') != 'xxxx-uuid-here'
]
open('.tmp/modified.json', 'w').write(json.dumps(sections))
"
$PHP $CLI update-builder --page=home --content=@.tmp/modified.json
```

### Direct edit (if you can find a clean cut)
Find the block JSON `{...},` (with the trailing comma if it's not the last block, or the leading comma if it IS the last block) and remove that exact chunk. Validate by previewing immediately.

---

## Pattern: Inputs from Figma / Screenshot / Reference URL

When the user has visual input:

### Figma URL
- If you have Figma MCP available: `get_design_context` on the node-id
- Otherwise ask user for component-by-component description
- Map each Figma node to a block (consult `use-case-mapping.md`)
- Match tokens via `list-tokens` before using custom colors

### Screenshot
- Read with the Read tool (the image will be presented visually)
- Dissect: enumerate visible sections top-to-bottom
- For each section: identify blocks, then translate to JSON

### Reference URL
- WebFetch the URL or have user share screenshot
- Same dissection approach

In all three cases: produce a **section list** first (the concept), confirm with user if anything's unclear, then build.

---

## Pattern: Page-Settings change (Layout, Background, SEO)

These are all top-level page fields, edited directly. Use the Edit tool.

Examples:
- Change page background color: edit `Page-background-color:` (after `Custom-background-enabled: true`)
- Set SEO meta: edit `Seo-title:`, `Seo-description:`
- Hide navigation: edit `Hide-navigation: true`
- Set content alignment: edit `Content-alignment:`

Always check field names in `page-blueprints.md` for the right capitalization/spelling.

---

## Pattern: Custom CSS / JS for one page

Direct-edit the page's `.txt`:

1. Find the `Page-custom-css:` field, add your CSS (with comments!):
   ```
   Page-custom-css:

   /* ============================================
      Section-specific styling — added 2026-05-19
      ============================================ */
   .my-section h2 {
     font-size: clamp(32px, 5vw, 64px);
   }

   ----
   ```

2. Set the toggle:
   ```
   Page-css-toggle: false  →  Page-css-toggle: true
   ```

3. Same for `Page-custom-js:` / `Page-js-toggle:`.

---

## Backup discipline

**Always before:**
- `update-builder` (full replace)
- Mass delete (>3 blocks)
- Restructuring sections
- Any operation involving `--content=@<file>` where the file is large

```bash
$PHP $CLI get-builder --page=<id> > .tmp/<id>-backup-$(date +%Y%m%d-%H%M%S).json
```

If something breaks during preview verification, restore:
```bash
python -c "import json; d=json.load(open('.tmp/<id>-backup-...json')); open('.tmp/rb.json','w').write(d['raw'])"
$PHP $CLI update-builder --page=<id> --content=@.tmp/rb.json
```

---

## What you SHOULD NOT do

- ❌ Edit `Builder-content` JSON by re-writing the whole line in a single Edit — too error-prone. Use CLI for full replaces.
- ❌ Edit `.txt` files in `magpie-core/`, `kirby/`, `site/` — those aren't content files.
- ❌ Add a block-type that's not in `block-catalog.md` (or `list-blocks`). CLI will reject it.
- ❌ Forget the trailing `----` after the last field — it's not strictly required but keeps the file valid.
