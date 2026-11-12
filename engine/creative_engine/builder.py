"""Aus einem Creative-Engine-Projekt ein Godot-Projekt bauen (Spiel-Laufzeit + Daten + Assets).

Die Laufzeit (runtime/*.gd) liest game.json und lädt Bilder/GLB selbst – Godot muss nichts importieren.
"""

import json
import re
import shutil
from pathlib import Path

from . import project as proj

RUNTIME = Path(__file__).resolve().parent / "runtime"
GODOT_FEATURES = "4.3"

PROJECT_GODOT = """; Von der Creative Engine erzeugt – Änderungen bitte im Editor machen.
config_version=5

[application]

config/name="{name}"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("{features}", "GL Compatibility")
boot_splash/show_image=false
boot_splash/bg_color=Color(0, 0, 0, 1)

[display]

window/size/viewport_width={width}
window/size/viewport_height={height}
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"

[physics]

common/physics_ticks_per_second=120

[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
anti_aliasing/quality/msaa_3d=2
"""

MAIN_TSCN = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://main.gd" id="1"]

[node name="Main" type="Node"]
script = ExtResource("1")
"""

EXPORT_PRESETS = """[preset.0]

name="Linux"
platform="Linux"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="game.json, assets/*"
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false

[preset.0.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=0
binary_format/embed_pck=true
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"

[preset.1]

name="Windows"
platform="Windows Desktop"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="game.json, assets/*"
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false

[preset.1.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=0
binary_format/embed_pck=true
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
codesign/enable=false
application/modify_resources=false
application/product_name="{name}"
application/file_description="{name}"
"""


def godot_string(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build(project_folder, project_data, target):
    """Schreibt das Godot-Projekt nach target (wird neu angelegt, .godot-Cache bleibt erhalten)."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for old in target.iterdir():
        if old.name in (".godot",):
            continue
        if old.is_dir():
            shutil.rmtree(old)
        else:
            old.unlink()
    settings = project_data.get("settings", {})
    name = godot_string(project_data.get("name", "Spiel"))
    (target / "project.godot").write_text(PROJECT_GODOT.format(
        name=name, features=GODOT_FEATURES, width=int(settings.get("width", 1280)),
        height=int(settings.get("height", 720))), encoding="utf-8")
    (target / "main.tscn").write_text(MAIN_TSCN, encoding="utf-8")
    (target / "export_presets.cfg").write_text(EXPORT_PRESETS.format(name=name), encoding="utf-8")
    for script in RUNTIME.glob("*.gd"):
        shutil.copy2(script, target / script.name)
    game = json.loads(json.dumps(project_data))
    game.pop("characters", None)          # Editor-Daten (Skelett, Regler) braucht das Spiel nicht
    (target / "game.json").write_text(json.dumps(game, ensure_ascii=False), encoding="utf-8")
    used = proj.assets_used(project_data)
    if used:
        (target / "assets").mkdir(exist_ok=True)
    for rel in sorted(used):
        src = Path(project_folder) / rel
        if src.is_file() and rel.startswith("assets/"):
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            # Godot soll GLB/PNG nicht importieren – die Laufzeit lädt sie selbst
            if dst.suffix.lower() in (".glb", ".gltf", ".png", ".jpg", ".jpeg", ".webp", ".ogv"):
                (dst.parent / (dst.name + ".import")).write_text('[remap]\n\nimporter="keep"\n', encoding="utf-8")
    (target / ".gdignore_note").write_text("Erzeugt von der Creative Engine.\n", encoding="utf-8")
    return target


def file_name(name):
    s = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß_-]+", "-", name).strip("-") or "Spiel"
    return s
