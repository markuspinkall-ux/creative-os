"""Versteht, was gesagt wurde (deutsche Sätze → Absicht + Werte).

Bewusst einfach und ohne Internet: feste Satzmuster, die die üblichen
Formulierungen abdecken. Rein Python, darum gut testbar.
"""

import re
import unicodedata

NUMBERS = {
    "null": 0, "ein": 1, "eine": 1, "einen": 1, "einer": 1, "eins": 1, "zwei": 2, "zwo": 2, "drei": 3,
    "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11,
    "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15, "sechzehn": 16, "siebzehn": 17,
    "achtzehn": 18, "neunzehn": 19, "zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50,
    "sechzig": 60, "neunzig": 90,
}
UNITS = {"sekunde": 1, "sekunden": 1, "minute": 60, "minuten": 60, "stunde": 3600, "stunden": 3600}


def clean(text):
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\wäöüß\s.,:-]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .,")


def word_number(token):
    """„fünfundzwanzig“ → 25, „5“ → 5, sonst None."""
    if re.fullmatch(r"\d+([.,]\d+)?", token):
        return float(token.replace(",", "."))
    if token in NUMBERS:
        return NUMBERS[token]
    m = re.fullmatch(r"(\w+?)und(\w+)", token)
    if m and m.group(1) in NUMBERS and m.group(2) in NUMBERS:
        return NUMBERS[m.group(1)] + NUMBERS[m.group(2)]
    return None


def parse_duration(text):
    """Sekunden aus „5 minuten“, „eine halbe stunde“, „1 stunde und 20 minuten“ …"""
    t = clean(text)
    total = 0
    if "halbe stunde" in t:
        total += 1800
        t = t.replace("halbe stunde", "")
    if "viertelstunde" in t or "viertel stunde" in t:
        total += 900
        t = t.replace("viertelstunde", "").replace("viertel stunde", "")
    if "anderthalb stunden" in t or "eineinhalb stunden" in t:
        total += 5400
        t = t.replace("anderthalb stunden", "").replace("eineinhalb stunden", "")
    tokens = t.split()
    for i, tok in enumerate(tokens):
        unit = UNITS.get(tok)
        if unit and i > 0:
            n = word_number(tokens[i - 1])
            if n is not None:
                total += n * unit
            elif tokens[i - 1] in ("halbe", "halben"):
                total += unit / 2
    return int(total)


