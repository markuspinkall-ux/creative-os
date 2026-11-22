"""Hintergrundbilder „Emerald Earth“ (Gibeon OS 3) – drei Motive, je Graphit und Porzellan.

  python3 tools/earth-wallpaper.py <ordner>      → erde-<motiv>-<design>.svg
  python3 tools/earth-wallpaper.py --creative    → in Gibeon OS einsetzen (Schreibtisch, Anmeldung, …)

Motive:
  wolken   die Erde groß rechts mit Wolkenwirbeln, die Rakete kommt von der Venus
  horizont dicht über der Erde: ihr Rand füllt die untere Ecke, die Rakete zieht in die Umlaufbahn,
           auf der Nachtseite leuchten Städte, oben steht der Mond (bewegter Hintergrund)
  sichel   die Erde als Sichel im Gegenlicht – ruhig und schlicht

Gleicher Aufbau wie bei „Vivid Venus“ (Ebenen grund/wolken/rakete + Sterne für die Bewegung).
"""
import json
import math
import random
import sys
from pathlib import Path

W, H = 3840, 2160
T = 0.0          # Zeitpunkt der Animation (0…1, Schleife) – nur für die bewegte Vorschau

PAL = {
    "graphit": {
        "base0": "#161a24", "base1": "#0d1015", "blob1": "#171c26", "blob2": "#191e29",
        "star": "#dce6ff", "orbit": "#dce6ff", "orbit_op": 0.06, "night": "rgb(13,16,21)",
        "rocket_body": "#dce6ff", "rocket_fin": "#8fb3ff", "rocket_window": "#12151b", "flame": "#ffb07a",
        "glow": "#7fd3ff", "glow_op": 0.22, "sun_op": 0.5, "mercury": "#e2b46e", "moon": "#c9ccd3", "moon_shade": "rgb(13,16,21)", "moon_shade_op": 0.45,
    },
    "porzellan": {
        "base0": "#dde5f3", "base1": "#d3dbeb", "blob1": "#d6dff0", "blob2": "#dbe3f4",
        "star": "#7b8aa8", "orbit": "#3d4b66", "orbit_op": 0.08, "night": "rgb(60,52,46)",
        "rocket_body": "#ffffff", "rocket_fin": "#3d6fe0", "rocket_window": "#1c2433", "flame": "#d9773a",
        "glow": "#5cc4f2", "glow_op": 0.30, "sun_op": 0.42, "mercury": "#d9a85e", "moon": "#f4f5f8", "moon_shade": "#c3cad8", "moon_shade_op": 0.75,
    },
}
# Erde: Ozean von hell (Küste) bis tief, Land in Smaragdgrün, Wüsten in Sand, Wolken weiß
OCEAN = ["#4fb6d8", "#1f86b5", "#14608f", "#0c3f63", "#08263d"]
LAND = ["#2f9a63", "#3fae6e", "#57bf7a", "#23784c", "#8fbf6a"]
SAND = "#d2b77e"
CITY = "#ffcf7a"


def rocket(x, y, angle, scale, p):
    # sanftes Schweben in Flugrichtung, flackernde Flamme
    a = math.radians(angle - 90)
    bob = 16 * math.sin(2 * math.pi * T)
    x, y = x + bob * math.cos(a), y + bob * math.sin(a)
    flame = 1 + 0.3 * math.sin(2 * math.pi * T * 6)
    return (f'<g transform="translate({x:.1f} {y:.1f}) rotate({angle}) scale({scale}) translate(-12 -12)">'
            f'<path d="M7.5 12.5L5 15.5v3l2.8-1.6z" fill="{p["rocket_fin"]}"/>'
            f'<path d="M16.5 12.5L19 15.5v3l-2.8-1.6z" fill="{p["rocket_fin"]}"/>'
            f'<path d="M12 2c3 2.5 4.6 6 4.6 10v4.6H7.4V12C7.4 8 9 4.5 12 2z" fill="{p["rocket_body"]}"'
            f'{" stroke=\"#1c2433\" stroke-opacity=\"0.35\" stroke-width=\"0.6\"" if p is PAL["porzellan"] else ""}/>'
            f'<circle cx="12" cy="9.2" r="1.9" fill="{p["rocket_window"]}"/>'
            f'<path d="M10 17.6h4l-2 {4.4 * flame:.2f}z" fill="{p["flame"]}"/></g>')


