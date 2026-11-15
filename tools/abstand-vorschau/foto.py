"""Bildschirmfoto über KWin (ScreenShot2) – im Test ohne Rückfrage (KWIN_SCREENSHOT_NO_PERMISSION_CHECKS=1)."""
import os
import sys
import threading

import dbus
from PySide6.QtGui import QImage

r, w = os.pipe()
chunks = []
t = threading.Thread(target=lambda: chunks.append(os.fdopen(r, "rb").read()))
t.start()
bus = dbus.SessionBus()
shot = dbus.Interface(bus.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2"), "org.kde.KWin.ScreenShot2")
meta = shot.CaptureWorkspace(dbus.Dictionary({"include-cursor": False, "native-resolution": True}, signature="sv"),
                             dbus.types.UnixFd(w))
os.close(w)
t.join(20)
data = chunks[0]
width, height, stride, fmt = int(meta["width"]), int(meta["height"]), int(meta["stride"]), int(meta["format"])
print("Bild:", width, height, stride, fmt, len(data))
img = QImage(data, width, height, stride, QImage.Format(fmt)).copy()
img.save(sys.argv[1])
