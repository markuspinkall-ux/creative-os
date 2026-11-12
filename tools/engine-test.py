"""Test der Creative-Engine-Laufzeit mit echtem Godot (für den Workflow „Creative Engine prüfen“).

    python3 tools/engine-test.py <godot> <ausgabe>
Baut ein Beispielprojekt (inkl. selbst erzeugter GLB-Figur), lässt das Level automatisch spielen,
macht Bildschirmfotos (Splash, Menü, Level) und exportiert für Linux und Windows.
"""
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from creative_engine import builder, godot, project  # noqa: E402

GODOT = sys.argv[1]
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)


def cube_glb(path, color=(0.95, 0.55, 0.25, 1.0)):
    """Minimaler GLB-Würfel (Position + Index) mit Farbe – als Testfigur."""
    v = [(-.5, 0, -.5), (.5, 0, -.5), (.5, 1, -.5), (-.5, 1, -.5), (-.5, 0, .5), (.5, 0, .5), (.5, 1, .5), (-.5, 1, .5)]
    idx = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5]
    vb = b"".join(struct.pack("<3f", *p) for p in v)
    ib = b"".join(struct.pack("<H", i) for i in idx)
    ib += b"\0" * ((4 - len(ib) % 4) % 4)
    blob = vb + ib
    gltf = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "scale": [1, 2, 1]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
        "materials": [{"pbrMetallicRoughness": {"baseColorFactor": list(color)}}],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vb)},
                        {"buffer": 0, "byteOffset": len(vb), "byteLength": len(idx) * 2}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [-.5, 0, -.5], "max": [.5, 1, .5]},
                      {"bufferView": 1, "componentType": 5123, "count": len(idx), "type": "SCALAR"}],
    }
    js = json.dumps(gltf).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + blob
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)


def run(args, timeout=240, env=None, check=True):
    print("$", " ".join(map(str, args)), flush=True)
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
    out = r.stdout + r.stderr
    print(out[-4000:])
    bad = [l for l in out.splitlines() if "SCRIPT ERROR" in l or "Parse Error" in l or "Failed to load script" in l]
    if bad:
        raise SystemExit("GDScript-Fehler:\n" + "\n".join(bad))
    if check and r.returncode != 0:
        raise SystemExit(f"Fehler {r.returncode}")
    return out


work = Path(tempfile.mkdtemp())
folder = work / "Testspiel"
data = project.new_project("Testspiel")
folder.mkdir()
cube_glb(work / "figur.glb")
data["player"]["model"] = project.import_asset(folder, work / "figur.glb")
level_id = next(s["id"] for s in data["flow"] if s["type"] == "level")
data["levels"][level_id]["decor"].append({"model": data["player"]["model"], "x": 12, "y": 2, "z": -5, "height": 4})
project.save(folder, data)
game = builder.build(folder, data, work / "build")
print("Projekt:", sorted(p.name for p in game.iterdir()))

run([GODOT, *godot.import_args(game)], check=False)
out = run([GODOT, "--headless", "--path", str(game), "--quit-after", "4000", "--", f"--level={level_id}", "--autotest"],
          timeout=300, check=False)
print("Autotest:", [l for l in out.splitlines() if "AUTOTEST" in l])

xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"]
for name, extra in (("splash", ["--nach=1.2"]), ("menue", [f"--level={data['flow'][1]['id']}", "--nach=1.5"]),
                    ("level", [f"--level={level_id}", "--nach=3"])):
    run([*xvfb, GODOT, "--rendering-driver", "opengl3", "--path", str(game), "--resolution", "1280x720", "--",
         *extra, f"--screenshot={OUT / ('spiel-' + name + '.png')}", "--fenster"], timeout=120, check=False)

if godot.templates_ready():
    for preset, fname in (("Linux", "Testspiel.x86_64"), ("Windows", "Testspiel.exe")):
        target = work / "export" / preset / fname
        target.parent.mkdir(parents=True, exist_ok=True)
        run([GODOT, *godot.export_args(game, preset, target)], timeout=300, check=False)
        size = target.stat().st_size if target.exists() else 0
        print(f"Export {preset}: {size // 1024} KB")
        if size < 1_000_000:
            raise SystemExit(f"Export {preset} fehlgeschlagen")
    run([*xvfb, str(work / "export" / "Linux" / "Testspiel.x86_64"), "--rendering-driver", "opengl3", "--",
         f"--level={level_id}", f"--screenshot={OUT / 'export-linux.png'}", "--nach=3", "--fenster"],
        timeout=120, check=False)
print("Fertig.", sorted(p.name for p in OUT.iterdir()))
