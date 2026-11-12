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
    assert mod.recolor(dark) == light


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
    assert "#ffffff" in (out / "apps/scalable/kcalc.svg").read_text()
    assert "#3d6fe0" in (out / "apps/scalable/kcalc.svg").read_text()
    assert "#1c2433" in (out / "apps/scalable/creative-writer.svg").read_text()
