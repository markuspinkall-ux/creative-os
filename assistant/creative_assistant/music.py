"""Musik für den Sprachassistenten – über den offiziellen YouTube-Music-Player.

„Spiel …“ öffnet im Creative Player die offizielle YouTube-Music-Seite mit
der Suche und startet das erste Ergebnis. Pause, Weiter und Stopp steuern
diesen Player. Es wird nichts heruntergeladen und kein Fremd-Abspieler benutzt.
"""

import shutil
import subprocess


def _player(*args):
    try:
        subprocess.Popen(["creative-player", *args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


class MusicPlayer:
    def __init__(self, on_change):
        self._on_change = on_change
        self._title = ""
        self._paused = False
        self._ducked = False

    @staticmethod
    def available():
        return bool(shutil.which("creative-player"))

    def play(self, query, index=1):
        if not _player("--ytmusic", query):
            return None
        self._title, self._paused = query, False
        self._on_change()
        return query

    def playing(self):
        return bool(self._title)

    def stop(self, notify=True):
        if self._title:
            _player("--ytmusic-cmd", "pause")
        self._title = ""
        if notify:
            self._on_change()

    def pause(self):
        _player("--ytmusic-cmd", "pause")
        self._paused = True
        self._on_change()

    def resume(self):
        _player("--ytmusic-cmd", "play")
        self._paused = False
        self._on_change()

    def toggle(self):
        self.resume() if self._paused else self.pause()

    def change_volume(self, delta):
        # Lautstärke des Players über die Systemsteuerung des Tons (alle Ausgaben des Players)
        try:
            out = subprocess.run(["pactl", "list", "sink-inputs"], capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return
        idx = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Sink Input #"):
                idx = line.split("#", 1)[1]
            elif idx and "Creative Player" in line:
                subprocess.run(["pactl", "set-sink-input-volume", idx, f"{'+' if delta > 0 else '-'}{abs(delta)}%"],
                               capture_output=True, timeout=3)
                idx = None

    def next(self):
        if not self._title:
            return None
        _player("--ytmusic-cmd", "next")
        return self._title

    def duck(self, on):
        """Beim Zuhören kurz anhalten, danach weiter (nur wenn wir selbst angehalten haben)."""
        if not self._title or self._paused or on == self._ducked:
            return
        self._ducked = on
        _player("--ytmusic-cmd", "pause" if on else "play")

    @property
    def title(self):
        return self._title

    @property
    def paused(self):
        return self._paused
