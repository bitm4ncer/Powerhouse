# Page Blueprints — `default`, `project`, `legal`, `media-library`, `error`

What fields each page type exposes in the panel — and therefore what fields you can edit in the corresponding `.txt` files.

---

## `default` — General Page

Blueprint: `magpie-core/blueprints/pages/default.yml`
Filename: `default.txt`

### Tabs

#### `content` — Content Blocks (when Builder is OFF)
- `modular_content` — extends `mixins/content-blocks` (a sequential list of blocks, no sections)

#### `builder` — Page Builder (when ON)
- `builder_active` (toggle, default `false`)
  - `false` → renders `modular_content`
  - `true` → renders `builder_content`
- `builder_content` (JSON array of sections — see `block-catalog.md` → "Section Attributes")

#### `projects` — child Projects list (used for home/parent pages)
- `projects_list` — automatic from child pages with template `project`
- `project_header_settings` — these fields apply to the **child project pages** (header layout in those projects):
  - `project_header_elements` (structure: pick which to show — `title`, `year`, `categories`, `featured_image`, `custom_links`, with optional `size`)
  - `project_header_layout` (`vertical`/`horizontal`/`justified`/`two-column`)
  - `project_header_gap` (0-100px, default 10)
  - `project_header_top_spacing`, `project_header_bottom_spacing` (text)
  - `project_featured_image_width` (10-100%)
  - `project_header_column_width` (when two-column, 20-50%)
  - `project_description_width` (20-100%)

#### `styling` — Page Layout & Background
- **Page Layout:**
  - `content_width_mode` (`dynamic`/`max-width`)
  - `content_width` (10-100%, dynamic only)
  - `max_content_width` (300-2000px, max-width only)
  - `content_alignment` (left/center/right)
  - `center_vertically` (toggle)
  - `main_top_spacing`, `main_bottom_spacing` (text, default `"50px"`)
- **Custom Background** (when `custom_background_enabled: true`):
  - `show_page_title` (toggle, default false)
  - `hide_navigation` (toggle — hides nav + footer)
  - **Colors:** `page_background_color`, `page_text_color`, `page_accent_color`
  - **Image:** `page_background_image` (file), `page_bg_image_style`, `page_bg_image_blur` (0-20px)
  - **Video:** `page_background_video`, `page_bg_video_muted`, `page_bg_video_loop`
  - **p5.js:** `enable_page_p5_background`, `page_p5_sketch_code` (textarea)

#### `seo`
- `seo_title` (max 60)
- `seo_description` (max 160)
- `seo_image` (file)
- `seo_hide` (toggle — noindex)

#### `code` — page-specific Custom Code
- `page_custom_css` (textarea, monospace)
- `page_css_toggle` (toggle, default false) — **must** be true to render
- `page_custom_js` (textarea, monospace)
- `page_js_toggle` (toggle, default false) — **must** be true to render

**Rendering (handled by theme, do not touch):**
- `page_custom_css` → `<style id="page-custom-css">` in `<head>` AFTER global `custom_css` (page CSS overrides site CSS via cascade)
- `page_custom_js` → `<script id="page-custom-js">` before `</body>` AFTER global `custom_js`
- Both require the toggle to be `true`

---

## `project` — Portfolio Project Page

Blueprint: `magpie-core/blueprints/pages/project.yml`
Filename: `project.txt`

`project` is `default` + project-specific metadata + project-layout overrides. Most fields identical; below are the **differences/additions**.

### Tabs

#### `content`
Two-column panel:
- **Main column:**
  - `description` (textarea, small, with marks + nodes for formatting)
  - `modular_content` (same as default)
- **Sidebar:**
  - `featured_image` (single file, uploads to media-library)
  - `year` (text — supports any format: `"2024"`, `"March 2024"`, `"2024-03-15"`)
  - `category` (tags — multi-tag, options come from `site.categories` structure; defines portfolio filter buttons via site Tags tab)
  - `excerpt` (max 300 chars, used in gallery previews instead of `description`)
  - `custom_links` (structure):
    - Per link: `link_title`, `link_icon` (SVG file), `link_icon_size` (default `"20px"`), `link_url`, `link_file` (uploads to media-library)
    - Links open in new tab; files trigger download
  - `no_lead` (toggle) — when true, project only appears in portfolio feed without a clickable detail page (returns 404, noindex)

#### `builder`
Same as default.

#### `styling` — Project Layout
- `override_project_layout` (toggle) — when false, uses globals from Site → Theme; when true, project gets own layout
- When override is on:
  - Same fields as default's styling tab + `text_alignment` and `full-width` content-width mode
  - Plus the `custom_background` section (identical to default)

#### `seo`, `code`
Identical to default.

### Options
```yaml
options:
  changeSlug: true
  changeStatus: true
  changeTemplate: false   # cannot switch a project to another template
```

---

## `legal` — Legal Notice & Privacy Page

Blueprint: `magpie-core/blueprints/pages/legal.yml`
Filename: `legal.txt`

