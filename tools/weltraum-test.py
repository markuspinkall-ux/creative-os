"""Weltraum-Shooter der Engine mit echtem Godot prüfen (für „Engine prüfen“).

    python3 tools/weltraum-test.py GODOT ausgabe/

Baut das Beispiel-Weltraumprojekt, lässt den Autopiloten kämpfen, reparieren und landen,
macht Bildschirmfotos (Kampf, Schaden, Basis, Planet, gelandet) und exportiert für Linux.
"""
import json
import math
import struct
import wave
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "engine"))
from creative_engine import builder, godot, project, skeleton  # noqa: E402

GODOT = sys.argv[1]
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)


def cube_glb(path, color=(0.95, 0.55, 0.25, 1.0)):
    """Minimaler GLB-Würfel (wie in engine-test.py) – als eigenes Testmodell."""
    v = [(-.5, 0, -.5), (.5, 0, -.5), (.5, 1, -.5), (-.5, 1, -.5), (-.5, 0, .5), (.5, 0, .5), (.5, 1, .5), (-.5, 1, .5)]
    idx = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5]
    vb = b"".join(struct.pack("<3f", *p) for p in v)
    ib = b"".join(struct.pack("<H", i) for i in idx)
    ib += b"\0" * ((4 - len(ib) % 4) % 4)
    blob = vb + ib
    gltf = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "scale": [1, 0.6, 2.4]}],
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
    import zlib
    raw = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def ring(x, y, n, color):
    d = ((x - n / 2 + .5) ** 2 + (y - n / 2 + .5) ** 2) ** .5
    return color if n * 0.3 < d < n * 0.45 or (abs(x - n / 2) < 2 and abs(y - n / 2) < n * 0.2) else (0, 0, 0, 0)


