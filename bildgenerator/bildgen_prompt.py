"""Prompt-Aufbau des KI-Bildgenerators – ohne Qt, damit er sich testen lässt.

Im Modus „Für 3D Studio“ wird die Beschreibung um feste Vorgaben ergänzt, mit denen
TRELLIS die saubersten Figuren baut: ein einzelnes Motiv, ganz im Bild und mittig,
von vorn, neutraler Hintergrund, weiches gleichmäßiges Licht, keine harten Schatten,
kein Text. Figuren stehen dazu in neutraler A-Haltung (lässt sich später gut
mit Gelenken versehen).
"""

MODES = [
    ("figur", "Für 3D Studio – Figur", "Person, Tier oder Fantasiewesen als 3D-Vorlage"),
    ("gegenstand", "Für 3D Studio – Gegenstand", "Fahrzeug, Möbel, Requisite … als 3D-Vorlage"),
    ("frei", "Freies Bild", "Ganz normales Bild, ohne Vorgaben für 3D"),
]

STYLES = [
    ("auto", "Ohne Vorgabe", ""),
    ("realistisch", "Realistisch", "photorealistic, realistic materials and textures"),
    ("spielfigur", "Spielfigur (3D-Render)", "stylized 3D game asset render, clean shapes, PBR materials"),
    ("comic", "Comic", "stylized cartoon illustration, clean outlines, flat colors"),
    ("figur", "Sammelfigur", "collectible vinyl figure, smooth painted surfaces"),
]

SIZES = [
    ("quadrat", "Quadrat (1024 × 1024)", 1024, 1024),
    ("quer", "Querformat (1344 × 768)", 1344, 768),
    ("hoch", "Hochformat (768 × 1344)", 768, 1344),
]

# Vorgaben für 3D (Englisch – FLUX versteht Englisch am besten)
FOR_3D = {
    "figur": ("single character, full body from head to feet, standing in a neutral A-pose, arms slightly "
              "away from the body, facing the camera, front view, centered with margin around it"),
    "gegenstand": ("single object, entire object fully visible, three-quarter front view, centered with margin "
                   "around it, standing on nothing"),
}
BACKGROUND_3D = ("isolated on a plain light grey background, soft even studio lighting, no harsh shadows, "
                 "no text, no watermark, no other objects, sharp focus, high detail")


def build_prompt(text, mode="figur", style="auto"):
    """Fertiger Prompt für FLUX aus der Beschreibung des Nutzers."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    parts = [text]
    style_text = dict((k, v) for k, _, v in STYLES).get(style, "")
    if style_text:
        parts.append(style_text)
    if mode in FOR_3D:
        parts.insert(0, FOR_3D[mode].split(",")[0])        # „single character“/„single object“ nach vorn
        parts.append(FOR_3D[mode].split(",", 1)[1].strip())
        parts.append(BACKGROUND_3D)
    return ", ".join(parts)


def size_for(mode, size_key):
    """Format: 3D-Vorlagen immer quadratisch (so erwartet es TRELLIS)."""
    if mode in FOR_3D:
        return 1024, 1024
    for key, _, w, h in SIZES:
        if key == size_key:
            return w, h
    return 1024, 1024


def safe_stem(text, limit=40):
    """Dateiname aus der Beschreibung (nur Buchstaben, Ziffern, Bindestrich)."""
    out = []
    for ch in (text or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    stem = "".join(out).strip("-")[:limit].strip("-")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        stem = stem.replace(a, b)
    return "".join(c for c in stem if c.isascii()) or "bild"
