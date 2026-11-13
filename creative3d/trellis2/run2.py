"""Creative 3D – Rechenteil im TRELLIS.2-Container: Bild → texturierte 3D-Figur (4 Mrd. Parameter).

Gleiche Zeilen-Sprache wie run.py (P/OK/ERR), damit Creative 3D mitlesen kann.

  run2.py --prepare                          Modelle laden (einmalig, ≈ 13 GB nach /cache), braucht HF_TOKEN
  run2.py --image /out/bild.png --out /out [--quality normal|hoch|sehr-hoch] [--seed 1]
  run2.py --selftest                         Prüfung beim Bauen (ohne Grafikkarte)

Speicher: TRELLIS.2 ist für 24 GB gebaut. Hier läuft es im „low_vram“-Modus – jedes
Teilmodell kommt nur für seinen Schritt auf die Grafikkarte, der Rest wartet im
Arbeitsspeicher. Reicht es bei „Hoch“ trotzdem nicht, rechnet run2.py automatisch
mit der kleineren Auflösung (512³) weiter.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as base  # noqa: E402  – Ausgabe, Export, Foto-Projektion aus dem TRELLIS-Rechenteil

say, progress, safe_name = base.say, base.progress, base.safe_name

MODEL = "microsoft/TRELLIS.2-4B"           # MIT-Lizenz
MODEL_DIR = Path(os.environ.get("TRELLIS2_DIR", "/cache/trellis2"))
DINOV3 = "facebook/dinov3-vitl16-pretrain-lvd1689m"   # freischaltpflichtig (Meta)
BIREFNET = "ZhengPeng7/BiRefNet"                     # MIT – statt des nicht-kommerziellen RMBG-2.0
SS_DECODER = "microsoft/TRELLIS-image-large"
QUALITY = {
    # Auflösung der Form (512³ oder 1024³ in Stufen), Texturgröße, Ziel-Eckpunkte
    "normal": {"pipeline": "512", "texture": 2048, "vertices": 300_000},
    "hoch": {"pipeline": "1024_cascade", "texture": 2048, "vertices": 600_000},
    "sehr-hoch": {"pipeline": "1024_cascade", "texture": 4096, "vertices": 1_000_000},
}
GATED_HINT = ("DINOV3_GESPERRT Meta hat den Zugang zu DINOv3 für deinen Hugging-Face-Schlüssel noch nicht "
              "freigeschaltet. Bitte auf huggingface.co/" + DINOV3 + " den Zugang beantragen und nach der "
              "Freischaltung erneut einrichten.")


# ── Einrichten ────────────────────────────────────────────────────────────

def prepare():
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError, HfHubHTTPError
    token = os.environ.get("HF_TOKEN") or None
    try:
        progress(3, "Prüfe den Zugang zu DINOv3 (Meta) …")
        snapshot_download(DINOV3, token=token)
    except (GatedRepoError, RepositoryNotFoundError):
        say("ERR", GATED_HINT)
        return 4
    except HfHubHTTPError as error:
        if getattr(error.response, "status_code", 0) in (401, 403):
            say("ERR", GATED_HINT if token else "Bitte zuerst deinen Hugging-Face-Schlüssel eintragen.")
            return 4
        raise
    progress(10, "Lade TRELLIS.2 (≈ 13 GB, das dauert) …")
    snapshot_download(MODEL, local_dir=str(MODEL_DIR),
                      allow_patterns=["pipeline.json", "ckpts/ss_flow_*", "ckpts/*_dec_*",
                                      "ckpts/slat_flow_*_512_*", "ckpts/slat_flow_*_1024_*"])
    progress(80, "Lade den Form-Entschlüssler …")
    for ext in (".json", ".safetensors"):
        hf_hub_download(SS_DECODER, f"ckpts/ss_dec_conv3d_16l8_fp16{ext}")
    progress(88, "Lade die Hintergrund-Entfernung (BiRefNet) …")
    snapshot_download(BIREFNET)
    # Nicht-kommerzielles RMBG-2.0 durch BiRefNet (MIT) ersetzen
    cfg_path = MODEL_DIR / "pipeline.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["args"]["rembg_model"]["args"]["model_name"] = BIREFNET
    cfg_path.write_text(json.dumps(cfg, indent=2))
    progress(94, "Prüfe, ob alles zusammenpasst …")
    load_pipeline()
    progress(100, "Modelle bereit")
    say("OK", json.dumps({"prepared": True, "model": "TRELLIS.2"}))
    return 0


def load_pipeline():
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(MODEL_DIR))
    pipeline.low_vram = True            # jedes Teilmodell nur für seinen Schritt auf die Grafikkarte
    return pipeline


# ── Freistellen (wie TRELLIS.2, aber mit Maske für die Foto-Projektion) ───

def freistellen(pipeline, image):
    import numpy as np
    from PIL import Image
    has_alpha = image.mode == "RGBA" and not np.all(np.asarray(image)[:, :, 3] == 255)
    scale = min(1, 1024 / max(image.size))
    if scale < 1:
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    if has_alpha:
        output = image.convert("RGBA")
    else:
        pipeline.rembg_model.to("cuda")
        output = pipeline.rembg_model(image.convert("RGB"))
        pipeline.rembg_model.cpu()
    alpha = np.asarray(output)[:, :, 3]
    pts = np.argwhere(alpha > 0.8 * 255)
    if len(pts) == 0:
        raise ValueError("Im Bild wurde kein Motiv gefunden.")
    x0, y0, x1, y1 = pts[:, 1].min(), pts[:, 0].min(), pts[:, 1].max(), pts[:, 0].max()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    size = int(max(x1 - x0, y1 - y0))
    rgba = output.crop((cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)).convert("RGBA")
    arr = np.asarray(rgba).astype(np.float32) / 255
    rgb = Image.fromarray(((arr[:, :, :3] * arr[:, :, 3:4]) * 255).astype(np.uint8))
    # Für die Projektion auf 518 Pixel (wie bei TRELLIS) – genug für die Vorderseite
    return rgba.resize((518, 518), Image.Resampling.LANCZOS), rgb


def hook_stages(pipeline):
    """Fortschritt je Schritt (TRELLIS.2 meldet selbst nichts Brauchbares)."""
    stages = [("sample_sparse_structure", 22, "Erzeuge die Grundform"),
              ("sample_shape_slat", 38, "Erzeuge die feine Form"),
              ("sample_shape_slat_cascade", 38, "Erzeuge die feine Form (hohe Auflösung)"),
              ("sample_tex_slat", 58, "Erzeuge Farben und Material"),
              ("decode_latent", 70, "Baue das Netz")]
    for name, pct, text in stages:
        fn = getattr(pipeline, name, None)
        if fn is None:
            continue

        def wrapped(*a, _fn=fn, _pct=pct, _text=text, **kw):
            progress(_pct, _text + " …")
            return _fn(*a, **kw)
        setattr(pipeline, name, wrapped)


# ── Figur erzeugen ───────────────────────────────────────────────────────

def generate(args):
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
    gpu = torch.cuda.get_device_name(0)

    progress(2, "Lade TRELLIS.2 (die Teilmodelle warten im Arbeitsspeicher) …")
    pipeline = load_pipeline()
    pipeline.to(torch.device("cuda"))       # low_vram: bleibt im Arbeitsspeicher, nur Merker
    hook_stages(pipeline)
    progress(10, f"KI bereit ({gpu}, sparsamer Speichermodus)")

    progress(14, "Entferne den Hintergrund und schneide zu …")
    image = Image.open(args.image)
    image.load()
    photo, prepared = freistellen(pipeline, image)
    photo.save(out / "eingabe.png")

    kind = settings["pipeline"]
    while True:
        try:
            with torch.no_grad():
                mesh = pipeline.run(prepared, seed=args.seed, preprocess_image=False, pipeline_type=kind)[0]
            break
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if kind == "512":
                raise
            kind = "512"
            progress(20, "Zu wenig Grafikspeicher für die hohe Auflösung – rechne mit 512³ weiter …")
    mesh.simplify(16777216)                  # Grenze von nvdiffrast
    torch.cuda.empty_cache()

    progress(76, "Backe Textur und Material (das dauert etwas) …")
    import o_voxel
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs, coords=mesh.coords,
        attr_layout=mesh.layout, voxel_size=mesh.voxel_size, aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=settings["vertices"], texture_size=settings["texture"],
        remesh=True, remesh_band=1, remesh_project=0, verbose=False)
    del mesh
    torch.cuda.empty_cache()
    if glb is None or len(glb.faces) == 0:
        say("ERR", "Aus diesem Bild ließ sich keine Figur formen. Versuch ein Bild mit klarem Motiv.")
        return 2

    progress(88, "Lege das Originalfoto auf die Vorderseite …")
    try:
        info = base.foto_auf_front(glb, photo)
        if not info.get("projiziert"):
            progress(89, "Foto passt nicht genau genug auf die Form – behalte die berechnete Textur")
    except Exception as error:  # noqa: BLE001
        progress(89, f"Foto-Projektion ging nicht ({error})")

    progress(92, "Speichere GLB, OBJ, STL und PLY …")
    files = base.export_all(glb, out, name)
    seconds = round(time.time() - started)
    progress(100, f"Fertig in {seconds} s")
    say("OK", json.dumps({"files": files, "input": "eingabe.png", "faces": int(len(glb.faces)),
                          "device": gpu, "seconds": seconds, "model": "TRELLIS.2",
                          "resolution": kind}))
    return 0


def selftest():
    """Beim Bauen: Argumente, Konfiguration und gemeinsame Ausgabe-Hilfen ohne Grafikkarte prüfen."""
    assert set(QUALITY) == set(base.QUALITY), "Qualitätsstufen müssen zu run.py passen"
    assert base.safe_name("a b") == "a_b"
    base.selftest()
    print("TRELLIS.2-Rechenteil: Selbsttest bestanden")
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
            text = ("Zu wenig Grafikspeicher – auch im Sparmodus. Schließ Spiele und Browser-Tabs mit 3D "
                    "und stell die Qualität auf „Normal“.")
        say("ERR", text[:300])
        sys.exit(1)
