"""Jedes Schreibtisch-Widget muss sich auf einen anderen Monitor schieben lassen.

Die Shell lehnt in setWidgetScreen jeden Schlüssel ab, der nicht in DESKTOP_WIDGETS steht.
Ein neues Widget ohne Eintrag dort bleibt sonst still auf dem Hauptmonitor kleben.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "shell/creative_shell/__main__.py"
WALL = ROOT / "shell/creative_shell/qml/surfaces/Wallpaper.qml"


def desktop_widgets():
    for node in ast.parse(MAIN.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "DESKTOP_WIDGETS" for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError("DESKTOP_WIDGETS fehlt")


def test_alle_widgets_haben_monitorwahl():
    qml = WALL.read_text(encoding="utf-8")
    keys = set(re.findall(r'widgetOnScreen\("(\w+)"\)', qml)) | set(re.findall(r'widgetKey: "(\w+)"', qml))
    fehlt = keys - desktop_widgets()
    assert not fehlt, f"Monitorwahl abgelehnt für: {sorted(fehlt)}"
