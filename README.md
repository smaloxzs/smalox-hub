# Smalox Hub

Kostenlose Windows-App, die fünf Werkzeuge in einer `.exe` bündelt: **Dashboard** (To-Dos, Kalender, Projekte, Wunschliste, Second Brain, Claude-Chat, Dropbox), **Destille** (Links → To-Dos), **Deadswitch** (Deadlines mit Sperre), **Zeitblick** (Bildschirmzeit) und **Zeitschloss** (Chrome-Website-Blocker). Website mit Download: `docs/` (GitHub Pages).

## Bauen

```
pip install pyinstaller pywebview
python build_hub.py
```

Ergebnis: `dist/SmaloxHub.exe` (ca. 16 MB). `build_hub.py` kopiert die Apps aus `../marlons-dashboard`, `../destille`, `../deadswitch`, `../zeitblick`, `../zeitschloss` nach `build/apps` und lässt dabei alles Persönliche weg (`data/`, `.token`, Tests, Zeitblicks eigene `categories.json` → Stand aus Git). Findet es persönliche Spuren (`VERBOTEN`), bricht es ab.

## Wie die .exe funktioniert (`hub.py`)

- **Installer:** Erster Doppelklick kopiert sie nach `%LOCALAPPDATA%\SmaloxHub`, packt die Apps nach `apps\web-demos\…` aus, legt Desktop- und Startmenü-Symbol, Autostart (`HKCU\…\Run`, `--hintergrund`) und einen Eintrag unter „Apps“ (Deinstallieren) an. Neue Version drüber installieren behält alle `data/`-Ordner.
- **Starter:** startet Zeitblick, Destille, Deadswitch und den Dashboard-Server als eigene Prozesse und öffnet das Fenster (`fenster.py`, pywebview). Einstellungen (Name, Vault-Ordner) in `einstellungen.json`, beim ersten Start per Dialog abgefragt. Ohne eigenes Obsidian-Vault wird eine Vorlage `Second Brain` angelegt.
- **Python-Ersatz:** `SmaloxHub.exe <skript.py>` führt ein App-Skript aus. Die Apps starten sich gegenseitig über `sys.executable` (MCP-Server, Destille-Knopf, Fenster), dadurch läuft ihr Code unverändert in der .exe.
- Umgebung für die Apps: `HUB_NAME`, `HUB_TITEL`, `HUB_AUMID`, `HUB_START`, `HUB_ICON`, `HUB_WEBVIEW`, `VAULT_PFAD`, `SESSIONS_PFAD`, `*_PORT`, `DESTILLE_URL`, `DEADSWITCH_URL`. PyInstaller-Interna werden nicht an Kind-Prozesse vererbt (`sauberes_env`, sonst lädt pythonnet die falsche .NET-Laufzeit).
- Fehler landen in `%LOCALAPPDATA%\SmaloxHub\fehler.log`; `HUB_DEBUG=1` schreibt bei Hängern nach 25 s alle Threads in `haenger-*.log`.

## Testen ohne die eigene Installation zu stören

```
dist\SmaloxHub.exe --test %TEMP%\hubtest
```

Installiert in den Testordner, ohne Registry und Symbole, alle Ports +100 (8871…8876). Zeitblick beendet sich dabei selbst, wenn schon ein Zeitblick läuft (ein Tracker pro Nutzer).

## Grenzen

- Video-Auswertung (yt-dlp, faster-whisper) ist nicht enthalten (mehrere hundert MB); Destille liest dann Titel, Beschreibung und Seite.
- KI-Funktionen brauchen Claude Code (`claude`) mit Anmeldung auf dem jeweiligen PC.
- Die .exe ist nicht signiert, Windows SmartScreen warnt beim ersten Start.
- Chrome-Erweiterungen (Zeitschloss, Destille) werden entpackt aus `apps\web-demos\…` geladen.
