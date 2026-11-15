"""Creative Engine: Weltraum-Shooter und eigene Steuerung (ohne Godot und ohne Oberfläche)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
from creative_engine import builder, project as proj  # noqa: E402


def test_neues_weltraumprojekt_ist_spielbar():
    data = proj.new_project("Sternenjagd", "weltraum")
    assert proj.GENRES["weltraum"][2] is True
    assert proj.validate(data) == []
    lvl = next(iter(data["levels"].values()))
    kinds = {e["kind"] for e in lvl["entities"]}
    assert {"start", "enemy", "planet", "base", "asteroids"} <= kinds
    assert len(data["ship"]["weapons"]) == 4


def test_ziele_werden_geprueft():
    data = proj.new_project("Leer", "weltraum", sample=False)
    lvl = next(iter(data["levels"].values()))
    assert proj.validate(data) == []          # freier Flug
    lvl["goal"] = "landen"
    assert any("Planet" in p for p in proj.validate(data))
    lvl["entities"].append({"kind": "planet", "x": 0, "y": 0, "z": -500, "radius": 100, "landable": True})
    assert proj.validate(data) == []


def test_steuerung_eigene_belegung_und_konflikte():
    data = proj.new_project("Sternenjagd", "weltraum")
    assert proj.control_conflicts(data) == []
    actions = proj.controls_for(data)
    for a in ("looping", "fassrolle_links", "fassrolle_rechts", "boost", "bremse", "feuer"):
        assert a in actions
    proj.set_binding(data, "looping", "keys", ["W"])         # W ist schon „Schneller“
    assert any("doppelt" in p for p in proj.control_conflicts(data))
    proj.set_binding(data, "looping", "pad", ["Y", "RS", "LB"])
    assert proj.controls_for(data)["looping"]["pad"] == ["Y", "RS"]
    proj.reset_controls(data)
    assert proj.controls_for(data)["looping"]["keys"] == ["R"]


def test_jumpnrun_angriffe_in_der_steuerung():
    data = proj.new_project("Insel")
    c = proj.controls_for(data)
    assert c["angriff1"]["keys"] == [data["player"]["attacks"][0]["key"]]
    assert "springen" in c and "looping" not in c


def test_builder_schreibt_steuerung_und_laufzeit(tmp_path):
    data = proj.new_project("Sternenjagd", "weltraum")
    proj.set_binding(data, "feuer", "keys", ["F"])
    game = builder.build(tmp_path / "p", data, tmp_path / "build")
    g = json.loads((game / "game.json").read_text(encoding="utf-8"))
    assert g["controls"]["feuer"]["keys"] == ["F"]
    assert (game / "space.gd").exists()
    assert "apply_controls" in (game / "main.gd").read_text(encoding="utf-8")


def test_laufzeit_kennt_alle_controller_und_maustasten():
    main = (Path(proj.__file__).parent / "runtime" / "main.gd").read_text(encoding="utf-8")
    for key, _label in proj.PAD_INPUTS + proj.MOUSE_INPUTS:
        assert f'"{key}":' in main, key


def test_pausenmenue_einstellbar_und_in_der_laufzeit(tmp_path):
    data = proj.new_project("Sternenjagd", "weltraum")
    pause = data["settings"]["pause"]
    assert pause["position"] == "mitte" and pause["buttons"]["weiter"] is True
    pause["position"] = "rechts"
    pause["labels"]["menu"] = "Zurück zum Titel"
    game = builder.build(tmp_path / "p", data, tmp_path / "build")
    g = json.loads((game / "game.json").read_text(encoding="utf-8"))
    assert g["settings"]["pause"]["position"] == "rechts"
    gd = (game / "pausemenu.gd").read_text(encoding="utf-8")
    runtime_defaults = proj.pause_default()
    for key, label in runtime_defaults["labels"].items():
        assert f'"{key}": "{label}"' in gd          # Editor und Laufzeit haben dieselben Standards
    assert "PauseMenu" in (game / "space.gd").read_text(encoding="utf-8")
    assert "PauseMenu" in (game / "level.gd").read_text(encoding="utf-8")


def test_planeten_gross_mit_atmosphaere_und_landeanimation():
    data = proj.new_project("Sternenjagd", "weltraum")
    lvl = next(iter(data["levels"].values()))
    planets = [e for e in lvl["entities"] if e["kind"] == "planet"]
    assert all(p["radius"] >= 800 for p in planets)          # Planeten im Verhältnis zum Schiff groß
    assert lvl["size"] >= 5000
    src = (Path(proj.__file__).parent / "runtime" / "space.gd").read_text(encoding="utf-8")
    for phase in ('"anflug"', '"abstieg"', '"aufsetzen"', '"start"', '"austritt"'):
        assert phase in src
    assert "func atmo_height" in src
