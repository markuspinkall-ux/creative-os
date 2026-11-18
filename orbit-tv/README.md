# Orbit TV

Fire-TV-App für deutsches Fernsehen.

- **Öffentlich-rechtliche Sender** (ARD, ZDF, Dritte, arte, 3sat, phoenix, KiKA, …) laufen direkt in Orbit TV über ihre offiziellen, freien Livestreams. Die Stream-Adressen stammen aus [Zapp](https://github.com/mediathekview/zapp) (MediathekView, MIT-Lizenz) und werden beim Start über die Zapp-Schnittstelle aktualisiert; dort kommt auch „Jetzt läuft“ her.
- **ProSieben, Sat.1, Kabel Eins & Co.** öffnen die offizielle **Joyn**-App, **RTL, VOX, n-tv & Co.** die offizielle **RTL+**-App – angemeldet mit deinem eigenen Konto. Deren Streams sind kopiergeschützt und laufen nur in den eigenen Apps.

## Bedienung

| Taste | im Bild | in der Senderliste |
|---|---|---|
| OK / ◀ / ▶ / ☰ | Senderliste öffnen | Sender ansehen (lange drücken: Optionen) |
| ▲ ▼ / P+ P− | Sender umschalten | in der Liste blättern |
| ◀ ▶ | – | Gruppe wechseln: Alle, Favoriten, ARD, ZDF, Dritte, Joyn, RTL+, Ausgeblendet |
| ☰ | – | Favorit, nach oben/unten schieben, ausblenden |
| 0–9 | Senderplatz direkt wählen | |
| Zurück | zweimal: beenden | Liste schließen |

## Installieren (Fire TV)

1. Auf dem Fire TV unter *Einstellungen → Mein Fire TV → Entwickleroptionen* „Apps unbekannter Herkunft“ für **Downloader** erlauben.
2. App **Downloader** aus dem Amazon Appstore installieren und öffnen.
3. Adresse eingeben: `https://github.com/markuspinkall-ux/creative-os/releases/download/orbit-tv/OrbitTV.apk`
4. Installieren. Für ein Update dasselbe noch einmal.

Gebaut wird automatisch mit GitHub Actions (`.github/workflows/orbit-tv.yml`).
