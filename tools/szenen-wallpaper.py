"""Bewegte Hintergründe für Gibeon OS 3 – im Stil von „Emerald Earth“ (je Graphit und Porzellan).

  python3 tools/szenen-wallpaper.py --creative     → in Gibeon OS einsetzen
  python3 tools/szenen-wallpaper.py <ordner>       → Vorschaubilder (bild-<szene>-<design>.svg)

Szenen:
  umlaufbahn  ein Raumschiff zieht seine Runden um die Erde (fliegt auch hinter ihr vorbei)
  nordlicht   Nachtseite der Erde mit wehendem Polarlicht, ein Satellit zieht vorbei
  mondbasis   Erdaufgang über dem Mond: Mondbasis mit blinkenden Lichtern, die Rakete startbereit

Jede Szene ist ein Ordner mit Ebenen (SVG) und ebenen.json. Die Shell (Wallpaper.qml) bewegt die
Ebenen nach ihrer Art: fade (überblenden), bob (schweben), sway (wehen), orbit (Umlaufbahn),
line (gerade Bahn), blink (blinken), occluder (Planet vor dem Raumschiff, wenn es dahinter ist).
"""
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("earth", ROOT / "tools" / "earth-wallpaper.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
W, H = E.W, E.H
PAL = E.PAL


def wrap(body, note, w=W, h=H):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <!-- Gibeon OS 3 – {note} -->\n  {body}\n</svg>\n')


def erde(cx, cy, r, p, seed, cloud_seed=None, night=None, haze=True):
    """Erdscheibe wie bei „Emerald Earth“; cloud_seed: andere Wolken (für die Überblend-Ebene)."""
    cs = seed + 1 if cloud_seed is None else cloud_seed
    shade = ""
    if night:
        nx, ny, nr = night
        shade = (f'<radialGradient id="nacht{seed}{cs}" gradientUnits="userSpaceOnUse" cx="{nx}" cy="{ny}" r="{nr}">'
                 f'<stop offset="0" stop-color="{p["night"]}" stop-opacity="0.92"/>'
                 f'<stop offset="0.55" stop-color="{p["night"]}" stop-opacity="0.7"/>'
                 f'<stop offset="1" stop-color="{p["night"]}" stop-opacity="0"/></radialGradient>'
                 f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#nacht{seed}{cs})"/>'
                 + E.city_lights(cx, cy, r, seed + 2, night))
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r * 1.28:.0f}" fill="url(#haze)"/>'] if haze else []
    out.append(f'''<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#erde)"/>
  <g clip-path="url(#disc)">
    {E.continents(cx, cy, r, seed)}
    {E.cloud_bands(cx, cy, r, cs)}
    {shade}
  </g>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{p["glow"]}" stroke-opacity="0.6" stroke-width="8"/>
  <circle cx="{cx}" cy="{cy}" r="{r + 12}" fill="none" stroke="{p["glow"]}" stroke-opacity="0.2" stroke-width="18"/>''')
    return "\n  ".join(out)


def defs(p, design, extra=""):
    return f"<defs>{E.defs_common(p, design)}{extra}</defs>"


# ---- Raumschiff und Satellit (eigene kleine Bilder, zeigen nach rechts) -------------------------
SHIP_W, SHIP_H = 300, 140


def raumschiff(p, flame=1.0):
    light = p is PAL["porzellan"]
    edge = ' stroke="#1c2433" stroke-opacity="0.35" stroke-width="1.6"' if light else ""
    return wrap(f'''<path d="M42 60 L{42 - 40 * flame:.0f} 70 L42 80 Z" fill="{p["flame"]}" fill-opacity="0.9"/>
  <path d="M42 64 L{42 - 22 * flame:.0f} 70 L42 76 Z" fill="#fff4dc" fill-opacity="0.85"/>
  <rect x="38" y="54" width="16" height="32" rx="4" fill="{p["rocket_fin"]}"/>
  <path d="M76 50 L100 20 H126 L114 50 Z" fill="{p["rocket_fin"]}"/>
  <path d="M76 90 L100 120 H126 L114 90 Z" fill="{p["rocket_fin"]}"/>
  <path d="M52 50 H212 C250 50 278 60 292 70 C278 80 250 90 212 90 H52 Z" fill="{p["rocket_body"]}"{edge}/>
  <rect x="62" y="67" width="150" height="6" rx="3" fill="{p["rocket_fin"]}" fill-opacity="0.85"/>
  <path d="M226 58 C246 59 262 64 272 70 L226 70 Z" fill="{p["rocket_window"]}"/>
  <circle cx="150" cy="60" r="4" fill="{p["rocket_window"]}"/><circle cx="170" cy="60" r="4" fill="{p["rocket_window"]}"/>
  <circle cx="190" cy="60" r="4" fill="{p["rocket_window"]}"/>''', "Raumschiff", SHIP_W, SHIP_H)


SAT_W, SAT_H = 220, 90


def satellit(p):
    panel = "#3d6fe0" if p is PAL["porzellan"] else "#5b7fd6"
    grid = "".join(f'<path d="M{x} 30 V60" stroke="{p["rocket_window"]}" stroke-opacity="0.5" stroke-width="2"/>'
                   for x in (24, 44, 64, 156, 176, 196))
    return wrap(f'''<rect x="6" y="30" width="78" height="30" rx="3" fill="{panel}"/>
  <rect x="136" y="30" width="78" height="30" rx="3" fill="{panel}"/>
  {grid}
  <rect x="84" y="43" width="52" height="4" fill="{p["rocket_fin"]}"/>
  <rect x="92" y="24" width="36" height="42" rx="6" fill="{p["rocket_body"]}"/>
  <circle cx="110" cy="45" r="7" fill="{p["rocket_window"]}"/>
  <path d="M110 24 V8" stroke="{p["rocket_body"]}" stroke-width="3"/><circle cx="110" cy="7" r="4" fill="{p["flame"]}"/>''',
                "Satellit", SAT_W, SAT_H)


# ---- Szene 1: Umlaufbahn -------------------------------------------------------------------------
U = {"cx": 2380, "cy": 1180, "r": 640, "rx": 1120, "ry": 330, "tilt": -12, "seed": 31,
     "night": (2380 + 640 * 0.7, 1180 + 640 * 0.55, 640 * 1.05)}


def _orbit_pos(theta):
    a = math.radians(U["tilt"])
    x0, y0 = U["rx"] * math.cos(theta), U["ry"] * math.sin(theta)
    return U["cx"] + x0 * math.cos(a) - y0 * math.sin(a), U["cy"] + x0 * math.sin(a) + y0 * math.cos(a)


def umlaufbahn(design):
    p = PAL[design]
    cx, cy, r = U["cx"], U["cy"], U["r"]
    clip = f'<clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>'
    orbit = (f'<ellipse cx="{cx}" cy="{cy}" rx="{U["rx"]}" ry="{U["ry"]}" transform="rotate({U["tilt"]} {cx} {cy})" '
             f'fill="none" stroke="{p["orbit"]}" stroke-opacity="{p["orbit_op"] * 1.6:.3f}" stroke-width="3" stroke-dasharray="10 26"/>')
    grund = f'''{defs(p, design, clip)}
  <rect width="{W}" height="{H}" fill="url(#base)"/>
  <circle cx="420" cy="2260" r="1100" fill="{p["blob1"]}"/>
  <circle cx="-260" cy="-240" r="1700" fill="url(#sun)"/>
  <circle cx="820" cy="420" r="84" fill="{p["moon"]}"/>
  <circle cx="842" cy="440" r="84" fill="{p["moon_shade"]}" fill-opacity="{p["moon_shade_op"]}"/>
  {orbit}
  {erde(cx, cy, r, p, U["seed"], night=U["night"])}'''
    wolken = f'''{defs(p, design, clip)}
  {erde(cx, cy, r, p, U["seed"], cloud_seed=U["seed"] + 9, night=U["night"], haze=False)}'''
    vorne = f'''{defs(p, design, clip)}
  {erde(cx, cy, r, p, U["seed"], night=U["night"], haze=False)}'''
    star_avoid = (cx, cy, r * 1.3)
    speed = 1
    meta = {
        "size": [W, H], "duration": 70000, "starColor": p["star"],
        "stars": E.star_list(61, 110, star_avoid),
        "layers": [
            {"file": "grund.svg", "kind": "static"},
            {"file": "wolken.svg", "kind": "fade", "speed": 1, "ph": 0},
            {"file": "schiff.svg", "kind": "orbit", "w": SHIP_W, "h": SHIP_H, "scale": 1.0,
             "cx": cx, "cy": cy, "rx": U["rx"], "ry": U["ry"], "tilt": U["tilt"], "speed": speed, "ph": 0.08},
            {"file": "vorne.svg", "kind": "occluder", "speed": speed, "ph": 0.08},
        ],
    }
    sx, sy = _orbit_pos(2 * math.pi * 0.08)
    still = f'''{grund}
  <g transform="translate({sx - SHIP_W / 2:.0f} {sy - SHIP_H / 2:.0f}) rotate(-8 {SHIP_W / 2} {SHIP_H / 2})">{raumschiff(p).split(">", 1)[1].rsplit("</svg>", 1)[0]}</g>
  {E.stars(p, 61, n=110, avoid=star_avoid)}'''
    return {
        "grund.svg": wrap(grund, f"Umlaufbahn, Grund ({design})"),
        "wolken.svg": wrap(wolken, f"Umlaufbahn, Wolken ({design})"),
        "vorne.svg": wrap(vorne, f"Umlaufbahn, Erde vor dem Schiff ({design})"),
        "schiff.svg": raumschiff(p),
        "bild.svg": wrap(still, f"Umlaufbahn ({design})"),
        "ebenen.json": json.dumps(meta, indent=1) + "\n",
    }


# ---- Szene 2: Nordlicht --------------------------------------------------------------------------
N = {"cx": 1920, "cy": 3700, "r": 2400, "seed": 47}


def _aurora(design, seed, color_a, color_b, height, amp):
    """Polarlicht als weiche Bänder, die dem Erdrand folgen (unten hell, nach oben verblassend)."""
    rnd = random.Random(seed)
    cx, cy, r = N["cx"], N["cy"], N["r"]
    out = [f'''<defs><linearGradient id="pl{seed}" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="{color_a}" stop-opacity="0"/>
      <stop offset="0.12" stop-color="{color_a}" stop-opacity="0.55"/>
      <stop offset="0.4" stop-color="{color_a}" stop-opacity="0.26"/>
      <stop offset="0.75" stop-color="{color_b}" stop-opacity="0.1"/>
      <stop offset="1" stop-color="{color_b}" stop-opacity="0"/></linearGradient></defs>''']

    def limb(xx):
        return cy - math.sqrt(max(0.0, r * r - (xx - cx) ** 2))

    for band in range(5):
        x0 = rnd.randint(-200, 1400) + band * 520
        w = rnd.randint(1300, 2000)
        h = height * rnd.uniform(0.7, 1.15)
        lift = rnd.uniform(40, 140)
        ph = rnd.uniform(0, 6.28)
        n = 40
        top, bot = [], []
        for i in range(n + 1):
            xx = x0 + w * i / n
            env = math.sin(math.pi * i / n) ** 0.8          # Band läuft an den Enden aus
            base = limb(xx) - lift
            hh = h * env * (0.75 + 0.25 * math.sin(xx / 210 + ph)) + amp * env * math.sin(xx / 520 + ph * 1.7)
            top.append((xx, base - max(0.0, hh)))
            bot.append((xx, base + 30 * env))
        d = "M" + " L".join(f"{a:.0f} {b:.0f}" for a, b in top) + " L" + " L".join(
            f"{a:.0f} {b:.0f}" for a, b in reversed(bot)) + " Z"
        out.append(f'<path d="{d}" fill="url(#pl{seed})"/>')
    return "\n  ".join(out)


def nordlicht(design):
    p = PAL[design]
    cx, cy, r = N["cx"], N["cy"], N["r"]
    green, cyan, violet = ("#3ee6a0", "#5cd6ff", "#9b7bff") if design == "graphit" else ("#18b47a", "#2b9bd6", "#7a5ae0")
    clip = f'<clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>'
    night = (cx, cy - r, r * 1.15)
    grund = f'''{defs(p, design, clip)}
  <rect width="{W}" height="{H}" fill="url(#base)"/>
  <circle cx="3900" cy="-200" r="1500" fill="url(#sun)"/>
  <circle cx="3120" cy="360" r="70" fill="{p["moon"]}"/>
  <circle cx="3098" cy="378" r="70" fill="{p["moon_shade"]}" fill-opacity="{p["moon_shade_op"]}"/>
  {erde(cx, cy, r, p, N["seed"], night=night)}'''
    licht1 = _aurora(design, 3, green, cyan, 620, 90)
    licht2 = _aurora(design, 8, green, violet, 760, 120)
    avoid = (cx, cy, r * 1.05)
    meta = {
        "size": [W, H], "duration": 40000, "starColor": p["star"], "stars": E.star_list(73, 140, avoid),
        "layers": [
            {"file": "grund.svg", "kind": "static"},
            {"file": "licht1.svg", "kind": "sway", "amp": 60, "speed": 1, "ph": 0, "min": 0.55, "max": 1.0},
            {"file": "licht2.svg", "kind": "sway", "amp": -80, "speed": 1, "ph": 0.5, "min": 0.15, "max": 0.85},
            {"file": "satellit.svg", "kind": "line", "w": SAT_W, "h": SAT_H, "scale": 0.8,
             "x0": -300, "y0": 1300, "x1": 4100, "y1": 300, "angle": -13, "speed": 1, "ph": 0.3},
        ],
    }
    still = f'''{grund}
  <g opacity="0.9">{licht1}</g>
  <g opacity="0.5">{licht2}</g>
  <g transform="translate(1500 760) rotate(-13) scale(0.8)">{satellit(p).split(">", 1)[1].rsplit("</svg>", 1)[0]}</g>
  {E.stars(p, 73, n=140, avoid=avoid)}'''
    return {
        "grund.svg": wrap(grund, f"Nordlicht, Grund ({design})"),
        "licht1.svg": wrap(licht1, f"Nordlicht, Vorhang 1 ({design})"),
        "licht2.svg": wrap(licht2, f"Nordlicht, Vorhang 2 ({design})"),
        "satellit.svg": satellit(p),
        "bild.svg": wrap(still, f"Nordlicht ({design})"),
        "ebenen.json": json.dumps(meta, indent=1) + "\n",
    }


# ---- Szene 3: Mondbasis --------------------------------------------------------------------------
M = {"earth": (2760, 760, 430), "seed": 53, "rocket": (1440, 1590, 0, 7.5)}


def _mond(design):
    rnd = random.Random(9)
    if design == "graphit":
        far, near, crater, rim = "#262b36", "#30364330", "#20252f", "#3a4150"
        near = "#2e3440"
    else:
        far, near, crater, rim = "#c4cbd9", "#b4bccb", "#a7afbf", "#d5dbe6"
    hills = (f'<path d="M0 1560 C 500 1480, 900 1540, 1400 1500 C 1900 1460, 2500 1560, 3000 1520 '
             f'C 3400 1490, 3700 1530, 3840 1510 V2160 H0 Z" fill="{far}"/>')
    ground = (f'<path d="M0 1760 C 600 1680, 1100 1720, 1700 1700 C 2300 1680, 2900 1760, 3840 1700 V2160 H0 Z" fill="{near}"/>')
    craters = []
    for _ in range(26):
        x, y = rnd.randint(80, 3760), rnd.randint(1790, 2120)
        rx = rnd.randint(40, 170)
        ry = rx * rnd.uniform(0.22, 0.32)
        craters.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry:.0f}" fill="{crater}"/>'
                       f'<ellipse cx="{x}" cy="{y - ry * 0.35:.0f}" rx="{rx}" ry="{ry * 0.6:.0f}" fill="none" stroke="{rim}" stroke-opacity="0.5" stroke-width="4"/>')
    return hills + "\n  " + ground + "\n  " + "\n  ".join(craters)


