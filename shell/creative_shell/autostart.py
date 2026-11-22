"""Autostart: Programme beim Anmelden öffnen.

Startmenü › Rechtsklick › „Beim Anmelden starten“ legt eine Kopie des Starters unter
~/.config/autostart/ an (XDG-Standard – dieselben Einträge, die z. B. Steam oder Discord selbst
anlegen, wenn man dort „mit dem System starten“ wählt). Beim Anmelden startet
`python3 -m creative_shell.autostart` alle diese Einträge (die Gibeon-Sitzung hat keinen
KDE-Sitzungsmanager, der das sonst täte). Systemweite Einträge unter /etc/xdg/autostart bleiben
außen vor – das sind Hintergrunddienste von KDE/GNOME, die Gibeon OS selbst regelt.
"""

import configparser
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MARK = "X-Gibeon-Autostart"


def autostart_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def _read(path):
    p = configparser.ConfigParser(interpolation=None, strict=False)
    p.optionxform = str
    try:
        p.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    return p if p.has_section("Desktop Entry") else None


def enabled_entry(path, desktop=("GIBEON", "KDE")):
    """Soll dieser Autostart-Eintrag starten?"""
    p = _read(path)
    if p is None:
        return False
    e = p["Desktop Entry"]
    if e.get("Hidden", "false").lower() == "true":
        return False
    if e.get("X-GNOME-Autostart-enabled", "true").lower() == "false":
        return False
    only = [x for x in e.get("OnlyShowIn", "").split(";") if x]
    if only and not any(d in only for d in desktop):
        return False
    notin = [x for x in e.get("NotShowIn", "").split(";") if x]
    if any(d in notin for d in desktop):
        return False
    try_exec = e.get("TryExec", "")
    if try_exec and not (shutil.which(try_exec) or os.path.exists(try_exec)):
        return False
    return bool(e.get("Exec", "").strip())


def is_enabled(desktop_id):
    path = autostart_dir() / desktop_id
    return path.exists() and enabled_entry(path)


def enable(desktop_id, source_path):
    """Kopie des Starters nach ~/.config/autostart/ (mit Markierung, dass Gibeon sie angelegt hat)."""
    target = autostart_dir() / desktop_id
    target.parent.mkdir(parents=True, exist_ok=True)
    text = Path(source_path).read_text(encoding="utf-8")
    lines, out, in_main = text.splitlines(), [], False
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            in_main = s == "[Desktop Entry]"
        elif in_main and s.split("=", 1)[0].strip() in ("Hidden", "X-GNOME-Autostart-enabled", MARK):
            continue                         # alte Schalter raus, unten neu
        out.append(line)
        if s == "[Desktop Entry]":
            out.append(f"{MARK}=true")
    tmp = target.with_suffix(".neu")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    tmp.replace(target)


def disable(desktop_id):
    try:
        (autostart_dir() / desktop_id).unlink()
    except FileNotFoundError:
        pass


def start_all(delay=0.0):
    """Beim Anmelden: alle eingeschalteten Einträge starten (nacheinander, leicht versetzt)."""
    d = autostart_dir()
    if not d.is_dir():
        return []
    started = []
    for path in sorted(d.glob("*.desktop")):
        if not enabled_entry(path):
            continue
        try:
            subprocess.Popen(["gio", "launch", str(path)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started.append(path.name)
        except OSError:
            continue
        if delay:
            time.sleep(delay)
    return started


if __name__ == "__main__":
    names = start_all(delay=0.4)
    print("Autostart:", ", ".join(names) if names else "nichts", file=sys.stderr)
