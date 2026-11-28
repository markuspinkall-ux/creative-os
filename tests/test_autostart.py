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


def test_tray_schalter(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "autostart"
    d.mkdir()
    (d / "steam.desktop").write_text("[Desktop Entry]\nName=Steam\nExec=/usr/bin/steam %U\n", encoding="utf-8")
    (d / "com.discordapp.Discord.desktop").write_text(
        "[Desktop Entry]\nName=Discord\nExec=/usr/bin/flatpak run --branch=stable com.discordapp.Discord\n",
        encoding="utf-8")
    (d / "normal.desktop").write_text("[Desktop Entry]\nName=N\nExec=normal --x\nStartupWMClass=NormalApp\n",
                                      encoding="utf-8")
    (d / "offen.desktop").write_text(f"[Desktop Entry]\nName=O\nExec=steam\n{autostart.MINIMIZED}=false\n",
                                     encoding="utf-8")
    assert autostart.tray_command(d / "steam.desktop") == ["/usr/bin/steam", "-silent"]
    assert autostart.tray_command(d / "com.discordapp.Discord.desktop")[-1] == "--start-minimized"
    assert autostart.tray_command(d / "normal.desktop") is None
    assert autostart.app_names(d / "normal.desktop") == {"normal", "normalapp"}
    assert "com.discordapp.discord" in autostart.app_names(d / "com.discordapp.Discord.desktop")
    calls = []
    monkeypatch.setattr(autostart.subprocess, "Popen", lambda args, **kw: calls.append(args))
    autostart.start_all()
    assert ["/usr/bin/steam", "-silent"] in calls
    assert ["gio", "launch", str(d / "normal.desktop")] in calls
    assert ["gio", "launch", str(d / "offen.desktop")] in calls           # ausdrücklich nicht minimiert


def test_minimier_skript():
    js = autostart.minimizer_script({"steam", "normalapp"}, 90)
    assert '["normalapp", "steam"]' in js and "90 * 1000" in js
    assert "w.minimized = true" in js and "windowAdded.disconnect" in js
