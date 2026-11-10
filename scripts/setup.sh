#!/usr/bin/env bash
# setup.sh — Powerhouse setup for macOS/Linux.
# Renders opencode.json from config/opencode.json.tpl, copies jsonc files and all
# skills into the OpenCode config dir, and installs the pinned clipy-mcp package.
# Usage: bash scripts/setup.sh [--skip-install]
set -euo pipefail

# 1) Prerequisites FIRST — before any file write
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo 'Node.js >= 20 with npm is required' >&2
    exit 1
fi

# 2) Repo root (this script lives in <repo>/scripts)
repo="$(cd "$(dirname "$0")/.." && pwd)"

# 3) Substitution values
home_value="$HOME"
tmp_value="${TMPDIR:-/tmp}"
clipy_entry="$repo/clipy-mcp/node_modules/@clipy/mcp/dist/index.js"
videowizard_dir="${VIDEOWIZARD_DIR:-$HOME/VideoWizard}"
figma_server="${FIGMA_SERVER:-$HOME/tools/cursor-talk-to-figma-mcp/dist/server.js}"
cfg_dir="${OPENCODE_CFG_DIR:-$HOME/.config/opencode}"
skip_install=0
for arg in "$@"; do
    case "$arg" in
        --skip-install) skip_install=1 ;;
    esac
done

# 5) Backup every overwrite target once per run (unique dir, never merged)
if [ -d "$cfg_dir" ]; then
    present=()
    for item in opencode.json opencode-mem.jsonc dcp.jsonc skills; do
        if [ -e "$cfg_dir/$item" ]; then present+=("$item"); fi
    done
    if [ "${#present[@]}" -gt 0 ]; then
        stamp="$(date +%Y%m%d-%H%M%S)"
        backup="$cfg_dir/backup-$stamp"
        n=0
        while [ -e "$backup" ]; do n=$((n+1)); backup="$cfg_dir/backup-$stamp-$n"; done
        mkdir -p "$backup"
        for item in "${present[@]}"; do cp -R "$cfg_dir/$item" "$backup/$item"; done
        echo "Backup written to $backup"
    fi
fi

# 6) Render template via the shared JSON-safe renderer
mkdir -p "$cfg_dir"
node "$repo/scripts/render-config.js" forward "$repo/config/opencode.json.tpl" "$cfg_dir/opencode.json" \
    "HOME=$home_value" "TMP=$tmp_value" "CLIPY_MCP_ENTRY=$clipy_entry" "VIDEOWIZARD_DIR=$videowizard_dir" "FIGMA_SERVER=$figma_server"

# 7) jsonc files 1:1
cp -f "$repo/config/opencode-mem.jsonc" "$cfg_dir/opencode-mem.jsonc"
cp -f "$repo/config/dcp.jsonc" "$cfg_dir/dcp.jsonc"

# 8) Skills
mkdir -p "$cfg_dir/skills"
for d in "$repo"/skills/*/; do
    name="$(basename "$d")"
    rm -rf "$cfg_dir/skills/$name"
    cp -R "$d" "$cfg_dir/skills/$name"
done

# 9) Pinned clipy-mcp install
if [ "$skip_install" -eq 0 ]; then
    (cd "$repo/clipy-mcp" && npm ci)
fi

# 10) Manual steps
echo ''
echo 'Setup done — manual steps remaining:'
echo '  - Provider login: open OpenCode and sign in to your provider'
echo '  - Clipy login: npx -y @clipy/cli@latest login'
echo '  - MCP OAuth (if needed): use /mcps in OpenCode'
