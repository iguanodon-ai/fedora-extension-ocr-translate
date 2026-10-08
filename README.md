# OCR Translate (Fedora KDE)

Clipboard screenshot → OCR → offline translation to English, triggered by a
global shortcut. Fully local; no cloud, no network at runtime (after the
one-time model download).

## What it does

1. You take a screenshot that lands on the clipboard (Spectacle "Copy to
   clipboard", or `Print` configured to copy).
2. You press a global shortcut.
3. The tool reads the image from the clipboard, runs **Tesseract** OCR
   (`eng+ara` by default), **auto-detects** the text language, and translates
   it to English with **Argos Translate** (offline). English text is passed
   through unchanged.
4. The result is copied to the clipboard and shown in a KDE notification. For
   long text, a `kdialog` window shows the original and the translation.

## Stack (and why)

- **Tesseract** – fast, CPU-only, already on your system; good for printed text.
- **Argos Translate** – offline neural MT, CPU-only (ships CPU torch).
- **langdetect** – picks the source language so the right Argos model is used.
- **wl-clipboard / notify-send / kdialog** – Wayland/KDE integration.
- **uv** – isolated Python 3.12 env (system Python 3.14 is too new for the ML
  wheels).

Works on an AMD Phoenix1 iGPU (no CUDA), so the whole pipeline is
CPU-only by design. Typical run is a second or two.

## Install

```bash
./install.sh
```

This installs the system packages (via `sudo dnf`), creates the uv environment,
and pre-downloads the Argos models (`ar→en`, `fa→en`). Review the script first.

## Test it manually

```bash
# 1. Screenshot to clipboard (Spectacle -> Copy to clipboard), or:
wl-copy --type image/png < some_image.png

# 2. Run:
./ocr-translate.sh
```

The translated (or OCRed) text is now on your clipboard. 

## Bind a global shortcut (Plasma 6)

The reliable path on Plasma 6.7 is the GUI:

1. System Settings → **Keyboard** → **Shortcuts** → **Add New** →
   **Command or Script**.
2. Command: the **absolute** path to `ocr-translate.sh` in your clone (KDE
   won't expand `~` or relative paths). Get it by running this from the repo
   root:

   ```bash
   echo "$(pwd)/ocr-translate.sh"
   ```

   e.g. `/home/youruser/fedora-extension-ocr-translate/ocr-translate.sh`.
3. Click the shortcut field and press your key, e.g. **Meta+Shift+T**.
4. Apply.

Now: screenshot → copy to clipboard → press the shortcut.

### Making `Print` copy to clipboard

System Settings → Keyboard → Shortcuts → Spectacle → set *"Capture Rectangular
Region"* (or your preferred mode) and in Spectacle's settings enable
*"Copy image to clipboard"* / "automatically copy". Then your normal screenshot
flow feeds this tool directly.

## Configuration

Environment variables (set them in the shortcut command if you want to override):

| Variable                      | Default   | Meaning                                   |
| ----------------------------- | --------- | ----------------------------------------- |
| `OCR_TRANSLATE_LANGS`         | `eng+ara` | Tesseract OCR candidate languages         |
| `OCR_TRANSLATE_TARGET`        | `en`      | Translation target language               |
| `OCR_TRANSLATE_POPUP_CHARS`   | `280`     | Show the kdialog popup above this length  |

Example shortcut command with Farsi added to OCR:

```bash
OCR_TRANSLATE_LANGS=eng+ara+fas /path/to/fedora-extension-ocr-translate/ocr-translate.sh
```

## Adding languages

**OCR language** (so Tesseract can read a new script):

```bash
sudo dnf install tesseract-langpack-fas   # Farsi, for example
```
then add it to `OCR_TRANSLATE_LANGS` (e.g. `eng+ara+fas`).

**Translation model** (so Argos can translate a new source language):

Edit the `PAIRS` array in `install.sh` and re-run it, or install ad hoc:

```bash
uv run python - <<'PY'
import argostranslate.package as pkg
pkg.update_package_index()
p = next(x for x in pkg.get_available_packages()
         if x.from_code == "fa" and x.to_code == "en")
pkg.install_from_path(p.download())
PY
```

## Troubleshooting

- **"No image on the clipboard"** – your screenshot wasn't copied as an image.
  Use Spectacle's "Copy to clipboard".
- **No translation, only OCR** – no Argos model for the detected language; add
  the pair (see above). The original text is still copied.
- **Wrong OCR for a script** – install the matching `tesseract-langpack-*` and
  add it to `OCR_TRANSLATE_LANGS`.
- **Nothing happens on the shortcut** – test `./ocr-translate.sh` in a terminal
  first to see errors.

## Notes / limitations

- Tesseract is weaker on noisy, low-contrast, or handwritten text. If accuracy
  is poor, we can swap the OCR stage for RapidOCR/PaddleOCR (ONNX, CPU). The pipeline is modular (`ocr()` in `ocr_translate.py`).
- Language auto-detection runs on the OCRed text; very short strings can be
  mis-detected.
