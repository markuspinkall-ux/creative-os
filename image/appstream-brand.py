#!/usr/bin/python3
"""Creative-Namen und -Symbole in „Software“ (GNOME Software).

1. Die Programm-Beschreibungen (AppStream) der mitgelieferten Programme, die in
   Creative OS umbenannt sind, bekommen den Creative-Namen, das Creative-Symbol
   und keine Original-Bildschirmfotos mehr.
2. Die eigenen Creative-Apps bekommen eigene Beschreibungen, damit sie unter
   „Installiert“ mit Logo erscheinen.

Läuft beim Bauen des Abbilds (als root).
"""

import gzip
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = "Creative OS"
# AppStream-ID → (Name, Symbol, Kurzbeschreibung)
REBRAND = {
    "org.kde.konsole": ("Terminal", "creative-terminal", "Befehle eingeben – das Terminal von Creative OS"),
    "org.gnome.Ptyxis": ("Terminal", "creative-terminal", "Befehle eingeben – das Terminal von Creative OS"),
    "org.kde.spectacle": ("Bildschirmfoto-Dienst", "creative-shots", "Nimmt für Creative Shots im Hintergrund auf"),
    "org.kde.ark": ("Entpacken", "creative-archive", "ZIP- und andere Archive öffnen und entpacken"),
    "org.gnome.DiskUtility": ("Laufwerke (Erweitert)", "creative-drive", "Festplatten, SSDs und USB-Sticks für Fortgeschrittene"),
    "org.kde.krita": ("Creative Art", "creative-art", "Fotos und Grafiken bearbeiten – Ebenen, Auswahlen, Korrekturen, Filter"),
    "org.kde.partitionmanager": ("Laufwerke (Erweitert)", "creative-drive", "Festplatten, SSDs und USB-Sticks für Fortgeschrittene"),
    "org.gnome.Software": ("Software", "creative-store", "Programme installieren, aktualisieren und entfernen"),
    "org.kde.kwrite": ("Creative Notes", "creative-notes", "Texte und Code bearbeiten"),
    "org.kde.kate": ("Creative Notes", "creative-notes", "Texte und Code bearbeiten"),
    "org.kde.kcalc": ("Creative Calculator", "creative-calculator", "Rechnen mit Verlauf"),
    "org.kde.gwenview": ("Creative Pictures", "creative-pictures", "Fotos und Bilder ansehen"),
    "org.kde.plasma-systemmonitor": ("Taskmanager", "creative-taskmanager", "Prozesse und Leistung"),
    "org.kde.systemsettings": ("KDE-Einstellungen", "creative-settings", "Erweiterte Einstellungen"),
    "org.kde.dolphin": ("Dateien", "creative-files", "Ordner, Laufwerke und USB-Sticks"),
    "org.kde.elisa": ("Creative Player", "creative-player", "Musik, Videos und Fernsehen"),
    "org.kde.plasma-welcome": ("Willkommen", "creative-settings", "Erste Schritte"),
}

# Eigene Apps: Desktop-Datei → (Name, Symbol, Kurzbeschreibung, Beschreibung, Kategorie)
OWN = {
    "creative-files": ("Dateien", "creative-files", "Ordner, Laufwerke und USB-Sticks öffnen",
                       "Der Dateimanager von Creative OS: Dieser PC, Schnellzugriff, Papierkorb, Laufwerke und USB-Sticks.", "System"),
    "creative-player": ("Creative Player", "creative-player", "Musik, Videos, YouTube Music und Fernsehen",
                        "Spielt Musik und Videos ab, zeigt die YouTube-Music-Top-10 mit Suche und Favoriten und deutsches Fernsehen (IPTV).", "AudioVideo"),
    "creative-notes": ("Creative Notes", "creative-notes", "Texte und Code bearbeiten",
                       "Texteditor mit Reitern, Syntaxfarben, Suchen und Ersetzen – ungespeicherte Texte gehen nie verloren.", "Utility"),
    "creative-calculator": ("Creative Calculator", "creative-calculator", "Rechnen mit Verlauf",
                            "Rechner mit exakten Ergebnissen, Prozent wie bei Windows und Verlauf.", "Utility"),
    "creative-taskmanager": ("Taskmanager", "creative-taskmanager", "Programme beenden, Leistung ansehen",
                             "Prozesse, Leistung von CPU, Speicher, Datenträgern, Netzwerk und Grafikkarte, Autostart-Apps.", "System"),
    "creative-pictures": ("Creative Pictures", "creative-pictures", "Fotos und Bilder ansehen",
                          "Sammlung nach Monaten, Favoriten, Zoom, Drehen, Diashow und Bildinfos.", "Graphics"),
    "creative-shots": ("Creative Shots", "creative-shots", "Bildschirmfotos aufnehmen und beschriften",
                       "Rechteck, Fenster, Vollbild oder Freihand – mit Stift, Textmarker, Pfeil und Zuschneiden.", "Graphics"),
    "creative-settings": ("Systemsteuerung", "creative-settings", "Alle Einstellungen von Creative OS",
                          "Netzwerk, Bildschirme, Ton, Laufwerke, Drucker, Mein Server, Aussehen und Updates.", "Settings"),
}


