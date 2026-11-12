"""Projektdaten der Creative Engine (ohne Oberfläche, testbar).

Ein Projekt ist ein Ordner mit projekt.json und assets/. Der Ablauf (Timeline) besteht aus
Schritten: splash, menu, text, level. Level-Daten liegen getrennt unter levels[id].
"""

import copy
import json
import re
import shutil
import uuid
from pathlib import Path

VERSION = 1
GENRES = {
    "jumpnrun": ("Jump'n'Run (2,5D)", "Seitlich scrollend, 3D-Grafik, feste Seitenkamera – wie Rayman oder Trine.", True),
    "adventure": ("Action-Adventure", "Offene 3D-Welt: Landschaft formen, Wände ziehen, Häuser bauen.", False),
    "rennen-strecke": ("Rennspiel – Strecke", "Rundkurs mit Checkpoints und Rundenzähler.", False),
    "rennen-welt": ("Rennspiel – offene Welt", "Frei fahren, Missionen und Rennen in der Stadt.", False),
}
TILES = [
    ("gras", "Gras", "#5fb04a"), ("erde", "Erde", "#7a5a3a"), ("stein", "Stein", "#8a93a3"),
    ("ziegel", "Ziegel", "#b0603f"), ("holz", "Holz", "#a8794a"), ("eis", "Eis", "#bfe6ff"),
    ("metall", "Metall", "#6c7686"), ("wolke", "Wolke", "#f4f7ff"),
]
ENTITIES = [
    ("start", "Spielerstart", "Hier beginnt die Spielfigur (einmal pro Level)."),
    ("coin", "Münze", "Einsammeln gibt einen Punkt."),
    ("enemy", "Gegner", "Läuft hin und her – von oben draufspringen!"),
    ("spike", "Stacheln", "Kostet ein Leben."),
    ("spring", "Sprungfeder", "Schleudert die Figur hoch."),
    ("checkpoint", "Checkpoint", "Neustartpunkt nach einem Sturz."),
    ("npc", "NPC", "Figur mit Sprechblasen-Dialog, wenn man vorbeikommt."),
    ("goal", "Ziel", "Fahne – hier ist das Level geschafft."),
]
SINGLE = {"start", "goal"}
ACTIONS = [("start", "Spiel starten"), ("quit", "Beenden"), ("next", "Weiter zum nächsten Schritt")]


def new_id(prefix):
    return f"{prefix}{uuid.uuid4().hex[:6]}"


def slug(name):
    s = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß _-]+", "", name).strip() or "Spiel"
    return s


def empty_level(name="Level 1", width=80, height=20):
    tiles = {}
    for x in range(width):
        for y in range(2):
            if 18 <= x <= 20 and y >= 0:
                continue  # eine Lücke zum Drüberspringen
            tiles[f"{x},{y}"] = "gras" if y == 1 else "erde"
    return {"name": name, "width": width, "height": height, "sky": "#8ec5ff", "ground": "#6f9e5c",
            "tiles": tiles, "entities": [{"kind": "start", "x": 2, "y": 2}, {"kind": "goal", "x": width - 4, "y": 2}],
            "decor": []}


def sample_level(name="Level 1"):
    lvl = empty_level(name)
    t = lvl["tiles"]
    for x in range(8, 12):
        t[f"{x},4"] = "holz"
    for x in range(26, 30):
        t[f"{x},5"] = "stein"
    for x in range(34, 37):
        for y in range(2, 4):
            t[f"{x},{y}"] = "ziegel"
    for x in range(44, 49):
        t[f"{x},6"] = "wolke"
    lvl["entities"] += [
        {"kind": "coin", "x": 9, "y": 5}, {"kind": "coin", "x": 10, "y": 5}, {"kind": "coin", "x": 19, "y": 4},
        {"kind": "coin", "x": 27, "y": 6}, {"kind": "coin", "x": 28, "y": 6}, {"kind": "coin", "x": 46, "y": 7},
        {"kind": "enemy", "x": 15, "y": 2, "range": 3, "speed": 2, "model": ""},
        {"kind": "enemy", "x": 40, "y": 2, "range": 2, "speed": 2.5, "model": ""},
        {"kind": "spike", "x": 31, "y": 2}, {"kind": "spring", "x": 42, "y": 2},
        {"kind": "checkpoint", "x": 38, "y": 4},
        {"kind": "npc", "x": 5, "y": 2, "model": "", "name": "Lotte", "mode": "gespraech", "seconds": 3.0,
         "once": True, "dialog": [{"who": "npc", "text": "Hallo! Schön, dass du da bist."},
                                  {"who": "spieler", "text": "Wo geht's lang?"},
                                  {"who": "npc", "text": "Immer nach rechts zur Fahne – pass auf die Stacheln auf!"}]},
    ]
    return lvl


