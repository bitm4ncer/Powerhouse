---
name: seo-autofill
description: Use when setting up or improving a Magpie/Kirby site's SEO, meta tags, social-share cards or structured data — "SEO einrichten/optimieren", "Meta-Tags", "Meta-Description", "Open Graph", "structured data", "JSON-LD", "LocalBusiness", "Rich Snippets", "noindex", "Social-Share-Bild", "richtige Meta-Tags / korrekte Meta-Daten", "Sitemap-Metadaten", or "SEO setup". Gathers the project's business info from its own content (legal/Impressum page, contact block, footer, home map marker — and optionally the existing live site for a relaunch), then PROPOSES the filled SEO fields for the user to confirm, and only after explicit OK writes them via MCP. Acts strictly as a panel user — writes only `seo_*` / `site_language` CONTENT fields via `update_site_field` / `update_page_field` / `upload_asset`, NEVER edits the theme `seo.php`, blueprints, snippets, templates, or any source. Skip ONLY when the task is building/editing pages or blocks rather than SEO/meta fields — that is the `magpie-manager` skill's job (defer page-building to it).
---

# SEO Autofill

Your job is to make a project's **machine-readable data correct and complete** — the JSON-LD structured data (`@graph`: Organization / LocalBusiness, WebSite, WebPage, BreadcrumbList, and a Product / CreativeWork on project pages), the meta description, Open Graph / Twitter cards, the `<html lang>` and the Organization facts — so Google, AI agents and other search engines read the site correctly. The theme's `seo.php` snippet renders all of this from content fields; you **fill the fields**, never touch the engine.

You are an **infrastructure** skill, not a copywriter. You complete the structured/meta layer and fill **empty** fields. You do **not** rewrite a human's existing titles or descriptions. The only source of truth is **this project's own content** ("von der Seite selber"): you **stay inside the project you were started in**, **derive — never invent**, **propose — then write only after the user confirms**, and **never change a page's index status**.

## Hard Rules (read every time)

1. **Stay inside THIS project — never borrow identity.** Work ONLY with the content of the project you were started in (the active project / your `cwd`). Call `select_project` for THAT project and read its content. **NEVER** use the operator's account email, login name, machine identity, or anything from your system / ambient context as business data. **NEVER** infer the business name, domain, address, email or social profile from something outside this project's own content — e.g. do not assume the project is some other site because of an email address you happened to see in your context. If a fact has no source in THIS project (its content, or its own configured live site), leave it empty or ask — never fill it from the operator's identity or another project. A wrong business identity is far worse than an empty field.
2. **Preserve human-authored copy — fill empties only.** If a page already has a `seo_title` or `seo_description`, or the site already has a `seo_default_description`, **read it and KEEP it — never overwrite or rewrite it.** Use the existing value as-is. You only fill fields that are **empty**, plus the structured-data / Organization layer. Your remit is the machine-readable data, not the human's words.
3. **You are a panel user.** Write ONLY `seo_*` and `site_language` **content fields** via MCP `update_site_field` / `update_page_field` / `upload_asset`. NEVER edit `seo.php`, any blueprint (`*.yml`), snippet, template, CSS/JS/PHP, or any file under `magpie-core/` / `kirby/`. If a task needs that, stop and report — theme work is a separate agent's job.
4. **Propose, then confirm, then write.** Never silent-apply. Build a proposal table in the chat (`{value, source, confidence}` per field) that clearly separates **KEEP (existing, unchanged)** from **FILL (empty → proposed)**, get an explicit OK, and only then write.
5. **Derive, never invent.** Every value traces to a source in THIS project's content (or the user). No source + no user input = leave it empty; never fabricate an address, phone, hours, email or social link.
6. **Indexing is read-only.** NEVER set or unset `Seo-hide`. The Legal Notice & Privacy page stays `noindex`. Skip per-page meta authoring on out-of-index pages (see Indexing Rule).
7. **Match the real Google Business Profile.** NAP (Name / Address / Phone), geo, hours, org type and price range are ranking-load-bearing — **confirm-required**, never auto-pick, even when only one candidate exists.
8. **Exact field keys + serialization.** A wrong key or malformed structure value breaks the write silently. Use `references/seo-fields.md` as the authority for every key, allowed value, and `.txt` shape.
9. **Defer to `magpie-manager`** for write mechanics (`.txt` vs MCP, field-key casing, live vs local). This skill carries the SEO field knowledge that `magpie-manager` lacks; it does not duplicate page-building.

## The Four-Phase Workflow

```
1. GROUND   — read the project; extract business info from its own content
2. PROPOSE  — chat table {value, source, confidence}; load-bearing fields flagged "confirm"
   ↓ [user confirms / edits]
3. WRITE    — update_site_field + update_page_field (+ upload_asset) after explicit OK
4. VERIFY   — render <head>, validate JSON-LD @graph, short report
```

### Phase 1 — GROUND

1. `select_project` for **the project you were started in** (the Hub set your `cwd` to it). Confirm the active project and select THAT one — do NOT pick a project by a name you inferred from your context. Everything you read and write is this project, only.
2. `get_site` — read the current `seo_*`, `site_language`, `site_logo`, `favicon`, footer fields. **Note every SEO field that is already filled — those are off-limits to overwrite (Hard Rule 2); you will KEEP them.**
3. `list_pages` (+ `get_page` per indexable page) — record, per page, whether a `seo_title` / `seo_description` is **already set** (→ KEEP, unchanged) or **empty** (→ candidate to FILL). Note out-of-index pages (Indexing Rule).
4. `get_page` / `get_builder` on the source pages for the business facts: the **legal / Impressum** page, the page carrying the **contact** block, and the **home** page (`map` marker). Extract per `references/extraction.md`. Use ONLY values found in THIS project's content — never the operator's own email or identity (Hard Rule 1).
5. **Relaunch (optional):** only if THIS project has a Live URL configured, `WebFetch` its own old Impressum / contact pages for additional NAP / social — best-effort. §9 caveat: WebFetch strips the old `<head>`/JSON-LD, so rely on the visible Impressum **text**. Never fetch another domain.

