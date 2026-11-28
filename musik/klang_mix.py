"""Mischer des KI-Musikgenerators – nur numpy und die Standardbibliothek.

Die KI erzeugt kurze Klänge (z. B. mehrere verschiedene Vogelrufe). Daraus baut
build_ambience() eine lange Spur: die Klänge in wechselnder Reihenfolge, mit
zufälligen, einstellbaren Pausen dazwischen, leicht unterschiedlicher Lautstärke
und Stereo-Position, auf Wunsch über einem leisen Klangteppich (z. B. Wind im Wald).
make_loop() macht jede Spur nahtlos wiederholbar (für Spiele).

Audio ist hier immer ein float32-Feld der Form (Samples, 2) im Bereich −1 … 1.
"""

import random
import wave

import numpy as np

RATE = 44100

PAUSES = [
    ("kurz", "Kurz (2–6 s)", 2, 6),
    ("mittel", "Mittel (5–15 s)", 5, 15),
    ("lang", "Lang (15–40 s)", 15, 40),
    ("sehrlang", "Sehr lang (30–90 s)", 30, 90),
]


# ---- Ein- und Ausgabe ---------------------------------------------------------------
def read_wav(path):
    """WAV (8/16/24/32 Bit, mono/stereo) → (Audio, Rate)."""
    with wave.open(str(path), "rb") as w:
        channels, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 1:
        data = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        data = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        ints = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
        data = ints.astype(np.float32) / 8388608
    else:
        data = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
    data = data.reshape(-1, channels)
    if channels == 1:
        data = np.repeat(data, 2, axis=1)
    return data[:, :2].copy(), rate


def write_wav(path, audio, rate=RATE):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def resample(audio, rate, target=RATE):
    """Einfaches lineares Umrechnen der Abtastrate (reicht für Geräusche)."""
    if rate == target or len(audio) == 0:
        return audio
    n = int(round(len(audio) * target / rate))
    x_old = np.linspace(0, 1, len(audio), endpoint=False)
    x_new = np.linspace(0, 1, n, endpoint=False)
    return np.stack([np.interp(x_new, x_old, audio[:, c]) for c in range(2)], axis=1).astype(np.float32)


# ---- Bausteine ----------------------------------------------------------------------
def db(value):
    return 10 ** (value / 20)