def say_duration(seconds):
    seconds = int(round(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    parts = []
    if h:
        parts.append("eine Stunde" if h == 1 else f"{h} Stunden")
    if m:
        parts.append("eine Minute" if m == 1 else f"{m} Minuten")
    if s and not h:
        parts.append("eine Sekunde" if s == 1 else f"{s} Sekunden")
    if not parts:
        return "0 Sekunden"
    return " und ".join([", ".join(parts[:-1]), parts[-1]]) if len(parts) > 1 else parts[0]


DAY_WORDS = {"heute": 0, "morgen": 1, "übermorgen": 2}

PLAY_VERBS = r"(spiel\w*|abspielen|play|hör\w*|anmachen|mach\w*|leg\w*|starte\w*|such\w*)"
EDGE_WORDS = {
    "computer", "hey", "bitte", "mal", "doch", "einmal", "mir", "uns", "kannst", "könntest", "würdest", "du",
    "ich", "will", "möchte", "würde", "gern", "gerne", "spiel", "spiele", "spielen", "spielst", "abspielen",
    "play", "hör", "höre", "hören", "mach", "mache", "machen", "leg", "lege", "legen", "starte", "starten",
    "such", "suche", "suchen", "auf", "an", "ab", "vor", "etwas", "was", "musik", "das", "lied", "den", "die",
    "song", "titel", "einen", "ein", "eine", "und", "bei", "über", "the", "nach",
}
LEADING_ONLY = {"von", "lieder", "songs", "album"}


def music_query(t):
    """Gibt den Suchbegriff zurück, "" wenn nur „spiel Musik“ gesagt wurde,
    oder None, wenn es nicht um Musik geht."""
    t = t.replace(",", " ").replace(".", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if not re.search(rf"\b{PLAY_VERBS}\b", t) and "youtube" not in t:
        return None
    # „… auf/bei/von/über youtube“ am Ende weg
    t = re.sub(r"\s*\b(auf|bei|von|über|in|mit)\s+youtube\b", " ", t)
    t = t.replace("youtube", " ")
    words = t.split()
    while words and (words[0] in EDGE_WORDS or words[0] in LEADING_ONLY):
        words.pop(0)
    while words and words[-1] in EDGE_WORDS:
        words.pop()
    return " ".join(words).strip()



def parse(text):
    """Gibt (absicht, werte) zurück."""
    t = clean(text)
    if not t:
        return ("nothing", {})

    # --- Musik steuern (kurze Befehle zuerst) ---
    if re.fullmatch(r"(stopp?|stop|halt|aus|ruhe|sei still|musik (aus|stopp?|stoppen|beenden)|stopp? die musik|beende die musik|aufhören|hör auf)", t):
        return ("stop", {})
    if re.fullmatch(r"(pause|pausieren|musik pausieren|pausiere( die musik)?)", t):
        return ("pause", {})
    if re.fullmatch(r"(weiter|fortsetzen|weiterspielen|musik weiter|spiel weiter)", t):
        return ("resume", {})
    if re.search(r"\blauter\b", t):
        return ("volume", {"delta": +15})
    if re.search(r"\bleiser\b", t):
        return ("volume", {"delta": -15})
    if re.search(r"(nächste[sn]? (lied|song|titel)|überspringen|skip)", t):
        return ("next", {})

    # --- Beginnt der Satz mit „Spiel …“, geht es um Musik (auch bei „Kalt wie Eis“) ---
    if re.match(rf"^(?:(?:computer|hey|bitte|mal|kannst du|könntest du|ich (?:will|möchte|würde gern))\s+)*{PLAY_VERBS}\b",
                t.replace(",", " ")) and not re.search(r"\b(timer|wecker)\b", t):
        query = music_query(t)
        if query is not None:
            return ("music_ask", {}) if query == "" else ("play", {"query": query})

    # --- Timer ---
    if "timer" in t or "wecker" in t or "erinnere mich in" in t:
        if re.search(r"(stopp|stop|abbrechen|lösch|beende|aus\b|aus$)", t):
            return ("timer_stop", {})
        if re.search(r"(wie lange|wie viel zeit|restzeit|noch)", t) and not parse_duration(t):
            return ("timer_status", {})
        seconds = parse_duration(t)
        if seconds:
            return ("timer_set", {"seconds": seconds})
        return ("timer_ask", {})

    # --- Wetter ---
    if re.search(r"\b(wetter|regnet|regnen|regen|schnee|schneit|temperatur|grad|warm|kalt|sonnig|regenschirm)\b", t):
        day = 0
        for word, n in DAY_WORDS.items():
            if re.search(rf"\b{word}\b", t):
                day = n
        city = ""
        m = re.search(r"\bin ([a-zäöüß][\wäöüß\- ]*?)(?: heute| morgen| übermorgen| am wochenende|$)", t)
        if m:
            city = m.group(1).strip()
            city = re.sub(r"^(der|die|dem|den) ", "", city)
        return ("weather", {"day": day, "city": city})

    # --- Uhrzeit / Datum ---
    if re.search(r"(wie spät|uhrzeit|wieviel uhr|wie viel uhr)", t):
        return ("time", {})
    if re.search(r"(welcher tag|welches datum|der wievielte|welcher wochentag|datum)", t):
        return ("date", {})

    # --- Musik abspielen (viele Formulierungen, Kommas egal) ---
    query = music_query(t)
    if query is not None:
        if query == "":
            return ("music_ask", {})
        return ("play", {"query": query})

    if re.search(r"(was kannst du|hilfe|wie funktionierst du)", t):
        return ("help", {})
    if re.search(r"^(danke|dankeschön|vielen dank)", t):
        return ("thanks", {})
    return ("unknown", {"text": t})
