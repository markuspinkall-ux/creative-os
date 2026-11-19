"""Messenger: gehört zum System (Tray, Autostart), nicht ins Startmenü; Schnittstellen passen zusammen."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_nur_im_tray_nicht_im_startmenue():
    desk = (ROOT / "messenger" / "orbit-messenger.desktop").read_text(encoding="utf-8")
    assert "NoDisplay=true" in desk and "StartupWMClass=orbit-messenger" in desk
    bar = (ROOT / "shell" / "creative_shell" / "qml" / "surfaces" / "Taskbar.qml").read_text(encoding="utf-8")
    assert "shell.toggleMessenger(root.screenName)" in bar and 'name: "chat"' in bar
    apps = (ROOT / "shell" / "creative_shell" / "apps.py").read_text(encoding="utf-8")
    assert "orbit-messenger" not in apps                     # nicht in der Gibeon Suite


def test_autostart_und_abbild():
    sup = (ROOT / "shell" / "session" / "creative-shell-supervisor").read_text(encoding="utf-8")
    assert "orbit-messenger 2>&1" in sup
    cf = (ROOT / "image" / "Containerfile").read_text(encoding="utf-8")
    assert "COPY messenger/daemon /usr/lib/orbit-messenger" in cf and "npm ci" in cf
    assert (ROOT / "messenger" / "daemon" / "package-lock.json").exists(), "package-lock.json fehlt"


def test_befehle_von_shell_kennt_der_dienst():
    daemon = (ROOT / "messenger" / "daemon" / "index.js").read_text(encoding="utf-8")
    known = set(re.findall(r"case '([a-z]+)':", daemon))
    model = (ROOT / "shell" / "creative_shell" / "messenger.py").read_text(encoding="utf-8")
    used = set(re.findall(r'"cmd": "([a-z]+)"', model))
    assert used and used <= known, used - known


def test_popup_und_fenster_registriert():
    main = (ROOT / "shell" / "creative_shell" / "__main__.py").read_text(encoding="utf-8")
    assert '"messenger"' in main and "MessengerMenu.qml" in main and '"messenger": MessengerModel()' in main
    assert (ROOT / "shell" / "creative_shell" / "qml" / "messenger" / "MessengerWindow.qml").exists()
