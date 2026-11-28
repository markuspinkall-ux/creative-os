"""Rechenteil des KI-Bildgenerators (läuft im Container, FLUX.1 [schnell]).

  run.py --prepare                         Modell einmalig laden und verkleinert speichern
  run.py --prompt "…" --count 4 --out /out Bilder erzeugen

Ausgabe für die App, eine Zeile je Meldung:
  P <prozent> <text>      Fortschritt
  IMG <datei> <seed>      ein Bild ist fertig (Datei relativ zu --out)
  OK <json>               fertig
  ERR <text>              Fehler (verständlich formuliert)
"""

import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

CACHE = Path(os.environ.get("BILDGEN_CACHE", "/cache"))
RAW = CACHE / "flux"            # Originaldateien ohne Transformer/T5 (VAE, CLIP, Tokenizer, Scheduler)
SMALL = CACHE / "flux-klein"    # verkleinerter Transformer (4 Bit) und T5 (8 Bit)
READY = CACHE / "bereit.json"
REPOS = [r for r in os.environ.get("BILDGEN_REPO", "").split(",") if r] or [
    "black-forest-labs/FLUX.1-schnell",   # Original (für manche Konten freischaltpflichtig)
    "unsloth/FLUX.1-schnell",             # unveränderte, frei ladbare Kopie – gleiche Apache-2.0-Lizenz
]
PATTERNS = ["model_index.json", "scheduler/*", "text_encoder/*", "text_encoder_2/*", "tokenizer/*",
            "tokenizer_2/*", "transformer/*", "vae/*", "LICENSE*", "README.md"]


def say(kind, text=""):
    print(f"{kind} {text}".rstrip(), flush=True)


def prepare():
    if READY.is_file() and (SMALL / "transformer").is_dir() and (SMALL / "text_encoder_2").is_dir():
        say("OK", READY.read_text().strip())
        return 0
    import torch
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        say("ERR", "Keine NVIDIA-Grafikkarte im Container gefunden.")
        return 1
    CACHE.mkdir(parents=True, exist_ok=True)
    used = None
    for repo in REPOS:
        say("P", f"5 Lade FLUX.1 [schnell] von {repo} (≈ 33 GB, einmalig) …")
        try:
            snapshot_download(repo, local_dir=str(RAW), allow_patterns=PATTERNS,
                              token=os.environ.get("HF_TOKEN") or None)
            used = repo
            break
        except Exception as error:  # noqa: BLE001 – freischaltpflichtig, nicht erreichbar …
            say("P", f"5 {repo} nicht ladbar ({type(error).__name__}) – versuche die nächste Quelle …")
    if used is None:
        say("ERR", "Das Modell ließ sich nicht herunterladen. Bitte Internetverbindung prüfen und erneut versuchen.")
        return 1

    from diffusers import BitsAndBytesConfig as DiffusersBnb
    from diffusers import FluxTransformer2DModel
    from transformers import BitsAndBytesConfig as TransformersBnb
    from transformers import T5EncoderModel

    say("P", "70 Verkleinere den Bildteil auf 4 Bit (damit er auf 12 GB passt) …")
    transformer = FluxTransformer2DModel.from_pretrained(
        str(RAW), subfolder="transformer", torch_dtype=torch.bfloat16,
        quantization_config=DiffusersBnb(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                         bnb_4bit_compute_dtype=torch.bfloat16))
    transformer.save_pretrained(str(SMALL / "transformer"))
    del transformer
    torch.cuda.empty_cache()

    say("P", "85 Verkleinere das Textmodell auf 8 Bit …")
    t5 = T5EncoderModel.from_pretrained(str(RAW), subfolder="text_encoder_2", torch_dtype=torch.bfloat16,
                                        quantization_config=TransformersBnb(load_in_8bit=True))
    t5.save_pretrained(str(SMALL / "text_encoder_2"))
    del t5
    torch.cuda.empty_cache()

    say("P", "95 Räume die großen Originaldateien auf …")
    for big in ("transformer", "text_encoder_2"):
        shutil.rmtree(RAW / big, ignore_errors=True)
    shutil.rmtree(CACHE / "hf", ignore_errors=True)
    info = json.dumps({"repo": used, "modell": "FLUX.1 [schnell]", "lizenz": "Apache-2.0", "zeit": int(time.time())})
    READY.write_text(info + "\n")
    say("OK", info)
    return 0


def load_pipeline():
    import torch
    from diffusers import FluxPipeline, FluxTransformer2DModel
    from transformers import T5EncoderModel

    transformer = FluxTransformer2DModel.from_pretrained(str(SMALL / "transformer"), torch_dtype=torch.bfloat16)
    t5 = T5EncoderModel.from_pretrained(str(SMALL / "text_encoder_2"), torch_dtype=torch.bfloat16)
    pipe = FluxPipeline.from_pretrained(str(RAW), transformer=transformer, text_encoder_2=t5,
                                        torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()       # immer nur ein Teil auf der Grafikkarte
    pipe.set_progress_bar_config(disable=True)
    return pipe


def generate(args):
    if not READY.is_file():
        say("ERR", "Das Modell ist noch nicht eingerichtet.")
        return 1
    import torch

    if not torch.cuda.is_available():
        say("ERR", "Keine NVIDIA-Grafikkarte im Container gefunden.")
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    count = max(1, min(4, args.count))
    width, height = (max(256, min(1440, v)) // 16 * 16 for v in (args.width, args.height))
    seed = args.seed if args.seed >= 0 else random.randrange(2 ** 31)
    started = time.time()
    say("P", "3 Lade das Modell auf die Grafikkarte …")
    try:
        pipe = load_pipeline()
        files = []
        for i in range(count):
            say("P", f"{10 + int(85 * i / count)} Male Bild {i + 1} von {count} …")
            generator = torch.Generator("cpu").manual_seed(seed + i)
            image = pipe(args.prompt, guidance_scale=0.0, num_inference_steps=max(1, min(8, args.steps)),
                         max_sequence_length=256, width=width, height=height, generator=generator).images[0]
            name = f"{args.prefix}-{i + 1}.png"
            image.save(out / name)
            files.append({"file": name, "seed": seed + i})
            say("IMG", f"{name} {seed + i}")
    except torch.cuda.OutOfMemoryError:
        say("ERR", "Der Grafikspeicher reicht nicht. Bitte andere Programme mit Grafikkarte (Spiele, 3D Studio) "
                   "schließen oder ein kleineres Format wählen.")
        return 1
    say("P", "100 Fertig")
    say("OK", json.dumps({"files": files, "seconds": int(time.time() - started), "width": width, "height": height}))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--out", default="/out")
    ap.add_argument("--prefix", default="bild")
    args = ap.parse_args()
    try:
        if args.prepare:
            return prepare()
        if not args.prompt.strip():
            say("ERR", "Bitte beschreibe, was auf dem Bild sein soll.")
            return 1
        return generate(args)
    except Exception as error:  # noqa: BLE001 – lesbare Meldung statt Python-Ablaufverfolgung
        say("ERR", f"{type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
