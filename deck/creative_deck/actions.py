"""Was eine Taste tut. Seitenwechsel und Helligkeit erledigt der Dienst selbst (deck_actions)."""

import os
import shutil
import subprocess

from . import apps, obs
from .keys import Keyboard, german

# Typ → (Name im Editor, Beschreibung)
TYPES = [
    ("app", "Programm starten"),
    ("befehl", "Befehl ausführen"),
    ("webseite", "Webseite öffnen"),
    ("tasten", "Tastenkürzel"),
    ("text", "Text einfügen"),
    ("medien", "Musik & Video"),
    ("lautstaerke", "Lautstärke"),
    ("mikrofon", "Mikrofon stumm"),
    ("obs", "OBS Studio"),
    ("sound", "Ton abspielen"),
    ("seite", "Seite öffnen"),
    ("zurueck", "Zurück"),
    ("helligkeit", "Helligkeit"),
    ("keine", "Nichts"),
]
TYPE_NAMES = dict(TYPES)
DECK_ACTIONS = ("seite", "zurueck", "helligkeit")

MEDIA = {"play-pause": "playpause", "weiter": "next", "zurueck": "previous", "stopp": "stop"}
MEDIA_NAMES = {"play-pause": "Abspielen/Pause", "weiter": "Nächster Titel", "zurueck": "Voriger Titel",
               "stopp": "Stopp"}
VOLUME_NAMES = {"lauter": "Lauter", "leiser": "Leiser", "stumm": "Ton aus/an"}
OBS_NAMES = {"aufnahme": "Aufnahme starten/stoppen", "stream": "Stream starten/stoppen",
             "pause": "Aufnahme pausieren", "replay": "Replay speichern", "replay-an": "Replay-Puffer an/aus",
             "szene": "Szene wechseln", "stumm": "Quelle stumm/laut"}
BRIGHT_NAMES = {"hoch": "Heller", "runter": "Dunkler"}


def describe(action, pages=()):
    """Kurze Beschreibung für den Editor."""
    a = action or {}
    t = a.get("typ", "keine")
    if t == "app":
        return "Startet " + apps.name_of(a.get("app", "")) if a.get("app") else "Programm wählen"
    if t == "befehl":
        return a.get("befehl") or "Befehl eintragen"
    if t == "webseite":
        return a.get("url") or "Adresse eintragen"
    if t == "tasten":
        return german(a.get("tasten", "")) or "Kürzel aufnehmen"
    if t == "text":
        return (a.get("text") or "Text eintragen")[:40]
    if t == "medien":
        return MEDIA_NAMES.get(a.get("was"), "")
    if t == "lautstaerke":
        return VOLUME_NAMES.get(a.get("was"), "")
    if t == "mikrofon":
        return "Mikrofon stumm/an"
    if t == "obs":
        extra = f" „{a.get('name')}“" if a.get("name") and a.get("was") in ("szene", "stumm") else ""
        return OBS_NAMES.get(a.get("was"), "OBS") + extra
    if t == "sound":
        return (a.get("datei") or "Ton wählen").rsplit("/", 1)[-1]
    if t == "seite":
        i = a.get("seite", 0)
        return "Öffnet „" + pages[i] + "“" if isinstance(i, int) and 0 <= i < len(pages) else "Seite wählen"
    if t == "zurueck":
        return "Zur vorigen Seite"
    if t == "helligkeit":
        return BRIGHT_NAMES.get(a.get("was"), "")
    return "Keine Aktion"


def _clean_env():
    """Umgebung für gestartete Programme: nichts vom unsichtbaren Dienst weitergeben."""
    env = dict(os.environ)
    if env.get("QT_QPA_PLATFORM") == "offscreen":
        env.pop("QT_QPA_PLATFORM")
    for key in ("PYTHONPATH", "QT_QUICK_BACKEND"):
        env.pop(key, None)
    return env


def _spawn(argv):
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, env=_clean_env())
        return True
    except OSError:
        return False


class Runner:
    """Führt Aktionen aus (im Dienst und für „Taste testen“ im Editor)."""

    def __init__(self):
        self.keyboard = Keyboard()

    def run(self, action, cfg):
        """Gibt "" (ok) oder eine Fehlermeldung zurück."""
        a = action or {}
        t = a.get("typ", "keine")
        try:
            if t == "app":
                path, _entry = apps.find(a.get("app", ""))
                if not path:
                    return "Programm nicht gefunden"
                return "" if _spawn(["gio", "launch", str(path)]) else "Programm ließ sich nicht starten"
            if t == "befehl":
                cmd = (a.get("befehl") or "").strip()
                return "" if cmd and _spawn(["sh", "-c", cmd]) else "Kein Befehl"
            if t == "webseite":
                url = (a.get("url") or "").strip()
                if url and "://" not in url:
                    url = "https://" + url
                # im Creative Browser öffnen (sonst im eingestellten Standardbrowser)
                opener = ["creative-browser", url] if shutil.which("creative-browser") else ["xdg-open", url]
                return "" if url and _spawn(opener) else "Keine Adresse"
            if t == "tasten":
                return "" if self.keyboard.press(a.get("tasten", "")) else self.keyboard.error
            if t == "text":
                return "" if self.keyboard.paste_text(a.get("text", "")) else self.keyboard.error
            if t == "medien":
                return "" if self.keyboard.press(MEDIA.get(a.get("was"), "playpause")) else self.keyboard.error
            if t == "lautstaerke":
                return self._volume(a.get("was"))
            if t == "mikrofon":
                return "" if _spawn(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]) else "wpctl fehlt"
            if t == "obs":
                obs.run(cfg.get("obs") or {}, a.get("was", "aufnahme"), a.get("name", ""))
                return ""
            if t == "sound":
                player = shutil.which("pw-play") or shutil.which("paplay")
                if not player or not a.get("datei"):
                    return "Kein Ton gewählt"
                return "" if _spawn([player, a["datei"]]) else "Ton ließ sich nicht abspielen"
        except obs.ObsError as exc:
            return str(exc)
        except (OSError, KeyError, ValueError) as exc:
            return str(exc)
        return ""

    def _volume(self, was):
        # Lautstärketasten: KDE zeigt dabei die gewohnte Anzeige; ohne virtuelle Tastatur über wpctl
        key = {"lauter": "volumeup", "leiser": "volumedown", "stumm": "mute"}.get(was)
        if key and self.keyboard.press(key):
            return ""
        args = {"lauter": ["set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+"],
                "leiser": ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"],
                "stumm": ["set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]}.get(was)
        return "" if args and _spawn(["wpctl"] + args) else "Lautstärke ließ sich nicht ändern"
