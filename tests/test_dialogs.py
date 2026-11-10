"""Graphit-Dialoge: Selbsttest (läuft nur, wenn PySide6 vorhanden ist)."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dialogs"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import creative_dialogs
except ImportError:  # kein Qt in dieser Umgebung
    creative_dialogs = None


@unittest.skipIf(creative_dialogs is None, "PySide6 fehlt")
class DialogTest(unittest.TestCase):
    def test_selftest(self):
        self.assertEqual(creative_dialogs._selftest(), 0)

    def test_same_enums(self):
        from PySide6.QtWidgets import QMessageBox
        self.assertIs(creative_dialogs.QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Yes)


if __name__ == "__main__":
    unittest.main()