def _basis(p, design, lights_only=False):
    dome = "#dce6ff" if design == "graphit" else "#ffffff"
    dome_op = 0.16 if design == "graphit" else 0.75
    metal = p["rocket_fin"]
    lamp = "#ffcf7a"
    if lights_only:
        return "\n  ".join(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{lamp}"/>'
                           for x, y, rr in ((1960, 1610, 9), (2140, 1585, 9), (2320, 1612, 9), (1330, 1462, 11),
                                            (2650, 1650, 7), (2700, 1650, 7)))
    return f'''<path d="M1880 1700 A 220 150 0 0 1 2400 1700 Z" fill="{dome}" fill-opacity="{dome_op}" stroke="{metal}" stroke-opacity="0.6" stroke-width="5"/>
  <path d="M1960 1700 V1625 M2140 1700 V1585 M2320 1700 V1628" stroke="{metal}" stroke-opacity="0.35" stroke-width="4"/>
  <rect x="2560" y="1640" width="220" height="70" rx="20" fill="{p["rocket_body"]}" fill-opacity="{0.85 if design == "graphit" else 1}"/>
  <rect x="2590" y="1655" width="160" height="10" rx="5" fill="{metal}" fill-opacity="0.8"/>
  <path d="M2400 1690 H2560" stroke="{metal}" stroke-width="10" stroke-linecap="round"/>
  <!-- Startplatz -->
  <rect x="1270" y="1700" width="340" height="24" rx="8" fill="{metal}" fill-opacity="0.8"/>
  <path d="M1330 1470 V1700" stroke="{metal}" stroke-opacity="0.7" stroke-width="12"/>
  <path d="M1330 1520 H1395 M1330 1600 H1395" stroke="{metal}" stroke-opacity="0.7" stroke-width="7"/>
  <!-- Antenne -->
  <path d="M3200 1700 V1480" stroke="{metal}" stroke-width="8"/>
  <path d="M3130 1470 A 80 50 0 0 0 3270 1470 Z" fill="{p["rocket_body"]}" fill-opacity="0.9"/>'''


