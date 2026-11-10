# Workflow — Create a New Page

When the user wants a new page (About, Contact, Press, Studio, …).

---

## Step 1 — Concept first (if brief is vague)

If the brief is anything less than "build me this exact Figma" / "use this screenshot", **present a concept** before building.

Concept template:
```
<Page name> — proposed structure

1. <Section name> — <block(s) used>: <1-line purpose>
2. ...

Section rhythm: <padding pattern e.g. 2xl / lg / md / lg / 2xl>
Background rhythm: <e.g. transparent → none → accent → none>
Tone: <e.g. editorial restrained / playful bold / minimal>

Open questions:
- <Question 1>
- <Question 2>
```

Wait for "go" / corrections before building.

For visual/typographic concept (when "what should this LOOK like" is the question), **load `frontend-design`** skill — pass it the existing site's theme (colors, fonts, current pages) and ask for a mood + typographic hierarchy. Translate the result into Magpie blocks.

---

## Step 2 — Verify project state

```bash
# What pages exist? Which template should the new page use?
$PHP $CLI list-pages

# What's the prefix scheme? (Read content/ directly to see folders)
# e.g. content/1_home/, content/2_legal-notice-privacy/, content/3_about/ would be next
```

---

## Step 3 — Create the page (CLI)

```bash
$PHP $CLI create-page --slug=about --title="About" --template=default
# or for a child page (project under home):
$PHP $CLI create-page --slug=q4-launch --title="Q4 Launch" --parent=home --template=project
```

Returns the new page id. Note: page is created as **unlisted (draft)**. To list and assign sort order, rename the folder afterward:
```bash
# Move into the right prefix slot (3rd in nav order)
mv content/_drafts/about content/3_about
```
(If the page was created as a child of `home`, it lives in `content/1_home/_drafts/q4-launch` — rename to `content/1_home/3_q4-launch`.)

The CLI puts the page in `_drafts/` initially. Rename to add the numeric prefix and lift it out of `_drafts/`.

---

## Step 4 — Enable Builder (if using sections)

The new page has `builder_active: false` by default. To use sectioned layout:

Direct edit the new `.txt`:
```
Builder-active: false  →  Builder-active: true
```

Or stay with `modular_content` (a simple sequential block list, no section attrs).

---

## Step 5 — Build sections (per concept)

For each section in your concept:

1. Construct section JSON (see `block-catalog.md` for section attrs + block fields)
2. Save to `.tmp/section.json`
3. Validate:
   ```bash
   $PHP $CLI validate --section=@.tmp/section.json
   ```
4. Append:
   ```bash
   $PHP $CLI append-section --page=<new-page-id> --section=@.tmp/section.json
   ```
5. Continue with next section.

---

## Step 6 — Add the page to Navigation (if needed)

The new page won't appear in the menu unless added to `Menu-items` in site.txt.

Direct edit `content/site.txt` → find `Menu-items: ` → append a new item:
```
Menu-items: 
- 
  link_type: page
  link_page: 
    - page://0YFjXXizqWY5FBQR     # existing entry
  title: Work
  new_tab: false
- 
  link_type: page
  link_page: 
    - page://<new-page-uuid>      # ← your new page (get from list-pages output or pageid)
  title: About
  new_tab: false
```

To get the new page's UUID: it's not in `list-pages`. Either:
- Open the page's `.txt` and look at the auto-generated UUID at the very top (some Kirby pages have it), OR
- Use the page id as plain text reference in `link_page` (e.g. `page://about` — relative reference works)

Cleaner: use the page id form `page://about` if UUID isn't trivially accessible.

---

## Step 7 — Verify

Load `verification.md` — preview, screenshot, console check, design critique.

---

## Variations

### "I just need a draft I can flesh out later"
- `create-page` only
- Leave in `_drafts/`
- Don't append sections yet — let user fill in via panel

### "Project page" (with featured image, year, category)
- `--template=project --parent=<parent-page>`
- Then edit `project.txt` to set `featured_image`, `year`, `category`, `excerpt`, `custom_links`
- These are NOT Builder fields — they're top-level page fields, direct-edit only

### "Legal page"
- DON'T create one — `legal` page already exists in every Magpie project (`content/X_legal-notice-privacy/`). It's protected.
- To edit: open the existing `legal.txt`, set `legal_name`, `legal_email`, `legal_address`, `legal_hosting_provider_select`, etc.

### "Media-library"
- DON'T create — it's protected and unique per site.
- To upload assets: use `upload-asset --page=media-library --file=...`.
