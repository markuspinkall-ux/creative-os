"""KI-Liedstudio: Songtext-Aufbereitung und Stichwörter – ohne Qt.

    python3 -m pytest -q tests/test_lieder.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lieder"))

import lied_stil as ls  # noqa: E402


def test_sections_translated():
    text = "[Strophe 1]\nZeile eins\n\n[Refrain]\nLa la\n\n[Vor-Refrain]\nGleich\n\n[Brücke]\nAnders\n\n[Schluss]\nEnde"
    out = ls.to_ace(text)
    assert out.split("\n")[0] == "[verse]"
    for tag in ("[chorus]", "[pre-chorus]", "[bridge]", "[outro]"):
        assert tag in out


def test_skeleton_alone_is_instrumental():
    assert not ls.has_lyrics(ls.SKELETON)
    assert not ls.has_lyrics("")
    assert ls.has_lyrics("[Refrain]\nOh oh")


def test_empty_sections_dropped_and_solo_kept():
    out = ls.to_ace("[Intro]\n…\n\n[Strophe]\nText\n\n[Solo]\n\n[Refrain]\n...")
    assert out == "[verse]\nText\n\n[inst]"


def test_prompt():
    p = ls.build_prompt("schlager", "mann", "froehlich", "deutsch", 128, "akkordeon")
    assert p.startswith("german schlager")
    for part in ("male vocals", "happy", "german lyrics", "128 bpm", "akkordeon"):
        assert part in p
    assert "bpm" not in ls.build_prompt("pop", "frau")


def test_length_and_names():
    short = "[Refrain]\nEins\nZwei"
    long = "[Strophe]\n" + "\n".join(f"Zeile {i}" for i in range(60))
    assert ls.suggest_length(short) == 60
    assert ls.suggest_length(long) == 240
    assert ls.safe_name("Mein/Lied: Sommer!") == "Mein Lied Sommer"
    assert ls.safe_name("   ") == "Mein Lied"


def test_worker_takes_lyrics_file():
    run = ROOT / "musik" / "container" / "run.py"
    out = subprocess.run([sys.executable, str(run), "--musik", "--prompt", " ", "--lyrics-file",
                          str(Path(tempfile.mkdtemp()) / "x.txt")], capture_output=True, text=True)
    assert out.returncode == 1 and out.stdout.startswith("ERR ")      # Argument bekannt, leerer Prompt abgelehnt
