# `builder-cli.php` — Full Reference

The validating write channel to Magpie content. Bootstraps Kirby, exposes JSON-in/JSON-out commands. Use for **structural** operations (new section, new page, full builder replace, asset upload, validation). For surgical edits, prefer direct `.txt` edits.

Path: `magpie-core/bin/builder-cli.php`

PHP binary varies per machine. Common locations:
- MAMP Windows: `C:/MAMP/bin/php/php8.3.1/php.exe`
- MAMP macOS: `/Applications/MAMP/bin/php/php8.3.1/bin/php`
- System: `php` (if 8.2+)

Set once per session:
```bash
PHP="C:/MAMP/bin/php/php8.3.1/php.exe"
CLI="magpie-core/bin/builder-cli.php"
```

All commands:
- Print JSON to stdout on success
- Print JSON error to stderr + exit 1 on failure
- Auto-impersonate the Kirby user (no auth needed for CLI)

---

## Value resolver

Flags that take JSON (`--section`, `--content`) accept three input forms:
- `--section='<inline json string>'`
- `--section=@path/to/file.json` (read from file)
- `--section=-` (read from stdin)

---

## Read Commands

### `list-blocks`
List all block types registered in the page-builder.
```bash
$PHP $CLI list-blocks
```
Output:
```json
{
  "blocks": [
    { "type": "text", "blueprint": "...", "name": "Text", "icon": "text", "preview": false, "fieldKeys": ["text", "text_align", ...] },
    ...
  ],
  "count": 22
}
```
**Don't call this routinely** — knowledge base already has the catalog. Use only for sanity check or to detect project-specific blocks.

### `get-schema <type>`
Full blueprint for one block type.
```bash
$PHP $CLI get-schema gallery
$PHP $CLI get-schema text
```
Returns the full YAML-parsed blueprint as JSON. Same caveat as `list-blocks` — usually unneeded.

### `get-section-schema`
Section attrs schema (layouts + settings).
```bash
$PHP $CLI get-section-schema
```
Returns:
```json
{
  "layouts": ["1/1", "1/2, 1/2", "1/3, 1/3, 1/3", ...],
  "settings": { "section_bg_type": { ... }, ... }
}
```

### `list-tokens`
Project-specific theme tokens.
```bash
$PHP $CLI list-tokens
```
Returns:
```json
{
  "spacing_tokens": { "none": 0, "xs": 16, "sm": 32, "md": 64, "lg": 96, "xl": 128, "2xl": 192 },
  "gap_tokens":     { "none": 0, "sm": 16, "md": 32, "lg": 48, "xl": 64 },
  "site_tokens":    { "background_color": "#f4efe7", "text_color": "#303030", "accent_color": "#7A8761", ... }
}
```
Call this **once per session** to verify the project's spacing/gap scale and current theme colors.

### `list-pages`
All pages in the site tree.
```bash
$PHP $CLI list-pages
```
Returns:
```json
{
  "pages": [
    { "id": "home", "title": "Home", "template": "default", "status": "listed", "depth": 1, "has_builder": true, "builder_active": true },
    { "id": "home/stadt-laden", "title": "Stadt Laden", "template": "project", ... },
    { "id": "legal-notice-privacy", "title": "Legal Notice & Privacy", "template": "legal", ... },
    ...
  ],
  "count": 5
}
```

### `get-builder --page=<id>`
Current builder content of a page. Use for **backup before destructive op**.
```bash
$PHP $CLI get-builder --page=home > .tmp/home-backup.json
```
Returns:
```json
{
  "page": "home",
  "builder_active": true,
  "sections": [ ... structured (parsed) ... ],
  "raw": "[{...}]"     // verbatim JSON string, ideal for restoration
}
```
- `sections` is the parsed object form (good for in-memory manipulation)
- `raw` is the exact string stored in `.txt` (good for restoration: pass back to `update-builder`)

---

## Write Commands

### `create-page`
Create a new page (folder + `.txt`).
```bash
$PHP $CLI create-page --slug=about --title="About" --template=default
$PHP $CLI create-page --slug=q4-launch --title="Q4 Launch" --parent=home --template=project
```
- `--slug` (required) — kebab-case URL slug
- `--title` (required) — display title
- `--parent` (optional) — page id of parent; omit for root-level page
- `--template` (default `default`) — must be one of the existing page templates (`default`, `project`, `legal`, `media-library`, `error`)

Creates page in **draft (unlisted)** status. To list/publish, edit the folder name to add a prefix (`3_about/`), or set via panel.

Returns:
```json
{ "id": "about", "slug": "about", "template": "default", "status": "unlisted", "path": "..." }
```