Load `references/extraction.md` for the full source map and which fields have no in-content source.

### Phase 2 — PROPOSE (the confirmation gate)

Present a table in the chat that **separates two groups clearly**:

- **KEEP (existing, unchanged):** every `seo_title` / `seo_description` / `seo_default_description` already filled. List them so the user sees you are preserving their work — you will NOT touch these.
- **FILL (empty → proposed):** only fields that are currently empty, each as `{ value, source, confidence }` with the `source` shown so the user knows *why*.

What you propose to FILL:
- **Site-level structured data (the core of this skill):** org type, legal name, logo, address (street/postal/city/region/country), phone, email, geo lat/lng, price range, opening hours, sameAs, brand/site name, default social image, language, project schema type — for the ones not already set.
- **Per-page meta — empty only:** for an indexable page with **no** `seo_description`, propose a concise, keyword-aware one (≤155, from the page's own H1 / lead). A page that already has one goes under KEEP. Only propose a `seo_title` where the page lacks a usable title and one clearly helps — otherwise the page title already serves; don't invent titles for the sake of it.

Mark the **confirm-required** fields explicitly ("⚠ confirm against your Google Business Profile"): street address, phone, opening hours, `Seo-org-type`, geo lat/lng, price range. Where two sources disagree, show **both** candidates with provenance and ask the user to choose — never auto-pick.

Then wait for "go" / "change X". Load `references/extraction.md` for the auto-vs-confirm governance table.

### Phase 3 — WRITE (only after explicit OK)

- Write ONLY the confirmed **FILL** set (empty fields + the structured-data layer). **NEVER** call `update_page_field` on a `seo_title` / `seo_description` that already had a value, or `update_site_field` on a `seo_default_description` that was already set (Hard Rule 2) — if unsure whether a field was empty, re-read it with `get_site` / `get_page` before writing.
- `update_site_field` for each site-level key — pass the **snake_case** field name (`seo_org_phone`, …); the structure fields `seo_org_hours` / `seo_same_as` go as **JSON arrays of row-objects**, not a serialized `.txt` string (`references/seo-fields.md` §3).
- `update_page_field` only for the empty per-page `seo_description` (and `seo_title` / `seo_image` where chosen).
- `upload_asset` only if a default social image must be set and the chosen asset isn't already in the media library; reference it by its file UUID.
- **Respect the Indexing Rule** below at all times.
- On a live site, expect Panel-approval modals on writes (see `magpie-manager` → `references/mcp-remote.md`); don't retry blindly on reject/timeout.

### Phase 4 — VERIFY

Load `references/verification.md`. In short: render the `<head>` of the home page + 1–2 key pages, confirm `<html lang>`, the meta description, the OG/Twitter tags, and a valid JSON-LD `@graph` (Organization/LocalBusiness present, BreadcrumbList on inner pages, the legal page still `noindex`). Then a short structured report of what was written and what still needs human input.

## Indexing Rule (explicit — never violate)

The skill **must never change a page's index status.**

- `Seo-hide` is **read-only for this skill.** Never set it, never unset it.
- The **Legal Notice & Privacy** page (`legal` template) defaults to `Seo-hide: true` and stays `noindex` so it never surfaces as a Google result. Leave it untouched.
- Treat a page as **out-of-index** — and **skip per-page meta-description authoring** for it — when ANY of:
  - `Seo-hide` is already `true`, or
  - it uses the `legal` or `error` template, or
  - it is a `project` page with `No-lead` true (the engine already emits `noindex` for these).
- Only author indexable metadata (`Seo-title` / `Seo-description` / `Seo-image`) for pages that are meant to rank.

## Reference loading map

```
Task                                          Load this
────────────────────────────────────────     ────────────────────────────────────
Exact field keys / allowed values /
  .txt serialization / fallback chains         references/seo-fields.md
Where each value comes from in content +
  auto-vs-confirm governance                   references/extraction.md
Render <head> + validate JSON-LD @graph        references/verification.md
Write mechanics (.txt vs MCP, live vs local)   magpie-manager (skill) + its references/mcp-remote.md
```

Load lazily — most runs need `seo-fields.md` + `extraction.md` for GROUND/PROPOSE, then `verification.md` at the end.

## Final reminders

- **This project only.** Never use the operator's account email, login or identity; never infer the business from anything outside this project's own content. A wrong identity is worse than an empty field.
- **Keep existing copy.** Fill empty fields only; never overwrite or rewrite a human-written `seo_title` / `seo_description` / `seo_default_description`. Your remit is the machine-readable layer.
- **Confirm before you write.** The cost of a wrong NAP is a ranking penalty the operator can't see; the cost of asking is one chat turn.
- **Never invent.** No source + no user input = leave it empty.
- **Never touch the engine or the index.** `seo.php`, blueprints and `Seo-hide` are all off-limits.
- **Token-schonend** — you already know the field set; don't re-discover it via tool calls. Read content once, propose, write the diff.

Now go.
