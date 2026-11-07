"""Explicit article searches on German Wikipedia."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://de.wikipedia.org/w/api.php"
MAX_RESPONSE = 64 * 1024


def lookup(query):
    params = urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": query, "gsrnamespace": 0, "gsrlimit": 1,
        "prop": "extracts", "exintro": 1, "explaintext": 1, "exsentences": 2,
    })
    request = Request(f"{ENDPOINT}?{params}", headers={
        "User-Agent": "CreativeOS-Assistant/1.0 (https://github.com/markuspinkall-ux/creative-os)",
    })
    with urlopen(request, timeout=6) as response:
        payload = response.read(MAX_RESPONSE + 1)
    if len(payload) > MAX_RESPONSE:
        raise ValueError("Wikipedia-Antwort zu groß")
    data = json.loads(payload)
    if "error" in data:
        raise ValueError("Wikipedia hat die Suche abgelehnt")
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    title = page["title"]
    extract = " ".join(page.get("extract", "").split())
    if len(extract) > 420:
        extract = extract[:417].rsplit(" ", 1)[0] + " …"
    return title, extract, f"https://de.wikipedia.org/?curid={int(page['pageid'])}"
