"""DINOv2 ViT-L/14 mit Registern für TRELLIS bereitstellen – aus der timm-Fassung auf Hugging Face.

TRELLIS lädt DINOv2 per torch.hub von dl.fbaipublicfiles.com (Meta). Ist dieser Server nicht
erreichbar (z. B. abgelaufenes Zertifikat im November 2026), holt dieses Skript dieselben Gewichte
von huggingface.co/timm/vit_large_patch14_reg4_dinov2.lvd142m und schreibt sie im Format von Meta
dorthin, wo torch.hub sie sucht. timm hat beim Umpacken Klassen-Token und erste Positionseinbettung
zusammengelegt; das Rechenergebnis ist dasselbe (im Test gegen das Original geprüft).

Läuft im TRELLIS-Container:  python3 dinov2_from_timm.py [/cache/torch/hub/checkpoints]
"""

import os
import sys

REPO = "timm/vit_large_patch14_reg4_dinov2.lvd142m"
NAME = "dinov2_vitl14_reg4_pretrain.pth"


def convert(timm_sd):
    import torch
    sd = dict(timm_sd)
    reg = sd.pop("reg_token")                 # (1, 4, 1024)
    cls = sd.pop("cls_token")                 # (1, 1, 1024) = cls + pos_embed[:, 0] bei Meta
    pos = sd.pop("pos_embed")                 # (1, 1369, 1024) ohne Klassen-Position
    sd["register_tokens"] = reg
    sd["cls_token"] = cls
    sd["pos_embed"] = torch.cat([torch.zeros_like(pos[:, :1]), pos], dim=1)
    sd["mask_token"] = torch.zeros(1, pos.shape[-1])
    sd.pop("head.weight", None)
    sd.pop("head.bias", None)
    return sd


def main(target):
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file
    out = os.path.join(target, NAME)
    if os.path.exists(out):
        print("DINOv2 ist schon da.")
        return 0
    os.makedirs(target, exist_ok=True)
    print("Lade DINOv2 von Hugging Face …", flush=True)
    sd = convert(load_file(hf_hub_download(REPO, "model.safetensors")))
    torch.save(sd, out + ".part")
    os.replace(out + ".part", out)
    print("DINOv2 bereit:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/cache/torch/hub/checkpoints"))
