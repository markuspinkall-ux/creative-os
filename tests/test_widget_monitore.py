"""Widgets lassen sich mit gedrückter Maustaste auf einen anderen Monitor ziehen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ziehen_ueber_monitore():
    qml = (ROOT / "shell/creative_shell/qml/surfaces/Wallpaper.qml").read_text(encoding="utf-8")
    # alle verschiebbaren Widgets: RSS/Wetter, Uhr & Co., Leistungsanzeige
    assert qml.count("root.crossDragMove(") == 3
    assert qml.count("root.crossDragDrop(") == 3
    assert "shell.widgetGhost" in qml and "visible: g.screen === root.screenName" in qml
    main = (ROOT / "shell/creative_shell/__main__.py").read_text(encoding="utf-8")
    for part in ("def screenAt(", "def screenGeometry(", "def setWidgetGhost("):
        assert part in main


def test_obere_leiste_fluid():
    """Fluid-Design: Tray oben links, Uhrzeit rechts, Taskleiste unten ohne Tray, Menüs oben."""
    top = (ROOT / "shell/creative_shell/qml/surfaces/Topbar.qml").read_text(encoding="utf-8")
    assert "shell.toggleQuickPanel(root.screenName)" in top and "shell.toggleCalendar(root.screenName)" in top
    assert "trayApps.items" in top and 'text: "Gibeon OS"' in top
    bar = (ROOT / "shell/creative_shell/qml/surfaces/Taskbar.qml").read_text(encoding="utf-8")
    assert "toggleQuickPanel" not in bar and "trash.open()" in bar
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
