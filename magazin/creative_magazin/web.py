"""Internetseiten laden, RSS-/Atom-Feeds finden und auslesen."""

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.entities import name2codepoint
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

MAX_BYTES = 8 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0 CreativeMagazin/1.0"
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml",
              "application/feed+xml", "application/xml", "text/xml")
FEED_PATHS = ("/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml",
              "/rss/news.xml", "/news/rss", "/feeds/all.rss")

# Beliebte Seiten für den ersten Start. Der Feed-Hinweis wird zuerst probiert;
# klappt er nicht, sucht die App den Feed selbst auf der Startseite.
CATALOGUE = [
    dict(name="ComputerBase", home="https://www.computerbase.de/", feed="https://www.computerbase.de/rss/news.xml"),
    dict(name="Golem.de", home="https://www.golem.de/", feed="https://rss.golem.de/rss.php?feed=ATOM1.0"),
    dict(name="heise online", home="https://www.heise.de/", feed="https://www.heise.de/rss/heise-atom.xml"),
    dict(name="PC Games Hardware", home="https://www.pcgameshardware.de/", feed="https://www.pcgameshardware.de/feed.cfm"),
    dict(name="GameStar", home="https://www.gamestar.de/", feed="https://www.gamestar.de/news/rss/news.rss"),
    dict(name="GamePro", home="https://www.gamepro.de/", feed="https://www.gamepro.de/rss/gamepro.rss"),
    dict(name="Hardwareluxx", home="https://www.hardwareluxx.de/", feed="https://www.hardwareluxx.de/index.php/rss/feed/news.html"),
    dict(name="WinFuture", home="https://winfuture.de/", feed="https://static.winfuture.de/feeds/WinFuture-News-rss2.0.xml"),
    dict(name="t3n", home="https://t3n.de/", feed="https://t3n.de/rss.xml"),
    dict(name="Caschys Blog", home="https://stadt-bremerhaven.de/", feed="https://stadt-bremerhaven.de/feed/"),
    dict(name="Notebookcheck", home="https://www.notebookcheck.com/", feed=""),
    dict(name="CHIP", home="https://www.chip.de/", feed=""),
]


def web_url(url):
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def site_name(url):
    host = urlsplit(url).hostname or url
    return host[4:] if host.startswith("www.") else host


def fetch(url, timeout=15):
    """Lädt eine Adresse; liefert (Bytes, endgültige Adresse, Zeichensatz)."""
    if not web_url(url):
        raise ValueError("Bitte eine Internetadresse eingeben.")
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
    })
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Die Seite ist zu groß.")
        return data, response.geturl(), response.headers.get_content_charset()


def decode(data, charset=None):
    if not charset:
        match = re.search(rb"""<meta[^>]+charset=["']?([\w-]+)""", data[:4096], re.I)
        charset = match.group(1).decode("ascii", "ignore") if match else "utf-8"
    try:
        return data.decode(charset, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def item_id(source, key):
    return hashlib.sha256(f"{source}\n{key}".encode()).hexdigest()[:24]


# ---------------------------------------------------------------- Feeds lesen

def _local(tag):
    return tag.rpartition("}")[2] if isinstance(tag, str) else ""


def _entity(match):
    code = name2codepoint.get(match.group(1))
    return chr(code) if code else ""


def parse_xml(data):
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        # Viele Feeds benutzen HTML-Entitäten wie &nbsp;, die XML nicht kennt.
        text = decode(data).lstrip("﻿ \r\n\t")
        text = re.sub(r"^<\?xml[^>]*\?>", "", text)
        text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)([A-Za-z][A-Za-z0-9]*);", _entity, text)
        return ET.fromstring(text)