def star_list(seed, n=80, avoid=None):
    """Sterne als Daten (für die Animation in der Shell): x, y, r, Deckkraft, Tempo, Phase."""
    rnd = random.Random(seed)
    rows = []
    for _ in range(n):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        if avoid and math.hypot(x - avoid[0], y - avoid[1]) < avoid[2] + 30:
            continue
        r = rnd.choice((1.5, 2, 2, 2.5, 3))
        op = rnd.choice((0.2, 0.3, 0.35, 0.45, 0.55))
        speed, phase = rnd.choice((1, 1, 2)), rnd.random()
        rows.append({"x": x, "y": y, "r": r, "o": op, "s": speed, "p": round(phase, 3)})
    return rows


def stars(p, seed, n=80, avoid=None):
    rnd = random.Random(seed)
    out = [f'<g fill="{p["star"]}">']
    for _ in range(n):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        if avoid and math.hypot(x - avoid[0], y - avoid[1]) < avoid[2] + 30:
            continue
        r = rnd.choice((1.5, 2, 2, 2.5, 3))
        op = rnd.choice((0.2, 0.3, 0.35, 0.45, 0.55))
        speed, phase = rnd.choice((1, 1, 2)), rnd.random()
        op *= 0.55 + 0.45 * math.sin(2 * math.pi * (T * speed + phase))
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill-opacity="{op}"/>')
    out.append("</g>")
    return "\n  ".join(out)


def _bezier(p0, p1, p2, p3, n=48):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _interp(pts, x):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * ((x - x0) / (x1 - x0) if x1 != x0 else 0)
    return pts[0][1] if x < pts[0][0] else pts[-1][1]


def _band_in_disc(top, bot, cx, cy, r, steps=90):
    """Fläche zwischen zwei Kurven, schon auf die Planetenscheibe zugeschnitten.
    (Qt zeichnet SVG-clipPath nicht überall – darum wird hier selbst geschnitten.)"""
    runs, run = [], []
    for i in range(steps + 1):
        x = cx - r + 2 * r * i / steps
        half = math.sqrt(max(0.0, r * r - (x - cx) ** 2))
        lo, hi = max(_interp(top, x), cy - half), min(_interp(bot, x), cy + half)
        if hi - lo > 0.5:
            run.append((x, lo, hi))
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    paths = []
    for run in runs:
        if len(run) < 2:
            continue
        up = " L".join(f"{x:.0f} {lo:.0f}" for x, lo, _ in run)
        down = " L".join(f"{x:.0f} {hi:.0f}" for x, _, hi in reversed(run))
        paths.append(f"M{up} L{down} Z")
    return " ".join(paths)


def _inside(x, y, cx, cy, r):
    """Punkt auf die Planetenscheibe ziehen (Qt zeichnet SVG-clipPath nicht überall)."""
    d = math.hypot(x - cx, y - cy)
    if d <= r * 0.995:
        return x, y
    k = r * 0.995 / d
    return cx + (x - cx) * k, cy + (y - cy) * k


def _blob(rnd, x, y, rx, ry, cx, cy, r, n=44, rough=0.22, rot=0.0):
    """Weiche, unregelmäßige Fläche (geglättet über Kurven), auf die Scheibe gezogen."""
    pts = []
    phase = [rnd.uniform(0, 6.3) for _ in range(4)]
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + rough * (0.45 * math.sin(2 * a + phase[0]) + 0.3 * math.sin(3 * a + phase[1])
                         + 0.15 * math.sin(5 * a + phase[2]) + 0.1 * math.sin(8 * a + phase[3]))
        px, py = rx * k * math.cos(a), ry * k * math.sin(a)
        px, py = px * math.cos(rot) - py * math.sin(rot), px * math.sin(rot) + py * math.cos(rot)
        pts.append(_inside(x + px, y + py, cx, cy, r))
    # Mittelpunkte als Stützpunkte → runde Kurven statt Ecken
    mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    d = f"M{mids[-1][0]:.0f} {mids[-1][1]:.0f}"
    for i in range(n):
        d += f" Q{pts[i][0]:.0f} {pts[i][1]:.0f} {mids[i][0]:.0f} {mids[i][1]:.0f}"
    return d + " Z"


