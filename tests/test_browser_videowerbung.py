"""Videowerbung auf YouTube/Twitch (preload-videoad.js): Skript-Logik in Node prüfen, Einbindung im Browser."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "webbrowser" / "app"


@pytest.mark.skipif(not shutil.which("node"), reason="node fehlt")
def test_werbedaten_werden_entfernt():
    out = subprocess.run(["node", str(ROOT / "tools" / "browser-videowerbung-test.js")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "alles ok" in out.stdout


def test_preload_eingebunden_und_schaltbar():
    main = (APP / "main.js").read_text(encoding="utf-8")
    assert "registerPreloadScript" in main and "preload-videoad.js" in main
    assert "'creative-videoad'" in main and "'adblock-video'" in main
    assert "videoAdFor" in (APP / "adblock.js").read_text(encoding="utf-8")
    assert "sw-video" in (APP / "ui" / "ui.js").read_text(encoding="utf-8")
    pre = (APP / "preload-videoad.js").read_text(encoding="utf-8")
    assert "executeInMainWorld" in pre       # früh und synchron im Hauptkontext, nicht per IPC später
