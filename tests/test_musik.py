"""KI-Musikgenerator: Mischer, Vorschläge, Rechenteil – ohne Qt und ohne Grafikkarte.

    python3 -m pytest -q tests/test_musik.py
"""

import ast
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "musik"))

import klang_mix as km  # noqa: E402
import musik_vorschlaege as mv  # noqa: E402

R = km.RATE


def chirp(freq, seconds=1.2, silence=1.0):
    t = np.arange(int(seconds * R)) / R
    s = (np.sin(2 * np.pi * freq * t) * np.exp(-3 * t) * 0.5).astype(np.float32)
    pad = np.zeros(int(silence * R), np.float32)
    s = np.concatenate([pad, s, pad])
    return np.stack([s, s], 1)


def test_wav_roundtrip_and_mono():
    path = Path(tempfile.mkdtemp()) / "a.wav"
    audio = chirp(1000)
    km.write_wav(path, audio)
    back, rate = km.read_wav(path)
    assert rate == R and back.shape == audio.shape
    assert np.abs(back - audio).max() < 1e-3


def test_trim_and_fade():
    a = chirp(2000)
    trimmed = km.trim_silence(a)
    assert len(trimmed) < len(a) - R
    faded = km.fade(trimmed, 0.1, 0.1)
    assert abs(faded[0]).max() < 1e-3


def test_ambience_has_pauses_and_right_length():
    events = [chirp(f) for f in (2000, 3000, 4000)]
    out, placed = km.build_ambience(events, 120, "lang", seed=1, loop=False)
    assert len(out) == 120 * R
    assert 3 <= placed <= 8                                    # lange Pausen → nur wenige Rufe
    level = np.abs(out).max(axis=1)
    quiet = (level < 1e-3).mean()
    assert quiet > 0.6                                         # überwiegend Stille – nervt nicht
    assert np.abs(out).max() <= 0.9


def test_short_pauses_place_more_events():
    events = [chirp(f) for f in (2000, 3000)]
    _, few = km.build_ambience(events, 120, "sehrlang", seed=2)
    _, many = km.build_ambience(events, 120, "kurz", seed=2)
    assert many > few


def test_no_immediate_repeat_and_bed():
    events = [chirp(2000), chirp(5000)]
    bed = np.random.default_rng(0).normal(0, 0.05, (5 * R, 2)).astype(np.float32)
    out, _ = km.build_ambience(events, 60, "kurz", bed, seed=3)
    level = np.abs(out).max(axis=1)
    assert (level < 1e-3).mean() < 0.05                        # Klangteppich füllt die Pausen


def test_loop_is_seamless():
    noise = np.random.default_rng(1).normal(0, 0.2, (20 * R, 2)).astype(np.float32)
    looped = km.make_loop(noise, 3.0)
    assert len(looped) == 17 * R
    jump = np.abs(looped[0] - looped[-1]).max()
    assert jump < 1.0


def test_chain_for_continuous_sounds():
    clips = [np.random.default_rng(i).normal(0, 0.1, (10 * R, 2)).astype(np.float32) for i in range(2)]
    out, placed = km.chain(clips, 60, loop=False)
    assert len(out) == 60 * R and placed >= 6
    assert (np.abs(out).max(axis=1) < 1e-4).mean() < 0.01      # durchgehend, keine Löcher


def test_resample():
    a = chirp(1000)
    b = km.resample(a, 48000)
    assert abs(len(b) - len(a) * R / 48000) <= 1


def test_suggestions():
    assert mv.suggest("Vogelgezwitscher")[0]["key"] == "voegel-wald"
    assert "Möwen am Meer" in [s["title"] for s in mv.suggest("vog")]
    assert mv.suggest("boss", mv.MUSIK)[0]["key"] == "boss"
    assert all(s["kind"] == mv.ATMO for s in mv.suggest("regen wald", mv.ATMO))
    assert mv.suggest("xyz") == []
    keys = [s["key"] for s in mv.SUGGESTIONS]
    assert len(keys) == len(set(keys))


def test_prompts():
    assert mv.music_prompt("", mv.by_key("dorf")).startswith("instrumental, fantasy")
    assert mv.music_prompt("ruhige Klaviermusik").startswith("instrumental, background music, ruhige Klaviermusik")
    plan = mv.atmo_plan("Regen im Wald")
    assert plan["event"].startswith("rain in the forest")
    bird = mv.atmo_plan("", mv.by_key("voegel-wald"))
    assert bird["bed"] and not bird["continuous"] and bird["pause"] == "lang"


def test_worker_and_setup_syntax():
    run = ROOT / "musik" / "container" / "run.py"
    ast.parse(run.read_text(encoding="utf-8"))
    out = subprocess.run([sys.executable, str(run), "--musik", "--prompt", " "], capture_output=True, text=True)
    assert out.returncode == 1 and out.stdout.startswith("ERR ")
    assert subprocess.run(["sh", "-n", str(ROOT / "musik" / "gibeon-musik-setup")]).returncode == 0
