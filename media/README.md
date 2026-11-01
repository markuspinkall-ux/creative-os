# Creative Player

Musik, Videos und Fernsehen (IPTV) für Creative OS – im Graphit-Look.

- **Musik:** liest den Ordner „Musik“ mit Titel, Künstler, Album und Dauer.
- **YouTube Music:** die Top 10 aus Deutschland, Suche nach Liedern und Künstlern, ein Klick spielt direkt im Player ab (ohne Browser).
  Suche, Zufall, Wiederholen, Fortschritt, Lautstärke.
- **Videos:** liest den Ordner „Videos“. Doppelklick aufs Bild = Vollbild.
- **IPTV** (wie Team Eleven Media Player 1.4.0): voreingestellte deutsche
  Senderliste, Suche, Kategorien, Zurück/Weiter oder Bild auf/ab zum
  Senderwechsel, Doppelklick = randloses Vollbild, Esc beendet es,
  eigene M3U-Quelle eintragbar, Aktualisieren.
- Standardprogramm für Musik- und Videodateien (Doppelklick im Dateimanager).
- Tasten: Leertaste = Pause, F11 = Vollbild, Strg+←/→ = vorheriger/nächster
  Titel bzw. Sender.

Abgespielt wird über Qt Multimedia mit FFmpeg – mit Hardware-Beschleunigung.

## Testen

```sh
sudo dnf install python3-pyside6 qt6-qtmultimedia qt6-qtsvg python3-mutagen
./run-dev.sh
```

Der Ordner `shell` (Creative Shell) muss daneben liegen – von dort kommt das
gemeinsame Design.

## Noch offen

- Medientasten der Tastatur (MPRIS) und Anzeige im Schnellzugriff
- Playlisten
