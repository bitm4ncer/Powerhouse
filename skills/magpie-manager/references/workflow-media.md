# Workflow — Media Library

The central asset repository (`content/media-library/`). All images, icons, videos, audio, fonts, and documents that other blocks reference live here.

---

## Why everything goes in media-library

- **Reusability:** Same image referenced by multiple blocks across pages (no duplication)
- **Stable UUIDs:** Files get a `file://<uuid>` that survives renames
- **Panel UX:** Single place to browse/search assets

Other blocks pick from media-library via their `files`-type fields with `query: site.find('media-library').files...`.

---

## Upload assets

### Via CLI
```bash
$PHP $CLI upload-asset --page=media-library --file=path/to/hero.jpg
```
Returns the file UUID — paste it into block `content` fields as `file://<uuid>`.

The CLI uses template `image` by default. For non-image uploads, the template might be wrong (audio files want `audio` template, videos want `video`). After upload, check/edit the file's accompanying `.txt`:

```
content/media-library/hero.mp4.txt   ← edit if needed
```

Add (or change):
```
Template: video
```

Better: for non-image assets, upload via the Kirby panel — drag into the right tab, gets the right template automatically.

### Via panel
1. Open `/panel`
2. Go to Media Library page
3. Click the appropriate tab (Images / Icons / Videos / Audio / Fonts / Documents)
4. Drag-and-drop files

The panel auto-assigns the correct template.

---

## Reference uploaded files in blocks

After upload, the CLI returns:
```json
{ "uuid": "file://abc123" }
```

Use in block content:
```json
{ "type": "image", "content": { "image": ["file://abc123"], "alt": "Hero shot" } }
```

For galleries:
```json
{ "type": "gallery", "content": {
    "gallery": ["file://abc123", "file://def456", "file://ghi789"],
    "grid_columns": 3
} }
```

For background fields in section attrs:
```json
"attrs": { "section_bg_type": "image", "section_bg_image": ["file://abc123"] }
```

---

## Set alt text / caption on a file

Each uploaded file has its own `.txt` for metadata:
```
content/media-library/hero.jpg.txt
```

Contents (created automatically, may have these fields):
```
Alt: Hero shot of the studio

----

Caption: Studio, autumn 2025

----
```

Edit these via panel (click the file, edit its metadata) or direct edit. Alt text becomes the `alt` attribute on the rendered `<img>` if the block doesn't have its own `alt` field.

---

## Supported file types per tab

| Tab | Extensions | Max file size |
|---|---|---|
| Images | jpg, jpeg, png, webp, gif | (no hard limit in blueprint — server-side limit) |
| Icons | svg | (small) |
| Videos | mp4, webm, ogg, mov, avi | 200 MB (per video block uploads) |
| Audio | mp3, wav, ogg, m4a, aac | 50 MB |
| Fonts | woff, woff2, ttf, otf, eot | (small) |
| Documents | pdf, txt, doc, docx, xls, xlsx, csv, zip, rar | (none) |

---

## Find an existing file's UUID

Two ways:

### Via filesystem
1. Open `content/media-library/`
2. Find the file (e.g. `hero.jpg`)
3. Read `hero.jpg.txt` — somewhere near the top is `Uuid: xn8c3ztssdvlapdf` (Kirby stores UUID inside metadata file)

### Via CLI
There's no direct `list-files` command. Quick PHP one-liner:
```bash
$PHP -r "
require 'kirby/bootstrap.php';
\$kirby = new Kirby(['roots' => ['index' => __DIR__, 'templates' => 'magpie-core/templates', 'snippets' => 'magpie-core/snippets', 'plugins' => 'magpie-core/plugins', 'blueprints' => 'magpie-core/blueprints', 'models' => 'magpie-core/models']]);
foreach (\$kirby->page('media-library')->files() as \$f) {
  echo \$f->filename() . ' -> file://' . \$f->uuid()->id() . PHP_EOL;
}
"
```

Easier: rely on the CLI's `upload-asset` output if you're uploading right now.

---

## Delete files

No CLI command. Options:
- **Panel:** select file, click delete
- **Filesystem:** delete the file + its `.txt` companion. Then run a search to make sure no `file://<uuid>` references remain in any page's content — if they do, those blocks will silently fail to render their image.

Search for stale references:
```bash
grep -r "file://<deleted-uuid>" content/
```

---

## Organize / rename files

- Renaming requires updating all references (UUID stays stable though — rename only changes the URL/filename, not the UUID, so references via `file://uuid` survive)
- For panel-managed renames: panel handles it
- For filesystem renames: rename both `hero.jpg` and `hero.jpg.txt` to the new name

---

## Best practices

1. **Upload to media-library, not to individual pages.** Some block fields allow uploads `parent: site` which puts files at site root — avoid; consolidate in media-library.
2. **Use descriptive filenames** before upload (`hero-stadt-laden.jpg`, not `IMG_4521.jpg`). Helps panel search.
3. **Set alt text for every image** — important for accessibility AND auto-fallback when blocks don't specify their own `alt`.
4. **SVG icons go in the Icons tab** — they get rendered inline by some blocks (button, contact) which need SVG specifically.
5. **Fonts must include all weights/styles used.** Add corresponding entries in `site.txt` → `Custom-fonts:`.

---

## Common mistakes

- ❌ Uploading large videos (>200MB) — will be rejected by Kirby's file size limits
- ❌ Using `file://abc` (with the prefix in the field value where the field already adds `file://`) — double-prefix breaks the reference
- ❌ Embedding image URLs as raw `<img src="/media/...">` in text blocks — won't survive a path change. Use proper `image` block with `file://` reference.
- ❌ Uploading icons with `template: image` — won't appear in icon-specific picker fields. Either upload via panel's Icons tab, or post-edit the file's `.txt` to `Template: image` is correct (icon = image with .svg extension in Magpie).
