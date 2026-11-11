# Creative Mail

E-Mail-Programm für Creative OS im Graphit-Look (IMAP/SMTP):

- drei Spalten: Ordner und eigene Labels mit Ungelesen-Zählern, Nachrichtenliste
  mit Absender-Kürzel, Datum, Vorschau und Stern, Lesebereich
- echte HTML-Darstellung (Qt WebEngine, ohne JavaScript); Bilder aus dem Netz
  sind zum Schutz vor Tracking gesperrt, bis man „Bilder laden“ wählt
- Anhänge speichern, eingebettete Bilder, Antworten, Allen antworten,
  Weiterleiten (mit Anhängen), Archivieren, Löschen, (un)gelesen, markieren
- Verfassen mit Cc/Bcc, Formatierung (fett, kursiv, Liste, Link), Anhängen bis
  25 MB und Signatur; Gmail-Suche, automatisches Nachladen beim Blättern,
  alle zwei Minuten neue Mails
- Tastenkürzel: Strg+N neu, Strg+R antworten, Strg+Umschalt+R allen,
  Strg+Umschalt+F weiterleiten, E archivieren, Entf löschen, S markieren,
  U ungelesen, F5 aktualisieren, Strg+Eingabe s## Konto anmelden

**E-Mail-Konto anmelden** wählen, Adresse und Passwort eingeben – den Anbieter erkennt
Creative Mail an der Adresse und trägt die Server selbst ein:

| Anbieter | Hinweis |
|---|---|
| Gmail | App-Passwort nötig (Google-Konto → Sicherheit → Bestätigung in zwei Schritten → App-Passwörter) |
| GMX, WEB.DE | IMAP-Zugriff einmalig in den Einstellungen des Postfachs erlauben |
| T-Online | eigenes E-Mail-Passwort für Mailprogramme anlegen |
| Yahoo, AOL, iCloud | App-Passwort bzw. app-spezifisches Passwort |
| freenet, IONOS/1&1, Posteo, mailbox.org | normales Passwort |
| Andere | Server unter „Servereinstellungen anzeigen“ von Hand eintragen |
| Outlook/Hotmail | geht nicht: Microsoft erlaubt seit September 2024 keine Anmeldung mit Passwort mehr |

Das Passwort liegt im System-Schlüsselbund (Secret Service), die Serverdaten in den
Einstellungen von Creative Mail. Gesendete E-Mails landen im Ordner „Gesendet“ des Postfachs.
