# Block Catalog — Knowledge Base (22 Blocks)

The canonical inline reference for every Magpie content block. **Do not** call `list-blocks` or `get-schema` — read this file instead. Use `php builder-cli.php list-blocks` only as a sanity check if a block seems missing (e.g. a project ships custom blocks).

Each entry lists:
- **Purpose** — what the block is semantically for
- **Use when** — typical briefing language that maps here
- **Use NOT for** — common mistakes
- **Fields** — every panel field with type and default
- **Minimal JSON** — copy-paste skeleton
- **Notes / gotchas**

Universal field group (almost every block has these):
- `top_spacing`, `bottom_spacing` — CSS length (e.g. `"20px"`, `"4rem"`, `"5vh"`), default `"20px"`
- `custom_class` — adds a class to the block wrapper
- `custom_id` — adds an id (anchor link target)
- `horizontal_shift` (range `-1` … `1`) — -1 left, 0 center, 1 right (block-level offset)

---

## Section Attributes (wraps blocks in a layout)

A Magpie page's `Builder-content` is an array of **sections**. Each section has `attrs`, `columns`, and `id`. Columns hold blocks.

### Section `attrs`

| Field | Type | Default | Values |
|---|---|---|---|
| `section_bg_type` | select | `"none"` | `none`, `color`, `image`, `gradient` |
| `section_bg_color` | color | `""` | hex with optional alpha (#rrggbbaa) |
| `section_bg_image` | files | `[]` | `["file://<uuid>"]` |
| `section_bg_image_style` | select | `"cover"` | `cover`, `contain`, `fixed-cover`, `fixed-contain`, `repeat`, `repeat-y` |
| `section_bg_overlay` | color | `""` | e.g. `"rgba(0,0,0,0.35)"` |
| `section_gradient_start` | color | `""` |  |
| `section_gradient_end` | color | `""` |  |
| `section_gradient_direction` | select | `"to bottom"` | `to top` … `to bottom right` |
| `section_width` | select | `"contained"` | `contained`, `wide`, `full` |
| `section_valign` | select | `"top"` | `top`, `center`, `bottom`, `stretch` |
| `section_column_gap` | select | `"md"` | `none`, `sm`, `md`, `lg`, `xl` |
| `section_padding_top` | select | `"md"` | `none`, `xs`, `sm`, `md`, `lg`, `xl`, `2xl`, `custom` |
| `section_padding_top_custom` | text | `""` | when `_top: custom`, e.g. `"80px"`, `"10vh"` |
| `section_padding_bottom` | select | `"md"` | same as `_top` |
| `section_padding_bottom_custom` | text | `""` | when `_bottom: custom` |
| `section_text_color` | color | `""` | overrides default text color for the section |
| `section_custom_class` | text | `""` |  |
| `section_custom_id` | text | `""` | anchor target |

### Column

| Field | Default | Values |
|---|---|---|
| `width` | `"1/1"` | `1/1`, `1/2`, `1/3`, `2/3`, `1/4`, `3/4`, `1/5`, `2/5`, `3/5`, `4/5`, `1/6`, `5/6` |
| `blocks` | `[]` | array of block objects |

### Spacing/Gap tokens (verify per project with `list-tokens`)

Typical defaults:
- Spacing: `none`=0, `xs`=16, `sm`=32, `md`=64, `lg`=96, `xl`=128, `2xl`=192 (px)
- Gap: `none`=0, `sm`=16, `md`=32, `lg`=48, `xl`=64 (px)
- Width: `contained`=content-width, `wide`=90%, `full`=edge-to-edge

**Theme conformance rule:** If a Token matches the design value semantically → use the token. Custom values only when no token fits. Drift = bad (token gets re-defined later, your section won't update).

---

## TEXT BLOCKS

### `text`
- **Purpose:** Any paragraph, heading, list, blockquote, inline link, inline image
- **Use when:** copy, body text, headlines (via Markdown `#`), bulleted lists, lead text, quote, eyebrow label, link sentence
- **Use NOT for:** standalone CTAs (use `button`), standalone images (use `image`), contact info (use `contact`)
- **Markdown supported:** `# H1` `## H2` `### H3`, `**bold**`, `*italic*`, `__underline__`, `~~strike~~`, `[link](url)`, `- list`, `1. ordered`, `> quote`, `---` (hr), `![alt](file://uuid)`
- **Fields:**
  - `text` (textarea, Markdown)
  - `text_align` (select: `left`/`center`/`right`/`justify`, default `left`)
  - `text_width` (range 0-100, default 100, %)
  - `horizontal_shift` (range -1…1, default -1)
  - `text_size_override` (select: `""`/`large`/`medium`/`small`/`tiny`/`custom`)
  - `custom_text_size` (number 8-72, when override=custom)
  - `text_color` (color, alpha)
  - `top_spacing`, `bottom_spacing` (text, default `"20px"`)
  - `custom_class`, `custom_id`
- **Minimal JSON:**
  ```json
  { "type": "text", "content": { "text": "# Hallo\n\nFließtext.", "text_align": "left" } }
  ```
- **Common `custom_class` conventions** (project-dependent — read existing pages):
  - `display-xl`, `display-lg`, `display-md` — large display headings
  - `lead` — lead paragraph below H1
  - `eyebrow` — small uppercase label above heading
  - `prose-en` — italic English mirror of German text

### `header`
- **Purpose:** Page-hero or section-header with full image, headline, subline, optional scroll arrow
- **Use when:** "Hero", "Heldenbild", landing intro, big title with image
- **Use NOT for:** small page titles (use `text` with `# Heading`), CTA section (use multiple blocks)
- **Fields:**
  - `image` (single file)
  - `image_mode` (toggle: `false`=Background / `true`=Scalable)
  - `image_size` (cover/contain, when image_mode=false)
  - `image_width` (text, when image_mode=true, default `"100%"`)
  - `header_height` (select: `full` / `custom`)
  - `custom_height` (when header_height=custom, default `"500px"`)
  - `headline` (text, H1)
  - `subline` (text, H2)
  - `text_color` (color, default `#ffffff`)
  - `text_shadow` (toggle, default true)
  - `vertical_position` (text offset, default `"0"`)
  - `enable_arrow` (toggle, default false)
  - `arrow_size`, `arrow_spacing_bottom`, `arrow_color` (when arrow enabled)
  - `top_spacing`/`bottom_spacing` (default `"0px"`)
  - `custom_class`, `custom_id`
- **Minimal JSON:**
  ```json
  { "type": "header", "content": {
      "image": ["file://<uuid>"], "headline": "Title", "subline": "Subtitle",
      "header_height": "full", "text_color": "#ffffff" } }
  ```

---

## MEDIA — Images

### `image`
- **Purpose:** Single image with caption, alt, optional link or lightbox
- **Use when:** standalone illustration, photo in text flow, screenshot
- **Use NOT for:** galleries (use `gallery`, `masonry`, `infinity-gallery`, `floating-gallery`)
- **Fields:** `image` (single), `caption` (textarea), `alt`, `image_width` (default `"100%"`), `horizontal_shift`, `top_spacing`/`bottom_spacing` (default `"20px"`), `click_behavior` (`none`/`lightbox`/`link`), `link`/`new_tab` (when link), `round_corners` (0-50px), `border_width` (0-20px), `border_color`, `custom_class`/`custom_id`
- **Minimal JSON:**
  ```json
  { "type": "image", "content": { "image": ["file://<uuid>"], "alt": "Description", "image_width": "100%" } }
  ```

### `gallery`
- **Purpose:** Structured Grid-Gallery, configurable aspect ratio, captions, hover effects
- **Use when:** "Bildstrecke", "Galerie", "Produkt-Showcase" with regular grid
- **Use NOT for:** asymmetric/Masonry (use `masonry`), infinite/scroll-driven (use `infinity-gallery`), single image (use `image`)
- **Key fields:**
  - `gallery` (files multiple, sortable)
  - `layout_style` (`1:1`/`4:3`/`3:4`/`16:9`/`9:16`/`default`)
  - `grid_columns` (1-5, default 3)
  - `gap_size` (text, default `"25px"`)
  - `extra_vertical_gap`, `content_width` (10-100%), `content_alignment`
  - `click_behavior` (`none`/`lightbox`/`link`, default `lightbox`)
  - `round_corners` (0-50px)
  - **Caption block** (when `caption_show_text: true`): `caption_style` (above/below/left/right/overlay), `caption_visibility` (show/hide/show_on_hover/hide_on_hover/caption_only), `caption_shift` (-80 … 80, for left/right), `caption_image_gap` (0-100px), 4× `caption_padding_*`, `caption_text_alignment`, `caption_text_color`, `caption_excerpt_length` (50-300 chars), `caption_element_spacing`, `caption_category_spacing`, `caption_bg_color` + `caption_bg_transparency`, `caption_bottom_line_enabled` + width/color
  - **Overlay** (when `caption_style: overlay`): `overlay_vertical_alignment` (top/middle/bottom)
  - **Hover effects** (granular): `tooltip_enabled` + `tooltip_content` (caption/image multiselect) + `tooltip_bg_color`/`tooltip_bg_transparency`; `caption_title_hover_color` (none/accent/custom) + `caption_title_hover_underline`; `hover_inner_scale_enabled` + amount (100-150%); `hover_object_scale_enabled` + amount; `hover_transparency_enabled` + amount; `hover_blur_enabled` + `hover_blur_target` (inner/object) + amount; `hover_outline_enabled` + width/color; `hover_rise_enabled` + amount
  - `gallery_id` (text, alphanumeric-dash pattern)
- **Minimal JSON:**
  ```json
  { "type": "gallery", "content": {
      "gallery": ["file://<a>","file://<b>","file://<c>"],
      "grid_columns": 3, "layout_style": "1:1", "click_behavior": "lightbox" } }
  ```

### `masonry`
- **Purpose:** Pinterest-style masonry, natural heights; overlay-only captions
- **Use when:** Moodboard, asymmetric image collection
- **Differences from `gallery`:** No aspect-ratio forcing; captions only overlay (no above/below/left/right); shadow hover effect available
- **Key fields:** `gallery` (files), `grid_columns` (1-5, default 3), `gap_size` (default `"25px"`), `content_width`, `content_alignment`, `click_behavior` (default lightbox), `round_corners`, caption overlay options (when `caption_show_text: true`), hover effects (scale, transparency, blur, outline, shadow), `gallery_id`

### `infinity-gallery`
- **Purpose:** Infinite Canvas with scroll-driven opacity/scale animations
- **Use when:** "Endlos-Scroll", "kinetisch", experimental portfolio
- **Key fields:** `gallery`, `container_height` (default `"100vh"`), `initial_density` (5-50, default 15 visible), desktop/tablet/mobile min/max widths, `parallax_intensity`, `animation_smoothness`, `drag_sensitivity`, `opacity_animation_enabled`/`opacity_from`/`opacity_to`, `scale_animation_enabled`/`scale_from`/`scale_to`, `animation_type` (interpolation/immediate), `animate_early`, hover scale/opacity, lightbox options, `gallery_id`

### `floating-gallery`
- **Purpose:** Scattered "schwebende" Gallery with parallax+drag interaction
- **Use when:** Editorial cloud-of-images, very experimental
- **Modes:**
  - `content_source: "images"` → upload images
  - `content_source: "projects"` → use child projects (with `project_source: children/all`, `project_filter_category`, `project_click_behavior: page/lightbox`)
- **Key fields:** `container_height`, `image_spacing`, `scatter_area_size` (0=auto, 0-10x viewport), `z_index`, responsive sizes (desktop/tablet/mobile min/max), `parallax_intensity`, `animation_smoothness`, `drag_sensitivity`, `scroll_zoom_enabled`, `round_corners`, `image_opacity`, hover opacity, click_behavior (none/lightbox), `gallery_id`

### `image-space`
- **Purpose:** Scrollable "Cloud" Gallery (similar to floating but scroll-driven, not drag)
- **Use when:** Scroll-reveal of scattered images
- **Almost identical to `floating-gallery`** but without `scatter_area_size` and content-source modes — only `gallery` files
- **Key fields:** `gallery`, `container_height`, `image_spacing`, `z_index`, responsive sizes, parallax/smoothness/drag/scroll-zoom, round_corners, opacity, hover, click_behavior, `gallery_id`

---

## MEDIA — Audio / Video

### `video`
- **Purpose:** Embedded (YouTube/Vimeo) or uploaded video
- **Use when:** any moving image content
- **Fields:**
  - `video_type` (`embed`/`upload`, default `embed`)
  - `video_file` (when upload, max 200MB)
  - `url` (when embed, YouTube/Vimeo URL)
  - `caption` (textarea)
  - `poster` (single image)
  - `autoplay` (toggle, default false)
  - `content_width` (0-100%), `horizontal_shift`
  - `top_spacing`/`bottom_spacing`, `custom_class`/`custom_id`

### `audio`
- **Purpose:** Audio player (mp3, wav, ogg, m4a)
- **Use when:** Podcast, sound piece, interview
- **Fields:**
  - `layout_variation` (`default`/`minimal`/`cover`)
  - `title`, `audio_file` (max 50MB), `cover_image`
  - `disable_download` (toggle, default true)
  - `caption`, `audio_width` (10-100%), `horizontal_shift`
  - `top_spacing`/`bottom_spacing`, `custom_class`/`custom_id`

---

## INTERACTIVE / CTA

### `button`
- **Purpose:** Single styled CTA button with link
- **Use when:** "Mehr erfahren", "Kontakt", "Download", standalone CTA inline
- **Use NOT for:** large Hero CTA (use `button` inside a centered layout column with hero text)
- **Key fields:**
  - `button_text` (max 100, required-ish — "Click here" placeholder)
  - `link_type` (`none`/`page`/`url`/`email`/`phone`/`file`, default `url`)
  - Conditional link fields: `link_page` (+ `new_tab_page`), `link_url` (+ `new_tab_url`), `link_email`, `link_phone`, `link_file` (with accept-list for downloads)
  - **Style:**
    - `button_size` (`small`/`medium`/`large`/`xl`, default `medium`)
    - `button_text_style` (`tiny`/`tiny_bold`/`small`/`small_bold`/`medium`/`medium_bold`/`large`/`large_bold`)
    - `button_variant` (`primary`/`primary_accent`/`secondary`/`outline`/`ghost`)
    - `button_width` (`auto`/`full`/`custom`), `button_custom_width` (10-100%, when custom)
    - `button_alignment` (`left`/`center`/`right`)
    - `button_radius` (`none`/`small`/`medium`/`large`/`full`)
    - `button_border_width` (0-5px)
  - **Custom colors** (toggle `custom_colors`): `button_bg_color`, `button_text_color`, `button_border` toggle + `button_border_color`
  - **Hover effects:** `hover_scale`, `hover_shadow`, `hover_rise`, `hover_accent`, `hover_custom_enabled` + `hover_custom_color`
  - **Icon options** (toggle `button_icon`): `icon_type` (character/svg), `icon_character` (e.g. `"→"`), `icon_svg`, `icon_position` (left/right/only), `icon_spacing` (0-20px)
- **Minimal JSON:**
  ```json
  { "type": "button", "content": {
      "button_text": "Mehr erfahren", "link_type": "url", "link_url": "https://example.com",
      "button_variant": "primary", "button_size": "medium" } }
  ```

### `contact`
- **Purpose:** Structured list of contact items (email/phone/url/page) with icons
- **Use when:** Contact section, footer-like contact info, "Kontaktdaten"
- **Use NOT for:** A single contact email in body text — that's a `text` block with `[mail](mailto:…)`
- **Key fields:**
  - `contact_items` (structure, sortable). Per item:
    - `link_type` (`email`/`url`/`phone`/`page`)
    - `text` (display label)
    - `new_tab` (when page/url)
    - `link_page` / `link_url` / `link_email` / `link_phone` (conditional)
    - `custom_icon` (SVG file)
  - **Layout:** `layout` (`vertical`/`horizontal`), `icon_position` (`left`/`right`), `gap` (0-100px), `content_alignment` (left/center/right)
  - **Styling:** `text_size` (e.g. `"inherit"`, `"16px"`), `text_decoration` (none/underline/overline/line-through), `font_weight` (`inherit`/100-900)
  - **Hover:** `horizontal_slide_enabled` + `slide_direction` (left/right) + `slide_distance` (5-50px)
- **Minimal JSON:**
  ```json
  { "type": "contact", "content": {
      "contact_items": [
        { "link_type": "email", "text": "hello@example.com", "link_email": "hello@example.com" },
        { "link_type": "phone", "text": "+49 …", "link_phone": "+49…" }
      ],
      "layout": "vertical" } }
  ```

---

## STRUCTURE & LAYOUT

### `layout` (2-column container)
- **Purpose:** Inline two-column layout WITHIN a single section column (nested layout)
- **Use when:** Image left + text right *inside* a wider section
- **Use NOT for:** Full-section two-column — use Section with two columns (Builder-content level)
- **Allowed child blocks (in `left_column` + `right_column`):** text, button, contact, gallery, audio, video, image, slider, code
- **Fields:**
  - `left_column` (blocks)
  - `right_column` (blocks)
  - `horizontal_shift` (10-90, default 50 = equal columns; 70 = left wider; 30 = right wider)
  - `column_gap` (0-80px, default 30)
  - `vertical_alignment` (top/center/bottom/stretch)
  - `mobile_behavior` (stack/keep/reverse)
  - `padding_top`/`padding_bottom`/`padding_left`/`padding_right` (text, default `"20px"`/`"0px"`)
  - **Styling:** `background_color` (alpha), `enable_border` toggle + `border_color` + `border_width` (1-5px) + `border_radius` (0-30px)

### `toggle` (accordion)
- **Purpose:** Expandable/collapsible section with nested blocks
- **Use when:** FAQ, expandable details, optional content
- **Allowed child blocks (in `toggle_blocks`):** text, button, contact, divider, gallery, masonry, audio, video, image, slider, code, table, layout
- **Fields:**
  - `section_title` (required)
  - `description` (small textarea)
  - `toggle_blocks` (blocks)
  - `default_open` (toggle, default false)
  - `enable_line` toggle + `line_color` (alpha) + `line_width` (1-5px)
  - `section_width` (0-100%), `horizontal_shift`
  - `background_color` (alpha), `text_color` (alpha), `round_corners` (0-50px)
  - 4× `padding_*` (default `"0"`)

### `divider`
- **Purpose:** Horizontal divider OR pure spacer
- **Use when:** Visual break within a section / breathing room without a line
- **Fields:**
  - `divider_color` (default `""` = theme text color)
  - `divider_thickness` (1-10px)
  - `divider_width` (10-100%)
  - `horizontal_shift` (-50…50%)
  - `hide_line` (toggle — true = spacer only, no line)
  - `enable_animation` (entrance animation on scroll)

---

## DATA / SPECIAL

### `code`
- **Purpose:** Embed iframe/HTML/Codepen
- **Use when:** Maps, forms, third-party embeds, Codepen, sketches
- **Use NOT for:** Custom CSS (that goes in `page_custom_css`) or JS (that goes in `page_custom_js`)
- **Fields:**
  - `code` (textarea, monospace) — paste iframe or HTML
  - `caption`, `height` (default `"400px"`), `content_width` (0-100%), `horizontal_shift`
  - `top_spacing`/`bottom_spacing`, `custom_class`/`custom_id`

### `table`
- **Purpose:** CV/Timeline or Custom Data Table
- **Use when:** CV (year + title), tabular data with optional links
- **Two modes:**
  - `table_type: "cv"` → `cv_data` (structure: year, title, url)
  - `table_type: "data"` → `data_rows` (structure: row_data comma-sep, row_url)
- **Styling:**
  - `table_title`, `table_title_size` (12-48px), `table_title_weight` (100-900), `table_title_distance` (0-80px)
  - `table_width` (10-100%), `horizontal_shift`, `row_height` (0-100px), `table_align` (left/center/right), `year_column_width` (text, default `"auto"`)
  - `show_borders` (default true), `striped_rows`, `hover_style` (background/accent_text/underline_text/custom_color_text)
  - Colors: `text_color`, `border_color`, `stripe_color`, `hover_bg_color` (when bg), `hover_text_color` (when custom)

### `map`
- **Purpose:** Leaflet-based map with marker
- **Use when:** Office location, event venue, contact map
- **Fields:**
  - `label`, `latitude` (-90…90, required), `longitude` (-180…180, required), `zoom` (1-20, default 13)
  - `show_marker` (default true), `custom_marker_svg`, `marker_size` (16-64px)
  - `link_type` (none/page/url), `link_page`/`link_url`/`new_tab`
  - `map_height` (default `"400px"`), `content_width`, `horizontal_shift`

---

## SLIDERS

### `slider` (image slider)
- **Purpose:** Image carousel with arrows/dots
- **Fields:**
  - `slides` (files multiple), `height` (default `"400px"`), `object_fit` (cover/contain)
  - `autoplay`, `speed` (ms, default 3000), `show_caption`
  - **Arrows:** `arrows`, `arrow_position` (inside/outside/cursor), `arrow_size` (small/medium/large), `colored_arrow` (text/background/white/accent), `arrow_style` (none/rect/round/circle), `arrow_background_color_*` (per style), `arrow_alignment_*` (per position)
  - **Dots:** `dots`, `dot_size`, `colored_dots` (false=text, true=accent)
  - `slider_width` (default `"100%"`), `horizontal_shift`

### `contentslider`
- **Purpose:** Slider for arbitrary content (not just images)
- **Allowed slides:** text, image, video, audio, code, button, gallery
- **Fields:** Same nav-controls as `slider`. `height` default `"600px"`. `slides` is type `blocks` not `files`.

### `projectheroslider`
- **Purpose:** Hero slider rotating through Projects (with custom image override)
- **Use when:** Landing-page Hero showing portfolio projects in rotation
- **Fields:**
  - `slides` (structure): per slide `project` (page select, listed projects only) + `custom_image` (optional override)
  - `height` (default `"80vh"`), `object_fit`, `autoplay` + `speed` (default 5000ms)
  - Nav (arrows + dots) like `slider`
  - **Layout:** `full_width` (toggle, default true) — when true: `full_screen` (extends behind nav) + `full_height` (100vh - nav). When false: `slider_width` + `horizontal_shift`
  - **Captions** (when `show_caption: true`): `caption_vertical_position` (top/middle/bottom, default bottom), `caption_text_alignment`, `caption_bg_color` (default `#000000cc`), `caption_text_color` (default `#ffffff`), `caption_padding`
  - **Scroll arrow:** `enable_arrow_down` + size/spacing/color

### `projects` (Projects Grid)
- **Purpose:** Auto-Grid of child Projects (template `project`), with extensive filter/sort/caption options
- **Use when:** Portfolio overview, work-grid
- **Use NOT for:** Manual list of fixed images (use `gallery`)
- **Caveat:** Pulls **child projects** of the current page automatically. To use elsewhere, the parent must have child pages with template `project`.
- **Key fields:**
  - **Layout:** `project_grid_layout` (aspect ratio), `project_grid_columns` (1-5), `project_grid_gap` (default `"50px"`), `project_extra_vertical_gap`, `gallery_top_spacing`/`gallery_bottom_spacing` (default `"3rem"`), `project_content_width`, `project_content_alignment`, `portfolio_round_corners`
  - **Caption content selection:** `project_caption_content` (multiselect: `title`/`year`/`category`/`excerpt`/`custom_links`, default `[title, year, category]`)
  - **Caption appearance:** `project_caption_style` (above/below/left/right/overlay, default below), `project_caption_shift`, `project_caption_visibility`, `project_caption_image_gap`, `project_caption_element_spacing`, `project_caption_category_mode` (button/comma, default comma), `project_caption_category_spacing`, 4× `project_caption_padding_*`, `project_caption_text_alignment`, `project_caption_excerpt_length`, `project_caption_title_size`, `project_caption_excerpt_size`
  - **Caption colors:** `project_caption_bg_color` (default `#00000000`), `project_caption_text_color`, `project_caption_bottom_line_enabled` + width/color
  - **Hover (rich):** `project_tooltip_*`, `project_caption_title_hover_*`, `project_hover_inner_scale_*`, `project_hover_object_scale_*`, `project_hover_transparency_*`, `project_hover_blur_*`, `project_hover_outline_*`, `project_hover_rise_*` (all prefixed `project_`)
  - **Filter & Sort:** `project_filter_enabled`, `project_filter_alignment`, `project_filter_show_count`, `project_filter_search` (+ `project_filter_search_position`: inline/spaced); `project_sort_enabled`, `project_sort_options` (multiselect: `title`/`shuffle`/`default`), `project_sort_default`, `project_sort_direction_toggle`

---

## QUICK LOOK-UP TABLE

| Brief says… | Use block |
|---|---|
| Hero / Heldenbild / Header-Image | `header` (single hero) or `projectheroslider` (rotating projects) |
| Headline / H1 / H2 / Title-Text | `text` with Markdown `#` / `##` |
| Lead / Intro-Paragraph | `text` with `custom_class: "lead"` |
| Eyebrow / Kicker / Pre-Headline | `text` with `custom_class: "eyebrow"` |
| Body / Fließtext / Description | `text` |
| List / Aufzählung | `text` with `- item` |
| Quote / Zitat | `text` with `> quote` |
| Inline image in text flow | `image` (own block, NOT `<img>` in text!) |
| Single image with caption | `image` |
| Photo Gallery (regular grid) | `gallery` |
| Masonry / Pinterest grid | `masonry` |
| Infinite scrolling images | `infinity-gallery` |
| Scattered, parallax | `floating-gallery` or `image-space` |
| Image Carousel | `slider` |
| Carousel of mixed content | `contentslider` |
| Hero rotating through projects | `projectheroslider` |
| Portfolio Grid (auto from children) | `projects` |
| YouTube / Vimeo / video file | `video` |
| Podcast / audio | `audio` |
| CTA Button / "Click here" | `button` |
| Mail-to / Tel / Adresse-Block | `contact` |
| FAQ / Akkordeon | `toggle` |
| 2-Column inline (image+text) | `layout` |
| Section background change | Section `attrs.section_bg_*` |
| Visual line / spacing only | `divider` (with `hide_line` for pure spacer) |
| Codepen / iframe / embed | `code` |
| CV / Timeline / Tabelle | `table` |
| Map / Location | `map` |

## Common Mistakes (DON'T)

1. **Don't write HTML in `text` blocks.** `<h2>Foo</h2>` should be `## Foo`. `<a href="...">` should be `[text](url)`. `<img>` should be a separate `image` block.
2. **Don't use `divider` for normal Section-Spacing.** Use `section_padding_top`/`_bottom` instead. `divider` is for visual breaks within a section.
3. **Don't approximate a Gallery with a `text` block listing image URLs.** Use `gallery` / `masonry` / etc.
4. **Don't put Custom CSS into a `code` block.** It belongs in `page_custom_css` (page Code tab) or site-level `custom_css` (Site Settings → Code).
5. **Don't fight block options.** If `gallery` has `hover_inner_scale_enabled`, use it instead of writing CSS.
6. **Don't invent block types.** If `pricing-table` is needed and doesn't exist → hard stop. Theme work, not content work.
