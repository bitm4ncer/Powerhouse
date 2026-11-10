# Workflow — Site Settings (`content/site.txt`)

All site-wide settings: theme colors, navigation, typography, tags, global custom code. Always **direct edit** — there's no CLI for site.

Read `site-blueprint.md` for the full field inventory.

---

## General approach

1. Read `content/site.txt` first to see current state and exact field names.
2. Make targeted edits with Edit tool.
3. Preview the site (any page) to verify the change.

---

## Common operations

### Change a theme color
```
old_string: "Accent-color: #7A8761"
new_string: "Accent-color: #ff6b35"
```
Or for empty fields:
```
old_string: "Accent-color: \n\n----"
new_string: "Accent-color: #ff6b35\n\n----"
```

### Add a menu item
Find the `Menu-items:` block, append a new structure item. Watch the YAML indentation (2 spaces for sub-fields).

```
old_string: |
  Menu-items: 
  - 
    link_type: page
    link_page: 
      - page://0YFjXXizqWY5FBQR
    title: Work
    new_tab: false

  ----
new_string: |
  Menu-items: 
  - 
    link_type: page
    link_page: 
      - page://0YFjXXizqWY5FBQR
    title: Work
    new_tab: false
  - 
    link_type: anchor
    link_anchor: "#contact"
    title: Contact
    new_tab: false

  ----
```

For a `link_type: page` entry, you need the page's UUID. If you don't have it, use the page id slug instead: `link_page:\n    - page://about` works for pages in `content/about/` etc.

### Remove a menu item
Find the unique structure item and remove it (including its trailing newline before the next `- ` or before the closing of the block).

### Change navigation appearance
- Logo: `Site-logo: \n - file://<uuid>` (upload logo to Media Library first)
- Logo size: `Logo-size: "60px"`
- Nav background: `Nav-background-color: rgba(255,255,255,0.95)`
- Sticky on/off: `Sticky-navigation: true|false`
- Burger menu: `Burger-menu-behavior: mobile|always|never`

### Change Typography
- Override a single element: edit `Typography-overrides:` structure, add an entry for the element
- Add a new font: see "Add a custom font" below

### Add a custom font
1. Upload font files via CLI to media-library:
   ```bash
   $PHP $CLI upload-asset --page=media-library --file=path/to/MyFont-Regular.woff2
   $PHP $CLI upload-asset --page=media-library --file=path/to/MyFont-Bold.woff2
   ```
   Save the returned uuids.

2. Direct edit `site.txt` → `Custom-fonts:`:
   ```
   Custom-fonts: 
   - 
     font_name: My Font
     font_weights:
       - 
         weight: "400"
         style: normal
         font_files:
           - file://<uuid-of-regular>
       - 
         weight: "700"
         style: normal
         font_files:
           - file://<uuid-of-bold>
   ```

3. To make this the default body font, add a Typography-Override or update existing ones to reference `My Font` in `font_family_override`.

### Add a category (tag)
Edit `Categories:` structure in site.txt. Each category has its own styling fields (varies per project). Read existing entries for the pattern.

### Add global custom CSS
1. Find `Custom-css:` field
2. Append CSS (with comment):
   ```
   Custom-css:

   /* Existing styles… */
   .existing { … }

   /* ============================================
      Added 2026-05-19 — bigger H1 on landing
      ============================================ */
   body.is-home h1 {
     font-size: clamp(64px, 10vw, 120px);
   }

   ----
   ```
3. Make sure `Css-toggle: true` (or change it from `false`).

### Add global custom JS
Same pattern with `Custom-js:` + `Js-toggle: true`. Always wrap in IIFE:
```javascript
(function () {
  'use strict';
  // your code
})();
```

### Global background
- Image: upload to media-library → `Background-image: \n - file://<uuid>` → set `Bg-image-style: cover` → set `Enable-background: true`
- Video: `Background-video: \n - file://<uuid>` → set `Bg-video-muted: true` → set `Bg-video-loop: true`
- p5.js: paste sketch code into `P5-sketch-code:` textarea → set `Enable-p5-background: true`

---

## Indentation pitfalls in structure fields

YAML structures are line-indentation sensitive. Common errors:

- ❌ Item separator with 2 spaces instead of 0: `  - ` — breaks parsing
- ❌ Sub-field with 4 spaces instead of 2: parser thinks it's a nested array
- ❌ Tabs anywhere — only spaces in YAML
- ❌ Trailing space after `- ` followed by sub-field on next line — sometimes parses, sometimes not (be safe: no trailing space)

When unsure: copy an existing structure entry verbatim, then modify just the values.

---

## Verifying site.txt changes

1. Reload any page in preview
2. Check console for parse errors (Kirby's "Could not parse" usually shows in PHP errors / page 500)
3. If page 500s, you broke the YAML in site.txt — restore via git

```bash
git diff content/site.txt    # before applying changes — inspect
git checkout content/site.txt  # restore if broken
```

---

## What you SHOULD NOT do at site level

- ❌ Edit `magpie-core/blueprints/site.yml` (theme blueprint)
- ❌ Override theme behavior in PHP via `custom_php` unless absolutely needed (it's `eval`'d — security risk)
- ❌ Add a category by editing project pages' `category` fields without also updating `Categories:` structure — orphaned tags don't filter properly
