# Verification — render the `<head>` and validate the JSON-LD

After writing, prove the fields actually rendered. The theme's `seo.php` does the rendering; you check
its output on the running local server (or, for a live site, the live URL).

---

## 1. Render the `<head>`

1. Make sure the project's local server is running (it is started by `select_project`; the Hub
   reports the URL, e.g. `http://localhost:PORT/`). For a live site, use the live URL.
2. Fetch the rendered HTML of the **home page** + **1–2 key indexable pages** (a service/about page and,
   if present, one `project` page so the BreadcrumbList + project item node can be checked). Prefer a
   Preview / Chrome DevTools MCP if one is available. **Caveat:** `WebFetch`'s markdown conversion
   usually strips the `<head>` and the JSON-LD `<script>`, so it cannot confirm structured data — when
   only `WebFetch` is available, treat the **`get_site` / `get_page` field read-back (step 3) as the
   reliable confirmation** that the data was written, and say plainly that the rendered JSON-LD was not
   directly inspected.
3. Read back the written fields with `get_site` (and `get_page` per page) to confirm the structure
   fields (`Seo-org-hours` / `Seo-same-as`) serialized correctly.

> Note: `seo.php` skips emitting `<title>` / `<meta description>` itself if the optional Meta Knight
> plugin is active (it owns them then). The OG/Twitter tags and JSON-LD are always emitted by the
> snippet, so verify those regardless.

---

## 2. Checklist per page

**Home page**
- `<html lang="…">` matches the resolved language (`Site-language`).
- `<title>` = the brand (`Seo-site-name` / site `Title`), unless an explicit home `Seo-title` was set.
- `<meta name="description">` present and = the intended copy (page → default fallback).
- Open Graph: `og:title`, `og:description`, `og:url`, `og:type` = `website`, `og:site_name`,
  `og:locale` (mapped, e.g. `de_DE`), `og:image` (+ width/height when known).
- Twitter: `twitter:card=summary_large_image`, `twitter:title`, `twitter:description`, `twitter:image`.
- JSON-LD `@graph` contains **Organization / LocalBusiness** (correct `@type`, `name`, `address`,
  `telephone`, `geo` if lat+lng, `openingHoursSpecification`, `sameAs`) **and** WebSite **and** WebPage.
- **No** `BreadcrumbList` on the home page (correct — it's skipped there).

**Inner indexable page**
- `<html lang>`, `<title>` = `Page | Brand`, meta description present.
- JSON-LD `@graph` includes **BreadcrumbList** with the correct crumb chain (brand → parents → page).
- On a `project` page: the item node has the right `@type` (`Seo-project-schema-type`) with its
  type-specific fields (Product → `brand`/`category`; CreativeWork → `author`/`dateCreated`/`keywords`).

**Legal Notice & Privacy page (regression check)**
- `<meta name="robots" content="noindex, nofollow">` is **still present** — confirm the skill did NOT
  unset `Seo-hide`.

---

## 3. Validate the JSON-LD

- Extract the `<script type="application/ld+json">` block and confirm it parses as valid JSON.
- Confirm `@context = https://schema.org` and that `@graph` is an array of the expected nodes.
- Sanity-check the `@type` values and that required sub-objects (`PostalAddress`, `GeoCoordinates`,
  `OpeningHoursSpecification`) are well-formed.
- If a browser tool is available, a quick eval of the parsed JSON, or pasting into Google's Rich
  Results Test, confirms no schema errors. (Optional — JSON validity + the field checklist above is
  the minimum bar.)

---

## 4. Report

Close with a short, structured report:

```
SEO Autofill — <project> — done

Written (site):   brand, language, org type, address, phone, email, geo,
                  hours (N rows), sameAs (N), default description, default image
Written (pages):  N indexable pages got Seo-title + Seo-description
Skipped:          Legal Notice & Privacy (noindex, untouched); <other noindex/no_lead pages>
Verified:         <html lang>, meta description, OG/Twitter, JSON-LD @graph
                  (Organization/LocalBusiness + BreadcrumbList on inner pages) ✓
Still needs you:  <e.g. confirm GBP phone matches; add opening hours if applicable;
                  geo lat/lng not in content — supply if a map listing matters>
```

Surface anything that was confirm-required but the user left unanswered, and anything left empty
because no source existed — so the human knows exactly what remains.
