"""Design von Creative OS: „graphit“ (dunkel) oder „porzellan“ (hell) und die Akzentfarbe.

Gespeichert in ~/.config/creative-os/look.conf (INI, wird auch von QML gelesen: Theme.qml).
Python-Programme mit eigenen Farben holen sich hier ihre Palette: palette().
"""

import configparser
import os
import shutil
import subprocess
from pathlib import Path

DESIGNS = ("graphit", "porzellan")
ACCENTS = {"blau": ("#8fb3ff", "#3d6fe0"), "gruen": ("#6fdcc0", "#1f9e7f"),
           "orange": ("#ffb07a", "#d9773a"), "lila": ("#c3a6ff", "#7c4ddb")}

GRAPHIT = {"ground": "#12151b", "surface": "#1c2029", "side": "#171a22", "raised": "#232836",
           "track": "#3a4252", "line": "#2a303d", "text": "#dce6ff", "muted": "#9aa6c4", "dim": "#6f7a92",
           "accent": "#8fb3ff", "accentText": "#12151b", "accentHover": "#a6c3ff", "select": "#2a3a5c",
           "flame": "#ffb07a", "ok": "#6fdcc0", "danger": "#ff8a8e", "star": "#f2d58a", "view": "#161920"}
PORZELLAN = {"ground": "#e9eef6", "surface": "#ffffff", "side": "#f4f6fa", "raised": "#eef1f6",
             "track": "#cdd5e2", "line": "#d9dfe9", "text": "#1c2433", "muted": "#5d6884", "dim": "#8a93a8",
             "accent": "#3d6fe0", "accentText": "#ffffff", "accentHover": "#2f5fcf", "select": "#dbe6fb",
             "flame": "#d9773a", "ok": "#1f9e7f", "danger": "#d23c45", "star": "#c99a1e", "view": "#ffffff"}


def path():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "look.conf"


def read():
    cp = configparser.ConfigParser()
    try:
        cp.read(path(), encoding="utf-8")
    except (OSError, configparser.Error):
        pass
    design = cp.get("Look", "design", fallback="graphit")
    accent = cp.get("Look", "accent", fallback="blau")
    return (design if design in DESIGNS else "graphit"), (accent if accent in ACCENTS else "blau")


def write(design=None, accent=None):
    cur_design, cur_accent = read()
    design = design if design in DESIGNS else cur_design
    accent = accent if accent in ACCENTS else cur_accent
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".neu")   # ersetzen statt überschreiben: die Taskleiste bemerkt es sofort
    tmp.write_text(f"[Look]\ndesign={design}\naccent={accent}\n", encoding="utf-8")
    tmp.replace(p)
    return design, accent


def is_light():
    return read()[0] == "porzellan"


def palette(base=None):
    """Farbtabelle für das gewählte Design (Schlüssel wie oben); base: eigene Tabelle eines Programms,
    deren bekannte Schlüssel ersetzt werden."""
    design, accent = read()
    pal = dict(PORZELLAN if design == "porzellan" else GRAPHIT)
    dark_acc, light_acc = ACCENTS[accent]
    pal["accent"] = light_acc if design == "porzellan" else dark_acc
    if accent != "blau":
        pal["accentHover"] = pal["accent"]
    if base is None:
        return pal
    out = dict(base)
    for key in out:
        if key in pal:
            out[key] = pal[key]
    return out


def wallpaper_dir(qml_dir):
    return Path(qml_dir) / "Creative" / ("wallpapers-light" if is_light() else "wallpapers")


def default_wallpaper(qml_dir):
    folder = wallpaper_dir(qml_dir)
    for name in ("porzellan.svg", "graphit.svg"):
        if (folder / name).exists():
            return folder / name
    return Path(qml_dir) / "Creative" / "wallpapers" / "graphit.svg"


def apply_system():
    """GTK-, KDE- und Terminal-Farben ans Design anpassen (läuft als Benutzer)."""
    tool = shutil.which("creative-look-apply") or "/usr/libexec/creative-look-apply"
    if os.path.exists(tool):
        subprocess.Popen([tool], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
