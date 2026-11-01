"""Musik von YouTube direkt abspielen – nur der Ton, ohne Browser.

yt-dlp sucht den passenden Titel, mpv spielt ihn im Hintergrund ab.
Gesteuert wird mpv über seine Steuer-Schnittstelle (Pause, Lautstärke …).
"""

import json
import os
import shutil
import socket
import subprocess
import threading
from pathlib import Path


def _sock_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/creative-{os.getuid()}"
    Path(base).mkdir(parents=True, exist_ok=True)
    return str(Path(base) / "creative-assistant-mpv.sock")


class MusicPlayer:
    def __init__(self, on_change):
        self._proc = None
        self._title = ""
        self._query = ""
        self._index = 1
        self._volume = 70
        self._paused = False
        self._ducked = False
        self._on_change = on_change
        self._lock = threading.Lock()

    @staticmethod
    def available():
        return bool(shutil.which("mpv") and shutil.which("yt-dlp"))

    # ---- Suchen ---------------------------------------------------------------
    def find(self, query, index=1):
        """Liefert (titel, url) für den index-ten Treffer."""
        out = subprocess.run(
            ["yt-dlp", "--no-warnings", "--flat-playlist", "--print", "%(title)s\t%(webpage_url)s",
             f"ytsearch{index}:{query} audio"],
            capture_output=True, text=True, timeout=25,
        ).stdout.strip().splitlines()
        if len(out) < index:
            return None
        title, _, url = out[index - 1].partition("\t")
        return title.strip(), url.strip()

    def play(self, query, index=1):
        found = self.find(query, index)
        if not found:
            return None
        title, url = found
        self.stop(notify=False)
        sock = _sock_path()
        try:
            os.unlink(sock)
        except OSError:
            pass
        with self._lock:
            self._proc = subprocess.Popen(
                ["mpv", "--no-video", "--no-terminal", "--really-quiet", f"--volume={self._volume}",
                 f"--input-ipc-server={sock}", "--ytdl-format=bestaudio/best",
                 "--title=Creative Assistent", url],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._title, self._query, self._index, self._paused = title, query, index, False
        threading.Thread(target=self._watch, args=(self._proc,), daemon=True).start()
        self._on_change()
        return title

    def _watch(self, proc):
        proc.wait()
        with self._lock:
            if self._proc is proc:
                self._proc = None
                self._title = ""
        self._on_change()

    # ---- Steuern --------------------------------------------------------------
    def _send(self, *command):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(1.5)
                s.connect(_sock_path())
                s.sendall((json.dumps({"command": list(command)}) + "\n").encode())
        except OSError:
            pass

    def playing(self):
        return self._proc is not None and self._proc.poll() is None

    def stop(self, notify=True):
        with self._lock:
            proc, self._proc = self._proc, None
            self._title = ""
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if notify:
            self._on_change()

    def pause(self):
        if self.playing():
            self._paused = True
            self._send("set_property", "pause", True)
            self._on_change()

    def resume(self):
        if self.playing():
            self._paused = False
            self._send("set_property", "pause", False)
            self._on_change()

    def toggle(self):
        self.resume() if self._paused else self.pause()

    def change_volume(self, delta):
        self._volume = max(5, min(130, self._volume + delta))
        self._send("set_property", "volume", self._volume)

    def next(self):
        if self._query:
            return self.play(self._query, self._index + 1)
        return None

    def duck(self, on):
        """Beim Zuhören leiser stellen."""
        if self.playing() and on != self._ducked:
            self._ducked = on
            self._send("set_property", "volume", max(5, self._volume // 4) if on else self._volume)

    @property
    def title(self):
        return self._title if self.playing() else ""

    @property
    def paused(self):
        return self._paused
