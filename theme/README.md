# Creative OS – Aussehen für alle Programme

- **Fensterrahmen:** Breeze mit Graphit-Farben (breezerc). Der SVG-Rahmen „Creative Graphit“ (KWin/Aurorae) liegt bei, ist aber abgeschaltet, weil bei SVG-Rahmen Nahtstellen sichtbar werden. Alt:: dunkle Titelleiste, runde obere Ecken, weicher Schatten,
  links das App-Symbol, rechts Minimieren · Maximieren · Schließen wie bei Windows 11 (Schließen wird rot).
  Neu erzeugen: `python3 tools/make_aurorae.py aurorae/CreativeGraphit`
- **Graphit-Farben + Arial** für Qt/KDE-Programme (`kdeglobals`, gilt nur in der Creative-Sitzung)
- **Graphit für GTK-Programme** wie Software (`gtk/`; die gtk.css wird beim Anmelden in die Benutzereinstellungen gelegt)
- **Aufgeräumtes Startmenü** (`apps/creative-apps-sync`): nur die nötigsten Apps, deutsche Namen, Creative-Symbole.
  Alles andere bleibt installiert, wird aber ausgeblendet. Später installierte Apps erscheinen normal.

Installieren: `sudo ./install.sh` (danach Creative OS neu starten)
