import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("porzellan_icons", ROOT / "theme" / "icons" / "porzellan-icons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_recolor_matches_light_shell_icons():
    mod = load()
    dark = (ROOT / "shell/creative_shell/qml/Creative/icons/lock.svg").read_text()
    light = (ROOT / "shell/creative_shell/qml/Creative/icons-light/lock.svg").read_text()
    # App-Symbole in Porzellan ohne Blau: Akzent schiefergrau statt #3d6fe0 (Shell-Symbole behalten Blau)
    assert mod.recolor(dark) == light.replace("#3d6fe0", "#5b6576")


def test_build_theme(tmp_path):
    mod = load()
    src = tmp_path / "Creative"
    (src / "apps" / "scalable").mkdir(parents=True)
    (src / "index.theme").write_text("[Icon Theme]\nName=Creative\nComment=x\nInherits=breeze-dark,breeze,hicolor\n")
    (src / "apps" / "scalable" / "kcalc.svg").write_text('<svg><rect fill="#232836" stroke="#8FB3FF"/></svg>')
    extra = tmp_path / "creative-writer.svg"
    extra.write_text('<svg><path fill="#dce6ff"/></svg>')
    mod.main(src, tmp_path / "CreativePorzellan", [extra])
    out = tmp_path / "CreativePorzellan"
    assert "Inherits=breeze,hicolor" in (out / "index.theme").read_text()
    assert "#edf0f5" in (out / "apps/scalable/kcalc.svg").read_text()      # runde Fläche zartes Grau
    kcalc = (out / "apps/scalable/kcalc.svg").read_text()
    assert "#d3d9e3" in kcalc and "#3d6fe0" not in kcalc.lower()   # Kachelrand hellgrau, kein Blau
    assert "#1c2433" in (out / "apps/scalable/creative-writer.svg").read_text()


def test_runde_symbole():
    spec = importlib.util.spec_from_file_location("round_icons", ROOT / "theme" / "icons" / "round-icons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tile = (ROOT / "studio" / "gibeon-studio.svg").read_text()
    out = mod.roundify(tile)
    assert '<circle cx="32" cy="32" r="29" fill="#10131a"/>' in out and "#232836" not in out.lower() and "<rect x=\"4\"" not in out
    assert "#8fb3ff" not in out.lower() and "#ffb07a" not in out.lower()     # nur Schriftfarbe
    glyph = (ROOT / "shell/creative_shell/qml/Creative/icons/lock.svg").read_text()
    assert mod.roundify(glyph) == glyph                                    # Strichsymbole bleiben
