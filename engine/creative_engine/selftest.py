"""Selbsttest ohne Oberfläche: Projekt anlegen, Godot-Projekt bauen, Figur mit Bewegungen speichern."""

import json
import tempfile
from pathlib import Path

from . import builder, project as proj, skeleton as S


def run():
    work = Path(tempfile.mkdtemp(prefix="creative-engine-test-"))
    data = proj.new_project("Selbsttest")
    proj.add_step(data, "text", 1)
    proj.duplicate_step(data, len(data["flow"]) - 1)
    assert not proj.validate(data), proj.validate(data)
    figur = S.orient(S.demo_figure())
    joints = S.fit(figur["vertices"])
    anims = {k: S.preset(k) for k, _n in S.SLOTS}
    (work / "spiel" / "assets").mkdir(parents=True)
    S.export(work / "spiel" / "assets" / "figur.glb", figur, joints, anims)
    gltf, _bin = S.R.read_glb(work / "spiel" / "assets" / "figur.glb")
    assert [a["name"] for a in gltf["animations"]] == [k for k, _n in S.SLOTS]
    again = S.load_mesh(work / "spiel" / "assets" / "figur.glb")
    assert len(again["faces"]) == len(figur["faces"])
    data["player"]["model"] = "assets/figur.glb"
    proj.save(work / "spiel", data)
    assert proj.load(work / "spiel")["name"] == "Selbsttest"
    target = builder.build(work / "spiel", data, work / "build")
    game = json.loads((target / "game.json").read_text(encoding="utf-8"))
    assert len(game["flow"]) == 5 and (target / "assets" / "figur.glb").exists()
    parsed = S.parse_ai('{"name":"Ente","length":1,"loop":true,"keys":[{"t":0,"Hips":[0,0,12],"bob":0.01},'
                        '{"t":0.5,"Hips":[0,0,-12]}]}')
    assert parsed["tracks"]["Hips"][1][3] == -12
    print("Creative Engine Selbsttest: OK")
    return 0
