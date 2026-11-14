"""Tastenkürzel über eine virtuelle Tastatur (uinput) – funktioniert unter Wayland in jedem Programm.

Kürzel werden als Text gespeichert, z. B. "ctrl+shift+m" oder "meta+l". Buchstaben sind die
Zeichen auf der deutschen Tastatur: "z" drückt die Taste mit dem Z (auf der US-Belegung „Y“).
"""

import os
import subprocess
import time

try:
    from evdev import UInput, ecodes
except ImportError:  # python3-evdev fehlt
    UInput = ecodes = None

MODS = {"ctrl": "KEY_LEFTCTRL", "shift": "KEY_LEFTSHIFT", "alt": "KEY_LEFTALT",
        "altgr": "KEY_RIGHTALT", "meta": "KEY_LEFTMETA"}
NAMED = {
    "enter": "KEY_ENTER", "esc": "KEY_ESC", "tab": "KEY_TAB", "space": "KEY_SPACE",
    "backspace": "KEY_BACKSPACE", "delete": "KEY_DELETE", "insert": "KEY_INSERT",
    "home": "KEY_HOME", "end": "KEY_END", "pageup": "KEY_PAGEUP", "pagedown": "KEY_PAGEDOWN",
    "up": "KEY_UP", "down": "KEY_DOWN", "left": "KEY_LEFT", "right": "KEY_RIGHT",
    "print": "KEY_SYSRQ", "pause": "KEY_PAUSE",
    "playpause": "KEY_PLAYPAUSE", "next": "KEY_NEXTSONG", "previous": "KEY_PREVIOUSSONG",
    "stop": "KEY_STOPCD", "volumeup": "KEY_VOLUMEUP", "volumedown": "KEY_VOLUMEDOWN",
    "mute": "KEY_MUTE", "micmute": "KEY_MICMUTE",
    "minus": "KEY_SLASH", "plus": "KEY_RIGHTBRACE", "comma": "KEY_COMMA", "period": "KEY_DOT",
}
GERMAN = {"MODS": {"ctrl": "Strg", "shift": "Umschalt", "alt": "Alt", "altgr": "AltGr", "meta": "Windows"},
          "enter": "Eingabe", "esc": "Esc", "tab": "Tab", "space": "Leertaste", "backspace": "Rücktaste",
          "delete": "Entf", "insert": "Einfg", "home": "Pos1", "end": "Ende", "pageup": "Bild↑",
          "pagedown": "Bild↓", "up": "↑", "down": "↓", "left": "←", "right": "→", "print": "Druck",
          "pause": "Pause", "playpause": "Wiedergabe", "next": "Nächster Titel", "previous": "Voriger Titel",
          "stop": "Stopp", "volumeup": "Lauter", "volumedown": "Leiser", "mute": "Stumm",
          "micmute": "Mikro stumm", "minus": "-", "plus": "+", "comma": ",", "period": "."}


def _layout():
    return (os.environ.get("XKB_DEFAULT_LAYOUT") or "de").split(",")[0]


def code_for(token):
    """evdev-Name einer Taste (oder None)."""
    t = token.strip().lower()
    if t in MODS:
        return MODS[t]
    if t in NAMED:
        return NAMED[t]
    if len(t) == 1 and "a" <= t <= "z":
        if _layout() == "de" and t in "yz":      # QWERTZ: Y und Z liegen vertauscht
            t = "z" if t == "y" else "y"
        return "KEY_" + t.upper()
    if len(t) == 1 and t.isdigit():
        return "KEY_" + t
    if t.startswith("f") and t[1:].isdigit() and 1 <= int(t[1:]) <= 24:
        return "KEY_" + t.upper()
    return None


def parse(combo):
    tokens = [t for t in (combo or "").replace(" ", "").split("+") if t]
    codes = [code_for(t) for t in tokens]
    return None if not codes or None in codes else codes


def german(combo):
    """„ctrl+shift+m“ → „Strg + Umschalt + M“"""
    out = []
    for t in (combo or "").split("+"):
        t = t.strip().lower()
        if not t:
            continue
        out.append(GERMAN["MODS"].get(t) or GERMAN.get(t) or t.upper())
    return " + ".join(out)


class Keyboard:
    """Eine virtuelle Tastatur für die ganze Laufzeit (anlegen dauert kurz)."""

    def __init__(self):
        self._ui = None
        self.error = ""

    def _device(self):
        if self._ui is not None:
            return self._ui
        if UInput is None:
            self.error = "python3-evdev fehlt"
            return None
        names = set(MODS.values()) | set(NAMED.values()) \
            | {f"KEY_{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"} \
            | {f"KEY_F{i}" for i in range(1, 25)}
        codes = sorted({getattr(ecodes, n) for n in names if hasattr(ecodes, n)})
        try:
            self._ui = UInput({ecodes.EV_KEY: codes}, name="Creative Deck")
        except (OSError, PermissionError) as exc:
            self.error = f"Virtuelle Tastatur nicht verfügbar ({exc})"
            return None
        time.sleep(0.3)   # bis der Compositor das neue Gerät kennt
        return self._ui

    def press(self, combo):
        codes = parse(combo)
        if not codes:
            self.error = f"Unbekanntes Tastenkürzel: {combo}"
            return False
        ui = self._device()
        if ui is None:
            return False
        nums = [getattr(ecodes, c) for c in codes]
        for n in nums:
            ui.write(ecodes.EV_KEY, n, 1)
        ui.syn()
        time.sleep(0.02)
        for n in reversed(nums):
            ui.write(ecodes.EV_KEY, n, 0)
        ui.syn()
        return True

    def paste_text(self, text):
        """Text über die Zwischenablage einfügen (klappt mit jeder Tastaturbelegung)."""
        try:
            subprocess.run(["wl-copy", "--", text], timeout=3, check=True)
        except (OSError, subprocess.SubprocessError):
            self.error = "wl-copy fehlt"
            return False
        time.sleep(0.05)
        return self.press("ctrl+v")

    def close(self):
        if self._ui is not None:
            try:
                self._ui.close()
            except OSError:
                pass
            self._ui = None
