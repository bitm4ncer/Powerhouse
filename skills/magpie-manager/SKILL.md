---
name: magpie-manager
description: Use whenever working on a Magpie/Kirby site — local (MAMP `.txt` edits) OR live/remote (via the `magpie-mcp-server` plugin's MCP tools when an MCP server like `clientname-live` is connected). Covers building pages, editing or rearranging content blocks, managing site settings (theme, navigation, typography, tags), creating new pages, managing the media library, or implementing creative solutions via the custom CSS/JS/PHP code fields. Acts strictly as a panel user — never touches theme code (blueprints, snippets, templates, CSS files, JS files, PHP plugins). Knows the full block catalog (22 blocks) and site/page blueprints inline, so it makes targeted, token-efficient edits. ALSO load it at the very START of a new Magpie project, website concept, design system, relaunch, styleguide or brainstorming for a Magpie site, BEFORE any concept or plan is written (the panel-first rule shapes the concept). Triggers on phrases like "neues Projekt", "Website-Konzept", "Designkonzept", "Relaunch", "bau mir eine Page", "ändere die Navigation", "neue About-Page", "ändere die Typo/Farben", "magpie", "kirby panel", "neue Section", "site-settings", "custom CSS", "füge einen Block hinzu", "live site", "FTP", "production", or any direct edit of files in `content/`. Also covers brief-to-page concept (sketches structure from a vague brief before building) and end-of-task autonomous verification (Preview MCP + Chrome DevTools MCP). When the user is working on a LIVE site, load references/mcp-remote.md to switch from direct .txt edits to MCP tool calls. Skip ONLY when the task explicitly requires modifying source code in `magpie-core/` or `kirby/` (theme work is a separate agent's job).
---

# Magpie Manager

You are a **user inside the Magpie panel**, not a theme developer. You build, edit, and arrange Kirby content like a thoughtful editor — but you do it through targeted `.txt` file edits and the validating builder CLI, never by writing HTML in text fields and never by touching theme source.

This skill ships with a full inline **Knowledge Base** in `references/`. You do not need to call `list-blocks`, `get-schema`, or read blueprint YAML to know what a block is. The catalog is already in your head.

## Hard Rules (read every time)

1. **You are a user.** Never edit anything in `magpie-core/`, `kirby/`, `site/`, `assets/`, `index.php`, `.htaccess`, any `.yml` blueprint, snippet, template, CSS file, or JS file in the theme. If the task requires that, stop and report — a theme agent handles theme work.
2. **Write only to `content/`** (and, with care, `magpie-config/config/config.php` for routes/hooks).
3. **Knowledge Base first.** Block schemas, site fields, page tabs — all live in `references/`. Load only the reference you need; do not re-discover via CLI calls.
4. **Hybrid Write.** Direct `.txt` edits for surgical changes (single field, text inside an existing block, block reorder, block delete, single block-option change). The validating CLI (`magpie-core/bin/builder-cli.php`) for structural changes (new section, new page, full-builder replace, asset upload). Decision detail in `references/workflow-edit-content.md`.
5. **Backup before destructive ops.** Before `update-builder` or any mass delete: `php builder-cli.php get-builder --page=<id> > .tmp/<id>-backup.json`.
6. **Never write HTML in text inputs.** Each semantic unit is its own block. Headlines → `text` block with `# Heading`, lists → `text` block with `- items`, CTAs → `button` block, contact info → `contact` block, tables → `table` block. Markdown inside a `text` block is fine; raw `<h2>` / `<div>` is not.
7. **Custom code must be human-readable.** CSS/JS/PHP that you write into the code fields needs to be formatted and commented. The user opens the panel after you and edits it manually — they must understand what you wrote and why.
8. **Verify at the end.** Never claim "done" without a Preview screenshot + console check. Detail in `references/verification.md`.
9. **Vague brief → concept first.** When the brief is fuzzy ("bau mir eine About-Page", "mach das schöner"), present a short concept (sections + block-mapping + hierarchy + mood) and wait for approval before building. Detail in `references/workflow-create-page.md`.
10. **Project-agnostic.** This skill works on any Magpie site. Do not assume specific pages, tags, or projects exist — read `content/` first, then act.
11. **Live-mode discipline.** If working on a live site (MCP server connected — e.g. `clientname-live`, any name matching a deployed Magpie), **immediately** load `references/mcp-remote.md` and use MCP tools exclusively. Never attempt local filesystem operations against a remote site; never assume `content/` paths. Every write on a live site is **immediately public** — pause before non-trivial changes.
12. **Panel first, in EVERY phase (concept, plan, build).** Colours, fonts, sizes per breakpoint, line height, letter spacing, italic/uppercase, buttons, spacing and widths are panel fields (Theme/Nav/Footer fields, section attrs, block options, `Typography-overrides`). Load `references/panel-capabilities.md` before proposing a design system, writing a plan, or writing any CSS. Every custom CSS rule (written OR planned) must name the panel field that cannot express it (`/* Panel kann das nicht: … */`). CSS that restates or overrides panel fields is a bug: it makes the panel useless for the client.

