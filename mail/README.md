# Creative Mail

Nativer Gmail-Client für Creative OS im Graphit-Look:

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
  U ungelesen, F5 aktualisieren, Strg+Eingabe senden

## Google-Konto verbinden

Für einen privaten Test in der Google Cloud Console ein Projekt anlegen,
die Gmail API aktivieren und unter Google Auth Platform einen OAuth-Client
vom Typ **Desktop-App** erstellen. Bei einer externen App im Status **Testing**
die eigene Gmail-Adresse als Testnutzer hinzufügen. Die JSON-Datei des
Desktop-Clients herunterladen. Creative Mail öffnen, **Mit Google anmelden**
wählen und die Datei auswählen. Die Anmeldung und Freigabe erfolgen im
Standardbrowser. Creative Mail liest danach die Kontoadresse aus Gmail aus.
Es braucht keine IMAP- oder SMTP-Einstellungen.

Die OAuth-Datei am gewählten Ort behalten. Das Aktualisierungstoken liegt im
System-Schlüsselbund. Die Testfreigabe kann nach sieben Tagen ablaufen. Für
eine öffentliche Auslieferung mit Anmeldung ab Werk benötigt Creative OS
einen eigenen für den Gmail-Zugriff freigegebenen Desktop-OAuth-Client.
Ein vorhandener System-Client unter
`/usr/share/creative-mail/google-oauth.json` wird automatisch verwendet.

[Google-Dokumentation zu Desktop-OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
und [Gmail-Berechtigungen](https://developers.google.com/workspace/gmail/api/auth/scopes).
