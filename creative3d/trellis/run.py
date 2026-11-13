"""Creative 3D – Rechenteil im TRELLIS-Container: Bild → texturierte 3D-Figur.

Meldet sich zeilenweise (wie bisher), damit Creative 3D mitlesen kann:
  P <prozent> <text>      Fortschritt
  OK <json>               fertig: {"files": {"glb": "name.glb", …}, "input": "eingabe.png", …}
                          (Dateinamen relativ zum Ausgabeordner)
  ERR <text>              Fehler

  run.py --prepare                          Modelle laden (einmalig, ≈ 4 GB nach /cache)
  run.py --image /in/bild.png --out /out [--quality normal|hoch|sehr-hoch] [--seed 1]
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
    # 2048 backen (passt sicher in 12 GB), dann per KI (Real-ESRGAN ×4) auf 8192 und sauber auf 4096
    "sehr-hoch": {"ss_steps": 40, "slat_steps": 40, "texture": 2048, "simplify": 0.85, "upscale": 4096},
}
ESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
ESRGAN_SHA256 = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"   # BSD-3-Lizenz


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


# ── KI-Hochskalierung der Textur (Real-ESRGAN x4plus, eigene schlanke Umsetzung) ──

def esrgan_net():
    """RRDBNet wie in Real-ESRGAN/BasicSR (BSD-3) – nur das, was zum Hochrechnen nötig ist."""
    import torch
    from torch import nn
    from torch.nn import functional as F

    class RDB(nn.Module):
        def __init__(self, f=64, g=32):
            super().__init__()
            self.conv1 = nn.Conv2d(f, g, 3, 1, 1)
            self.conv2 = nn.Conv2d(f + g, g, 3, 1, 1)
            self.conv3 = nn.Conv2d(f + 2 * g, g, 3, 1, 1)
            self.conv4 = nn.Conv2d(f + 3 * g, g, 3, 1, 1)
            self.conv5 = nn.Conv2d(f + 4 * g, f, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            return self.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, f=64, g=32):
            super().__init__()
            self.rdb1, self.rdb2, self.rdb3 = RDB(f, g), RDB(f, g), RDB(f, g)

        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, f=64, blocks=23, g=32):
            super().__init__()
            self.conv_first = nn.Conv2d(3, f, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB(f, g) for _ in range(blocks)])
            self.conv_body = nn.Conv2d(f, f, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(f, f, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(f, f, 3, 1, 1)
            self.conv_hr = nn.Conv2d(f, f, 3, 1, 1)
            self.conv_last = nn.Conv2d(f, 3, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
            return self.conv_last(self.lrelu(self.conv_hr(feat)))

    return RRDBNet()


def esrgan_weights(cache=Path(os.environ.get("TORCH_HOME", "/cache/torch")) / "esrgan"):
    """Gewichte laden (einmalig ≈ 64 MB von GitHub) und per Prüfsumme sichern."""
    import hashlib
    import urllib.request
    path = cache / "RealESRGAN_x4plus.pth"
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        urllib.request.urlretrieve(ESRGAN_URL, part)
        digest = hashlib.sha256(part.read_bytes()).hexdigest()
        if digest != ESRGAN_SHA256:
            part.unlink(missing_ok=True)
            raise RuntimeError("Real-ESRGAN: Prüfsumme passt nicht")
        part.replace(path)
    return path


def upscale_texture(image, target, tile=384, pad=16):
    """PIL-Bild per Real-ESRGAN ×4 hochrechnen und auf target × target bringen (in Kacheln, fp16 auf der GPU)."""
    import numpy as np
    import torch
    from PIL import Image
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = esrgan_net()
    state = torch.load(esrgan_weights(), map_location="cpu")
    net.load_state_dict(state.get("params_ema", state.get("params", state)), strict=True)
    net.eval().to(device)
    half = device == "cuda"
    if half:
        net.half()
    rgba = image.convert("RGBA")
    rgb = np.asarray(rgba.convert("RGB"), np.float32) / 255.0
    h, w = rgb.shape[:2]
    out = np.zeros((h * 4, w * 4, 3), np.float32)
    x = torch.from_numpy(rgb).permute(2, 0, 1)[None]
    with torch.no_grad():
        for top in range(0, h, tile):
            for left in range(0, w, tile):
                t0, l0 = max(0, top - pad), max(0, left - pad)
                t1, l1 = min(h, top + tile + pad), min(w, left + tile + pad)
                part = x[:, :, t0:t1, l0:l1].to(device)
                part = part.half() if half else part
                res = net(part).float().clamp(0, 1)[0].permute(1, 2, 0).cpu().numpy()
                bt, bl = (top - t0) * 4, (left - l0) * 4
                th, tw = min(tile, h - top) * 4, min(tile, w - left) * 4
                out[top * 4:top * 4 + th, left * 4:left * 4 + tw] = res[bt:bt + th, bl:bl + tw]
    del net
    if device == "cuda":
        torch.cuda.empty_cache()
    big = Image.fromarray((out * 255 + 0.5).astype(np.uint8))
    if big.size != (target, target):
        big = big.resize((target, target), Image.LANCZOS)
    if rgba.getextrema()[3][0] < 255:   # Transparenz übernehmen
        big.putalpha(rgba.getchannel("A").resize(big.size, Image.LANCZOS))
    return big


# ── Freistellen (wie TRELLIS, aber mit Maske für die Foto-Projektion) ─────

def freistellen(pipeline, image):
    """Wie TrellisImageTo3DPipeline.preprocess_image – liefert zusätzlich das RGBA-Bild.

    Rückgabe: (rgba 518×518 mit Maske, rgb vormultipliert für TRELLIS)."""
    import numpy as np
    from PIL import Image
    has_alpha = image.mode == "RGBA" and not np.all(np.asarray(image)[:, :, 3] == 255)
    if has_alpha:
        output = image
    else:
        image = image.convert("RGB")
        scale = min(1, 1024 / max(image.size))
        if scale < 1:
            image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
        import rembg
        if getattr(pipeline, "rembg_session", None) is None:
            pipeline.rembg_session = rembg.new_session("u2net")
        output = rembg.remove(image, session=pipeline.rembg_session)
    alpha = np.asarray(output)[:, :, 3]
    pts = np.argwhere(alpha > 0.8 * 255)
    if len(pts) == 0:
        raise ValueError("Im Bild wurde kein Motiv gefunden.")
    x0, y0, x1, y1 = pts[:, 1].min(), pts[:, 0].min(), pts[:, 1].max(), pts[:, 0].max()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    size = int(max(x1 - x0, y1 - y0) * 1.2)
    rgba = output.crop((cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)) \
        .resize((518, 518), Image.Resampling.LANCZOS).convert("RGBA")
    arr = np.asarray(rgba).astype(np.float32) / 255
    rgb = Image.fromarray(((arr[:, :, :3] * arr[:, :, 3:4]) * 255).astype(np.uint8))
    return rgba, rgb


def foto_auf_front(glb, photo):
    """Originalfoto auf die sichtbare Vorderseite der Textur legen (siehe foto_projektion.py)."""
    from foto_projektion import project_photo
    material = glb.visual.material
    key = "baseColorTexture" if getattr(material, "baseColorTexture", None) is not None else "image"
    texture = getattr(material, key)
    new, info = project_photo(glb.vertices, glb.faces, glb.visual.uv, glb.vertex_normals, texture, photo,
                              log=lambda text: None)
    if info.get("projiziert"):
        setattr(material, key, new)
    return info


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
    photo, prepared = freistellen(pipeline, image)
    photo.save(out / "eingabe.png")

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
    progress(84, "Lege das Originalfoto auf die Vorderseite …")
    try:
        info = foto_auf_front(glb, photo)
        if not info.get("projiziert"):
            progress(85, "Foto passt nicht genau genug auf die Form – behalte die gebackene Textur")
    except Exception as error:  # noqa: BLE001 – lieber ohne Projektion als gar keine Figur
        progress(85, f"Foto-Projektion ging nicht ({error})")
    if settings.get("upscale"):
        progress(86, f"Rechne die Textur per KI auf {settings['upscale']} × {settings['upscale']} hoch …")
        try:
            material = glb.visual.material
            texture = material.baseColorTexture if getattr(material, "baseColorTexture", None) is not None \
                else material.image
            sharp = upscale_texture(texture, settings["upscale"])
            if getattr(material, "baseColorTexture", None) is not None:
                material.baseColorTexture = sharp
            else:
                material.image = sharp
        except Exception as error:  # noqa: BLE001 – lieber normale Textur als gar keine Figur
            progress(88, f"Hochrechnen ging nicht ({error}) – nehme die normale Textur")
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
    # Foto-Projektion: Kugel, rotes Foto von vorne → Vorderseite rot, Rückseite unverändert
    from PIL import ImageDraw
    from foto_projektion import project_photo
    sphere = trimesh.creation.uv_sphere(radius=1.0, count=[32, 32])
    if getattr(sphere.visual, "uv", None) is not None:
        photo = Image.new("RGBA", (518, 518), (0, 0, 0, 0))
        ImageDraw.Draw(photo).ellipse([109, 109, 409, 409], fill=(220, 30, 30, 255))
        tex, info = project_photo(sphere.vertices, sphere.faces, sphere.visual.uv, sphere.vertex_normals,
                                  Image.new("RGB", (128, 128), (128, 128, 128)), photo, log=lambda t: None)
        assert info["projiziert"], info
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
