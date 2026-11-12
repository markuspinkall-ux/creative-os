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


# ---- Fertige Apps mit festen Graphit-Farben ins gewählte Design bringen ------------------------
# Viele Creative-Apps schreiben ihre Farben als Graphit-Hexwerte. themed() übersetzt diese Werte
# (in Stylesheets, Paletten, einzelnen Farben) ins helle Design „Porzellan“ und die Akzentfarbe
# ins gewählte Akzent – Programmcode der Apps bleibt dabei unverändert.
_LIGHT = {
    # Flächen
    "#12151b": "#e9eef6", "#101218": "#e4e9f2", "#10131d": "#e4e9f2", "#111827": "#e9eef6",
    "#131722": "#eef1f6", "#141720": "#eef1f6", "#161920": "#f4f6fa", "#161922": "#f4f6fa",
    "#171a22": "#f4f6fa", "#171b22": "#f4f6fa", "#18192a": "#eef1f6", "#1c2029": "#ffffff",
    "#1d2230": "#ffffff", "#1e222c": "#f2f5fa", "#202634": "#f4f6fa", "#232836": "#eef1f6",
    "#252643": "#eef1f6", "#252842": "#eef1f6", "#262b39": "#eef1f6", "#2a3040": "#e3e8f0",
    "#2a303d": "#d9dfe9", "#2a3144": "#e3e8f0", "#2c3242": "#e3e8f0", "#293246": "#e3e8f0",
    "#30384a": "#d9dfe9", "#30384f": "#d9dfe9", "#343b4d": "#d2d9e5", "#343c53": "#d2d9e5",
    "#3a4252": "#cdd5e2", "#3a4460": "#c6cfde", "#3b455e": "#c6cfde", "#404774": "#c6cfde",
    "#475576": "#b9c3d6", "#4d5568": "#b5bfd0", "#5a6171": "#8a93a8",
    # Auswahl
    "#2f4675": "#dbe6fb", "#2c3650": "#e3ebfb", "#33405e": "#d3defa", "#243451": "#dbe6fb",
    "#293855": "#dbe6fb", "#2a3a5c": "#dbe6fb",
    # Schrift
    "#dce6ff": "#1c2433", "#eaf0ff": "#1c2433", "#b8c3de": "#3a4660", "#b9c9ff": "#2f4b8f",
    "#9aa6c4": "#5d6884", "#9aa6c2": "#5d6884", "#aab4cb": "#5d6884", "#8993a6": "#5d6884",
    "#8590a6": "#5d6884", "#6f7a92": "#8a93a8",
    # Signalfarben (auf hellem Grund dunkler)
    "#6fdcc0": "#1f9e7f", "#ffb07a": "#d9773a", "#f2d58a": "#a8800f", "#d7a8ff": "#8a3fc9",
    "#ff8a8e": "#d23c45", "#5a4a22": "#f6e7bd", "#5c2a30": "#fbe0e2", "#174249": "#d6efe9",
}
_ACCENTS = ("#8fb3ff", "#9cbcff", "#84a9f7", "#68a0ff")
_ACCENT_HOVER = ("#a3c1ff", "#a6c3ff")
_HEX = None


def _table():
    design, accent = read()
    table = dict(_LIGHT) if design == "porzellan" else {}
    pal = palette()
    if design == "porzellan" or accent != "blau":
        for h in _ACCENTS:
            table[h] = pal["accent"]
        for h in _ACCENT_HOVER:
            table[h] = pal["accentHover"]
    return table, design == "porzellan"


def themed(value):
    """Graphit-Farben in einem Text (Stylesheet, HTML, einzelne Farbe) ins gewählte Design übersetzen."""
    global _HEX
    if not isinstance(value, str) or "#" not in value and "rgba(255" not in value:
        return value
    table, light = _table()
    if not table:
        return value
    import re
    if _HEX is None:
        _HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
    out = _HEX.sub(lambda m: table.get(m.group(0).lower(), m.group(0)), value)
    if light:
        out = re.sub(r"rgba\(\s*255\s*,\s*255\s*,\s*255\s*,", "rgba(28,36,51,", out)
    return out


def install():
    """In einer Qt-Widgets-App aufrufen (nach dem Import von PySide6): alle Stylesheets laufen dann
    durch themed(). Für Farben im Programmcode: QColor(themed("#12151b"))."""
    try:
        from PySide6.QtWidgets import QApplication, QWidget
    except ImportError:
        return
    if getattr(QWidget, "_creative_themed", False):
        return
    widget_set = QWidget.setStyleSheet
    app_set = QApplication.setStyleSheet

    def set_widget(self, css):
        widget_set(self, themed(css))

    def set_app(self, css):
        app_set(self, themed(css))

    QWidget.setStyleSheet = set_widget
    QApplication.setStyleSheet = set_app
    QWidget._creative_themed = True
