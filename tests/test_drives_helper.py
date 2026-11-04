"""Safety regressions; never execute storage commands on the host."""
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / 'drives/creative-drives-helper'

class DriveSafety(unittest.TestCase):
    def setUp(self):
        self.g = runpy.run_path(str(HELPER))['setup'].__globals__
        self.disk = {'path': '/dev/test', 'type': 'disk', 'children': [
            {'path': '/dev/test1', 'type': 'part', 'uuid': 'old', 'mountpoints': ['/data', '/data/nested']}]}
        self.calls = []
        self.g['find'] = lambda p: self.disk
        self.g['is_system'] = lambda n: False
        self.g['run'] = self.run_command
        self.g['fail'] = lambda message: (_ for _ in ()).throw(RuntimeError(message))

    def run_command(self, *args, **kwargs):
        self.calls.append(args)
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def test_system_disk_never_written(self):
        self.g['is_system'] = lambda n: True
        with self.assertRaisesRegex(RuntimeError, 'System-Laufwerk'):
            self.g['setup']('/dev/test', 'Data', 'ext4')
        self.assertEqual(self.calls, [])

    def test_swap_rejected_before_any_mutation(self):
        with patch.object(Path, 'read_text', return_value='Filename Type Size Used Priority\n/dev/test1 partition 100 0 -2\n'):
            with self.assertRaisesRegex(RuntimeError, 'Auslagerung'):
                self.g['setup']('/dev/test', 'Data', 'ext4')
        self.assertEqual(self.calls, [])

    def test_nested_mount_first_and_no_writes_if_still_mounted(self):
        with patch.object(Path, 'read_text', return_value='Filename Type Size Used Priority\n'):
            with self.assertRaisesRegex(RuntimeError, 'noch verbunden'):
                self.g['setup']('/dev/test', 'Data', 'ext4')
        self.assertEqual(self.calls, [('umount', '--', '/data/nested'), ('umount', '--', '/data')])

    def test_busy_mount_stops_before_wipe(self):
        self.g['run'] = lambda *a, **k: SimpleNamespace(returncode=1, stderr='busy')
        with patch.object(Path, 'read_text', return_value='Filename Type Size Used Priority\n'):
            with self.assertRaisesRegex(RuntimeError, 'gerade benutzt'):
                self.g['setup']('/dev/test', 'Data', 'ext4')

if __name__ == '__main__':
    unittest.main()
