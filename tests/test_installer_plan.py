"""Tests für die Logik der Creative-Installation (ohne Qt, ohne root)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "installer"))
from creative_installer import plan  # noqa: E402

LSBLK = {"blockdevices": [
    {"name": "/dev/nvme0n1", "path": "/dev/nvme0n1", "size": 1000204886016, "model": "Samsung SSD 980 PRO 1TB  ",
     "tran": "nvme", "type": "disk", "rm": False, "ro": False, "fstype": None, "label": None,
     "children": [{"name": "/dev/nvme0n1p1", "fstype": "vfat", "label": "SYSTEM", "type": "part"},
                  {"name": "/dev/nvme0n1p3", "fstype": "ntfs", "label": "Windows", "type": "part"}]},
    {"name": "/dev/sda", "path": "/dev/sda", "size": 32000000000, "model": "Kleine SSD", "tran": "sata",
     "type": "disk", "rm": False, "ro": False},
    {"name": "/dev/sdb", "path": "/dev/sdb", "size": 64000000000, "model": "SanDisk", "tran": "usb",
     "type": "disk", "rm": True, "ro": False, "children": [{"fstype": "iso9660", "label": "Creative-Live"}]},
    {"name": "/dev/vda", "path": "/dev/vda", "size": 64424509440, "model": None, "tran": None,
     "type": "disk", "rm": False, "ro": False},
    {"name": "/dev/loop0", "path": "/dev/loop0", "size": 5000000000, "type": "loop"},
    {"name": "/dev/zram0", "path": "/dev/zram0", "size": 8000000000, "type": "disk"},
]}


def disks():
    return plan.parse_disks(json.dumps(LSBLK), {"/dev/sdb"})


def test_disks_eligibility():
    d = {x["path"]: x for x in disks()}
    assert "/dev/loop0" not in d and "/dev/zram0" not in d
    assert d["/dev/nvme0n1"]["eligible"]
    assert d["/dev/nvme0n1"]["previous"].startswith("Windows")
    assert d["/dev/nvme0n1"]["model"] == "Samsung SSD 980 PRO 1TB"
    assert d["/dev/nvme0n1"]["sizeText"] == "1,0 TB"
    assert not d["/dev/sda"]["eligible"] and "klein" in d["/dev/sda"]["reason"]
    assert not d["/dev/sdb"]["eligible"] and "Stick" in d["/dev/sdb"]["reason"]
    assert d["/dev/vda"]["eligible"] and d["/dev/vda"]["previous"] == "leer"
    # wählbare zuerst
    assert disks()[0]["eligible"]


def test_suggest_username():
    assert plan.suggest_username("Markus Pinkall") == "markus"
    assert plan.suggest_username("Jürgen Groß") == "juergen"
    assert plan.suggest_username("  Émile ") == "emile"
    assert plan.suggest_username("123 Test") == "u123"
    assert plan.suggest_username("root") == "root1"
    assert plan.suggest_username("") == ""


def cfg(**kw):
    base = {"disk": "/dev/nvme0n1", "fullName": "Markus P", "userName": "markus", "password": "geheim123",
            "password2": "geheim123", "hostName": "creative-os", "keyboard": "Deutsch", "variant": "nvidia"}
    base.update(kw)
    return base


def test_validate():
    assert plan.validate(cfg(), disks()) == ""
    assert "Festplatte" in plan.validate(cfg(disk=""), disks())
    assert "Festplatte" in plan.validate(cfg(disk="/dev/sda; rm -rf /"), disks())
    assert "Stick" in plan.validate(cfg(disk="/dev/sdb"), disks())
    assert "klein" in plan.validate(cfg(disk="/dev/sda"), disks())
    assert "Benutzername" in plan.validate(cfg(userName="Markus"), disks())
    assert "reserviert" in plan.validate(cfg(userName="root"), disks())
    assert "6 Zeichen" in plan.validate(cfg(password="abc", password2="abc"), disks())
    assert "überein" in plan.validate(cfg(password2="anders123"), disks())
    assert "Name" in plan.validate(cfg(fullName='Bob "x"'), disks())
    assert "Computername" in plan.validate(cfg(hostName="mein pc"), disks())


def test_kickstart():
    ks = plan.kickstart(cfg(), "$6$salz$hash", "ghcr.io/markuspinkall-ux/creative-os:nvidia")
    assert "ignoredisk --only-use=nvme0n1" in ks
    assert "clearpart --all --initlabel --drives=nvme0n1" in ks
    assert "autopart --type=btrfs --noswap" in ks
    assert "user --name=markus --gecos=\"Markus P\" --groups=wheel --iscrypted --password=$6$salz$hash" in ks
    assert "geheim123" not in ks
    assert "--transport=containers-storage" in ks
    assert "bootc switch --mutate-in-place --transport registry ghcr.io/markuspinkall-ux/creative-os:nvidia" in ks
    assert "keyboard --vckeymap=de-nodeadkeys --xlayouts='de(nodeadkeys)'" in ks
    assert "{" not in ks.replace("{print $1; exit}", "").replace("{4}", "")


def test_stage_never_goes_back():
    assert plan.stage_for("Deployment starting: ...", 0) == (14, "Creative OS wird kopiert")
    assert plan.stage_for("Starting installer", 50) is None
    assert plan.stage_for("Installation complete", 90)[0] == 100
    assert plan.stage_for("irgendwas", 10) is None


def test_password_strength():
    assert plan.password_strength("") == 0
    assert plan.password_strength("abcdef") == 1
    assert plan.password_strength("Abcdefgh12!x") == 3