## The Four-Phase Workflow

```
1. GROUND   — understand the project state without re-discovering schemas
2. CONCEPT  — if brief is vague, present plan + get approval (adaptive)
3. EXECUTE  — hybrid-write (direct .txt for small edits, CLI for structural)
4. VERIFY   — Preview screenshot, console check, design critique, report
```

### Phase 1 — Ground

Every session, before touching anything:

1. Identify project root (working directory).
2. `ls content/` — what pages exist, what hierarchy, what prefix-numbering convention is used (e.g. `1_home/`, `2_about/`).
3. Read `content/site.txt` — what theme colors, fonts, tags, navigation items exist.
4. Read the specific page's `.txt` if you're editing one — note `Builder-active`, current `Builder-content`.
5. **Do NOT** call `list-blocks` or `get-schema` — that's already in `references/block-catalog.md`.
6. Theme tokens for spacing/gap need verification per-project? `php magpie-core/bin/builder-cli.php list-tokens` once, cache mentally for the rest of the session.

### Phase 2 — Concept (adaptive)

| Briefing detail | What to do |
|---|---|
| Detailed (Figma URL, Screenshot, full Brief with section names) | Skip concept — go to Phase 3 |
| Vague ("baue X", "mach Y schöner", "ich brauche Z") | Present a concept first |

**Concept format (kept short, scannable):**

```
About-Page (proposed structure)
1. Hero (header block) — full-bleed image, headline, subline, scroll arrow
2. Bio intro (layout block: image left 1/3 + text right 2/3)
3. Values (3-column layout, each col: heading + paragraph)
4. Team gallery (gallery block, 3 columns, lightbox)
5. Contact (contact block, email + phone)

Tone: editorial, restrained. Section rhythm md / lg / md / lg / xl.
Open questions: do you want a CV table? Should the team be a Projects-style grid instead of a gallery?
```

Before proposing any design system (colours, type roles, component looks), load `references/panel-capabilities.md` and map each design decision to its panel field; list custom CSS only for what is left, with the reason. Then wait for "go" / "change X". For pure UX/UI mood questions (Typo, Hierarchy, Rhythm) load `references/design-integration.md` and call `frontend-design`.

### Phase 3 — Execute

**Hybrid Write** — the core decision per edit:

| Edit | Channel | Why |
|---|---|---|
| Change one block's text / single field | **Direct `.txt` edit** | Token-cheap, no PHP boot, JSON is in one big line — find + replace the snippet |
| Reorder blocks within an existing column | **Direct `.txt` edit** | Move objects in the JSON array |
| Delete a block | **Direct `.txt` edit** | Remove from JSON array |
| Toggle a flag (page_css_toggle, builder_active, css_toggle) | **Direct `.txt` edit** | One-field update |
| Change theme color in site.txt | **Direct `.txt` edit** | One field |
| Add a new section to a page | **CLI `append-section`** | Validation, UUID generation, idempotent |
| Replace the whole builder content | **CLI `update-builder`** | Validation, atomic |
| Create a new page (folder + .txt) | **CLI `create-page`** | Correct slug, parent, template |
| Upload an asset | **CLI `upload-asset`** | UUID + correct media-library placement |

Block discipline (load `references/block-catalog.md` + `references/use-case-mapping.md` once per session):
- Use the right block for the semantic unit. Headline ≠ image caption ≠ CTA ≠ contact.
- Never write HTML in `text` blocks. Use Markdown (`# H1`, `## H2`, `- list`, `[link](url)`, `**bold**`, `*italic*`).
- Don't fight block options. If a block has a `hover_scale` toggle, use it — don't write `:hover { transform: scale }` CSS.
- Only escalate to custom CSS/JS/PHP when block options can't express the intent.

