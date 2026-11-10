# Use Case → Block Mapping

A pragmatic lookup table for translating user briefs into the right block. Pair with `block-catalog.md` for field details.

---

## "I want a Hero / Heldenbild / Header-Image"

| Specifics | Block |
|---|---|
| Single hero with image + headline + subline | `header` |
| Rotating hero through several projects | `projectheroslider` |
| Full-screen video bg | Section with `attrs.section_bg_type: "image"` + `section_bg_image` of a video poster, then page Custom Background with `page_background_video` |

---

## "I need text / heading / paragraph"

Always `text` block — never raw HTML. Use Markdown:
- `# Heading 1` → for the main page title (avoid duplicate H1; usually `header`'s `headline` is your H1)
- `## Heading 2` → section headlines
- `### Heading 3` → sub-headings
- Plain text → paragraphs
- `- item` → bulleted list
- `1. item` → ordered list
- `> quote` → blockquote
- `**bold**`, `*italic*`, `[link](url)` → inline formatting
- `![alt](file://uuid)` → inline image (rare — prefer separate `image` block)

Use `custom_class` for theme styles (read existing pages for available classes):
- `display-xl`, `display-lg`, `display-md` — large display headings
- `lead` — lead paragraph
- `eyebrow` — small uppercase label
- `prose-en` — italic English translation

---

## "I want to show a CTA / Button / Link"

| Briefing | Approach |
|---|---|
| Single styled button | `button` block |
| Inline link in a sentence | `text` with `[link text](url)` |
| Email/Phone CTA | `button` with `link_type: "email"` / `"phone"` OR `contact` block (better for grouped contact info) |
| Multiple CTAs in a row | Multiple `button` blocks in a layout column (use `layout` block or section with 2-3 columns) |
| Download file | `button` with `link_type: "file"` + `link_file` |
| Anchor link to another section | `button` with `link_type: "url"` + `link_url: "#section-id"` (where section-id matches a section's `section_custom_id` or block's `custom_id`) |

---

## "I need contact / email / phone displayed"

Always `contact` block with structured items. Each item has `link_type`, label `text`, and the right link field:

```json
{ "type": "contact", "content": {
    "contact_items": [
      { "link_type": "email", "text": "hello@example.com", "link_email": "hello@example.com" },
      { "link_type": "phone", "text": "+49 178 …", "link_phone": "+49178…" },
      { "link_type": "url", "text": "Instagram", "link_url": "https://instagram.com/…", "new_tab": true }
    ],
    "layout": "vertical", "icon_position": "left"
} }
```

For a physical address (no link), use a `text` block:
```
**Studio**  
Name  
Street 7  
12345 City
```

---

## "Show a table / CV / Timeline"

Always `table` block.

- **CV / Timeline:** `table_type: "cv"`, populate `cv_data` (each entry: `year`, `title`, optional `url`)
- **Data table:** `table_type: "data"`, populate `data_rows` (each entry: `row_data` comma-separated)
- **Multiple tables:** Multiple `table` blocks. Each can have its own `table_title`.

Don't try to build a table with `text` blocks + alignment hacks.

---

## "I need an image / photo"

| Briefing | Block |
|---|---|
| Single image with caption | `image` |
| Image with link/lightbox | `image` + `click_behavior: "lightbox"` or `"link"` |
| Multiple images, regular grid | `gallery` (set `layout_style` for aspect ratio) |
| Pinterest/masonry | `masonry` |
| Carousel / Slideshow | `slider` (images) or `contentslider` (mixed) |
| Background image for section | Section `attrs.section_bg_type: "image"` + `section_bg_image` |
| Background image for whole page | Page Custom Background tab → `page_background_image` |

---

## "I want a gallery"

| Style | Block |
|---|---|
| Regular grid, equal aspect ratios | `gallery` with `layout_style` (1:1 / 4:3 / etc.) |
| Pinterest / asymmetric heights | `masonry` |
| Infinite scrolling / endless | `infinity-gallery` |
| Scattered / cloud / parallax / drag-interactive | `floating-gallery` |
| Scroll-driven scattered | `image-space` |
| Hero rotation | `slider` for plain images, `projectheroslider` for projects |

---

## "Show projects / portfolio"

| Style | Block |
|---|---|
| Auto-grid of child projects | `projects` (must be on a page that HAS child pages with template `project`) |
| Hero showing 3-5 projects | `projectheroslider` |
| Cloud/parallax of project images | `floating-gallery` with `content_source: "projects"` |

To customize what's shown per project: edit the child project's `project.txt` fields (`featured_image`, `year`, `category`, `excerpt`, `custom_links`).

---

## "Video / Audio"

| Source | Block |
|---|---|
| YouTube/Vimeo URL | `video` with `video_type: "embed"` |
| MP4/WebM file | `video` with `video_type: "upload"` |
| Podcast / MP3 | `audio` |

---

## "Add an FAQ / Accordion / Collapsible"

`toggle` block. Each toggle has its own title + nested blocks. For multiple FAQ entries: multiple `toggle` blocks.

---

## "Two-column layout: image left, text right"

**Two options:**

### Option A — Section with two columns (PREFERRED for full-width 2-col)
Use the page's Builder-content section with `columns: [{width: "1/2", blocks: [image]}, {width: "1/2", blocks: [text]}]`.

### Option B — `layout` block (nested inline 2-col within a wider section)
Use when the 2-col is **inside** a contained area, perhaps alongside other blocks above/below in the same section column.

Decision rule: If the 2-col should be at section level (e.g. the whole section is image+text), use **Section** columns. If the 2-col is one element among others, use **`layout`** block.

---

## "Embed Codepen / iframe / external widget"

`code` block. Paste the full iframe/embed HTML into `code` field. Set `height` to match the iframe's intrinsic height (look for `height="XXX"` in the embed code).

DON'T use this for custom CSS or JS — those go in the page Code tab.

---

## "I need a map / location"

`map` block. Get latitude/longitude from Google Maps or OpenStreetMap. Set `zoom: 13` for street-level.

---

## "Add a divider / spacer between content"

| Want | Approach |
|---|---|
| Visible horizontal line | `divider` with `hide_line: false` |
| Just empty space (vertical breathing room) | `divider` with `hide_line: true`, set `top_spacing`/`bottom_spacing` |
| Bigger gap between sections | Don't use `divider` — adjust section's `section_padding_top` / `_bottom` |

---

## Section composition heuristics

When designing a full page, think in section rhythm:

**Typical landing structure:**
1. Hero (`header` or `projectheroslider`) — `section_padding_*: 2xl`, full-bleed
2. Lead / Intro — `contained`, `2xl` top, `md` bottom
3. Content sections (alternate `contained` and `wide`, alternate transparent and `bg_color` for visual rhythm)
4. Projects / Gallery — often `wide` or `full`
5. CV / details — `contained`
6. Contact / CTA — `contained`, sometimes with accent `section_bg_color`
7. Footer-CTA — `full`, `xl` padding

**Spacing rhythm rules:**
- `md` is base
- `lg` for breathing room between major sections
- `xl` / `2xl` only for hero, final CTA, or intentional gaps
- Don't use `2xl` consecutively — over-spacing breaks visual flow

**Background-color rhythm:**
- Don't switch every section — feels nervous
- Pattern that works: `none, none, color, none, color-accent, none, none`
- Accent-background sections work best for testimonials, final CTAs

---

## "Make hover / animation / micro-interaction X"

1. **First check block options.** Gallery, masonry, projects, button — all have rich hover toggles (scale, opacity, blur, outline, shadow, rise). 90% of "I want a hover effect" is already there.
2. **If no option:** scoped `page_custom_css` with `@keyframes` etc. Use `custom_class` on the relevant block to scope.
3. **JS-driven (scroll-trigger, mouse-follow, etc.):** `page_custom_js`. Add comments so the user understands.
4. **NEVER write `<script>` tags into a `text` or `code` block** unless it's a self-contained external embed (Codepen, etc.).

---

## "Make typography X"

| Want | Where |
|---|---|
| Change H1 size globally | Site Settings → Typography → `Typography-overrides` → element `h1` |
| Custom font family | Site Settings → Typography → `Custom-fonts` (upload .woff2 via Media-Library, then add to structure) |
| One specific block bigger | Block's `text_size_override` field (text block has it) or `custom_text_size` |
| Custom class for one section | `custom_class` on block + custom CSS in `page_custom_css` |

---

## "Make it more / less spacious"

In order of preference:
1. Adjust the section's `section_padding_top` / `_bottom` (use tokens: md/lg/xl/2xl)
2. Adjust block's `top_spacing` / `bottom_spacing` (numeric, e.g. `"32px"`)
3. Add a `divider` with `hide_line: true` between elements

---

## When NO block fits

If a brief calls for something that genuinely doesn't fit any block (e.g. "pricing table with column comparison", "step-by-step process diagram", "social proof avatars row"):

1. **Stop. Don't fake it.**
2. Re-read `block-catalog.md` — is there a block that could be configured creatively? (e.g. pricing → multi-column section with `text` blocks)
3. If approximation is good enough, do that and report the compromise.
4. If approximation is ugly/wrong, **report to user**: "Block 'X' doesn't exist in this Magpie. To build this properly, the theme needs a new block — that's beyond user-level work." Suggest a simplified version using existing blocks.
