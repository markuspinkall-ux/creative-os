"""Bereinigung: räumt nur Zwischenspeicher/Papierkorb auf – nie eigene Dateien, KI-Modelle nur auf Wunsch."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "settings"))
from creative_settings import cleanup  # noqa: E402


def _w(p, n=4096):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * n)


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(cleanup.Path, "home", classmethod(lambda cls: tmp_path))
    _w(tmp_path / "Dokumente/Rechnung.pdf")
    _w(tmp_path / ".config/creative-os/shell.json")
    _w(tmp_path / ".local/share/Trash/files/alt.txt", 10000)
    _w(tmp_path / ".local/share/Trash/info/alt.txt.trashinfo", 100)
    _w(tmp_path / ".cache/thumbnails/large/a.png", 20000)
    _w(tmp_path / ".cache/mozilla/firefox/cache2/x", 30000)
    _w(tmp_path / ".cache/irgendeine-app/daten", 5000)
    _w(tmp_path / ".cache/huggingface/hub/modell.safetensors", 80000)
    _w(tmp_path / ".var/app/com.discordapp.Discord/cache/c", 7000)
    _w(tmp_path / ".var/app/com.discordapp.Discord/config/einstellungen", 100)
    return tmp_path


def test_analyse_und_bereinigen(tmp_path, monkeypatch):
    h = _home(tmp_path, monkeypatch)
    sizes = {k: cleanup.analyze(k)[0] for k in ("trash", "thumbs", "browser", "apps", "models")}
    assert all(sizes[k] > 0 for k in sizes), sizes
    for k in ("trash", "thumbs", "browser", "apps"):
        assert cleanup.clean(k)[0]
    # weg
    assert not (h / ".local/share/Trash/files/alt.txt").exists()
    assert not (h / ".cache/thumbnails/large").exists() and (h / ".cache/thumbnails").is_dir()
    assert not (h / ".cache/mozilla/firefox").exists()
    assert not (h / ".cache/irgendeine-app/daten").exists()
    assert not (h / ".var/app/com.discordapp.Discord/cache/c").exists()
    # bleibt
    assert (h / "Dokumente/Rechnung.pdf").exists()
    assert (h / ".config/creative-os/shell.json").exists()
    assert (h / ".var/app/com.discordapp.Discord/config/einstellungen").exists()
    assert (h / ".cache/huggingface/hub/modell.safetensors").exists()      # Modelle nur, wenn angehakt
    cleanup.clean("models")
    assert not (h / ".cache/huggingface/hub").exists()


def test_voreinstellung_und_anzeige():
    on = {c["key"]: c["on"] for c in cleanup.CATEGORIES}
    assert on["trash"] and on["apps"] and not on["models"] and not on["journal"] and not on["shader"]
    assert cleanup.human(0) == "0 MB" and cleanup.human(1536 * 1024 ** 2) == "1,5 GB"
    main = (ROOT / "settings/creative_settings/qml/Main.qml").read_text(encoding="utf-8")
    assert 'file: "CleanupPage.qml"' in main