def _spot(rnd, cx, cy, r, view):
    """Zufälliger Punkt auf der Scheibe, der im sichtbaren Bildausschnitt liegt."""
    for _ in range(400):
        a, d = rnd.uniform(0, 2 * math.pi), r * math.sqrt(rnd.random()) * 0.97
        x, y = cx + d * math.cos(a), cy + d * math.sin(a)
        if view[0] - 100 <= x <= view[2] + 100 and view[1] - 100 <= y <= view[3] + 100:
            return x, y
    return cx, cy


def continents(cx, cy, r, seed, view=(0, 0, 3840, 2160), size=1.0):
    """Kontinente in Smaragdgrün mit Wäldern, Wüsten und hellem Küstensaum."""
    rnd = random.Random(seed)
    out = []
    for i in range(7):
        x, y = _spot(rnd, cx, cy, r, view)
        sx, sy = rnd.uniform(0.10, 0.22) * r * size, rnd.uniform(0.06, 0.14) * r * size
        rot = rnd.uniform(-0.8, 0.8)
        out.append(f'<path d="{_blob(rnd, x, y, sx * 1.08, sy * 1.12, cx, cy, r, rot=rot)}" fill="{OCEAN[0]}" fill-opacity="0.45"/>')
        out.append(f'<path d="{_blob(rnd, x, y, sx, sy, cx, cy, r, rot=rot)}" fill="{rnd.choice(LAND[:3])}"/>')
        out.append(f'<path d="{_blob(rnd, x - sx * 0.2, y - sy * 0.1, sx * 0.5, sy * 0.45, cx, cy, r, rot=rot)}" fill="{LAND[3]}" fill-opacity="0.6"/>')
        if rnd.random() < 0.5:
            out.append(f'<path d="{_blob(rnd, x + sx * 0.3, y + sy * 0.2, sx * 0.35, sy * 0.3, cx, cy, r, rot=rot)}" fill="{SAND}" fill-opacity="0.6"/>')
    return "\n    ".join(out)


def cloud_bands(cx, cy, r, seed, view=(0, 0, 3840, 2160), tilt=-14):
    """Wolken: lange weiße Schleier und zwei Wirbel – ziehen langsam (Ebene „wolken“ überblendet)."""
    rnd = random.Random(seed)
    drift = r * 0.05 * math.sin(2 * math.pi * T)
    out = []
    for _ in range(15):
        x, y = _spot(rnd, cx, cy, r, view)
        x += drift
        rx, ry = rnd.uniform(0.08, 0.26) * r, rnd.uniform(0.012, 0.035) * r
        rot = math.radians(tilt + rnd.uniform(-12, 12))
        out.append(f'<path d="{_blob(rnd, x, y, rx, ry, cx, cy, r, n=36, rough=0.35, rot=rot)}" fill="#ffffff" '
                   f'fill-opacity="{rnd.uniform(0.3, 0.6):.2f}"/>')
    # zwei Wirbel (Tiefdruckgebiete) als weiche Spiralen
    for _ in range(2):
        x, y = _spot(rnd, cx, cy, r, view)
        x += drift
        size = rnd.uniform(0.05, 0.08) * r
        pts = []
        for i in range(70):
            t = i / 69 * 3.2 * math.pi
            rr = size * (0.12 + 0.88 * t / (3.2 * math.pi))
            pts.append(_inside(x + rr * math.cos(t) * 1.25, y + rr * math.sin(t), cx, cy, r))
        d = "M" + " L".join(f"{px:.0f} {py:.0f}" for px, py in pts)
        out.append(f'<path d="{d}" fill="none" stroke="#ffffff" stroke-opacity="0.5" stroke-width="{max(6, r * 0.014):.0f}" '
                   f'stroke-linecap="round" stroke-linejoin="round"/>')
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{size * 0.35:.0f}" fill="#ffffff" fill-opacity="0.35"/>')
    return "\n    ".join(out)


def city_lights(cx, cy, r, seed, night):
    """Lichter der Städte auf der Nachtseite (night = Mittelpunkt und Größe der Nachtseite)."""
    nx, ny, nr = night
    rnd = random.Random(seed)
    out = [f'<g fill="{CITY}">']
    for _ in range(170):
        a, d = rnd.uniform(0, 2 * math.pi), nr * 0.75 * math.sqrt(rnd.random())
        x, y = nx + d * math.cos(a), ny + d * math.sin(a)
        if math.hypot(x - cx, y - cy) > r * 0.97:
            continue
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.choice((2, 2.5, 3, 3.5, 4.5))}" fill-opacity="{rnd.uniform(0.3, 0.85):.2f}"/>')
    out.append("</g>")
    return "\n    ".join(out)


