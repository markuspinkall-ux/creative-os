"""Impressum in Systemsteuerung › System: Daten aus impressum.json, Karte erst bei vollständigen Angaben."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "settings"))


def _loader():
    src = (ROOT / "settings" / "creative_settings" / "system.py").read_text(encoding="utf-8")
    start = src.index("def load_impressum")
    end = src.index("\n\n\n", start)
    ns = {"json": json, "Path": Path, "IMPRESSUM": ROOT / "settings" / "creative_settings" / "impressum.json"}
    exec(src[start:end], ns)
    return ns["load_impressum"]


def test_impressum_datei_und_laden(tmp_path):
    load = _loader()
    data = load(ROOT / "settings" / "creative_settings" / "impressum.json")
    assert data["name"] == "Markus Pinkall" and set(data) == {"name", "anschrift", "email", "web"}
    f = tmp_path / "i.json"
    f.write_text('{"name": " A ", "anschrift": "B", "email": "c@d.de"}', encoding="utf-8")
    assert load(f) == {"name": "A", "anschrift": "B", "email": "c@d.de", "web": ""}
    assert load(tmp_path / "fehlt.json") == {}


def test_karte_unter_quellcode_und_lizenzen():
    qml = (ROOT / "settings" / "creative_settings" / "qml" / "pages" / "SystemPage.qml").read_text(encoding="utf-8")
    assert qml.index('title: "Quellcode und Lizenzen"') < qml.index('title: "Impressum"')
    assert "visible: !!imp.name && !!imp.anschrift && !!imp.email" in qml
    assert "alle Rechte vorbehalten" not in qml