def new_project(name, genre="jumpnrun", sample=True):
    level_id = new_id("l")
    return {
        "version": VERSION,
        "name": name,
        "genre": genre,
        "flow": [
            {"type": "splash", "id": new_id("s"), "name": "Splash", "bg": "#000000", "logo": "", "logoSize": 0.35,
             "text": "präsentiert", "textColor": "#ffffff", "textSize": 26, "duration": 2.0, "fade": 0.6},
            {"type": "menu", "id": new_id("m"), "name": "Startbildschirm", "bg": "#12151b", "bgImage": "",
             "elements": [
                 {"kind": "text", "text": name, "x": 0.5, "y": 0.28, "w": 0.8, "h": 0.2, "size": 72,
                  "color": "#ffffff", "bold": True},
                 {"kind": "button", "text": "Spielen", "action": "start", "x": 0.5, "y": 0.56, "w": 0.24, "h": 0.09,
                  "size": 30, "color": "#8fb3ff", "textColor": "#12151b", "radius": 16},
                 {"kind": "button", "text": "Beenden", "action": "quit", "x": 0.5, "y": 0.69, "w": 0.24, "h": 0.09,
                  "size": 30, "color": "#2a303d", "textColor": "#dce6ff", "radius": 16},
             ]},
            {"type": "level", "id": level_id, "name": "Level 1"},
        ],
        "levels": {level_id: sample_level("Level 1") if sample else empty_level("Level 1")},
        "player": {"model": "", "height": 1.6, "speed": 7.0, "jump": 12.0, "lives": 3},
        "settings": {"width": 1280, "height": 720, "fullscreen": False},
    }


def add_step(project, kind, after=None):
    count = sum(1 for s in project["flow"] if s["type"] == kind) + 1
    if kind == "level":
        sid = new_id("l")
        name = f"Level {count}"
        project["levels"][sid] = empty_level(name)
        step = {"type": "level", "id": sid, "name": name}
    elif kind == "splash":
        step = {"type": "splash", "id": new_id("s"), "name": "Splash", "bg": "#000000", "logo": "", "logoSize": 0.35,
                "text": "", "textColor": "#ffffff", "textSize": 26, "duration": 2.0, "fade": 0.6}
    elif kind == "menu":
        step = {"type": "menu", "id": new_id("m"), "name": "Menü", "bg": "#12151b", "bgImage": "",
                "elements": [{"kind": "button", "text": "Weiter", "action": "next", "x": 0.5, "y": 0.6, "w": 0.24,
                              "h": 0.09, "size": 30, "color": "#8fb3ff", "textColor": "#12151b", "radius": 16}]}
    elif kind == "seite":
        step = {"type": "seite", "id": new_id("p"), "name": "Seite", "bg": "#20263a", "bgImage": "", "duration": 4.0,
                "elements": [
                    {"kind": "bubble", "text": "Was für ein Tag!", "speaker": "", "x": 0.32, "y": 0.3, "w": 0.32,
                     "h": 0.2, "size": 34, "color": "#ffffff", "textColor": "#1c2433", "tail": "unten-links",
                     "after": 0.0},
                    {"kind": "bubble", "text": "Und er fängt gerade erst an …", "speaker": "", "x": 0.66, "y": 0.62,
                     "w": 0.36, "h": 0.2, "size": 34, "color": "#ffe9a8", "textColor": "#1c2433",
                     "tail": "unten-rechts", "after": 1.5}]}
    else:
        step = {"type": "text", "id": new_id("t"), "name": "Zwischentext", "bg": "#12151b",
                "text": "Kapitel 2\nDie Reise geht weiter …", "textColor": "#ffffff", "textSize": 40, "duration": 0}
    index = len(project["flow"]) if after is None else after + 1
    project["flow"].insert(index, step)
    return step