def defs_common(p, design):
    return f'''<linearGradient id="base" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{p["base0"]}"/><stop offset="1" stop-color="{p["base1"]}"/>
    </linearGradient>
    <radialGradient id="sun" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffe0b0" stop-opacity="{p["sun_op"]}"/>
      <stop offset="0.25" stop-color="#ffb07a" stop-opacity="0.22"/>
      <stop offset="0.6" stop-color="#ffb07a" stop-opacity="0.06"/>
      <stop offset="1" stop-color="#ffb07a" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="haze" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0.55" stop-color="{p["glow"]}" stop-opacity="{p["glow_op"]}"/>
      <stop offset="0.75" stop-color="{p["glow"]}" stop-opacity="{p["glow_op"] * 0.35:.3f}"/>
      <stop offset="1" stop-color="{p["glow"]}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="erde" cx="0.25" cy="0.22" r="0.95">
      <stop offset="0" stop-color="{OCEAN[0]}"/><stop offset="0.3" stop-color="{OCEAN[1]}"/>
      <stop offset="0.65" stop-color="{OCEAN[2]}"/><stop offset="1" stop-color="{OCEAN[4]}"/>
    </radialGradient>
    <radialGradient id="night" cx="0.85" cy="0.85" r="0.8">
      <stop offset="0" stop-color="{p["night"]}" stop-opacity="0.85"/>
      <stop offset="0.55" stop-color="{p["night"]}" stop-opacity="0.35"/>
      <stop offset="1" stop-color="{p["night"]}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="trail" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="{p["flame"]}" stop-opacity="0"/><stop offset="1" stop-color="{p["flame"]}" stop-opacity="0.75"/>
    </linearGradient>'''


def planet(cx, cy, r, p, seed, night=None, view=(0, 0, 3840, 2160)):
    return f'''<circle cx="{cx}" cy="{cy}" r="{r * 1.28:.0f}" fill="url(#haze)"/>
  {disc(cx, cy, r, p, seed, night, view)}'''


def disc(cx, cy, r, p, seed, night=None, view=(0, 0, 3840, 2160)):
    """Die Erdscheibe: Ozean, Kontinente, Wolken, Nachtseite mit Städten, leuchtender Atmosphärenrand.
    night: (x, y, Radius) der Nachtseite oder None."""
    shade = ""
    if night:
        nx, ny, nr = night
        shade = (f'<radialGradient id="nacht{seed}" gradientUnits="userSpaceOnUse" cx="{nx}" cy="{ny}" r="{nr}">'
                 f'<stop offset="0" stop-color="{p["night"]}" stop-opacity="0.92"/>'
                 f'<stop offset="0.55" stop-color="{p["night"]}" stop-opacity="0.7"/>'
                 f'<stop offset="1" stop-color="{p["night"]}" stop-opacity="0"/></radialGradient>'
                 f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#nacht{seed})"/>'
                 + city_lights(cx, cy, r, seed + 2, night))
    return f'''<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#erde)"/>
  <g clip-path="url(#disc)">
    {continents(cx, cy, r, seed, view)}
    {cloud_bands(cx, cy, r, seed + 1, view)}
    {shade}
  </g>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{p["glow"]}" stroke-opacity="0.6" stroke-width="8"/>
  <circle cx="{cx}" cy="{cy}" r="{r + 12}" fill="none" stroke="{p["glow"]}" stroke-opacity="0.2" stroke-width="18"/>'''


