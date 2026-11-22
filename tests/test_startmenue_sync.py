"""Jede App, die das Abbild ins Startmenü legt, ist in creative-apps-sync freigeschaltet
(sonst bricht der Bau ab – so fällt es schon bei den Tests auf)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_startmenue_vollstaendig():
    res = subprocess.run([sys.executable, str(ROOT / "tools/startmenue-check.py")], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr or res.stdout
