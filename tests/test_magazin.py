"""Tests für Creative Magazin ohne Internet und ohne Qt: python3 -m unittest tests/test_magazin.py"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "magazin"))

from creative_magazin import extract, web  # noqa: E402
from creative_magazin.store import Store  # noqa: E402

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Hardware&nbsp;News</title><link>https://example.org/</link>
<item><title>Radeon RX 9070 im Test</title><link>https://example.org/test/rx-9070</link>
<guid>a1</guid><pubDate>Mon, 09 Nov 2026 10:00:00 +0100</pubDate>
<description>&lt;p&gt;Die neue Karte &lt;b&gt;überzeugt&lt;/b&gt;.&lt;/p&gt;</description>
<dc:creator>Max Muster</dc:creator><media:content url="https://example.org/a.jpg" medium="image"/>
<category>Grafikkarten</category></item>
<item><title>Treiber 25.11 erschienen</title><link>https://example.org/news/treiber</link>
<pubDate>Mon, 09 Nov 2026 09:00:00 +0100</pubDate>
<content:encoded><![CDATA[<p>Kurz.</p><img src="/b.png" width="800">]]></content:encoded></item>
</channel></rss>""".encode()

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom-Seite</title>
<link rel="self" href="https://example.com/atom.xml"/><link href="https://example.com/"/>
<entry><title>Kommentar: Warum Linux gewinnt</title><id>tag:1</id>
<link rel="alternate" href="https://example.com/kommentar"/><updated>2026-11-09T08:00:00Z</updated>
<author><name>Erika</name></author><summary>Eine Meinung.</summary></entry></feed>"""

PAGE = """<!doctype html><html><head><title>X</title>
<meta property="og:image" content="https://example.org/hero.jpg">
<meta property="og:site_name" content="Beispiel">
<script type="application/ld+json">{"@type":"NewsArticle","author":{"@type":"Person","name":"Max Muster"}}</script>
</head><body>
<nav><ul><li><a href="/">Start</a></li><li><a href="/news">News</a></li></ul></nav>
<div class="layout"><article class="article">
<header><h1>Radeon RX 9070 im Test</h1><p class="byline">Von Max</p></header>
<div class="article-content">
<p>Die neue Grafikkarte von AMD tritt gegen die Konkurrenz an und muss sich in vielen Spielen beweisen.</p>
<figure><img src="https://example.org/hero.jpg?w=800"><figcaption>Die Karte</figcaption></figure>
<h2>Leistung</h2>
<p>In WQHD liegt die Karte vorn &amp; bleibt dabei angenehm leise, selbst unter Volllast nach einer Stunde.</p>
<figure><picture><img data-src="/bilder/benchmark.png" width="900"></picture><figcaption>Benchmark</figcaption></figure>
<ul><li>Leise Lüfter im Leerlauf</li><li>Guter Preis für die Leistung</li></ul>
<div class="ad-box"><p>Anzeige: Kaufen Sie jetzt diese tolle Karte bei unserem Partner, sofort lieferbar!</p></div>
<blockquote>Die beste Karte des Jahres.</blockquote>
<table><tr><th>Spiel</th><th>FPS</th></tr><tr><td>Cyberpunk</td><td>98</td></tr></table>
<p>Fazit: Wer eine schnelle Karte für WQHD sucht, wird hier fündig und spart dabei noch Geld.<br>Zweite Zeile.</p>
</div></article>
<aside class="sidebar"><p>Beliebte Artikel aus der Seitenleiste, die nichts mit dem Test zu tun haben, gar nichts.</p></aside>
<div class="comments"><p>Kommentar eines Lesers, der sehr lang ist und eigentlich gar nicht in den Artikel gehört.</p></div>
</div><footer><p>Impressum</p></footer></body></html>"""


class Feeds(unittest.TestCase):
    def test_rss(self):
        title, home, entries = web.parse_feed(RSS, "https://example.org/feed")
        self.assertEqual(title, "Hardware\xa0News")
        self.assertEqual(home, "https://example.org/")
        first, second = entries
        self.assertEqual(first["rubric"], "Tests")
        self.assertEqual(first["author"], "Max Muster")
        self.assertEqual(first["image"], "https://example.org/a.jpg")
        self.assertEqual(first["summary"], "Die neue Karte überzeugt.")
        self.assertEqual(first["published"].hour, 9)
        self.assertEqual(second["rubric"], "News")
        self.assertEqual(second["image"], "https://example.org/b.png")
        self.assertTrue(web.is_feed(RSS))

    def test_atom(self):
        title, home, entries = web.parse_feed(ATOM, "https://example.com/atom.xml")
        self.assertEqual((title, home), ("Atom-Seite", "https://example.com/"))
        self.assertEqual(entries[0]["link"], "https://example.com/kommentar")
        self.assertEqual(entries[0]["author"], "Erika")
        self.assertEqual(entries[0]["rubric"], "Artikel")

    def test_rubrics(self):
        self.assertEqual(web.rubric("Angespielt: Neues Spiel"), "Reviews")
        self.assertEqual(web.rubric("Testament der Zeit"), "News")
        self.assertEqual(web.rubric("Monitore", link="https://x.de/tests/monitor-123"), "Tests")

    def test_html_is_no_feed(self):
        self.assertFalse(web.is_feed(PAGE.encode()))

    def test_candidates(self):
        self.assertEqual(web._candidates("golem.de")[1], "https://www.golem.de/")
        self.assertEqual(web._candidates("beispiel.de"), ["https://beispiel.de"])
        self.assertEqual(web._candidates("ComputerBase")[0], "https://www.computerbase.de/rss/news.xml")
        self.assertEqual(web._candidates("Mein Blog"), ["https://www.meinblog.de/", "https://www.meinblog.com/"])


class Extract(unittest.TestCase):
    def test_article(self):
        result = extract.extract(PAGE, "https://example.org/test/rx-9070", "Radeon RX 9070 im Test")
        texts = [block["text"] for block in result["blocks"]]
        kinds = [block["type"] for block in result["blocks"]]
        self.assertEqual(result["author"], "Max Muster")
        self.assertEqual(result["image"], "https://example.org/hero.jpg")
        self.assertTrue(texts[0].startswith("Die neue Grafikkarte"))
        self.assertIn("Leistung", texts)
        self.assertIn("In WQHD liegt die Karte vorn & bleibt dabei angenehm leise, selbst unter Volllast nach einer Stunde.", texts)
        self.assertNotIn("https://example.org/hero.jpg?w=800", [b["src"] for b in result["blocks"]])
        image = [b for b in result["blocks"] if b["type"] == "img"]
        self.assertEqual([(b["src"], b["text"]) for b in image], [("https://example.org/bilder/benchmark.png", "Benchmark")])
        self.assertIn("li", kinds)
        self.assertIn("quote", kinds)
        self.assertIn("Cyberpunk · 98", texts)
        joined = " ".join(texts)
        for junk in ("Anzeige", "Seitenleiste", "Leser", "Impressum", "Start", "Von Max"):
            self.assertNotIn(junk, joined)
        self.assertIn("Geld.\nZweite Zeile.", joined)
        self.assertTrue(result["short"])

    def test_div_text_without_paragraphs(self):
        markup = "<html><body><div id='main'>" + ("Ein langer Satz ohne Absatz. " * 40) + "</div></body></html>"
        result = extract.extract(markup, "https://example.org/", "")
        self.assertEqual(result["blocks"][0]["type"], "p")
        self.assertFalse(result["short"])

    def test_broken_html(self):
        extract.extract("<div><p>offen<span>und <b>kaputt</div></p></i>", "https://example.org/")


class StoreTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "m.sqlite")
            _, _, entries = web.parse_feed(RSS, "https://example.org/feed")
            store.add_source("https://example.org/feed", "Hardware", "https://example.org/")
            self.assertEqual(store.add_articles("https://example.org/feed", entries), 2)
            self.assertEqual(store.add_articles("https://example.org/feed", entries), 0)
            issues = store.issues()
            self.assertEqual(issues[0]["count"], 2)
            self.assertIn("November 2026", issues[0]["label"])
            articles = store.articles(issues[0]["date"])
            key = articles[0]["id"]
            store.set_rubric(key, "Artikel")
            store.add_articles("https://example.org/feed", entries)
            self.assertEqual(store.article(key)["rubric"], "Artikel")
            store.set_flag(key, "saved", True)
            store.remove_source("https://example.org/feed")
            self.assertEqual([a["id"] for a in store.articles("gemerkt")], [key])
            self.assertEqual(store.issues(), [])


if __name__ == "__main__":
    unittest.main()
