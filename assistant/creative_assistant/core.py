"""Der Assistent selbst: hört zu, versteht, antwortet.

Läuft als eigener Hintergrund-Dienst. Die Taskleiste (Tray) verbindet sich
über eine lokale Schnittstelle (JSON-Zeilen über einen Unix-Socket):
  Dienst → Tray: Zustand (hört zu, denkt nach, spricht …), Pegel, Texte
  Tray → Dienst: aktivieren, Mikrofon/Stimme wählen, Musik/Timer stoppen
"""

import array
import datetime
import math
import json
import os
import re
import select
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from . import intents, weather
from .music import MusicPlayer
from .speech import RATE, Speaker, Transcriber, WakeWord, list_voices

CHUNK = 3200                     # 0,1 s bei 16 kHz, 16 bit, mono
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "creative-os" / "assistant.json"
SOUNDS = Path("/usr/share/sounds/freedesktop/stereo")
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]


def rms(chunk):
    """Lautstärke eines Audio-Stücks (16 bit), ohne Zusatzmodule."""
    samples = array.array("h", chunk[: len(chunk) - len(chunk) % 2])
    if not samples:
        return 0
    return math.sqrt(sum(x * x for x in samples[::2]) / len(samples[::2]))


def socket_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/creative-{os.getuid()}"
    return str(Path(base) / "creative-assistant.sock")


def default_city():
    try:
        zone = os.path.realpath("/etc/localtime").split("zoneinfo/")[-1]
        city = zone.split("/")[-1].replace("_", " ")
        return {"Berlin": "Berlin", "Vienna": "Wien", "Zurich": "Zürich", "Busingen": "Büsingen"}.get(city, city)
    except Exception:
        return "Berlin"


def list_inputs():
    """Mikrofone (PipeWire/Pulse), ohne „Monitor“-Quellen."""
    try:
        out = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True,
                             timeout=5, env={**os.environ, "LC_ALL": "C"}).stdout
        data = json.loads(out)
    except Exception:
        return []
    return [{"name": d.get("name", ""), "label": d.get("description") or d.get("name", "")}
            for d in data if not d.get("name", "").endswith(".monitor")]


