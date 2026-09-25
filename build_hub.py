"""
Baut dist/SmaloxHub.exe: sammelt die fuenf Apps (ohne persoenliche Daten) nach build/apps,
zeichnet das Symbol und packt alles mit PyInstaller in eine einzige .exe.

    python build_hub.py

Braucht: pip install pyinstaller pywebview
"""

import ast
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
WEB = HIER.parent
BUILD = HIER / "build"
APPS = BUILD / "apps"
APP_ORDNER = ["marlons-dashboard", "destille", "deadswitch", "zeitblick", "zeitschloss"]
# Nie mit ausliefern: persoenliche Daten, Zugangsdaten, Test- und Build-Reste
WEG = ["data", "__pycache__", ".git", ".gitignore", "build", "dist", "*.pid", ".token", "test_*.py", "fake_*.py",
       "*.spec", "*.log", "focus_state.json", "instagram_cookies.txt", "*.exe", "releases", "version_info.txt",
       "build_exe.py", "Zeitblick.cmd", "*.cmd"]
OHNE_IMPORT = {"faster_whisper", "yt_dlp", "av", "PIL", "PyInstaller"}  # Video-Auswertung ist optional (zu gross)
VERBOTEN = ["smalox.der.beste", "Second Brain Smalox", "GEHEIM"]  # darf nirgends im Paket stehen


def ignorieren(_ordner, namen):
    return {n for n in namen if any(fnmatch.fnmatch(n, m) for m in WEG)}


def apps_sammeln():
    shutil.rmtree(BUILD, ignore_errors=True)
    for app in APP_ORDNER:
        shutil.copytree(WEB / app, APPS / "web-demos" / app, ignore=ignorieren)
    # Zeitblick: Kategorien im Auslieferungszustand, nicht Marlons eigene Anpassungen
    standard = subprocess.run(["git", "-C", str(WEB / "zeitblick"), "show", "HEAD:categories.json"],
                              capture_output=True, text=True, encoding="utf-8").stdout
    if standard:
        (APPS / "web-demos" / "zeitblick" / "categories.json").write_text(standard, encoding="utf-8")
    for pfad in APPS.rglob("*"):
        if pfad.is_file() and pfad.suffix in (".py", ".js", ".json", ".md", ".html", ".txt"):
            text = pfad.read_text(encoding="utf-8", errors="ignore")
            treffer = [v for v in VERBOTEN if v in text and "VERBOTEN" not in text]
            if treffer and pfad.name != "quellen.py":  # quellen.py nennt nur den Standardpfad fuer Marlons PC
                raise SystemExit(f"Persoenliches in {pfad.relative_to(APPS)}: {treffer}")


def importe_sammeln():
    """Alle Module, die die App-Skripte importieren, damit PyInstaller sie in die .exe packt."""
    eigene = {p.stem for p in APPS.rglob("*.py")}
    module = set()
    for p in APPS.rglob("*.py"):
        for knoten in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Import):
                module |= {a.name.split(".")[0] for a in knoten.names}
            elif isinstance(knoten, ast.ImportFrom) and knoten.module and not knoten.level:
                module.add(knoten.module.split(".")[0])
    module -= eigene | OHNE_IMPORT
    module |= {"webview", "clr", "tkinter"}
    zeilen = [f"try:\n    import {m}  # noqa: F401\nexcept ImportError:\n    pass" for m in sorted(module)]
    (BUILD / "_app_importe.py").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return sorted(module)


def symbol():
    """Ein "S" im Stil des Dashboard-Symbols."""
    sys.path.insert(0, str(WEB / "marlons-dashboard"))
    import make_icon
    make_icon.M_PUNKTE = [(0.7, 0.3), (0.3, 0.3), (0.3, 0.5), (0.7, 0.5), (0.7, 0.7), (0.3, 0.7)]
    import struct
    groessen = [16, 24, 32, 48, 64, 128, 256]
    bilder = {g: make_icon.render(g) for g in groessen}
    kopf, versatz = struct.pack("<HHH", 0, 1, len(groessen)), 6 + 16 * len(groessen)
    eintraege, daten = b"", b""
    for g in groessen:
        eintraege += struct.pack("<BBBBHHII", g % 256, g % 256, 0, 0, 1, 32, len(bilder[g]), versatz + len(daten))
        daten += bilder[g]
    (APPS / "smalox-hub.ico").write_bytes(kopf + eintraege + daten)
    (HIER / "docs").mkdir(exist_ok=True)
    (HIER / "docs" / "icon.png").write_bytes(bilder[256])


def main():
    apps_sammeln()
    module = importe_sammeln()
    symbol()
    print(f"{len(module)} Module fuer die Apps: {', '.join(module)}")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--noconsole", "--name", "SmaloxHub",
                    "--icon", str(APPS / "smalox-hub.ico"), "--add-data", f"{APPS};apps", "--paths", str(BUILD),
                    "--hidden-import", "_app_importe", "--collect-all", "webview", "--collect-all", "clr_loader",
                    "--collect-all", "pythonnet", "--collect-all", "clr",
                    "--distpath", str(HIER / "dist"), "--workpath", str(BUILD / "pyinstaller"), "--specpath", str(BUILD),
                    str(HIER / "hub.py")], check=True)
    exe = HIER / "dist" / "SmaloxHub.exe"
    print(f"fertig: {exe} ({exe.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
