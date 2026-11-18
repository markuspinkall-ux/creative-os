import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'creative_capture'))
import wach  # noqa: E402


class WachTests(unittest.TestCase):
    def test_sperre_endet_mit_capture(self):
        cmd = wach.inhibit_cmd(4242)
        self.assertIn('systemd-inhibit', cmd)
        self.assertIn('--what=idle:sleep', cmd)
        self.assertEqual(cmd[-4:], ['tail', '--pid=4242', '-f', '/dev/null'])

    def test_capture_haelt_wach(self):
        main = (Path(__file__).resolve().parents[1] / 'creative_capture' / '__main__.py').read_text(encoding='utf-8')
        self.assertIn('WachHalten().start()', main)
        self.assertIn('aboutToQuit.connect(wach.stop)', main)


if __name__ == '__main__':
    unittest.main()
