"""KI-Helfer: ein lokales Open-Source-Sprachmodell (Gemma 4, Apache 2.0) als Desktop-Widget.

Alles läuft auf dem eigenen PC: llama.cpp (Vulkan – NVIDIA und AMD) rechnet,
das Modell liegt einmal für alle Konten in /var/lib/creative-ki/modelle.
Für Wissensfragen werden passende Artikel der deutschen Wikipedia als
Hintergrund mitgegeben – das macht die Antworten deutlich verlässlicher.

Der Rechenteil (llama-server) startet erst bei der ersten Frage und beendet
sich nach zehn Minuten Ruhe wieder, damit Spiele den Grafikspeicher bekommen.
"""

import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import config
from .mainthread import post

LIB = Path(os.environ.get("CREATIVE_KI_LIB", "/usr/lib/creative-ki"))
MODELLE = Path(os.environ.get("CREATIVE_KI_MODELLE", "/var/lib/creative-ki/modelle"))
SETUP = "/usr/libexec/creative-ki-setup"
REIHENFOLGE = ("gross", "mittel", "klein")
LEERLAUF_MS = 10 * 60 * 1000
WIKI = "https://de.wikipedia.org/w/api.php"
WIKI_AGENT = "CreativeOS-KI/1.0 (https://github.com/markuspinkall-ux/creative-os)"

SYSTEM = (
    "Du bist der KI-Helfer von Creative OS. Du antwortest immer auf Deutsch, freundlich, "
    "klar und knapp – wie ein gut informierter Freund. Bei Wissensfragen nennst du zuerst "
    "die direkte Antwort in einem Satz und ergänzt dann höchstens drei Sätze Hintergrund. "
    "Wenn du dir nicht sicher bist, sag das ehrlich, statt etwas zu erfinden. "
    "Wenn du E-Mails, Briefe oder Nachrichten formulierst, lieferst du direkt den fertigen "
    "Text mit Betreff (bei E-Mails) und ohne lange Vorrede; Platzhalter in eckigen Klammern. "
    "Nutze einfaches Markdown (fett, Listen) nur, wenn es hilft. Heute ist der {datum}."
)

# Schreibaufträge brauchen kein Nachschlagen
SCHREIBEN = re.compile(
    r"\b(e-?mail|mail|brief|nachricht|schreib|formulier|antwort(e|en)? auf|text für|"
    r"übersetz|einladung|bewerbung|kündigung|glückwunsch|whatsapp|sms|entschuldigung)\w*",
    re.I,
)
FUELL = re.compile(
    r"\b(wer|was|wann|wo|wie|warum|wieso|weshalb|welche[rsmn]?|war|waren|ist|sind|hat|hatte|"
    r"der|die|das|den|dem|des|ein|eine|einer|eines|einem|einen|und|oder|von|im|in|am|an|zu|"
    r"zum|zur|mir|mich|bitte|erklär\w*|sag\w*|weißt|du|kannst|eigentlich|denn|mal|es|gibt)\b",
    re.I,
)


def vram_gb():
    """Größter Grafikspeicher in GB (NVIDIA über nvidia-smi, AMD über sysfs), sonst 0."""
    best = 0.0
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if line.strip().isdigit():
                best = max(best, int(line.strip()) / 1024)
    except (OSError, subprocess.SubprocessError):
        pass
    for f in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
        try:
            best = max(best, int(f.read_text().strip()) / 1024 ** 3)
        except (OSError, ValueError):
            pass
    return best


