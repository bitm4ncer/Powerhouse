#!/usr/bin/env bash
# Read-only verification of a restored OpenCode harness. Exit 0 = all checks pass.
set -u

cfg_dir="${OPENCODE_CFG_DIR:-$HOME/.config/opencode}"
fail=0

# 1. Rendered config exists and has no leftover template tokens
cfg="$cfg_dir/opencode.json"
if [ ! -f "$cfg" ]; then
    echo "[fail] config: $cfg not found"
    fail=1
elif grep -q '{{' "$cfg"; then
    echo "[fail] config: leftover {{...}} placeholder"
    fail=1
else
    echo "[ok] config: $cfg (no placeholders)"
fi

# 2. Rendered config parses as JSON (node check)
if [ -f "$cfg" ]; then
    if node -e "JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'))" "$cfg"; then
        echo "[ok] config: valid JSON"
    else
        echo "[fail] config: JSON parse failed"
        fail=1
    fi
fi

# 3. Skills: at least 8 folders
skills_dir="$cfg_dir/skills"
count=0
if [ -d "$skills_dir" ]; then
    count=$(find "$skills_dir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
fi
if [ "$count" -lt 8 ]; then
    echo "[fail] skills: $count found (< 8)"
    fail=1
else
    echo "[ok] skills: $count"
fi

# 4. Memory status line (export age + import hint)
repo="$(cd "$(dirname "$0")/.." && pwd)"
export_file="$repo/memory/export.json"
if [ -f "$export_file" ]; then
    if [ "$(find "$export_file" -mtime +7 2>/dev/null)" ]; then
        echo "[info] memory export: older than 7 days - refresh with snapshot on the maintained machine"
    else
        echo "[info] memory export: fresh (<= 7 days) - import with the memory tool (mode=import)"
    fi
else
    echo "[info] memory export: missing - run snapshot on the maintained machine"
fi

exit $fail
