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
from creative_engine import builder, godot, project, skeleton  # noqa: E402

GODOT = sys.argv[1]
OUT = Path(sys.argv[2]).resolve()
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


def png(path, w, h, pixel):
    """Kleines PNG ohne Zusatzpakete: pixel(x, y) -> (r, g, b, a)."""
    import zlib
    raw = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def bubble_px(x, y, n=96, r=26):
    """Eigene Sprechblasen-Grafik: abgerundetes Kästchen mit dickem orangem Rand."""
    cx = min(max(x, r), n - 1 - r)
    cy = min(max(y, r), n - 1 - r)
    d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
    if d > r:
        return (0, 0, 0, 0)
    return (255, 150, 60, 255) if d > r - 6 or min(x, y, n - 1 - x, n - 1 - y) < 6 else (255, 248, 230, 255)


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
seite = project.add_step(data, "seite", 1)
folder.mkdir()
cube_glb(work / "kiste.glb")
kiste = project.import_asset(folder, work / "kiste.glb")
# Spielfigur wie aus dem Charakter-Editor: Beispielfigur mit Skelett und allen festen Bewegungen
figur = skeleton.orient(skeleton.demo_figure())
joints = skeleton.fit(figur["vertices"])
anims = {k: skeleton.preset(k, waddle=14 if k == "walk" else 0, flap=30 if k == "walk" else 0)
         for k, _n in skeleton.SLOTS + skeleton.ATTACK_SLOTS}
(folder / "assets").mkdir(exist_ok=True)
skeleton.export(folder / "assets" / "held-figur.glb", figur, joints, anims)
data["player"]["model"] = "assets/held-figur.glb"
level_id = next(s["id"] for s in data["flow"] if s["type"] == "level")
# Eigene Grafiken: Sprechblase und Münz-Symbol; Gegner halten 3 Treffer aus, zwei Angriffe
png(folder / "assets" / "blase.png", 96, 96, bubble_px)
png(folder / "assets" / "muenze.png", 32, 32,
    lambda x, y: (255, 200, 40, 255) if (x - 15.5) ** 2 + (y - 15.5) ** 2 < 196 else (0, 0, 0, 0))
data["settings"]["ui"].update({"bubble": "assets/blase.png", "bubbleMargin": 30, "coin": "assets/muenze.png"})
data["player"]["attacks"].append(project.new_attack(1))
for e in data["levels"][level_id]["entities"]:
    if e["kind"] == "enemy":
        e["hp"] = 3
# Video: Testbild (3 s) als Ogg Theora – Splash im Vollbild, auf der Seite als Fenster
run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-t", "3",
     "-c:v", "libtheora", "-q:v", "6", str(folder / "assets" / "film.ogv")], timeout=120)
data["flow"][0].update({"bgVideo": "assets/film.ogv", "bgRatio": 16 / 9, "untilVideoEnd": True, "text": ""})
seite["elements"].append({"kind": "video", "video": "assets/film.ogv", "x": 0.5, "y": 0.62, "w": 0.4, "h": 0.4,
                          "fit": "contain", "ratio": 16 / 9, "loop": True, "after": 0.0})
data["levels"][level_id]["decor"].append({"model": kiste, "x": 12, "y": 2, "z": -5, "height": 4})
for e in data["levels"][level_id]["entities"]:
    if e["kind"] == "npc":
        e["model"] = "assets/held-figur.glb"
project.save(folder, data)
game = builder.build(folder, data, work / "build")
print("Projekt:", sorted(p.name for p in game.iterdir()))

run([GODOT, *godot.import_args(game)], check=False)
out = run([GODOT, "--headless", "--path", str(game), "--fixed-fps", "60", "--quit-after", "2400", "--", f"--level={level_id}", "--autotest"],
          timeout=300, check=False)
print("Autotest:", [l for l in out.splitlines() if "AUTOTEST" in l])

xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"]
for name, extra in (("splash", ["--nach=1.6"]), ("menue", [f"--level={data['flow'][1]['id']}", "--nach=1.5"]),
                    ("level", [f"--level={level_id}", "--nach=3"]),
                    ("lauf", [f"--level={level_id}", "--autotest", "--nach=2.4"]),
                    ("dialog", [f"--level={level_id}", "--autotest", "--nach=1.3"]),
                    ("seite", [f"--level={seite['id']}", "--nach=2.2"]),
                    ("angriff", [f"--level={level_id}", "--autotest", "--nach=6.6"])):
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
