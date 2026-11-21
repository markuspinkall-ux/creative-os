"""Broadcast, Deck und Shots stehen nicht im Startmenü; Deck sitzt im Tray."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shell"))
sys.path.insert(0, str(ROOT / "deck"))

DESKTOPS = {
    "broadcast/creative-broadcast.desktop",
    "deck/creative-deck.desktop",
    "shots/creative-shots.desktop",
}


def _main_section(path):
    return (ROOT / path).read_text(encoding="utf-8").split("\n[Desktop Action", 1)[0]


def test_nicht_im_startmenue():
    for d in DESKTOPS:
        sec = _main_section(d)
        assert "NoDisplay=true" in sec, d
        assert "X-Orbit-Tray=true" in sec, d


def test_nicht_in_orbit_suite():
    src = (ROOT / "shell/creative_shell/apps.py").read_text(encoding="utf-8")
    suite = src.split("SUITE = {", 1)[1].split("}", 1)[0]
    for d in DESKTOPS:
        assert Path(d).name not in suite


def test_deck_programmauswahl_zeigt_tray_apps(tmp_path, monkeypatch):
    folder = tmp_path / "applications"
    folder.mkdir()
    for d in DESKTOPS:
        (folder / Path(d).name).write_text((ROOT / d).read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "versteckt.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Versteckt\nExec=x\nNoDisplay=true\n", encoding="utf-8")
    from creative_deck import apps as deck_apps
    monkeypatch.setattr(deck_apps, "data_dirs", lambda: [str(tmp_path)])
    ids = {a["id"] for a in deck_apps.installed()}
    assert {"creative-broadcast.desktop", "creative-deck.desktop", "creative-shots.desktop"} <= ids
    assert "versteckt.desktop" not in ids


def test_deck_status(tmp_path):
    import pytest
    pytest.importorskip("PySide6")
    from creative_shell.decktray import read_devices
    p = tmp_path / "status.json"
    assert read_devices(p) == []
    p.write_text(json.dumps({"geraete": [{"modell": "Stream Deck MK.2"}]}), encoding="utf-8")
    assert read_devices(p) == ["Stream Deck MK.2"]
    p.write_text(json.dumps({"geraete": [], "beendet": True}), encoding="utf-8")
    assert read_devices(p) == []


def test_deck_im_tray_und_autostart():
    qml = (ROOT / "shell/creative_shell/qml/surfaces/Taskbar.qml").read_text(encoding="utf-8")
    assert "deckTray.open()" in qml and 'focusApp("creative-deck.desktop")' in qml
    main = (ROOT / "shell/creative_shell/__main__.py").read_text(encoding="utf-8")
    assert '"deckTray": DeckTray()' in main
    for d in ("icons", "icons-light"):
        assert (ROOT / f"shell/creative_shell/qml/Creative/{d}/deck.svg").is_file()
    sup = (ROOT / "shell/session/creative-shell-supervisor").read_text(encoding="utf-8")
    assert "creative-deck --hintergrund" in sup


def test_widgets_nur_per_rechtsklick():
    """Widgets steht nicht im Startmenü, ist aber über den Schreibtisch-Rechtsklick erreichbar."""
    assert "NoDisplay=true" in _main_section("widgets/creative-widgets.desktop")
    src = (ROOT / "shell/creative_shell/apps.py").read_text(encoding="utf-8")
    assert '"creative-widgets.desktop"' not in src.split("SUITE = {", 1)[1].split("}", 1)[0]
    qml = (ROOT / "shell/creative_shell/qml/surfaces/Wallpaper.qml").read_text(encoding="utf-8")
    assert 'act: "widgets"' in qml


def test_pictures_nur_als_standard_app():
    """Pictures steht nicht im Startmenü, öffnet aber weiterhin Bilder (Standard-App)."""
    assert "NoDisplay=true" in _main_section("pictures/creative-pictures.desktop")
    cf = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
    assert "=creative-pictures.desktop/' >> /etc/xdg/mimeapps.list" in cf


def test_engine_entfernt():
    """Engine ist komplett raus; installierte Engine wird beim Anmelden entfernt."""
    assert not (ROOT / "engine").exists()
    for f in ("shell/creative_shell/apps.py", "shell/creative_shell/icons.py", "image/Containerfile",
              "software/creative-software"):
        assert "org.creativeos.Engine" not in (ROOT / f).read_text(encoding="utf-8"), f
    user = (ROOT / "theme/apps/creative-theme-user").read_text(encoding="utf-8")
    assert "flatpak uninstall --user -y --noninteractive org.creativeos.Engine" in user


def test_3d_ansicht_nur_als_standard_app():
    """3D-Ansicht steht nicht im Startmenü, öffnet aber weiterhin .glb/.gltf (Standard-App)."""
    assert "NoDisplay=true" in _main_section("viewer3d/creative-3dansicht.desktop")
    cf = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
    assert "model/gltf-binary=creative-3dansicht.desktop" in cf
