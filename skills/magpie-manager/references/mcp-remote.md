# MCP-Remote — Working on a Live Magpie Site

When the user is working on a **live Magpie site** (FTP-hosted, not local MAMP), the local `.txt` editing approach doesn't apply — those files live on a remote server. Instead, the site exposes itself as an **MCP server** via the `magpie-mcp-server` Kirby plugin, and you reach it through MCP tools.

Load this reference whenever the user mentions: "live site", "production", "FTP", "the deployed site", "clientname-live.com" (or any other live magpie URL), or when you detect that an MCP server named like a Magpie deployment is connected (e.g. `clientname-live`, `clientname-live`).

---

## Mental model

| Local MAMP work | Live site work |
|---|---|
| Edit `content/*.txt` directly | MCP `update_*` tools |
| `php builder-cli.php list-pages` | MCP `list_pages` tool |
| `php builder-cli.php append-section ...` | MCP `append_section` tool |
| Read files with Read tool | MCP `get_page`, `get_builder`, `get_site` |
| Preview at `http://localhost/...` | Preview at the live URL |

**Crucially:** on a live site, every write is **immediate and visible to the public**. Extra caution.

---

## Detection: am I in live or local mode?

At the start of a task on a magpie site, check which MCP servers are connected. If you see an MCP server with a name like `clientname-live`, `clientname-live`, `production`, or any name the user has assigned to a remote Magpie deployment → assume **live mode**. If not, you're local.

You may also ask: "Working on the live site or local?" if ambiguous.

When in doubt and the user has both connected: ask. Don't write on production by accident.

---

## Hard Rules in Live Mode

1. **All writes go via MCP tools.** Never attempt direct filesystem operations on a live site — you can't reach `content/` from your machine and any path-based assumption breaks.
2. **Backup before destructive writes.** Always `get_builder` (or `get_site`) before `update_builder` / `update_site_field` on critical pages. Save the `raw` field locally as `.tmp/<page>-backup.json` so you can rollback via `update_builder`.
3. **Respect approval modals.** Some write tools may block waiting for an admin to approve in the Panel (per device settings). When the tool response says "Approval timed out" or "User rejected", do NOT retry blindly — report to the user and ask.
4. **Verify on the live URL.** After writes, screenshot the live page via Chrome DevTools MCP. Don't claim done without seeing the change rendered publicly.
5. **Be public-aware.** A typo lands publicly. A broken section breaks the site for visitors. Pause and double-check before any non-trivial write.
6. **Project tokens are scoped.** The MCP server's tools are documented `[magpie-manager-only]`. Don't proxy them through other skills — call them directly inside magpie-manager workflows.

---

## Tool mapping (local-CLI → MCP-tool)

| Local | MCP-Remote | Notes |
|---|---|---|
| Read `content/site.txt` | `get_site` | Returns full site content array |
| Read `content/<page>/<page>.txt` | `get_page {page_id}` | Returns full page content |
| `builder-cli list-pages` | `list_pages` | Same shape (id, title, template, status, depth) |
| `builder-cli list-tokens` | `list_tokens` | Spacing/gap/site tokens |
| `builder-cli list-blocks` | `list_blocks` | Sanity check; KB has the standard 22 |
| `builder-cli get-builder --page=<id>` | `get_builder {page_id}` | Returns `sections` + `raw` (backup) |
| Direct `.txt` edit of a single field | `update_page_field {page_id, field, value}` | Backup created automatically |
| Direct `.txt` edit of site.txt field | `update_site_field {field, value}` | Backup created. May require Panel approval. |
| `builder-cli append-section ...` | `append_section {page_id, section}` | UUIDs auto-filled |
| `builder-cli update-builder ...` | `update_builder {page_id, sections}` | Full replace, backup created |
| `builder-cli create-page ...` | `create_page {slug, title, parent?, template?}` | Creates draft (unlisted) |
| `builder-cli upload-asset ...` | `upload_asset {page_id, filename, data_base64\|url}` | Small files inline as base64; larger via URL |

