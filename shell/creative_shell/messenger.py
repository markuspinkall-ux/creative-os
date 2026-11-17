"""Messenger in Tray und Fenster: spricht über einen Unix-Socket mit dem Dienst orbit-messenger.

Der Dienst (messenger/daemon, systemd: orbit-messenger.service) hält Verbindungen, Kontakte und die
Warteschlange; dieses Modell zeigt nur an und schickt Befehle (JSON-Zeilen).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalSocket


def socket_path():
    env = os.environ.get("ORBIT_MESSENGER_SOCKET")
    if env:
        return env
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return str(Path(base) / "orbit-messenger.sock")


def initials(name):
    name = (name or "?").strip()
    return (name[:1] or "?").upper()


COLORS = ["#8fb3ff", "#6fdcc0", "#ffb07a", "#c3a6ff", "#f2a7c3", "#9fd36f"]


def color_for(orbit_id):
    return COLORS[sum(ord(ch) for ch in (orbit_id or "")) % len(COLORS)]


def clock(ts_ms):
    """Uhrzeit für heute, sonst Datum."""
    import time
    if not ts_ms:
        return ""
    t = time.localtime(ts_ms / 1000)
    now = time.localtime()
    if (t.tm_year, t.tm_yday) == (now.tm_year, now.tm_yday):
        return time.strftime("%H:%M", t)
    if now.tm_yday - t.tm_yday == 1 and t.tm_year == now.tm_year:
        return "gestern"
    return time.strftime("%d.%m.", t)


STATE_LABEL = {"queued": "wartet", "delivered": "zugestellt", "read": "gelesen"}


class MessengerModel(QObject):
    changed = Signal()
    messagesChanged = Signal()
    errorChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = {}
        self._connected = False
        self._chat = ""
        self._messages = []
        self._error = ""
        self._req = 0
        self._pending = {}
        self._buf = b""
        self._sock = QLocalSocket(self)
        self._sock.connected.connect(self._on_connected)
        self._sock.disconnected.connect(self._on_disconnected)
        self._sock.readyRead.connect(self._on_ready)
        self._sock.errorOccurred.connect(lambda _e: self._on_disconnected())
        self._retry = QTimer(self)
        self._retry.setInterval(3000)
        self._retry.timeout.connect(self._connect)
        self._retry.start()
        QTimer.singleShot(300, self._connect)

    # ---- Verbindung zum Dienst ----------------------------------------------------------------
    def _connect(self):
        if self._sock.state() == QLocalSocket.LocalSocketState.UnconnectedState:
            self._sock.connectToServer(socket_path())

    def _on_connected(self):
        self._connected = True
        self._call({"cmd": "state"}, self._take_state)
        if self._chat:
            self.openChat(self._chat)
        self.changed.emit()

    def _on_disconnected(self):
        if self._connected:
            self._connected = False
            self.changed.emit()

    def _on_ready(self):
        self._buf += bytes(self._sock.readAll())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            if msg.get("ev") == "changed":
                self._take_state(msg.get("state") or {})
                if self._chat:
                    self._load_messages()
                continue
            cb = self._pending.pop(msg.get("re"), None)
            if not msg.get("ok"):
                self._set_error(msg.get("error") or "Unbekannter Fehler")
            elif cb:
                cb(msg.get("result"))

    def _call(self, obj, callback=None, user=False):
        if not self._connected:
            # Abfragen holt _on_connected nach; nur echte Aktionen melden den Fehler
            if user:
                self._set_error("Der Messenger-Dienst läuft gerade nicht – gleich noch einmal versuchen.")
            return
        self._req += 1
        obj = dict(obj, req=self._req)
        if callback:
            self._pending[self._req] = callback
        self._sock.write((json.dumps(obj) + "\n").encode("utf-8"))
        self._sock.flush()

    def _take_state(self, state):
        if isinstance(state, dict) and "contacts" in state:
            self._state = state
            self.changed.emit()

    def _set_error(self, text):
        self._error = text
        self.errorChanged.emit()

    # ---- Für QML: Zustand -------------------------------------------------------------------------
    def _contacts(self, status):
        out = []
        for c in self._state.get("contacts", []):
            if status and c.get("status") != status:
                continue
            last = c.get("last") or {}
            preview = last.get("text", "")
            if last.get("me"):
                preview = "Du: " + preview
            out.append({
                "id": c.get("id", ""), "name": c.get("name", ""), "status": c.get("status", ""),
                "online": bool(c.get("online")), "unread": int(c.get("unread") or 0),
                "preview": preview or ("Anfrage gesendet – wartet auf Annahme" if c.get("status") == "outgoing"
                                       else "Noch keine Nachrichten"),
                "time": clock(last.get("ts") or c.get("since")),
                "initial": initials(c.get("name")), "color": color_for(c.get("id")),
                "fingerprint": c.get("fingerprint", ""),
            })
        return out

    def _me(self):
        return self._state.get("me") or {}

    available = Property(bool, lambda self: shutil.which("orbit-messenger") is not None
                         or bool(os.environ.get("ORBIT_MESSENGER_SOCKET")), constant=True)
    connected = Property(bool, lambda self: self._connected, notify=changed)
    ready = Property(bool, lambda self: bool(self._state.get("ready")), notify=changed)
    myId = Property(str, lambda self: self._me().get("id", ""), notify=changed)
    myName = Property(str, lambda self: self._me().get("name", ""), notify=changed)
    unread = Property(int, lambda self: int(self._state.get("unread") or 0), notify=changed)
    queued = Property(int, lambda self: int(self._state.get("queued") or 0), notify=changed)
    dnd = Property(bool, lambda self: bool(self._state.get("dnd")), notify=changed)
    contacts = Property("QVariantList", lambda self: self._contacts("accepted") + self._contacts("outgoing"),
                        notify=changed)
    requests = Property("QVariantList", lambda self: self._contacts("incoming"), notify=changed)
    error = Property(str, lambda self: self._error, notify=errorChanged)

    def _chat_info(self):
        for c in self._contacts(""):
            if c["id"] == self._chat:
                return c
        return {}

    chat = Property(str, lambda self: self._chat, notify=messagesChanged)
    chatInfo = Property("QVariantMap", lambda self: self._chat_info(), notify=changed)
    messages = Property("QVariantList", lambda self: self._messages, notify=messagesChanged)

    # ---- Für QML: Befehle -------------------------------------------------------------------------
    @Slot()
    def clearError(self):
        self._set_error("")

    @Slot(str)
    def setup(self, name):
        self._set_error("")
        self._call({"cmd": "setup", "name": name}, self._take_state, user=True)

    @Slot(str)
    def add(self, orbit_id):
        self._set_error("")
        self._call({"cmd": "add", "id": orbit_id.strip().lower()}, self._take_state, user=True)

    @Slot(str)
    def accept(self, orbit_id):
        self._call({"cmd": "accept", "id": orbit_id}, self._take_state, user=True)

    @Slot(str)
    def decline(self, orbit_id):
        self._call({"cmd": "decline", "id": orbit_id}, self._take_state, user=True)

    @Slot(str)
    def remove(self, orbit_id):
        if orbit_id == self._chat:
            self._chat = ""
            self._messages = []
            self.messagesChanged.emit()
        self._call({"cmd": "remove", "id": orbit_id}, self._take_state, user=True)

    @Slot(str, str)
    def send(self, orbit_id, text):
        if text.strip():
            self._call({"cmd": "send", "id": orbit_id, "text": text}, lambda _r: self._load_messages(), user=True)

    @Slot(bool)
    def setDnd(self, on):
        self._call({"cmd": "dnd", "on": bool(on)}, self._take_state, user=True)

    @Slot(str)
    def openChat(self, orbit_id):
        self._chat = orbit_id
        self._messages = []
        self.messagesChanged.emit()
        self._load_messages()
        self._call({"cmd": "read", "id": orbit_id}, self._take_state)

    @Slot(str, bool)
    def setVisibleChat(self, orbit_id, focused):
        """Fenster meldet, welcher Chat gerade zu sehen ist – dafür keine Meldung, gleich gelesen."""
        self._call({"cmd": "ui", "id": orbit_id, "focused": bool(focused)})

    def _load_messages(self):
        chat = self._chat
        if not chat:
            return

        def take(result):
            if chat != self._chat or not isinstance(result, list):
                return
            msgs = []
            for m in result:
                msgs.append({
                    "mid": m.get("mid", ""), "me": bool(m.get("me")), "text": m.get("text", ""),
                    "time": clock(m.get("ts")),
                    "state": m.get("state", ""), "stateLabel": STATE_LABEL.get(m.get("state", ""), ""),
                })
            self._messages = msgs
            self.messagesChanged.emit()
        self._call({"cmd": "messages", "id": chat}, take)

    @Slot()
    def copyId(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self.myId)

    @Slot()
    @Slot(str)
    def openWindow(self, orbit_id=""):
        args = ["orbit-messenger-window"] + ([orbit_id] if orbit_id else [])
        subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
