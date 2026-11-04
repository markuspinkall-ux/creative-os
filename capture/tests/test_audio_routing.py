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
