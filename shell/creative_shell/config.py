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
