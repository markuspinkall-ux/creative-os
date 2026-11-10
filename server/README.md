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

## Server-Modus

Ein/Aus-Menü › **Server-Modus** (erscheint, sobald Mein Server eingeschaltet ist):

- Alle Programme werden geschlossen, die Sitzung endet. Mein Server (und DuckDNS) laufen weiter.
- Bereitschaft, Ruhezustand, Deckel und Standby-Taste werden blockiert; Energieprofil „Energiesparen“;
  Bluetooth, Drucker und Modem pausieren (nur was vorher lief, startet danach wieder).
- Der Anmeldebildschirm zeigt die Server-Maske: Status, Heimnetz-/IP-/Internet-Adresse und seit wann.
  Nach 2 Minuten ohne Eingabe wird abgedunkelt.
- **Zurück zum normalen Modus** öffnet das Passwortfeld; die Anmeldung beendet den Server-Modus.
- Der Modus übersteht einen Neustart (Dienst `creative-servermode.service`).

Technik: `creative-servermode` (root, über pkexec ohne Passwort für die aktive Sitzung),
Status für die Maske in `/var/lib/creative-servermode/state.json`.

Technik: `creative-server-helper` (root, über pkexec/polkit), Dienst `creative-server.service`,
Einstellungen unter `/var/lib/creative-server/`.