def modelle():
    try:
        return json.loads((LIB / "modelle.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def empfehlung(liste, vram):
    for key in REIHENFOLGE:
        if key in liste and vram + 0.5 >= liste[key]["vram_gb"]:
            return key
    return "klein"


def installiert(liste):
    """Bestes vorhandenes Modell (vollständig geladen) oder ''."""
    for key in REIHENFOLGE:
        info = liste.get(key)
        if not info:
            continue
        f = MODELLE / info["datei"]
        try:
            if f.stat().st_size == info["groesse"]:
                return key
        except OSError:
            pass
    return ""


def server_binary():
    for p in (LIB / "llama" / "llama-server", Path("/usr/bin/llama-server")):
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


def freier_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def suchbegriff(frage):
    text = re.sub(r"[?!.,;:\"„“]", " ", frage)
    text = FUELL.sub(" ", text)
    return " ".join(text.split())[:120]


def wikipedia(frage, anzahl=2):
    """Kurze Auszüge der passendsten Wikipedia-Artikel: [(titel, text, url)]."""
    begriff = suchbegriff(frage)
    if len(begriff) < 3:
        return []
    params = urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": begriff, "gsrnamespace": 0, "gsrlimit": anzahl,
        "prop": "extracts|info", "inprop": "url", "exintro": 1, "explaintext": 1, "exsentences": 6,
    })
    req = Request(f"{WIKI}?{params}", headers={"User-Agent": WIKI_AGENT})
    with urlopen(req, timeout=5) as r:
        data = json.loads(r.read(256 * 1024))
    pages = sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        text = " ".join(p.get("extract", "").split())
        if len(text) > 60:
            out.append((p["title"], text[:1200], p.get("fullurl") or f"https://de.wikipedia.org/?curid={p['pageid']}"))
    return out


