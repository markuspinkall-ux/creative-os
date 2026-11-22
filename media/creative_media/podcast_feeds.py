"""Public podcast catalogue, RSS playlists and audio downloads."""

import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

MAX_FEED_BYTES = 16 * 1024 * 1024
ATOM = "{http://www.w3.org/2005/Atom}"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def web_url(url):
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def request(url):
    if not web_url(url):
        raise ValueError("Bitte eine HTTP- oder HTTPS-Adresse eingeben.")
    return urlopen(Request(url, headers={"User-Agent": "Podcast/1.0"}), timeout=15)


def document(url):
    with request(url) as response:
        data = response.read(MAX_FEED_BYTES + 1)
        if len(data) > MAX_FEED_BYTES:
            raise ValueError("Die Antwort ist zu groß.")
        return data, response.geturl()


def _show(result):
    url = result.get("feedUrl") or ""
    if not web_url(url):
        return None
    art = result.get("artworkUrl600") or result.get("artworkUrl100") or ""
    return dict(url=url, title=result.get("collectionName") or result.get("trackName") or "Podcast",
                author=result.get("artistName", ""), image=art if web_url(art) else "")


def search(term):
    """Podcasts suchen (Apple-Podcast-Verzeichnis, frei zugänglich)."""
    query = urlencode(dict(term=term, media="podcast", entity="podcast", country="DE", limit=50))
    data, _ = document(f"https://itunes.apple.com/search?{query}")
    shows = {}
    for result in json.loads(data).get("results", []):
        show = _show(result)
        if show:
            shows.setdefault(show["url"], show)
    return list(shows.values())


def top(country="de", limit=40):
    """Beliebte Podcasts (Charts) – als Kacheln beim Öffnen."""
    data, _ = document(f"https://rss.applemarketingtools.com/api/v2/{country}/podcasts/top/{limit}/podcasts.json")
    ids = [r.get("id") for r in json.loads(data).get("feed", {}).get("results", []) if r.get("id")]
    if not ids:
        return []
    data, _ = document("https://itunes.apple.com/lookup?" + urlencode(dict(id=",".join(ids), entity="podcast",
                                                                            country=country.upper())))
    found = {}
    for result in json.loads(data).get("results", []):
        show = _show(result)
        if show:
            found[str(result.get("collectionId"))] = show
    return [found[i] for i in ids if i in found]


def _image(node):
    if node is None:
        return ""
    it = node.find(f"{ITUNES}image")
    if it is not None and web_url(it.get("href") or ""):
        return it.get("href")
    url = node.findtext("image/url") or ""
    return url if web_url(url) else ""


def playlist(show):
    url = show["url"]
    visited = set()
    episodes = {}
    details = show
    while url and url not in visited:
        if len(visited) >= 20:
            raise ValueError("Der Feed enthält mehr als 20 Seiten.")
        visited.add(url)
        data, base = document(url)
        root = ET.fromstring(data)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("Diese Adresse liefert keinen Podcast-RSS-Feed.")
        if len(visited) == 1:
            details = dict(show, title=channel.findtext("title") or show.get("title") or "Podcast",
                           author=show.get("author") or channel.findtext(f"{ITUNES}author") or "",
                           image=show.get("image") or _image(channel))
        for item in channel.findall("item"):
            for enclosure in item.findall("enclosure"):
                href = enclosure.get("url")
                if not href:
                    continue
                media = urljoin(base, href)
                mime = enclosure.get("type", "").partition(";")[0].strip().lower()
                if not web_url(media) or mime.startswith(("image/", "text/")) or mime == "application/pdf":
                    continue
                guid = item.findtext("guid") or media
                key = hashlib.sha256(f"{show['url']}\n{guid}".encode()).hexdigest()
                episodes.setdefault(key, dict(
                    key=key, url=media, mime=mime, title=item.findtext("title") or "Unbenannte Folge",
                    date=_date(item.findtext("pubDate") or ""), show=details["title"],
                    image=_image(item) or details.get("image", ""),
                ))
                break
        next_page = channel.find(f"{ATOM}link[@rel='next']")
        href = next_page.get("href") if next_page is not None else None
        url = urljoin(base, href) if href else None
    return details, list(episodes.values())


def _date(text):
    """„Tue, 18 Nov 2026 06:00:00 +0000“ → „18.11.2026“"""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(text).strftime("%d.%m.%Y")
    except (TypeError, ValueError, IndexError):
        return text


def download(episode, directory):
    directory.mkdir(parents=True, exist_ok=True)
    extension = Path(urlsplit(episode["url"]).path).suffix.lower()
    if extension not in (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac", ".mp4"):
        extension = mimetypes.guess_extension(episode["mime"]) or ".audio"
    destination = directory / (episode["key"] + extension)
    with request(episode["url"]) as response:
        content_type = response.headers.get_content_type()
        if content_type.startswith(("text/", "image/")):
            raise ValueError("Der Server hat keine Audiodatei geliefert.")
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as output:
            partial = Path(output.name)
            try:
                shutil.copyfileobj(response, output)
                size = output.tell()
                expected = response.headers.get("Content-Length")
                if not size or (expected and size != int(expected)):
                    raise ValueError("Der Download ist unvollständig.")
                output.close()
                os.replace(partial, destination)
            finally:
                partial.unlink(missing_ok=True)
    return dict(episode, file=str(destination))
