# Mein Server

Eine eigene Webseite im Heimnetz – eingeschaltet mit einem Schalter in der Systemsteuerung.

- Webserver: Caddy, mit PHP (php-fpm). Kein Datenbank- und kein Kontosystem.
- Speicherort: eine Zusatz-Festplatte (wird dauerhaft eingebunden, **nie formatiert**) oder ein
  geschützter Ordner auf dem System-Laufwerk (`/var/srv/mein-server`).
- Die Webseite liegt im Ordner `Mein Server/Webseite` – einfach Dateien hineinlegen.
- Erreichbar nur im Heimnetz: `http://<gerätename>.local` oder die IP-Adresse.
- Ausschalten stoppt den Dienst und schließt die Firewall wieder; die Dateien bleiben.

Technik: `creative-server-helper` (root, über pkexec/polkit), Dienst `creative-server.service`,
Einstellungen unter `/var/lib/creative-server/`.
