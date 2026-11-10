# Site Blueprint — `content/site.txt`

Everything that lives at the **site level**: theme colors, navigation, typography, tags, global custom code. The blueprint file is `magpie-core/blueprints/site.yml` (do NOT edit it). The user's content lives in `content/site.txt`, which you edit.

Site-level fields are written like page fields: `Field-Name: value` blocks separated by `----`. Multi-word fields use kebab-case with the first letter capitalized (`Background-color`, `Custom-fonts`, `Site-logo`).

---

## Site Tabs Overview

| Tab | Purpose |
|---|---|
| **Pages** | Page management (read-only here — you create/edit pages via filesystem) |
| **Tags** | Categories used by `projects` block + project pages |
| **Theme** | Colors, page-layout defaults, global background (image/video/p5.js) |
| **Navigation** | Menu items, logo, dropdown, burger, off-canvas, hover-index |
| **Typography** | Custom fonts, global sizes, typography overrides per element |
| **Code** | Global Custom CSS / JS / PHP |

---

## Theme Tab (`Background-color`, `Text-color`, `Accent-color`, ...)

### Core colors (always present)
- `Background-color` (color) — page bg
- `Text-color` (color) — body text
- `Accent-color` (color) — buttons, links, highlights

### Page-Layout defaults (apply when page has no override)
- `Default-content-width-mode` (`dynamic`/`max-width`)
- `Default-content-width` (10-100%)
- `Default-max-content-width` (300-2000 px)
- `Default-content-alignment` (left/center/right)
- `Default-main-top-spacing` / `Default-main-bottom-spacing` (text)

### Global background (image / video / p5.js)
- `Enable-background` (toggle)
- `Background-image` (file ref)
- `Bg-image-style` (`fixed-cover`/`fixed-contain`/`repeat-y`/`repeat`/`contain`/`cover`)
- `Bg-image-blur` (0-20px)
- `Background-video` (file ref)
- `Bg-video-muted`, `Bg-video-loop`, `Bg-video-landing-only` (toggles)
- `Enable-p5-background` (toggle)
- `P5-sketch-code` (textarea, monospace) — actual p5.js code
- `P5-landing-only` (toggle)

### Direct-edit example (change accent color)
```
Accent-color: #ff6b35
```

---

## Navigation Tab

### Logo / Site Name
- `Site-logo` (file ref to image)
- `Logo-size` (default `"40px"`)
- `Hide-site-name` (toggle) — when logo + name both visible

### Bar / Layout
- `Nav-height` (default `"70px"`)
- `Sticky-navigation` (toggle)
- `Nav-background-color`, `Nav-blur-amount`
- `Nav-border-enabled` + `Nav-border-color` + `Nav-border-thickness`
- `Nav-shadow-enabled` etc.

### Menu Items (`Menu-items`)
Structure-field. Each item:
- `link_type` (`page`/`url`/`email`/`anchor`)
- `link_page` (when page)
- `link_url` (when url)
- `link_email` (when email)
- `anchor_page` + `link_anchor` (when anchor — e.g. `#about-text`, optionally on another page)
- `title` (override display title)
- `new_tab` (toggle)

### Dropdown / Submenus
- `Dropdown-enabled` (toggle) — show children on hover
- `Dropdown-background-style` (`solid_bg`/`transparent`)
- `Dropdown-divided-by-lines` (toggle)

### Burger Menu (mobile or always)
- `Burger-menu-behavior` (`mobile`/`always`/`never`)
- `Off-canvas-menu-style` (`left`/`right`/`below`/`fullscreen`)
- `Off-canvas-text-align`, `Off-canvas-menu-gap`, `Off-canvas-background-color`, `Off-canvas-background-blur`
- Shadow: `Off-canvas-shadow-enabled` + color/blur/spread
- Width per style: `Off-canvas-menu-width` (left), `Off-canvas-menu-width-right`, `Off-canvas-menu-height` (below)

### Hover Index List (rich hover preview of child projects on nav link)
- `Hover-index-enabled` (toggle)
- `Hover-index-disable-nav-link` (when enabled, makes parent link unclickable)
- `Hover-index-animation-direction` (left/right)
- `Hover-index-show-year` / `Hover-index-show-category` (toggles)
- `Hover-index-max-items` (number)
- `Category-mode` (`button`/`comma`) — display mode for project categories in hover list

### Cursor
- `Cursor-enabled` (toggle) — enables custom-cursor.js

---

## Typography Tab

### Custom fonts (`Custom-fonts` structure)
Each font:
- `font_name` (e.g. `"Nimbus Sans"`)
- `font_weights` (sub-structure): per weight:
  - `weight` (100-900)
  - `style` (`normal`/`italic`)
  - `font_files` (file refs, accepts woff2/woff/ttf/otf)

