"""Installierte Programme (.desktop-Dateien) – für „Programm starten“ und App-Symbole."""

import os
from pathlib import Path


def data_dirs():
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    dirs = [home] + (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    for extra in (str(Path.home() / ".local/share/flatpak/exports/share"), "/var/lib/flatpak/exports/share"):
        if extra not in dirs:
            dirs.append(extra)
    return [d for d in dirs if d]


def _parse(path):
    entry, section = {}, ""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("["):
                section = line
                continue
            if section != "[Desktop Entry]" or "=" not in line:
                continue
            k, v = line.split("=", 1)
            entry.setdefault(k.strip(), v.strip())
    except OSError:
        return None
    return entry


def find(desktop_id):
    """Pfad und Inhalt einer .desktop-Datei (erste Fundstelle gewinnt, wie bei XDG)."""
    if not desktop_id:
        return None, {}
    for d in data_dirs():
        p = Path(d) / "applications" / desktop_id
        if p.is_file():
            return p, _parse(p) or {}
    return None, {}


def icon_of(desktop_id):
    _path, entry = find(desktop_id)
    return entry.get("Icon", "") or "application-x-executable"


def name_of(desktop_id):
    _path, entry = find(desktop_id)
    return entry.get("Name[de]") or entry.get("Name") or desktop_id.removesuffix(".desktop")


def installed():
    """Sichtbare Programme, nach Namen sortiert: [{id, name, icon}]"""
    seen, apps = set(), []
    for d in data_dirs():
        folder = Path(d) / "applications"
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.desktop")):
            if p.name in seen:
                continue
            seen.add(p.name)
            e = _parse(p) or {}
            if e.get("Type", "Application") != "Application" or e.get("NoDisplay") == "true" \
                    or e.get("Hidden") == "true" or not e.get("Exec"):
                continue
            apps.append({"id": p.name, "name": e.get("Name[de]") or e.get("Name") or p.stem,
                         "icon": e.get("Icon", "")})
    apps.sort(key=lambda a: a["name"].lower())
    return apps
