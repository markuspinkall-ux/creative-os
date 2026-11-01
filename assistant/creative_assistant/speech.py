"""Hören und Sprechen.

- Aktivierungswort („Computer“): Vosk, läuft sparsam ständig mit
- Befehl verstehen: faster-whisper (sehr gut, auch englische Liedtitel),
  ersatzweise Vosk
- Sprechen: Piper (natürliche deutsche Stimmen), ersatzweise espeak-ng

Alle Modelle liegen lokal – es wird nichts ins Internet geschickt.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

MODEL_DIRS = [Path.home() / ".local/share/creative-assistant/models", Path("/usr/share/creative-assistant/models")]
RATE = 16000

VOICE_NAMES = {
    "thorsten": "Thorsten (männlich)", "kerstin": "Kerstin (weiblich)", "ramona": "Ramona (weiblich)",
    "eva_k": "Eva (weiblich)", "karlsson": "Karlsson (männlich)", "pavoque": "Pavoque (männlich)",
}


def model_path(*parts):
    for base in MODEL_DIRS:
        p = base.joinpath(*parts)
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Aktivierungswort
# ---------------------------------------------------------------------------
class WakeWord:
    def __init__(self, words=("computer",)):
        self.words = words
        self._rec = None
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
            SetLogLevel(-1)
            path = model_path("vosk-de")
            if path:
                self._model = Model(str(path))
                grammar = json.dumps(list(words) + ["[unk]"])
                self._rec = KaldiRecognizer(self._model, RATE, grammar)
        except Exception as exc:  # Vosk fehlt → nur per Klick
            print("Assistent: kein Aktivierungswort möglich:", exc)

    @property
    def available(self):
        return self._rec is not None

    def feed(self, chunk):
        """True, sobald das Aktivierungswort gehört wurde."""
        if not self._rec:
            return False
        if self._rec.AcceptWaveform(chunk):
            text = json.loads(self._rec.Result()).get("text", "")
        else:
            text = json.loads(self._rec.PartialResult()).get("partial", "")
        if any(w in text.split() for w in self.words):
            self._rec.Reset()
            return True
        return False

    def reset(self):
        if self._rec:
            self._rec.Reset()


# ---------------------------------------------------------------------------
# Befehl verstehen
# ---------------------------------------------------------------------------
class Transcriber:
    def __init__(self):
        self._whisper = None
        self._vosk_model = None
        self._tried = False

    def _load(self):
        if self._tried:
            return
        self._tried = True
        try:
            from faster_whisper import WhisperModel
            path = model_path("whisper-small") or model_path("whisper-base")
            if path:
                self._whisper = WhisperModel(str(path), device="cpu", compute_type="int8",
                                             cpu_threads=max(2, (os.cpu_count() or 4) // 2))
        except Exception as exc:
            print("Assistent: Whisper nicht verfügbar:", exc)
        if self._whisper is None:
            try:
                from vosk import Model
                path = model_path("vosk-de")
                if path:
                    self._vosk_model = Model(str(path))
            except Exception as exc:
                print("Assistent: Vosk nicht verfügbar:", exc)

    @property
    def available(self):
        self._load()
        return self._whisper is not None or self._vosk_model is not None

    def transcribe(self, pcm):
        self._load()
        if self._whisper is not None:
            import numpy as np
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _info = self._whisper.transcribe(
                audio, language="de", beam_size=1, vad_filter=True,
                initial_prompt="Wetter, Timer, Minuten, Spiele, Musik, YouTube, lauter, leiser, stopp.")
            return " ".join(s.text for s in segments).strip()
        if self._vosk_model is not None:
            from vosk import KaldiRecognizer
            rec = KaldiRecognizer(self._vosk_model, RATE)
            rec.AcceptWaveform(pcm)
            return json.loads(rec.FinalResult()).get("text", "")
        return ""


# ---------------------------------------------------------------------------
# Sprechen
# ---------------------------------------------------------------------------
def list_voices():
    voices = []
    seen = set()
    for base in MODEL_DIRS:
        for f in sorted(glob.glob(str(base / "piper" / "*.onnx"))):
            vid = Path(f).stem                         # de_DE-thorsten-medium
            if vid in seen:
                continue
            seen.add(vid)
            key = vid.split("-")[1] if "-" in vid else vid
            voices.append({"id": vid, "name": VOICE_NAMES.get(key, key.capitalize()), "path": f})
    if not voices and shutil.which("espeak-ng"):
        voices.append({"id": "espeak", "name": "Computerstimme (einfach)", "path": ""})
    return voices


class Speaker:
    def __init__(self):
        self._voices = {}
        self._proc = None

    def _voice(self, vid):
        if vid in self._voices:
            return self._voices[vid]
        info = next((v for v in list_voices() if v["id"] == vid), None)
        voice = None
        if info and info["path"]:
            try:
                from piper import PiperVoice
                voice = PiperVoice.load(info["path"])
            except Exception as exc:
                print("Assistent: Stimme nicht ladbar:", exc)
        self._voices[vid] = voice
        return voice

    def synth(self, text, vid):
        """Erzeugt eine WAV-Datei und gibt den Pfad zurück (oder None)."""
        fd, path = tempfile.mkstemp(prefix="creative-say-", suffix=".wav")
        os.close(fd)
        voice = self._voice(vid) if vid != "espeak" else None
        if voice is not None:
            try:
                with wave.open(path, "wb") as wav:
                    if hasattr(voice, "synthesize_wav"):
                        voice.synthesize_wav(text, wav)
                    else:
                        voice.synthesize(text, wav)
                return path
            except Exception as exc:
                print("Assistent: Sprechen fehlgeschlagen:", exc)
        if shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "de", "-s", "160", "-w", path, text], capture_output=True)
            return path
        return None

    def play(self, path, wait=True):
        player = "pw-play" if shutil.which("pw-play") else "paplay"
        self._proc = subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wait:
            self._proc.wait()
            try:
                os.unlink(path)
            except OSError:
                pass

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


def clean_for_speech(text):
    return re.sub(r"\s+", " ", text).strip()
