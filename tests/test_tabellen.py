"""Tabellen-Ansicht: Excel lesen (Werte, Formate, Farben, verbunden, Formeln) und Einbindung ins System."""
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tabellen"))
openpyxl = pytest.importorskip("openpyxl")
from orbit_tabellen import xlsxdata as x  # noqa: E402


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    f = tmp_path_factory.mktemp("xl") / "b.xlsx"
    subprocess.run([sys.executable, str(ROOT / "tools" / "tabellen-beispiel.py"), str(f)], check=True)
    return x.load(f)


def test_blaetter_und_groesse(book):
    assert [s.name for s in book.sheets] == ["Haushalt 2026", "Spiele", "Inventar"]
    sh = book.sheets[0]
    assert (sh.rows, sh.cols) == (15, 5) and sh.freeze == (3, 0)
    assert (0, 0, 1, 5) in sh.merged and (13, 1, 2, 4) in sh.merged


def test_deutsche_formate_und_farben(book):
    sh = book.sheets[0]
    assert sh.cells[(3, 1)].text == "3.250,00 €"
    assert sh.cells[(12, 1)].text == "17.11.2026"
    head = sh.cells[(2, 0)]
    assert head.bold and head.fill == "#4472C4" and head.color == "#FFFFFF" and head.align == "center"
    assert book.sheets[1].cells[(1, 2)].text == "WAHR"


def test_formeln_ohne_gespeicherten_wert_werden_nachgerechnet(book):
    sh = book.sheets[0]
    assert sh.cells[(3, 3)].text == "439,60 €" and sh.cells[(3, 3)].computed
    assert sh.cells[(3, 4)].text == "13,5 %"
    assert sh.cells[(10, 1)].text == "19.950,50 €" and sh.cells[(10, 1)].formula == "=SUM(B4:B9)"


def test_unbekannte_formeln_bleiben_sicher():
    assert x._translate("=VLOOKUP(A1,B:C,2)") is None
    assert x._translate("=__import__('os')") is None
    assert x._translate("=A1+1") == "_ref(0,0)+1"


@pytest.mark.parametrize("value,fmt,text", [
    (1234567.891, "#,##0.00", "1.234.567,89"), (0.256, "0%", "26 %"), (3.0, "General", "3"),
    (1 / 3, "General", "0,3333333333"), (False, "General", "FALSCH"), (dt.time(9, 5), "h:mm", "09:05"),
])
def test_zahlen(value, fmt, text):
    assert x.format_value(value, fmt) == text


def test_nur_per_doppelklick():
    desk = (ROOT / "tabellen" / "orbit-tabellen.desktop").read_text(encoding="utf-8")
    assert "NoDisplay=true" in desk and "spreadsheetml.sheet" in desk and "Exec=orbit-tabellen %f" in desk
    cf = (ROOT / "image" / "Containerfile").read_text(encoding="utf-8")
    assert "python3-openpyxl" in cf and "=orbit-tabellen.desktop/' >> \"$f\"" in cf


def test_querformat_aus_datei(book):
    assert book.sheets[2].landscape and not book.sheets[0].landscape
