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
    "weltraum": ("Weltraum-Shooter (3D)", "Raumschiff aus der Verfolgerkamera: Gegner abschießen, auf Planeten "
                 "landen, an Raumbasen reparieren – wie Star Fox oder Freelancer.", True),
    "adventure": ("Action-Adventure", "Offene 3D-Welt: Landschaft formen, Wände ziehen, Häuser bauen.", False),
    "rennen-strecke": ("Rennspiel – Strecke", "Rundkurs mit Checkpoints und Rundenzähler.", False),
    "rennen-welt": ("Rennspiel – offene Welt", "Frei fahren, Missionen und Rennen in der Stadt.", False),
}
SPACE_ENTITIES = [
    ("start", "Schiffsstart", "Hier startet das eigene Raumschiff (einmal pro Level)."),
    ("enemy", "Gegner", "Feindliches Schiff oder Geschütz – schießt zurück."),
    ("planet", "Planet", "Zum Hinfliegen und Landen (L)."),
    ("base", "Raumbasis", "Langsam hineinfliegen: repariert Hülle und Schild, füllt Raketen auf."),
    ("asteroids", "Asteroiden", "Feld aus Felsbrocken – Zusammenstöße kosten Hülle."),
]
SPACE_SINGLE = {"start"}
ENEMY_TYPES = [("jaeger", "Jäger", "schnell und wendig, Laser"), ("kreuzer", "Kreuzer", "groß und zäh, Plasma"),
               ("geschuetz", "Geschütz", "steht still, dreht sich mit")]
WEAPON_TYPES = [("laser", "Laser"), ("plasma", "Plasma"), ("rakete", "Raketen (zielsuchend)"),
                ("streu", "Streuschuss")]
GOALS = [("gegner", "Alle Gegner zerstören"), ("landen", "Auf einem Planeten landen"),
         ("basis", "Eine Raumbasis erreichen"), ("frei", "Freier Flug (kein Ziel)")]
HORIZON_SIDES = [("unten", "unten"), ("oben", "oben"), ("links", "links"), ("rechts", "rechts"),
                 ("vorne", "vorne"), ("hinten", "hinten")]
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


def space_level(name="Sektor 1", sample=True):
    """Weltraum-Level: Koordinaten in Metern, Karte von -1000 bis 1000 (x/z), y = Höhe."""
    lvl = {"name": name, "kind": "weltraum", "size": 1000, "sky": "#04060c", "nebula": "#3a2d6b", "skyImage": "",
           "stars": 1.0, "sunColor": "#fff3e0", "goal": "gegner", "goalTarget": "",
           "horizon": {"on": True, "side": "unten", "color": "#2f5fb3", "color2": "#3f8f4f",
                       "atmosphere": "#7fc4ff", "distance": 900, "bands": 0.0},
           "entities": [{"kind": "start", "x": 0, "y": 0, "z": 300, "dir": 0}], "tiles": {}, "decor": []}
    if not sample:
        lvl["goal"] = "frei"
    if sample:
        lvl["entities"] += [
            {"kind": "enemy", "type": "jaeger", "x": -60, "y": 10, "z": -40, "dir": 180},
            {"kind": "enemy", "type": "jaeger", "x": 70, "y": -5, "z": -80, "dir": 180},
            {"kind": "enemy", "type": "geschuetz", "x": 0, "y": 30, "z": -260},
            {"kind": "enemy", "type": "kreuzer", "x": 180, "y": 20, "z": -420, "dir": 200},
            {"kind": "base", "name": "Station Aurora", "x": -260, "y": 0, "z": 160, "dir": 0, "repair": 25},
            {"kind": "planet", "name": "Venus", "x": 420, "y": -40, "z": -640, "radius": 160, "color": "#e0b070",
             "color2": "#b0703a", "atmosphere": "#ffd9a0", "ground": "#c8925a", "landable": True, "bands": 0.6},
            {"kind": "planet", "name": "Kryos", "x": -560, "y": 80, "z": -760, "radius": 110, "color": "#bfe6ff",
             "color2": "#6f9ec4", "atmosphere": "#bfe6ff", "ground": "#d8ecf7", "landable": True, "ring": True},
            {"kind": "asteroids", "x": -200, "y": 0, "z": -380, "count": 28, "spread": 120, "size": 9},
        ]
    return lvl


