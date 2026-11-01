"""Erzeugt den Fensterrahmen „Creative Graphit“ (KWin/Aurorae).

Aufruf: python3 make_aurorae.py <Zielordner>
Titelleiste im Graphit-Ton, runde obere Ecken, weicher Schatten,
Knöpfe wie bei Windows 11 (Schließen wird beim Überfahren rot).
"""
import sys
from pathlib import Path

P, PB = 16, 16          # Schattenrand (seitlich, oben, unten)
T = 34                  # Höhe der Titelleiste
R = 8                   # Eckenradius oben
L = P + R               # Breite der linken/rechten Rahmenstücke
TT = P + T              # Höhe des oberen Rahmenstücks
BH = PB + 1             # Höhe des unteren Rahmenstücks
C = 40                  # Mittelstück

STYLES = {
    "": {"title": "#1c2029", "line": "#ffffff", "lineop": 0.10, "shadow": 0.42},
    "-inactive": {"title": "#171a22", "line": "#ffffff", "lineop": 0.06, "shadow": 0.24},
}

defs, body = [], []
gid = [0]


def grad(kind, coords, a, units="userSpaceOnUse"):
    gid[0] += 1
    name = f"g{gid[0]}"
    stops = (f'<stop offset="0" stop-color="#000" stop-opacity="{a}"/>'
             f'<stop offset="1" stop-color="#000" stop-opacity="0"/>')
    if kind == "lin":
        x1, y1, x2, y2 = coords
        defs.append(f'<linearGradient id="{name}" gradientUnits="{units}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{stops}</linearGradient>')
    else:
        cx, cy, r, inner = coords
        stops = f'<stop offset="0" stop-color="#000" stop-opacity="{a}"/>'
        if inner > 0:
            stops += f'<stop offset="{inner:.3f}" stop-color="#000" stop-opacity="{a}"/>'
        stops += '<stop offset="1" stop-color="#000" stop-opacity="0"/>'
        defs.append(f'<radialGradient id="{name}" gradientUnits="{units}" cx="{cx}" cy="{cy}" r="{r}" fx="{cx}" fy="{cy}">{stops}</radialGradient>')
    return f"url(#{name})"


