"""Holt den eigentlichen Artikeltext aus einer Webseite – ohne Menüs und Werbung.

Ergebnis sind einfache Blöcke (Überschrift, Absatz, Bild, Zitat, Aufzählung),
die die App als reinen Text darstellt. HTML der Seite wird nie ausgeführt.
"""

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "form", "button", "select",
        "textarea", "canvas", "video", "audio", "object", "nav", "aside", "footer", "dialog", "math"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
INLINE = {"a", "b", "strong", "em", "i", "u", "span", "small", "sup", "sub", "mark", "time",
          "abbr", "code", "cite", "q", "s", "del", "ins", "kbd", "var", "font", "label", "br", "bdi"}
BLOCK_STARTS = {"p", "div", "section", "article", "ul", "ol", "table", "blockquote", "figure",
                "h1", "h2", "h3", "h4", "h5", "h6", "pre", "header", "main"}
NEGATIVE = re.compile(
    r"comment|kommentar|footer|sidebar|related|teaser|newsletter|share|social|sharing|advert|"
    r"\bad\b|\bads\b|-ad-|promo|sponsor|cookie|consent|navigation|\bnav\b|menu|breadcrumb|"
    r"paywall|subscribe|abo-|banner|popup|modal|widget|outbrain|taboola|recommend|empfehlung|"
    r"author-box|byline|tags|meta-info|toolbar|pagination", re.I)
JUNK = re.compile(r"^(anzeige|werbung|mehr zum thema|lesen sie auch|auch interessant|zum artikel|"
                  r"weiterlesen|bild:|foto:|quelle:|\(bild|jetzt abonnieren)", re.I)
BAD_IMAGE = re.compile(r"pixel|tracking|spacer|blank\.|logo|avatar|icon|emoji|gravatar|1x1|\.svg(\?|$)", re.I)


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent

    def css(self):
        return f"{self.attrs.get('class', '')} {self.attrs.get('id', '')} {self.attrs.get('role', '')}"


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.current = self.root
        self.skipping = []
        self.meta = {}
        self.ld = []
        self._ld = None

    def handle_starttag(self, tag, attrs):
        attrs = {key: value or "" for key, value in attrs}
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
            if key and attrs.get("content"):
                self.meta.setdefault(key.lower(), attrs["content"].strip())
            return
        if self.skipping:
            if tag == self.skipping[-1] and tag not in VOID:
                self.skipping.append(tag)
            return
        if tag == "script" and "ld+json" in attrs.get("type", ""):
            self._ld = []
        if tag in SKIP or tag == "script":
            if tag not in VOID:
                self.skipping.append(tag)
            return
        if tag in BLOCK_STARTS and self.current.tag == "p":
            self.current = self.current.parent
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and tag != "meta":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skipping:
            if tag == self.skipping[-1]:
                self.skipping.pop()
                if tag == "script" and self._ld is not None:
                    self.ld.append("".join(self._ld))
                    self._ld = None
            return
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent

    def handle_data(self, data):
        if self.skipping:
            if self._ld is not None:
                self._ld.append(data)
            return
        if self.current.tag in ("head", "title"):
            return
        self.current.children.append(data)


def _space(text):
    return re.sub(r"[ \t\r\f\v ]+", " ", re.sub(r" *\n *", "\n", text)).strip()


def text_of(node):
    parts = []

    def walk(item):
        for child in item.children:
            if isinstance(child, str):
                parts.append(child.replace("\n", " "))
            elif child.tag == "br":
                parts.append("\n")
            elif child.tag in ("p", "li", "div", "h2", "h3", "h4", "tr"):
                parts.append(" ")
                walk(child)
                parts.append(" ")
            else:
                walk(child)
    walk(node)
    return _space("".join(parts))


def _negative(node):
    css = node.css()
    return bool(css.strip()) and bool(NEGATIVE.search(css)) and not re.search(r"article|content|body|text|story|post", node.attrs.get("class", "")[:30], re.I)


def _paragraph_text(node, cache):
    """Länge des Absatztexts unterhalb eines Knotens (Grundlage für die Auswahl)."""
    key = id(node)
    if key in cache:
        return cache[key]
    total = 0
    if not (node.parent is not None and _negative(node)):
        for child in node.children:
            if isinstance(child, str):
                continue
            if child.tag == "p":
                length = len(text_of(child))
                if length >= 30:
                    total += length
            elif child.tag not in VOID:
                total += _paragraph_text(child, cache)
    cache[key] = total
    return total


def find_body(root):
    """Engster Bereich der Seite, der fast den ganzen Absatztext enthält."""
    cache = {}
    node = root
    while True:
        here = _paragraph_text(node, cache)
        if here == 0:
            return node
        best = max((child for child in node.children if not isinstance(child, str)),
                   key=lambda child: _paragraph_text(child, cache), default=None)
        if best is None or _paragraph_text(best, cache) < here * 0.8:
            return node
        node = best


def _image_src(node, base):
    for key in ("data-src", "data-lazy-src", "data-original", "data-srcset", "srcset", "src"):
        value = node.attrs.get(key, "").strip()
        if not value or value.startswith("data:"):
            continue
        if "srcset" in key or "," in value and " " in value:
            value = value.split(",")[-1].strip().split(" ")[0]
        return urljoin(base, value)
    parent = node.parent
    if parent is not None and parent.tag == "picture":
        for sibling in parent.children:
            if not isinstance(sibling, str) and sibling.tag == "source" and sibling.attrs.get("srcset"):
                return urljoin(base, sibling.attrs["srcset"].split(",")[-1].strip().split(" ")[0])
    return ""


