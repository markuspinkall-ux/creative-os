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
        self.assertIn("noch etwa 3 Min.", s["text"])     # 1,3 GB / 10 MB/s = 130 s + 1,9 GB entpacken ≈ 32 s
        self.assertEqual(s["progress"], int(0.2 * 92))
        # Netzwerkkarte zählt mehr als die Schicht groß ist → nicht über die Schicht hinaus
        p.sample(61, 10_000_000_000)
        self.assertEqual(p.loaded, 2_000_000_000)
        p.feed("Fetching layer sha256:ccc (1.9 GB)... done")
        p.feed("Staging deployment...done")
        self.assertEqual(p.state()["progress"], 92)   # Einrichten beginnt bei 92 % und läuft bis 99 %

    def test_unpacking_after_download_and_stage(self):
        p = U.UpdateProgress({"proc_rate": 50e6, "stage_secs": 120})
        p.sample(0, 0, 0)
        p.feed("custom layers needed: 1 (1.0 GB)")
        p.feed("Fetching layer sha256:ccc (1.0 GB)...")
        for t in range(1, 101):                       # 100 s lang 10 MB/s → komplett da
            p.sample(t, t * 10_000_000, t * 1_000_000)
        p.sample(101, 1_000_000_000, 101_000_000)
        p.sample(110, 1_000_000_000, 101_000_000 + 9 * 50_000_000)
        s = p.state()
        self.assertTrue(p.unpacking)
        self.assertIn("Wird entpackt und gespeichert – Teil 1 von 1", s["text"])
        self.assertIn("schreibt", s["text"])
        # 1 GB, davon ~0,5 GB entpackt (10 s × 50 MB/s) → noch ~10 s
        self.assertIn("noch wenige Sekunden", s["text"])
        self.assertGreater(s["progress"], int(0.5 * 92) + 10)
        self.assertLess(s["progress"], 92)
        p.sample(140, 1_000_000_000, 2_000_000_000)
        p.feed("Fetching layer sha256:ccc (1.0 GB)... done")
        self.assertAlmostEqual(p.proc_rate, 50e6 + (1e9 / 40 - 50e6) * 0.6, delta=1)
        p.feed("Staging deployment...")
        p.sample(200, 1_000_000_000, 2_100_000_000)
        s = p.state()
        self.assertIn("läuft seit 1:00 Min.", s["text"])
        self.assertIn("noch etwa 1 Min.", s["text"])
        self.assertEqual(s["progress"], 92 + int(0.5 * 7))
        p.sample(400, 1_000_000_000, 2_100_000_000)
        self.assertIn("länger als sonst", p.state()["text"])
        p.finish(420)
        self.assertEqual(p.history()["stage_secs"], 280)

    def test_disk_bytes(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("   8       0 sda 1 0 2 3 4 0 100 5 0 0 0\n"
                    "   8       1 sda1 1 0 2 3 4 0 50 5 0 0 0\n"
                    " 259       0 nvme0n1 1 0 2 3 4 0 10 5 0 0 0\n")
        self.assertEqual(U.read_wx_bytes(f.name), 110 * 512)

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
