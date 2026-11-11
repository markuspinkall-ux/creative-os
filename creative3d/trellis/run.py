"""Creative 3D – Rechenteil im TRELLIS-Container: Bild → texturierte 3D-Figur.

Meldet sich zeilenweise (wie bisher), damit Creative 3D mitlesen kann:
  P <prozent> <text>      Fortschritt
  OK <json>               fertig: {"files": {"glb": "name.glb", …}, "input": "eingabe.png", …}
                          (Dateinamen relativ zum Ausgabeordner)
  ERR <text>              Fehler

  run.py --prepare                          Modelle laden (einmalig, ≈ 4 GB nach /cache)
  run.py --image /in/bild.png --out /out [--quality normal|hoch] [--seed 1]
  run.py --selftest                         Prüfung beim Bauen (ohne Grafikkarte)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

MODEL = "microsoft/TRELLIS-image-large"     # MIT-Lizenz
STL_HEIGHT_MM = 100.0
QUALITY = {
    # Abtastschritte (Form, Details), Texturgröße, Anteil entfernter Dreiecke
    "normal": {"ss_steps": 12, "slat_steps": 12, "texture": 1024, "simplify": 0.95},
    "hoch": {"ss_steps": 25, "slat_steps": 25, "texture": 2048, "simplify": 0.90},
}


def say(kind, *parts):
    print(kind, *parts, flush=True)


def progress(pct, text):
    say("P", int(pct), text)


def safe_name(stem):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:60] or "figur"


# ── Fortschritt aus den TRELLIS-Abtastern ─────────────────────────────────

def hook_sampler_progress(ranges):
    """TRELLIS zeigt die Abtastschritte mit tqdm an – daraus werden P-Zeilen.
    ranges: Liste von (von %, bis %, Text) für die 1., 2., … Abtastung."""
    import trellis.pipelines.samplers.flow_euler as fe
    original = fe.tqdm
    state = {"run": 0}

    class Reporter:
        def __init__(self, iterable=None, *args, total=None, **kwargs):
            self.items = list(iterable) if iterable is not None else []
            self.total = total or len(self.items)
            index = min(state["run"], len(ranges) - 1)
            self.low, self.high, self.text = ranges[index]
            state["run"] += 1

        def __iter__(self):
            last = -1
            for i, item in enumerate(self.items):
                pct = self.low + (self.high - self.low) * i / max(1, self.total)
                if int(pct) != last:
                    last = int(pct)
                    progress(pct, f"{self.text} ({i + 1}/{self.total})")
                yield item

    fe.tqdm = Reporter
    return original


# ── Hilfen für die Ausgabe ────────────────────────────────────────────────

def vertex_colors(mesh):
    """Farbe je Eckpunkt aus der Textur (für Vorschau ohne Grafikkarte, PLY und Skelett)."""
    import numpy as np
    visual = mesh.visual
    try:
        uv = np.asarray(visual.uv, np.float32)
        image = visual.material.baseColorTexture
        if image is None:
            image = visual.material.image
        tex = np.asarray(image.convert("RGBA"))
    except AttributeError:
        return np.full((len(mesh.vertices), 4), 200, np.uint8)
    h, w = tex.shape[:2]
    x = np.clip((uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(np.int64)
    y = np.clip((1 - uv[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(np.int64)
    return tex[y, x].astype(np.uint8)


def for_printing(mesh):
    """STL: Z nach oben, auf dem Boden stehend, 10 cm hoch (Einheit mm)."""
    import numpy as np
    import trimesh
    m = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=mesh.faces.copy(), process=False)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    height = m.bounds[1][2] - m.bounds[0][2]
    if height > 0:
        m.apply_scale(STL_HEIGHT_MM / height)
    m.apply_translation([-m.centroid[0], -m.centroid[1], -m.bounds[0][2]])
    return m


def export_all(mesh, out, name):
    import numpy as np
    import trimesh
    files = {}
    glb = out / f"{name}.glb"
    mesh.export(str(glb))
    files["glb"] = glb.name
    obj_dir = out / "obj"
    obj_dir.mkdir(exist_ok=True)
    mesh.export(str(obj_dir / f"{name}.obj"))          # mit .mtl und Textur-PNG daneben
    files["obj"] = f"obj/{name}.obj"
    colors = vertex_colors(mesh)
    ply = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces, vertex_colors=colors, process=False)
    ply.export(str(out / f"{name}.ply"))
    files["ply"] = f"{name}.ply"
    for_printing(mesh).export(str(out / f"{name}.stl"))
    files["stl"] = f"{name}.stl"
    np.savez_compressed(out / "netz.npz", vertices=np.asarray(mesh.vertices, np.float32),
                        faces=np.asarray(mesh.faces, np.uint32),
                        normals=np.asarray(mesh.vertex_normals, np.float32), colors=colors)
    files["npz"] = "netz.npz"
    return files


# ── Abläufe ───────────────────────────────────────────────────────────────

def load_pipeline():
    from trellis.pipelines import TrellisImageTo3DPipeline
    return TrellisImageTo3DPipeline.from_pretrained(MODEL)


def prepare():
    progress(5, "Lade TRELLIS (≈ 3 GB) …")
    pipeline = load_pipeline()                 # lädt auch DINOv2 (torch.hub)
    progress(85, "Lade die Hintergrund-Entfernung …")
    import rembg
    rembg.new_session("u2net")
    del pipeline
    progress(100, "Modelle bereit")
    say("OK", json.dumps({"prepared": True}))
    return 0


def generate(args):
    import numpy as np
    import torch
    from PIL import Image

    if not torch.cuda.is_available():
        say("ERR", "Keine NVIDIA-Grafikkarte im Container. Ist das NVIDIA-Abbild von Creative OS installiert?")
        return 3
    settings = QUALITY.get(args.quality, QUALITY["normal"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = safe_name(Path(args.image).stem)
    started = time.time()

    progress(2, "Lade TRELLIS in die Grafikkarte …")
    pipeline = load_pipeline()
    pipeline.cuda()
    gpu = torch.cuda.get_device_name(0)
    progress(15, f"KI bereit ({gpu})")

    progress(17, "Entferne den Hintergrund und schneide zu …")
    image = Image.open(args.image)
    image.load()
    prepared = pipeline.preprocess_image(image)
    prepared.save(out / "eingabe.png")

    hook_sampler_progress([(20, 45, "Erzeuge die Grundform"), (45, 70, "Erzeuge Details und Farben")])
    with torch.no_grad():
        cond = pipeline.get_cond([prepared])
        torch.manual_seed(args.seed)
        coords = pipeline.sample_sparse_structure(cond, 1, {"steps": settings["ss_steps"]})
        slat = pipeline.sample_slat(cond, coords, {"steps": settings["slat_steps"]})
        progress(72, "Baue Netz und Farbwolke …")
        outputs = pipeline.decode_slat(slat, ["mesh", "gaussian"])
    del cond, coords, slat
    # Modelle aus dem Grafikspeicher, damit das Texturbacken auf 12 GB passt
    for model in pipeline.models.values():
        model.cpu()
    torch.cuda.empty_cache()

    progress(78, "Backe die Textur (das dauert etwas) …")
    from trellis.utils import postprocessing_utils
    glb = postprocessing_utils.to_glb(outputs["gaussian"][0], outputs["mesh"][0], simplify=settings["simplify"],
                                      texture_size=settings["texture"], verbose=False)
    if glb is None or len(glb.faces) == 0:
        say("ERR", "Aus diesem Bild ließ sich keine Figur formen. Versuch ein Bild mit klarem Motiv.")
        return 2
    progress(92, "Speichere GLB, OBJ, STL und PLY …")
    files = export_all(glb, out, name)
    seconds = round(time.time() - started)
    progress(100, f"Fertig in {seconds} s")
    say("OK", json.dumps({"files": files, "input": "eingabe.png", "faces": int(len(glb.faces)),
                          "device": gpu, "seconds": seconds, "model": "TRELLIS"}))
    return 0


def selftest():
    """Beim Bauen: Argumente, Ausgabe-Hilfen und STL-Ausrichtung ohne Grafikkarte prüfen."""
    import tempfile
    import numpy as np
    import trimesh
    from PIL import Image
    box = trimesh.creation.box(extents=(1, 2, 1))
    uv = np.random.default_rng(1).random((len(box.vertices), 2))
    texture = Image.new("RGB", (8, 8), (200, 40, 40))
    box.visual = trimesh.visual.TextureVisuals(uv=uv, material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=texture))
    assert vertex_colors(box)[0, 0] == 200
    printable = for_printing(box)
    assert abs(printable.bounds[1][2] - STL_HEIGHT_MM) < 1e-3 and abs(printable.bounds[0][2]) < 1e-6
    with tempfile.TemporaryDirectory() as tmp:
        files = export_all(box, Path(tmp), "test")
        for rel in files.values():
            assert (Path(tmp) / rel).is_file(), rel
    assert safe_name("Mein Bild!.png".rsplit(".", 1)[0]) == "Mein_Bild_"
    print("TRELLIS-Rechenteil: Selbsttest bestanden")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--image")
    parser.add_argument("--out")
    parser.add_argument("--quality", default="normal", choices=sorted(QUALITY))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.prepare:
        return prepare()
    if not (args.image and args.out):
        parser.error("--image und --out fehlen")
    return generate(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 – Meldung für die Oberfläche
        text = str(error).splitlines()[0] if str(error) else type(error).__name__
        if "out of memory" in text.lower():
            text = ("Zu wenig Grafikspeicher. Schließ andere Programme mit Grafikkarten-Nutzung "
                    "(Spiele, Browser-Tabs mit 3D) und stell die Qualität auf „Normal“.")
        say("ERR", text[:300])
        sys.exit(1)
