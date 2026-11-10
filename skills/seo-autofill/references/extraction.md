# Extraction — where each value comes from, and what must be confirmed

The data already lives in **this project's** content ("von der Seite selber"). Extract it via MCP reads
(`get_site`, `get_page`, `get_builder`) of the project you were started in — **never** from the
operator's account / identity (e.g. their login email) or any other site. **Derive, never invent**;
**preserve** any `seo_title` / `seo_description` / `seo_default_description` that is already set (read it,
keep it, do not propose a replacement); and route every value through the auto-vs-confirm governance
below before writing.

---

## 1. Source map (ranked by confidence)

| Need | Primary source in content | Notes |
|---|---|---|
| Brand / name | site `Title`; footer `Footer-custom-text` / advanced footer text | `Seo-site-name` defaults to site `Title`. |
| Legal name | legal page `Legal-name` | The registered company name (often "… GmbH"). |
| Email | contact `contact` block with `link_type: email` (`link_email`); else legal page `Legal-email` | `mailto:` is unambiguous → high confidence. |
| Phone | contact `contact` block `link_phone` (already clean) | Legal page usually only has it inside `Legal-additional-text` free text → regex-extract as a fallback (lower confidence). |
| Address (street / postal / city / country) | legal page `Legal-address` (multi-line) | Parse the lines; map a country name → ISO code (`Germany`/`Deutschland` → `DE`). |
| Region / state | legal page address, if present | Often absent → confirm/supply. |
| Social `sameAs` | contact block items with `link_type: url`; footer nav-list / text links | Canonicalize (strip tracking params), dedupe, and DROP share-intent links (`facebook.com/sharer`, `twitter.com/intent`, `wa.me/?text=`). |
| Geo lat / lng | home `map` block — the business's **own** marker (its lat/lng fields) | Present in many projects. If multiple markers, pick the one matching the business address. |
| Logo | site `Site-logo` (file UUID); else `Favicon` | The engine falls back automatically, so `Seo-org-logo` is optional when `Site-logo` is set. |
| Default social image | site `Site-logo`; a strong home hero / `header` block image | Propose a candidate; the user confirms it reads well as a 1200×630-ish card. |

### Contact block fields (the `contact` block in the builder)
Each contact row carries a `link_type` (`email` / `phone` / `url`) plus the matching value
(`link_email` / `link_phone` / `link_url`). Read them via `get_builder` on the page that hosts the
contact block (commonly home or a "Kontakt" page), then map: email → `Seo-org-email`, phone →
`Seo-org-phone`, url → a `Seo-same-as` candidate.

### Legal / Impressum page
`get_page` the `legal`-template page. Fields: `Legal-name`, `Legal-email`, `Legal-address`
(multi-line — street / postal+city / country), `Legal-additional-text` (free text; phone often hides
here). This is the highest-trust NAP source after the contact block, but it is **still confirm-required**
(see governance) because it must match Google Business Profile exactly.

---

## 2. Relaunch (optional) — old live site

If a Live URL is configured (a WordPress→Kirby relaunch is the common case):

- `WebFetch` the old site's **Impressum** and **contact** pages for additional NAP / social / copy.
- Tier order if reachable: existing JSON-LD / meta → Impressum **text** → footer links.
- **§9 caveat (important):** WebFetch's markdown conversion usually **strips the old `<head>` and its
  JSON-LD**, so don't rely on structured data from WebFetch. The Impressum **body text** survives and
  is parseable; the new project's own content is the primary source regardless. Treat anything from
  WebFetch as a candidate to confirm, never as ground truth.

---

## 3. Fields with NO in-content source → must be confirmed / supplied by the human

These cannot be derived from content. Propose a sensible default where noted, but require confirmation:

| Field | What to do |
|---|---|
| `Seo-org-type` | Infer a candidate from the business kind (a bakery → `Bakery`, a café → `CafeOrCoffeeShop`, a shop → `Store`, a service firm → `ProfessionalService`, else `LocalBusiness` for a physical location or `Organization` for online-only) — then **confirm**. |
| `Seo-org-hours` | No content source. Ask; only author if the business actually has fixed hours. Never invent hours. |
| `Seo-org-price-range` | Ask (e.g. `€€`). Optional — skip if the user doesn't want it. |
| `Seo-org-region` | Often absent from the address. Ask or leave empty. |
| `Seo-project-schema-type` | Default `Product` for a sellable-goods catalog, `CreativeWork` for a portfolio. Infer from the project pages, then confirm. |
| `Seo-default-description` | Synthesize a short, keyword-rich proposal (≤160) from the site's content; present it for editing. |
| `Seo-same-as` (beyond linked) | Only include profiles actually linked in content. Don't guess handles. If the user names more, add them. |

---

## 4. Governance — auto vs confirm

Each proposed field is `{ value, source, confidence }`. The chat proposal shows `source` so the user
understands *why* a value was suggested.

### Auto — pre-fill (high confidence, still editable in the proposal)
- Content language (`Site-language`)
- Brand / company name (`Seo-site-name`)
- Logo (`Seo-org-logo` — or rely on the `Site-logo` fallback)
- Email (`Seo-org-email`) — from an unambiguous `mailto:`
- Social `sameAs` (`Seo-same-as`) — the links actually present in content
- Default social image candidate (`Seo-default-image`)
- Per-page `Seo-title` / `Seo-description` (derived from each page's H1 / lead)

### Confirm-required BEFORE writing (load-bearing / must match the real GBP)
- Street address (`Seo-org-street` / `-postal` / `-city`)
- Phone (`Seo-org-phone`)
- Opening hours (`Seo-org-hours`)
- `Seo-org-type`
- Geo lat / lng (`Seo-org-lat` / `Seo-org-lng`)
- Price range (`Seo-org-price-range`)

**Never auto-pick a confirm-required field — even if only one candidate exists.** The operator usually
has no GBP access and cannot self-correct a wrong NAP; the cost of a wrong value is an invisible
ranking penalty.

### On source conflict
When two sources disagree (e.g. contact-block phone vs legal-page phone; old-site address vs new
content), present **all** candidates with their provenance and force the user to choose. Do not merge
or silently prefer one.