def _small(node):
    for key in ("width", "height"):
        value = re.match(r"\d+", node.attrs.get(key, ""))
        if value and int(value.group()) < 120:
            return True
    return False


class _Blocks:
    def __init__(self, base, title):
        self.base = base
        self.title = (title or "").strip().lower()
        self.blocks = []
        self.images = set()

    def add(self, kind, text="", src=""):
        if len(self.blocks) >= 400:
            return
        if kind == "img":
            key = urlsplit(src)._replace(query="", fragment="").geturl()
            if not src.startswith(("http://", "https://")) or key in self.images or BAD_IMAGE.search(src):
                return
            self.images.add(key)
            self.blocks.append(dict(type="img", text=text, src=src))
            return
        text = _space(text)
        if len(text) < 2 or text.lower() == self.title:
            return
        if len(text) < 60 and JUNK.search(text):
            return
        self.blocks.append(dict(type=kind, text=text, src=""))

    def image(self, node, caption=""):
        if _small(node):
            return
        src = _image_src(node, self.base)
        if src:
            self.add("img", caption, src)

    def images_in(self, node):
        for child in node.children:
            if isinstance(child, str):
                continue
            if child.tag == "img":
                self.image(child)
            elif child.tag not in VOID:
                self.images_in(child)

    def walk(self, node):
        buffer = []

        def flush():
            if buffer:
                self.add("p", "".join(buffer))
                buffer.clear()

        for child in node.children:
            if isinstance(child, str):
                buffer.append(child.replace("\n", " "))
                continue
            tag = child.tag
            if _negative(child) or tag in ("h1", "header", "hr", "link", "source"):
                continue
            if tag == "br":
                buffer.append("\n")
            elif tag == "img":
                flush()
                self.image(child)
            elif tag in INLINE:
                buffer.append(" " + text_of(child) + " ")
                self.images_in(child)
            else:
                flush()
                self.block(child)
        flush()

    def block(self, node):
        tag = node.tag
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            self.add("h", text_of(node))
        elif tag == "p":
            text = text_of(node)
            if text:
                self.add("p", text)
            self.images_in(node)
        elif tag == "blockquote":
            self.add("quote", text_of(node))
        elif tag in ("ul", "ol"):
            items = [child for child in node.children if not isinstance(child, str) and child.tag == "li"]
            linked = sum(len(text_of(a)) for item in items for a in item.children
                         if not isinstance(a, str) and a.tag == "a")
            total = sum(len(text_of(item)) for item in items) or 1
            if linked / total < 0.6:
                for item in items:
                    self.add("li", text_of(item))
        elif tag == "figure":
            caption = ""
            for child in node.children:
                if not isinstance(child, str) and child.tag == "figcaption":
                    caption = text_of(child)
            before = len(self.blocks)
            self.images_in(node)
            if caption and len(self.blocks) > before:
                self.blocks[-1]["text"] = caption
        elif tag == "table":
            for row in _rows(node):
                self.add("p", " · ".join(row))
        elif tag == "pre":
            self.add("p", text_of(node))
        elif tag not in VOID:
            self.walk(node)


def _rows(table):
    rows = []

    def walk(node):
        for child in node.children:
            if isinstance(child, str):
                continue
            if child.tag == "tr":
                cells = [text_of(cell) for cell in child.children
                         if not isinstance(cell, str) and cell.tag in ("td", "th")]
                cells = [cell for cell in cells if cell]
                if cells:
                    rows.append(cells)
            elif child.tag not in VOID:
                walk(child)
    walk(table)
    return rows[:60]


def _ld_author(scripts):
    for script in scripts:
        try:
            data = json.loads(script)
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            stack.extend(item.get("@graph", []) if isinstance(item.get("@graph"), list) else [])
            author = item.get("author")
            if isinstance(author, list):
                author = author[0] if author else None
            if isinstance(author, dict) and author.get("name"):
                return str(author["name"])
            if isinstance(author, str) and author:
                return author
    return ""


def extract(markup, url, title=""):
    """Zerlegt eine Artikelseite in Blöcke; gibt zusätzlich Autor, Titelbild und Seitennamen zurück."""
    tree = _Tree()
    tree.feed(markup)
    tree.close()
    meta = tree.meta
    body = find_body(tree.root)
    blocks = _Blocks(url, title or meta.get("og:title", ""))
    hero = meta.get("og:image") or meta.get("twitter:image") or ""
    hero = urljoin(url, hero) if hero else ""
    if hero:
        blocks.images.add(urlsplit(hero)._replace(query="", fragment="").geturl())
    blocks.walk(body)
    words = sum(len(block["text"]) for block in blocks.blocks if block["type"] != "img")
    author = meta.get("author") or meta.get("article:author") or _ld_author(tree.ld)
    if author.startswith("http"):
        author = _ld_author(tree.ld)
    return dict(
        blocks=blocks.blocks,
        image=hero,
        author=author.strip(),
        site=meta.get("og:site_name", ""),
        short=words < 600,
    )
