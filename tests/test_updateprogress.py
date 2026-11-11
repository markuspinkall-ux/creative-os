"""Update-Center: Fortschritt nach Bytes und Restzeit."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "settings"))
from creative_settings import updateprogress as U  # noqa: E402


class ProgressTest(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(U.parse_size("1.2", "GB"), 1_200_000_000)
        self.assertEqual(U.parse_size("47,1", "MB"), 47_100_000)
        self.assertEqual(U.parse_size("1", "GiB"), 1024 ** 3)
        self.assertEqual(U.human_bytes(2_430_000_000), "2,4 GB")
        self.assertEqual(U.human_eta(200), "noch etwa 3 Min.")
        self.assertEqual(U.human_eta(20), "noch wenige Sekunden")
        self.assertEqual(U.human_eta(3 * 3600 + 600), "noch etwa 3 Std. 10 Min.")

    def test_download_with_big_layer(self):
        p = U.UpdateProgress()
        p.sample(0, 1_000)
        self.assertEqual(p.state()["progress"], -1)
        p.feed("ostree chunk layers needed: 2 (100.0 MB)")
        p.feed("custom layers needed: 1 (1.9 GB)")
        self.assertEqual(p.total, 2_000_000_000)
        p.feed("Fetching ostree chunk sha256:aaa (60.0 MB)... done")
        p.feed("Fetching ostree chunk sha256:bbb (40.0 MB)... done")
        p.feed("Fetching layer sha256:ccc (1.9 GB)...")
        # 10 MB/s über 60 s, während die große Schicht lädt
        for t in range(1, 61):
            p.sample(t, 1_000 + 100_000_000 + t * 10_000_000)
        s = p.state()
        self.assertEqual(p.loaded, 100_000_000 + 600_000_000)
        self.assertIn("700 MB von 2,0 GB", s["text"])
        self.assertIn("10 MB/s", s["text"])
        self.assertIn("noch etwa 2 Min.", s["text"])     # 1,3 GB / 10 MB/s = 130 s
        self.assertEqual(s["progress"], int(0.35 * 92))
        # Netzwerkkarte zählt mehr als die Schicht groß ist → nicht über die Schicht hinaus
        p.sample(61, 10_000_000_000)
        self.assertEqual(p.loaded, 2_000_000_000)
        p.feed("Fetching layer sha256:ccc (1.9 GB)... done")
        p.feed("Staging deployment...done")
        self.assertEqual(p.state()["progress"], 96)

    def test_speed_is_smoothed(self):
        p = U.UpdateProgress()
        p.feed("ostree chunk layers needed: 1 (1.0 GB)")
        p.feed("Fetching ostree chunk sha256:a (1.0 GB)...")
        p.sample(0, 0)
        p.sample(1, 10_000_000)
        p.sample(2, 20_000_000)
        p.sample(3, 20_000_000)          # kurzer Aussetzer
        self.assertGreater(p.speed, 5_000_000)

    def test_no_update(self):
        p = U.UpdateProgress()
        p.feed("No upgrade available.")
        self.assertEqual(p.state(), {"progress": 100, "text": "Kein neues Update."})

    def test_rx_reader(self):
        with tempfile.TemporaryDirectory() as root:
            for name, value in (("enp3s0", "1000"), ("lo", "99999"), ("wlan0", "500"), ("docker0", "7")):
                Path(root, name, "statistics").mkdir(parents=True)
                Path(root, name, "statistics", "rx_bytes").write_text(value)
            self.assertEqual(U.read_rx_bytes(root), 1500)
        self.assertEqual(U.read_rx_bytes("/gibt/es/nicht"), 0)


if __name__ == "__main__":
    unittest.main()
