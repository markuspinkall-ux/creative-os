"""Start-Verklemmungen verhindern: kein eigener Dienst darf sich vor udev oder das Laden der Treiber
schieben und gleichzeitig auf die Laufwerke warten (Update 15.11.: Notfallmodus hinter dem Bootlogo)."""
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EARLY = {"systemd-udev-trigger.service", "systemd-udevd.service", "systemd-modules-load.service",
         "local-fs.target", "local-fs-pre.target", "sysinit.target"}


def units():
    for p in (ROOT / "image").rglob("*.service"):
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        cp.optionxform = str
        cp.read_string(p.read_text(encoding="utf-8"))
        yield p, cp


def words(cp, key):
    return set(cp.get("Unit", key, fallback="").split()) if cp.has_section("Unit") else set()


def test_keine_dienste_vor_udev_oder_laufwerken():
    bad = []
    for p, cp in units():
        before = words(cp, "Before")
        after = words(cp, "After") | words(cp, "Requires") | words(cp, "Wants")
        if before & {"systemd-udev-trigger.service", "systemd-modules-load.service", "local-fs.target"}:
            bad.append(f"{p.relative_to(ROOT)}: Before={' '.join(sorted(before & EARLY))}")
        if "local-fs.target" in after and before & EARLY:
            bad.append(f"{p.relative_to(ROOT)}: wartet auf Laufwerke und blockiert frühen Start")
    assert not bad, "Gefährliche Startreihenfolge:\n" + "\n".join(bad)


def test_ton_fix_im_normalen_start():
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.read(ROOT / "image" / "geraete" / "creative-ton-fix.service", encoding="utf-8")
    assert cp.get("Unit", "DefaultDependencies", fallback="yes") != "no"
    assert cp.get("Install", "WantedBy") == "multi-user.target"
