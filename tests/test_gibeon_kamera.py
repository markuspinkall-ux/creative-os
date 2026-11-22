"""Gibeon Kamera: Broadcast nimmt keine Capture-Karte als Webcam und hängt nicht an einer belegten Kamera."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "broadcast"))
from creative_broadcast import daemon  # noqa: E402


def _fake_v4l(tmp, name, vendor):
    usb = tmp / f"usb-{vendor}"
    (usb / "1-1:1.0").mkdir(parents=True)
    (usb / "idVendor").write_text(vendor)
    d = tmp / f"video-{vendor}"
    d.mkdir()
    (d / "device").symlink_to(usb / "1-1:1.0")
    return d


def test_capture_karte_erkannt(tmp_path):
    assert daemon._is_capture_card(_fake_v4l(tmp_path, "Live Gamer MINI", "07ca"), "Live Gamer MINI")
    assert daemon._is_capture_card(_fake_v4l(tmp_path, "x", "0fd9"), "Game Capture HD60 X")
    assert not daemon._is_capture_card(_fake_v4l(tmp_path, "c", "046d"), "HD Pro Webcam C920")


def test_belegte_kamera_wird_uebersprungen(monkeypatch):
    class Cap:
        def __init__(self, dev, _api):
            self.dev = dev
        def isOpened(self): return True
        def set(self, *a): return True
        def read(self): return (self.dev == "/dev/video2", object())
        def release(self): pass

    class CV2:
        CAP_V4L2 = CAP_PROP_FOURCC = CAP_PROP_FRAME_WIDTH = CAP_PROP_FRAME_HEIGHT = CAP_PROP_FPS = CAP_PROP_BUFFERSIZE = 0
        VideoCapture = Cap
        @staticmethod
        def VideoWriter_fourcc(*a): return 0

    monkeypatch.setattr(daemon, "list_cameras", lambda: [
        {"device": "/dev/video0", "name": "Webcam belegt", "capture": False},
        {"device": "/dev/video4", "name": "Live Gamer MINI", "capture": True},
        {"device": "/dev/video2", "name": "Webcam frei", "capture": False}])
    monkeypatch.setattr(daemon.time, "sleep", lambda s: None)
    cam = daemon.Camera.__new__(daemon.Camera)
    cam.W, cam.H, cam.FPS, cam.FOURCC = 1280, 720, 30, "MJPG"
    cap = cam._open(CV2, "")
    assert cap is not None and cap.dev == "/dev/video2"        # belegte übersprungen, Capture-Karte nie


def test_studio_warnt():
    be = (ROOT / "studio/gibeon_studio/backend.py").read_text(encoding="utf-8")
    assert "def broadcast_device(" in be and "_warn_camera_conflict" in be and "broadcast_status()" in be
