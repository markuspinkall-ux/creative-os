"""Vorschläge des KI-Musikgenerators – ohne Qt, damit sie sich testen lassen.

Zwei Arten:
  musik  – Hintergrundmusik (ACE-Step), z. B. für Spiele, Videos, Menüs
  atmo   – Geräusche und Atmosphäre (Stable Audio Open), z. B. Vogelgezwitscher.
           Hier erzeugt die KI mehrere kurze Varianten („Ereignisse“), der Mischer
           baut daraus mit Pausen eine lange Spur – auf Wunsch über einem leisen
           Klangteppich („Grund“), damit es natürlich klingt und nicht nervt.

suggest(text) liefert passende Vorschläge zu dem, was man eintippt (deutsche
Stichwörter). Die KI-Prompts selbst sind englisch, weil die Modelle Englisch am
besten verstehen.
"""

import re
import unicodedata

MUSIK = "musik"
ATMO = "atmo"

# key, Titel, Art, Stichwörter, Prompt(s), Voreinstellungen
SUGGESTIONS = [
    # ---- Atmosphäre / Geräusche -----------------------------------------------------
    {"key": "voegel-wald", "title": "Vogelgezwitscher im Wald", "kind": ATMO,
     "words": "vogel vögel vogelgezwitscher zwitschern gezwitscher wald morgen frühling natur amsel",
     "event": "a single songbird singing a short melodic phrase, clear birdsong, forest, close, natural field recording",
     "bed": "quiet forest ambience, soft wind in leaves, distant birds, calm, field recording",
     "event_seconds": 8, "pause": "lang", "variants": 5},
    {"key": "voegel-morgen", "title": "Morgenchor (viele Vögel)", "kind": ATMO,
     "words": "vogel vögel morgen sonnenaufgang chor dawn",
     "event": "dawn chorus, several birds chirping, morning in the countryside, field recording",
     "bed": "", "event_seconds": 20, "pause": "kurz", "variants": 3},
    {"key": "moewen", "title": "Möwen am Meer", "kind": ATMO,
     "words": "möwe möwen meer küste hafen strand vogel",
     "event": "seagulls calling over the sea, coastal birds, field recording",
     "bed": "gentle ocean waves on a beach, calm sea ambience", "event_seconds": 6, "pause": "lang", "variants": 4},
    {"key": "eulen", "title": "Eulen in der Nacht", "kind": ATMO,
     "words": "eule eulen nacht kauz vogel dunkel wald",
     "event": "an owl hooting at night, single call, forest, field recording",
     "bed": "night forest ambience, crickets, soft wind", "event_seconds": 6, "pause": "sehrlang", "variants": 4},
    {"key": "regen", "title": "Regen am Fenster", "kind": ATMO,
     "words": "regen regnen tropfen fenster schauer gewitter",
     "event": "steady rain falling on a window and roof, cozy indoor rain ambience",
     "bed": "", "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "gewitter", "title": "Gewitter mit Donner", "kind": ATMO,
     "words": "gewitter donner blitz sturm unwetter regen",
     "event": "a distant thunder rumble, single thunderclap rolling away",
     "bed": "heavy rain ambience, steady rainfall", "event_seconds": 10, "pause": "lang", "variants": 4},
    {"key": "lagerfeuer", "title": "Lagerfeuer", "kind": ATMO,
     "words": "feuer lagerfeuer kamin knistern holz camping",
     "event": "crackling campfire, wood popping and burning, close recording",
     "bed": "", "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "meer", "title": "Meeresrauschen", "kind": ATMO,
     "words": "meer wellen strand ozean brandung see wasser",
     "event": "ocean waves crashing on a sandy beach, calm sea", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "bach", "title": "Plätschernder Bach", "kind": ATMO,
     "words": "bach fluss wasser plätschern quelle wald",
     "event": "a small stream flowing over rocks, gentle water babbling", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "hoehle", "title": "Höhle mit Wassertropfen", "kind": ATMO,
     "words": "höhle tropfen dungeon unterirdisch grotte echo",
     "event": "a single water drop falling in a cave, echo, reverberant",
     "bed": "dark cave ambience, low rumble, distant wind, reverberant", "event_seconds": 3,
     "pause": "mittel", "variants": 5},
    {"key": "stadt", "title": "Großstadt", "kind": ATMO,
     "words": "stadt verkehr autos straße großstadt menschen",
     "event": "busy city street ambience, traffic, people walking, distant horns", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "taverne", "title": "Taverne / Gasthaus", "kind": ATMO,
     "words": "taverne gasthaus kneipe mittelalter menschen gemurmel",
     "event": "medieval tavern ambience, crowd murmur, clinking mugs, laughter", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "wind", "title": "Wind in den Bergen", "kind": ATMO,
     "words": "wind berge sturm pfeifen gebirge kalt",
     "event": "howling wind in the mountains, cold, gusts", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "grillen", "title": "Grillen im Sommer", "kind": ATMO,
     "words": "grillen zirpen sommer abend nacht wiese insekten",
     "event": "crickets chirping on a warm summer night, meadow", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    {"key": "raumschiff", "title": "Raumschiff-Brücke", "kind": ATMO,
     "words": "weltraum raumschiff scifi computer piepen brücke",
     "event": "spaceship bridge ambience, low engine hum, soft computer beeps", "bed": "",
     "event_seconds": 30, "pause": "kurz", "variants": 2, "continuous": True},
    # ---- Musik ----------------------------------------------------------------------
    {"key": "dorf", "title": "Friedliches Dorf (Fantasy)", "kind": MUSIK,
     "words": "dorf fantasy rpg ruhig friedlich mittelalter flöte harfe",
     "prompt": "instrumental, fantasy RPG village theme, peaceful, warm, flute, harp, acoustic guitar, strings, 90 bpm",
     "seconds": 120},
    {"key": "boss", "title": "Epischer Bosskampf", "kind": MUSIK,
     "words": "boss kampf episch schlacht action orchester spannung",
     "prompt": "instrumental, epic orchestral boss battle music, intense, choir, timpani, brass, strings, 150 bpm",
     "seconds": 120},
    {"key": "dungeon", "title": "Dunkler Dungeon", "kind": MUSIK,
     "words": "dungeon dunkel höhle horror gruselig spannung",
     "prompt": "instrumental, dark ambient dungeon music, mysterious, low drones, sparse piano, eerie, 70 bpm",
     "seconds": 120},
    {"key": "8bit", "title": "Retro 8-Bit Menü", "kind": MUSIK,
     "words": "8bit retro chiptune pixel menü arcade nintendo",
     "prompt": "instrumental, chiptune, 8-bit retro video game menu music, catchy, upbeat, 130 bpm",
     "seconds": 90},
    {"key": "lofi", "title": "Entspannter Lo-Fi", "kind": MUSIK,
     "words": "lofi chill entspannt lernen ruhig beat",
     "prompt": "instrumental, lo-fi hip hop, chill, relaxed, soft piano, vinyl crackle, mellow drums, 80 bpm",
     "seconds": 150},
    {"key": "weltraum", "title": "Weltraum-Erkundung", "kind": MUSIK,
     "words": "weltraum space scifi sterne synth erkundung",
     "prompt": "instrumental, ambient synthwave space exploration music, ethereal pads, arpeggios, 100 bpm",
     "seconds": 150},
    {"key": "rennen", "title": "Rennspiel / Action", "kind": MUSIK,
     "words": "rennen auto racing action schnell elektro",
     "prompt": "instrumental, energetic electronic racing game music, driving bass, fast drums, synth lead, 160 bpm",
     "seconds": 120},
    {"key": "abenteuer", "title": "Großes Abenteuer", "kind": MUSIK,
     "words": "abenteuer reise held orchester episch weite",
     "prompt": "instrumental, adventurous orchestral theme, heroic, sweeping strings, horns, 110 bpm",
     "seconds": 120},
    {"key": "gemuetlich", "title": "Gemütlich / Farm", "kind": MUSIK,
     "words": "farm gemütlich bauernhof cozy landleben fröhlich",
     "prompt": "instrumental, cozy farming game music, cheerful, acoustic guitar, ukulele, glockenspiel, 100 bpm",
     "seconds": 150},
    {"key": "spannung", "title": "Spannung / Schleichen", "kind": MUSIK,
     "words": "spannung schleichen stealth krimi thriller",
     "prompt": "instrumental, tense stealth game music, pulsing bass, ticking percussion, suspense, 95 bpm",
     "seconds": 120},
]

# Einfache Wortliste für eigene Eingaben bei Geräuschen (Stable Audio versteht vor allem Englisch)
WORDS = {
    "vogel": "bird", "vögel": "birds", "vogelgezwitscher": "birdsong", "gezwitscher": "birds chirping",
    "zwitschern": "chirping", "wald": "forest", "regen": "rain", "gewitter": "thunderstorm", "donner": "thunder",
    "wind": "wind", "meer": "sea", "wellen": "waves", "strand": "beach", "bach": "stream", "fluss": "river",
    "wasser": "water", "feuer": "fire", "lagerfeuer": "campfire", "kamin": "fireplace", "stadt": "city",
    "verkehr": "traffic", "nacht": "night", "morgen": "morning", "abend": "evening", "grillen": "crickets",
    "eule": "owl", "möwen": "seagulls", "möwe": "seagull", "hund": "dog", "katze": "cat", "pferd": "horse",
    "schritte": "footsteps", "tür": "door", "glocke": "bell", "kirche": "church", "uhr": "clock", "ticken": "ticking",
    "höhle": "cave", "tropfen": "dripping", "schnee": "snow", "eis": "ice", "berge": "mountains",
    "taverne": "tavern", "menschen": "people", "markt": "marketplace", "schwert": "sword", "magie": "magic",
    "raumschiff": "spaceship", "computer": "computer", "maschine": "machine", "zug": "train", "auto": "car",
    "frösche": "frogs", "frosch": "frog", "insekten": "insects", "bienen": "bees", "wiese": "meadow",
    "ruhig": "calm", "leise": "quiet", "laut": "loud", "sanft": "gentle", "dunkel": "dark", "gruselig": "creepy",
    "fern": "distant", "nah": "close", "und": "and", "mit": "with", "im": "in the", "am": "at the", "in": "in",
}


def _plain(text):
    return unicodedata.normalize("NFC", (text or "").lower())


def _tokens(text):
    return [t for t in re.split(r"[^\wäöüß]+", _plain(text)) if t]


def suggest(text, kind=None, limit=6):
    """Passende Vorschläge zu einer Eingabe (Stichwörter, auch Wortanfänge wie „vog“)."""
    tokens = _tokens(text)
    scored = []
    for i, s in enumerate(SUGGESTIONS):
        if kind and s["kind"] != kind:
            continue
        words = s["words"].split() + _tokens(s["title"])
        score = 0
        for t in tokens:
            if len(t) < 3:
                continue
            if t in words:
                score += 3
            elif any(w.startswith(t) or (len(t) > 4 and t in w) for w in words):
                score += 2
            elif any(len(w) >= 4 and w in t for w in words):    # „vogelgezwitscher“ enthält „vogel“
                score += 1
        if score:
            scored.append((-score, i, s))
    scored.sort()
    return [s for _, _, s in scored[:limit]]


def by_key(key):
    return next((s for s in SUGGESTIONS if s["key"] == key), None)


def to_english(text):
    """Eigene Eingabe für Geräusche grob ins Englische übertragen (bekannte Wörter)."""
    out = []
    for t in _tokens(text):
        out.append(WORDS.get(t, t))
    return " ".join(out)


def music_prompt(text, suggestion=None):
    """Prompt für ACE-Step. ACE-Step versteht viele Sprachen; „instrumental“ verhindert Gesang."""
    base = suggestion["prompt"] if suggestion else ""
    extra = " ".join((text or "").split())
    if suggestion and extra and extra.lower() != suggestion["title"].lower():
        base = f"{base}, {extra}"
    elif not suggestion:
        base = f"instrumental, background music, {extra}, game soundtrack, loopable"
    if "instrumental" not in base.lower():
        base = "instrumental, " + base
    return base


def atmo_plan(text, suggestion=None):
    """Plan für Geräusche: welche Klänge erzeugen, wie lang, wie viele Varianten, ob mit Pausen."""
    if suggestion:
        return {"event": suggestion["event"], "bed": suggestion.get("bed", ""),
                "event_seconds": suggestion["event_seconds"], "variants": suggestion["variants"],
                "pause": suggestion["pause"], "continuous": bool(suggestion.get("continuous"))}
    english = to_english(text)
    return {"event": f"{english}, natural field recording, high quality", "bed": "", "event_seconds": 10,
            "variants": 4, "pause": "mittel", "continuous": False}
