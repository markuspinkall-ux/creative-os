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
- `[iso]` in einer Merge-Commit-Nachricht baut zusätzlich Installations-ISOs.
- `[freigeben]` veröffentlicht nach erfolgreichem Abbildbau im stabilen Kanal.
  Erst nach den erforderlichen Tests verwenden. Ohne Markierung bleibt der
  Build im Testkanal. `Freigeben` übernimmt die letzte getestete Test-Version.

Vor jeder Freigabe in einer VM bzw. auf geeigneter Hardware prüfen:
Anmeldung, Sperren, falsches Passwort, Entsperren, Standby/Aufwachen,
Textkonsole, Updates sowie Rollback. Syntaxprüfungen ersetzen diesen Test nicht.
