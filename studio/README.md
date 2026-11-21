# Studio

Aufnehmen und live streamen im Gibeon-Look – als Ersatz für OBS Studio, das unter Linux/Wayland oft hakt.

- **Mischpult:** Hauptbild (Bildschirm oder Fenster über das Wayland-Portal von KDE, Kamera oder
  Capture-Karte) plus Kamera-Einblendung in einer Ecke; Mikrofon, Desktop-Ton und eine weitere Tonquelle
  mit Pegel, Lautstärke und Stumm.
- **Ausgänge:** Aufnahme als MP4 (absturzsicher in Teilen geschrieben) oder MKV unter Videos › Studio;
  Stream zu Twitch, YouTube und/oder einem eigenen RTMP-Server – gleichzeitig möglich. Jeder Ausgang läuft
  in einer eigenen Pipeline: Bricht ein Stream ab, laufen Vorschau und Aufnahme weiter.
- **Kodierer:** NVIDIA NVENC bzw. VA-API, sonst x264/OpenH264; klappt die Grafikkarte nicht, nimmt Studio
  automatisch den Prozessor.
- **Konten:** Anmeldung bei Twitch und YouTube per Gerätecode (Passwort sieht Studio nie). Danach holt
  Studio den Stream-Schlüssel selbst, zeigt links den Chat und ändert Titel (und bei Twitch die Kategorie).

## Twitch und YouTube einrichten (einmalig, für alle Gibeon-PCs)

Die Anmeldung braucht eine App-Kennung pro Dienst. Sie steht in `studio/dienste.json`
(bzw. `~/.config/gibeon-studio/dienste.json` zum Ausprobieren):

```json
{"twitch_client_id": "…", "youtube_client_id": "…", "youtube_client_secret": "…"}
```

- **Twitch:** dev.twitch.tv/console → „Anwendung registrieren“ · Name „Gibeon Studio“ · OAuth-Weiterleitung
  `http://localhost` · Kategorie „Broadcaster Suite“ · **Clienttyp „Öffentlich“** → Client-ID kopieren.
- **YouTube:** console.cloud.google.com → neues Projekt → „YouTube Data API v3“ aktivieren → OAuth-Zustimmung
  (extern, Testnutzer eintragen) → Anmeldedaten → OAuth-Client-ID vom Typ **„Fernseher und Geräte mit
  eingeschränkter Eingabe“** → Client-ID und Clientschlüssel kopieren. Solange die App bei Google „im Test“ ist,
  können sich nur eingetragene Testnutzer anmelden (bis 100).

Ohne Kennungen funktioniert Studio trotzdem: Aufnehmen und Streamen an einen eigenen Server (z. B. mit dem
Stream-Schlüssel von Twitch/YouTube unter „Ziele › Eigener Server“).

Grundlagen: GStreamer (LGPL), PipeWire, xdg-desktop-portal, Qt/PySide6, Qt WebEngine (Chat).
