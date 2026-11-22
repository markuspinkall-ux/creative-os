"""Autostart aus dem Startmenü: Kopie in ~/.config/autostart, an/aus, Start beim Anmelden."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shell"))
from creative_shell import autostart  # noqa: E402


def test_an_aus(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    src = tmp_path / "discord.desktop"
    src.write_text("[Desktop Entry]\nType=Application\nName=Discord\nExec=discord\nHidden=false\n"
                   "[Desktop Action new]\nName=Neu\nExec=discord --new\n", encoding="utf-8")
    assert not autostart.is_enabled("discord.desktop")
    autostart.enable("discord.desktop", src)
    text = (tmp_path / "autostart/discord.desktop").read_text(encoding="utf-8")
    assert "X-Gibeon-Autostart=true" in text and "Exec=discord" in text and "[Desktop Action new]" in text
    assert autostart.is_enabled("discord.desktop")
    autostart.disable("discord.desktop")
    assert not autostart.is_enabled("discord.desktop")


def test_was_startet(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "autostart"
    d.mkdir()
    (d / "a.desktop").write_text("[Desktop Entry]\nName=A\nExec=a\n", encoding="utf-8")
    (d / "b.desktop").write_text("[Desktop Entry]\nName=B\nExec=b\nHidden=true\n", encoding="utf-8")
    (d / "c.desktop").write_text("[Desktop Entry]\nName=C\nExec=c\nX-GNOME-Autostart-enabled=false\n", encoding="utf-8")
    (d / "g.desktop").write_text("[Desktop Entry]\nName=G\nExec=g\nOnlyShowIn=GNOME;\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(autostart.subprocess, "Popen", lambda args, **kw: calls.append(args))
    assert autostart.start_all() == ["a.desktop"]
    assert calls == [["gio", "launch", str(d / "a.desktop")]]


def test_im_startmenue_und_beim_anmelden():
    sm = (ROOT / "shell/creative_shell/qml/surfaces/StartMenu.qml").read_text(encoding="utf-8")
    assert "apps.setAutostart(appMenu.desktopId, !appMenu.autostart)" in sm
    sup = (ROOT / "shell/session/creative-shell-supervisor").read_text(encoding="utf-8")
    assert "python3 -m creative_shell.autostart" in sup
