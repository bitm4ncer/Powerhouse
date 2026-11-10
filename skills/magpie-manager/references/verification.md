# End-of-Task Verification

The rule: **No "done" claim without fresh evidence.** Every non-trivial task ends with a verification loop.

---

## When to verify

| Task type | Verification |
|---|---|
| Single field text change | Light: load the page, eyeball it |
| New section / multiple blocks | Full: screenshot + console + design critique |
| Theme/Navigation/Typography change | Full + check multiple pages (changes propagate site-wide) |
| New page | Full: screenshot + console + design critique + a11y review |
| Custom CSS/JS added | Full + check across different viewports if applicable |
| Backup/restore op | Light: verify page renders + content matches expectation |

---

## The Verification Loop

### Step 1 — Make sure preview is running

If `localhost:8888/<project>` (or wherever MAMP serves) isn't already up:
```bash
# Check if MAMP / preview is reachable
curl -s -o /dev/null -w "%{http_code}" http://localhost/<project>/ || echo "Preview not running"
```

If not running, ask user to start MAMP / their local server. Don't try to start it for them — that's setup, not task work.

### Step 2 — Navigate to the changed page

Pick the right tool:

**Claude Preview MCP** (if available, faster):
```
preview_start (if not running)
preview_navigate <url>
preview_screenshot
preview_console_logs
```

**Chrome DevTools MCP** (preferred for full inspection):
```
new_page <url>
take_snapshot          # for structure inspection
take_screenshot        # for visual
list_console_messages  # for errors / warnings
list_network_requests  # for failed requests
```

URL pattern: `http://localhost/<project-slug>/<page-id>` where `<page-id>` is the same id used in `--page=<id>` (e.g. `home`, `home/stadt-laden`, `legal-notice-privacy`).

### Step 3 — Full-page screenshot

Capture the whole page (`fullPage: true` parameter). Save mentally what was changed and verify it appears as intended.

Check for:
- Layout breakage (overlapping, misaligned)
- Missing images (broken file refs?)
- Wrong fonts (Custom-fonts not loading?)
- Spacing inconsistencies
- Colors off (wrong hex? token mismatch?)

### Step 4 — Console check

Look at console messages. **Treat as blocking:**
- Red errors (PHP errors, JS syntax errors, 404 for required assets)
- Repeated warnings (e.g. "Image src is empty" → bad file reference)

**Treat as non-blocking but mention in report:**
- Browser deprecation warnings
- Mixed content warnings (if expected for dev)
- Single warning about non-critical missing optional asset

### Step 5 — Network check

```
list_network_requests
```

Look for:
- 4xx / 5xx → broken page or missing assets
- Slow requests (> 5s) → maybe a large image needs optimization (note in report)

### Step 6 — Design critique (for structural / visual changes)

Load `design:design-critique` skill. Pass the screenshot + brief description.

Findings:
- **Blocking** (broken hierarchy, illegible contrast, broken layout): fix immediately. Up to 2 iterations. After 2 fix attempts that don't resolve, stop and report.
- **Polish** (small spacing tweak, color refinement): mention in final report, ask user if they want it tweaked.
- **Subjective taste** (different choice could work): note in report, defer to user.

### Step 7 — Accessibility review (when relevant)

For: new page, theme change, navigation change, color change.

Load `design:accessibility-review`. If findings exist:
- Fix high-impact issues (contrast, missing alt, missing labels)
- Note medium-impact ones in report

### Step 8 — Report

Structured report at the end. Template:

```markdown
## Done — <task summary>

### Changes
- <Page-id>: <what changed>
- <Page-id>: <what changed>

### Files written
- `content/<path>` — direct edit (X fields changed)
- via CLI: `append-section` to `<page>` (1 new section)

### Custom code added
- `content/<page>/<page>.txt` → `Page-custom-css` field (lines 12-45): editorial typography overrides for the lead paragraph. Toggle `Page-css-toggle` set to true.
- (none)

### Verification
- Screenshot: ✓ layout renders as expected
- Console: ✓ no errors / warnings
- Design critique: <one-sentence summary or "no blocking findings">
- A11y: <one-sentence or "no blocking findings">

### Open items for you
- Consider <minor polish suggestion>
- The new section uses custom padding `300px` bottom — let me know if you want it switched to a token (`xl` ≈ 128px or `2xl` ≈ 192px)
- <other things to look at>
```

---

## What "no evidence, no claim" looks like in practice

**Bad:**
> Done. Added a new contact section to home.

**Good:**
> Done. Added a new contact section to home (CLI `append-section`).
>
> Verified at `http://localhost/clientname-live/`:
> - Screenshot: contact block renders at the bottom with email + phone, vertical layout, no overlap.
> - Console: no errors.
> - Design critique: "Spacing is consistent with the rest of the page; the eyebrow label could be tightened if you want a snappier feel — your call."
>
> Custom code: none added.

---

## Fix iterations

If verification fails:

1. **Identify**: what's broken? (screenshot delta vs intent)
2. **Fix**: smallest possible edit to address the specific issue
3. **Re-verify**: new screenshot, new console check
4. **Cap at 2 iterations** — if the third attempt is needed, stop and report what's going wrong. Don't churn.

---

## When verification reveals you broke something

1. **Don't panic.** Backup file exists if you did your job (see `workflow-edit-content.md`).
2. Restore: `update-builder --content=@.tmp/<id>-backup.json`'s `raw` field.
3. Re-verify the restored page (should match pre-edit state).
4. Diagnose what went wrong before re-attempting.

---

## A note on production vs local

Verification is always on **local preview** (`http://localhost/...`). Do NOT navigate to production URLs unless explicitly instructed. Production deploys are user-controlled.
