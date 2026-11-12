import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_helper_syntax():
    subprocess.run(["bash", "-n", str(ROOT / "users" / "creative-users-helper")], check=True)


def test_helper_rejects_bad_login():
    r = subprocess.run(["bash", str(ROOT / "users" / "creative-users-helper"), "add", "Böser Name", "x", "0"],
                       input="geheim\n", capture_output=True, text=True)
    assert r.returncode != 0 and "Kleinbuchstaben" in r.stderr


def test_suggest_login():
    pytest.importorskip("PySide6")
    import sys
    sys.path.insert(0, str(ROOT / "settings"))
    from creative_settings.users import initials, suggest_login
    assert suggest_login("Jörg Müller").startswith("joerg")
    assert suggest_login("  ") == ""
    assert initials("Anna Müller") == "AM"