# Eigene Grafiken des Raumschiffs und der Anzeige (Weltraum-Shooter)
SHIP_IMAGES = ("model", "crosshair", "hudIcon", "lifeIcon", "explosion")


def new_ship():
    return {"model": "", "size": 2.2, "color": "#8fb3ff", "speed": 60.0, "boost": 1.8, "turn": 1.6, "hull": 100,
            "shield": 60, "lives": 3, "mouse": 1.0, "invertY": False,
            "weapons": [new_weapon(t) for t in ("laser", "plasma", "rakete", "streu")]}


WEAPON_DEFAULTS = {
    "laser": {"name": "Laser", "damage": 1, "cooldown": 0.14, "speed": 420, "color": "#ff5d6c"},
    "plasma": {"name": "Plasma", "damage": 4, "cooldown": 0.6, "speed": 230, "color": "#7fe0ff"},
    "rakete": {"name": "Raketen", "damage": 6, "cooldown": 1.1, "speed": 170, "color": "#ffb347", "ammo": 12},
    "streu": {"name": "Streuschuss", "damage": 1, "cooldown": 0.5, "speed": 360, "color": "#c49bff"},
}


def new_weapon(kind="laser"):
    return {"type": kind, **copy.deepcopy(WEAPON_DEFAULTS.get(kind, WEAPON_DEFAULTS["laser"]))}


def is_space(project):
    return project.get("genre") == "weltraum"


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
            {"type": "level", "id": level_id, "name": "Sektor 1" if genre == "weltraum" else "Level 1"},
        ],
        "levels": {level_id: (space_level("Sektor 1", sample) if genre == "weltraum"
                              else sample_level("Level 1") if sample else empty_level("Level 1"))},
        "ship": new_ship(),
        "player": {"model": "", "height": 1.6, "speed": 7.0, "jump": 12.0, "lives": 3, "attacks": [new_attack(0)]},
        "settings": {"width": 1280, "height": 720, "fullscreen": False, "ui": dict(UI_DEFAULT)},
    }


ATTACK_KEYS = ["J", "K", "L", "U", "I", "O"]
ATTACK_NAMES = ["Schlag", "Tritt", "Hieb", "Wirbel"]
UI_DEFAULT = {"lives": "herzen", "heart": "", "heartEmpty": "", "coin": "", "panel": "", "panelMargin": 16,
              "barFill": "", "barBack": "", "barMargin": 6, "bubble": "", "bubbleMargin": 24, "bubbleText": "#1c2433"}
UI_IMAGES = ("heart", "heartEmpty", "coin", "panel", "barFill", "barBack", "bubble")


def new_attack(i):
    return {"name": ATTACK_NAMES[i] if i < len(ATTACK_NAMES) else f"Angriff {i + 1}", "key": ATTACK_KEYS[i % 6],
            "range": 1.5, "damage": 1, "cooldown": 0.4}


def add_step(project, kind, after=None):
    count = sum(1 for s in project["flow"] if s["type"] == kind) + 1
    if kind == "level":
        sid = new_id("l")
        if is_space(project):
            name = f"Sektor {count}"
            project["levels"][sid] = space_level(name, sample=False)
        else:
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
        if lvl.get("kind") == "weltraum":
            if "start" not in kinds:
                problems.append(f"{s['name']}: Schiffsstart fehlt.")
            goal = lvl.get("goal", "gegner")
            if goal == "gegner" and "enemy" not in kinds:
                problems.append(f"{s['name']}: Ziel „Alle Gegner zerstören“, aber es gibt keine Gegner.")
            if goal == "landen" and not any(e["kind"] == "planet" and e.get("landable", True)
                                            for e in lvl["entities"]):
                problems.append(f"{s['name']}: Ziel „Landen“, aber kein Planet zum Landen.")
            if goal == "basis" and "base" not in kinds:
                problems.append(f"{s['name']}: Ziel „Raumbasis“, aber keine Basis.")
            continue
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
    ship = project.get("ship", {})
    for key in SHIP_IMAGES:
        if ship.get(key):
            used.add(ship[key])
    for w in ship.get("weapons", []):
        for key in ("model", "icon"):
            if w.get(key):
                used.add(w[key])
    for lvl in project["levels"].values():
        if lvl.get("skyImage"):
            used.add(lvl["skyImage"])
        if lvl.get("horizon", {}).get("texture"):
            used.add(lvl["horizon"]["texture"])
        for e in lvl["entities"]:
            for key in ("texture", "groundTexture"):
                if e.get(key):
                    used.add(e[key])
    ui = project.get("settings", {}).get("ui", {})
    for key in UI_IMAGES:
        if ui.get(key):
            used.add(ui[key])
    for s in project["flow"]:
        for e in s.get("elements", []):
            if e.get("skin"):
                used.add(e["skin"])
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
    data["player"].setdefault("attacks", [])
    if data.get("genre") == "weltraum":
        ship = data.setdefault("ship", new_ship())
        for key, value in new_ship().items():
            ship.setdefault(key, value)
    ui = data["settings"].setdefault("ui", {})
    for key, value in UI_DEFAULT.items():
        ui.setdefault(key, value)
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



