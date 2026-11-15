"""Stimme für den KI-Helfer: liest Antworten vor – offline mit Piper (MIT-Lizenz, Stimmen frei).

Code wird nicht vorgelesen: Codeblöcke werden durch einen kurzen Hinweis ersetzt, Markdown-Zeichen,
Links und Adressen fallen weg. Beim Streamen wird Satz für Satz gesprochen, sobald ein Satz fertig ist.

Piper läuft als ein Prozess pro Stimme/Tempo: jede Zeile auf stdin wird eine WAV-Datei, deren Pfad
Piper auf stdout meldet. Ein zweiter Faden spielt die Dateien der Reihe nach ab (pw-play/paplay/aplay).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from collections import deque
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import config
from .mainthread import post

LIB = Path(os.environ.get("CREATIVE_KI_LIB", "/usr/lib/creative-ki"))
PIPER = Path(os.environ.get("CREATIVE_PIPER", str(LIB / "piper" / "piper")))
STIMMEN_LISTE = LIB / "stimmen.json"
ORDNER = [LIB / "stimmen", Path(os.environ.get("CREATIVE_KI_STIMMEN", "/var/lib/creative-ki/stimmen"))]
SETUP = "/usr/libexec/creative-ki-setup"
CODE_HINWEIS = "Den Code siehst du im Fenster."

# ---- Text fürs Vorlesen ------------------------------------------------------------------------
_FENCE = re.compile(r"```.*?(```|\Z)", re.S)
_INLINE = re.compile(r"`([^`\n]*)`")
_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
_MAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_LIST = re.compile(r"^\s*(?:[-*•+]|\d+[.)])\s+", re.M)
_HEAD = re.compile(r"^\s*#{1,6}\s*", re.M)
_QUOTE = re.compile(r"^\s*>\s?", re.M)
_EMPH = re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1")
_TABLE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_RULE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.M)
_SYMBOLE = re.compile(r"[*#_`|<>{}\[\]\\^~]")
_SATZENDE = re.compile(r"(?<=[.!?…])\s+|(?<=:)\s*\n|\n{1,}")


def _inline(m):
    """Kurze Fachbegriffe in `…` bleiben (z. B. `ls`), echter Code fällt weg."""
    inhalt = m.group(1).strip()
    if len(inhalt) <= 24 and re.fullmatch(r"[\wÄÖÜäöüß .,-]+", inhalt):
        return inhalt
    return ""


def vorlesbar(text):
    """Markdown-Antwort → Text zum Sprechen (ohne Code, Links, Zeichen)."""
    text = _FENCE.sub(f"\n{CODE_HINWEIS}\n", text)
    text = _TABLE.sub("", text)
    text = _RULE.sub("", text)
    text = _INLINE.sub(_inline, text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("dem Link", text)
    text = _MAIL.sub("", text)
    text = _HEAD.sub("", text)
    text = _QUOTE.sub("", text)
    text = _LIST.sub("", text)
    for _ in range(2):
        text = _EMPH.sub(r"\2", text)
    text = _SYMBOLE.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # Hinweis nicht mehrfach hintereinander
    text = re.sub(rf"({re.escape(CODE_HINWEIS)}\s*)+", CODE_HINWEIS + "\n", text)
    return text.strip()


def saetze(text):
    """In Sätze/Zeilen zerlegen; leere Teile und reine Satzzeichen fallen weg."""
    teile = [t.strip() for t in _SATZENDE.split(text)]
    return [t for t in teile if re.search(r"[\wÄÖÜäöüß]", t)]


def _code_bereiche(text):
    """(Anfang, Ende) aller ```-Blöcke; ein offener Block reicht bis zum Ende."""
    bereiche, pos = [], 0
    while True:
        a = text.find("```", pos)
        if a < 0:
            return bereiche
        b = text.find("```", a + 3)
        if b < 0:
            bereiche.append((a, len(text), False))
            return bereiche
        bereiche.append((a, b + 3, True))
        pos = b + 3


class Zerleger:
    """Nimmt gestreamte Antwortstücke und gibt fertige, vorlesbare Sätze heraus."""

    def __init__(self):
        self.puffer = ""

    def dazu(self, stueck):
        self.puffer += stueck
        return self._nimm(False)

    def ende(self):
        return self._nimm(True)

    def _nimm(self, final):
        text = self.puffer
        if not text:
            return []
        bereiche = _code_bereiche(text)
        if final:
            ende = len(text)
        else:
            schnitt = len(text)
            if bereiche and not bereiche[-1][2]:
                schnitt = bereiche[-1][0]           # offener Codeblock: davor anhalten
            ende = 0
            # dieselben Grenzen wie saetze(): Satzende + Leerraum oder Zeilenende (nicht „Erstens: …“)
            for m in re.finditer(r"[.!?…](?=\s)|\n", text[:schnitt]):
                ende = m.end()
            # nicht mitten in einem (geschlossenen) Codeblock schneiden
            for a, b, zu in bereiche:
                if a < ende < b and zu:
                    ende = b
            if bereiche and not bereiche[-1][2] and ende < bereiche[-1][0] and schnitt < len(text):
                # Text vor dem offenen Block ganz vorlesen und den Hinweis einmal sagen
                ende = max(ende, schnitt)
            if ende == 0:
                return []
        stueck, self.puffer = text[:ende], text[ende:]
        return saetze(vorlesbar(stueck))


