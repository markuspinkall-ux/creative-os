# Regionen-Sammelstelle einrichten (einmalig, ca. 5 Minuten, kostenlos)

Gibeon OS meldet – nur wenn der Nutzer zustimmt – einmal im Monat sein **Land** (z. B. „DE“).
Diese kleine Sammelstelle zählt mit. Gespeichert werden nur Zähler je Land: keine IP, keine Kennung.

## 1. Worker anlegen
1. Auf <https://dash.cloudflare.com/sign-up> kostenlos registrieren.
2. Links **Workers & Pages** → **Erstellen** → **Worker erstellen** → Name `gibeon-regionen` → **Bereitstellen**.
3. **Code bearbeiten** → alles löschen → den Inhalt von `worker.js` einfügen → **Bereitstellen**.

## 2. Speicher (KV) verbinden
1. Links **Speicher und Datenbanken** → **KV** → **Namespace erstellen** → Name `gibeon-regionen`.
2. Zurück zum Worker → **Einstellungen** → **Bindungen** → **Bindung hinzufügen** → **KV-Namespace**
   → Variablenname `ZAHLEN`, Namespace `gibeon-regionen` → Speichern.

## 3. Schlüssel fürs Widget
Worker → **Einstellungen** → **Variablen und Geheimnisse** → **Hinzufügen** → Typ **Geheimnis**,
Name `SCHLUESSEL`, Wert: ein langes Zufallswort (z. B. aus dem Terminal: `openssl rand -hex 24`).

## 4. Adresse an Claude geben
Die Adresse steht oben beim Worker, z. B. `https://gibeon-regionen.DEINNAME.workers.dev`.
Die kommt in `image/regionen.json` (dann melden alle Gibeon-Rechner mit Zustimmung dorthin).

## 5. Widget verbinden
Im Terminal:

    gibeon-entwickler regionen https://gibeon-regionen.DEINNAME.workers.dev DEIN-SCHLUESSEL

Danach zeigt das Entwickler-Widget die Länder.
