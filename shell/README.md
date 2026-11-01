# Creative Shell

Taskleiste, Startmenü und Schnellzugriff von **Creative OS**, im Graphit-Design.

## Was schon drin ist

- **Taskleiste auf jedem Monitor**, schwebend, links ausgerichtet:
  Startmenü (Rakete) · Dateien · Browser · Terminal.
  Werden Monitore an- oder abgesteckt, passt sich alles automatisch an.
- **Startmenü** im Stil von Windows 11: Suche oben, alle Apps alphabetisch
  mit Buchstaben-Überschriften. Lostippen sucht sofort, Enter startet,
  Pfeiltasten wählen aus. Unten: Benutzer, Sperren, Ein/Aus-Menü.
  Neu installierte Apps (auch Flatpak) erscheinen von selbst.
- **Tray** mit Helligkeit, Drucker, WLAN/Kabel und Uhr. Ein Klick öffnet den
  **Schnellzugriff**:
  - WLAN ein/aus, Netzliste, Verbinden mit Passworteingabe
  - Helligkeit **für jeden Monitor einzeln** – Laptop-Display über
    brightnessctl, externe Monitore über DDC/CI (ddcutil)
  - Druckerstatus mit Auftragszahl, Knopf zu den Druckereinstellungen
- **Absturzsicher**: Stürzt die Shell ab, startet sie in einer Sekunde neu.
  Offene Programme laufen weiter.

Alle Texte und Symbole in Arial und einheitlichem Weiß-Blau (`#dce6ff`),
Akzent `#8fb3ff`, Flamme `#ffb07a`. Alle Farben stehen in
`creative_shell/qml/Creative/Theme.qml`.

## Ausprobieren

**Schnelltest in einer bestehenden Fedora-Sitzung** (ohne etwas zu verändern):

```sh
sudo dnf install python3-pyside6 qt6-qtsvg brightnessctl ddcutil
./run-dev.sh
```

Die Leiste erscheint dann als normales Fenster am unteren Rand.

**Als eigene Sitzung installieren:**

```sh
sudo ./install.sh
```

Danach abmelden und im Anmeldebildschirm „Creative OS“ wählen.

## Aufbau

```
creative_shell/
  __main__.py      Start, ein Fenstersatz pro Monitor
  apps.py          App-Liste aus .desktop-Dateien, Suche, angeheftete Apps
  network.py       WLAN/Kabel über NetworkManager (nmcli)
  brightness.py    Helligkeit über brightnessctl und ddcutil
  printers.py      Druckerstatus über CUPS (lpstat)
  session.py       Sperren, Abmelden, Neustart, Ausschalten
  qml/
    HostLayer.qml  Wayland: fest verankert am Bildschirmrand (Layer-Shell)
    HostPlain.qml  Testmodus: normale Fenster
    surfaces/      Taskbar, StartMenu, QuickPanel
    Creative/      Theme, Knöpfe, Schalter, Symbole
session/           Sitzungsstart mit KWin und Absturz-Wächter
```

Angeheftete Apps lassen sich in `~/.config/creative-os/shell.json` ändern.

### Laufende Programme

Jede Taskleiste zeigt die Programme, die auf ihrem Monitor offen sind:
kurzer Strich = läuft, langer Strich in Akzentfarbe = ist vorne, zweiter
Punkt = mehrere Fenster. Klick holt das Fenster nach vorn (nochmal klicken
minimiert), bei mehreren Fenstern wird durchgeschaltet, mittlere Maustaste
öffnet ein neues Fenster. Grundlage ist das KWin-Skript `kwin/creative-tasks`.

### Windows-Tastenkürzel (nur in der Creative-OS-Sitzung)

| Taste | Wirkung |
|---|---|
| Win | Startmenü (auf dem Monitor mit dem aktiven Fenster) |
| Win+E | Dateien |
| Win+I | Einstellungen |
| Win+L | Sperren |
| Win+D | Desktop anzeigen |
| Win+Pfeiltasten | Fenster einrasten (KWin) |
| Alt+Tab | Fenster wechseln (KWin) |
| Win+Umschalt+S | Bildschirmausschnitt aufnehmen |
| Strg+Umschalt+Esc | Aufgaben-Manager |

Fensterknöpfe sitzen rechts wie bei Windows.

## Noch offen (nächste Schritte)

1. **Sperrbildschirm** im Graphit-Look (heute nur `loginctl lock-session`).
2. Eigener Dateimanager, Terminal-Profil, Systemsteuerung.

> Hinweis: Dieser Stand ist sorgfältig geschrieben, aber noch nicht auf
> echter Hardware getestet. Beim ersten Start auf Fedora bitte die
> Terminal-Ausgabe von `./run-dev.sh` mitschicken, falls etwas hakt.