def rect(x, y, w, h, fill, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{extra}/>'


def frame(prefix, st, ox, oy):
    """Neun Rahmenstücke; (ox, oy) verschiebt das Stück auf der Zeichenfläche."""
    a, title, line, lop = st["shadow"], st["title"], st["line"], st["lineop"]
    W = L + C + L
    H = TT + C + BH
    X0, Y0 = ox, oy
    ln = f' fill-opacity="{lop}"'

    def g(name, x, y, w, h, parts):
        body.append(f'<g id="{prefix}-{name}">' + rect(x, y, w, h, "#000", ' fill-opacity="0"') + "".join(parts) + "</g>")

    # oben links: Schatten (rund) + Titelecke
    x, y = X0, Y0
    g("topleft", x, y, L, TT, [
        rect(x, y, L, P + R, grad("rad", (x + L, y + P + R, P + R, R / (P + R)), a)),
        rect(x, y + P + R, P, T - R, grad("lin", (x + P, 0, x, 0), a)),
        f'<path d="M{x + P} {y + TT} V{y + P + R} A{R} {R} 0 0 1 {x + L} {y + P} V{y + TT} Z" fill="{title}"/>',
        f'<path d="M{x + P + 0.5} {y + TT} V{y + P + R} A{R - 0.5} {R - 0.5} 0 0 1 {x + L} {y + P + 0.5}" fill="none" stroke="{line}" stroke-opacity="{lop}"/>',
    ])
    # oben
    x = X0 + L
    g("top", x, y, C, TT, [
        rect(x, y, C, P, grad("lin", (0, y + P, 0, y), a)),
        rect(x, y + P, C, T, title),
        rect(x, y + P, C, 1, line, ln),
    ])
    # oben rechts
    x = X0 + L + C
    g("topright", x, y, L, TT, [
        rect(x, y, L, P + R, grad("rad", (x, y + P + R, P + R, R / (P + R)), a)),
        rect(x + R, y + P + R, P, T - R, grad("lin", (x + R, 0, x + L, 0), a)),
        f'<path d="M{x + R} {y + TT} V{y + P + R} A{R} {R} 0 0 0 {x} {y + P} V{y + TT} Z" fill="{title}"/>',
        f'<path d="M{x + R - 0.5} {y + TT} V{y + P + R} A{R - 0.5} {R - 0.5} 0 0 0 {x} {y + P + 0.5}" fill="none" stroke="{line}" stroke-opacity="{lop}"/>',
    ])
    # links / rechts
    y = Y0 + TT
    x = X0
    g("left", x, y, L, C, [rect(x, y, P, C, grad("lin", (x + P, 0, x, 0), a)), rect(x + P, y, 1, C, line, ln)])
    g("center", X0 + L, y, C, C, [])
    x = X0 + L + C
    g("right", x, y, L, C, [rect(x + R, y, P, C, grad("lin", (x + R, 0, x + L, 0), a)), rect(x + R - 1, y, 1, C, line, ln)])
    # unten
    y = Y0 + TT + C
    x = X0
    g("bottomleft", x, y, L, BH, [
        rect(x, y, P, 1, grad("lin", (x + P, 0, x, 0), a)),
        rect(x, y + 1, P, PB, grad("rad", (x + P, y + 1, PB, 0.0), a)),
        rect(x + P, y + 1, R, PB, grad("lin", (0, y + 1, 0, y + BH), a)),
        rect(x + P, y, L - P, 1, line, ln),
    ])
    x = X0 + L
    g("bottom", x, y, C, BH, [rect(x, y + 1, C, PB, grad("lin", (0, y + 1, 0, y + BH), a)), rect(x, y, C, 1, line, ln)])
    x = X0 + L + C
    g("bottomright", x, y, L, BH, [
        rect(x + R, y, P, 1, grad("lin", (x + R, 0, x + L, 0), a)),
        rect(x + R, y + 1, P, PB, grad("rad", (x + R, y + 1, PB, 0.0), a)),
        rect(x, y + 1, R, PB, grad("lin", (0, y + 1, 0, y + BH), a)),
        rect(x, y, R, 1, line, ln),
    ])
    return W, H


def maximized(prefix, title, ox, oy):
    for i, name in enumerate(["topleft", "top", "topright", "left", "center", "right", "bottomleft", "bottom", "bottomright"]):
        x, y = ox + (i % 3) * 12, oy + (i // 3) * 12
        body.append(f'<g id="{prefix}-{name}">{rect(x, y, 10, 10, title)}</g>')


def decoration():
    defs.clear(); body.clear()
    w, h = frame("decoration", STYLES[""], 0, 0)
    frame("decoration-inactive", STYLES["-inactive"], 0, h + 10)
    maximized("decoration-maximized", STYLES[""]["title"], w + 10, 0)
    maximized("decoration-maximized-inactive", STYLES["-inactive"]["title"], w + 60, 0)
    return svg(w + 110, 2 * h + 10)


def svg(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>\n')


BW, BHT = 46, T
GLYPHS = {
    "close": '<path d="M18 12 L28 22 M28 12 L18 22" fill="none" stroke="{c}" stroke-width="1.1" stroke-linecap="round"/>',
    "minimize": '<path d="M18 17.5 H28" fill="none" stroke="{c}" stroke-width="1.1" stroke-linecap="round"/>',
    "maximize": '<rect x="18.5" y="12.5" width="9" height="9" rx="1.6" fill="none" stroke="{c}" stroke-width="1.1"/>',
    "restore": '<rect x="18.5" y="14.5" width="7.5" height="7.5" rx="1.4" fill="none" stroke="{c}" stroke-width="1.1"/>'
               '<path d="M20.5 12.5 H26.2 A1.4 1.4 0 0 1 27.6 13.9 V19.6" fill="none" stroke="{c}" stroke-width="1.1" stroke-linecap="round"/>',
}
TEXT, MUTED = "#dce6ff", "#7f889c"


def button(kind):
    defs.clear(); body.clear()
    close = kind == "close"
    states = [
        ("active", None, TEXT), ("hover", "#c42b1c" if close else "rgba", "#ffffff" if close else TEXT),
        ("pressed", "#a32418" if close else "rgba2", "#ffffff" if close else TEXT),
        ("deactivated", None, MUTED), ("inactive", None, MUTED),
        ("hover-inactive", "#c42b1c" if close else "rgba", "#ffffff" if close else TEXT),
        ("pressed-inactive", "#a32418" if close else "rgba2", "#ffffff" if close else TEXT),
        ("deactivated-inactive", None, MUTED),
    ]
    for i, (state, bg, color) in enumerate(states):
        ox = i * (BW + 4)
        parts = [rect(0, 0, BW, BHT, "#000", ' fill-opacity="0"')]
        if bg == "rgba":
            parts.append(rect(0, 0, BW, BHT, "#ffffff", ' fill-opacity="0.08"'))
        elif bg == "rgba2":
            parts.append(rect(0, 0, BW, BHT, "#ffffff", ' fill-opacity="0.05"'))
        elif bg:
            # Schließen sitzt ganz rechts: obere rechte Ecke passend zum Fenster gerundet
            parts.append(f'<path d="M0 0 H{BW - R} A{R} {R} 0 0 1 {BW} {R} V{BHT} H0 Z" fill="{bg}"/>')
        parts.append(GLYPHS[kind].format(c=color))
        body.append(f'<g id="{state}-center" transform="translate({ox} 0)">' + "".join(parts) + "</g>")
    return svg(len(states) * (BW + 4), BHT)


RC = f"""[General]
ActiveTextColor=220,230,255,255
InactiveTextColor=127,136,156,255
TitleAlignment=Left
TitleVerticalAlignment=Center
Animation=120
Shadow=false
HaloActive=false
HaloInactive=false
DecorationPosition=0

[Layout]
BorderLeft=1
BorderRight=1
BorderBottom=1
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft=10
TitleEdgeRight=0
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=10
TitleEdgeRightMaximized=0
TitleBorderLeft=8
TitleBorderRight=8
TitleHeight={T}
ButtonWidth={BW}
ButtonHeight={BHT}
ButtonSpacing=0
ButtonMarginTop=0
ExplicitButtonSpacer=0
PaddingTop={P}
PaddingBottom={PB}
PaddingLeft={P}
PaddingRight={P}
"""

META_DESKTOP = """[Desktop Entry]
Name=Creative Graphit
Comment=Fensterrahmen von Creative OS
X-KDE-PluginInfo-Name=CreativeGraphit
X-KDE-PluginInfo-Author=Creative OS
X-KDE-PluginInfo-Version=1.0
X-KDE-PluginInfo-License=GPL
"""
META_JSON = """{
    "KPlugin": {
        "Id": "CreativeGraphit",
        "Name": "Creative Graphit",
        "Description": "Fensterrahmen von Creative OS",
        "Authors": [{ "Name": "Creative OS" }],
        "License": "GPL",
        "Version": "1.0"
    }
}
"""

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "CreativeGraphit")
    out.mkdir(parents=True, exist_ok=True)
    (out / "decoration.svg").write_text(decoration())
    for kind in GLYPHS:
        (out / f"{kind}.svg").write_text(button(kind))
    (out / "CreativeGraphitrc").write_text(RC)
    (out / "metadata.desktop").write_text(META_DESKTOP)
    (out / "metadata.json").write_text(META_JSON)
    print("Fensterrahmen erzeugt in", out)