def motiv_wolken(p, design):
    cx, cy, r = 2860, 900, 600
    return f'''<defs>{defs_common(p, design)}
    <clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>
  <rect width="{W}" height="{H}" fill="url(#base)"/>
  <circle cx="420" cy="2260" r="1100" fill="{p["blob1"]}"/>
  <circle cx="3200" cy="-200" r="1300" fill="{p["blob2"]}"/>
  <circle cx="-260" cy="-240" r="1700" fill="url(#sun)"/>
  <ellipse cx="-260" cy="-240" rx="3500" ry="1450" transform="rotate(14 -260 -240)" fill="none" stroke="{p["orbit"]}" stroke-opacity="{p["orbit_op"]}" stroke-width="3"/>
  <ellipse cx="-260" cy="-240" rx="2200" ry="900" transform="rotate(14 -260 -240)" fill="none" stroke="{p["orbit"]}" stroke-opacity="{p["orbit_op"] * 0.6:.3f}" stroke-width="2" stroke-dasharray="6 22"/>
  <!-- Venus, hinter uns -->
  <circle cx="1020" cy="520" r="52" fill="{p["mercury"]}"/>
  <circle cx="1036" cy="536" r="52" fill="{p["night"]}" fill-opacity="0.45"/>
  <!-- Mond -->
  <circle cx="2120" cy="300" r="70" fill="{p["moon"]}"/>
  <circle cx="2142" cy="322" r="70" fill="{p["moon_shade"]}" fill-opacity="{p["moon_shade_op"]}"/>
  {planet(cx, cy, r, p, 7, night=(cx + r * 0.75, cy + r * 0.6, r * 1.1))}
  <path d="M1150 1250 C 1480 1300, 1800 1330, 2120 1300" fill="none" stroke="url(#trail)" stroke-width="6" stroke-linecap="round"/>
  {rocket(2150, 1296, 84, 3.2, p)}
  {stars(p, 11, avoid=(cx, cy, r * 1.25))}'''


HORIZONT = {"cx": 3300, "cy": 2900, "r": 1750, "rocket": (1648, 1027, 118, 3.4), "seed": 23, "stars": 5,
            "night": (4300, 1900, 1100)}


def motiv_horizont(p, design, parts=("grund", "wolken", "rakete", "sterne"), drift=None):
    """parts: welche Ebenen ins Bild kommen – für die Animation einzeln (siehe layers())."""
    global T
    h = HORIZONT
    cx, cy, r = h["cx"], h["cy"], h["r"]
    keep_t = T
    if drift is not None:
        T = drift
    body = [f'''<defs>{defs_common(p, design)}
    <clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>''']
    if "grund" in parts:
        body.append(f'''<rect width="{W}" height="{H}" fill="url(#base)"/>
  <circle cx="300" cy="-300" r="1300" fill="{p["blob2"]}"/>
  <circle cx="-200" cy="-200" r="1500" fill="url(#sun)"/>
  <!-- Venus (woher die Rakete kommt) und der Mond -->
  <circle cx="420" cy="980" r="26" fill="{p["mercury"]}"/>
  <circle cx="2300" cy="420" r="92" fill="{p["moon"]}"/>
  <circle cx="2268" cy="398" r="16" fill="#000000" fill-opacity="0.08"/>
  <circle cx="2330" cy="450" r="11" fill="#000000" fill-opacity="0.08"/>
  <circle cx="2328" cy="446" r="92" fill="{p["moon_shade"]}" fill-opacity="{p["moon_shade_op"]}"/>
  {planet(cx, cy, r, p, h["seed"], night=HORIZONT["night"])}
  <!-- Umlaufbahn um die Erde -->
  <ellipse cx="{cx}" cy="{cy}" rx="{r + 380}" ry="{r + 180}" transform="rotate(-8 {cx} {cy})" fill="none" stroke="{p["orbit"]}" stroke-opacity="{p["orbit_op"] * 1.3:.3f}" stroke-width="3" stroke-dasharray="10 26"/>''')
    elif "wolken" in parts:
        # nur die Erdscheibe (deckend) mit weitergezogenen Wolken – wird in der Shell überblendet
        body.append(disc(cx, cy, r, p, h["seed"], night=HORIZONT["night"]))
    if "rakete" in parts:
        x, y, ang, sc = h["rocket"]
        body.append(f'''<path d="M700 700 C 1050 760, 1350 860, 1620 1010" fill="none" stroke="url(#trail)" stroke-width="6" stroke-linecap="round"/>
  {rocket(x, y, ang, sc, p)}''')
    if "sterne" in parts:
        body.append(stars(p, h["stars"], n=95, avoid=(cx, cy, r * 1.2)))
    T = keep_t
    return "\n  ".join(body)


def layers(design):
    """Ebenen für den bewegten Hintergrund: grund (ohne Rakete/Sterne), wolken (Scheibe mit
    verschobenen Wolken zum Überblenden), rakete (Spur + Rakete), sterne (Daten)."""
    global T
    p = PAL[design]
    T = 0.0
    wrap = lambda body: (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n  '
                         f'<!-- Gibeon OS 3 „Emerald Earth“ – Ebene für den bewegten Hintergrund ({design}) -->\n  {body}\n</svg>\n')
    h = HORIZONT
    x, y, ang, _ = h["rocket"]
    meta = {"size": [W, H], "rocket": {"x": x, "y": y, "angle": ang}, "stars": star_list(h["stars"], 95, (h["cx"], h["cy"], h["r"] * 1.2)),
            "starColor": p["star"]}
    return {
        "grund.svg": wrap(motiv_horizont(p, design, ("grund",))),
        "wolken.svg": wrap(motiv_horizont(p, design, ("wolken",), drift=0.25)),
        "rakete.svg": wrap(motiv_horizont(p, design, ("rakete",))),
        "ebenen.json": json.dumps(meta, indent=2) + "\n",
    }


