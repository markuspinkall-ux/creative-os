"""Tabellen-Ansicht drucken: Seitenaufteilung (ohne Qt)."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tabellen"))
from orbit_tabellen import druck as d  # noqa: E402


def blatt(rows, cols, breite=64, hoehe=20, **kw):
    cells = {(r, c): SimpleNamespace(text="x", fill=None) for r in range(rows) for c in range(cols)}
    base = dict(cells=cells, widths={c: breite for c in range(cols)}, heights={-1: hoehe},
                hidden_rows=set(), hidden_cols=set(), merged=[], freeze=(0, 0), name="T", landscape=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_bereich_bis_letzter_inhalt():
    sh = blatt(5, 3)
    sh.cells[(9, 6)] = SimpleNamespace(text="", fill="#ff0000")
    assert d.ganzes_blatt(sh) == d.Bereich(0, 9, 0, 6)
    assert d.ganzes_blatt(blatt(0, 0)) is None


def test_hochformat_mehr_zeilen_querformat_mehr_spalten():
    sh = blatt(100, 12)
    b = d.ganzes_blatt(sh)
    # A4 minus Ränder bei 96 dpi: hoch ~703×1009 px, quer ~1032×680 px
    hoch = d.seiten(sh, b, 703, 1009 - d.FOOTER_PX, 1.0)
    quer = d.seiten(sh, b, 1032, 680 - d.FOOTER_PX, 1.0)
    assert len({tuple(p.cols) for p in hoch}) == 2      # 12 × 64 px passt hochkant nicht in die Breite
    assert len({tuple(p.cols) for p in quer}) == 1
    assert len(hoch[0].rows) > len(quer[0].rows)
    # Reihenfolge wie Excel: erst nach unten
    assert hoch[0].cols == hoch[1].cols


def test_auf_seitenbreite_anpassen():
    sh = blatt(10, 20)
    b = d.ganzes_blatt(sh)
    s = d.massstab(sh, b, 703, True)
    assert abs(s - 703 / (20 * 64)) < 1e-9
    assert len({tuple(p.cols) for p in d.seiten(sh, b, 703, 1000, s)}) == 1
    assert d.massstab(blatt(3, 2), d.ganzes_blatt(blatt(3, 2)), 703, True) == 1.0   # nie vergrößern


def test_kopfzeilen_wiederholen_und_versteckte_weglassen():
    sh = blatt(200, 3, freeze=(1, 0), hidden_rows={5}, hidden_cols={1})
    pages = d.seiten(sh, d.ganzes_blatt(sh), 703, 600, 1.0, wiederholen=1)
    assert len(pages) > 1 and all(p.rows[0] == 0 for p in pages)
    assert all(5 not in p.rows and 1 not in p.cols for p in pages)
    alle = [r for p in pages for r in p.rows if r != 0]
    assert alle == [r for r in range(1, 200) if r != 5]
