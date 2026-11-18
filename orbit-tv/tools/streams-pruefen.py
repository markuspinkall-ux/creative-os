"""Prüft, welche Sender aus kandidaten.json heute noch senden (läuft in CI).

Ausgabe: lebend.json mit allen Einträgen, die einen abspielbaren Stream liefern.
Playlists (.m3u/.pls/.asx) werden aufgelöst; HLS muss eine gültige #EXTM3U liefern.
"""
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 9; AFTMM) OrbitTV/1.0"}


def get(url, n=4096):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.read(n)


def resolve(url, depth=0):
    """Gibt die direkte Stream-Adresse zurück oder None."""
    if depth > 2:
        return None
    try:
        final, ctype, data = get(url)
    except Exception as e:  # noqa: BLE001
        return None
    text = data.decode("utf-8", "replace")
    low = url.lower()
    if text.lstrip().startswith("#EXTM3U") and ("#EXT-X-" in text):
        return final                                   # HLS
    if low.endswith((".m3u", ".pls", ".asx", ".xspf")) or "audio/x-mpegurl" in ctype or "scpls" in ctype:
        m = re.search(r"(https?://[^\s\"'<>]+)", text)
        return resolve(m.group(1), depth + 1) if m else None
    if ctype.startswith(("audio/", "video/")) or "ogg" in ctype or "mpeg" in ctype or "aac" in ctype:
        return final
    return None


def main():
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    alive = []
    for e in data:
        url = resolve(e["url"])
        print(("OK   " if url else "tot  ") + e["name"] + "  " + (url or e["url"]), flush=True)
        if url:
            alive.append({**e, "url": url})
    json.dump(alive, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(alive)} von {len(data)} erreichbar")


if __name__ == "__main__":
    main()
