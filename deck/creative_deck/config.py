"""Einstellungen von Creative Deck: ~/.config/creative-deck/config.json

Ein Profil für alle Stream Decks: Seiten mit Tasten (Nummer → Taste). Jede Taste hat
Beschriftung, Symbol, Hintergrundfarbe und eine Aktion. Der Hintergrunddienst liest die
Datei neu, sobald der Editor sie speichert.
"""

import copy
import json
import os
from pathlib import Path

# Bekannte Modelle: Spalten, Zeilen (für die Vorschau ohne angestecktes Gerät)
MODELS = {
    "Stream Deck MK.2": (5, 3),
    "Stream Deck Original": (5, 3),
    "Stream Deck XL": (8, 4),
    "Stream Deck Mini": (3, 2),
    "Stream Deck +": (4, 2),
    "Stream Deck Neo": (4, 2),
}
DEFAULT_MODEL = "Stream Deck MK.2"


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-deck"


def config_path():
    return config_dir() / "config.json"


def status_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or str(Path.home() / ".cache")
    return Path(base) / "creative-deck" / "status.json"


def _key(text, symbol, aktion, farbe=""):
    return {"text": text, "symbol": symbol, "farbe": farbe, "aktion": aktion}


def default_config():
    """Erste Einrichtung: sinnvolle Beispiel-Tasten, die man sofort ausprobieren kann."""
    start = {
        "0": _key("Dateien", "app:creative-files.desktop", {"typ": "app", "app": "creative-files.desktop"}),
        "1": _key("Brave", "app:brave-browser.desktop", {"typ": "app", "app": "brave-browser.desktop"}),
        "2": _key("Terminal", "glyph:terminal", {"typ": "app", "app": "org.kde.konsole.desktop"}),
        "3": _key("Bildschirm-foto", "glyph:screenshot", {"typ": "tasten", "tasten": "print"}),
        "4": _key("OBS", "glyph:broadcast", {"typ": "seite", "seite": 1}, "#2b3550"),
        "5": _key("Zurück", "glyph:prev", {"typ": "medien", "was": "zurueck"}),
        "6": _key("", "glyph:play", {"typ": "medien", "was": "play-pause"}),
        "7": _key("Weiter", "glyph:next", {"typ": "medien", "was": "weiter"}),
        "8": _key("Leiser", "glyph:speaker", {"typ": "lautstaerke", "was": "leiser"}),
        "9": _key("Lauter", "glyph:volume", {"typ": "lautstaerke", "was": "lauter"}),
        "10": _key("Ton aus", "glyph:volume-off", {"typ": "lautstaerke", "was": "stumm"}),
        "11": _key("Mikro aus", "glyph:mic", {"typ": "mikrofon"}),
        "12": _key("Kopieren", "glyph:copy", {"typ": "tasten", "tasten": "ctrl+c"}),
        "13": _key("Einfügen", "glyph:paste", {"typ": "tasten", "tasten": "ctrl+v"}),
        "14": _key("Sperren", "glyph:lock", {"typ": "tasten", "tasten": "meta+l"}),
    }
    obs = {
        "0": _key("Zurück", "glyph:back", {"typ": "zurueck"}),
        "1": _key("Aufnahme", "glyph:video", {"typ": "obs", "was": "aufnahme"}, "#5a2a32"),
        "2": _key("Stream", "glyph:broadcast", {"typ": "obs", "was": "stream"}, "#2b3550"),
        "3": _key("Replay", "glyph:save", {"typ": "obs", "was": "replay"}),
        "4": _key("Mikro", "glyph:mic", {"typ": "obs", "was": "stumm", "name": "Mikrofon/AUX"}),
        "5": _key("Szene 1", "glyph:screen-tool", {"typ": "obs", "was": "szene", "name": "Szene"}),
    }
    return {
        "version": 1,
        "helligkeit": 70,
        "aus_nach_min": 0,
        "obs": {"host": "localhost", "port": 4455, "passwort": ""},
        "seiten": [{"name": "Start", "tasten": start}, {"name": "OBS", "tasten": obs}],
        "letztes_geraet": {"modell": DEFAULT_MODEL, "spalten": 5, "zeilen": 3},
    }


def _clean(cfg):
    base = default_config()
    if not isinstance(cfg, dict):
        return base
    out = copy.deepcopy(base)
    for k in ("helligkeit", "aus_nach_min", "letztes_geraet"):
        if k in cfg:
            out[k] = cfg[k]
    if isinstance(cfg.get("obs"), dict):
        out["obs"].update(cfg["obs"])
    seiten = cfg.get("seiten")
    if isinstance(seiten, list) and seiten:
        out["seiten"] = [
            {"name": str(s.get("name") or f"Seite {i + 1}"),
             "tasten": {str(k): v for k, v in (s.get("tasten") or {}).items() if isinstance(v, dict)}}
            for i, s in enumerate(seiten) if isinstance(s, dict)
        ] or base["seiten"]
    try:
        out["helligkeit"] = max(0, min(100, int(out["helligkeit"])))
        out["aus_nach_min"] = max(0, int(out["aus_nach_min"]))
    except (TypeError, ValueError):
        out["helligkeit"], out["aus_nach_min"] = 70, 0
    return out


def load():
    try:
        return _clean(json.loads(config_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return default_config()


def save(cfg):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def mtime():
    try:
        return config_path().stat().st_mtime_ns
    except OSError:
        return 0


def read_status():
    try:
        return json.loads(status_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_status(status):
    path = status_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
