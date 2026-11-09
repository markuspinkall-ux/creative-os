# Creative Magazin

Liest Tests, Reviews, News und Artikel der Lieblingsseiten wie eine Zeitschrift.

- **Quellen:** Name (z. B. „ComputerBase“), Adresse („golem.de“) oder RSS-Link eingeben –
  der Feed wird auf der Seite gesucht (`web.discover`). Eigene Feed-Verwaltung, getrennt von Creative Podcast.
- **Tägliche Ausgabe:** Jeder Artikel gehört zur Ausgabe seines Erscheinungstags. Abruf beim Start
  und alle 30 Minuten, solange die App offen ist (F5 = sofort). Archiv: 60 Tage, Gemerktes bleibt.
- **Heft:** Titelseite, Inhaltsverzeichnis, je Rubrik Seiten mit vier Artikeln; Doppelseiten ab
  1100 px Breite. Blättern mit Pfeiltasten, Bild auf/ab, Leertaste, Mausrad oder Wischen.
  Rechtsklick auf einen Artikel: Merken, Original öffnen, Rubrik korrigieren.
- **Lesen:** Volltext aus dem Feed oder von der Artikelseite (`extract.py`, nur Standardbibliothek,
  HTML wird nie ausgeführt, nur als Text dargestellt). Unter jedem Artikel steht die Quelle
  (Seite, Autor, Datum, Link, „Original öffnen“). Bei Bezahlschranken: Hinweis + Original.
- **Daten:** `~/.local/share/Creative OS/Creative Magazin/magazin.sqlite`

Tests ohne Internet und ohne Qt: `python3 -m unittest tests/test_magazin.py`
Selbsttest mit Oberfläche (beim Bauen): `creative-magazin --selftest` – scheitert bei jeder QML-Warnung.
