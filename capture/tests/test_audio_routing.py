import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'creative_capture'))
import audio_routing as routing

class AudioRoutingTests(unittest.TestCase):
    def select(self, sources, candidates, target='/usb/capture'):
        with patch.object(routing, 'video_usb', return_value=target), \
             patch.object(routing, 'source_usb', side_effect=lambda p: p.get('physical', '')), \
             patch.object(routing.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(sources))):
            return routing.matching_audio('/dev/video2', [{'id': c} for c in candidates])

    def test_usb_interfaces_share_the_same_physical_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb = Path(tmp) / '1-2'
            video = usb / '1-2:1.0' / 'video4linux' / 'video2'
            audio = usb / '1-2:1.2' / 'sound' / 'card3'
            video.mkdir(parents=True)
            audio.mkdir(parents=True)
            (usb / 'idVendor').write_text('1234')
            (usb / 'idProduct').write_text('5678')
            self.assertEqual(routing.usb_parent(video), str(usb))
            self.assertEqual(routing.usb_parent(audio), str(usb))

    def test_pcie_card_video_and_audio_on_same_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            slot = Path(tmp) / 'pci0000:00' / '0000:00:1c.0'
            video = slot / '0000:03:00.0' / 'video4linux' / 'video0'
            audio = slot / '0000:03:00.1' / 'sound' / 'card2'
            gpu_audio = Path(tmp) / 'pci0000:00' / '0000:01:00.1' / 'sound' / 'card1'
            for d in (video, audio, gpu_audio):
                d.mkdir(parents=True)
            for d in (slot / '0000:03:00.0', slot / '0000:03:00.1', Path(tmp) / 'pci0000:00' / '0000:01:00.1', slot):
                (d / 'vendor').write_text('0x1cd7')
            self.assertEqual(routing.device_key(video), 'pci:0000:03:00')
            self.assertEqual(routing.device_key(audio), routing.device_key(video))
            self.assertNotEqual(routing.device_key(gpu_audio), routing.device_key(video))

    def test_usb_wins_over_pci_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctrl = Path(tmp) / '0000:00:14.0'
            usb = ctrl / 'usb1' / '1-2'
            video = usb / '1-2:1.0' / 'video4linux' / 'video2'
            video.mkdir(parents=True)
            (ctrl / 'vendor').write_text('0x8086')
            (usb / 'idVendor').write_text('07ca')
            (usb / 'idProduct').write_text('0337')
            self.assertEqual(routing.device_key(video), str(usb))

    def test_selects_same_usb_device_instead_of_camera(self):
        sources = [{'name': 'camera', 'properties': {'physical': '/usb/camera'}},
                   {'name': 'capture', 'properties': {'physical': '/usb/capture'}}]
        self.assertEqual(self.select(sources, ['camera', 'capture']), 'capture')

    def test_no_matching_source_does_not_fall_back_to_camera(self):
        self.assertEqual(self.select([{'name': 'camera', 'properties': {'physical': '/usb/camera'}}], ['camera']), '')

    def test_ambiguous_profiles_require_manual_choice(self):
        sources = [{'name': n, 'properties': {'physical': '/usb/capture'}} for n in ['analog', 'digital']]
        self.assertEqual(self.select(sources, ['analog', 'digital']), '')

    def test_monitor_is_never_selected(self):
        self.assertEqual(self.select([{'name': 'capture.monitor', 'properties': {'physical': '/usb/capture'}}], ['capture.monitor']), '')

    def test_source_must_be_available_in_qt(self):
        self.assertEqual(self.select([{'name': 'capture', 'properties': {'physical': '/usb/capture'}}], ['camera']), '')

    def test_unknown_video_device_does_not_guess(self):
        self.assertEqual(self.select([], ['camera'], target=''), '')

    def test_unavailable_pactl_does_not_crash(self):
        with patch.object(routing, 'video_usb', return_value='/usb/capture'), \
             patch.object(routing.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(routing.matching_audio('/dev/video2', []), '')

if __name__ == '__main__':
    unittest.main()


class CaptureCardTests(unittest.TestCase):
    """Capture listet nur Capture-Karten – Webcams und virtuelle Kameras nicht."""

    def _fake(self, root, n, label, vendor=None):
        import os
        dev = root / "usb1" / f"1-{n}"
        (dev / "1.0").mkdir(parents=True)
        if vendor:
            (dev / "idVendor").write_text(vendor + "\n")
        node = root / "v4l" / f"video{n}"
        node.mkdir(parents=True)
        (node / "name").write_text(label + "\n")
        os.symlink(dev / "1.0", node / "device")

    def test_nur_capture_karten(self):
        import tempfile
        from pathlib import Path
        capture_card = routing.capture_card
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self._fake(root, 0, "Elgato HD60 X", "0fd9")
            self._fake(root, 1, "Live Gamer MINI: Live Gamer MINI", "07ca")
            self._fake(root, 2, "HD Pro Webcam C920", "046d")
            self._fake(root, 3, "Integrated Camera", "04f2")
            self._fake(root, 4, "USB Video: USB Video", "534d")
            self._fake(root, 5, "Gibeon Kamera")
            v = root / "v4l"
            self.assertEqual(capture_card("/dev/video0", v), "Elgato")
            self.assertEqual(capture_card("/dev/video1", v), "AVerMedia")
            self.assertEqual(capture_card("/dev/video2", v), "")
            self.assertEqual(capture_card("/dev/video3", v), "")
            self.assertEqual(capture_card("/dev/video4", v), "MacroSilicon")
            self.assertEqual(capture_card("/dev/video5", v), "")