# ---- Stimmen ------------------------------------------------------------------------------------
def stimmen_liste():
    try:
        return json.loads(STIMMEN_LISTE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def stimme_datei(info):
    """Pfad der .onnx-Datei, wenn die Stimme vollständig da ist."""
    namen = [d["datei"] for d in info.get("dateien", [])]
    for ordner in ORDNER:
        if namen and all((ordner / n).is_file() for n in namen):
            return ordner / next(n for n in namen if n.endswith(".onnx"))
    return None


def abspieler():
    for name, args in (("pw-play", ["pw-play", "--volume={v}"]), ("paplay", ["paplay", "--volume={pv}"]),
                       ("aplay", ["aplay", "-q"])):
        if shutil.which(name):
            return args
    return None


class Sprecher(QObject):
    changed = Signal()
    _setupLine = Signal(str)
    _setupEnd = Signal(int)
    _spricht = Signal(bool)

    def __init__(self):
        super().__init__()
        self._settings = config.load()["desktopExtras"]
        self._liste = stimmen_liste()
        self._lock = threading.Lock()
        self._piper = None
        self._piper_key = None
        self._gen = 0
        self._gesendet = deque()
        self._dateien = deque()
        self._signal = threading.Condition(self._lock)
        self._player = None
        self._speaking = False
        self._tmp = Path(tempfile.mkdtemp(prefix="creative-stimme-"))
        self._zerleger = Zerleger()
        self._setup = None
        self._laedt = ""
        self._progress = 0
        self._status = ""
        self._setupLine.connect(self._on_setup_line)
        self._setupEnd.connect(self._on_setup_end)
        self._spricht.connect(self._set_speaking)
        threading.Thread(target=self._abspielen, daemon=True).start()

    # ---- Einstellungen -------------------------------------------------------------
    def _save(self, **changes):
        settings = {**config.load()["desktopExtras"], **changes}
        if config.set_value("desktopExtras", settings):
            self._settings = settings
            self.changed.emit()

    def _stimme(self):
        key = self._settings.get("kiStimme")
        if key in self._liste and stimme_datei(self._liste[key]):
            return key
        for k, info in self._liste.items():
            if stimme_datei(info):
                return k
        return ""

    def _tempo(self):
        v = self._settings.get("kiTempo", 1.0)
        return float(v) if type(v) in (int, float) and 0.5 <= v <= 2.0 else 1.0

    def _lautstaerke(self):
        v = self._settings.get("kiLautstaerke", 1.0)
        return float(v) if type(v) in (int, float) and 0.0 <= v <= 1.0 else 1.0

    @Slot(bool)
    def setAutoRead(self, on):
        self._save(kiVorlesen=bool(on))
        if not on:
            self.stop()

    @Slot(str)
    def setVoice(self, key):
        if key in self._liste and stimme_datei(self._liste[key]):
            self.stop()
            self._save(kiStimme=key)

    @Slot(float)
    def setSpeed(self, v):
        self._save(kiTempo=round(max(0.5, min(2.0, v)), 2))

    @Slot(float)
    def setVolume(self, v):
        self._save(kiLautstaerke=round(max(0.0, min(1.0, v)), 2))

    # ---- Sprechen -------------------------------------------------------------------
    def bereit(self):
        return PIPER.is_file() and bool(self._stimme()) and abspieler() is not None

    def _piper_starten(self, key):
        tempo = self._tempo()
        wunsch = (key, tempo)
        if self._piper is not None and self._piper.poll() is None and self._piper_key == wunsch:
            return True
        self._piper_stop()
        modell = stimme_datei(self._liste[key])
        if modell is None:
            return False
        args = [str(PIPER), "-m", str(modell), "--output_dir", str(self._tmp), "--length_scale",
                f"{1.0 / tempo:.3f}", "--sentence_silence", "0.12", "-q"]
        espeak = PIPER.parent / "espeak-ng-data"
        if espeak.is_dir():
            args += ["--espeak_data", str(espeak)]
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(PIPER.parent) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        try:
            self._piper = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        except OSError:
            self._piper = None
            return False
        self._piper_key = wunsch
        self._gesendet.clear()
        threading.Thread(target=self._lesen, args=(self._piper,), daemon=True).start()
        return True

    def _piper_stop(self):
        proc, self._piper = self._piper, None
        if proc is not None and proc.poll() is None:
            proc.kill()

    def _lesen(self, proc):
        """Piper meldet je Zeile den Pfad der fertigen WAV-Datei."""
        for line in proc.stdout:
            pfad = line.strip()
            if not pfad:
                continue
            with self._lock:
                gen = self._gesendet.popleft() if self._gesendet else -1
                if gen == self._gen:
                    self._dateien.append(pfad)
                    self._signal.notify()
                    continue
            Path(pfad).unlink(missing_ok=True)

    def _abspielen(self):
        while True:
            with self._lock:
                while not self._dateien:
                    if self._speaking and not self._gesendet:
                        post(self._spricht.emit, False)
                    self._signal.wait()
                pfad = self._dateien.popleft()
                gen = self._gen
            befehl = abspieler()
            if befehl:
                v = self._lautstaerke()
                args = [a.format(v=f"{v:.2f}", pv=str(int(v * 65536))) for a in befehl] + [pfad]
                try:
                    self._player = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self._player.wait()
                except OSError:
                    pass
                self._player = None
            Path(pfad).unlink(missing_ok=True)
            with self._lock:
                if gen == self._gen and not self._dateien and not self._gesendet:
                    post(self._spricht.emit, False)

    def _set_speaking(self, on):
        if self._speaking != on:
            self._speaking = on
            self.changed.emit()

    def sag(self, saetze_):
        """Sätze in die Warteschlange (Zeile für Zeile an Piper)."""
        saetze_ = [s.replace("\n", " ") for s in saetze_ if s.strip()]
        if not saetze_:
            return
        key = self._stimme()
        if not key or not self._piper_starten(key):
            self._status = "Keine Stimme verfügbar."
            self.changed.emit()
            return
        try:
            with self._lock:
                self._gesendet.extend([self._gen] * len(saetze_))
            # außerhalb der Sperre schreiben – der Lesefaden braucht sie für Pipers Antworten
            self._piper.stdin.write("".join(s + "\n" for s in saetze_))
            self._piper.stdin.flush()
        except (OSError, ValueError):
            self._piper_stop()
            return
        self._set_speaking(True)

    @Slot()
    def stop(self):
        with self._lock:
            self._gen += 1
            for pfad in self._dateien:
                Path(pfad).unlink(missing_ok=True)
            self._dateien.clear()
        player = self._player
        if player is not None and player.poll() is None:
            player.terminate()
        self._zerleger = Zerleger()
        self._set_speaking(False)

    @Slot(str)
    def speakText(self, text):
        self.stop()
        self.sag(saetze(vorlesbar(text)))

    @Slot(str)
    def preview(self, key):
        if key in self._liste and stimme_datei(self._liste[key]):
            alt = self._settings.get("kiStimme")
            self.stop()
            self._settings = {**self._settings, "kiStimme": key}
            self.sag([f"Hallo, ich bin {self._liste[key]['name']}. So klinge ich, wenn ich dir Antworten vorlese."])
            self._settings = {**self._settings, "kiStimme": alt}

    # vom KI-Helfer beim Streamen
    def beginn(self):
        self.stop()

    def dazu(self, stueck):
        if self.autoRead:
            self.sag(self._zerleger.dazu(stueck))

    def ende(self):
        if self.autoRead:
            self.sag(self._zerleger.ende())
        self._zerleger = Zerleger()

    def quit(self):
        self.stop()
        self._piper_stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ---- Stimmen laden -----------------------------------------------------------------
    @Slot(str)
    def installVoice(self, key):
        if self._setup is not None or key not in self._liste:
            return
        self._laedt = key
        self._progress = 0
        self._status = "Download startet …"
        self.changed.emit()
        argv = ["pkexec", SETUP, "stimme", key] if os.geteuid() != 0 else [SETUP, "stimme", key]
        try:
            self._setup = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except OSError as exc:
            self._setup = None
            self._laedt = ""
            self._status = f"Laden nicht möglich: {exc}"
            self.changed.emit()
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
        key, self._laedt = self._laedt, ""
        if code == 0 and stimme_datei(self._liste.get(key, {})):
            self._status = ""
            self._save(kiStimme=key)
        elif code in (126, 127):
            self._status = "Laden wurde abgebrochen."
        elif not self._status:
            self._status = "Laden fehlgeschlagen."
        self.changed.emit()

    # ---- QML -----------------------------------------------------------------------------
    def _voices(self):
        rows = []
        for k, v in self._liste.items():
            groesse = sum(d.get("groesse", 0) for d in v.get("dateien", []))
            rows.append({"key": k, "name": v["name"], "geschlecht": v.get("geschlecht", ""),
                         "beschreibung": v.get("beschreibung", ""), "installiert": stimme_datei(v) is not None,
                         "mb": round(groesse / 1e6)})
        return rows

    autoRead = Property(bool, lambda self: bool(self._settings.get("kiVorlesen", True)), notify=changed)
    voice = Property(str, lambda self: self._stimme(), notify=changed)
    speed = Property(float, lambda self: self._tempo(), notify=changed)
    volume = Property(float, lambda self: self._lautstaerke(), notify=changed)
    voices = Property("QVariantList", _voices, notify=changed)
    speaking = Property(bool, lambda self: self._speaking, notify=changed)
    available = Property(bool, lambda self: self.bereit(), notify=changed)
    loadingVoice = Property(str, lambda self: self._laedt, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
