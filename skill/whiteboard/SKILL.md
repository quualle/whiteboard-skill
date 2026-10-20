---
name: whiteboard
description: Generiert Whiteboard-Bilder, Skizzen und Diagramme aus Text-Prompts via Google Gemini (Nano Banana Pro). MUSS verwendet werden, wenn der User sagt "zeichne", "skizziere", "whiteboard", "mal mir", "visualisiere", "als Diagramm", "als Bild", "nano banana" oder ähnliches. Das Tool ist eine CLI (`whiteboard`), die PNGs in ~/Pictures/whiteboards/ ablegt und automatisch öffnet. NIEMALS eigenes Python/curl/Gemini-SDK-Script schreiben — IMMER das CLI nutzen.
---

# Whiteboard — Bildgenerierung via CLI

## Harte Regeln

1. **Nie** ein eigenes Script schreiben, um Gemini direkt aufzurufen.
2. **Nie** `curl` gegen `generativelanguage.googleapis.com` bauen.
3. **Immer** das CLI `whiteboard` über das Bash-Tool aufrufen.
4. Kein `export GEMINI_API_KEY=...` nötig: Das CLI liest `~/.whiteboard.env` selbst.

## Aufruf

```bash
whiteboard "Konkrete Beschreibung: Boxen, Pfeile, Labels, Gruppierungen benennen"
whiteboard --aspect 16:9 --size 2K "Querformat-Tafelbild ..."
cat prompt.md | whiteboard --aspect 16:9
whiteboard --fast "schnelle Skizze"        # Flash-Modell, schneller und billiger
whiteboard --style sketch "..."            # Bleistift-Look
whiteboard --style raw "..."               # Prompt 1:1 ohne Whiteboard-Rahmen
whiteboard --no-open "..."                 # Bild nicht automatisch öffnen
```

- `--aspect`: `1:1` (Standard), `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`
- `--size`: `512`, `1K` (Standard), `2K`, `4K`

Das Pro-Modell braucht 30–90 Sekunden. Im Bash-Tool `timeout: 300000` setzen.

## Ausgabe

- Stdout = nur der absolute PNG-Pfad. Fortschritt läuft über stderr.
- Nach der Generierung das PNG mit dem Read-Tool ansehen und die Qualität prüfen (Rechtschreibung, Lesbarkeit). Bei Fehlern den Prompt präzisieren und neu erzeugen.

## Gute Prompts

- **Gut:** „Drei Zonen von links nach rechts. Links Box ‚Claude Code‘ mit Laptop, Pfeil ‚push‘ zu Box ‚GitHub‘ …“
- **Mäßig:** „Zeichne meine Pipeline“

Je konkreter Boxen, Richtungen, Beschriftungen und Farben beschrieben sind, desto besser das Bild. Deutsche Beschriftungen funktionieren.

## Fehler

- **HTTP 429:** Kontingent oder Abrechnung bei Google prüfen. Nicht still wiederholen.
- **HTTP 400/403:** Prompt umformulieren (Sicherheitsfilter) oder API-Key prüfen.
- **GEMINI_API_KEY fehlt:** Den User bitten, `~/.whiteboard.env` anzulegen (siehe README).
