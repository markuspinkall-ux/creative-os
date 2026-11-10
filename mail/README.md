# Creative Mail

Nativer Gmail-Client für Creative OS. Unterstützt Posteingang, Gesendet, alle
E-Mails, Gmail-Suche, Lesen und Senden von Text-E-Mails. HTML-Nachrichten werden
als Text angezeigt. Dateianhänge lassen sich in dieser Version nicht öffnen oder
versenden.

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