def is_feed(data):
    head = data[:2048].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        return False
    try:
        return _local(parse_xml(data).tag) in ("rss", "feed", "RDF")
    except ET.ParseError:
        return False


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def plain(markup, limit=0):
    text = re.sub(r"</?(?:p|div|br|li|ul|ol|h\d|tr|td|th|blockquote|figure|img)\b[^>]*>", " ", markup or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " …"
    return text


RUBRICS = ("Tests", "Reviews", "News", "Artikel")
_TEST = re.compile(r"\b(im test|test|tests|getestet|testbericht|benchmarks?|vergleichstest|praxistest)\b", re.I)
_REVIEW = re.compile(r"\b(review|reviews|kritik|wertung|angespielt|angezockt|hands[- ]on|ersteindruck)\b", re.I)
_ARTICLE = re.compile(r"\b(ratgeber|kaufberatung|kommentar|meinung|hintergrund|special|report|reportage|feature|"
                      r"kolumne|interview|analyse|guide|tipps|anleitung|essay|story)\b", re.I)


def rubric(title, categories=(), link=""):
    """Ordnet einen Artikel einer Rubrik zu: Tests, Reviews, News oder Artikel."""
    words = " ".join([title, " ".join(categories), urlsplit(link).path.replace("-", " ").replace("/", " ")])
    if _REVIEW.search(words):
        return "Reviews"
    if _TEST.search(words):
        return "Tests"
    if _ARTICLE.search(words):
        return "Artikel"
    return "News"


def _child(element, *names):
    for child in element:
        if _local(child.tag) in names:
            return child
    return None


def _text(element, *names):
    child = _child(element, *names)
    return (child.text or "").strip() if child is not None else ""


def _image_from_html(markup, base):
    match = re.search(r"""<img[^>]+?(?:data-src|src)=["']([^"']+)["']""", markup or "", re.I)
    if match and not match.group(1).startswith("data:"):
        return urljoin(base, html.unescape(match.group(1)))
    return ""


def parse_feed(data, url):
    """Liefert (Feed-Titel, Startseite, Einträge) eines RSS-, Atom- oder RDF-Feeds."""
    root = parse_xml(data)
    kind = _local(root.tag)
    if kind not in ("rss", "feed", "RDF"):
        raise ValueError("Unter dieser Adresse liegt kein RSS-Feed.")
    channel = _child(root, "channel") if kind != "feed" else root
    if channel is None:
        channel = root
    title = _text(channel, "title") or site_name(url)
    home = ""
    for link in channel:
        if _local(link.tag) == "link":
            href = link.get("href") or (link.text or "").strip()
            if href and link.get("rel", "alternate") == "alternate":
                home = urljoin(url, href)
                break
    entries = []
    for element in root.iter():
        if _local(element.tag) not in ("item", "entry"):
            continue
        link = ""
        for child in element:
            if _local(child.tag) != "link":
                continue
            href = child.get("href") or (child.text or "").strip()
            if href and child.get("rel", "alternate") == "alternate":
                link = urljoin(url, href)
                break
        guid = _text(element, "guid", "id")
        if not link and web_url(guid):
            link = guid
        if not web_url(link):
            continue
        summary = _text(element, "description", "summary")
        content = ""
        categories = []
        author = ""
        image = ""
        for child in element:
            name = _local(child.tag)
            if name in ("encoded", "content") and (child.text or "").strip():
                content = child.text.strip()
            elif name == "category":
                value = child.get("term") or (child.text or "").strip()
                if value:
                    categories.append(value)
            elif name in ("creator", "author") and not author:
                author = (_text(child, "name") or child.text or "").strip()
            elif name in ("content", "thumbnail") and child.get("url") and not image:
                if child.get("medium", "image") == "image" and not child.get("type", "image").startswith(("video", "audio")):
                    image = urljoin(url, child.get("url"))
            elif name == "enclosure" and child.get("type", "").startswith("image/") and not image:
                image = urljoin(url, child.get("url", ""))
        if not image:
            image = _image_from_html(content or summary, link)
        published = parse_date(_text(element, "pubDate", "published", "date", "issued", "updated", "modified"))
        heading = plain(_text(element, "title")) or "Ohne Titel"
        entries.append(dict(
            id=item_id(url, guid or link), title=heading, link=link,
            summary=plain(summary or content, 320), content=content,
            image=image if web_url(image) else "", author=plain(author),
            published=published, categories=categories,
            rubric=rubric(heading, categories, link),
        ))
    return title, home or f"https://{urlsplit(url).hostname}/", entries


# ---------------------------------------------------------------- Feeds finden

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.feeds = []
        self.title = ""
        self.site = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "alternate" in (attrs.get("rel") or "").lower().split():
            kind = (attrs.get("type") or "").lower()
            if attrs.get("href") and kind in FEED_TYPES:
                self.feeds.append(attrs["href"])
        elif tag == "meta" and attrs.get("property") == "og:site_name":
            self.site = attrs.get("content") or ""
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "head":
            raise StopIteration

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _feed_info(url):
    data, final, _ = fetch(url)
    title, home, entries = parse_feed(data, final)
    return dict(url=final, title=title, home=home, count=len(entries))


def _candidates(query):
    query = query.strip()
    for site in CATALOGUE:
        if query.lower() in (site["name"].lower(), site_name(site["home"])):
            return [site["feed"], site["home"]] if site["feed"] else [site["home"]]
    if re.match(r"^https?://", query, re.I):
        return [query]
    if "." in query and " " not in query:
        return [f"https://{query}"]
    slug = re.sub(r"[^a-z0-9-]", "", query.lower().replace(" ", ""))
    if not slug:
        raise ValueError("Bitte einen Seitennamen oder eine Adresse eingeben.")
    return [f"https://www.{slug}.de/", f"https://www.{slug}.com/"]


def discover(query):
    """Findet zu einem Namen, einer Adresse oder einem RSS-Link den passenden Feed."""
    errors = []
    for candidate in _candidates(query):
        if not candidate:
            continue
        try:
            data, final, charset = fetch(candidate)
        except Exception as exc:
            errors.append(str(exc))
            continue
        if is_feed(data):
            title, home, entries = parse_feed(data, final)
            return dict(url=final, title=title, home=home, count=len(entries))
        links = _Links()
        try:
            links.feed(decode(data, charset))
        except StopIteration:
            pass
        name = links.site.strip() or links.title.strip().split(" | ")[0].split(" - ")[0]
        tried = []
        for href in links.feeds + [urljoin(final, path) for path in FEED_PATHS]:
            href = urljoin(final, href)
            if href in tried:
                continue
            tried.append(href)
            try:
                info = _feed_info(href)
            except Exception:
                continue
            if info["count"]:
                if name and len(name) < 60:
                    info["title"] = name
                info["home"] = final
                return info
        errors.append(f"{site_name(final)} bietet keinen RSS-Feed an.")
    raise ValueError(errors[-1] if errors else "Keine passende Seite gefunden.")
