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
