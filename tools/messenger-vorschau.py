"""Bildschirmfotos vom echten Messenger-Fenster und Tray-Menü gegen einen nachgebauten Dienst.
   QT_QPA_PLATFORM=offscreen python3 tools/messenger-vorschau.py ausgabe-ordner [--neu]"""
import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shell"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "messenger-vorschau")
OUT.mkdir(parents=True, exist_ok=True)
NEW = "--neu" in sys.argv
SOCK = os.path.join(tempfile.mkdtemp(), "orbit-messenger.sock")
os.environ["ORBIT_MESSENGER_SOCKET"] = SOCK

now = int(time.time() * 1000)
MIN = 60_000
CHATS = {
    "jonas.gibeonos4417": [
        {"mid": "1", "me": False, "text": "Hast du das Update schon drauf? Die Rakete beim Start sieht richtig gut aus.", "ts": now - 14 * MIN, "state": ""},
        {"mid": "2", "me": True, "text": "Ja, läuft seit heute früh. Broadcast kann jetzt auch 2K.", "ts": now - 12 * MIN, "state": "read"},
        {"mid": "3", "me": False, "text": "Nice, dann teste ich das heute Abend mit meiner Brio.", "ts": now - 11 * MIN, "state": ""},
        {"mid": "4", "me": True, "text": "Sag Bescheid, wie es läuft. Ich trag dich als Orbit-Pilot ein.", "ts": now - 9 * MIN, "state": "read"},
        {"mid": "5", "me": False, "text": "Deal. Schick mir den Link zum Discord?", "ts": now - 2 * MIN, "state": ""},
    ],
    "lena.gibeonos0932": [
        {"mid": "6", "me": True, "text": "Hier ist das Spiel von gestern – sag mir, ob die Landung klappt!", "ts": now - 5 * MIN, "state": "queued"},
    ],
}


def state():
    if NEW:
        return {"ready": False, "me": None, "online": False, "dnd": False, "unread": 0, "queued": 0, "contacts": []}
    def last(cid):
        m = CHATS.get(cid, [])[-1:] or [None]
        return m[0]
    return {
        "ready": True, "me": {"id": "markus.gibeonos2801", "name": "Markus"}, "online": True, "dnd": False,
        "unread": 1, "queued": 1,
        "contacts": [
            {"id": "jonas.gibeonos4417", "name": "Jonas", "status": "accepted", "online": True, "unread": 1,
             "last": last("jonas.gibeonos4417"), "since": now - 86_400_000, "fingerprint": "a31e ced8"},
            {"id": "lena.gibeonos0932", "name": "Lena", "status": "accepted", "online": False, "unread": 0,
             "last": last("lena.gibeonos0932"), "since": now - 86_400_000, "fingerprint": "7c02 19fa"},
            {"id": "tim.gibeonos7710", "name": "tim", "status": "outgoing", "online": False, "unread": 0,
             "last": None, "since": now - 3_600_000, "fingerprint": ""},
            {"id": "paul.gibeonos3390", "name": "Paul", "status": "incoming", "online": True, "unread": 0,
             "last": None, "since": now - 300_000, "fingerprint": "e94b 0d21"},
        ],
    }


def serve():
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(4)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=client, args=(conn,), daemon=True).start()


def client(conn):
    buf = b""
    while True:
        data = conn.recv(65536)
        if not data:
            return
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            req = json.loads(line)
            cmd = req.get("cmd")
            result = CHATS.get(req.get("id"), []) if cmd == "messages" else ({"ok": True} if cmd == "ui" else state())
            conn.sendall((json.dumps({"re": req.get("req"), "ok": True, "result": result}) + "\n").encode())


threading.Thread(target=serve, daemon=True).start()
time.sleep(0.3)

from PySide6.QtCore import QObject, QTimer, QUrl, Slot          # noqa: E402
from PySide6.QtGui import QGuiApplication                       # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine                 # noqa: E402
from PySide6.QtQuick import QQuickView                          # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle                # noqa: E402

from creative_shell.messenger import MessengerModel             # noqa: E402

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
QML = ROOT / "shell" / "creative_shell" / "qml"
model = MessengerModel()


class FakeShell(QObject):
    @Slot()
    def closePopups(self):
        pass


fake_shell = FakeShell()
engine = QQmlApplicationEngine()
engine.addImportPath(str(QML))
engine.rootContext().setContextProperty("messenger", model)
engine.rootContext().setContextProperty("startChat", "" if NEW else "jonas.gibeonos4417")
engine.load(QUrl.fromLocalFile(str(QML / "messenger" / "MessengerWindow.qml")))
win = engine.rootObjects()[0]

tray = QQuickView()
tray.engine().addImportPath(str(QML))
tray.rootContext().setContextProperty("messenger", model)
tray.rootContext().setContextProperty("shell", fake_shell)
tray.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
tray.resize(430, 620)
tray.setColor("#12151b")
tray.setSource(QUrl.fromLocalFile(str(QML / "surfaces" / "MessengerMenu.qml")))
tray.show()

prefix = "neu-" if NEW else ""


def shot1():
    win.grabWindow().save(str(OUT / f"{prefix}fenster.png"))
    tray.grabWindow().save(str(OUT / f"{prefix}tray.png"))
    if NEW:
        app.quit()
        return
    win.setProperty("addOpen", True)
    QTimer.singleShot(800, shot2)


def shot2():
    win.grabWindow().save(str(OUT / "kontakt.png"))
    app.quit()


QTimer.singleShot(int(os.environ.get("CREATIVE_SCREENSHOT_DELAY", "2500")), shot1)
QTimer.singleShot(20000, app.quit)
app.exec()
print("Fotos:", sorted(p.name for p in OUT.iterdir()))
