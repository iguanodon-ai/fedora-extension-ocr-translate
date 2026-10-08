#!/usr/bin/env bash
# One-shot setup for the clipboard OCR + translate tool.
#
# This installs system packages (needs sudo), syncs the Python environment
# with uv, and pre-downloads the offline Argos translation models so the
# first real run is fully offline.
#
# Re-run safe (idempotent-ish). Review before running.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

echo "==> Installing system dependencies (dnf, needs sudo)"
# tesseract + langpacks for OCR, wl-clipboard for Wayland clipboard,
# libnotify for notify-send, kdialog ships with Plasma (kdialog pkg name).
sudo dnf install -y \
    tesseract \
    tesseract-langpack-eng \
    tesseract-langpack-ara \
    wl-clipboard \
    libnotify \
    kdialog

echo "==> Creating/updating the Python environment (uv, Python 3.12)"
uv python install 3.12
uv sync

echo "==> Pre-downloading Argos Translate models (offline MT)"
# Downloads and installs the language pairs we care about. Add more pairs by
# editing the PAIRS array below (source target). "en" is the target.
PAIRS=(
    "ar en"   # Arabic  -> English
    "fa en"   # Farsi   -> English
)

for pair in "${PAIRS[@]}"; do
    set -- $pair
    FROM="$1"; TO="$2"
    echo "    - ${FROM} -> ${TO}"
    uv run python - "$FROM" "$TO" <<'PY'
import sys
import argostranslate.package as pkg

from_code, to_code = sys.argv[1], sys.argv[2]
pkg.update_package_index()
available = pkg.get_available_packages()
match = next(
    (p for p in available if p.from_code == from_code and p.to_code == to_code),
    None,
)
if match is None:
    print(f"      (no package available for {from_code}->{to_code}, skipping)")
    sys.exit(0)

installed = {
    (p.from_code, p.to_code) for p in pkg.get_installed_packages()
}
if (from_code, to_code) in installed:
    print("      already installed")
    sys.exit(0)

path = match.download()
pkg.install_from_path(path)
print("      installed")
PY
done

echo
echo "==> Done."
echo "Test it:  take a screenshot to the clipboard, then run:"
echo "    $SCRIPT_DIR/ocr-translate.sh"
echo
echo "Then bind $SCRIPT_DIR/ocr-translate.sh to a global shortcut:"
echo "  System Settings -> Shortcuts -> Add Command/URL  (see README.md)"
