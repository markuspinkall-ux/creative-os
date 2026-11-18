#!/usr/bin/env python3
"""Lösungsbuch Ocarina of Time (Switch 2) – persönliche App für Orbit OS.

Zeigt das Lösungsbuch (index.html neben dieser Datei) in einem eigenen Fenster.
Häkchen und Zähler werden dauerhaft im Benutzerordner gespeichert.
"""
import configparser
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "Lösungsbuch Ocarina of Time"


def dunkel():
    """Orbit-OS-Design: Graphit (dunkel) oder Porzellan (hell)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    cfg = configparser.ConfigParser()
    try:
        cfg.read(Path(base) / "creative-os" / "look.conf", encoding="utf-8")
        return cfg.get("Look", "design", fallback="graphit").strip().lower() != "porzellan"
    except (configparser.Error, OSError):
        return True


def main():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QColor, QIcon
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("orbit-loesungsbuch")
    app.setApplicationDisplayName(NAME)
    app.setDesktopFileName("orbit-loesungsbuch")
    app.setWindowIcon(QIcon(str(HERE / "orbit-loesungsbuch.svg")))

    # Eigenes, dauerhaftes Profil: Fortschritt bleibt nach dem Schließen erhalten
    profile = QWebEngineProfile("orbit-loesungsbuch")
    profile.setPersistentStoragePath(str(Path.home() / ".local/share/orbit-loesungsbuch/daten"))
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)

    thema = "dark" if dunkel() else "light"
    page = QWebEnginePage(profile)
    page.setBackgroundColor(QColor("#0d1f19" if thema == "dark" else "#f3f5ee"))
    view = QWebEngineView()
    view.setPage(page)
    view.setWindowTitle(NAME)
    view.resize(1280, 880)
    url = QUrl.fromLocalFile(str(HERE / "index.html"))
    url.setQuery(f"thema={thema}")              # Orbit-Design an die Seite weitergeben
    view.load(url)
    view.show()
    foto = os.environ.get("ORBIT_LB_FOTO")      # nur zum Prüfen: Fenster fotografieren und beenden
    if foto:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(6000, lambda: (view.grab().save(foto), app.quit()))
    code = app.exec()
    del view, page          # Seite vor dem Profil freigeben, sonst meckert Qt beim Beenden
    return code


if __name__ == "__main__":
    sys.exit(main())