class KiHelfer(QObject):
    changed = Signal()
    messagesChanged = Signal()
    _chunk = Signal(str)
    _done = Signal(str, object)
    _setupLine = Signal(str)
    _setupEnd = Signal(int)

    def __init__(self):
        super().__init__()
        self._settings = config.load()["desktopExtras"]
        self._liste = modelle()
        self._vram = vram_gb()
        self._modell = installiert(self._liste)
        self._wahl = self._settings.get("kiModell") if self._settings.get("kiModell") in self._liste \
            else empfehlung(self._liste, self._vram)
        self._messages = []          # {role: user|assistant, text, quellen: [{titel,url}]}
        self._state = "bereit" if self._modell else "einrichten"
        self._status = ""
        self._progress = 0
        self._proc = None
        self._port = 0
        self._busy = False
        self._stop = threading.Event()
        self._setup = None
        self._chunk.connect(self._on_chunk)
        self._done.connect(self._on_done)
        self._setupLine.connect(self._on_setup_line)
        self._setupEnd.connect(self._on_setup_end)
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(LEERLAUF_MS)
        self._idle.timeout.connect(self.unload)
        app = QGuiApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.unload)
        # Ein anderes Konto hat das Modell vielleicht gerade geladen
        self._poll = QTimer(self)
        self._poll.setInterval(15000)
        self._poll.timeout.connect(self._recheck)
        self._poll.start()

    # ---- Einstellungen -------------------------------------------------------------
    def _save(self, **changes):
        settings = {**config.load()["desktopExtras"], **changes}
        if config.set_value("desktopExtras", settings):
            self._settings = settings
            self.changed.emit()
            return True
        return False

    @Slot(float, float)
    def setPos(self, x, y):
        self._save(kiPos=[max(0, min(1, x)), max(0, min(1, y))])

    def _position(self, axis):
        value = self._settings.get("kiPos")
        if isinstance(value, list) and len(value) == 2 and all(type(n) in (float, int) and 0 <= n <= 1 for n in value):
            return float(value[axis])
        return -1.0

    def setEnabled(self, enabled):
        if not self._save(kiEnabled=bool(enabled)):
            raise ValueError("Die Einstellung konnte nicht gespeichert werden.")
        if not enabled:
            self.unload()

    @Slot()
    def toggle(self):
        try:
            self.setEnabled(not self.enabled)
        except ValueError:
            pass

    @Slot(str)
    def chooseModel(self, key):
        if key in self._liste and not self._setup:
            self._wahl = key
            self._save(kiModell=key)

    def _recheck(self):
        neu = installiert(self._liste)
        if neu != self._modell and self._setup is None:
            self._modell = neu
            if self._state == "einrichten" and neu:
                self._state = "bereit"
            self.changed.emit()

    # ---- Einrichten (Modell laden) ---------------------------------------------------
    @Slot()
    def install(self):
        if self._setup is not None:
            return
        info = self._liste.get(self._wahl)
        if not info:
            self._fail("Die Modellliste fehlt – bitte Creative OS aktualisieren.")
            return
        self._state = "laedt"
        self._progress = 0
        self._status = "Download startet …"
        self.changed.emit()
        argv = ["pkexec", SETUP, "laden", self._wahl] if os.geteuid() != 0 else [SETUP, "laden", self._wahl]
        try:
            self._setup = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except OSError as exc:
            self._setup = None
            self._fail(f"Einrichten nicht möglich: {exc}")
            return

        def lesen(proc):
            for line in proc.stdout:
                post(self._setupLine.emit, line.rstrip("\n"))
            post(self._setupEnd.emit, proc.wait())

        threading.Thread(target=lesen, args=(self._setup,), daemon=True).start()

    def _on_setup_line(self, line):
        if line.startswith("FORTSCHRITT "):
            parts = line.split(" ", 2)
            try:
                self._progress = int(parts[1])
            except ValueError:
                pass
            self._status = parts[2] if len(parts) > 2 else ""
        elif line.startswith("FEHLER "):
            self._status = line[7:]
        self.changed.emit()

    def _on_setup_end(self, code):
        self._setup = None
        self._modell = installiert(self._liste)
        if code == 0 and self._modell:
            self._state = "bereit"
            self._status = ""
        else:
            self._state = "einrichten"
            if code in (126, 127):
                self._status = "Einrichten wurde abgebrochen."
            elif not self._status:
                self._status = "Einrichten fehlgeschlagen."
        self.changed.emit()

    # ---- Rechenteil (llama-server) ---------------------------------------------------
    def _start_server(self, gpu=True):
        binary = server_binary()
        info = self._liste.get(self._modell)
        if binary is None or info is None:
            raise RuntimeError("Der KI-Rechenteil fehlt – bitte Creative OS aktualisieren.")
        self._port = freier_port()
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(binary.parent) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        args = [str(binary), "-m", str(MODELLE / info["datei"]), "--host", "127.0.0.1", "--port", str(self._port),
                "-c", "8192", "--jinja", "-ngl", "999" if gpu else "0"]
        cache = Path.home() / ".cache"
        cache.mkdir(parents=True, exist_ok=True)
        log = open(cache / "creative-ki.log", "wb")
        self._proc = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        frist = time.monotonic() + 240
        while time.monotonic() < frist:
            if self._proc.poll() is not None:
                return False
            try:
                with urlopen(f"http://127.0.0.1:{self._port}/health", timeout=2) as r:
                    if r.status == 200:
                        return True
            except OSError:
                pass
            if self._stop.is_set():
                return False
            time.sleep(0.5)
        return False

    def _ensure_server(self):
        if self._proc is not None and self._proc.poll() is None:
            return
        if self._start_server(gpu=True):
            return
        self.unload_now()
        # Zu wenig Grafikspeicher (z. B. ein Spiel läuft): auf dem Prozessor rechnen
        if not self._stop.is_set() and self._start_server(gpu=False):
            return
        self.unload_now()
        raise RuntimeError("Das KI-Modell ließ sich nicht starten. Details: ~/.cache/creative-ki.log")

    def unload_now(self):
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @Slot()
    def unload(self):
        if self._busy:
            self._idle.start()
            return
        self.unload_now()
        if self._state == "bereit":
            self.changed.emit()

    # ---- Fragen ------------------------------------------------------------------------
    @Slot(str)
    def ask(self, text):
        text = text.strip()
        if not text or self._busy or not self._modell:
            return
        self._messages.append({"role": "user", "text": text, "quellen": []})
        self._messages.append({"role": "assistant", "text": "", "quellen": []})
        self._busy = True
        self._stop.clear()
        self._idle.stop()
        self._status = "Denkt nach …" if self._proc is not None and self._proc.poll() is None else "KI wird geladen …"
        self.messagesChanged.emit()
        self.changed.emit()
        verlauf = [{"role": m["role"], "content": m["text"]} for m in self._messages[:-1] if m["text"]][-12:]
        threading.Thread(target=self._antworten, args=(verlauf, text), daemon=True).start()

    def _antworten(self, verlauf, frage):
        quellen = []
        try:
            self._ensure_server()
            system = SYSTEM.format(datum=time.strftime("%d.%m.%Y"))
            if not SCHREIBEN.search(frage):
                try:
                    treffer = wikipedia(frage)
                except (OSError, ValueError):
                    treffer = []
                if treffer:
                    quellen = [{"titel": t, "url": u} for t, _, u in treffer]
                    system += ("\n\nHintergrund aus der Wikipedia (nur verwenden, wenn es zur Frage passt; "
                               "nicht erwähnen, dass dir Text vorliegt):\n" +
                               "\n\n".join(f"[{t}] {x}" for t, x, _ in treffer))
            post(self._chunk.emit, "")         # Status: denkt
            body = json.dumps({
                "messages": [{"role": "system", "content": system}] + verlauf,
                "stream": True, "temperature": 0.4, "max_tokens": 1200,
                "chat_template_kwargs": {"enable_thinking": False},
            }).encode()
            req = Request(f"http://127.0.0.1:{self._port}/v1/chat/completions", data=body,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=300) as r:
                for raw in r:
                    if self._stop.is_set():
                        break
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0].get("delta", {})
                    except (ValueError, KeyError, IndexError):
                        continue
                    if delta.get("content"):
                        post(self._chunk.emit, delta["content"])
            post(self._done.emit, "", quellen)
        except Exception as exc:  # noqa: BLE001 – jede Störung landet als Meldung im Widget
            post(self._done.emit, str(exc) or exc.__class__.__name__, quellen)

    def _on_chunk(self, text):
        if not self._messages:
            return
        if not text:
            self._status = "Denkt nach …"
            self.changed.emit()
            return
        if self._status:
            self._status = ""
            self.changed.emit()
        self._messages[-1]["text"] += text
        self.messagesChanged.emit()

    def _on_done(self, error, quellen):
        self._busy = False
        self._idle.start()
        if self._messages:
            last = self._messages[-1]
            last["text"] = last["text"].strip()
            if error and not last["text"]:
                last["text"] = "⚠ " + error
                last["fehler"] = True
            elif self._stop.is_set():
                last["text"] += " …"
            else:
                last["quellen"] = quellen
        self._status = ""
        self.messagesChanged.emit()
        self.changed.emit()

    @Slot()
    def stop(self):
        self._stop.set()

    @Slot()
    def clear(self):
        if self._busy:
            self._stop.set()
        self._messages = []
        self.messagesChanged.emit()

    @Slot(int)
    def copy(self, index):
        if 0 <= index < len(self._messages):
            QGuiApplication.clipboard().setText(self._messages[index]["text"])

    def _fail(self, text):
        self._state = "einrichten"
        self._status = text
        self.changed.emit()

    # ---- QML ---------------------------------------------------------------------------
    def _modelle_qml(self):
        return [{"key": k, "name": v["name"], "beschreibung": v["beschreibung"],
                 "gb": round(v["groesse"] / 1e9, 1), "empfohlen": k == empfehlung(self._liste, self._vram)}
                for k, v in self._liste.items()]

    enabled = Property(bool, lambda self: bool(self._settings.get("kiEnabled", True)), notify=changed)
    state = Property(str, lambda self: self._state, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    loaded = Property(bool, lambda self: self._proc is not None and self._proc.poll() is None, notify=changed)
    modelName = Property(str, lambda self: self._liste.get(self._modell, {}).get("name", ""), notify=changed)
    choice = Property(str, lambda self: self._wahl, notify=changed)
    models = Property("QVariantList", _modelle_qml, notify=changed)
    vram = Property(float, lambda self: round(self._vram, 1), notify=changed)
    messages = Property("QVariantList", lambda self: self._messages, notify=messagesChanged)
    posX = Property(float, lambda self: self._position(0), notify=changed)
    posY = Property(float, lambda self: self._position(1), notify=changed)
