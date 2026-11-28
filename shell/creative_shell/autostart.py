"""Autostart: Programme beim Anmelden öffnen.

Startmenü › Rechtsklick › „Beim Anmelden starten“ legt eine Kopie des Starters unter
~/.config/autostart/ an (XDG-Standard – dieselben Einträge, die z. B. Steam oder Discord selbst
anlegen, wenn man dort „mit dem System starten“ wählt). Beim Anmelden startet
`python3 -m creative_shell.autostart` alle diese Einträge (die Gibeon-Sitzung hat keinen
KDE-Sitzungsmanager, der das sonst täte). Systemweite Einträge unter /etc/xdg/autostart bleiben
außen vor – das sind Hintergrunddienste von KDE/GNOME, die Gibeon OS selbst regelt.

Programme aus dem Autostart starten minimiert: Wer es kann, startet gleich unsichtbar im Tray
(Steam, Discord, Telegram … mit ihrem eigenen Schalter, siehe TRAY_FLAGS). Für alle anderen
legt ein kurzes KWin-Skript die Fenster, die in den ersten zwei Minuten aufgehen, gleich
minimiert ab. Ein Eintrag mit „X-Gibeon-Autostart-Minimized=false“ startet normal.
"""

import configparser
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

MARK = "X-Gibeon-Autostart"
MINIMIZED = "X-Gibeon-Autostart-Minimized"
MINIMIZE_SECONDS = 120

# Programme mit eigenem Schalter „im Tray starten“ (Schlüssel: Programm- oder Flatpak-Name, klein)
TRAY_FLAGS = {
    "steam": ["-silent"], "com.valvesoftware.steam": ["-silent"],
    "discord": ["--start-minimized"], "com.discordapp.discord": ["--start-minimized"],
    "vesktop": ["--start-minimized"], "dev.vencord.vesktop": ["--start-minimized"],
    "telegram-desktop": ["-startintray"], "org.telegram.desktop": ["-startintray"],
    "signal-desktop": ["--start-in-tray"], "org.signal.signal": ["--start-in-tray"],
    "element-desktop": ["--hidden"], "im.riot.riot": ["--hidden"],
    "nextcloud": ["--background"], "com.nextcloud.desktopclient.nextcloud": ["--background"],
    "keepassxc": ["--minimized"], "org.keepassxc.keepassxc": ["--minimized"],
}


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


def wants_minimized(path):
    p = _read(path)
    return p is None or p["Desktop Entry"].get(MINIMIZED, "true").lower() != "false"


def app_names(path):
    """Namen, unter denen das Programm auftreten kann: Desktop-Datei, Befehl, Flatpak-ID, Fensterklasse."""
    names = {Path(path).stem.lower()}
    p = _read(path)
    if p is None:
        return names
    e = p["Desktop Entry"]
    try:
        args = shlex.split(e.get("Exec", ""))
    except ValueError:
        args = e.get("Exec", "").split()
    if args:
        names.add(os.path.basename(args[0]).lower())
        if os.path.basename(args[0]) == "flatpak" and "run" in args:
            rest = [a for a in args[args.index("run") + 1:] if not a.startswith("-")]
            if rest:
                names.add(rest[0].lower())
    if e.get("StartupWMClass"):
        names.add(e["StartupWMClass"].lower())
    return {n for n in names if n and n not in ("env", "sh", "bash", "flatpak", "gio")}


def tray_command(path):
    """Startbefehl mit dem eigenen „im Tray starten“-Schalter des Programms – oder None."""
    p = _read(path)
    if p is None:
        return None
    try:
        args = shlex.split(p["Desktop Entry"].get("Exec", ""))
    except ValueError:
        return None
    flags = next((TRAY_FLAGS[n] for n in sorted(app_names(path)) if n in TRAY_FLAGS), None)
    if not args or not flags:
        return None
    # Feldcodes (%U, %f …) gelten nur beim Öffnen von Dateien – beim Anmelden weglassen
    args = [a for a in args if not re.fullmatch(r"%[a-zA-Z]", a)]
    return args + [f for f in flags if f not in args]


MINIMIZER_JS = """
const names = %s;
const until = Date.now() + %d * 1000;
const firstSeen = {};
function matches(w, n) {
    const app = (w.desktopFileName || "").toLowerCase();
    const cls = (w.resourceClass || "").toLowerCase();
    return app === n || cls === n || app.endsWith("." + n) || cls.endsWith("." + n)
        || n.endsWith("." + app) || (n.length > 3 && cls.indexOf(n) >= 0);
}
function gibeonAutostartMinimize(w) {
    if (Date.now() > until) {
        workspace.windowAdded.disconnect(gibeonAutostartMinimize);
        return;
    }
    if (!w || !w.normalWindow || w.skipTaskbar)
        return;
    const n = names.find(x => matches(w, x));
    if (n === undefined)
        return;
    // Nur die Fenster beim Start (Begrüßung + Hauptfenster): danach selbst geöffnete Fenster bleiben offen
    if (firstSeen[n] === undefined)
        firstSeen[n] = Date.now();
    if (Date.now() - firstSeen[n] <= 20000)
        w.minimized = true;
}
workspace.windowAdded.connect(gibeonAutostartMinimize);
"""


def minimizer_script(names, seconds=MINIMIZE_SECONDS):
    """KWin-Skript: Fenster dieser Programme in den ersten Minuten gleich minimieren."""
    import json
    return MINIMIZER_JS % (json.dumps(sorted(names)), int(seconds))


def _kwin(method, *args):
    cmd = ["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/Scripting",
           "--method", f"org.kde.kwin.Scripting.{method}", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def load_minimizer(names):
    """Skript laden und starten; gibt den Namen zum späteren Entladen zurück (oder None)."""
    if not names or not shutil.which("gdbus"):
        return None
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    name = f"gibeon-autostart-minimiert-{os.getpid()}"
    file = Path(base) / f"{name}.js"
    try:
        file.write_text(minimizer_script(names), encoding="utf-8")
        out = _kwin("loadScript", str(file), name)
        if out.returncode != 0:
            return None
        _kwin("start")
        return name
    except (OSError, subprocess.SubprocessError):
        return None


def unload_minimizer(name):
    if not name:
        return
    try:
        _kwin("unloadScript", name)
        base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        Path(base, f"{name}.js").unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError):
        pass


def entries():
    d = autostart_dir()
    return [p for p in sorted(d.glob("*.desktop")) if enabled_entry(p)] if d.is_dir() else []


def start_all(delay=0.0):
    """Beim Anmelden: alle eingeschalteten Einträge starten (nacheinander, leicht versetzt)."""
    started = []
    for path in entries():
        cmd = tray_command(path) if wants_minimized(path) else None
        try:
            subprocess.Popen(cmd or ["gio", "launch", str(path)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started.append(path.name)
        except OSError:
            continue
        if delay:
            time.sleep(delay)
    return started


if __name__ == "__main__":
    # Erst das Minimier-Skript laden, dann starten – so erwischt es auch das erste Fenster
    minimize = set()
    for entry in entries():
        if wants_minimized(entry):
            minimize |= app_names(entry)
    script = load_minimizer(minimize)
    names = start_all(delay=0.4)
    print("Autostart:", ", ".join(names) if names else "nichts",
          "(minimiert)" if script else "", file=sys.stderr)
    if script:
        time.sleep(MINIMIZE_SECONDS + 5)
        unload_minimizer(script)