**Protected page** — `options: { delete: false, status: false, template: false }`. Cannot be deleted or template-changed from the panel.

### Tabs

#### `content` — Legal Info
- `legal_name` (required) — full name / company
- `legal_email` (required, email)
- `legal_address` (required, textarea)
- `legal_additional_text` (textarea) — extra legal info
- `legal_hosting_provider_select` (select: hetzner/ionos/allinkl/domainfactory/hostinger/netcup/strato/versatel/mittwald/custom)
- `legal_hosting_provider_custom` (textarea, required when select=custom)
- `legal_additional_privacy_text` (textarea)

#### `custom_content` — Override template
- `use_custom_text` (toggle)
- `custom_text` (huge textarea, Markdown, when use_custom_text=true) — fully replaces the auto-generated legal text

#### `styling`, `seo`
Identical to default.

**Note:** The `seo_hide` field defaults to `true` (hidden from search engines by default — typical for legal pages).

---

## `media-library` — Asset Repository

Blueprint: `magpie-core/blueprints/pages/media-library.yml`
Filename: `media-library/default.txt` (or auto-managed)

**Locked** — cannot be created, deleted, sorted, duplicated, renamed, or have its slug/status/template changed. Cannot be read on the site frontend (`read: { panel: true, site: false }`).

This is the **central file repository** that other pages query (`site.find('media-library').files`).

### Tabs (each tab is a `files` section filtered by extension)

| Tab | Extensions | Pagination |
|---|---|---|
| **Images** | jpg, jpeg, png, webp, gif | 20/page |
| **Icons** | svg | 30/page |
| **Videos** | mp4, webm, ogg, mov, avi | 10/page |
| **Audio** | mp3, wav, ogg, m4a, aac | 20/page |
| **Fonts** | woff, woff2, ttf, otf, eot | 100 total |
| **Documents** | pdf, txt, doc, docx, xls, xlsx, csv, zip, rar | 25/page |

### How to add files
- Via panel: drag-and-drop into the right tab
- Via CLI: `php builder-cli.php upload-asset --page=media-library --file=path/to/file.jpg`
- Then reference the file in other blocks via `file://<uuid>` (CLI returns the uuid after upload)

---

## `error` — 404 Page

Blueprint: `magpie-core/blueprints/pages/error.yml`
Filename: `error/error.txt`

**Locked** — listed=false (hidden from page tree), delete=false, status/template/changeSlug/duplicate all false.

Has **no editable content fields** — it's purely managed by `error.php` template. Don't try to edit it.

---

## Common Field Type Reference

When reading `.txt` files, fields appear like:

```
Field-Name: value
```

with `----` separators. Some types:

| Field-Type | `.txt` representation |
|---|---|
| `text`, `url`, `email`, `tel`, `number` | `Field-Name: value` |
| `textarea` | `Field-Name:\n\nmulti\nline\ntext` |
| `select`, `select`-single | `Field-Name: optionvalue` |
| `multiselect`, `tags` | `Field-Name: option1, option2, option3` |
| `toggle` | `Field-Name: true` or `false` |
| `color` | `Field-Name: #rrggbb` or `#rrggbbaa` |
| `range`, `number` | `Field-Name: 42` |
| `files` (single) | `Field-Name: \n - file://<uuid>` (YAML array even for single) |
| `files` (multiple) | `Field-Name:\n - file://<a>\n - file://<b>` |
| `pages` | `Field-Name:\n - page://<uuid>` |
| `structure` | `Field-Name:\n -\n   sub_field: value\n   other: value\n -\n   ...` (YAML list of objects) |
| `blocks` / `builder_content` | `Field-Name: [{"type":"text",...}]` (JSON array, all on one line) |

When in doubt, open an existing page's `.txt` file and copy the pattern.

---

## Direct-Edit Pattern Cheat-Sheet

### Toggle a flag
```
Page-css-toggle: false
```
→ change to
```
Page-css-toggle: true
```

### Add or change a single field
```
Seo-title: 

----
```
→ becomes
```
Seo-title: My Custom SEO Title

----
```

### Change a block's text inside `Builder-content`
The whole `Builder-content` is one long JSON line. Use Edit tool with a unique snippet around the text. Example: change "Studio" eyebrow:

`old_string`: `"text":"Studio","text_align":"left","text_width":100,"horizontal_shift":0,"text_size_override":"","custom_text_size":"","text_color":null,"top_spacing":"0px","bottom_spacing":"24px","custom_class":"eyebrow"`

`new_string`: `"text":"About","text_align":"left","text_width":100,"horizontal_shift":0,"text_size_override":"","custom_text_size":"","text_color":null,"top_spacing":"0px","bottom_spacing":"24px","custom_class":"eyebrow"`

That's surgical, no JSON re-parsing, no risk to other fields.

### Toggle `Builder-active`
- `false` → `modular_content` is rendered
- `true` → `Builder-content` is rendered

Both fields can coexist in the `.txt`; only one is rendered based on this toggle.
