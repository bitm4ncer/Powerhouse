#!/usr/bin/env bash
# snapshot.sh — Sync this machine's live OpenCode setup back into the repository.
# Usage: OPENCODE_CFG_DIR=~/.config/opencode bash scripts/snapshot.sh [--dry-run]
set -euo pipefail

cfg="${OPENCODE_CFG_DIR:-$HOME/.config/opencode}"
dry=""
for arg in "$@"; do
  case "$arg" in
    --dry-run|-n) dry="1" ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

repo="$(cd "$(dirname "$0")/.." && pwd)"
renderer="$repo/scripts/render-config.js"
live="$cfg/opencode.json"
[ -f "$live" ] || { echo "No opencode.json at $live" >&2; exit 1; }
tpl_path="$repo/config/opencode.json.tpl"

render() { # $1=in $2=out (reverse-render)
  node "$renderer" reverse "$1" "$2" \
    "CLIPY_MCP_ENTRY=$repo/clipy-mcp/node_modules/@clipy/mcp/dist/index.js" \
    "CLIPY_MCP_ENTRY=$HOME/.clipy-mcp/node_modules/@clipy/mcp/dist/index.js" \
    "TMP=${TMPDIR:-/tmp}" \
    "HOME=$HOME" \
    "VIDEOWIZARD_DIR=$HOME/VideoWizard"
}

scan_secrets() { # reads NUL-separated paths on stdin; prints secret-like offenders
  local f
  while IFS= read -r -d '' f; do
    case "$f" in
      *service.json*|*.auth-token|*.db|*.db/*|*node_modules*) printf '%s\n' "$f" ;;
    esac
  done
}

assert_no_secrets() {
  local off
  off="$(
    {
      git -C "$repo" diff --cached --name-only -z
      git -C "$repo" status --porcelain -z | while IFS= read -r -d '' e; do printf '%s\0' "${e:3}"; done
    } | scan_secrets
  )"
  if [ -n "$off" ]; then
    echo "SECRET GUARD: refusing to snapshot the following paths:" >&2
    printf '%s\n' "$off" >&2
    exit 1
  fi
}

# --- 1. Guard first: never snapshot secrets, even already-staged ones --------
assert_no_secrets

# --- 2. Template: reverse-render live config (dry: compare only) -------------
if [ -n "$dry" ]; then
  tmpout="$(mktemp "${TMPDIR:-/tmp}/powerhouse-snapshot-check.XXXXXX")"
  render "$live" "$tmpout"
  if [ -f "$tpl_path" ] && cmp -s "$tmpout" "$tpl_path"; then
    echo 'template: unchanged'
  else
    echo 'template: would update'
  fi
  rm -f "$tmpout"
else
  render "$live" "$tpl_path"
  echo "Rendered template: $tpl_path"
fi

# --- 3. Skills union: .config > .claude > .agents; first occurrence wins -----
chosen=" "
for src in "$cfg/skills" "$HOME/.claude/skills" "$HOME/.agents/skills"; do
  [ -d "$src" ] || continue
  for dir in "$src"/*/; do
    [ -d "$dir" ] || continue
    name="$(basename "$dir")"
    case "$chosen" in
      *" $name "*) continue ;;
    esac
    chosen="$chosen$name "
    if [ -n "$dry" ]; then
      if [ ! -d "$repo/skills/$name" ]; then
        echo "skills/$name would add"
      elif ! diff -rq "$dir" "$repo/skills/$name" >/dev/null 2>&1; then
        echo "skills/$name would update"
      fi
    else
      rm -rf "$repo/skills/$name"
      cp -R "$dir" "$repo/skills/$name"
    fi
  done
done
if [ -z "$dry" ]; then
  echo "Synced skills:$chosen"
fi
for dir in "$repo/skills"/*/; do
  [ -d "$dir" ] || continue
  name="$(basename "$dir")"
  case "$chosen" in
    *" $name "*) ;;
    *) echo "stale (not deleted): $name" ;;
  esac
done

# --- 4. jsonc 1:1 (dry: compare only) ----------------------------------------
for f in opencode-mem.jsonc dcp.jsonc; do
  [ -f "$cfg/$f" ] || continue
  if [ -n "$dry" ]; then
    if [ ! -f "$repo/config/$f" ] || ! cmp -s "$cfg/$f" "$repo/config/$f"; then
      echo "config/$f would update"
    fi
  else
    cp -f "$cfg/$f" "$repo/config/$f"
  fi
done

# --- 5. Memory export reminder (missing or older than 7 days) ----------------
mem="$repo/memory/export.json"
if [ ! -f "$mem" ] || [ -n "$(find "$mem" -mtime +7 -print -quit 2>/dev/null)" ]; then
  echo "MEMORY: Run in OpenCode: memory export to $mem (missing or older than 7 days)"
fi

# --- 6. Dry run stops here (no repo writes happened) -------------------------
if [ -n "$dry" ]; then
  echo 'DRY RUN - no files were written'
  git -C "$repo" status --short
  exit 0
fi

# --- 7. Stage, re-check guard, then commit + push ----------------------------
git -C "$repo" add -A
off="$(git -C "$repo" diff --cached --name-only -z | scan_secrets)"
if [ -n "$off" ]; then
  git -C "$repo" reset -q
  echo "SECRET GUARD: refusing to commit the following paths:" >&2
  printf '%s\n' "$off" >&2
  exit 1
fi
rc=0
git -C "$repo" diff --cached --quiet || rc=$?
case "$rc" in
  0) echo 'nothing to snapshot'; exit 0 ;;
  1) : ;;
  *) echo "git diff --cached --quiet failed (exit $rc)" >&2; exit 1 ;;
esac
git -C "$repo" commit -m "snapshot: $(date '+%Y-%m-%d %H:%M')"
git -C "$repo" push
echo 'snapshot pushed'
