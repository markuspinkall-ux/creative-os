"""Studio (Gibeon OS) vom Stream Deck steuern: Live, Aufnahme, Szenen, Stumm.

Studio lauscht auf einem lokalen Socket ($XDG_RUNTIME_DIR/gibeon-studio.sock) auf einzelne
Textzeilen, z. B. „szene Pause“. Läuft Studio nicht, wird es gestartet; der Befehl folgt, sobald
es bereit ist."""

import os
import socket
import subprocess
import time
from pathlib import Path

NAMES = {"live": "Live gehen/beenden", "aufnahme": "Aufnahme starten/stoppen", "szene": "Szene wechseln",
         "naechste": "Nächste Szene", "mikrofon": "Mikrofon stumm/an", "desktop": "Desktop-Ton stumm/an"}


class StudioError(Exception):
    pass


def socket_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return str(Path(base) / "gibeon-studio.sock")


def command(was, name=""):
    if was == "szene":
        if not name.strip():
            raise StudioError("Welche Szene? Namen eintragen (oder 1, 2, 3 …).")
        return f"szene {name.strip()}"
    if was in ("live", "aufnahme", "naechste"):
        return was
    if was in ("mikrofon", "desktop"):
        return "stumm " + {"mikrofon": "mic", "desktop": "desktop"}[was]
    raise StudioError("Unbekannte Studio-Aktion")


def _send(line, timeout=2.0):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(socket_path())
        s.sendall(line.encode() + b"\n")
        try:
            return s.recv(512).decode("utf-8", "replace").strip()
        except socket.timeout:
            return ""
    finally:
        s.close()


def run(was, name="", start=True):
    line = command(was, name)
    try:
        answer = _send(line)
    except OSError:
        if not start:
            raise StudioError("Studio läuft nicht.")
        try:
            subprocess.Popen(["gibeon-studio"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise StudioError("Studio ließ sich nicht starten.") from exc
        deadline = time.monotonic() + 15
        while True:
            time.sleep(0.5)
            try:
                answer = _send(line)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise StudioError("Studio antwortet nicht.")
    if answer.startswith("fehler"):
        raise StudioError(answer.partition(" ")[2] or "Studio konnte das nicht.")
    return answer
