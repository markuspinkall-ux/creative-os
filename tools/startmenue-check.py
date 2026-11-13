"""Jede App, die das Abbild ins Startmenü legt, muss in creative-apps-sync freigeschaltet sein –
sonst blendet das aufgeräumte Startmenü sie aus. Läuft beim Bauen."""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
containerfile = (root / "image" / "Containerfile").read_text(encoding="utf-8")
installed = sorted(set(re.findall(r"COPY \S+\.desktop /usr/share/applications/(\S+\.desktop)", containerfile)))
sync = (root / "theme" / "apps" / "creative-apps-sync").read_text(encoding="utf-8")
visible = set(re.findall(r'"([^"]+\.desktop)":', sync))
missing = []
for name in installed:
    src = next((p for p in root.rglob(name) if ".git" not in p.parts), None)
    hidden = src and re.search(r"^NoDisplay\s*=\s*true", src.read_text(encoding="utf-8"), re.M | re.I)
    if name not in visible and not hidden:
        missing.append(name)
if missing:
    sys.exit("Fehlt im Startmenü (theme/apps/creative-apps-sync, VISIBLE): " + ", ".join(missing))
print(f"Startmenü: alle {len(installed)} eigenen Apps sichtbar")
