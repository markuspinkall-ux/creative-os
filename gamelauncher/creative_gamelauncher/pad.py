"""Controller lesen (Xbox, PlayStation, Switch Pro, Steam Controller …) über evdev.

Kein exklusiver Zugriff: Spiele und Steam bekommen die Tasten weiterhin. Das Fenster
reagiert nur, solange es aktiv ist (prüft die Oberfläche). Neu eingesteckte
Controller werden alle paar Sekunden erkannt.
"""

import threading
import time

try:
    import evdev
    from evdev import ecodes as E
except ImportError:          # ohne python3-evdev: nur Tastatur und Maus
    evdev = None

REPEAT_DELAY = 0.38
REPEAT_RATE = 0.11


def _buttons():
    return {
        E.BTN_SOUTH: "a", E.BTN_EAST: "b", E.BTN_NORTH: "y", E.BTN_WEST: "x",
        E.BTN_TL: "lb", E.BTN_TR: "rb", E.BTN_START: "menu", E.BTN_SELECT: "view", E.BTN_MODE: "guide",
        E.BTN_DPAD_LEFT: "left", E.BTN_DPAD_RIGHT: "right", E.BTN_DPAD_UP: "up", E.BTN_DPAD_DOWN: "down",
    }


class Pads:
    """Ruft on_action(name) aus einem Hintergrund-Thread auf (der Aufrufer reicht es weiter)."""

    def __init__(self, on_action, on_count=None):
        self._on_action = on_action
        self._on_count = on_count or (lambda n: None)
        self._devices = {}
        self._held = {}           # Richtung → (seit, zuletzt)
        self._axes = {}
        self._stop = threading.Event()
        self.available = evdev is not None

    def start(self):
        if evdev is None:
            return
        threading.Thread(target=self._loop, name="controller", daemon=True).start()

    def stop(self):
        self._stop.set()

    def _scan(self):
        known = set(self._devices)
        for path in evdev.list_devices():
            if path in known:
                continue
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities().get(E.EV_KEY, [])
                if E.BTN_SOUTH in caps or E.BTN_GAMEPAD in caps:
                    self._devices[path] = dev
                else:
                    dev.close()
            except OSError:
                pass
        self._on_count(len(self._devices))

    def _press(self, name):
        self._on_action(name)
        if name in ("left", "right", "up", "down"):
            now = time.monotonic()
            self._held[name] = [now, now]

    def _release(self, name):
        self._held.pop(name, None)

    def _axis(self, dev, code, value):
        """Stick und Steuerkreuz (als Achse) → Richtungen."""
        if code in (E.ABS_HAT0X, E.ABS_HAT0Y):
            neg, pos = ("left", "right") if code == E.ABS_HAT0X else ("up", "down")
            state = -1 if value < 0 else (1 if value > 0 else 0)
        elif code in (E.ABS_X, E.ABS_Y):
            info = dev.absinfo(code)
            mid = (info.max + info.min) / 2
            span = max(1, (info.max - info.min) / 2)
            v = (value - mid) / span
            neg, pos = ("left", "right") if code == E.ABS_X else ("up", "down")
            old = self._axes.get((dev.path, code), 0)
            state = -1 if v < -0.6 else (1 if v > 0.6 else (old if abs(v) > 0.35 else 0))
        else:
            return
        key = (dev.path, code)
        old = self._axes.get(key, 0)
        if state == old:
            return
        self._axes[key] = state
        if old:
            self._release(neg if old < 0 else pos)
        if state:
            self._press(neg if state < 0 else pos)

    def _loop(self):
        import select
        buttons = _buttons()
        last_scan = 0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_scan > 3:
                self._scan()
                last_scan = now
            fds = {dev.fd: dev for dev in self._devices.values()}
            if not fds:
                time.sleep(0.5)
                continue
            ready, _, _ = select.select(list(fds), [], [], 0.05)
            for fd in ready:
                dev = fds[fd]
                try:
                    for ev in dev.read():
                        if ev.type == E.EV_KEY and ev.code in buttons:
                            name = buttons[ev.code]
                            if ev.value == 1:
                                self._press(name)
                            elif ev.value == 0:
                                self._release(name)
                        elif ev.type == E.EV_ABS:
                            self._axis(dev, ev.code, ev.value)
                except OSError:          # abgesteckt
                    self._devices.pop(dev.path, None)
                    self._held.clear()
                    self._on_count(len(self._devices))
            # Richtungen wiederholen, solange gehalten
            now = time.monotonic()
            for name, times in list(self._held.items()):
                since, last = times
                if now - since > REPEAT_DELAY and now - last > REPEAT_RATE:
                    times[1] = now
                    self._on_action(name)
