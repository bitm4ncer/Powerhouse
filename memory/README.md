# Memory (empty by design)

Powerhouse ships **no personal memories**. This directory is a placeholder so
the snapshot and verify scripts have a stable location.

`memory/export.json` and `memory/global-rules.json` are listed in
`.gitignore`. Never commit them.

## Use your own memory

1. Install the `opencode-mem` plugin (already in `config/opencode.json.tpl`).
2. Ask OpenCode to export your project memory to `memory/export.json`.
3. Optionally add global rules and profile data to
   `memory/global-rules.json`.
4. Run `scripts/snapshot.*` on your maintained machine to refresh the export;
   `scripts/verify.*` warns when it is older than seven days.

The export contains project paths, session identifiers, and notes. Treat it as
private data.
