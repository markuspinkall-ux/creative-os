"""Prüfung KI-Helfer: echte Fragen an das lokale Modell + Fotos von Karte und Chat-Fenster.

Aufruf (in der Prüfung auf GitHub):  python3 tools/ki-test.py <ausgabeordner> [graphit|porzellan]
Erwartet llama-server unter /usr/lib/creative-ki/llama und ein Modell in /var/lib/creative-ki/modelle.
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1])
DESIGN = sys.argv[2] if len(sys.argv) > 2 else "graphit"
OUT.mkdir(parents=True, exist_ok=True)

conf = Path(os.environ.get("XDG_CONFIG_HOME", "/tmp/ki-conf"))
(conf / "creative-os").mkdir(parents=True, exist_ok=True)
(conf / "creative-os" / "look.conf").write_text(f"[Look]\ndesign={DESIGN}\naccent=blau\n")
os.environ["XDG_CONFIG_HOME"] = str(conf)
sys.path.insert(0, str(ROOT / "shell"))

from PySide6.QtCore import QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from creative_shell import ki  # noqa: E402
from creative_shell.mainthread import install  # noqa: E402

FRAGEN = [
    "Wer war der erste Bundeskanzler der Bundesrepublik Deutschland?",
    "Schreib eine kurze, freundliche E-Mail an meinen Vermieter: Die Heizung im Bad ist seit gestern kaputt.",
]


def warten(app, cond, sekunden):
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende and not cond():
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 100)
        time.sleep(0.05)
    return cond()


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv[:1])
    _timer = install()  # noqa: F841
    helfer = ki.KiHelfer()
    print("Grafikspeicher:", helfer.vram, "GB · Empfehlung:", helfer.choice, "· Modell:", helfer.modelName or "–")
    fehler = 0
    if helfer.state == "einrichten" and os.environ.get("KI_EINRICHTEN") == "1":
        # Gleicher Weg wie im Widget: „Jetzt einrichten“
        helfer.install()
        letzte = [""]

        def zeigen():
            if helfer.status != letzte[0] and helfer.progress % 10 == 0:
                letzte[0] = helfer.status
                print(f"  {helfer.progress} % {helfer.status}", flush=True)
            return helfer.state != "laedt"
        warten(app, zeigen, 1800)
        print("Einrichten:", helfer.state, helfer.status)
    if os.environ.get("KI_FRAGEN", "1") == "1":
        assert helfer.state == "bereit", f"Kein Modell installiert (Zustand {helfer.state})"
        for frage in FRAGEN:
            start = time.monotonic()
            helfer.ask(frage)
            ok = warten(app, lambda: not helfer.busy, 900)
            antwort = helfer.messages[-1]
            dauer = time.monotonic() - start
            print(f"\n### {frage}\n{antwort['text']}\n(Quellen: {[q['titel'] for q in antwort.get('quellen', [])]}"
                  f" · {dauer:.0f} s)")
            if not ok or not antwort["text"] or antwort.get("fehler"):
                fehler += 1
        erste = helfer.messages[1]["text"]
        if "Adenauer" not in erste:
            print("WARNUNG: Adenauer nicht in der ersten Antwort")
            fehler += 1

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT / "shell" / "creative_shell" / "qml"))
    engine.rootContext().setContextProperty("kiHelper", helfer)
    qml = f"""
import QtQuick
import QtQuick.Window
import Creative
import "file://{ROOT}/shell/creative_shell/qml/surfaces"
Item {{
    property alias chat: chatWin
    Window {{
        id: desk
        objectName: "desk"
        width: 400; height: 230; visible: true
        color: Theme.ground
        Rectangle {{
            x: 20; y: 20; width: 330; height: 178; radius: 22
            color: Theme.bar; border.color: Theme.hairline
            KiCard {{ anchors.fill: parent; anchors.leftMargin: 30; anchors.rightMargin: 12; anchors.topMargin: 10; anchors.bottomMargin: 10; ki: kiHelper }}
        }}
    }}
    KiChat {{ id: chatWin; objectName: "chat"; ki: kiHelper }}
    Component.onCompleted: chatWin.openChat()
}}
"""
    qml_file = OUT / "ki-vorschau.qml"
    qml_file.write_text(qml)
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        print("QML konnte nicht geladen werden")
        return 1
    warten(app, lambda: False, 2.5)
    from PySide6.QtQuick import QQuickWindow
    for w in app.topLevelWindows():
        if isinstance(w, QQuickWindow):
            name = w.objectName() or "fenster"
            w.grabWindow().save(str(OUT / f"ki-{name}-{DESIGN}.png"))
            print("Foto:", OUT / f"ki-{name}-{DESIGN}.png")
    helfer.unload_now()
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