### `append-section --page=<id> --section=<json>`
Append a new section to a page's `builder_content`. Validates JSON shape and auto-generates UUIDs for section/columns/blocks.
```bash
$PHP $CLI append-section --page=home --section=@.tmp/section.json
```
The CLI:
- Adds UUIDs where missing (`id` on section, columns, blocks)
- Defaults `isHidden: false` on blocks
- Defaults `content: {}` if missing
- Defaults `attrs: {}` if missing
- **Validates** `columns` is an array and each block has a `type`
- Errors on unknown block types

Returns:
```json
{ "page": "home", "appended_section": "<new-uuid>", "total_sections": 5 }
```

### `update-builder --page=<id> --content=<json>`
**Complete replacement** of `builder_content`. Use for restoration or bulk rewrite.
```bash
$PHP $CLI update-builder --page=home --content=@.tmp/full.json
```
- Decodes JSON, fails fast on parse errors
- Writes the entire array back to the page

Returns:
```json
{ "page": "home", "sections": 7, "status": "updated" }
```

### `upload-asset --page=<id> --file=<path>`
Upload a file to a page's directory (typically media-library).
```bash
$PHP $CLI upload-asset --page=media-library --file=.tmp/hero.jpg
```
Returns:
```json
{
  "page": "media-library",
  "filename": "hero.jpg",
  "uuid": "file://abc123uuid",
  "url": "/media/pages/media-library/.../hero.jpg",
  "path": "/full/server/path/hero.jpg"
}
```
Use the returned `uuid` in subsequent block-content fields (e.g. `"image": ["file://abc123uuid"]`).

**Template handling:** The CLI uploads with `template: image`. For non-image uploads (audio, video, fonts, documents), the panel's drag-and-drop works better. Or upload, then edit the resulting `.txt` of the file in `media-library/<filename>.<ext>.txt` to set the correct template.

### `validate --section=<json>` or `--content=<json>`
Dry-run validation without writing.
```bash
$PHP $CLI validate --section=@.tmp/section.json
$PHP $CLI validate --content=@.tmp/full.json
```
Returns:
```json
{ "valid": true, "issues": [], "count": 1 }
```
Or with errors:
```json
{ "valid": false, "issues": [
  "Section #0 column #0 block #2: unknown type 'pricing-table'",
  "Section #1: missing 'columns'"
], "count": 2 }
```
**Always run validate** before append/update on non-trivial JSON.

---

## Backup & Rollback Pattern

```bash
# 1. Backup
$PHP $CLI get-builder --page=home > .tmp/home-backup.json

# 2. Do destructive op (update-builder, etc.)
$PHP $CLI update-builder --page=home --content=@.tmp/new-content.json

# 3. If broken: rollback using the 'raw' field from backup
# (use jq or python or PowerShell to extract 'raw' from backup)

# bash + python:
python -c "import json; d=json.load(open('.tmp/home-backup.json')); open('.tmp/rb.json','w').write(d['raw'])"
$PHP $CLI update-builder --page=home --content=@.tmp/rb.json

# powershell:
$d = Get-Content .tmp\home-backup.json -Raw | ConvertFrom-Json
Set-Content -Path .tmp\rb.json -Value $d.raw -Encoding utf8
& "C:\MAMP\bin\php\php8.3.1\php.exe" magpie-core/bin/builder-cli.php update-builder --page=home --content=@.tmp/rb.json
```

---

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `Page not found: <id>` | Wrong page id | `list-pages` to verify ids |
| `Section must include a 'columns' array` | Section JSON without `columns` | Add `"columns": [ ... ]` |
| `Block missing 'type' field` | Block without `type` | Add `"type": "text"` etc. |
| `File not found: <path>` | `@file` path doesn't exist | Use absolute path or path relative to PWD |
| `Invalid JSON for ...` | JSON syntax error | Validate with `python -m json.tool` first |
| `Blueprint not found for block type` | Unknown/typo block type | `list-blocks` to see actual types |
| `Could not locate project root` | CLI run from wrong dir | Run from project root (where `index.php` is) |

---

## Minimal Section JSON

```json
{
  "attrs": {
    "section_width": "contained",
    "section_padding_top": "md",
    "section_padding_bottom": "md"
  },
  "columns": [
    {
      "width": "1/1",
      "blocks": [
        { "type": "text", "content": { "text": "Hello", "text_align": "left" } }
      ]
    }
  ]
}
```

UUIDs auto-generated. `isHidden` defaults `false`. `content` defaults `{}`. `attrs` defaults `{}`.

---

## What the CLI does NOT do

- **No site.txt editing** — there's no `update-site` command. Site fields must be direct-edited.
- **No `modular_content` editing** — only `builder_content`. If page has `builder_active: false`, the CLI's commands won't affect the rendered output (you'd be editing the un-rendered branch). Either set `builder_active: true` first (direct edit) or edit `modular_content` directly.
- **No page deletion** — must be done via filesystem or panel.
- **No file deletion** — same.
- **No multi-language awareness** — assumes single language.
- **No publish-status changes** — must be done via filesystem (rename folder to add prefix) or panel.
