"""Widgets lassen sich mit gedrückter Maustaste auf einen anderen Monitor ziehen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ziehen_ueber_monitore():
    qml = (ROOT / "shell/creative_shell/qml/surfaces/Wallpaper.qml").read_text(encoding="utf-8")
    # alle verschiebbaren Widgets: RSS/Wetter, Uhr & Co., Leistungsanzeige, Ablage
    assert qml.count("root.crossDragMove(") == 4
    assert qml.count("root.crossDragDrop(") == 4
    assert "shell.widgetGhost" in qml and "visible: g.screen === root.screenName" in qml
    # Dateien und Ordner genauso – der alte Rechtsklick „Auf … verschieben“ ist weg
    assert "root.iconCrossTarget(p.x, p.y)" in qml and "desktop.placeDragged(path, crossIcon.screen" in qml
    assert "MonitorGripMenu" not in qml and "monitorMenu" not in qml and '"screen:"' not in qml


def test_obere_leiste_bei_maximiert():
    """Maximiertes Fenster: obere Leiste weg, kein Abstand, Uhr unten in der Taskleiste."""
    main = (ROOT / "shell/creative_shell/__main__.py").read_text(encoding="utf-8")
    assert "shell.watch_tasks(tasks)" in main and "tasks.maximized_outputs()" in main
    js = (ROOT / "shell/kwin/creative-tasks/contents/code/main.js").read_text(encoding="utf-8")
    assert "maximized: isMaximized(w)" in js and "fullscreen: !!w.fullScreen" in js
    assert "creative-abstandEnabled=false" in (ROOT / "shell/kwin/kwinrc").read_text(encoding="utf-8")
    bar = (ROOT / "shell/creative_shell/qml/surfaces/Taskbar.qml").read_text(encoding="utf-8")
    assert "id: clockPill" in bar and "anchors.right: clockPill.left" in bar
    top = (ROOT / "shell/creative_shell/qml/surfaces/Topbar.qml").read_text(encoding="utf-8")
    assert "toggleCalendar" not in top
    # eingefahren: nur ein Streifen oben nimmt die Maus, dann fährt die Leiste herein
    assert "transform: Translate { y: root.shift }" in top and "shell.setInputRect(Window.window, 0, 0, trayRight, edge)" in top
    # ausgefahren nur am Tray: rechts bleiben die Fensterknöpfe (Minimieren/Maximieren/Schließen) bedienbar
    assert "shell.setInputRect(Window.window, 0, 0, trayRight, height)" in top
    assert "opacity: shown ? 1 : 0" in top
    host = (ROOT / "shell/creative_shell/qml/HostLayer.qml").read_text(encoding="utf-8")
    assert "exclusionZone: isBar ? (autoHide ? 0 : surfaceHeight)" in host and "HoverHandler" in host
    assert 'win.setProperty("autoHide", name in wanted)' in main and "def setInputRect(" in main


def test_maximized_outputs():
    import sys
    import pytest
    pytest.importorskip("PySide6")
    sys.path.insert(0, str(ROOT / "shell"))
    from creative_shell.tasks import TaskModel
    m = TaskModel.__new__(TaskModel)
    m._windows = [
        {"output": "DP-1", "maximized": True},
        {"output": "DP-2", "maximized": True, "minimized": True},
        {"output": "HDMI-A-1", "fullscreen": True},
        {"output": "DP-3"},
    ]
    assert m.maximized_outputs() == {"DP-1", "HDMI-A-1"}
    main = (ROOT / "shell/creative_shell/__main__.py").read_text(encoding="utf-8")
    for part in ("def screenAt(", "def screenGeometry(", "def setWidgetGhost("):
        assert part in main


def test_obere_leiste_fluid():
    """Fluid-Design: Tray oben links, Uhrzeit rechts, Taskleiste unten ohne Tray, Menüs oben."""
    top = (ROOT / "shell/creative_shell/qml/surfaces/Topbar.qml").read_text(encoding="utf-8")
    assert "shell.toggleQuickPanel(root.screenName)" in top
    tray = (ROOT / "shell/creative_shell/qml/surfaces/TrayIcons.qml").read_text(encoding="utf-8")
    assert "trayApps.items" in tray and 'text: "Gibeon OS"' in top
    bar = (ROOT / "shell/creative_shell/qml/surfaces/Taskbar.qml").read_text(encoding="utf-8")
    assert ("toggleQuickPanel" not in bar or "visible: shell.trayInTaskbar" in bar) and "trash.open()" in bar
    assert "shell.toggleCalendar(root.screenName)" in bar
    main = (ROOT / "shell/creative_shell/__main__.py").read_text(encoding="utf-8")
    assert '"Topbar.qml"' in main and "TOP_HEIGHT = 50" in main
    host = (ROOT / "shell/creative_shell/qml/HostLayer.qml").read_text(encoding="utf-8")
    assert "AnchorTop" in host and '"topleft"' in host
    for f in ("QuickPanel", "BluetoothMenu", "MessengerMenu", "TrayAppMenu"):
        qml = (ROOT / f"shell/creative_shell/qml/surfaces/{f}.qml").read_text(encoding="utf-8")
        assert "root.atTop ? parent.top" in qml, f


def test_fluid_glas():
    """Fluid-Glas: durchscheinende Leisten/Startmenü, KWin-Weichzeichnen über KWindowEffects."""
    glas = (ROOT / "shell/creative_shell/glas.py").read_text(encoding="utf-8")
    assert "_ZN14KWindowEffects16enableBlurBehindEP7QWindowbRK7QRegion" in glas
    for f in ("Taskbar", "Topbar", "StartMenu"):
        qml = (ROOT / f"shell/creative_shell/qml/surfaces/{f}.qml").read_text(encoding="utf-8")
        assert "shell.setBlur(Window.window" in qml and "Theme.glass" in qml, f
    assert "blurEnabled=true" in (ROOT / "shell/kwin/kwinrc").read_text(encoding="utf-8")


def test_widgets_glas():
    qml = (ROOT / "shell/creative_shell/qml/surfaces/Wallpaper.qml").read_text(encoding="utf-8")
    assert "component GlassBackdrop" in qml and "id: wallLayerItem" in qml and "import QtQuick.Effects" in qml
    for target in ("widget", "extra", "statsBox", "shelfBox"):
        assert f"target: {target}" in qml, target


def test_glas_aus_wird_neu_gezeichnet():
    # Ohne neues Bild bleibt unter Wayland das alte Glas stehen (Streifen oben links)
    glas = (ROOT / "shell/creative_shell/glas.py").read_text(encoding="utf-8")
    assert '"update", "requestUpdate"' in glas
    top = (ROOT / "shell/creative_shell/qml/surfaces/Topbar.qml").read_text(encoding="utf-8")
    assert "if (!shown) shell.setBlur(Window.window, [])" in top


def test_tray_position():
    tb = (ROOT / "shell/creative_shell/qml/surfaces/Taskbar.qml").read_text(encoding="utf-8")
    top = (ROOT / "shell/creative_shell/qml/surfaces/Topbar.qml").read_text(encoding="utf-8")
    tray = (ROOT / "shell/creative_shell/qml/surfaces/TrayIcons.qml").read_text(encoding="utf-8")
    main = (ROOT / "shell/creative_shell/__main__.py").read_text(encoding="utf-8")
    assert "visible: shell.trayInTaskbar" in tb and "TrayIcons {" in tb and "TrayIcons {" in top
    assert "root." not in tray                       # eigenständig, Monitor über screenName
    assert 'return "right" if self._tray_pos == "taskleiste" else "topleft"' in main
    look = (ROOT / "settings/creative_settings/qml/pages/LookPage.qml").read_text(encoding="utf-8")
    assert 'look.setTrayPosition("taskleiste")' in look and 'look.setTrayPosition("oben")' in look