def _id(comp):
    el = comp.find("id")
    return re.sub(r"\.desktop$", "", el.text.strip()) if el is not None and el.text else ""


def _set_single(comp, tag, text):
    for el in comp.findall(tag):
        comp.remove(el)
    new = ET.SubElement(comp, tag)
    new.text = text
    return new


def rebrand(comp):
    cid = _id(comp)
    if cid not in REBRAND:
        return False
    name, icon, summary = REBRAND[cid]
    _set_single(comp, "name", name)
    _set_single(comp, "summary", summary)
    for el in comp.findall("icon"):
        comp.remove(el)
    ic = ET.SubElement(comp, "icon", {"type": "stock"})
    ic.text = icon
    for el in comp.findall("screenshots") + comp.findall("description"):
        comp.remove(el)
    d = ET.SubElement(comp, "description")
    ET.SubElement(d, "p").text = summary + "."
    for tag in ("developer_name", "developer"):
        for el in comp.findall(tag):
            comp.remove(el)
    dev = ET.SubElement(comp, "developer", {"id": "creativeos"})
    ET.SubElement(dev, "name").text = f"{BASE} (Grundlage: Open-Source-Projekt)"
    return True


def process(path):
    raw = path.read_bytes()
    gz = path.suffix == ".gz"
    data = gzip.decompress(raw) if gz else raw
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return 0
    comps = [root] if root.tag == "component" else root.findall("component")
    n = sum(1 for c in comps if rebrand(c))
    if n:
        out = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        path.write_bytes(gzip.compress(out) if gz else out)
    return n


def own_metainfo(target):
    target.mkdir(parents=True, exist_ok=True)
    for desk, (name, icon, summary, desc, cat) in OWN.items():
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.creativeos.{desk.split('-', 1)[1]}</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <name>{name}</name>
  <summary>{summary}</summary>
  <description><p>{desc}</p></description>
  <launchable type="desktop-id">{desk}.desktop</launchable>
  <icon type="stock">{icon}</icon>
  <developer id="creativeos"><name>{BASE}</name></developer>
  <url type="homepage">https://github.com/markuspinkall-ux/creative-os</url>
  <categories><category>{cat}</category></categories>
  <compulsory_for_desktop>KDE</compulsory_for_desktop>
  <provides><binary>{desk}</binary></provides>
</component>
"""
        (target / f"org.creativeos.{desk.split('-', 1)[1]}.metainfo.xml").write_text(xml, encoding="utf-8")


def main():
    total = 0
    for d in (Path("/usr/share/metainfo"), Path("/usr/share/appdata"),
              Path("/usr/share/swcatalog/xml"), Path("/usr/share/app-info/xmls")):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.name.endswith((".xml", ".xml.gz")):
                try:
                    total += process(f)
                except OSError as exc:
                    print(f"übersprungen: {f} ({exc})", file=sys.stderr)
    own_metainfo(Path("/usr/share/metainfo"))
    print(f"Software: {total} Einträge auf Creative-Namen umgestellt, {len(OWN)} eigene Apps eingetragen.")


if __name__ == "__main__":
    main()
