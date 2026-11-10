# Mein Server

Eine eigene Webseite im Heimnetz – eingeschaltet mit einem Schalter in der Systemsteuerung.

- Webserver: Caddy, mit PHP (php-fpm). Kein Datenbank- und kein Kontosystem.
- Speicherort: eine Zusatz-Festplatte (wird dauerhaft eingebunden, **nie formatiert**) oder ein
  geschützter Ordner auf dem System-Laufwerk (`/var/srv/mein-server`).
- Die Webseite liegt im Ordner `Mein Server/Webseite` – einfach Dateien hineinlegen.
- Erreichbar nur im Heimnetz: `http://<gerätename>.local` oder die IP-Adresse.
- Optional im Internet erreichbar über DuckDNS (Adresse wird alle 5 Minuten aktualisiert).
- „Verbindung prüfen“ zeigt Heimnetz-IP, öffentliche IPv4/IPv6 und wohin DuckDNS zeigt, und meldet
  typische Fehler: veraltete DuckDNS-IP, Aktualisierung aus, Port 443 in der Firewall zu, CGNAT.
  „Jetzt aktualisieren“ setzt DuckDNS sofort neu und repariert Aktualisierung und Firewall.
- Ausschalten stoppt den Dienst und schließt die Firewall wieder; die Dateien bleiben.

Technik: `creative-server-helper` (root, über pkexec/polkit), Dienst `creative-server.service`,
Einstellungen unter `/var/lib/creative-server/`.
