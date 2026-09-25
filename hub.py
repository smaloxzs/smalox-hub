"""
Smalox Hub - eine .exe fuer alles: Dashboard, Destille, Deadswitch, Zeitblick (+ Zeitschloss-Erweiterung).

Die .exe hat drei Rollen:
  1. Installer:  Doppelklick auf die heruntergeladene Datei kopiert sie nach %LOCALAPPDATA%\\SmaloxHub,
                 packt die Apps aus, legt Desktop-/Startmenue-Symbol, Autostart und einen Eintrag unter
                 "Apps & Features" an und startet den Hub.
  2. Starter:    startet die vier Dienste (jeweils eigener Prozess) und oeffnet das Dashboard-Fenster.
                 "--hintergrund" (Autostart) startet nur die Dienste.
  3. Python-Ersatz: "SmaloxHub.exe <skript.py> [args]" fuehrt ein App-Skript aus. Weil alle Apps sich
                 gegenseitig ueber sys.executable starten (MCP-Server, Destille-Knopf, Fenster), laeuft so
                 der unveraenderte Code der Apps auch in der .exe.
Weitere Schalter: "--deinstallieren", "--test <ordner>" (ohne Registry/Symbole, Ports +100; fuer Tests).

Persoenliche Daten sind nicht enthalten: Name und Second-Brain-Ordner fragt der erste Start ab
(ohne Vault wird ein leeres Second Brain als Vorlage angelegt). Nur Standardbibliothek + pywebview.
"""

import json
import os
import runpy
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

VERSION = "1.0.0"
TITEL = "Smalox Hub"
AUMID = "Smalox.Hub"
PORTS = {"zeitblick": 8771, "destille": 8773, "deadswitch": 8775, "dashboard": 8776}
DIENSTE = [  # (Name, Skript relativ zu apps/web-demos)
    ("zeitblick", "zeitblick/tracker.py"),
    ("destille", "destille/server.py"),
    ("deadswitch", "deadswitch/server.py"),
    ("dashboard", "marlons-dashboard/server.py"),
]
OHNE_FENSTER = getattr(subprocess, "CREATE_NO_WINDOW", 0)
GEFROREN = bool(getattr(sys, "frozen", False))

TEST = "--test" in sys.argv
if TEST:
    ZIEL = Path(sys.argv[sys.argv.index("--test") + 1]).resolve()
    PORTS = {k: v + 100 for k, v in PORTS.items()}
elif GEFROREN and (Path(sys.executable).parent / "apps").is_dir():
    ZIEL = Path(sys.executable).resolve().parent  # die installierte .exe (auch Test-Kopien) kennt ihren Ordner selbst
else:
    ZIEL = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SmaloxHub"
EXE = ZIEL / "SmaloxHub.exe"
APPS = ZIEL / "apps"
WEB = APPS / "web-demos"
EINSTELLUNGEN = ZIEL / "einstellungen.json"
ICON = APPS / "smalox-hub.ico"


# ───────────────────────── Rolle 3: App-Skript ausfuehren ─────────────────────────

def skript_ausfuehren(skript, args):
    skript = Path(skript).resolve()
    sys.argv = [str(skript)] + args
    sys.path.insert(0, str(skript.parent))
    os.chdir(skript.parent)
    if skript.name == "tracker.py":
        sys.frozen = False  # Zeitblick soll sich hier NICHT selbst als Zeitblick.exe installieren
    if os.environ.get("HUB_DEBUG"):  # haengt etwas? Nach 25 s alle Threads ins Protokoll
        import faulthandler
        faulthandler.dump_traceback_later(25, file=open(ZIEL / f"haenger-{skript.stem}.log", "w"))
    try:
        runpy.run_path(str(skript), run_name="__main__")
    except SystemExit:
        raise
    except BaseException:  # ohne Konsole sieht man Fehler sonst nie
        import traceback
        ZIEL.mkdir(parents=True, exist_ok=True)
        with open(ZIEL / "fehler.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {skript.name}\n{traceback.format_exc()}\n")
        raise


# ───────────────────────── Hilfen ─────────────────────────

