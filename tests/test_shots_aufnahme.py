"""Shots: Desktop als Video aufnehmen (Aufnehmen / Stopp)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shots"))

from creative_shots import recorder  # noqa: E402


def test_pipeline_mit_grafikkarte_und_ton(monkeypatch):
    monkeypatch.setattr(recorder, "has", lambda e: e in ("vah264enc", "x264enc", "avenc_aac"))
    desc, out = recorder.build_pipeline(7, 42, "/tmp/Aufnahme 1.mp4", True)
    assert out == "/tmp/Aufnahme 1.mp4"
    assert "pipewiresrc fd=7 path=42" in desc and "vah264enc" in desc and "framerate=60/1" in desc
    assert "pulsesrc device=@DEFAULT_MONITOR@" in desc and "avenc_aac" in desc
    assert 'filesink location="/tmp/Aufnahme 1.mp4"' in desc and "mp4mux" in desc


def test_pipeline_ohne_ton_und_ohne_h264(monkeypatch):
    monkeypatch.setattr(recorder, "has", lambda e: e == "opusenc")
    desc, out = recorder.build_pipeline(3, 9, "/tmp/a.mp4", False)
    assert out == "/tmp/a.webm" and "vp8enc" in desc and "webmmux" in desc
    assert "pulsesrc" not in desc


def test_oberflaeche():
    snip = (ROOT / "shots/creative_shots/qml/SnipOverlay.qml").read_text(encoding="utf-8")
    main = (ROOT / "shots/creative_shots/qml/Main.qml").read_text(encoding="utf-8")
    bar = (ROOT / "shots/creative_shots/qml/RecordBar.qml").read_text(encoding="utf-8")
    assert "shots.startRecording()" in snip and "shots.startRecording()" in main
    assert "RecordBar {}" in main and "shots.stopRecording()" in bar
    backend = (ROOT / "shots/creative_shots/backend.py").read_text(encoding="utf-8")
    assert '"creative_shots.recorder"' in backend and "Bildschirmaufnahmen" in backend
    assert "creative-shots --record" in (ROOT / "shots/creative-shots.desktop").read_text(encoding="utf-8")