def remove_step(project, index):
    step = project["flow"].pop(index)
    if step["type"] == "level":
        project["levels"].pop(step["id"], None)
    return step


def duplicate_step(project, index):
    step = copy.deepcopy(project["flow"][index])
    old = step["id"]
    step["id"] = new_id(step["id"][0])
    step["name"] = step.get("name", "") + " (Kopie)"
    if step["type"] == "level":
        project["levels"][step["id"]] = copy.deepcopy(project["levels"][old])
        project["levels"][step["id"]]["name"] = step["name"]
    project["flow"].insert(index + 1, step)
    return step


def validate(project):
    """Probleme, die das Spiel kaputt machen würden (Liste von Texten)."""
    problems = []
    levels = [s for s in project["flow"] if s["type"] == "level"]
    if not levels:
        problems.append("Es gibt noch kein Level.")
    for s in levels:
        lvl = project["levels"].get(s["id"])
        if lvl is None:
            problems.append(f"{s['name']}: Leveldaten fehlen.")
            continue
        kinds = [e["kind"] for e in lvl["entities"]]
        if "start" not in kinds:
            problems.append(f"{s['name']}: Spielerstart fehlt.")
        if "goal" not in kinds:
            problems.append(f"{s['name']}: Ziel fehlt.")
    if not any(s["type"] == "menu" for s in project["flow"]):
        pass  # ohne Menü startet das Spiel direkt
    return problems


def assets_used(project):
    used = set()
    for s in project["flow"]:
        for key in ("logo", "bgImage", "bgVideo"):
            if s.get(key):
                used.add(s[key])
        for e in s.get("elements", []):
            for key in ("image", "video"):
                if e.get(key):
                    used.add(e[key])
    for lvl in project["levels"].values():
        for e in lvl["entities"] + lvl.get("decor", []):
            if e.get("model"):
                used.add(e["model"])
    if project["player"].get("model"):
        used.add(project["player"]["model"])
    return used


def import_asset(folder, source):
    """Datei nach assets/ kopieren (eindeutiger Name). Rückgabe: relativer Pfad „assets/…“."""
    folder = Path(folder)
    source = Path(source)
    target_dir = folder / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", source.name)
    target = target_dir / name
    if target.exists() and target.resolve() != source.resolve():
        stem, suffix = target.stem, target.suffix
        n = 2
        while (target_dir / f"{stem}-{n}{suffix}").exists():
            n += 1
        target = target_dir / f"{stem}-{n}{suffix}"
    if target.resolve() != source.resolve():
        shutil.copy2(source, target)
    return f"assets/{target.name}"


def save(folder, project):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "projekt.json.neu"
    tmp.write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(folder / "projekt.json")


def load(folder):
    data = json.loads((Path(folder) / "projekt.json").read_text(encoding="utf-8"))
    if data.get("version", 0) > VERSION:
        raise ValueError("Das Projekt stammt aus einer neueren Creative Engine.")
    data.setdefault("player", {"model": "", "height": 1.6, "speed": 7.0, "jump": 12.0, "lives": 3})
    data.setdefault("settings", {"width": 1280, "height": 720, "fullscreen": False})
    for lvl in data.get("levels", {}).values():
        lvl.setdefault("decor", [])
        lvl.setdefault("entities", [])
        lvl.setdefault("tiles", {})
        for e in lvl["entities"]:
            if e.get("kind") == "npc":
                upgrade_npc(e)
    return data


def upgrade_npc(e):
    """Ältere NPCs hatten nur „text“ – daraus wird ein Dialog mit einer Zeile."""
    if "dialog" not in e:
        text = e.pop("text", "")
        e["dialog"] = [{"who": "npc", "text": text}] if text else []
    e.setdefault("name", "")
    e.setdefault("mode", "gespraech")
    e.setdefault("seconds", 3.0)
    e.setdefault("once", True)
    return e