# ---- Steuerung --------------------------------------------------------------------------------
# Je Aktion: Tasten (bis 2), Maustasten (bis 2), Controller (bis 2). Namen wie in Godot
# (OS.find_keycode_from_string); Controller und Maus mit eigenen Namen, die die Laufzeit übersetzt.
MAX_BINDINGS = 2
PAD_INPUTS = [
    ("A", "A / Kreuz"), ("B", "B / Kreis"), ("X", "X / Quadrat"), ("Y", "Y / Dreieck"),
    ("LB", "LB / L1"), ("RB", "RB / R1"), ("LT", "LT / L2 (Trigger)"), ("RT", "RT / R2 (Trigger)"),
    ("Start", "Start / Options"), ("Back", "Back / Share"), ("LS", "Linker Stick drücken"),
    ("RS", "Rechter Stick drücken"), ("Hoch", "Steuerkreuz hoch"), ("Runter", "Steuerkreuz runter"),
    ("Links", "Steuerkreuz links"), ("Rechts", "Steuerkreuz rechts"),
    ("LS-Links", "Linker Stick links"), ("LS-Rechts", "Linker Stick rechts"), ("LS-Hoch", "Linker Stick hoch"),
    ("LS-Runter", "Linker Stick runter"), ("RS-Links", "Rechter Stick links"), ("RS-Rechts", "Rechter Stick rechts"),
    ("RS-Hoch", "Rechter Stick hoch"), ("RS-Runter", "Rechter Stick runter"),
]
MOUSE_INPUTS = [("Links", "Linke Maustaste"), ("Rechts", "Rechte Maustaste"), ("Mitte", "Mittlere Maustaste"),
                ("RadHoch", "Mausrad hoch"), ("RadRunter", "Mausrad runter"), ("Seite1", "Seitentaste 1"),
                ("Seite2", "Seitentaste 2")]
# (Aktion, Anzeige, Tasten, Maus, Controller)
CONTROLS = {
    "jumpnrun": [
        ("links", "Nach links", ["A", "Left"], [], ["Links", "LS-Links"]),
        ("rechts", "Nach rechts", ["D", "Right"], [], ["Rechts", "LS-Rechts"]),
        ("springen", "Springen", ["Space", "W"], [], ["A"]),
        ("pause", "Pause", ["Escape", "P"], [], ["Start"]),
        ("weiter", "Weiter (Dialoge, Menüs)", ["Enter", "Space"], ["Links"], ["A"]),
    ],
    "weltraum": [
        ("schub", "Schneller", ["W"], [], ["RT"]),
        ("bremse", "Bremsen", ["S"], [], ["LT"]),
        ("boost", "Boost", ["Shift"], [], ["LB", "LS"]),
        ("gieren_links", "Nach links lenken", ["A", "Left"], [], ["LS-Links"]),
        ("gieren_rechts", "Nach rechts lenken", ["D", "Right"], [], ["LS-Rechts"]),
        ("nicken_hoch", "Nase hoch", ["Down"], [], ["LS-Runter"]),
        ("nicken_runter", "Nase runter", ["Up"], [], ["LS-Hoch"]),
        ("rollen_links", "Rollen links", ["Q"], [], ["RS-Links"]),
        ("rollen_rechts", "Rollen rechts", ["E"], [], ["RS-Rechts"]),
        ("looping", "Looping", ["R"], [], ["Hoch", "RS"]),
        ("fassrolle_links", "Fassrolle links (Schüsse prallen ab)", ["X"], [], ["Links"]),
        ("fassrolle_rechts", "Fassrolle rechts (Schüsse prallen ab)", ["C"], [], ["Rechts"]),
        ("feuer", "Feuern", ["Space", "Ctrl"], ["Links"], ["RB"]),
        ("waffe_weiter", "Nächste Waffe", ["Tab"], ["Rechts", "RadRunter"], ["X"]),
        ("waffe_zurueck", "Vorige Waffe", [], ["RadHoch"], ["B"]),
        ("landen", "Landen / Starten", ["L"], [], ["Y"]),
        ("pause", "Pause", ["Escape", "P"], [], ["Start"]),
        ("weiter", "Weiter (Menüs)", ["Enter"], [], ["A"]),
    ],
}
ATTACK_PADS = ["X", "Y", "B", "RB", "LB"]
# Qt-Tastennamen → Godot-Namen (wo sie sich unterscheiden)
QT_TO_GODOT_KEYS = {"Esc": "Escape", "Return": "Enter", "Control": "Ctrl", "Meta": "Meta", "PgUp": "PageUp",
                    "PgDown": "PageDown", "Ins": "Insert", "Del": "Delete", "Backspace": "BackSpace"}
