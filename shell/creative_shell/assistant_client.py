"""Verbindung der Taskleiste zum Sprachassistenten (creative-assistant).

Der Assistent läuft als eigener Dienst; hier kommen sein Zustand und der
Mikrofon-Pegel an (für den kleinen Visualizer im Tray), und Klicks gehen zurück.
"""

import json
import os
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalSocket


def socket_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/creative-{os.getuid()}"
    return str(Path(base) / "creative-assistant.sock")


class AssistantClient(QObject):
    changed = Signal()
    levelChanged = Signal()
    spoke = Signal()          # neue Antwort → Sprechblase zeigen

    def __init__(self, parent=None):
        super().__init__(parent)
        self._s = {}
        self._level = 0.0
        self._buf = b""
        self._sock = QLocalSocket(self)
        self._sock.readyRead.connect(self._read)
        self._sock.disconnected.connect(self._lost)
        self._sock.errorOccurred.connect(lambda _e: self._lost())
        self._retry = QTimer(self)
        self._retry.setInterval(3000)
        self._retry.timeout.connect(self._connect)
        self._decay = QTimer(self)
        self._decay.setInterval(80)
        self._decay.timeout.connect(self._fade)
        self._decay.start()
        self._connect()

    def _connect(self):
        if self._sock.state() == QLocalSocket.LocalSocketState.UnconnectedState:
            self._sock.connectToServer(socket_path())
            if self._sock.waitForConnected(150):
                self._retry.stop()
            else:
                self._retry.start()

    def _lost(self):
        if self._s:
            self._s = {}
            self.changed.emit()
        self._retry.start()

    def _read(self):
        self._buf += self._sock.readAll().data()
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            try:
                msg = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if msg.get("type") == "level":
                self._level = float(msg.get("level", 0))
                self.levelChanged.emit()
            elif msg.get("type") == "state":
                old_answer = self._s.get("answer", "")
                old_state = self._s.get("state", "")
                self._s = msg
                self.changed.emit()
                if (msg.get("answer") and msg.get("answer") != old_answer) or \
                   (msg.get("state") == "listening" and old_state != "listening"):
                    self.spoke.emit()

    def _fade(self):
        if self._level > 0.01:
            self._level *= 0.75
            self.levelChanged.emit()

    def _send(self, **msg):
        if self._sock.state() == QLocalSocket.LocalSocketState.ConnectedState:
            self._sock.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
            self._sock.flush()

    @Slot()
    def activate(self):
        self._send(cmd="activate")

    @Slot()
    def cancel(self):
        self._send(cmd="cancel")

    @Slot(str)
    def setDevice(self, name):
        self._send(cmd="setDevice", name=name)

    @Slot(str)
    def setVoice(self, vid):
        self._send(cmd="setVoice", id=vid)

    @Slot(bool)
    def setWake(self, on):
        self._send(cmd="setWake", on=on)

    @Slot(str)
    def setCity(self, city):
        self._send(cmd="setCity", city=city)

    @Slot(str)
    def say(self, text):
        self._send(cmd="say", text=text)

    @Slot()
    def stopMusic(self):
        self._send(cmd="stopMusic")

    @Slot()
    def toggleMusic(self):
        self._send(cmd="toggleMusic")

    @Slot()
    def stopTimer(self):
        self._send(cmd="stopTimer")

    @Slot()
    def refresh(self):
        self._send(cmd="refresh")

    def _g(self, key, default):
        return self._s.get(key, default)

    available = Property(bool, lambda self: bool(self._s), notify=changed)
    state = Property(str, lambda self: self._g("state", "off"), notify=changed)
    heard = Property(str, lambda self: self._g("heard", ""), notify=changed)
    answer = Property(str, lambda self: self._g("answer", ""), notify=changed)
    timer = Property(int, lambda self: int(self._g("timer", 0)), notify=changed)
    timerTotal = Property(int, lambda self: int(self._g("timerTotal", 0)), notify=changed)
    music = Property(str, lambda self: self._g("music", ""), notify=changed)
    paused = Property(bool, lambda self: bool(self._g("paused", False)), notify=changed)
    devices = Property("QVariantList", lambda self: self._g("devices", []), notify=changed)
    device = Property(str, lambda self: self._g("device", ""), notify=changed)
    voices = Property("QVariantList", lambda self: self._g("voices", []), notify=changed)
    voice = Property(str, lambda self: self._g("voice", ""), notify=changed)
    wake = Property(bool, lambda self: bool(self._g("wake", False)), notify=changed)
    wakeAvailable = Property(bool, lambda self: bool(self._g("wakeAvailable", False)), notify=changed)
    city = Property(str, lambda self: self._g("city", ""), notify=changed)
    level = Property(float, lambda self: self._level, notify=levelChanged)
