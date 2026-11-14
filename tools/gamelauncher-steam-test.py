"""Game Launcher: Steam wird unsichtbar (-silent) gestartet, Aufträge kommen erst danach.
   QT_QPA_PLATFORM=offscreen python3 tools/gamelauncher-steam-test.py"""
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(home)
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
os.environ["XDG_CACHE_HOME"] = str(home / ".cache")
bindir = home / "bin"
bindir.mkdir()
log = home / "steam.log"
fake = bindir / "steam"
fake.write_text(f"""#!/bin/sh
echo "$@" >> {log}
if [ "$1" = "-silent" ]; then
    sleep 2                                   # Steam braucht beim Start einen Moment
    mkdir -p {home}/.steam && echo $$ > {home}/.steam/steam.pid
    sleep 120
fi
""")
fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
os.environ["PATH"] = f"{bindir}:{os.environ['PATH']}"

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "gamelauncher"), str(ROOT / "shell")]
from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv)
from creative_gamelauncher import backend, steam  # noqa: E402

steam.steam_root = lambda: None
toasts = []
la = backend.Launcher()
la.toast.connect(toasts.append)
assert not backend.steam_running(), "Steam läuft angeblich schon"
la.install(570, "Dota 2")
la.play(730, "Counter-Strike 2")


def lines():
    return log.read_text().splitlines() if log.exists() else []


def check():
    got = lines()
    if any("steam://" in g for g in got):
        assert got[0] == "-silent", f"Steam wurde nicht unsichtbar gestartet: {got}"
        assert got.count("-silent") == 1, f"Steam mehrfach gestartet: {got}"
        assert "steam://install/570" in got and "steam://rungameid/730" in got, got
        assert backend.steam_running()
        la.install(440, "Team Fortress 2")             # Steam läuft: sofort, ohne -silent
        time.sleep(0.5)
        assert lines()[-1] == "steam://install/440" and lines().count("-silent") == 1, lines()
        print("Steam leise starten:", lines())
        print("Hinweise:", toasts)
        print("Game Launcher › Steam im Hintergrund: alles in Ordnung")
        os.system(f"pkill -f '{fake} -silent'")
        app.exit(0)
    else:
        assert "-silent" in got or time.monotonic() - start < 3, f"Steam nicht gestartet: {got}"
        QTimer.singleShot(500, check)


start = time.monotonic()
QTimer.singleShot(500, check)
QTimer.singleShot(40000, lambda: (print("FEHLER: Zeitüberschreitung", lines()), app.exit(1)))
sys.exit(app.exec())
