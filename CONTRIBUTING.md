# Gemeinsame Entwicklung mit Claude und Codex

Alle Installationen verwenden dieselben stabilen Quellen:
`ghcr.io/markuspinkall-ux/creative-os:amd` bzw. `:nvidia`.
Die ISO-Herkunft ändert daran nichts. Änderungen gehören in dieses Repository.

- Für jede Aufgabe einen eigenen Branch vom aktuellen `main` erstellen.
- Änderungen per Pull Request zusammenführen. Vor dem Merge den aktuellen
  Stand berücksichtigen und Konflikte lösen. Keine Force-Pushes auf `main`.
- Keine App-Installationen, Tokens, Repository-Berechtigungen oder Secrets
  des anderen Assistenten entfernen oder austauschen.
- Builds und Freigaben werden durch dieselbe Actions-Concurrency-Gruppe
  serialisiert. Ein überholter Build darf keine Registry-Tags veröffentlichen.
- Actions → „Installations-ISO erstellen“ baut Netinstall-ISOs aus dem Stable-Kanal oder Offline-ISOs aus einer veröffentlichten Build-ID.
- `[freigeben]` veröffentlicht nach erfolgreichem Abbildbau im stabilen Kanal.
  Erst nach den erforderlichen Tests verwenden. Ohne Markierung bleibt der
  Build im Testkanal. `Freigeben` übernimmt die letzte getestete Test-Version.

Vor jeder Freigabe in einer VM bzw. auf geeigneter Hardware prüfen:
Anmeldung, Sperren, falsches Passwort, Entsperren, Standby/Aufwachen,
Textkonsole, Updates sowie Rollback. Syntaxprüfungen ersetzen diesen Test nicht.

### Funktionsupdates und Systembuilds

Änderungen an Creative Art, Writer, Podcast, der Systemsteuerung oder der
Sichtbarkeitsliste des Startmenüs können auf der letzten vollständigen
Systembasis gebaut werden. Der Workflow prüft alle Änderungen seit dieser
Basis und fällt bei anderen Dateien auf einen vollständigen Build zurück.
Neue Laufzeitabhängigkeiten gehören in den regulären Containerfile. Der
Nachtlauf und die manuelle Option „Vollständigen Systembuild erzwingen“
erneuern die Systembasis für AMD und NVIDIA.

In der Actions-Zusammenfassung steht die Größe der neuen komprimierten
Schichten gegenüber dem vorherigen Test- und Stable-Abbild.
