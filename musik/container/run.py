"""Rechenteil des KI-Musikgenerators (läuft im Container).

  run.py --prepare musik                   ACE-Step einmalig laden (Apache 2.0, ≈ 8 GB)
  run.py --prepare atmo                    Stable Audio Open laden (HF_TOKEN nötig, ≈ 5 GB)
  run.py --musik --prompt … --seconds 120 --count 2 --out /out
  run.py --atmo  --prompt … --seconds 8   --count 5 --out /out [--prefix ereignis]

Alle Dateien werden als 16-Bit-WAV gespeichert (Musik 48 kHz, Geräusche 44,1 kHz).
Ausgabe für die App, eine Zeile je Meldung:
  P <prozent> <text> · AUDIO <datei> <seed> · OK <json> · ERR <text>
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

CACHE = Path(os.environ.get("MUSIK_CACHE", "/cache"))
ACE_DIR = CACHE / "ace-step"
SAO_DIR = CACHE / "stable-audio-open"
ACE_REPO = "ACE-Step/ACE-Step-v1-3.5B"
SAO_REPO = "stabilityai/stable-audio-open-1.0"
SAO_PATTERNS = ["model_index.json", "scheduler/*", "text_encoder/*", "tokenizer/*", "transformer/*", "vae/*",
                "projection_model/*", "LICENSE*", "README.md"]


def say(kind, text=""):
    print(f"{kind} {text}".rstrip(), flush=True)


def as_pcm16(path):
    """Datei als 16-Bit-PCM neu schreiben (die App liest WAV mit der Python-Standardbibliothek)."""
    import soundfile as sf
    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    sf.write(str(path), data.clip(-1, 1), rate, subtype="PCM_16")


def prepare(which):
    from huggingface_hub import snapshot_download

    CACHE.mkdir(parents=True, exist_ok=True)
    if which == "musik":
        if (ACE_DIR / "bereit").is_file():
            say("OK", '{"musik": true}')
            return 0
        say("P", "5 Lade ACE-Step (≈ 8 GB, einmalig) …")
        snapshot_download(ACE_REPO, local_dir=str(ACE_DIR))
        (ACE_DIR / "bereit").write_text(str(int(time.time())))
        say("OK", '{"musik": true}')
        return 0
    if (SAO_DIR / "bereit").is_file():
        say("OK", '{"atmo": true}')
        return 0
    token = os.environ.get("HF_TOKEN") or None
    if not token:
        say("ERR", "ZUGANG_FEHLT Für Geräusche fehlt der Hugging-Face-Schlüssel.")
        return 1
    say("P", "5 Lade Stable Audio Open (≈ 5 GB, einmalig) …")
    try:
        snapshot_download(SAO_REPO, local_dir=str(SAO_DIR), allow_patterns=SAO_PATTERNS, token=token)
    except Exception as error:  # noqa: BLE001
        name = type(error).__name__
        if "Gated" in name or "401" in str(error) or "403" in str(error):
            say("ERR", "ZUGANG_GESPERRT Stable Audio Open ist für dein Hugging-Face-Konto noch nicht freigegeben.")
        else:
            say("ERR", f"Stable Audio Open ließ sich nicht laden ({name}).")
        return 1
    (SAO_DIR / "bereit").write_text(str(int(time.time())))
    say("OK", '{"atmo": true}')
    return 0


def gen_music(args, out):
    if not (ACE_DIR / "bereit").is_file():
        say("ERR", "Die Musik-KI ist noch nicht eingerichtet.")
        return 1
    from acestep.pipeline_ace_step import ACEStepPipeline

    say("P", "3 Lade die Musik-KI auf die Grafikkarte …")
    pipe = ACEStepPipeline(checkpoint_dir=str(ACE_DIR), dtype="bfloat16", torch_compile=False,
                           cpu_offload=True, overlapped_decode=True)
    seed = args.seed if args.seed >= 0 else random.randrange(2 ** 31)
    seconds = max(10, min(240, args.seconds))
    files = []
    for i in range(args.count):
        say("P", f"{10 + int(85 * i / args.count)} Komponiere Stück {i + 1} von {args.count} …")
        target = out / f"{args.prefix}-{i + 1}.wav"
        pipe(format="wav", audio_duration=seconds, prompt=args.prompt, lyrics="[instrumental]", infer_step=60,
             guidance_scale=15.0, scheduler_type="euler", cfg_type="apg", omega_scale=10.0,
             manual_seeds=[seed + i], guidance_interval=0.5, guidance_interval_decay=0.0, min_guidance_scale=3.0,
             use_erg_tag=True, use_erg_lyric=False, use_erg_diffusion=True, oss_steps=[],
             guidance_scale_text=0.0, guidance_scale_lyric=0.0, save_path=str(target))
        for extra in out.glob(f"{target.stem}*.json"):        # ACE-Step legt eine Parameterdatei daneben
            extra.unlink(missing_ok=True)
        as_pcm16(target)
        files.append({"file": target.name, "seed": seed + i})
        say("AUDIO", f"{target.name} {seed + i}")
    return files


def gen_atmo(args, out):
    if not (SAO_DIR / "bereit").is_file():
        say("ERR", "Die Geräusch-KI ist noch nicht eingerichtet.")
        return 1
    import soundfile as sf
    import torch
    from diffusers import StableAudioPipeline

    say("P", "3 Lade die Geräusch-KI auf die Grafikkarte …")
    pipe = StableAudioPipeline.from_pretrained(str(SAO_DIR), torch_dtype=torch.float16).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    rate = pipe.vae.sampling_rate
    seed = args.seed if args.seed >= 0 else random.randrange(2 ** 31)
    seconds = max(1.0, min(47.0, float(args.seconds)))
    files = []
    for i in range(args.count):
        say("P", f"{10 + int(85 * i / args.count)} Erzeuge Klang {i + 1} von {args.count} …")
        generator = torch.Generator("cuda").manual_seed(seed + i)
        audio = pipe(args.prompt, negative_prompt="low quality, distorted, music, speech",
                     num_inference_steps=100, audio_end_in_s=seconds, num_waveforms_per_prompt=1,
                     generator=generator).audios[0]
        data = audio.T.float().cpu().numpy()
        target = out / f"{args.prefix}-{i + 1}.wav"
        sf.write(str(target), data.clip(-1, 1), rate, subtype="PCM_16")
        files.append({"file": target.name, "seed": seed + i})
        say("AUDIO", f"{target.name} {seed + i}")
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", choices=["musik", "atmo"])
    ap.add_argument("--musik", action="store_true")
    ap.add_argument("--atmo", action="store_true")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--out", default="/out")
    ap.add_argument("--prefix", default="klang")
    args = ap.parse_args()
    args.count = max(1, min(8, args.count))
    try:
        if args.prepare:
            return prepare(args.prepare)
        if not args.prompt.strip():
            say("ERR", "Bitte beschreibe, was du hören möchtest.")
            return 1
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        started = time.time()
        import torch
        if not torch.cuda.is_available():
            say("ERR", "Keine NVIDIA-Grafikkarte im Container gefunden.")
            return 1
        try:
            files = gen_music(args, out) if args.musik else gen_atmo(args, out)
        except torch.cuda.OutOfMemoryError:
            say("ERR", "Der Grafikspeicher reicht nicht. Bitte Spiele und andere KI-Programme schließen "
                       "oder eine kürzere Länge wählen.")
            return 1
        if isinstance(files, int):
            return files
        say("P", "100 Fertig")
        say("OK", json.dumps({"files": files, "seconds": int(time.time() - started)}))
        return 0
    except Exception as error:  # noqa: BLE001
        say("ERR", f"{type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
