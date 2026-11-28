"""Thumbnail Studio: Zeichnen und Vorlagen (braucht PySide6, sonst übersprungen).

    QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_thumbnail.py
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "thumbnail"))

from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402

import thumb_render as tr  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture()
def home(monkeypatch):
    d = tempfile.mkdtemp(prefix="thumb-")
    monkeypatch.setenv("XDG_DATA_HOME", d)
    return Path(d)


def photo(path, color="#33aa55"):
    img = QImage(400, 300, QImage.Format.Format_ARGB32)
    img.fill(QColor(color))
    img.save(str(path))
    return path


def test_render_size_and_background():
    d = tr.new_design()
    d["background"] = {"type": "farbe", "color1": "#ff0000", "dim": 0}
    img = tr.render(d)
    assert (img.width(), img.height()) == (1280, 720)
    assert QColor(img.pixel(640, 360)).name() == "#ff0000"


def test_dim_and_frame():
    d = tr.new_design()
    d["background"] = {"type": "farbe", "color1": "#ffffff", "dim": 50}
    d["frame"] = {"style": "schlicht", "color": "#0000ff", "width": 20}
    img = tr.render(d)
    assert QColor(img.pixel(5, 360)).name() == "#0000ff"            # Rahmen am Rand
    assert QColor(img.pixel(640, 360)).lightness() < 200             # abgedunkelt


def test_text_and_stickers_draw_something():
    d = tr.new_design()
    d["background"] = {"type": "farbe", "color1": "#000000"}
    d["texts"] = [tr.new_text("HALLO")]
    for kind, _, _ in tr.STICKERS:
        d["stickers"].append(tr.new_sticker(kind))
    blank = tr.render({**tr.new_design(), "background": {"type": "farbe", "color1": "#000000"}})
    for style, _ in tr.FRAMES:
        d["frame"]["style"] = style
        img = tr.render(d)
        assert img != blank
        row = [QColor(img.pixel(x, 360)).name() for x in range(420, 860, 4)]
        assert any(c != "#000000" for c in row)                          # Text in der Mitte


def test_image_layer_and_hit_rect(tmp_path):
    d = tr.new_design()
    d["images"] = [tr.new_image(photo(tmp_path / "a.png"))]
    d["images"][0].update({"x": 640, "y": 360, "outline": True})
    img = tr.render(d)
    assert QColor(img.pixel(640, 360)).name() == "#33aa55"
    assert tr.layer_rect("images", d["images"][0]).contains(640, 360)


def test_templates_roundtrip(home, tmp_path):
    src = photo(tmp_path / "hintergrund.jpg", "#123456")
    d = tr.new_design()
    d["background"].update({"type": "bild", "image": str(src)})
    d["images"] = [tr.new_image(photo(tmp_path / "ich.png"))]
    d["texts"] = [tr.new_text("FOLGE 1")]
    tid = tr.save_template(d, "Let's Play Serie")
    src.unlink()                                                     # Original weg – Vorlage bleibt nutzbar
    (tmp_path / "ich.png").unlink()
    items = tr.list_templates()
    assert [t["name"] for t in items] == ["Let's Play Serie"]
    assert Path(items[0]["preview"]).is_file()
    loaded = tr.load_template(tid)
    assert Path(loaded["background"]["image"]).is_file()
    assert Path(loaded["images"][0]["path"]).is_file()
    assert str(home) in loaded["background"]["image"]               # liegt im Programm, nicht auf dem Desktop
    # Aktualisieren ohne Bilder → alte Bild-Kopien werden aufgeräumt
    loaded["images"] = []
    tr.save_template(loaded, "Let's Play Serie", tid)
    folder = tr.templates_dir() / tid
    assert len(list(folder.glob("bild-*"))) == 1
    tr.rename_template(tid, "Neu")
    assert tr.list_templates()[0]["name"] == "Neu"
    tr.delete_template(tid)
    assert tr.list_templates() == []
