"""Kleiner Client für obs-websocket 5 (in OBS Studio ab Version 28 eingebaut).

OBS › Werkzeuge › WebSocket-Servereinstellungen: Server aktivieren, Port 4455, Passwort.
Für jede Aktion wird kurz verbunden – das reicht für Tasten und braucht keinen Hintergrund-Thread.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import uuid


class ObsError(Exception):
    pass


class _WebSocket:
    def __init__(self, host, port, timeout=3):
        try:
            self.sock = socket.create_connection((host, int(port)), timeout=timeout)
        except OSError as exc:
            raise ObsError("OBS ist nicht erreichbar – läuft OBS und ist der WebSocket-Server an?") from exc
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
               "Sec-WebSocket-Protocol: obswebsocket.json\r\n\r\n")
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ObsError("OBS hat die Verbindung abgelehnt.")
            head += chunk
        head, self.buf = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ObsError("OBS hat die Verbindung abgelehnt.")

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ObsError("Verbindung zu OBS getrennt.")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        data = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b2 & 0x80 else None
            payload = self._read(n)
            if mask:
                payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
            op = b1 & 0x0F
            if op == 8:
                raise ObsError("OBS hat die Verbindung beendet (Passwort falsch?).")
            if op == 9:                 # Ping → Pong
                self._send(payload, 10)
                continue
            data += payload
            if b1 & 0x80:
                return json.loads(data.decode("utf-8"))

    def _send(self, payload, op=1):
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | op])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        self.sock.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))

    def send(self, obj):
        self._send(json.dumps(obj).encode("utf-8"))

    def close(self):
        try:
            self._send(b"", 8)
            self.sock.close()
        except OSError:
            pass


def _auth(password, salt, challenge):
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def request(settings, request_type, data=None):
    """Eine Anfrage an OBS schicken und die Antwort (responseData) zurückgeben."""
    ws = _WebSocket(settings.get("host") or "localhost", settings.get("port") or 4455)
    try:
        hello = ws.recv()
        ident = {"rpcVersion": 1}
        auth = (hello.get("d") or {}).get("authentication")
        if auth:
            if not settings.get("passwort"):
                raise ObsError("OBS verlangt ein Passwort – in Creative Deck › OBS eintragen.")
            ident["authentication"] = _auth(settings["passwort"], auth["salt"], auth["challenge"])
        ws.send({"op": 1, "d": ident})
        if ws.recv().get("op") != 2:
            raise ObsError("OBS hat die Anmeldung abgelehnt.")
        rid = uuid.uuid4().hex
        ws.send({"op": 6, "d": {"requestType": request_type, "requestId": rid, "requestData": data or {}}})
        while True:
            msg = ws.recv()
            d = msg.get("d") or {}
            if msg.get("op") == 7 and d.get("requestId") == rid:
                status = d.get("requestStatus") or {}
                if not status.get("result"):
                    raise ObsError(status.get("comment") or f"OBS: {request_type} ging nicht.")
                return d.get("responseData") or {}
    finally:
        ws.close()


ACTIONS = {
    "aufnahme": ("ToggleRecord", None),
    "stream": ("ToggleStream", None),
    "replay": ("SaveReplayBuffer", None),
    "replay-an": ("ToggleReplayBuffer", None),
    "pause": ("ToggleRecordPause", None),
    "szene": ("SetCurrentProgramScene", "sceneName"),
    "stumm": ("ToggleInputMute", "inputName"),
}


def run(settings, was, name=""):
    request_type, field = ACTIONS[was]
    if field and not name:
        raise ObsError("Bitte den Namen (Szene oder Quelle wie in OBS) eintragen.")
    return request(settings, request_type, {field: name} if field else None)
