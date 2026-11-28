"""KI-Liedstudio – Stile, Stimmen und Songtext-Aufbau (ohne Qt, damit es sich testen lässt).

ACE-Step erwartet:
  prompt  – Stichwörter zu Stil, Instrumenten, Stimme, Tempo (englisch)
  lyrics  – Songtext mit Abschnitten in eckigen Klammern: [verse], [chorus], [bridge] …
Im Liedstudio schreibt man deutsch („Strophe“, „Refrain“ …); to_ace() übersetzt die
Abschnittsnamen, der Text selbst bleibt in der Sprache, in der er geschrieben ist.
"""

import re

STYLES = [
    ("pop", "Pop", "pop, catchy, modern production, radio hit"),
    ("schlager", "Schlager", "german schlager, upbeat, accordion, catchy chorus, party"),
    ("rock", "Rock", "rock, electric guitar, drums, energetic, anthemic"),
    ("ballade", "Ballade", "ballad, emotional, piano, strings, slow"),
    ("hiphop", "Hip-Hop / Rap", "hip hop, rap, boom bap, deep bass, groovy"),
    ("edm", "EDM / Dance", "edm, dance, electronic, festival, drop, synth"),
    ("country", "Country", "country, acoustic guitar, banjo, warm"),
    ("metal", "Metal", "metal, heavy distorted guitars, double bass drums, powerful"),
    ("rnb", "R&B / Soul", "r&b, soul, smooth, groovy bass, warm keys"),
    ("akustik", "Akustik / Singer-Songwriter", "acoustic, singer-songwriter, guitar, intimate"),
    ("reggae", "Reggae", "reggae, offbeat guitar, relaxed, sunny"),
    ("jazz", "Jazz / Swing", "jazz, swing, upright bass, brushes, saxophone"),
    ("kinder", "Kinderlied", "children's song, cheerful, simple melody, playful"),
    ("weihnacht", "Weihnachtslied", "christmas song, sleigh bells, warm, festive"),
]

VOICES = [
    ("frau", "Frauenstimme", "female vocals"),
    ("mann", "Männerstimme", "male vocals"),
    ("duett", "Duett (Frau und Mann)", "duet, female and male vocals"),
    ("chor", "Chor", "choir vocals"),
]

MOODS = [
    ("", "Ohne Vorgabe", ""),
    ("froehlich", "Fröhlich", "happy, uplifting"),
    ("traurig", "Traurig", "sad, melancholic"),
    ("romantisch", "Romantisch", "romantic, tender"),
    ("energisch", "Energisch", "energetic, driving"),
    ("ruhig", "Ruhig", "calm, gentle"),
    ("episch", "Episch", "epic, powerful, cinematic"),
]

LANGUAGES = [("deutsch", "Deutsch", "german"), ("englisch", "Englisch", "english"),
             ("spanisch", "Spanisch", "spanish"), ("franzoesisch", "Französisch", "french"),
             ("italienisch", "Italienisch", "italian")]

LENGTHS = [(60, "1 Minute"), (90, "1½ Minuten"), (120, "2 Minuten"), (150, "2½ Minuten"),
           (180, "3 Minuten"), (210, "3½ Minuten"), (240, "4 Minuten")]

# deutsche Abschnittsnamen → ACE-Step
SECTIONS = {
    "strophe": "verse", "vers": "verse", "verse": "verse",
    "refrain": "chorus", "chorus": "chorus", "kehrreim": "chorus",
    "vor-refrain": "pre-chorus", "vorrefrain": "pre-chorus", "pre-chorus": "pre-chorus", "prechorus": "pre-chorus",
    "bridge": "bridge", "brücke": "bridge", "zwischenteil": "bridge",
    "intro": "intro", "einleitung": "intro", "outro": "outro", "schluss": "outro", "ende": "outro",
    "solo": "inst", "instrumental": "inst", "inst": "inst", "rap": "verse",
}

SKELETON = """[Strophe]
…

[Refrain]
…

[Strophe]
…

[Refrain]
…

[Bridge]
…

[Refrain]
…
"""


def _pick(table, key):
    for k, _label, value in table:
        if k == key:
            return value
    return ""


def build_prompt(style, voice, mood="", language="deutsch", bpm=0, extra=""):
    """Stichwörter für ACE-Step aus den Auswahlfeldern."""
    parts = [_pick(STYLES, style), _pick(VOICES, voice), _pick(MOODS, mood)]
    lang = _pick(LANGUAGES, language)
    if lang:
        parts.append(f"{lang} lyrics")
    if bpm:
        parts.append(f"{int(bpm)} bpm")
    extra = " ".join((extra or "").split())
    if extra:
        parts.append(extra)
    return ", ".join(p for p in parts if p)


def to_ace(lyrics):
    """Songtext ins ACE-Step-Format: Abschnittsnamen übersetzen, Platzhalter und Leerzeilen-Wirrwarr entfernen."""
    out = []
    for raw in (lyrics or "").replace("\r", "").split("\n"):
        line = raw.strip()
        m = re.fullmatch(r"\[\s*([^\]\d]+?)\s*\d*\s*\]", line)
        if m:
            name = m.group(1).strip().lower()
            out.append(f"[{SECTIONS.get(name, name)}]")
        elif line in ("…", "..."):
            continue
        else:
            out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Abschnitte ohne Text weglassen (ACE-Step singt sonst nichts Sinnvolles)
    blocks = [b for b in re.split(r"\n(?=\[)", text) if b.strip()]
    keep = [b for b in blocks if not re.fullmatch(r"\[[^\]]+\]\s*", b.strip()) or "[inst]" in b]
    return "\n\n".join(b.strip() for b in keep).strip()


def has_lyrics(lyrics):
    text = to_ace(lyrics)
    return bool(re.sub(r"\[[^\]]*\]", "", text).strip())


def suggest_length(lyrics):
    """Grobe Länge aus der Zahl der Textzeilen (≈ 4 s pro Zeile, dazu Intro/Outro)."""
    lines = [ln for ln in to_ace(lyrics).split("\n") if ln and not ln.startswith("[")]
    seconds = 20 + 4 * len(lines)
    best = min(LENGTHS, key=lambda item: abs(item[0] - seconds))
    return best[0]


def safe_name(title):
    s = re.sub(r"[^\w äöüÄÖÜß-]+", " ", (title or "").strip())
    return re.sub(r"\s+", " ", s)[:60].strip() or "Mein Lied"
