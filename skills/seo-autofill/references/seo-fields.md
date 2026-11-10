# SEO Field Reference — exact keys, values, serialization

This is the authority for **what the skill writes**. A wrong key or a malformed structure value writes
nothing useful and the engine silently falls back. Double-check each key against this table; it mirrors
`magpie-core/snippets/seo.php` + `blueprints/site.yml` (SEO tab + `theme_colors > appearance`
`site_language`) + `blueprints/fields/seo.yml`.

**Key form — don't confuse the two:**
- **MCP `field` parameter = the snake_case blueprint name** (the "blueprint name" column below): pass
  `seo_org_phone`, `seo_org_hours`, `seo_title`, … to `update_site_field` / `update_page_field` (the
  tool examples use `seo_title`). Kirby writes the on-disk key for you.
- **On-disk `.txt` key = the Capitalized-Hyphen form** (`Seo-org-phone:`): how Kirby stores it in the
  file. Type this form only for a *direct* local `.txt` edit (MAMP mode), never as the MCP `field`.

**File-reference fields** (`seo_image`, `seo_default_image`, `seo_org_logo`): pass the value as
`file://<uuid>` (get the UUID from `get_site` / `get_page`, or from `upload_asset`'s result).

All site-level fields write to `content/site.txt` (MCP: `update_site_field`). All per-page fields
write to that page's `<template>.txt` (MCP: `update_page_field`).

---

## 1. Site-level keys → `content/site.txt`

| Key (.txt) | blueprint name | Type | What the engine renders |
|---|---|---|---|
| `Seo-site-name` | `seo_site_name` | text | Brand. Used in `<title>`, `og:site_name`, JSON-LD `name`. Falls back to site `Title`. |
| `Site-language` | `site_language` | text, ISO 639-1, default `de` (lives in **Theme → appearance**, not the SEO tab) | `<html lang>`, `og:locale` (mapped, e.g. `de`→`de_DE`), JSON-LD `inLanguage`. |
| `Seo-default-description` | `seo_default_description` | textarea, max 160 | Last-resort meta description (when a page has neither `Seo-description` nor a page `description`). |
| `Seo-default-image` | `seo_default_image` | files (single, `- file://uuid`) | Last-resort OG/Twitter image. |
| `Seo-org-enabled` | `seo_org_enabled` | toggle, default **true** when empty | Gates the whole Organization/LocalBusiness node. Leave empty or `true` to emit it. |
| `Seo-org-type` | `seo_org_type` | select, default `Organization` | JSON-LD org `@type`. Allowed values below. |
| `Seo-org-legal-name` | `seo_org_legal_name` | text | `legalName` (only if set). |
| `Seo-org-logo` | `seo_org_logo` | files (single) | `logo` (ImageObject) + `image`. Falls back to `Site-logo` → `Favicon`. |
| `Seo-org-phone` | `seo_org_phone` | tel | `telephone`. |
| `Seo-org-email` | `seo_org_email` | email | `email`. |
| `Seo-org-street` | `seo_org_street` | text | `PostalAddress.streetAddress`. |
| `Seo-org-postal` | `seo_org_postal` | text | `PostalAddress.postalCode`. |
| `Seo-org-city` | `seo_org_city` | text | `PostalAddress.addressLocality`. |
| `Seo-org-region` | `seo_org_region` | text | `PostalAddress.addressRegion`. |
| `Seo-org-country` | `seo_org_country` | text, ISO 3166-1 alpha-2, default `DE` | `PostalAddress.addressCountry`. Write the **code** (`DE`), not "Germany". |
| `Seo-org-lat` | `seo_org_lat` | text | `geo.latitude`. **Both** lat AND lng required, else `geo` is skipped entirely. |
| `Seo-org-lng` | `seo_org_lng` | text | `geo.longitude`. |
| `Seo-org-price-range` | `seo_org_price_range` | text | `priceRange` (e.g. `€€` or `€€€`). |
| `Seo-org-hours` | `seo_org_hours` | structure: `days` / `opens` / `closes` | `openingHoursSpecification[]`. Serialization in §3. |
| `Seo-same-as` | `seo_same_as` | structure: `url` | `sameAs[]`. Serialization in §3. |
| `Seo-project-schema-type` | `seo_project_schema_type` | select, default `CreativeWork` | `@type` of the item node on `project` pages. Allowed values below. |

### Allowed values

`Seo-org-type` (pick the **most specific** that fits — search engines reward specificity):
`Organization` (generic, default) · `LocalBusiness` · `Store` · `FoodEstablishment` · `Bakery` ·
`CafeOrCoffeeShop` · `Restaurant` · `ProfessionalService`.

`Seo-project-schema-type`:
`CreativeWork` (portfolio — default) · `Product` (shop / catalog) · `Article`.

---

## 2. Per-page keys → each page's `<template>.txt`

| Key (.txt) | blueprint name | Type | What the engine renders |
|---|---|---|---|
| `Seo-title` | `seo_title` | text, max 60 | Overrides `<title>` / OG / Twitter title. |
| `Seo-description` | `seo_description` | textarea, max 160 | meta / OG / Twitter description. Keep ≤ ~155 for clean SERP display. |
| `Seo-image` | `seo_image` | files (single) | OG / Twitter image. Falls back to `featured_image` → first content image → `Seo-default-image`. |
| `Seo-hide` | `seo_hide` | toggle | `noindex, nofollow`. **READ-ONLY for this skill — NEVER write it.** |
| `Seo-language` | `seo_language` | text, ISO 639-1 | Per-page override of `<html lang>` / `og:locale` / `inLanguage`. Leave empty to inherit the site language. |

---

## 3. Structure-field serialization (`.txt`)

These two fields are **structure** (a YAML list of objects) inside `.txt`. The exact shape matters.

`Seo-org-hours` — one row per distinct opening block. `days` is a **comma-separated** list that the
engine splits and emits verbatim into `dayOfWeek`, so use **schema.org English day names**
(`Monday`…`Sunday`). `opens` / `closes` are `HH:MM`.

```
Seo-org-hours:

-
  days: Monday, Tuesday, Wednesday, Thursday, Friday
  opens: 09:00
  closes: 18:00
-
  days: Saturday
  opens: 10:00
  closes: 14:00
```

`Seo-same-as` — one row per profile URL, sub-key `url`:

```
Seo-same-as:

-
  url: https://www.instagram.com/yourbrand
-
  url: https://www.facebook.com/yourbrand
```

Serialization rules (see `magpie-manager` → `references/txt-format.md` for the general format):
- The field name line, then a blank line, then the list.
- Item separator: `-` at indent 0; sub-fields indented **2 spaces**.
- Day names: full English (`Monday`, not `Mon` / `Montag`) — the engine passes them through unchanged.
- Empty structure = no node emitted (no `openingHoursSpecification` / no `sameAs`). Don't write an
  empty row.

> **Writing via MCP (important):** pass the value as a **JSON array of row-objects**, NOT the
> serialized `.txt` string — e.g. `update_site_field` with
> `{ "field": "seo_org_hours", "value": [ { "days": "Monday, Tuesday", "opens": "09:00", "closes": "18:00" } ] }`
> and `{ "field": "seo_same_as", "value": [ { "url": "https://instagram.com/brand" } ] }`. The tool's
> contract is "structure fields take a YAML-style array"; Kirby encodes it to the `.txt` shown above.
> `days` stays a **comma-separated string** (never a nested array — the engine uses `->split()`). The
> `.txt` blocks above are the on-disk result (type that form only for a direct local edit). Confirm
> with `get_site` after writing.

---

## 4. Title pattern (home vs inner)

The engine builds `<title>` as:

- **Home page:** brand only — `Seo-site-name` (or site `Title`). If you set a `Seo-title` on the home
  page, it is used verbatim instead. Usually leave the home `Seo-title` empty unless the user wants a
  tagline (e.g. `be bananas — Fruit catering in Düsseldorf`).
- **Inner pages:** `<page title or Seo-title> | <brand>` (the `| brand` suffix is dropped if the page
  title already equals the brand). So a good inner `Seo-title` is the page-specific part only — the
  engine appends the brand. Don't repeat the brand inside an inner-page `Seo-title`.

The social title (`og:title` / `twitter:title`) follows the same home-vs-inner logic.

---

## 5. Fallback chains the engine applies

Knowing these prevents over-writing fields that already resolve correctly:

- **Brand:** `Seo-site-name` → site `Title`.
- **Language:** page `Seo-language` → `Site-language` → `de`.
- **Page title:** page `Seo-title` → page `Title`.
- **Description (per page):** page `Seo-description` → page `description` (excerpt 155) → `Seo-default-description`.
- **Social image:** page `Seo-image` → page `featured_image` → page's first content image → `Seo-default-image`.
- **Org logo:** `Seo-org-logo` → `Site-logo` → `Favicon`.
- **Org type:** `Seo-org-type` → `Organization`.
- **Project item type:** `Seo-project-schema-type` → `CreativeWork`.

Implications:
- If `Site-logo` is already set and square-ish, `Seo-org-logo` is optional (it falls back).
- A page with a good `featured_image` already has an OG image; only set `Seo-image` to override.
- A page whose own `description` is already strong may not need a `Seo-description` — but authoring an
  explicit, length-tuned one is usually better for SERP control.

---

## 6. JSON-LD `@graph` the engine emits (so the proposal can explain the payoff)

From the written fields, `seo.php` outputs one `<script type="application/ld+json">` with `@graph`:

- **Organization / LocalBusiness** (when `Seo-org-enabled`): `@type` = `Seo-org-type`; `name`, `url`,
  optional `legalName`, `logo`+`image`, `address` (PostalAddress), `telephone`, `email`, `geo`
  (only if lat AND lng), `priceRange`, `openingHoursSpecification[]`, `sameAs[]`.
- **WebSite** — always; `inLanguage` from the resolved language; `publisher` → the Organization.
- **WebPage** — always; `name`, `description`, `primaryImageOfPage`, `about` → Organization;
  `breadcrumb` link on inner pages.
- **BreadcrumbList** — on every non-home page (built from the page's parents).
- **Project item** — on `project`-template pages: `@type` = `Seo-project-schema-type`
  (`Product` adds `brand` + `category`; `CreativeWork` adds `author` + `dateCreated` + `keywords`).

`Robots noindex` is emitted when `Seo-hide` is true OR the project page has `No-lead` true — which is
exactly why this skill leaves those alone (see the Indexing Rule in `SKILL.md`).
