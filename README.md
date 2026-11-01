# Creative OS

Ein Betriebssystem auf Basis von **Fedora Atomic**, das sich anfühlt wie Windows –
im dunklen Graphit-Design, wie aus einem Guss, und so gebaut, dass man nichts kaputt machen kann.
Spiele laufen ab Werk (Steam + Proton fest eingebaut).

| Teil | Ordner |
|---|---|
| Taskleiste, Startmenü, Schnellzugriff, Kalender, Papierkorb, Schreibtisch, Sperrbildschirm | `shell/` |
| Dateimanager „Dateien“ | `files/` |
| Creative Player (Musik, Videos, IPTV) | `media/` |
| Systemsteuerung (Netzwerk, Bildschirme, Ton, Drucker, Mein Server, Darstellung, Updates, System) | `settings/` |
| Mein Server (Webseite im Heimnetz) | `server/` |
| Brave-Startseite und -Einstellungen | `browser/` |
| Willkommens-Assistent | `welcome/` |
| Aussehen aller Apps (Farben, Fensterrahmen, Symbole, aufgeräumtes Startmenü) | `theme/` |
| System-Abbild und Installations-ISO | `image/`, `.github/workflows/build.yml` |

## Installations-ISO bekommen

Das Abbild wird automatisch auf GitHub gebaut (Actions › „Creative OS bauen“).

1. **Actions** öffnen › „Creative OS bauen“ › **Run workflow** (Häkchen „Installations-ISO“ an).
2. Nach ca. 30–60 Minuten unten bei **Artifacts** die ISO herunterladen
   (`creative-os-nvidia-…` für NVIDIA-Grafik, `creative-os-amd-…` für AMD/Intel).
3. Einmalig: Unter **Packages › creative-os › Package settings** die Sichtbarkeit auf
   **Public** stellen – sonst bekommen installierte PCs keine Updates.

Installierte Systeme holen sich jede Nacht gebaute Updates selbst im Hintergrund; aktiv werden sie
beim nächsten Neustart. Im Bootmenü steht immer der vorherige Stand bereit.

## In einer VM testen (VirtualBox)

- Typ „Fedora (64-bit)“, **EFI aktivieren** (Ändern › System), 8 GB RAM, 4 CPUs, **80 GB** Festplatte,
  Grafik: VMSVGA mit 128 MB.
- ISO einlegen, starten, „Install Creative OS“ wählen, Festplatte und Benutzer festlegen.
- Für die VM die Variante **amd** nehmen (NVIDIA-Treiber braucht echte NVIDIA-Hardware).