def motiv_sichel(p, design):
    cx, cy, r = 2760, 960, 560
    # Sichel: Sonne von links oben – der Rest liegt im Schatten (nur clipPath, kein mask: Qt SVG)
    shadow = p["base1"] if design == "graphit" else "#c9d1e2"
    return f'''<defs>{defs_common(p, design)}
    <clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
    <radialGradient id="rim" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0.8" stop-color="{p["glow"]}" stop-opacity="0"/>
      <stop offset="0.86" stop-color="{p["glow"]}" stop-opacity="{p["glow_op"] * 1.4:.2f}"/>
      <stop offset="1" stop-color="{p["glow"]}" stop-opacity="0"/>
    </radialGradient></defs>
  <rect width="{W}" height="{H}" fill="url(#base)"/>
  <circle cx="420" cy="2260" r="1100" fill="{p["blob1"]}"/>
  <circle cx="-300" cy="-300" r="1800" fill="url(#sun)"/>
  <circle cx="{cx}" cy="{cy}" r="{r * 1.25:.0f}" fill="url(#rim)"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#erde)"/>
  <g clip-path="url(#disc)">
    {continents(cx, cy, r, 41)}
    {cloud_bands(cx, cy, r, 42)}
    <circle cx="{cx + 230}" cy="{cy + 150}" r="{r * 1.02:.0f}" fill="{shadow}" fill-opacity="0.96"/>
  </g>
  <path d="M900 1820 C 1250 1700, 1560 1600, 1860 1520" fill="none" stroke="url(#trail)" stroke-width="5" stroke-linecap="round"/>
  {rocket(1888, 1512, 72, 2.8, p)}
  {stars(p, 3, n=110, avoid=(cx, cy, r * 1.3))}'''


MOTIVE = {"wolken": motiv_wolken, "horizont": motiv_horizont, "sichel": motiv_sichel}


def build(motiv, design):
    p = PAL[design]
    body = MOTIVE[motiv](p, design)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
            f'  <!-- Gibeon OS 3 „Emerald Earth“ – Motiv „{motiv}“, Design {design} -->\n  {body}\n</svg>\n')


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--frames":
    # bewegte Vorschau: python3 earth-wallpaper.py --frames <ordner> <motiv> <design> [bilder]
    out, motiv, design = Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    n = int(sys.argv[5]) if len(sys.argv) > 5 else 120
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        T = i / n
        (out / f"{i:04d}.svg").write_text(build(motiv, design), encoding="utf-8")
    sys.exit(0)

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--creative":
    # in Gibeon OS einsetzen: Hintergrund „Horizont“ für Schreibtisch, Anmeldung, Sperre, Startseite
    root = Path(__file__).resolve().parent.parent
    qml = root / "shell/creative_shell/qml/Creative"
    T = 0.0
    full = {d: build("horizont", d) for d in PAL}
    targets = {
        qml / "wallpapers/graphit.svg": full["graphit"], qml / "wallpapers-light/porzellan.svg": full["porzellan"],
        root / "browser/startpage/graphit.svg": full["graphit"], root / "browser/startpage/porzellan.svg": full["porzellan"],
        root / "login/creative/background.svg": full["graphit"], root / "login/creative/background-light.svg": full["porzellan"],
        root / "shell/lockscreen/graphit.svg": full["graphit"],
    }
    for d, folder in (("graphit", qml / "wallpapers/erde"), ("porzellan", qml / "wallpapers-light/erde")):
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in layers(d).items():
            targets[folder / name] = text
    for path, text in targets.items():
        path.write_text(text, encoding="utf-8")
        print("geschrieben:", path.relative_to(root))
    sys.exit(0)

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    for m in MOTIVE:
        for d in PAL:
            (out / f"erde-{m}-{d}.svg").write_text(build(m, d), encoding="utf-8")
            print(out / f"erde-{m}-{d}.svg")
