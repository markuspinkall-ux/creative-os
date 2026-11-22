"""Regionen: nur mit Zustimmung, nur das Land, einmal im Monat; Worker zählt richtig."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shell"))
from creative_shell import entwickler, region  # noqa: E402


def test_land_aus_zeitzone(tmp_path):
    tab = tmp_path / "zone.tab"
    tab.write_text("# kommentar\nDE\t+5230+01322\tEurope/Berlin\nAT\t+4813+01620\tEurope/Vienna\n", encoding="utf-8")
    assert region.country_from_tz("Europe/Berlin", (str(tab),)) == "DE"
    assert region.country_from_tz("Mars/Olympus", (str(tab),)) == ""
    assert region.country_from_lang("de_AT.UTF-8") == "AT"
    assert region.country_from_lang("C") == ""


def test_nur_mit_zustimmung_und_einmal_im_monat(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    gesendet = []

    class Antwort:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def urlopen(req, timeout=0):
        gesendet.append(json.loads(req.data))
        return Antwort()

    monkeypatch.setattr(region.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(region, "endpoint", lambda: "https://sammelstelle.example")
    monkeypatch.setattr(region, "country", lambda: "DE")
    assert region.consent() is None
    assert region.report_if_due() is False and gesendet == []          # nie gefragt → nichts
    region.set_consent(False)
    assert region.report_if_due() is False and gesendet == []          # abgelehnt → nichts
    region.set_consent(True)
    assert region.report_if_due() is True
    assert region.report_if_due() is False                             # diesen Monat schon
    assert len(gesendet) == 1 and gesendet[0]["land"] == "DE" and gesendet[0]["neu"] is True
    assert set(gesendet[0]) == {"land", "monat", "neu"}                # sonst nichts


def test_ohne_sammelstelle_nichts(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(region, "endpoint", lambda: "")
    region.set_consent(True)
    assert region.report_if_due() is False


def test_widget_zeilen():
    rows = entwickler.regionen_rows({"installationen": {"DE": 5, "AT": 2}, "aktiv": {"DE": 3, "CH": 1}})
    assert [r["land"] for r in rows] == ["Deutschland", "Österreich", "Schweiz"]
    assert rows[0]["inst"] == 5 and rows[0]["aktiv"] == 3


def test_worker():
    if not shutil.which("node"):
        pytest.skip("node fehlt")
    subprocess.run(["node", str(ROOT / "tests/regionen_worker_probe.mjs")], check=True)


def test_zustimmung_abfragen():
    welcome = (ROOT / "welcome/creative_welcome/qml/Main.qml").read_text(encoding="utf-8")
    system = (ROOT / "settings/creative_settings/qml/pages/SystemPage.qml").read_text(encoding="utf-8")
    assert "regionConsent.setEnabled(v)" in welcome and "regionConsent.setEnabled(v)" in system
