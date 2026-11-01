# Creative OS – System-Abbild

Creative OS ist ein **Fedora-Atomic**-System:

- **Schreibgeschützt:** Systemdateien lassen sich nicht versehentlich ändern
  oder löschen. Deine eigenen Dateien, Einstellungen und Apps liegen
  getrennt davon und bleiben bei jedem Update erhalten.
- **Updates nur als Ganzes:** Ein Update klappt komplett oder gar nicht.
  Es wird im Hintergrund geladen und beim nächsten Neustart aktiv.
- **Immer ein Rückweg:** Im Bootmenü steht der vorherige Stand bereit.
- **Fest eingebaut** und nicht entfernbar: Steam (mit Proton), Brave,
  alle Codecs, GameMode, die Creative Shell – und bei der NVIDIA-Variante
  der NVIDIA-Treiber.

## Bauen (auf Fedora, z. B. in der VM)

```sh
sudo dnf install -y podman
./image/build.sh          # NVIDIA-Variante
./image/build.sh amd      # AMD/Intel-Variante
```

Das dauert beim ersten Mal 20–40 Minuten und braucht rund 30 GB freien
Platz. Ergebnis: `output/bootiso/install.iso`.

## Noch offen

- **Update-Quelle:** GitHub Actions baut das Abbild jede Nacht und legt es in
  der GitHub-Registry ab (`.github/workflows/build.yml`) – das Paket muss dort
  einmal auf „Public“ gestellt werden.
- **Secure Boot mit NVIDIA:** Der Treiber muss signiert werden, sonst bei
  aktivem Secure Boot im BIOS Secure Boot ausschalten.
- **Steam Play für alle Spiele** ab Werk voreinstellen.
- Der NVIDIA-Teil und der Brave-Einbau sind noch nicht getestet.
