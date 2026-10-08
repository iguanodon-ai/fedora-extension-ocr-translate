#!/usr/bin/env python3
"""Clipboard OCR + offline translation for Fedora KDE (Wayland).

Flow:
  1. Read an image from the Wayland clipboard (via `wl-paste`).
  2. Run Tesseract OCR over it (candidate langs, default eng+ara).
  3. Detect the text language and translate it to English with Argos Translate
     (offline). If the text is already English, skip translation.
  4. Copy the result to the clipboard (`wl-copy`), show a KDE notification
     (`notify-send`), and open a `kdialog` text box when the text is long.

This script is intended to be invoked by a KDE global shortcut. It never
raises to the user as a traceback: all failures become notifications.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# --- Configuration (edit freely) ------------------------------------------

# Tesseract OCR candidate languages. These must be installed as
# tesseract-langpack-* packages. "+" joins multiple scripts in one pass.
OCR_LANGS = os.environ.get("OCR_TRANSLATE_LANGS", "eng+ara")

# Target language for translation.
TARGET_LANG = os.environ.get("OCR_TRANSLATE_TARGET", "en")

# Show the kdialog popup window when the (combined) text exceeds this length.
LONG_TEXT_THRESHOLD = int(os.environ.get("OCR_TRANSLATE_POPUP_CHARS", "280"))

APP_NAME = "OCR Translate"


# --- Small helpers ---------------------------------------------------------


def _run(cmd: list[str], *, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        check=False,
    )


def notify(title: str, body: str = "", *, urgency: str = "normal") -> None:
    """Best-effort KDE/desktop notification."""
    if shutil.which("notify-send"):
        _run(
            [
                "notify-send",
                "--app-name",
                APP_NAME,
                "--urgency",
                urgency,
                "--icon",
                "edit-paste",
                title,
                body,
            ]
        )
    else:  # fallback so the user still sees *something*
        print(f"{title}: {body}", file=sys.stderr)


def die(message: str) -> "NoReturn":  # type: ignore[name-defined]
    notify(f"{APP_NAME}: failed", message, urgency="critical")
    sys.exit(1)


# --- Pipeline steps --------------------------------------------------------


def read_clipboard_image() -> bytes:
    """Return raw PNG bytes of the image on the clipboard, or exit."""
    if not shutil.which("wl-paste"):
        die("wl-paste not found. Install wl-clipboard.")

    # What MIME types are available on the clipboard right now?
    types = _run(["wl-paste", "--list-types"])
    available = types.stdout.decode("utf-8", "replace").split()

    image_type = None
    for preferred in ("image/png", "image/jpeg", "image/bmp", "image/tiff"):
        if preferred in available:
            image_type = preferred
            break
    if image_type is None:
        # Maybe there's an image type we didn't list explicitly.
        image_type = next((t for t in available if t.startswith("image/")), None)

    if image_type is None:
        die(
            "No image on the clipboard.\n"
            "Take a screenshot that copies to the clipboard first "
            "(Spectacle: 'Copy to clipboard')."
        )

    result = _run(["wl-paste", "--type", image_type])
    if result.returncode != 0 or not result.stdout:
        die("Could not read the image from the clipboard.")
    return result.stdout


def ocr(image_bytes: bytes) -> str:
    """Run Tesseract over the image bytes and return extracted text."""
    if not shutil.which("tesseract"):
        die("tesseract not found. Install tesseract + langpacks.")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        # `tesseract <img> stdout -l <langs>` prints recognized text to stdout.
        result = _run(["tesseract", tmp_path, "stdout", "-l", OCR_LANGS])
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        die(f"Tesseract failed:\n{stderr}")

    text = result.stdout.decode("utf-8", "replace").strip()
    if not text:
        die("OCR found no text in the image.")
    return text


@dataclass
class Translation:
    source_lang: str
    text: str
    translated: bool


def translate(text: str) -> Translation:
    """Detect source language and translate to TARGET_LANG via Argos."""
    try:
        from langdetect import detect  # type: ignore
    except Exception:  # pragma: no cover - import guard
        detect = None  # type: ignore

    source_lang = TARGET_LANG
    if detect is not None:
        try:
            source_lang = detect(text)
        except Exception:
            source_lang = "unknown"

    # Normalise a few langdetect codes to Argos codes.
    normalise = {"zh-cn": "zh", "zh-tw": "zh"}
    source_lang = normalise.get(source_lang, source_lang)

    if source_lang == TARGET_LANG:
        return Translation(source_lang=source_lang, text=text, translated=False)

    try:
        import argostranslate.translate as at  # type: ignore
    except Exception:
        notify(
            f"{APP_NAME}: OCR only",
            "Argos Translate not available; copied original text.",
        )
        return Translation(source_lang=source_lang, text=text, translated=False)

    try:
        translated_text = at.translate(text, source_lang, TARGET_LANG)
    except Exception:
        # No installed model for this pair, or runtime error.
        notify(
            f"{APP_NAME}: no model",
            f"No {source_lang}->{TARGET_LANG} model installed; copied original.",
        )
        return Translation(source_lang=source_lang, text=text, translated=False)

    if not translated_text or translated_text.strip() == text.strip():
        return Translation(source_lang=source_lang, text=text, translated=False)

    return Translation(source_lang=source_lang, text=translated_text, translated=True)


def deliver(original: str, result: Translation) -> None:
    """Copy to clipboard, notify, and optionally show a popup window."""
    output = result.text

    if shutil.which("wl-copy"):
        _run(["wl-copy"], stdin=output.encode("utf-8"))

    if result.translated:
        summary = f"Translated {result.source_lang} -> {TARGET_LANG} (copied)"
    else:
        summary = f"OCR text copied (detected: {result.source_lang})"

    # Short preview in the notification.
    preview = output if len(output) <= 160 else output[:157] + "..."
    notify(summary, preview)

    combined_len = len(original) + len(output)
    if combined_len >= LONG_TEXT_THRESHOLD and shutil.which("kdialog"):
        if result.translated:
            body = (
                f"=== Original ({result.source_lang}) ===\n{original}\n\n"
                f"=== Translation ({TARGET_LANG}) ===\n{output}"
            )
        else:
            body = output
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        try:
            _run(["kdialog", "--title", APP_NAME, "--textbox", tmp_path, "600", "400"])
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def main() -> None:
    image_bytes = read_clipboard_image()
    original = ocr(image_bytes)
    result = translate(original)
    deliver(original, result)


if __name__ == "__main__":
    main()
