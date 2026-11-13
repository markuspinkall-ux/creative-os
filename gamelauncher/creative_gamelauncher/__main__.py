"""Game Launcher – Steam-Spiele im Vollbild mit dem Controller starten (wie Big Picture).

  creative-gamelauncher              Vollbild auf dem Hauptbildschirm
  creative-gamelauncher --fenster    im Fenster (zum Ausprobieren)
  creative-gamelauncher --foto BILD  nach dem Laden ein Foto speichern (Prüfung)
  creative-gamelauncher --selftest   ohne Bildschirm laden und Warnungen melden
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

for _p in (Path(__file__).resolve().parent.parent.parent / "shell", Path("/usr/lib/creative-shell")):
    if (_p / "creative_shell").is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))
        break

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

HERE = Path(__file__).resolve().parent


def primary_output():
    """Name des Hauptbildschirms, wie in den Bildschirm-Einstellungen festgelegt (Priorität 1).
    Qt kennt unter Wayland nur den „ersten“ Bildschirm – der ist oft nicht der Hauptbildschirm."""
    try:
        raw = subprocess.run(["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=3).stdout
        data = json.loads(raw[raw.index("{"):])
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    outs = [o for o in data.get("outputs", []) if o.get("enabled", True) and o.get("connected", True)]
    outs.sort(key=lambda o: int(o.get("priority", 99) or 99))
    return outs[0].get("name", "") if outs else ""


def kwin_to_output(name):
    """KWin bitten, dieses Fenster auf den Bildschirm `name` zu legen und ins Vollbild zu schalten
    (unter Wayland darf ein Programm das nicht selbst)."""
    if not name:
        return
    code = (
        f"const target = workspace.screens.find(o => o.name === {json.dumps(name)});\n"
        "for (const w of workspace.windowList()) {\n"
        f"    if (w.pid !== {os.getpid()} || !w.normalWindow) continue;\n"
        "    if (target && w.output !== target) workspace.sendClientToScreen(w, target);\n"
        "    w.fullScreen = true;\n"
        "    workspace.activeWindow = w;\n"
        "}\n"
    )
    script = Path(tempfile.gettempdir()) / f"creative-gamelauncher-{os.getpid()}.js"
    plugin = f"creative-gamelauncher-{os.getpid()}"
    call = ["gdbus", "call", "--session", "--dest", "org.kde.KWin"]
    try:
        script.write_text(code, encoding="utf-8")
        out = subprocess.run(call + ["--object-path", "/Scripting", "--method",
                                     "org.kde.kwin.Scripting.loadScript", str(script), plugin],
                             capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"\((-?\d+),?\)", out)
        if m and int(m.group(1)) >= 0:
            subprocess.run(call + ["--object-path", f"/Scripting/Script{m.group(1)}", "--method",
                                   "org.kde.kwin.Script.run"], capture_output=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        def cleanup():
            subprocess.run(call + ["--object-path", "/Scripting", "--method",
                                   "org.kde.kwin.Scripting.unloadScript", plugin], capture_output=True, timeout=3)
            try:
                script.unlink()
            except OSError:
                pass
        QTimer.singleShot(2000, cleanup)


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Game Launcher")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-gamelauncher")
    app.setWindowIcon(QIcon.fromTheme("input-gaming"))

    from creative_shell.mainthread import install
    from .backend import Launcher
    _timer = install()  # noqa: F841

    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    launcher = Launcher()
    engine.rootContext().setContextProperty("launcher", launcher)
    engine.quit.connect(app.quit)
    problems = []
    engine.warnings.connect(lambda ws: problems.extend(w.toString() for w in ws))
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        print("\n".join(problems))
        return 1
    win = engine.rootObjects()[0]
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    if "--selftest" in sys.argv:
        def done():
            for p in problems:
                print("QML:", p)
            app.exit(1 if problems else 0)
        QTimer.singleShot(1500, done)
        return app.exec()

    # Nur auf dem Hauptbildschirm (wie in den Bildschirm-Einstellungen festgelegt), im Vollbild
    main_output = "" if "--foto" in sys.argv else primary_output()
    screen = next((sc for sc in app.screens() if sc.name() == main_output), None) or app.primaryScreen()
    if screen is not None:
        win.setScreen(screen)
        win.setGeometry(screen.geometry())
    if "--fenster" in sys.argv or "--foto" in sys.argv:
        win.resize(1920, 1080)
        win.show()
    else:
        win.showFullScreen()
        # Sicherheitshalber KWin den Bildschirm vorgeben (einmal sofort, einmal nach dem Aufbau)
        QTimer.singleShot(300, lambda: kwin_to_output(screen.name() if screen else main_output))
        QTimer.singleShot(1500, lambda: kwin_to_output(screen.name() if screen else main_output))

    if "--foto" in sys.argv:
        target = sys.argv[sys.argv.index("--foto") + 1]
        wait = 4000
        if "--warten" in sys.argv:
            wait = int(sys.argv[sys.argv.index("--warten") + 1])

        def shot():
            win.grabWindow().save(target)
            for p in problems:
                print("QML:", p)
            print("Foto:", target)
            app.quit()
        QTimer.singleShot(wait, shot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