### Global Sizes
- `Font-size-large` / `Font-size-medium` / `Font-size-small` / `Font-size-tiny` (px)
- `Line-height-large` / `_medium` / `_small` / `_tiny`
- `Letter-spacing-large` / `_medium` / `_small` / `_tiny`

### Typography Overrides (`Typography-overrides` structure)
Per element override (up to 30 entries). Each:
- `element_name` (`h1`, `h2`, `.project-title`, `.site-header__title`, etc.)
- `custom_selector` (any CSS selector)
- `font_family_override` (picks from `custom_fonts`)
- `font_size_override` (px)
- `color_override`
- `font_weight_override` (100-900)
- `text_transform_override` (none/uppercase/lowercase/capitalize)
- `font_style_italic` (toggle)
- `letter_spacing_override` (px)

These render into a dedicated CSS block via `advanced-typography-css.php` (theme handles it — you just set fields).

---

## Tags Tab

`Categories` (structure) — used by `project` pages' `category` field and by `projects` block's filter:
Per category:
- `category` (text — display name)
- + styling/option fields per project (varies)

**Order matters** — the structure order determines filter-button order on portfolio pages.

---

## Code Tab (most important for creative escalation)

### Global CSS
```
Custom-css:

/* === Comment header explaining what + when added === */
.your-class {
  /* … */
}

----

Css-toggle: true
```
- `Custom-css` (textarea, monospace)
- `Css-toggle` (toggle) — must be `true` to render
- **Rendered**: in `<style id="custom-css">` in `<head>`, after theme CSS. Highest specificity.

### Global JS
```
Custom-js:

(function () {
  'use strict';
  // … your code
})();

----

Js-toggle: true
```
- `Custom-js` (textarea, monospace)
- `Js-toggle` (toggle)
- **Rendered**: in `<script id="custom-js">` before `</body>` (footer.php).

### Global PHP (rare)
- `Custom-php` (textarea, monospace) — actual PHP that gets `eval`'d
- `Php-toggle` (toggle)
- **Rendered**: eval'd in header.php's dropdown-navigation logic. Currently the only documented use: defining a `$modifyChildUrl` callable to rewrite dropdown URLs (e.g. for redirects, slug rewrites). Use with care — this is a real `eval()`.

Example (`Custom-php` content):
```php
<?php
// Modify URLs of dropdown items under "Projects":
// Append a query parameter for tracking.
$modifyChildUrl = function ($child, $menuPage) {
  if ($menuPage->slug() === 'projects') {
    return $child->url() . '?from=nav';
  }
  return $child->url();
};
```

---

## Footer
- `Footer-custom-text` (textarea/text) — right-aligned text in footer

---

## Real example from a Studio Partyka site.txt (illustrative)

```
Title: Studio Partyka

----

Background-color: #f4efe7

----

Text-color: #303030

----

Accent-color: #7A8761

----

Site-logo: 

----

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

----

Custom-fonts: 
-
  font_name: "Suisse Intl"
  font_weights:
    -
      weight: "400"
      style: normal
      font_files:
        - file://suisseintl-regular-woff2

----

Custom-css:

/* Editorial typography overrides */
.display-xl { font-size: clamp(48px, 8vw, 96px); }
.eyebrow { text-transform: uppercase; letter-spacing: 0.1em; }

----

Css-toggle: true
```

---

## Hybrid-Write Decisions for site.txt

| Task | Channel |
|---|---|
| Change a theme color | Direct `.txt` edit (one field) |
| Toggle css/js/php | Direct `.txt` edit |
| Add CSS rules to existing `Custom-css` | Direct `.txt` edit (append to textarea content) |
| Add a menu item | Direct `.txt` edit (append to `Menu-items` structure) |
| Add a custom font (with files) | Hybrid: `upload-asset` to upload files into `site.find('media-library')`, then direct edit to add to `Custom-fonts` structure |
| Add many categories | Direct `.txt` edit (structure list) |
| Rebuild the navigation from scratch | Direct edit (replace `Menu-items` block content) |

There is **no `update-site` CLI command** — site.txt edits are always direct. Be careful with structure fields (YAML list under a field) — wrong indentation breaks parsing.

---

## Site-File Indentation Pitfall

Structure fields use YAML inside the `----`-delimited block. Indentation:
```
Menu-items: 
- 
  link_type: page
  link_page: 
    - page://0YFjXXizqWY5FBQR
  title: Work
- 
  link_type: url
  link_url: https://example.com
  title: External
```
- First `- ` has a single space after.
- Sub-fields indent **2 spaces** (NOT 4).
- Nested arrays (like `link_page`) indent **4 spaces** under the field name + `- ` for items.
- Empty values: trailing space after colon or just nothing.

If unsure, open `content/site.txt` and copy the existing pattern.
