"""Ergebnisse aus Hintergrund-Threads sicher in den Haupt-Thread bringen.

Ein Qt-Signal direkt aus einem Python-Thread auszulösen kann beim Start mit
PySide6 verklemmen: Der Thread hält die Python-Sperre (GIL) und wartet auf
Qts Signal-Sperre, während der Haupt-Thread genau umgekehrt wartet. Dann
zeichnet die Oberfläche nie – schwarzer Bildschirm, obwohl alles „läuft“.

Darum legen Threads ihre Ergebnisse hier ab (`post`), und ein Zeitgeber im
Haupt-Thread arbeitet sie ab. `install()` einmal nach dem Erzeugen der App.
"""

import queue
import traceback

from PySide6.QtCore import QTimer

_queue = queue.SimpleQueue()
_timer = None


def post(fn, *args):
    """fn(*args) im Haupt-Thread ausführen (aus jedem Thread aufrufbar)."""
    _queue.put((fn, args))


def _drain():
    for _ in range(500):
        try:
            fn, args = _queue.get_nowait()
        except queue.Empty:
            return
        try:
            fn(*args)
        except Exception:  # noqa: BLE001 – ein Fehler darf die Schlange nicht anhalten
            traceback.print_exc()


def install(interval_ms=25):
    global _timer
    if _timer is None:
        _timer = QTimer()
        _timer.setInterval(interval_ms)
        _timer.timeout.connect(_drain)
        _timer.start()
    return _timer
