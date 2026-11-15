"""Weltraum-Shooter der Creative Engine mit echtem Godot prüfen (für „Creative Engine prüfen“).

    python3 tools/weltraum-test.py GODOT ausgabe/

Baut das Beispiel-Weltraumprojekt, lässt den Autopiloten kämpfen, reparieren und landen,
macht Bildschirmfotos (Kampf, Schaden, Basis, Planet, gelandet) und exportiert für Linux.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "engine"))
from creative_engine import builder, godot, project  # noqa: E402

GODOT = sys.argv[1]
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)


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
out = run([GODOT, "--headless", "--path", str(game), "--fixed-fps", "60", "--quit-after", "6000", "--",
           f"--level={level_id}", "--autotest"], timeout=400, check=False)
lines = [l for l in out.splitlines() if "AUTOTEST" in l]
print("Autotest:", lines)
need = {"Treffer": "eigene Schüsse treffen", "Gegner zerstört": "Gegner lassen sich abschießen",
        "Schaden genommen": "Gegner schießen zurück / Schaden", "Repariert": "Reparatur an der Basis",
        "Gelandet auf": "Landung auf einem Planeten", "Manöver Looping": "Looping",
        "Manöver Fassrolle": "Fassrolle"}
missing = [why for key, why in need.items() if not any(key in l for l in lines)]
if missing:
    raise SystemExit("Autotest unvollständig: " + ", ".join(missing))

xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"]
for name, extra in (("start", ["--nach=1.5"]), ("rolle", ["--autotest", "--nach=1.3"]),
                    ("kampf", ["--autotest", "--nach=4"]), ("treffer", ["--autotest", "--nach=9"])):
    run([*xvfb, GODOT, "--rendering-driver", "opengl3", "--path", str(game), "--resolution", "1280x720", "--",
         f"--level={level_id}", *extra, f"--screenshot={OUT / ('weltraum-' + name + '.png')}", "--fenster"],
        timeout=120, check=False)
print("Fertig.", sorted(p.name for p in OUT.iterdir()))