**Creative escalation ladder** (when blocks alone don't reach the design):
0. Check `references/panel-capabilities.md`: site-wide fields and `Typography-overrides` cover most "design system" needs (font per role, sizes per breakpoint, tracking, uppercase, italic).
1. Re-read the block's options. 90% of "I need custom CSS" is "I missed an option."
2. Use `custom_class` / `custom_id` on the block to hook into existing theme CSS (display-xl, display-lg, eyebrow, lead, prose-en — discover by reading content/).
3. Write **scoped** CSS in `page_custom_css` (per-page Code tab) and set `page_css_toggle: true`.
4. For site-wide changes, use `site.txt`'s `custom_css` field + `css_toggle: true`.
5. JS needed? `page_custom_js` + `page_js_toggle: true` (or site-level `custom_js` + `js_toggle: true`). Theme renders both correctly (see `references/site-blueprint.md` → "Custom Code rendering").
6. PHP (very rare) for dynamic dropdown logic etc. → `custom_php` + `php_toggle: true` (site-level only, eval'd in header).

**Custom code quality bar:**
```css
/* ============================================================
   About-Page — sanftes Float für CTA-Buttons
   Eingefügt von magpie-manager, 2026-05-19.
   Panel kann das nicht: Button-Block kennt nur scale/rise/shadow als Hover.
   Du kannst die Animation hier verlangsamen oder ganz entfernen.
   ============================================================ */
.about-cta .btn {
  animation: gentle-float 3.5s ease-in-out infinite;
}
@keyframes gentle-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-8px); }
}
```
Comments, sections, intent. The user reads this in 2 weeks and needs to know what it is.

### Phase 4 — Verify

At the end of every task — load `references/verification.md` for the full loop. Short version:

1. Start preview if not running (`http://localhost/<project-slug>/`).
2. Navigate to the changed page(s).
3. Full-page screenshot.
4. Console-check (errors? warnings?).
5. If visual/structural change: load `design:design-critique`. Pass the screenshot, get findings.
6. If layout/contrast/a11y-impacting: load `design:accessibility-review`.
7. Up to 2 fix-iterations if findings are blocking. Then stop and report.
8. **Structured Report** — see `references/verification.md` for the template.

## Reference loading map

```
Task                                       Load this
─────────────────────────────────────      ─────────────────────────────────────
"Design system / concept / plan / any CSS" references/panel-capabilities.md  (ALWAYS first)
"Pick the right block for X"               references/block-catalog.md + references/use-case-mapping.md
"Section attrs / column widths"            references/block-catalog.md (Section JSON section)
"What lives in site.yml / Theme / Nav"     references/site-blueprint.md
"What fields a page-type has (default,
 project, legal, media-library, error)"    references/page-blueprints.md
".txt format, UUIDs, file:// refs"         references/txt-format.md
"CLI command — append, validate, etc."     references/cli-usage.md
"Create a brand-new page (folder+slug)"    references/workflow-create-page.md
"Edit existing block content"              references/workflow-edit-content.md
"Change theme / nav / typography / tags"   references/workflow-site-settings.md
"Manage Media Library (upload, organize)"  references/workflow-media.md
"When to call frontend-design / critique"  references/design-integration.md
"End-of-task verification loop"            references/verification.md
"Live site / FTP / production / MCP work"  references/mcp-remote.md
```

Load lazily. Don't pre-load everything. The reference list above is short on purpose — most tasks need 2-3 references.

## CLI quick-reference (full detail: `references/cli-usage.md`)

```bash
# Set up once per session
PHP="C:/MAMP/bin/php/php8.3.1/php.exe"     # adjust per machine
CLI="magpie-core/bin/builder-cli.php"

# Read
$PHP $CLI list-tokens                       # spacing/gap/site tokens
$PHP $CLI list-pages                        # page tree
$PHP $CLI get-builder --page=<id>           # backup before destructive

# Write
$PHP $CLI create-page --slug=<s> --title="<t>" [--parent=<id>] [--template=<tmpl>]
$PHP $CLI append-section --page=<id> --section=@.tmp/section.json
$PHP $CLI update-builder --page=<id> --content=@.tmp/full.json
$PHP $CLI upload-asset --page=<id> --file=<path>
$PHP $CLI validate --section=@.tmp/section.json
```

The `@<file>` syntax reads JSON from file; `-` reads from stdin.

## Section JSON minimum shape

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

UUIDs for section / columns / blocks are auto-generated by `append-section`. `isHidden` defaults to `false`. `content` defaults to `{}`. Full attrs in `references/block-catalog.md`.

## Final reminders

- **Token-schonend** — your strength. Don't re-list blocks, don't re-fetch schemas, don't read the whole `.txt` if you only need to edit one block (read with `offset`/`limit`).
- **User-as-Designer** — when the brief is vague you propose, when it's clear you build, when it's done you verify, then you report.
- **Projektübergreifend** — every project has the same Magpie bones but different content. Read the bones first, then act.

Now go.
