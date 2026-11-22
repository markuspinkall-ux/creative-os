"""Fenster öffnen dynamisch: KWin-Effekt „gibeon-fenster“ und die Shell-Anbindung."""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EFFECT = ROOT / "shell/kwin/gibeon-fenster"


def test_effekt_paket():
    meta = json.loads((EFFECT / "metadata.json").read_text(encoding="utf-8"))
    assert meta["KPlugin"]["Id"] == "gibeon-fenster"
    assert meta["KPackageStructure"] == "KWin/Effect"
    code = (EFFECT / "contents/code/main.js").read_text(encoding="utf-8")
    for needle in ("effects.windowAdded.connect", "effects.windowClosed.connect", "minimizedChanged",
                   'readConfig("Tasten"', 'readConfig("Start"', "Effect.Translation", "Effect.Scale"):
        assert needle in code, needle
    if shutil.which("node"):
        subprocess.run(["node", "--check", str(EFFECT / "contents/code/main.js")], check=True)


def test_eingebaut_und_eingeschaltet():
    rc = (ROOT / "shell/kwin/kwinrc").read_text(encoding="utf-8")
    assert "gibeon-fensterEnabled=true" in rc and "scaleEnabled=false" in rc and "squashEnabled=false" in rc
    cf = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
    assert "COPY shell/kwin/gibeon-fenster /usr/share/kwin/effects/gibeon-fenster" in cf
    tb = (ROOT / "shell/creative_shell/qml/surfaces/Taskbar.qml").read_text(encoding="utf-8")
    assert "windowAnim.setTaskPoints(" in tb
    sm = (ROOT / "shell/creative_shell/qml/surfaces/StartMenu.qml").read_text(encoding="utf-8")
    assert sm.count("root.noteLaunch(") == 2


def test_namen():
    import sys
    import pytest
    pytest.importorskip("PySide6")
    sys.path.insert(0, str(ROOT / "shell"))
    from creative_shell.fensteranimation import names_for
    n = names_for("org.kde.dolphin", "org.kde.dolphin.desktop", [{"app": "org.kde.dolphin", "cls": "Dolphin"}])
    assert n[:2] == ["org.kde.dolphin", "dolphin"]