def fade(audio, fade_in=0.3, fade_out=0.3, rate=RATE):
    audio = audio.copy()
    for seconds, head in ((fade_in, True), (fade_out, False)):
        n = min(len(audio) // 2, int(seconds * rate))
        if n > 0:
            ramp = np.sin(np.linspace(0, np.pi / 2, n)) ** 2
            if head:
                audio[:n] *= ramp[:, None]
            else:
                audio[-n:] *= ramp[::-1, None]
    return audio


def trim_silence(audio, threshold_db=-45, rate=RATE, keep=0.05):
    """Stille am Anfang und Ende entfernen (die KI lässt oft Luft)."""
    if len(audio) == 0:
        return audio
    level = np.abs(audio).max(axis=1)
    loud = np.nonzero(level > db(threshold_db))[0]
    if len(loud) == 0:
        return audio[:0]
    pad = int(keep * rate)
    return audio[max(0, loud[0] - pad):min(len(audio), loud[-1] + pad)]


def normalize(audio, peak_db=-1.0):
    peak = float(np.abs(audio).max()) if len(audio) else 0.0
    return audio * (db(peak_db) / peak) if peak > 1e-6 else audio


def pan(audio, position):
    """position −1 (links) … 1 (rechts), gleich laut wirkend."""
    angle = (position + 1) * np.pi / 4
    return audio * np.array([np.cos(angle), np.sin(angle)], dtype=np.float32) * np.sqrt(2)


def loop_to(audio, length, crossfade=2.0, rate=RATE):
    """Klang mit weichen Übergängen wiederholen, bis die Länge erreicht ist."""
    if len(audio) == 0:
        return np.zeros((length, 2), np.float32)
    x = min(int(crossfade * rate), len(audio) // 3)
    out = np.zeros((length + len(audio), 2), np.float32)
    pos, step = 0, max(1, len(audio) - x)
    piece = fade(audio, x / rate, x / rate, rate) if x else audio
    while pos < length:
        out[pos:pos + len(piece)] += piece
        pos += step
    return out[:length]


def make_loop(audio, crossfade=3.0, rate=RATE):
    """Ende weich in den Anfang überblenden – die Spur lässt sich dann endlos wiederholen."""
    x = min(int(crossfade * rate), len(audio) // 4)
    if x <= 0:
        return audio
    body = audio[:-x].copy()
    tail = audio[-x:]
    ramp = np.sin(np.linspace(0, np.pi / 2, x)) ** 2
    body[:x] = body[:x] * ramp[:, None] + tail * ramp[::-1, None]
    return body


# ---- Zusammenbauen ------------------------------------------------------------------
def pause_range(key):
    for k, _, lo, hi in PAUSES:
        if k == key:
            return lo, hi
    return 5, 15


def build_ambience(events, total_seconds, pause="mittel", bed=None, bed_db=-14.0, seed=None, rate=RATE,
                   loop=True):
    """Lange Spur aus einzelnen Klängen mit Pausen dazwischen.

    events: Liste von Audio-Feldern (verschiedene Varianten, z. B. Vogelrufe)
    bed:    optionaler Klangteppich, der leise darunter läuft (wird wiederholt)
    """
    rng = random.Random(seed)
    length = int(total_seconds * rate)
    out = np.zeros((length, 2), np.float32)
    if bed is not None and len(bed):
        out += loop_to(normalize(bed), length, rate=rate) * db(bed_db)
    clips = [fade(normalize(trim_silence(e, rate=rate)), 0.15, 0.6, rate) for e in events]
    clips = [c for c in clips if len(c) > rate * 0.2]
    lo, hi = pause_range(pause)
    pos = int(rng.uniform(0.5, min(lo, 3)) * rate)
    last = None
    placed = 0
    while clips and pos < length:
        choices = [i for i in range(len(clips)) if i != last] or [0]
        i = rng.choice(choices)
        clip = pan(clips[i] * db(rng.uniform(-6, 0)), rng.uniform(-0.6, 0.6))
        end = min(length, pos + len(clip))
        out[pos:end] += clip[:end - pos]
        placed += 1
        last = i
        pos = end + int(rng.uniform(lo, hi) * rate)
    if loop:
        out = make_loop(out, 3.0, rate)
    return normalize(out, -1.0), placed


def finish_music(audio, loop=False, rate=RATE):
    """Musikstück: Stille kürzen, sanft ein- und ausblenden oder nahtlos schließen."""
    audio = trim_silence(audio, -50, rate)
    audio = make_loop(audio, 2.5, rate) if loop else fade(audio, 0.05, 2.0, rate)
    return normalize(audio, -1.0)


def chain(clips, total_seconds, crossfade=2.0, seed=None, rate=RATE, loop=True):
    """Durchgehende Geräusche (Regen, Feuer …): Varianten in wechselnder Folge weich aneinanderhängen."""
    rng = random.Random(seed)
    clips = [normalize(trim_silence(c, rate=rate)) for c in clips]
    clips = [c for c in clips if len(c) > rate * 2]
    length = int(total_seconds * rate)
    out = np.zeros((length + rate * 60, 2), np.float32)
    if not clips:
        return out[:length], 0
    x = int(crossfade * rate)
    pos, last, placed = 0, None, 0
    while pos < length:
        i = rng.choice([k for k in range(len(clips)) if k != last] or [0])
        piece = fade(clips[i], crossfade, crossfade, rate)
        end = min(len(out), pos + len(piece))
        out[pos:end] += piece[:end - pos]
        pos += max(rate, len(piece) - x)
        last = i
        placed += 1
    out = out[:length]
    if loop:
        out = make_loop(out, crossfade, rate)
    return normalize(out, -1.0), placed
