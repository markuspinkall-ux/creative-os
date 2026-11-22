"""Startmenü nach Kategorien: Einteilung der Apps und Stil-Wahl."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shell"))
pytest.importorskip("PySide6")
from creative_shell import apps  # noqa: E402


def _e(did, cats):
    e = apps.AppEntry(did, "", did, "", "", "", "true", False)
    e.categories = cats
    return e


def test_einteilung():
    assert apps.category_of(_e("steam.desktop", ["Game"])) == "Spiele"
    assert apps.category_of(_e("creative-mail.desktop", ["Network", "Email"])) == "Internet"
    assert apps.category_of(_e("gibeon-studio.desktop", ["AudioVideo", "Video"])) == "Kreativ und Medien"
    assert apps.category_of(_e("orbit-tabellen.desktop", ["Office", "Spreadsheet"])) == "Büro"
    assert apps.category_of(_e("creative-notes.desktop", ["Utility", "TextEditor", "Development"])) == "Büro"
    assert apps.category_of(_e("creative-settings.desktop", ["Settings", "System"])) == "System"
    assert apps.category_of(_e("x.desktop", [])) == "Sonstige"


def test_standard_ist_kategorien(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert apps.start_menu_style() == "kategorien"
    from creative_shell import config
    config.set_value("startMenuStyle", "alphabet")
    assert apps.start_menu_style() == "alphabet"
    config.set_value("startMenuStyle", "quatsch")
    assert apps.start_menu_style() == "kategorien"


def test_kategorien_aus_desktop_datei(tmp_path):
    f = tmp_path / "x.desktop"
    f.write_text("[Desktop Entry]\nType=Application\nName=X\nExec=true\nCategories=Graphics;3DGraphics;\n", encoding="utf-8")
    e = apps.parse_desktop_file(f, "x.desktop", ["de"])
    assert e.categories == ["Graphics", "3DGraphics"] and apps.category_of(e) == "Kreativ und Medien"
