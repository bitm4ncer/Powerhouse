#!/usr/bin/env bash
# Powerhouse installer - macOS / Linux.
set -euo pipefail
exec bash "$(cd "$(dirname "$0")" && pwd)/scripts/setup.sh" "$@"
