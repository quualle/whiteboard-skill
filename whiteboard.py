#!/usr/bin/env python3
"""
=============================================================================
WHITEBOARD / NANO-BANANA CLI (Google Gemini Image Generation)
=============================================================================

Erzeugt Whiteboard-artige Diagramme aus Text-Prompts via
gemini-3-pro-image-preview (Nano Banana Pro) bzw. dessen Flash-Variante.

VERWENDUNG:
-----------
    whiteboard "Drei Boxen: Website -> Formular -> Datenbank"
    echo "Drei Boxen: A, B, C" | whiteboard
    cat /tmp/prompt.md | nano-banana
    whiteboard --fast "quick skizze"

OPTIONEN:
---------
    --fast         Nano Banana 2 (Flash, schneller, weniger reasoning)
    --aspect       Seitenverhältnis: 1:1 (default), 16:9, 9:16, 4:3, 3:4
    --size         Auflösung: 1K (default), 2K, 4K
    --style        Prompt-Stil: whiteboard (default), sketch, raw
    --out          Output-Verzeichnis (default: ~/Pictures/whiteboards/ oder $WHITEBOARD_OUT)
    --no-open      PNG nicht automatisch öffnen

STDOUT: absoluter Pfad zur PNG-Datei (parse-freundlich für aufrufende Agents)
STDERR: Fortschritts-/Fehlermeldungen
EXIT:   0 bei Erfolg, !=0 bei Fehler
=============================================================================
"""

import sys
import os
import json
import base64
import argparse
import subprocess
import ssl
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

MODEL_PRO = "gemini-3-pro-image-preview"
MODEL_FAST = "gemini-3.1-flash-image-preview"
ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

OUT_DIR_DEFAULT = Path(os.environ.get("WHITEBOARD_OUT", Path.home() / "Pictures" / "whiteboards"))
ENV_PATH = Path(os.environ.get("WHITEBOARD_ENV", Path.home() / ".whiteboard.env"))

STYLE_TEMPLATES = {
    "whiteboard": (
        "Hand-drawn whiteboard sketch on clean white background. "
        "Black marker with occasional blue and red accent strokes. "
        "Architectural diagram style with labeled boxes, arrows, and swimlanes. "
        "Clean, schematic, clearly readable. Handwritten labels in German. "
        "No photorealism, no shading, no 3D — purely schematic. "
        "Subject: {prompt}"
    ),
    "sketch": (
        "Loose hand-drawn pencil sketch, minimal color, notebook-style doodle "
        "with clear labels in German handwriting. Subject: {prompt}"
    ),
    "raw": "{prompt}",
}


def log(msg: str) -> None:
    print(f"[WB] {msg}", file=sys.stderr)


def load_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    if not ENV_PATH.exists():
        log(f"Fehler: {ENV_PATH} nicht gefunden und GEMINI_API_KEY nicht gesetzt.")
        sys.exit(2)
    for raw in ENV_PATH.read_text().splitlines():
        line = raw.strip()
        if line.startswith("GEMINI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    log("Fehler: GEMINI_API_KEY nicht in .env gefunden.")
    sys.exit(2)


def slugify(text: str, maxlen: int = 40) -> str:
    text = text.lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:maxlen].rstrip("-")) or "whiteboard"


def build_payload(prompt: str, style: str, aspect: str, size: str) -> dict:
    wrapped = STYLE_TEMPLATES[style].format(prompt=prompt.strip())
    return {
        "contents": [{"parts": [{"text": wrapped}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect, "imageSize": size},
        },
    }


def call_gemini(payload: dict, model: str, api_key: str, timeout: int) -> dict:
    url = ENDPOINT_TMPL.format(model=model)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        log(f"HTTP {e.code} {e.reason}")
        log(f"Details: {body[:600]}")
        sys.exit(3)
    except urllib.error.URLError as e:
        log(f"Netzwerk-Fehler: {e.reason}")
        sys.exit(3)


def extract_image_bytes(resp: dict) -> bytes:
    candidates = resp.get("candidates") or []
    if not candidates:
        log("Keine candidates in der Antwort.")
        log(f"Response-Keys: {list(resp.keys())}")
        sys.exit(4)
    parts = (candidates[0].get("content") or {}).get("parts") or []
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    log("Kein Bild in der Antwort gefunden (möglicherweise Safety-Filter).")
    log(f"Antwort-Parts: {json.dumps(parts)[:400]}")
    sys.exit(4)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Whiteboard-Bild aus Text-Prompt via Gemini Nano Banana Pro.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="*", help="Prompt-Text (oder via stdin).")
    parser.add_argument("--fast", action="store_true", help="Flash-Modell statt Pro.")
    parser.add_argument("--aspect", default="1:1",
                        choices=["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"])
    parser.add_argument("--size", default="1K", choices=["512", "1K", "2K", "4K"])
    parser.add_argument("--style", default="whiteboard", choices=list(STYLE_TEMPLATES.keys()))
    parser.add_argument("--out", default=str(OUT_DIR_DEFAULT))
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)

    args = parser.parse_args()

    if args.prompt:
        prompt_text = " ".join(args.prompt)
    elif not sys.stdin.isatty():
        prompt_text = sys.stdin.read()
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)

    prompt_text = prompt_text.strip()
    if not prompt_text:
        log("Fehler: Leerer Prompt.")
        sys.exit(1)

    api_key = load_api_key()
    model = MODEL_FAST if args.fast else MODEL_PRO

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    first_line = prompt_text.splitlines()[0]
    out_path = out_dir / f"{ts}_{slugify(first_line)}.png"

    log(f"Modell: {model}  Aspect: {args.aspect}  Size: {args.size}  Style: {args.style}")
    log(f"Prompt ({len(prompt_text)} Zeichen): {first_line[:80]}{'…' if len(first_line) > 80 else ''}")
    log("Generiere …")

    payload = build_payload(prompt_text, args.style, args.aspect, args.size)
    resp = call_gemini(payload, model, api_key, args.timeout)
    image_bytes = extract_image_bytes(resp)

    out_path.write_bytes(image_bytes)
    log(f"Fertig: {out_path} ({len(image_bytes) // 1024} KB)")

    if not args.no_open:
        opener = {"darwin": ["open"], "win32": ["cmd", "/c", "start", ""]}.get(sys.platform, ["xdg-open"])
        try:
            subprocess.run(opener + [str(out_path)], check=False)
        except FileNotFoundError:
            pass

    print(str(out_path))


if __name__ == "__main__":
    main()
