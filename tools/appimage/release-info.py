#!/usr/bin/python3
"""Update-Angaben für die AppImages: studio.json und 3d-studio.json neben die AppImages legen.

  python3 tools/appimage/release-info.py <ordner> <version>

Studio liest beim Start studio.json aus dem Release „appimages“: Version, Download-Adresse, Größe
und die Neuerungen – getrennt für Studio und Broadcast (aus den Neuerungen von Gibeon OS)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE = "https://github.com/markuspinkall-ux/creative-os/releases/download/appimages/"
out, version = Path(sys.argv[1]), sys.argv[2]
news = json.loads((ROOT / "settings/creative_settings/neuerungen.json").read_text(encoding="utf-8"))


def lines(*words, exclude=()):
    found = []
    for entry in news[:3]:                       # die letzten Updates
        for key in ("neu", "verbessert", "behoben"):
            for text in entry.get(key, []):
                if any(w in text for w in words) and not any(x in text for x in exclude) and text not in found:
                    found.append(text)
    return found[:8]


for app, name, notes in (
        ("studio", "Gibeon-Studio", {"studio": lines("Studio", exclude=("3D Studio",)),
                                     "broadcast": lines("Broadcast", "Gibeon Kamera")}),
        ("3d-studio", "Gibeon-3D-Studio", {"3d": lines("3D Studio")})):
    image = out / f"{name}-x86_64.AppImage"
    info = {"version": version, "url": BASE + image.name, "size": image.stat().st_size if image.exists() else 0,
            "notizen": notes}
    (out / f"{app}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(app, version, info["size"] // 1_000_000, "MB", {k: len(v) for k, v in notes.items()})
