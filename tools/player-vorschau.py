#!/usr/bin/python3
"""Player prüfen und fotografieren: YouTube Music (Kacheln von der echten Seite, Suche) und Podcasts.

  python3 tools/player-vorschau.py <ausgabeordner>

Lädt die offizielle YouTube-Music-Seite unsichtbar, liest Kacheln und Suchtreffer aus und fotografiert
die eigene Oberfläche. Ohne Internet/mit Zustimmungsseite wird das nur gemeldet (kein Fehler)."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "media"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "player-fotos")
OUT.mkdir(parents=True, exist_ok=True)
tmp = tempfile.mkdtemp()
os.environ.update(XDG_CONFIG_HOME=tmp, XDG_DATA_HOME=tmp, XDG_CACHE_HOME=tmp, HOME=tmp,
                  QT_QPA_PLATFORM="offscreen", QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox")

from PySide6.QtWebEngineQuick import QtWebEngineQuick  # noqa: E402
QtWebEngineQuick.initialize()
from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv[:1])
app.setOrganizationName("Creative OS")
app.setApplicationName("Creative Player")
from creative_media.ytmusic import YtMusicModel  # noqa: E402
from creative_media.podcasts import Podcasts, episodes_dir  # noqa: E402
from creative_media.library import LibraryModel  # noqa: E402
from creative_media.iptv import IptvModel  # noqa: E402
from creative_media.settings import Settings  # noqa: E402
from creative_media.nowplaying import NowPlayingWriter  # noqa: E402

settings = Settings()
ytm = YtMusicModel()
pods = Podcasts(episodes_dir())
engine = QQmlApplicationEngine()
engine.addImportPath(str(ROOT / "shell" / "creative_shell" / "qml"))
ctx = engine.rootContext()
KEEP = dict(settings=settings, music=LibraryModel("music"), videos=LibraryModel("video"), iptv=IptvModel(settings),
            ytmusic=ytm, podcasts=pods, nowplaying=NowPlayingWriter(), startFiles=[], webEngineAvailable=True)
for k, v in KEEP.items():       # Verweise behalten, sonst räumt Python die Objekte weg
    ctx.setContextProperty(k, v)
engine.load(QUrl.fromLocalFile(str(ROOT / "media" / "creative_media" / "qml" / "Main.qml")))
if not engine.rootObjects():
    print("FEHLER: Player-Oberfläche lädt nicht")
    sys.exit(1)
win = engine.rootObjects()[0]
win.setProperty("width", 1360)
win.setProperty("height", 860)
fails = []


def shot(name):
    path = OUT / name
    win.grabWindow().save(str(path))
    print("Foto:", path)


steps = []


def step(delay, fn):
    steps.append((delay, fn))


def run_steps():
    t = 0
    for delay, fn in steps:
        t += delay
        QTimer.singleShot(t, fn)
    QTimer.singleShot(t + 500, app.quit)


step(500, lambda: win.setProperty("section", "ytmusic"))
step(25000, lambda: (print(f"YouTube Music: {len(ytm.shelves)} Kachelreihen, "
                           f"{sum(len(s['items']) for s in ytm.shelves)} Kacheln, Zustimmung nötig: {ytm.needsConsent}"),
                     [print("  ·", s["title"], "–", ", ".join(i["title"] for i in s["items"][:4])) for s in ytm.shelves[:4]],
                     shot("player-ytmusic.png")))
step(500, lambda: ytm.find("Queen Bohemian Rhapsody"))
step(15000, lambda: (print(f"Suche: {len(ytm.results)} Treffer"),
                     [print("  ·", r["title"], "|", r["subtitle"][:60], "|", r["videoId"]) for r in ytm.results[:5]],
                     shot("player-ytmusic-suche.png")))
step(500, lambda: win.setProperty("section", "podcast"))
step(500, lambda: pods.search("Wissen"))
step(8000, lambda: (print(f"Podcasts: {len(pods.catalogue)} Treffer"), shot("player-podcast.png")))
run_steps()
app.exec()
sys.exit(1 if fails else 0)
