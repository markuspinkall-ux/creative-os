# Brave im Creative-Look

- **Startseite** (`startpage/`): Uhr, Begrüßung, Suche (Brave Search), Kacheln zum Anheften
  (Claude, ChatGPT, YouTube, Twitch …) – „Kacheln bearbeiten“ zum Entfernen/Hinzufügen.
  Liegt unter `/usr/share/creative-os/startpage/` und ist Start- und Neuer-Tab-Seite.
- **Richtlinien** (`/etc/brave/policies/managed/creative-os.json`): Graphit-Farbe (#1C2029),
  Startseite, kein „Als Standardbrowser festlegen“-Hinweis, Rewards/Wallet/VPN/KI-Chat/Tor/News aus.
- Firefox (nur Notlösung, solange Brave fehlt): dieselbe Startseite.

## YouTube auf dem Desktop ansehen

In Brave einmal `brave://extensions` öffnen, den Entwicklermodus einschalten
und über „Entpackte Erweiterung laden“ den Ordner
`/usr/share/creative-os/brave-extensions/youtube-desktop-video` auswählen.
Bei einem bereits geöffneten YouTube-Tab die Seite neu laden.

Auf einer YouTube-Videoseite erscheint „Auf Desktop ansehen“. Der Knopf
öffnet das laufende Video an seiner aktuellen Position in Braves
verschiebbarem Bild-in-Bild-Fenster. Der YouTube-Tab bleibt für die Wiedergabe
geöffnet.
