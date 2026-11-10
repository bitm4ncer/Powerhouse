# Panel Capabilities: Design intent → Panel field

**Load this BEFORE proposing a design system, a concept, a plan, or any custom CSS.**
Hard Rule 12 ("Panel first") depends on it: every custom CSS rule must name the panel field
that can NOT express it. If a row below covers the intent, use the field, not CSS.

Field names are the `.txt` keys (Kirby capitalises the first letter, e.g. `Nav-text-color`).
Verify exotic ones against `magpie-core/blueprints/site.yml` or the block blueprint once per project;
cores differ slightly between versions.

## Colours

| Intent | Panel field |
|---|---|
| Page background, body text, accent | Site → Theme: `Text-color`, `Accent-color`, background colour field of the Theme tab |
| Section background / text colour (alternating colour fields) | Section attrs `section_bg_type: color`, `section_bg_color`, `section_text_color` (also `image`, `gradient`, `section_bg_overlay`) |
| Navigation bar + links | `Nav-background-color`, `Nav-text-color`, `Nav-border-*`, `Nav-shadow-*` |
| Burger / off-canvas menu | `Off-canvas-background-color`, `Off-canvas-menu-style` (left/right/below/fullscreen), `Off-canvas-text-align` |
| Footer | `Footer-background-color`, `Footer-text-color`, `Footer-border-color`, footer columns |
| Single text block colour | block `text_color` |
| Button colours | button `custom_colors: true` + `button_bg_color`, `button_text_color`, `button_border` + `button_border_color` |
| Colour of one element type site-wide | `Typography-overrides` → `color_override` |

## Typography

| Intent | Panel field |
|---|---|
| Load web fonts (self-hosted woff2) | `Custom-fonts` (structure: `font_name`, `font_weights[weight, style, font_files]`) |
| Base sizes / line heights / letter spacing | `Font-size-large|medium|small|tiny`, `Line-height-*`, `Letter-spacing-*` |
| **Font per role** (display serif for headings, label font, etc.) | `Typography-overrides` with `element_name` (preset list: h1–h3, p, a, `.site-header__nav`, `.burger-menu__link`, `.project-title`, `.caption-title`, `.btn`, …) **or `custom_selector`** (any selector, e.g. `.my-mark h2`) |
| Size per breakpoint | overrides: `font_size_override`, `font_size_tablet_override`, `font_size_mobile_override` |
| Weight, line height, letter spacing | overrides: `font_weight_override`, `line_height_override`, `letter_spacing_override` |
| Italic, uppercase, underline | overrides: `font_style_italic`, `text_transform_override`, `text_decoration_override` |
| Size of one text block | block `text_size_override` (large/medium/small/tiny/custom) + `custom_text_size` |

Pattern: give text blocks a `custom_class` (e.g. `brand-hero`) and target `.brand-hero h1` via an override
`custom_selector`. The class is a hook; the styling lives in the panel.

## Layout and spacing

| Intent | Panel field |
|---|---|
| Section width, vertical padding, column gap, vertical alignment | `section_width` (contained/wide/full), `section_padding_top|bottom` (tokens or `custom`), `section_column_gap`, `section_valign` |
| Column proportions | column `width` (1/1 … 5/6) |
| Space around a block | block `top_spacing`, `bottom_spacing` |
| Reading width / offset / alignment | text `text_width`, `horizontal_shift`, `text_align` |
| Anchor targets | `section_custom_id` / block `custom_id` |
| Image size, corners, border | image `image_width`, `round_corners`, `border_width`, `border_color` |
| Grid of images with fixed ratio | gallery `layout_style`: `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `default` |
| Project grid | `projects` block: ratio (same list, **no 4:5**), columns, gap, caption content/style, hover effects, filter/sort. Shows ONLY children of its own page, no item limit, backend order |
| Project detail header | on the PARENT page: `Project-header-layout` (vertical/horizontal/justified/two-column), `Project-header-elements` |
| Prev/next project links | Site: `Project-navigation-arrows|labels|titles|border|bottom-spacing` |

## Buttons

`button_variant` (primary/primary_accent/secondary/outline/ghost), `button_size`, `button_text_style`,
`button_radius` (none…full = pill), `button_border_width`, `button_width`, `button_alignment`,
custom colours (above), icon options, hover: `hover_scale`, `hover_rise`, `hover_shadow`, `hover_accent`,
`hover_custom_enabled` + `hover_custom_color`.
**Gotcha:** hover colour changes the BACKGROUND only, text colour stays. Use a translucent tint
(e.g. `#f2e2cc26`) or you get invisible text on hover.

## Forms, maps, embeds

- `contact-form`: recipient, labels/texts, optional fields (phone/subject/company/privacy), `custom_fields`
  (own inputs), auto-response. Store-first inbox in the panel.
- `map`: lat/lon, zoom, marker (custom SVG + size), height, width. No tile styling.
- `magpie-instagram`: count, layout, columns per breakpoint, ratio, captions, follow button. Needs the account connected (token) first.

## Genuinely CSS/JS only (escalate, and say why in a comment)

- `font-stretch` / variable-font axes other than weight
- Fluid `clamp()` sizes (overrides give three fixed breakpoints, usually enough)
- An exception inside a styled element (e.g. `em` inside an uppercase heading stays lowercase)
- Aspect ratios not offered by the block (e.g. 4:5 on images or project grids): `aspect-ratio` + `object-fit`
- Table layouts from Markdown tables in a text block (the `table` block has no header row and splits commas)
- Shapes and rotation (round badges/stickers), overlaps across section edges, `position` tricks
- Section minimum height (no field)
- Hover text-colour swaps, pseudo elements, transitions beyond the built-in hover toggles
- Map tile filters, form field look
- Anything that needs data from another page (e.g. teaser of the newest child projects elsewhere) or DOM reordering: JS

## Pre-CSS checklist (run it, don't skip it)

1. Which panel field would express this? Check the tables above.
2. If none: write the CSS **scoped** to a `custom_class` hook, and head the rule with
   `/* Panel kann das nicht: <reason> */`.
3. Never restate in CSS what a panel field already sets (colours, fonts, sizes, spacing, radii).
   CSS that overrides panel fields makes the panel useless for the client.
