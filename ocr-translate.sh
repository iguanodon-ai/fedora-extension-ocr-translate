#!/usr/bin/env bash
# Stable launcher for the KDE global shortcut.
# Resolves its own directory so it works no matter the CWD, then runs the
# Python pipeline inside the uv-managed environment.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

exec uv run --project "$SCRIPT_DIR" python "$SCRIPT_DIR/ocr_translate.py" "$@"
