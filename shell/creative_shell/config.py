"""Einstellungen der Shell.

Gelesen wird ~/.config/creative-os/shell.json. Fehlt die Datei oder ist sie
kaputt, gelten die Standardwerte – die Shell startet also immer.
"""

import json
import os
from pathlib import Path

# Jede angeheftete App ist eine Liste von Kandidaten: die erste .desktop-Datei,
# die auf dem System existiert, wird verwendet. So funktioniert die Taskleiste
# auch, solange z. B. der eigene Dateimanager noch nicht installiert ist.
DEFAULTS = {
    # Eigenes Hintergrundbild: Pfad zu einer Bild-Datei, leer = Creative-Graphit
    "wallpaper": "",
    # Leistungsanzeige (CPU, Speicher …) oben rechts auf dem Schreibtisch
    "desktopStats": True,
    "desktopWidgetRSS": {},
    "desktopWidgetWeather": {},
    "desktopStatsPosition": [],
    "desktopExtras": {},
    # Musik-Visualizer hinter der Taskleiste
    "taskbarVisualizer": True,
    "visualizerOpacity": 0.1,
    # Interpret und Titel des laufenden Liedes mittig in der Taskleiste
    "taskbarNowPlaying": True,
    # Ablage oben mittig auf dem Schreibtisch (Verknüpfungen, wie das Dock bei macOS)
    "desktopShelf": True,
    "shelf": [],
    "hiddenStartApps": [],
    # Position der Ablage (Anteil der freien Fläche 0…1; -1 = oben mittig)
    "shelfX": -1.0,
    "shelfY": -1.0,
    "pinned": [
        {
            "icon": "files",
            "candidates": [
                "creative-files.desktop",
                "org.kde.dolphin.desktop",
                "org.gnome.Nautilus.desktop",
            ],
        },
        {
            "icon": "browser",
            "candidates": [
                "brave-browser.desktop",
                "com.brave.Browser.desktop",
                "firefox.desktop",
                "org.mozilla.firefox.desktop",
            ],
        },
        {
            "icon": "terminal",
            "candidates": [
                "creative-terminal.desktop",
                "org.kde.konsole.desktop",
                "org.gnome.Ptyxis.desktop",
                "foot.desktop",
            ],
        },
        # KI-Assistenten als eigene Fenster (Web-Apps über Brave).
        # "match": so heißen ihre Fenster bei KWin – damit der Punkt unter
        # dem Symbol erscheint, wenn das Fenster offen ist.
        {
            "icon": "claude",
            "candidates": ["creative-claude.desktop"],
            "match": ["brave-claude.ai", "creative-claude"],
        },
        {
            "icon": "gemini",
            "candidates": ["creative-gemini.desktop"],
            "match": ["brave-gemini.google.com", "creative-gemini"],
        },
        {
            "icon": "chatgpt",
            "candidates": ["creative-chatgpt.desktop"],
            "match": ["brave-chatgpt.com", "creative-chatgpt"],
        },
        {
            "icon": "youtube",
            "candidates": ["creative-youtube.desktop"],
            "match": ["brave-www.youtube.com", "brave-youtube.com", "creative-youtube"],
        },
        {
            "icon": "twitch",
            "candidates": ["creative-twitch.desktop"],
            "match": ["brave-www.twitch.tv", "brave-twitch.tv", "creative-twitch"],
        },
        {
            "icon": "whatsapp",
            "candidates": ["creative-whatsapp.desktop"],
            "match": ["brave-web.whatsapp.com", "creative-whatsapp"],
        },
    ],
}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os"


def load() -> dict:
    data = json.loads(json.dumps(DEFAULTS))  # tiefe Kopie
    path = config_dir() / "shell.json"
    try:
        with path.open(encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            for key, value in user.items():
                if key in data and type(value) is type(data[key]):
                    data[key] = value
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        print(f"creative-shell: {path} wird ignoriert ({exc})")
    return data


def set_value(key, value):
    """Einen Wert in shell.json ändern, ohne den Rest anzufassen."""
    path = config_dir() / "shell.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError as exc:
        print(f"creative-shell: {path} nicht gespeichert ({exc})")
        return False
