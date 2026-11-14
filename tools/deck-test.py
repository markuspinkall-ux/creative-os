"""Creative Deck ohne echtes Gerät prüfen: Einstellungen, Tastenkürzel, OBS-Protokoll und der
Hintergrunddienst mit einem nachgebauten Stream Deck (Seiten, Zurück, Helligkeit, Befehl,
Ein-/Ausstecken, Neuladen der Einstellungen). Legt ein Foto der Tasten ab.

    QT_QPA_PLATFORM=offscreen python3 tools/deck-test.py [fotoordner]
"""
import base64
import hashlib
import io
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(home)
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
os.environ["XDG_RUNTIME_DIR"] = str(home / "run")
os.environ["XKB_DEFAULT_LAYOUT"] = "de"
fotos = Path(sys.argv[1]) if len(sys.argv) > 1 else None
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "deck"))
sys.path.insert(0, str(ROOT / "shell"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv)

from creative_deck import actions, config, keys, obs  # noqa: E402
from creative_deck.editor import shortcut_from_qt  # noqa: E402

ok = []


def check(cond, what):
    if not cond:
        raise SystemExit("FEHLER: " + what)
    ok.append(what)


# ---- Einstellungen -------------------------------------------------------------------------
cfg = config.load()
check(cfg["seiten"][0]["name"] == "Start" and "4" in cfg["seiten"][0]["tasten"], "Grundeinstellung mit Beispielen")
cfg["helligkeit"] = 250
config.save(cfg)
check(config.load()["helligkeit"] == 100, "Helligkeit wird begrenzt")
old = config.default_config()
old["seiten"][0]["tasten"]["1"] = {"text": "Brave", "symbol": "app:brave-browser.desktop", "farbe": "",
                                   "aktion": {"typ": "app", "app": "brave-browser.desktop"}}
config.save(old)
k1 = config.load()["seiten"][0]["tasten"]["1"]
check(k1["aktion"]["app"] == "creative-browser.desktop" and k1["text"] == "Browser"
      and k1["symbol"] == "app:creative-browser.desktop", "Brave-Taste wird zum Creative Browser")
config.config_path().write_text("kaputt", encoding="utf-8")
check(config.load()["seiten"], "kaputte Datei → Grundeinstellung")

# ---- Tastenkürzel ----------------------------------------------------------------------------
check(keys.parse("ctrl+shift+m") == ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_M"], "Kürzel lesen")
check(keys.parse("ctrl+z") == ["KEY_LEFTCTRL", "KEY_Y"], "QWERTZ: Z liegt auf KEY_Y")
check(keys.parse("ctrl+banane") is None, "unbekannte Taste abgelehnt")
check(keys.german("ctrl+shift+m") == "Strg + Umschalt + M", "Kürzel auf Deutsch")
mods = (Qt.ControlModifier | Qt.ShiftModifier).value
check(shortcut_from_qt(Qt.Key_M.value, mods) == "ctrl+shift+m", "Kürzel aus dem Editor")
check(shortcut_from_qt(Qt.Key_Control.value, Qt.ControlModifier.value) == "", "nur Strg ist kein Kürzel")
check(shortcut_from_qt(Qt.Key_F5.value, 0) == "f5", "F-Tasten")
check(actions.describe({"typ": "seite", "seite": 1}, ["Start", "OBS"]) == "Öffnet „OBS“", "Beschreibung")

# ---- OBS: nachgebauter obs-websocket-Server --------------------------------------------------
PASSWORD, SALT, CHALLENGE = "geheim", "c2FsdA==", "Y2hhbGxlbmdl"
seen = []


def serve(srv):
    conn, _ = srv.accept()
    data = b""
    while b"\r\n\r\n" not in data:
        data += conn.recv(1024)
    key = [line.split(b": ")[1] for line in data.split(b"\r\n") if line.lower().startswith(b"sec-websocket-key")][0]
    accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")

    def send(obj):
        p = json.dumps(obj).encode()
        conn.sendall(bytes([0x81, len(p)]) + p if len(p) < 126 else bytes([0x81, 126]) + struct.pack(">H", len(p)) + p)

    def recv():
        b1, b2 = conn.recv(2)
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", conn.recv(2))[0]
        mask = conn.recv(4)
        payload = b""
        while len(payload) < n:
            payload += conn.recv(n - len(payload))
        payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        return (b1 & 0x0F), payload

    send({"op": 0, "d": {"rpcVersion": 1, "authentication": {"salt": SALT, "challenge": CHALLENGE}}})
    _, ident = recv()
    ident = json.loads(ident)
    secret = base64.b64encode(hashlib.sha256((PASSWORD + SALT).encode()).digest()).decode()
    expected = base64.b64encode(hashlib.sha256((secret + CHALLENGE).encode()).digest()).decode()
    if ident["d"].get("authentication") != expected:
        conn.sendall(bytes([0x88, 0]))
        conn.close()
        return
    send({"op": 2, "d": {"negotiatedRpcVersion": 1}})
    _, req = recv()
    req = json.loads(req)["d"]
    seen.append((req["requestType"], req.get("requestData")))
    send({"op": 7, "d": {"requestType": req["requestType"], "requestId": req["requestId"],
                         "requestStatus": {"result": True, "code": 100}, "responseData": {}}})
    conn.close()


for request, data in (("aufnahme", ""), ("szene", "Kamera")):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    t = threading.Thread(target=serve, args=(srv,), daemon=True)
    t.start()
    obs.run({"host": "127.0.0.1", "port": port, "passwort": PASSWORD}, request, data)
    t.join(3)
    srv.close()
check(seen == [("ToggleRecord", {}), ("SetCurrentProgramScene", {"sceneName": "Kamera"})], "OBS: Anmeldung und Befehle")
try:
    obs.run({"host": "127.0.0.1", "port": 1, "passwort": ""}, "aufnahme")
    check(False, "OBS nicht erreichbar wird gemeldet")
except obs.ObsError:
    ok.append("OBS nicht erreichbar wird gemeldet")

# ---- Gestartete Programme erben nicht „offscreen“ vom Dienst ----------------------------------------
os.environ["QT_QPA_PLATFORM"] = "offscreen"
probe = home / "env.txt"
actions._spawn(["sh", "-c", f'echo "qpa=${{QT_QPA_PLATFORM:-}}" > {probe}'])
for _ in range(40):
    if probe.exists() and probe.read_text().strip():
        break
    time.sleep(0.05)
check(probe.read_text().strip() == "qpa=", "Programme starten sichtbar (kein offscreen)")

# ---- Dienst mit nachgebautem Stream Deck ------------------------------------------------------
from creative_deck import daemon as dmod  # noqa: E402


class FakeDeck:
    def __init__(self):
        self.images, self.brightness, self.alive, self.cb = {}, None, True, None

    def id(self): return "/dev/hidraw-test"
    def open(self): pass
    def reset(self): pass
    def close(self): pass
    def connected(self): return self.alive
    def deck_type(self): return "Stream Deck MK.2"
    def get_serial_number(self): return "TEST123"
    def key_layout(self): return (3, 5)
    def key_count(self): return 15
    def is_visual(self): return True
    def key_image_format(self): return {"size": (72, 72), "format": "JPEG", "flip": (False, False), "rotation": 0}
    def set_brightness(self, v): self.brightness = v
    def set_key_image(self, k, img): self.images[k] = img
    def set_key_callback(self, cb): self.cb = cb
    def __enter__(self): return self
    def __exit__(self, *a): return False


class FakeManager:
    def __init__(self, decks): self.decks = decks
    def enumerate(self): return list(self.decks)


fake = FakeDeck()
manager = FakeManager([fake])
config.save(config.default_config())
d = dmod.Daemon(manager)
check(not dmod.LIB_ERROR, "Stream-Deck-Bibliothek geladen")
d.poll()
check(len(d.decks) == 1 and len(fake.images) == 15, "Gerät erkannt, alle 15 Tasten gezeichnet")
check(fake.brightness == 70, "Helligkeit gesetzt")
status = config.read_status()
check(status["geraete"][0]["modell"] == "Stream Deck MK.2" and status["geraete"][0]["spalten"] == 5, "Status für den Editor")

if fotos:
    from PIL import Image
    fotos.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (5 * 72 + 6 * 12, 3 * 72 + 4 * 12), (13, 15, 19))
    for k, data in fake.images.items():
        sheet.paste(Image.open(io.BytesIO(bytes(data))), (12 + (k % 5) * 84, 12 + (k // 5) * 84))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.LANCZOS).save(fotos / "tasten-auf-dem-geraet.png")


def press(k):
    fake.cb(fake, k, True)
    fake.cb(fake, k, False)
    d.tick()


press(4)                                   # „OBS“ öffnet Seite 2
check(d.decks["/dev/hidraw-test"].page == 1, "Taste öffnet Seite")
press(0)                                   # „Zurück“
check(d.decks["/dev/hidraw-test"].page == 0, "Zurück zur vorigen Seite")

marker = home / "gedrueckt"
cfg = config.load()
cfg["seiten"][0]["tasten"]["14"] = {"text": "Test", "symbol": "", "farbe": "",
                                    "aktion": {"typ": "befehl", "befehl": f"touch {marker}"}}
cfg["seiten"][0]["tasten"]["13"] = {"text": "Hell", "symbol": "", "farbe": "",
                                    "aktion": {"typ": "helligkeit", "was": "hoch"}}
time.sleep(0.02)
config.save(cfg)
before = dict(fake.images)
d.tick()                                   # neue Einstellungen übernehmen
check(fake.images[14] != before[14], "Änderung aus dem Editor wird übernommen")
press(14)
for _ in range(40):
    if marker.exists():
        break
    time.sleep(0.05)
check(marker.exists(), "Befehl wird ausgeführt")
press(13)
check(fake.brightness == 85, "Helligkeit per Taste")

fake.alive = False
d.poll()
check(not d.decks, "Abziehen wird erkannt")
fake.alive = True
d.poll()
check(len(d.decks) == 1, "Wieder einstecken wird erkannt")
d.close()

print("\n".join("ok  " + w for w in ok))
print(f"Creative Deck: alle {len(ok)} Prüfungen bestanden")
