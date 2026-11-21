"""Fluid-Glas: KWin zeichnet den Hintergrund hinter Leisten und Startmenü weich.

Dafür bietet KDE KWindowEffects::enableBlurBehind (KF6 WindowSystem). Eine Python-Anbindung
dafür gibt es nicht; die Funktion wird deshalb direkt aus libKF6WindowSystem aufgerufen –
mit den C++-Zeigern, die PySide (shiboken6) für das Fenster und die Fläche liefert.

Fehlt die Bibliothek oder die Funktion, bleibt alles wie es ist (Glas ohne Weichzeichnen).
"""

import ctypes

from PySide6.QtCore import QRect
from PySide6.QtGui import QRegion

SYMBOL = "_ZN14KWindowEffects16enableBlurBehindEP7QWindowbRK7QRegion"
_fn = None
_tried = False


def _load():
    global _fn, _tried
    if _tried:
        return _fn
    _tried = True
    for name in ("libKF6WindowSystem.so.6", "libKF6WindowSystem.so"):
        try:
            lib = ctypes.CDLL(name)
            fn = getattr(lib, SYMBOL)
        except (OSError, AttributeError):
            continue
        fn.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p]
        fn.restype = None
        _fn = fn
        break
    return _fn


def available():
    return _load() is not None


def rounded(x, y, w, h, r):
    """Fläche mit runden Ecken (aus Rechtecken und Ellipsen zusammengesetzt)."""
    x, y, w, h = int(round(x)), int(round(y)), int(round(w)), int(round(h))
    r = int(max(0, min(r, w / 2, h / 2)))
    if w <= 0 or h <= 0:
        return QRegion()
    if r == 0:
        return QRegion(QRect(x, y, w, h))
    reg = QRegion(QRect(x + r, y, w - 2 * r, h)).united(QRegion(QRect(x, y + r, w, h - 2 * r)))
    d = 2 * r
    for cx, cy in ((x, y), (x + w - d, y), (x, y + h - d), (x + w - d, y + h - d)):
        reg = reg.united(QRegion(QRect(cx, cy, d, d), QRegion.RegionType.Ellipse))
    return reg


def set_blur(window, rects):
    """rects: [{"x","y","w","h","r"}] in Fensterkoordinaten. Leere Liste = aus."""
    fn = _load()
    if fn is None or window is None:
        return False
    try:
        from shiboken6 import getCppPointer
    except ImportError:
        return False
    region = QRegion()
    for rc in rects or []:
        try:
            region = region.united(rounded(rc["x"], rc["y"], rc["w"], rc["h"], rc.get("r", 0)))
        except (KeyError, TypeError, ValueError):
            continue
    try:
        win_ptr = getCppPointer(window)[0]
        reg_ptr = getCppPointer(region)[0]
    except (TypeError, RuntimeError):
        return False
    fn(win_ptr, not region.isEmpty(), reg_ptr)
    return True
