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


def web_url(url):
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def request(url):
    if not web_url(url):
        raise ValueError("Bitte eine HTTP- oder HTTPS-Adresse eingeben.")
    return urlopen(Request(url, headers={"User-Agent": "Creative Podcast/1.0"}), timeout=15)


def document(url):
    with request(url) as response:
        data = response.read(MAX_FEED_BYTES + 1)
        if len(data) > MAX_FEED_BYTES:
            raise ValueError("Die Antwort ist zu groß.")
        return data, response.geturl()


def search(term):
    query = urlencode(dict(term=term, media="podcast", entity="podcast", country="DE", limit=40))
    data, _ = document(f"https://itunes.apple.com/search?{query}")
    shows = {}
    for result in json.loads(data)["results"]:
        url = result.get("feedUrl") or ""
        if web_url(url):
            shows.setdefault(url, dict(url=url, title=result["collectionName"],
                                       author=result.get("artistName", "")))
    return list(shows.values())


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
            details = dict(show, title=channel.findtext("title") or show["title"])
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
                    date=item.findtext("pubDate") or "", show=details["title"],
                ))
                break
        next_page = channel.find(f"{ATOM}link[@rel='next']")
        href = next_page.get("href") if next_page is not None else None
        url = urljoin(base, href) if href else None
    return details, list(episodes.values())


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