def wav(path, secs, freq):
    """Kurze Test-WAV (16 Bit, mono) als eigene Musik bzw. eigener Klang."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / 22050)))
                               for i in range(int(secs * 22050))))


def run(args, timeout=240, check=True):
    print("$", " ".join(map(str, args)), flush=True)
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    out = r.stdout + r.stderr
    print(out[-5000:])
    bad = [l for l in out.splitlines() if "SCRIPT ERROR" in l or "Parse Error" in l or "Failed to load script" in l
           or "SHADER ERROR" in l]
    if bad:
        raise SystemExit("Fehler in Skript oder Shader:\n" + "\n".join(bad))
    if check and r.returncode != 0:
        raise SystemExit(f"Fehler {r.returncode}")
    return out


work = Path(tempfile.mkdtemp())
folder = work / "Sternenjagd"
data = project.new_project("Sternenjagd", "weltraum")
assert not project.validate(data), project.validate(data)
level_id = next(s["id"] for s in data["flow"] if s["type"] == "level")
folder.mkdir()
project.save(folder, data)
game = builder.build(folder, data, work / "build")
assert (game / "space.gd").exists()

run([GODOT, *godot.import_args(game)], check=False)
out = run([GODOT, "--headless", "--path", str(game), "--fixed-fps", "60", "--quit-after", "9000", "--",
           f"--level={level_id}", "--autotest"], timeout=400, check=False)
lines = [l for l in out.splitlines() if "AUTOTEST" in l]
print("Autotest:", lines)
sounds_line = next((l for l in lines if "Klänge gespielt" in l), "")
for key in ("laser", "explosion", "rolle", "looping", "boost", "bremse", "treffer", "reparatur"):
    if key not in sounds_line:
        raise SystemExit(f"Klang „{key}“ wurde nicht gespielt: {sounds_line}")
if not any("Klänge bereit 13/13" in l for l in lines):
    raise SystemExit("Eingebaute Klänge nicht vollständig")
need = {"Treffer": "eigene Schüsse treffen", "Gegner zerstört": "Gegner lassen sich abschießen",
        "Schaden genommen": "Gegner schießen zurück / Schaden", "Repariert": "Reparatur an der Basis",
        "Gelandet auf": "Landung auf einem Planeten", "Manöver Looping": "Looping",
        "Manöver Fassrolle": "Fassrolle", "Landeanflug": "Landeanflug-Animation",
        "Gestartet von": "Start-Animation zurück ins All"}
missing = [why for key, why in need.items() if not any(key in l for l in lines)]
if missing:
    raise SystemExit("Autotest unvollständig: " + ", ".join(missing))

xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"]
for name, extra in (("start", ["--nach=1.5"]), ("rolle", ["--autotest", "--nach=1.3"]),
                    ("kampf", ["--autotest", "--nach=4"]), ("treffer", ["--autotest", "--nach=9"]),
                    ("pause", ["--autotest", "--pausebild", "--nach=2"]),
                    ("atmosphaere", ["--autotest", "--foto=anflug:0.6", "--nach=900"]),
                    ("landeanflug", ["--autotest", "--foto=anflug:3.0", "--nach=900"]),
                    ("abstieg", ["--autotest", "--foto=abstieg:3.6", "--nach=900"]),
                    ("gelandet", ["--autotest", "--foto=gelandet:0.8", "--nach=900"]),
                    ("abflug", ["--autotest", "--foto=start:2.2", "--nach=900"]),
                    ("austritt", ["--autotest", "--foto=austritt:0.5", "--nach=900"])):
    run([*xvfb, GODOT, "--rendering-driver", "opengl3", "--path", str(game), "--resolution", "1280x720", "--",
         f"--level={level_id}", *extra, f"--screenshot={OUT / ('weltraum-' + name + '.png')}", "--fenster"],
        timeout=240, check=False)
# ---- Alle Grafiken ausgetauscht: eigene GLB-Modelle und Bilder ---------------------------------
own = work / "Eigene Grafiken"
data2 = project.new_project("Eigene Grafiken", "weltraum")
a = own / "assets"
a.mkdir(parents=True)
skeleton.demo_glb(a / "schiff.glb")           # eigenes Modell mit Normalen (sichtbar beleuchtet)
cube_glb(a / "geschoss.glb", (1, 1, 0.2, 1))
cube_glb(a / "fels.glb", (0.5, 0.4, 0.35, 1))
cube_glb(a / "planet.glb", (0.7, 0.3, 0.9, 1))
png(a / "fadenkreuz.png", 64, 64, lambda x, y: ring(x, y, 64, (120, 255, 160, 255)))
png(a / "symbol.png", 48, 48, lambda x, y: ring(x, y, 48, (255, 255, 255, 255)))
png(a / "explosion.png", 64, 64, lambda x, y: (255, 200, 60, max(0, 255 - int(8 * (((x - 32) ** 2 + (y - 32) ** 2) ** .5)))))
png(a / "venus.png", 128, 64, lambda x, y: (40 + x, 80 + y * 2, 160, 255) if (x // 16 + y // 16) % 2 else (230, 120, 60, 255))
wav(a / "musik.wav", 2.0, 220)
wav(a / "piu.wav", 0.2, 880)
data2["settings"]["music"].update({"menu": "assets/musik.wav", "level": "assets/musik.wav"})
data2["ship"]["sounds"] = {"laser": "assets/piu.wav"}
png(a / "boden.png", 32, 32, lambda x, y: (90, 140, 70, 255) if (x // 8 + y // 8) % 2 else (70, 110, 55, 255))
ship = data2["ship"]
ship.update({"model": "assets/schiff.glb", "crosshair": "assets/fadenkreuz.png", "hudIcon": "assets/symbol.png",
             "lifeIcon": "assets/symbol.png", "explosion": "assets/explosion.png"})
for w in ship["weapons"]:
    w.update({"model": "assets/geschoss.glb", "icon": "assets/symbol.png"})
lvl2 = next(iter(data2["levels"].values()))
lvl2["horizon"]["texture"] = "assets/venus.png"
for e in lvl2["entities"]:
    if e["kind"] == "planet" and e["name"] == "Venus":
        e.update({"texture": "assets/venus.png", "groundTexture": "assets/boden.png"})
    elif e["kind"] == "planet":
        e["model"] = "assets/planet.glb"
    elif e["kind"] == "asteroids":
        e["model"] = "assets/fels.glb"
    elif e["kind"] == "enemy":
        e["model"] = "assets/schiff.glb"
ship["proportion"] = {"x": 1.6, "y": 0.7, "z": 1.3}         # breiter, flacher, länger
for e in lvl2["entities"]:
    if e["kind"] == "enemy" and e["type"] == "kreuzer":
        e.update({"scale": 2.0, "proportion": {"x": 0.6, "y": 1.0, "z": 1.5}})
lvl2["entities"].append({"kind": "asteroid", "x": 60, "y": 0, "z": 120, "size": 20, "model": "assets/fels.glb"})
project.save(own, data2)
used = project.assets_used(data2)
assert len([u for u in used if u.startswith("assets/")]) == 11, sorted(used)
game2 = builder.build(own, data2, work / "build2")
assert all((game2 / u).exists() for u in used), "Grafik fehlt im Spiel"
level2 = next(s["id"] for s in data2["flow"] if s["type"] == "level")
run([GODOT, *godot.import_args(game2)], check=False)
out2 = run([GODOT, "--headless", "--path", str(game2), "--fixed-fps", "60", "--quit-after", "9000", "--",
            f"--level={level2}", "--autotest"], timeout=400, check=False)
lines2 = [l for l in out2.splitlines() if "AUTOTEST" in l]
print("Autotest (eigene Grafiken):", lines2)
if not any("Musik assets/musik.wav" in l for l in lines2):
    raise SystemExit("Eigene Musik lief nicht")
if not any("Gelandet auf" in l for l in lines2) or not any("Gegner zerstört" in l for l in lines2):
    raise SystemExit("Autotest mit eigenen Grafiken unvollständig")
bad = [l for l in out2.splitlines() if "nicht lesbar" in l or "fehlt:" in l]
if bad:
    raise SystemExit("Grafik nicht geladen:\n" + "\n".join(bad))
for name, extra in (("eigene-grafiken", ["--autotest", "--nach=9"]), ("eigene-grafiken-start", ["--nach=1.5"])):
    run([*xvfb, GODOT, "--rendering-driver", "opengl3", "--path", str(game2), "--resolution", "1280x720", "--",
         f"--level={level2}", *extra, f"--screenshot={OUT / ('weltraum-' + name + '.png')}", "--fenster"],
        timeout=120, check=False)
print("Fertig.", sorted(p.name for p in OUT.iterdir()))