class Assistant:
    def __init__(self):
        self.cfg = {"device": "", "voice": "", "wake": True, "city": default_city()}
        try:
            self.cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self.state = "idle"            # idle | listening | thinking | speaking | alarm
        self.heard = ""
        self.answer = ""
        self.level = 0.0
        self.timer_end = 0.0
        self.timer_total = 0
        self.clients = []
        self.lock = threading.Lock()
        self.wake = WakeWord()
        self.stt = Transcriber()
        self.speaker = Speaker()
        self.music = MusicPlayer(self.push)
        self.voices = list_voices()
        if not self.cfg["voice"] or not any(v["id"] == self.cfg["voice"] for v in self.voices):
            preferred = next((v for v in self.voices if "thorsten" in v["id"]), None)
            self.cfg["voice"] = (preferred or (self.voices[0] if self.voices else {"id": ""}))["id"]
        self.devices = list_inputs()
        self._mic = None
        self._mic_restart = threading.Event()
        self._activate = threading.Event()
        self._cancel = threading.Event()

    # ---- Einstellungen ------------------------------------------------------------
    def save(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG)

    # ---- Zustand an die Taskleiste --------------------------------------------------
    def snapshot(self):
        remaining = max(0, int(self.timer_end - time.time())) if self.timer_end else 0
        return {
            "type": "state", "state": self.state, "heard": self.heard, "answer": self.answer,
            "timer": remaining, "timerTotal": self.timer_total,
            "music": self.music.title, "paused": self.music.paused,
            "devices": self.devices, "device": self.cfg["device"],
            "voices": [{"id": v["id"], "name": v["name"]} for v in self.voices], "voice": self.cfg["voice"],
            "wake": bool(self.cfg["wake"]), "wakeAvailable": self.wake.available,
            "sttAvailable": True, "city": self.cfg["city"],
        }

    def send(self, msg):
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            for c in list(self.clients):
                try:
                    c.sendall(data)
                except OSError:
                    self.clients.remove(c)

    def push(self):
        self.send(self.snapshot())

    def set_state(self, state):
        self.state = state
        self.music.duck(state in ("listening", "thinking", "speaking"))
        self.push()

    # ---- Sprechen ------------------------------------------------------------------
    def say(self, text):
        self.answer = text
        self.set_state("speaking")
        wav = self.speaker.synth(text, self.cfg["voice"])
        if wav:
            # Pegel für den Visualizer aus der WAV-Datei schätzen
            t = threading.Thread(target=self._fake_level, args=(text,), daemon=True)
            t.start()
            self.speaker.play(wav)
        self.set_state("idle")

    def _fake_level(self, text):
        end = time.time() + max(1.2, len(text) / 14)
        while time.time() < end and self.state == "speaking":
            self.send({"type": "level", "level": 0.35 + 0.4 * abs(((time.time() * 7) % 2) - 1)})
            time.sleep(0.08)

    def chime(self, name="message.oga"):
        f = SOUNDS / name
        if f.exists():
            subprocess.Popen(["pw-play" if shutil.which("pw-play") else "paplay", str(f)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ---- Mikrofon ------------------------------------------------------------------
    def _open_mic(self):
        args = ["parec", "--rate=16000", "--channels=1", "--format=s16le", "--raw", "--latency-msec=60"]
        if self.cfg["device"]:
            args.append(f"--device={self.cfg['device']}")
        try:
            return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except OSError:
            return None

    def _read(self, timeout=1.5):
        """Liest 0,1 s Audio; gibt None zurück, wenn das Mikrofon nichts liefert."""
        mic = self._mic
        if mic is None or mic.stdout is None:
            return None
        ready, _, _ = select.select([mic.stdout], [], [], timeout)
        if not ready:
            return None
        data = b""
        while len(data) < CHUNK:
            part = os.read(mic.stdout.fileno(), CHUNK - len(data))
            if not part:
                return data or b""
            data += part
            if len(data) < CHUNK:
                r, _, _ = select.select([mic.stdout], [], [], timeout)
                if not r:
                    break
        return data

    def no_signal(self):
        self.answer = ("Ich bekomme kein Signal vom Mikrofon. Bitte in der Systemsteuerung unter Ton "
                       "das Mikrofon prüfen – oder per Rechtsklick hier ein anderes wählen.")
        self.set_state("idle")

    def mic_loop(self):
        """Läuft immer: liest das Mikrofon, erkennt das Aktivierungswort,
        nimmt nach dem Aktivieren den Befehl auf."""
        noise = 300.0
        while True:
            need_mic = (self.cfg["wake"] and self.wake.available) or self._activate.is_set()
            if not need_mic:
                if self._mic:
                    self._mic.terminate()
                    self._mic = None
                self._activate.wait(timeout=1.0)
                continue
            if self._mic is None or self._mic.poll() is not None or self._mic_restart.is_set():
                if self._mic:
                    self._mic.terminate()
                self._mic_restart.clear()
                self._mic = self._open_mic()
                if self._mic is None:
                    if self._activate.is_set():
                        self._activate.clear()
                        self.no_signal()
                    time.sleep(3)
                    continue
            chunk = self._read()
            if chunk is None:                              # Mikrofon liefert nichts
                if self._activate.is_set():
                    self._activate.clear()
                    self.no_signal()
                continue
            if not chunk:
                self._mic = None
                if self._activate.is_set():
                    self._activate.clear()
                    self.no_signal()
                time.sleep(1)
                continue
            level = rms(chunk)
            if self.state in ("idle",):
                noise = 0.97 * noise + 0.03 * min(level, 3000)
            triggered = self._activate.is_set()
            if not triggered and self.state == "idle" and self.cfg["wake"]:
                triggered = self.wake.feed(chunk)
            if triggered and self.state in ("idle", "alarm"):
                self._activate.clear()
                if self.state == "alarm":
                    self.stop_alarm()
                pcm = self.record(noise)
                if pcm:
                    threading.Thread(target=self.handle_audio, args=(pcm,), daemon=True).start()
                else:
                    self.set_state("idle")

    def record(self, noise):
        """Nimmt einen Befehl auf, bis wieder Ruhe ist (höchstens 8 Sekunden)."""
        self.heard = ""
        self.answer = ""
        self.set_state("listening")
        self.chime()
        self._cancel.clear()
        frames, started, silent, waited = [], False, 0, 0
        threshold = max(450, noise * 2.6)
        while len(frames) < 80:                           # 8 s
            if self._cancel.is_set():
                return None
            chunk = self._read()
            if chunk is None:
                self.no_signal()
                return None
            if not chunk:
                break
            level = rms(chunk)
            self.send({"type": "level", "level": min(1.0, level / 4000)})
            frames.append(chunk)
            if level > threshold:
                started, silent = True, 0
            elif started:
                silent += 1
                if silent >= 8:                            # 0,8 s Ruhe → fertig
                    break
            else:
                waited += 1
                if waited >= 45:                           # 4,5 s nichts gesagt
                    self.answer = "Ich habe nichts gehört."
                    self.push()
                    return None
        self.wake.reset()
        return b"".join(frames)

    # ---- Verstehen und Handeln -------------------------------------------------------
    def handle_audio(self, pcm):
        self.set_state("thinking")
        try:
            text = self.stt.transcribe(pcm)
        except Exception as exc:
            print("Assistent: Erkennung fehlgeschlagen:", exc)
            text = ""
        text = re.sub(r"^(computer[,.!]?\s*)", "", text.strip(), flags=re.I)
        self.heard = text
        self.push()
        if not text:
            self.say("Entschuldigung, das habe ich nicht verstanden.")
            return
        self.handle_text(text)

    def handle_text(self, text):
        intent, v = intents.parse(text)
        try:
            reply = self.act(intent, v)
        except Exception as exc:
            print("Assistent:", intent, exc)
            reply = "Das hat leider nicht geklappt. Besteht eine Internetverbindung?"
        if reply:
            self.say(reply)
        else:
            self.set_state("idle")

    def act(self, intent, v):
        if intent == "weather":
            self.set_state("thinking")
            return weather.report(v.get("city") or self.cfg["city"], v.get("day", 0))
        if intent == "timer_set":
            self.timer_total = v["seconds"]
            self.timer_end = time.time() + v["seconds"]
            self.push()
            return f"Timer gestellt auf {intents.say_duration(v['seconds'])}."
        if intent == "timer_stop":
            if self.timer_end or self.state == "alarm":
                self.stop_timer()
                return "Timer gestoppt."
            return "Es läuft gerade kein Timer."
        if intent == "timer_status":
            if self.timer_end:
                return f"Noch {intents.say_duration(self.timer_end - time.time())}."
            return "Es läuft gerade kein Timer."
        if intent == "timer_ask":
            return "Wie lange soll der Timer laufen? Sag zum Beispiel: Timer auf fünf Minuten."
        if intent == "play":
            if not MusicPlayer.available():
                return "Zum Abspielen fehlen mpv und yt-dlp."
            self.set_state("thinking")
            self.answer = f"Suche „{v['query']}“ …"
            self.push()
            title = self.music.play(v["query"])
            if not title:
                return f"Dazu habe ich nichts gefunden."
            self.answer = f"♪ {title}"
            self.set_state("idle")
            return None                                    # Musik spricht für sich
        if intent == "music_ask":
            return "Was möchtest du hören? Sag zum Beispiel: Spiele Musik von Queen."
        if intent == "stop":
            if self.state == "alarm" or self.timer_end and self.timer_end <= time.time():
                self.stop_timer()
            self.music.stop()
            return None
        if intent == "pause":
            self.music.pause()
            return None
        if intent == "resume":
            self.music.resume()
            return None
        if intent == "volume":
            self.music.change_volume(v["delta"])
            return None
        if intent == "next":
            title = self.music.next()
            if title:
                self.answer = f"♪ {title}"
                self.push()
            return None if title else "Es läuft gerade keine Musik."
        if intent == "time":
            now = datetime.datetime.now()
            return f"Es ist {now.hour} Uhr {now.minute:02d}." if now.minute else f"Es ist genau {now.hour} Uhr."
        if intent == "date":
            d = datetime.date.today()
            return f"Heute ist {WEEKDAYS[d.weekday()]}, der {d.day}. {MONTHS[d.month - 1]} {d.year}."
        if intent == "help":
            return ("Frag mich nach dem Wetter, stell einen Timer, oder sag zum Beispiel: "
                    "Spiele Musik von Queen. Mit Stopp beende ich die Musik.")
        if intent == "thanks":
            return "Gern geschehen!"
        return "Das kann ich leider noch nicht. Frag mich nach dem Wetter, stell einen Timer oder lass Musik spielen."

    # ---- Timer ---------------------------------------------------------------------
    def timer_loop(self):
        last_push = 0
        while True:
            time.sleep(0.5)
            if self.timer_end and time.time() >= self.timer_end and self.state != "alarm":
                self.timer_end = 0
                self.answer = "Der Timer ist abgelaufen."
                self.set_state("alarm")
                threading.Thread(target=self._ring, daemon=True).start()
            elif self.timer_end and time.time() - last_push >= 1:
                last_push = time.time()
                self.push()

    def _ring(self):
        end = time.time() + 60
        while self.state == "alarm" and time.time() < end:
            self.chime("alarm-clock-elapsed.oga")
            time.sleep(2.5)
        if self.state == "alarm":
            self.set_state("idle")

    def stop_alarm(self):
        if self.state == "alarm":
            self.set_state("idle")

    def stop_timer(self):
        self.timer_end = 0
        self.timer_total = 0
        self.stop_alarm()
        self.push()

    # ---- Befehle aus der Taskleiste ---------------------------------------------------
    def command(self, msg):
        cmd = msg.get("cmd")
        if cmd == "activate":
            if self.state == "alarm":
                self.stop_timer()
            elif self.state in ("listening",):
                self._cancel.set()
                self.set_state("idle")
            elif self.state == "speaking":
                self.speaker.stop()
            else:
                self._activate.set()
        elif cmd == "cancel":
            self._cancel.set()
            self.speaker.stop()
            self.stop_alarm()
        elif cmd == "say":                               # Texteingabe (Testen ohne Mikrofon)
            threading.Thread(target=self.handle_text, args=(msg.get("text", ""),), daemon=True).start()
        elif cmd == "setDevice":
            self.cfg["device"] = msg.get("name", "")
            self.save()
            self._mic_restart.set()
            self.push()
        elif cmd == "setVoice":
            self.cfg["voice"] = msg.get("id", "")
            self.save()
            self.push()
            threading.Thread(target=self.say, args=("So klinge ich. Sag Computer, wenn du etwas brauchst.",),
                             daemon=True).start()
        elif cmd == "setWake":
            self.cfg["wake"] = bool(msg.get("on"))
            self.save()
            self.push()
        elif cmd == "setCity":
            city = msg.get("city", "").strip()
            if city:
                self.cfg["city"] = city
                self.save()
                self.push()
        elif cmd == "stopMusic":
            self.music.stop()
        elif cmd == "toggleMusic":
            self.music.toggle()
        elif cmd == "stopTimer":
            self.stop_timer()
        elif cmd == "refresh":
            self.devices = list_inputs()
            self.voices = list_voices()
            self.push()

    # ---- Schnittstelle -----------------------------------------------------------------
    def serve(self):
        path = socket_path()
        try:
            os.unlink(path)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        os.chmod(path, 0o600)
        srv.listen(4)
        while True:
            conn, _ = srv.accept()
            with self.lock:
                self.clients.append(conn)
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()
            self.push()

    def _client(self, conn):
        buf = b""
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    self.command(json.loads(line.decode("utf-8")))
                except (ValueError, UnicodeDecodeError):
                    pass
        with self.lock:
            if conn in self.clients:
                self.clients.remove(conn)

    def run(self):
        threading.Thread(target=self.mic_loop, daemon=True).start()
        threading.Thread(target=self.timer_loop, daemon=True).start()
        self.serve()