def mondbasis(design):
    p = PAL[design]
    ex, ey, er = M["earth"]
    clip = f'<clipPath id="disc"><circle cx="{ex}" cy="{ey}" r="{er}"/></clipPath>'
    night = (ex + er * 0.55, ey + er * 0.35, er * 1.15)
    grund = f'''{defs(p, design, clip)}
  <rect width="{W}" height="{H}" fill="url(#base)"/>
  <circle cx="-200" cy="-200" r="1500" fill="url(#sun)"/>
  {erde(ex, ey, er, p, M["seed"], night=night)}
  {_mond(design)}
  {_basis(p, design)}'''
    wolken = f'''{defs(p, design, clip)}
  {erde(ex, ey, er, p, M["seed"], cloud_seed=M["seed"] + 7, night=night, haze=False)}'''
    rx, ry, ang, sc = M["rocket"]
    keep = E.T
    E.T = 0.0
    rakete = E.rocket(rx, ry, ang, sc, p)
    E.T = keep
    lichter = _basis(p, design, lights_only=True)
    avoid = (ex, ey, er * 1.3)
    meta = {
        "size": [W, H], "duration": 30000, "starColor": p["star"],
        "stars": [s for s in E.star_list(91, 150, avoid) if s["y"] < 1450],
        "layers": [
            {"file": "grund.svg", "kind": "static"},
            {"file": "wolken.svg", "kind": "fade", "speed": 1, "ph": 0},
            {"file": "rakete.svg", "kind": "bob", "angle": 0, "amp": 22, "speed": 2, "ph": 0},
            {"file": "lichter.svg", "kind": "blink", "speed": 4, "ph": 0},
        ],
    }
    still = f'''{grund}
  {rakete}
  {lichter}
  {E.stars(p, 91, n=150, avoid=avoid).replace("<circle", "<circle")}'''
    return {
        "grund.svg": wrap(grund, f"Mondbasis, Grund ({design})"),
        "wolken.svg": wrap(wolken, f"Mondbasis, Wolken ({design})"),
        "rakete.svg": wrap(rakete, f"Mondbasis, Rakete ({design})"),
        "lichter.svg": wrap(lichter, f"Mondbasis, Lichter ({design})"),
        "bild.svg": wrap(still, f"Mondbasis ({design})"),
        "ebenen.json": json.dumps(meta, indent=1) + "\n",
    }


SZENEN = {"umlaufbahn": umlaufbahn, "nordlicht": nordlicht, "mondbasis": mondbasis}

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--creative":
    qml = ROOT / "shell/creative_shell/qml/Creative"
    for design, base in (("graphit", qml / "wallpapers"), ("porzellan", qml / "wallpapers-light")):
        for name, fn in SZENEN.items():
            folder = base / "szenen" / name
            folder.mkdir(parents=True, exist_ok=True)
            for fname, text in fn(design).items():
                (folder / fname).write_text(text, encoding="utf-8")
            print("geschrieben:", folder.relative_to(ROOT))
    sys.exit(0)

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in SZENEN.items():
        for design in PAL:
            files = fn(design)
            (out / f"bild-{name}-{design}.svg").write_text(files["bild.svg"], encoding="utf-8")
            print(out / f"bild-{name}-{design}.svg")