def port_offen(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def einstellungen_laden():
    try:
        return json.loads(EINSTELLUNGEN.read_text(encoding="utf-8-sig"))  # utf-8-sig: auch mit BOM (Editor)
    except (OSError, ValueError):
        return {}


def sauberes_env():
    """os.environ ohne PyInstaller-Interna (sonst erbt ein neu gestarteter Hub-Prozess falsche Einstellungen)."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONNET_RUNTIME" and not k.startswith(("_PYI", "_MEIPASS"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def umgebung(e):
    """Alles, was die Apps ueber Umgebungsvariablen einstellen (siehe quellen.py, fenster.py ...)."""
    env = sauberes_env()
    env.update({
        "HUB_NAME": e.get("name") or "Du", "HUB_TITEL": TITEL, "HUB_AUMID": AUMID,
        "HUB_INTERESSEN": e.get("interessen") or "eigene Projekte, Lernen, Selbstorganisation",
        "HUB_START": f'"{EXE if GEFROREN else sys.executable}"', "HUB_ICON": str(ICON),
        "HUB_WEBVIEW": str(ZIEL / "webview"),
        "VAULT_PFAD": e.get("vault") or str(ZIEL / "Second Brain"), "SESSIONS_PFAD": str(APPS),
        "ZEITBLICK_PORT": str(PORTS["zeitblick"]), "DESTILLE_PORT": str(PORTS["destille"]),
        "DEADSWITCH_PORT": str(PORTS["deadswitch"]), "DASHBOARD_PORT": str(PORTS["dashboard"]),
        "DESTILLE_URL": f"http://127.0.0.1:{PORTS['destille']}", "DEADSWITCH_URL": f"http://127.0.0.1:{PORTS['deadswitch']}",
    })
    return env


def selbst(*args):
    """Befehl, der diese .exe (oder im Entwicklungsbetrieb python hub.py) mit args startet."""
    return [str(EXE if GEFROREN and EXE.exists() else sys.executable)] + ([] if GEFROREN else [str(Path(__file__).resolve())]) + list(args)


def alle_prozesse_beenden():
    """Beendet alle laufenden Hub-Prozesse (fuer Update und Deinstallation), ausser diesem."""
    ps = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -eq '{EXE}' -and $_.ProcessId -ne {os.getpid()} }}"
          " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=OHNE_FENSTER, capture_output=True)


def verknuepfung(pfad, ziel, args=""):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:L); $s.TargetPath=$env:Z; $s.Arguments=$env:A; "
          "$s.IconLocation=$env:Z+',0'; $s.Description='Smalox Hub'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env={**os.environ, "L": str(pfad), "Z": str(ziel), "A": args},
                   creationflags=OHNE_FENSTER, capture_output=True)


def ordner(name):
    out = subprocess.run(["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{name}')"],
                         capture_output=True, text=True, creationflags=OHNE_FENSTER).stdout.strip()
    return Path(out) if out else None


# ───────────────────────── Rolle 1: Installation ─────────────────────────

def apps_auspacken():
    """Kopiert die mitgelieferten Apps nach ZIEL/apps. data/-Ordner bleiben erhalten (Updates verlieren nichts)."""
    quelle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent / "build")) / "apps"
    if not quelle.is_dir():
        raise SystemExit(f"Apps fehlen im Paket ({quelle}). Erst build_hub.py ausfuehren.")
    shutil.copytree(quelle, APPS, dirs_exist_ok=True)
    (APPS / "version.txt").write_text(VERSION, encoding="utf-8")


def installieren():
    ZIEL.mkdir(parents=True, exist_ok=True)
    if GEFROREN and Path(sys.executable).resolve() != EXE.resolve():
        alle_prozesse_beenden()
        time.sleep(1)
        shutil.copy2(sys.executable, EXE)
    apps_auspacken()
    if TEST:
        return
    import winreg
    start = f'"{EXE}"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
        winreg.SetValueEx(k, "SmaloxHub", 0, winreg.REG_SZ, f"{start} --hintergrund")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SmaloxHub") as k:
        for name, wert in (("DisplayName", TITEL), ("DisplayVersion", VERSION), ("Publisher", "Smalox"),
                           ("DisplayIcon", str(EXE)), ("InstallLocation", str(ZIEL)),
                           ("UninstallString", f"{start} --deinstallieren")):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, wert)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
    for basis in (ordner("Desktop"), ordner("Programs")):
        if basis:
            verknuepfung(basis / "Smalox Hub.lnk", EXE)


def deinstallieren():
    import tkinter
    from tkinter import messagebox
    tkinter.Tk().withdraw()
    if not messagebox.askyesno(TITEL, "Smalox Hub deinstallieren?"):
        return
    daten_weg = messagebox.askyesno(TITEL, "Auch deine Daten löschen (To-Dos, Deadlines, Links, Bildschirmzeit)?\n\n"
                                           "Nein = Daten bleiben in " + str(ZIEL) + " liegen.\nDein Second-Brain-Ordner wird nie gelöscht.")
    alle_prozesse_beenden()
    import winreg
    for pfad, wert in ((r"Software\Microsoft\Windows\CurrentVersion\Run", "SmaloxHub"),):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pfad, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, wert)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SmaloxHub")
    except OSError:
        pass
    for basis in (ordner("Desktop"), ordner("Programs")):
        if basis:
            (basis / "Smalox Hub.lnk").unlink(missing_ok=True)
    # Die laufende .exe kann sich nicht selbst loeschen: das erledigt eine kurze Nachfolge-Aufgabe.
    weg = f'rmdir /s /q "{ZIEL}"' if daten_weg else f'rmdir /s /q "{APPS}" & del /f /q "{EXE}"'
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & {weg}', creationflags=OHNE_FENSTER, shell=True)
    messagebox.showinfo(TITEL, "Smalox Hub wurde entfernt.")


# ───────────────────────── Erster Start: Name und Second Brain ─────────────────────────

VORLAGE = {
    "00 Kontext/Über mich.md": "# Über mich\n{name}\n\n## Ziele\n- \n\n## Sonstiges\n- \n",
    "01 Inbox/Brain Dump.md": "---\ntags: [inbox]\n---\n\n# Brain Dump\n\nWirf hier alles rein, was dir einfällt.\n\n---\n",
    "02 Projekte/Wichtig/Erstes Projekt.md": "---\ntags: [projekt]\nstatus: aktiv\nprioritaet: hoch\ndeadline: offen\n---\n\n# Erstes Projekt\n\n"
                                             "## Ziel\nSmalox Hub kennenlernen.\n\n## Nächste Schritte\n- [ ] Dashboard ansehen\n- [ ] Erste Deadline in Deadswitch anlegen\n"
                                             "- [ ] Einen Link in Destille werfen\n",
    "02 Projekte/Mittel wichtig/.gitkeep": "", "02 Projekte/Unwichtig/.gitkeep": "",
    "03 Bereiche/Gesundheit/Gesundheit.md": "---\ntags: [bereich]\n---\n\n# Gesundheit\n\n## Beschreibung\n\n## Notizen\n",
    "04 Ressourcen/Sonstiges/Sonstiges.md": "---\ntags: [ressource]\n---\n\n# Sonstiges\n\n## Notizen\n",
    "05 Daily Notes/.gitkeep": "", "06 Archiv/.gitkeep": "", "08 Vorlagen/.gitkeep": "",
}


def erster_start():
    e = einstellungen_laden()
    if e.get("name"):
        return e
    if TEST:
        e = {"name": "Test", "vault": ""}
    else:
        import tkinter
        from tkinter import filedialog, messagebox, simpledialog
        tkinter.Tk().withdraw()
        e["name"] = (simpledialog.askstring(TITEL, "Willkommen bei Smalox Hub!\n\nWie heißt du?",
                                            initialvalue=os.environ.get("USERNAME", "")) or "Du").strip()[:40]
        e["vault"] = ""
        if messagebox.askyesno(TITEL, "Hast du schon ein Obsidian-Vault (Second Brain), das der Hub anzeigen soll?\n\n"
                                      "Nein = der Hub legt ein neues, leeres Second Brain für dich an."):
            e["vault"] = filedialog.askdirectory(title="Ordner deines Obsidian-Vaults wählen") or ""
    if not e["vault"]:
        vault = ZIEL / "Second Brain"
        for rel, inhalt in VORLAGE.items():
            pfad = vault / rel
            if not pfad.exists():
                pfad.parent.mkdir(parents=True, exist_ok=True)
                pfad.write_text(inhalt.replace("{name}", e["name"]), encoding="utf-8")
        e["vault"] = str(vault)
    ZIEL.mkdir(parents=True, exist_ok=True)
    EINSTELLUNGEN.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
    return e


# ───────────────────────── Rolle 2: Starten ─────────────────────────

def starten(fenster=True):
    env = umgebung(erster_start())
    for name, skript in DIENSTE:
        if not port_offen(PORTS[name]):
            subprocess.Popen(selbst(str(WEB / skript)), env=env, cwd=str((WEB / skript).parent),
                             creationflags=OHNE_FENSTER, close_fds=True)
    if not fenster:
        return
    for _ in range(60):  # bis zu 15 s auf das Dashboard warten
        if port_offen(PORTS["dashboard"]):
            break
        time.sleep(0.25)
    subprocess.Popen(selbst(str(WEB / "marlons-dashboard" / "fenster.py"), f"http://127.0.0.1:{PORTS['dashboard']}"),
                     env=env, creationflags=OHNE_FENSTER, close_fds=True)


def main():
    args = sys.argv[1:]
    if args and args[0].endswith(".py"):
        return skript_ausfuehren(args[0], args[1:])
    if "--deinstallieren" in args:
        return deinstallieren()
    installiert = EXE.exists() and GEFROREN and Path(sys.executable).resolve() == EXE.resolve()
    veraltet = not (APPS / "version.txt").is_file() or (APPS / "version.txt").read_text(encoding="utf-8").strip() != VERSION
    if (GEFROREN and not installiert) or veraltet or TEST:
        installieren()
        if GEFROREN and not installiert and not TEST:
            subprocess.Popen([str(EXE)], env=sauberes_env(), creationflags=OHNE_FENSTER, close_fds=True)
            return
    starten(fenster="--hintergrund" not in args)


def fehler_merken(wo):
    import traceback
    try:
        ZIEL.mkdir(parents=True, exist_ok=True)
        with open(ZIEL / "fehler.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {wo}\n{traceback.format_exc()}\n")
    except OSError:
        pass


if __name__ == "__main__":
    if sys.argv == ["__nie__"]:  # nur damit PyInstaller alle Module findet, die die Apps brauchen
        import _app_importe  # noqa: F401
    try:
        main()
    except SystemExit:
        raise
    except BaseException:  # ohne Konsole sieht man Fehler sonst nie
        fehler_merken(" ".join(sys.argv[1:]) or "start")
        raise