KEY_LABELS = {"Space": "Leertaste", "Left": "←", "Right": "→", "Up": "↑", "Down": "↓", "Escape": "Esc",
              "Enter": "Enter", "Shift": "Umschalt", "Ctrl": "Strg", "Alt": "Alt", "Tab": "Tab",
              "BackSpace": "Rücktaste", "Delete": "Entf", "Insert": "Einfg", "PageUp": "Bild ↑",
              "PageDown": "Bild ↓", "Home": "Pos1", "End": "Ende"}


def control_actions(project):
    """Aktionen des Genres samt Angriffen (Jump'n'Run): Liste (Aktion, Anzeige, Standard-Belegung)."""
    genre = "weltraum" if is_space(project) else "jumpnrun"
    rows = [(a, label, {"keys": list(k), "mouse": list(m), "pad": list(p)})
            for a, label, k, m, p in CONTROLS[genre]]
    if genre == "jumpnrun":
        for i, att in enumerate(project.get("player", {}).get("attacks", [])):
            rows.append((f"angriff{i + 1}", f"Angriff {i + 1}: {att.get('name') or 'Angriff'}",
                         {"keys": [att.get("key", ATTACK_KEYS[i % 6])], "mouse": [],
                          "pad": [ATTACK_PADS[i]] if i < len(ATTACK_PADS) else []}))
    return rows


def controls_for(project):
    """Fertige Belegung für das Spiel: eigene Änderungen über den Standardwerten."""
    own = project.get("controls", {})
    result = {}
    for action, _label, default in control_actions(project):
        b = dict(default)
        for kind in ("keys", "mouse", "pad"):
            if kind in own.get(action, {}):
                b[kind] = list(own[action][kind])[:MAX_BINDINGS]
        result[action] = b
    return result


def set_binding(project, action, kind, values):
    project.setdefault("controls", {}).setdefault(action, {})[kind] = list(values)[:MAX_BINDINGS]


def reset_controls(project):
    project.pop("controls", None)


def control_conflicts(project):
    """Gleiche Taste/Knopf für zwei Aktionen (außer bekannten Paaren wie Springen/Weiter)."""
    allowed = {frozenset(("springen", "weiter")), frozenset(("feuer", "weiter")), frozenset(("pause", "weiter"))}
    labels = {a: label for a, label, _d in control_actions(project)}
    seen = {}
    problems = []
    for action, b in controls_for(project).items():
        for kind in ("keys", "mouse", "pad"):
            for v in b[kind]:
                other = seen.get((kind, v))
                if other and frozenset((other, action)) not in allowed:
                    problems.append(f"„{binding_label(kind, v)}“ ist doppelt belegt: {labels[other]} und {labels[action]}")
                seen.setdefault((kind, v), action)
    return problems


def binding_label(kind, value):
    if kind == "keys":
        return KEY_LABELS.get(value, value)
    names = dict(MOUSE_INPUTS if kind == "mouse" else PAD_INPUTS)
    return names.get(value, value)


def qt_key_to_godot(name):
    return QT_TO_GODOT_KEYS.get(name, name)
