"""Update-Center: „Was ist neu?“ – die Liste der Neuerungen ist gültig und lesbar."""

import datetime
import json
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "settings" / "creative_settings" / "neuerungen.json"
KEYS = ("neu", "verbessert", "behoben")


class NeuerungenTest(unittest.TestCase):
    def test_format(self):
        entries = json.loads(FILE.read_text(encoding="utf-8"))
        self.assertIsInstance(entries, list)
        self.assertTrue(entries)
        dates = []
        for e in entries:
            datetime.date.fromisoformat(e["datum"])
            dates.append(e["datum"])
            self.assertTrue(e["titel"].strip(), e["datum"])
            self.assertTrue(any(e.get(k) for k in KEYS), f"{e['datum']}: leer")
            for k in KEYS:
                for item in e.get(k, []):
                    self.assertIsInstance(item, str)
                    self.assertTrue(item.strip())
            self.assertFalse(set(e) - {"datum", "titel", *KEYS}, f"{e['datum']}: unbekannte Felder")
        self.assertEqual(len(dates), len(set(dates)), "Datum doppelt")
        self.assertEqual(dates, sorted(dates, reverse=True), "neueste zuerst")


if __name__ == "__main__":
    unittest.main()