**For surgical edits to text-inside-a-block (e.g. change one heading):**
Local: direct Edit on the `.txt`. Live: `get_builder` → modify the section JSON in memory → `update_builder` (with full sections array). There is no "edit-single-block-in-place" tool — you replace the whole builder or append a new section.

---

## Standard workflow on Live

```
1. GROUND
   - list_pages → which pages exist
   - get_site   → current theme colors, nav, typo
   - (Skip list_blocks — KB has them)

2. CONCEPT (if brief vague)
   - Same as local: present concept, get approval

3. EXECUTE
   - For each change:
     - Read current state via get_page / get_builder (= backup baseline)
     - Plan diff in memory
     - Call appropriate update_*/append_*/create_* tool
     - If tool returns "pending approval" → tell user "Waiting for Panel approval"
     - If approved → continue; if rejected/timed-out → stop and report

4. VERIFY (on Live URL)
   - Chrome DevTools MCP: navigate to live URL of changed page
   - Full-page screenshot
   - Console check (any new errors?)
   - design:design-critique on the live screenshot
   - Report with live URL, screenshot, and summary
```

---

## Approval-aware writes

Some MCP write tools may return a result like:
```json
{
  "content": [{ "type": "text", "text": "User rejected the operation in the Panel." }],
  "isError": true
}
```
or:
```json
{
  "content": [{ "type": "text", "text": "Approval timed out (no Panel response within 60 seconds)." }],
  "isError": true
}
```

When this happens:
- **Do not** retry automatically — the user actively declined or wasn't watching.
- Report to the user, briefly explain what you were trying to do, and ask whether to retry.
- If retrying, narrow the change to the smallest possible diff so the next approval is easier to grant quickly.

---

## Rollback

Every write tool returns `backup_path` (a filename under `content/.mcp/backups/` on the server). To roll back:

1. There's no direct "restore from backup" MCP tool in the current plugin version. You have to:
   - Read your local copy of the page's state from BEFORE the write (you saved `raw` from get_builder, didn't you?)
   - Call `update_builder` with the previous `sections` array

→ **Lesson:** always save the `raw` from `get_builder` to a local `.tmp` file before destructive writes. Then a rollback is one `update_builder` call away.

---

## Custom CSS / JS on Live

The same fields exist:
- `update_page_field {page_id, field: "page_custom_css", value: "..."}` + toggle on
- `update_site_field {field: "custom_css", value: "..."}` + `css_toggle: true`

But: writing to `custom_css` site-wide affects every visitor. Use **page-specific** custom_css whenever possible. Comment your code:

```css
/* ============================================================
   Live MCP edit — 2026-05-19
   Reason: gentle button float (block options didn't have it)
   Added by: Jannes via magpie-manager + MCP
   ============================================================ */
.about-cta .btn {
  animation: gentle-float 3.5s ease-in-out infinite;
}
```

The next person opening Panel will read this and know what it is.

---

## When NOT to use Live MCP

- **Schema migrations / theme code changes** → out of scope; live MCP only edits content.
- **Database / config.php / Kirby internals** → not exposed via MCP; ask user to handle manually.
- **Mass-import of 100s of pages/files** → MCP works but is slow per-call; user can do via Panel + drag-and-drop.

---

## Connection troubleshooting

| Symptom | Likely cause |
|---|---|
| `ip_not_allowed` from any tool | Your IP changed; user must update allowlist in Panel |
| `token_expired` | Token lifetime ran out; user generates a new one |
| `device_inactive` | Device auto-suspended (>24h idle); user re-pairs |
| `missing_token` | Token isn't being sent — check `.mcp.json` / `claude mcp list` |
| Endpoint returns 404 | Plugin disabled (kill-switch) or no tokens exist; user reactivates in Panel |
| 429 with Retry-After | Rate limited; back off and try later |
| `ip_blocked` | Too many auth fails from your IP; 1h cooldown |

In all cases: report to user, don't keep retrying.
