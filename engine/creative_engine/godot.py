"""Godot 4 als unsichtbarer Motor: Herunterladen, Testspielen, Exportieren."""

import os
import shutil
import stat
import zipfile
from pathlib import Path

VERSION = "4.3"
TAG = f"{VERSION}-stable"
BASE = f"https://github.com/godotengine/godot/releases/download/{TAG}"
EDITOR_ZIP = f"Godot_v{TAG}_linux.x86_64.zip"
EDITOR_BIN = f"Godot_v{TAG}_linux.x86_64"
TEMPLATES = f"Godot_v{TAG}_export_templates.tpz"
EDITOR_URL = f"{BASE}/{EDITOR_ZIP}"
TEMPLATES_URL = f"{BASE}/{TEMPLATES}"
TEMPLATES_SIZE_MB = 1200


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "creative-engine"


def binary():
    """Pfad zu Godot oder None. Reihenfolge: eigener Download, CREATIVE_ENGINE_GODOT, godot4/godot im PATH."""
    own = data_dir() / "godot" / EDITOR_BIN
    if own.is_file():
        return own
    env = os.environ.get("CREATIVE_ENGINE_GODOT")
    if env and Path(env).is_file():
        return Path(env)
    for name in ("godot4", "godot"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def templates_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "godot" / "export_templates" / f"{VERSION}.stable"


def templates_ready():
    d = templates_dir()
    return (d / "linux_release.x86_64").is_file() and (d / "windows_release_x86_64.exe").is_file()


def install_editor(zip_path):
    target = data_dir() / "godot"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        member = next((m for m in z.namelist() if m.endswith(EDITOR_BIN)), None)
        if member is None:
            raise OSError("Im Download fehlt das Godot-Programm.")
        out = target / EDITOR_BIN
        with z.open(member) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
    out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return out


def install_templates(tpz_path):
    target = templates_dir()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(tpz_path) as z:
        for member in z.namelist():
            if not member.startswith("templates/") or member.endswith("/"):
                continue
            name = member.split("/", 1)[1]
            # Nur Linux und Windows (spart Platz: kein Android/iOS/Web/macOS)
            if not (name.startswith("linux_") or name.startswith("windows_") or name == "version.txt"):
                continue
            out = target / name
            with z.open(member) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if name.startswith("linux_"):
                out.chmod(out.stat().st_mode | stat.S_IXUSR)
    return target


def run_args(project_dir, start=None):
    args = ["--path", str(project_dir)]
    if start:
        args += ["--", f"--level={start}", "--fenster"]
    return args


def export_args(project_dir, preset, out_file):
    return ["--headless", "--path", str(project_dir), "--export-release", preset, str(out_file)]


def import_args(project_dir):
    return ["--headless", "--path", str(project_dir), "--import"]
