"""Creative 3D – Rechenteil: Bild → 3D-Figur mit TripoSR.

Läuft in der KI-Umgebung (~/.local/share/creative-3d/venv), nicht im System-Python.
Meldet sich zeilenweise auf stdout, damit die Oberfläche mitlesen kann:
  P <prozent> <text>      Fortschritt
  OK <json>               fertig: {"files": {"glb": …, …}, "input": …, "faces": …}
  ERR <text>              Fehler

Aufruf:
  python creative3d_worker.py --image foto.jpg --out ORDNER [--resolution 256]
                              [--keep-background] [--foreground 0.85]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

DATA = Path(os.environ.get("CREATIVE3D_HOME") or Path.home() / ".local/share/creative-3d")
STL_HEIGHT_MM = 100.0                 # STL für den 3D-Druck: Figur 10 cm hoch


def say(kind, *parts):
    print(kind, *parts, flush=True)


def progress(pct, text):
    say("P", int(pct), text)


def orient_y_up(mesh):
    """TripoSR-Koordinaten → Y nach oben, Blick nach vorn (wie die TripoSR-Demo)."""
    import numpy as np
    import trimesh
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    return mesh


def for_printing(mesh):
    """Kopie für STL: Z nach oben, auf dem Boden stehend, 10 cm hoch (Einheit mm)."""
    import numpy as np
    import trimesh
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    height = m.bounds[1][2] - m.bounds[0][2]
    if height > 0:
        m.apply_scale(STL_HEIGHT_MM / height)
    m.apply_translation([-m.centroid[0], -m.centroid[1], -m.bounds[0][2]])
    return m


def export_all(mesh, out, name):
    files = {}
    for fmt in ("glb", "obj", "ply"):
        path = out / f"{name}.{fmt}"
        mesh.export(str(path))
        files[fmt] = str(path)
    path = out / f"{name}.stl"
    for_printing(mesh).export(str(path))
    files["stl"] = str(path)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--foreground", type=float, default=0.85)
    parser.add_argument("--keep-background", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(args.image).stem)[:60] or "figur"

    progress(2, "Lade die KI …")
    sys.path.insert(0, str(DATA / "TripoSR"))
    os.environ.setdefault("HF_HOME", str(DATA / "hf"))
    os.environ.setdefault("U2NET_HOME", str(DATA / "u2net"))
    import numpy as np
    import torch
    import trimesh
    from PIL import Image
    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    started = time.time()
    model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(8192)
    model.to(device)
    progress(25, "KI bereit" + (" (Grafikkarte)" if device != "cpu" else " (Prozessor – das dauert länger)"))

    progress(30, "Bereite das Bild vor …")
    image = Image.open(args.image)
    image.load()
    if args.keep_background:
        image = image.convert("RGB")
    else:
        import rembg
        progress(32, "Entferne den Hintergrund …")
        session = rembg.new_session()
        image = remove_background(image.convert("RGBA"), session)
        image = resize_foreground(image, max(0.5, min(0.95, args.foreground)))
        arr = np.array(image).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        image = Image.fromarray((arr * 255.0).astype(np.uint8))
    prepared = out / "eingabe.png"
    image.save(prepared)

    progress(45, "Erzeuge die 3D-Form …")
    with torch.no_grad():
        scene_codes = model([image], device=device)
    progress(70, "Baue das Netz und färbe es ein …")
    mesh = model.extract_mesh(scene_codes, True, resolution=args.resolution)[0]
    if len(mesh.faces) == 0:
        say("ERR", "Aus diesem Bild ließ sich keine Figur formen. Versuch ein Foto mit klarem Motiv.")
        return 2
    mesh = orient_y_up(mesh)
    trimesh.repair.fix_normals(mesh)
    progress(88, "Speichere GLB, OBJ, STL und PLY …")
    files = export_all(mesh, out, name)
    # Rohdaten für das Skelett (Creative 3D rechnet die Gelenke im System-Python)
    colors = np.asarray(mesh.visual.vertex_colors, dtype=np.uint8) if mesh.visual.kind == "vertex" else None
    np.savez_compressed(out / "netz.npz", vertices=np.asarray(mesh.vertices, np.float32),
                        faces=np.asarray(mesh.faces, np.uint32), normals=np.asarray(mesh.vertex_normals, np.float32),
                        colors=colors if colors is not None else np.zeros((0, 4), np.uint8))
    files["npz"] = str(out / "netz.npz")
    seconds = round(time.time() - started)
    progress(100, f"Fertig in {seconds} s")
    say("OK", json.dumps({"files": files, "input": str(prepared), "faces": int(len(mesh.faces)),
                          "device": device, "seconds": seconds}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 – Meldung für die Oberfläche
        text = str(error).splitlines()[0] if str(error) else type(error).__name__
        if "out of memory" in text.lower():
            text = "Zu wenig Grafikspeicher. Stell die Detailstufe auf „Normal“ und schließ andere Programme."
        say("ERR", text[:300])
        sys.exit(1)
