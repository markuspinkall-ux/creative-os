"""Hintergrundbilder „Vivid Venus“ (Creative OS 2) – drei Motive, je Graphit und Porzellan.

  python3 tools/venus-wallpaper.py <ordner>      → venus-<motiv>-<design>.svg

Motive:
  wolken   Venus groß rechts mit wirbelnden Wolkenbändern, die Rakete kommt vom Merkur
  horizont dicht über der Venus: ihr Rand füllt die untere Ecke, die Rakete zieht in die Umlaufbahn
  sichel   Venus als schmale Sichel im Gegenlicht der Sonne – ruhig und schlicht
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
        "glow": "#ffcf8a", "glow_op": 0.20, "sun_op": 0.5, "mercury": "#8a8781",
    },
    "porzellan": {
        "base0": "#dde5f3", "base1": "#d3dbeb", "blob1": "#d6dff0", "blob2": "#dbe3f4",
        "star": "#7b8aa8", "orbit": "#3d4b66", "orbit_op": 0.08, "night": "rgb(60,52,46)",
        "rocket_body": "#ffffff", "rocket_fin": "#3d6fe0", "rocket_window": "#1c2433", "flame": "#d9773a",
        "glow": "#ffd59a", "glow_op": 0.30, "sun_op": 0.42, "mercury": "#a9a49c",
    },
}
# Venus: blasses Gold bis Sandfarben (dichte Schwefelsäure-Wolken)
VENUS = ["#fff1cf", "#f4d9a0", "#e2b46e", "#b9844a", "#6b4a33"]


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


def cloud_bands(cx, cy, r, seed, tilt=-18):
    """Venus-Wolken: wenige, breite und sehr weiche Schleier (keine Streifen wie beim Jupiter),
    dazu das typische liegende „Y“ als zarter dunklerer Bogen."""
    rnd = random.Random(seed)
    drift = r * 0.06 * math.sin(2 * math.pi * T)     # Wolken ziehen langsam (Superrotation)
    out = [f'<g transform="translate({drift:.1f} 0) rotate({tilt} {cx} {cy})">']
    y = cy - r * 1.05
    while y < cy + r:
        h = rnd.uniform(0.16, 0.3) * r
        col = rnd.choice(VENUS[:3])
        op = rnd.uniform(0.07, 0.16)
        amp = rnd.uniform(0.06, 0.14) * r
        bend = (y - cy) / r * 0.22 * r
        x0, x1 = cx - r * 1.1, cx + r * 1.1
        top = (f"M{x0:.0f} {y:.0f} C {cx - r * 0.5:.0f} {y - amp + bend:.0f}, "
               f"{cx + r * 0.3:.0f} {y + amp + bend:.0f}, {x1:.0f} {y - amp * 0.4:.0f}")
        bot = (f"L{x1:.0f} {y + h:.0f} C {cx + r * 0.3:.0f} {y + h + amp + bend:.0f}, "
               f"{cx - r * 0.5:.0f} {y + h - amp + bend:.0f}, {x0:.0f} {y + h:.0f} Z")
        out.append(f'<path d="{top} {bot}" fill="{col}" fill-opacity="{op:.2f}"/>')
        y += h * rnd.uniform(0.55, 0.9)
    # liegendes Y
    out.append(f'<path d="M{cx - r * 1.1:.0f} {cy - r * 0.35:.0f} Q {cx - r * 0.1:.0f} {cy - r * 0.05:.0f} {cx + r * 1.1:.0f} {cy - r * 0.02:.0f} '
               f'L{cx + r * 1.1:.0f} {cy + r * 0.12:.0f} Q {cx - r * 0.1:.0f} {cy + r * 0.08:.0f} {cx - r * 1.1:.0f} {cy + r * 0.4:.0f} Z" '
               f'fill="{VENUS[3]}" fill-opacity="0.10"/>')
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
    <radialGradient id="venus" cx="0.25" cy="0.22" r="0.95">
      <stop offset="0" stop-color="{VENUS[0]}"/><stop offset="0.35" stop-color="{VENUS[1]}"/>
      <stop offset="0.7" stop-color="{VENUS[2]}"/><stop offset="1" stop-color="{VENUS[3]}"/>
    </radialGradient>
    <radialGradient id="night" cx="0.85" cy="0.85" r="0.8">
      <stop offset="0" stop-color="{p["night"]}" stop-opacity="0.85"/>
      <stop offset="0.55" stop-color="{p["night"]}" stop-opacity="0.35"/>
      <stop offset="1" stop-color="{p["night"]}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="trail" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="{p["flame"]}" stop-opacity="0"/><stop offset="1" stop-color="{p["flame"]}" stop-opacity="0.75"/>
    </linearGradient>'''


def planet(cx, cy, r, p, seed, night=True):
    return f'''<circle cx="{cx}" cy="{cy}" r="{r * 1.28:.0f}" fill="url(#haze)"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#venus)"/>
  <g clip-path="url(#disc)">
    {cloud_bands(cx, cy, r, seed)}
    {f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#night)"/>' if night else ""}
  </g>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{VENUS[0]}" stroke-opacity="0.35" stroke-width="5"/>'''


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
  <!-- Merkur, hinter uns -->
  <circle cx="1020" cy="520" r="46" fill="{p["mercury"]}"/>
  <circle cx="1034" cy="534" r="46" fill="{p["night"]}" fill-opacity="0.45"/>
  {planet(cx, cy, r, p, 7)}
  <path d="M1150 1250 C 1480 1300, 1800 1330, 2120 1300" fill="none" stroke="url(#trail)" stroke-width="6" stroke-linecap="round"/>
  {rocket(2150, 1296, 84, 3.2, p)}
  {stars(p, 11, avoid=(cx, cy, r * 1.25))}'''


HORIZONT = {"cx": 3300, "cy": 2900, "r": 1750, "rocket": (1648, 1027, 118, 3.4), "seed": 23, "stars": 5}


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
  {planet(cx, cy, r, p, h["seed"])}
  <!-- Umlaufbahn um die Venus -->
  <ellipse cx="{cx}" cy="{cy}" rx="{r + 380}" ry="{r + 180}" transform="rotate(-8 {cx} {cy})" fill="none" stroke="{p["orbit"]}" stroke-opacity="{p["orbit_op"] * 1.3:.3f}" stroke-width="3" stroke-dasharray="10 26"/>''')
    elif "wolken" in parts:
        # nur die Planetenscheibe (deckend) mit anders liegenden Wolken – wird in der Shell überblendet
        body.append(f'''<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#venus)"/>
  <g clip-path="url(#disc)">
    {cloud_bands(cx, cy, r, h["seed"])}
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#night)"/>
  </g>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{VENUS[0]}" stroke-opacity="0.35" stroke-width="5"/>''')
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
                         f'<!-- Creative OS 2 „Vivid Venus“ – Ebene für den bewegten Hintergrund ({design}) -->\n  {body}\n</svg>\n')
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
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#venus)"/>
  <g clip-path="url(#disc)">
    {cloud_bands(cx, cy, r, 41)}
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
            f'  <!-- Creative OS 2 „Vivid Venus“ – Motiv „{motiv}“, Design {design} -->\n  {body}\n</svg>\n')


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--frames":
    # bewegte Vorschau: python3 venus-wallpaper.py --frames <ordner> <motiv> <design> [bilder]
    out, motiv, design = Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    n = int(sys.argv[5]) if len(sys.argv) > 5 else 120
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        T = i / n
        (out / f"{i:04d}.svg").write_text(build(motiv, design), encoding="utf-8")
    sys.exit(0)

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--creative":
    # in Creative OS einsetzen: Hintergrund „Horizont“ für Schreibtisch, Anmeldung, Sperre, Startseite
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
    for d, folder in (("graphit", qml / "wallpapers/venus"), ("porzellan", qml / "wallpapers-light/venus")):
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
            (out / f"venus-{m}-{d}.svg").write_text(build(m, d), encoding="utf-8")
            print(out / f"venus-{m}-{d}.svg")
