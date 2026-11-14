"""Bildschirme über kscreen-doctor (KWin): Auflösung, Bildwiederholrate,
Skalierung, Ausrichtung, Hauptbildschirm, Anordnung.

Wie bei Windows: Nach „Übernehmen“ fragt das System 15 Sekunden lang, ob
alles passt. Ohne Bestätigung wird automatisch zurückgestellt – so bleibt
man nie mit einem schwarzen Bildschirm sitzen.
"""

import copy
import json
import subprocess

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from creative_shell.runner import Runner

ROTATIONS = {1: "normal", 2: "left", 4: "inverted", 8: "right"}
ROTATION_LABELS = {"normal": "Querformat", "left": "Hochformat (links)",
                   "right": "Hochformat (rechts)", "inverted": "Querformat (gedreht)"}
SCALES = [1.0, 1.25, 1.5, 1.75, 2.0]
CONFIRM_SECONDS = 15


def parse_outputs(data):
    outputs = []
    for o in data.get("outputs", []):
        if not o.get("connected", True):
            continue
        modes = []
        for m in o.get("modes", []):
            size = m.get("size") or {}
            w, h = int(size.get("width", 0)), int(size.get("height", 0))
            if w and h:
                modes.append({"id": str(m.get("id")), "w": w, "h": h,
                              "hz": round(float(m.get("refreshRate", 0)))})
        cur = str(o.get("currentModeId", ""))
        cur_mode = next((m for m in modes if m["id"] == cur), modes[0] if modes else {"id": "", "w": 1920, "h": 1080, "hz": 60})
        pos = o.get("pos") or {}
        outputs.append({
            "name": o.get("name", "?"),
            "enabled": bool(o.get("enabled", True)),
            "primary": int(o.get("priority", 0) or 0) == 1,
            "x": int(pos.get("x", 0)), "y": int(pos.get("y", 0)),
            "scale": float(o.get("scale", 1.0) or 1.0),
            "rotation": ROTATIONS.get(int(o.get("rotation", 1) or 1), "normal"),
            "modeId": cur_mode["id"], "modes": modes,
        })
    outputs.sort(key=lambda o: (o["x"], o["y"]))
    for n, o in enumerate(outputs, 1):
        o["number"] = n
    return outputs


def logical_size(o):
    mode = next((m for m in o["modes"] if m["id"] == o["modeId"]), None)
    w, h = (mode["w"], mode["h"]) if mode else (1920, 1080)
    if o["rotation"] in ("left", "right"):
        w, h = h, w
    return round(w / o["scale"]), round(h / o["scale"])


def tidy_layout(outputs):
    """Ordnet eingeschaltete Bildschirme lückenlos nebeneinander an
    (Reihenfolge und Höhenversatz wie vom Benutzer gezogen)."""
    active = sorted([o for o in outputs if o["enabled"]], key=lambda o: o["x"])
    if not active:
        return
    x = 0
    top = min(o["y"] for o in active)
    for o in active:
        w, h = logical_size(o)
        o["x"] = x
        o["y"] = max(0, o["y"] - top)
        x += w


def build_commands(old, new):
    args = []
    old_by = {o["name"]: o for o in old}
    for o in new:
        p = old_by.get(o["name"], {})
        n = f"output.{o['name']}"
        if o["enabled"] != p.get("enabled"):
            args.append(f"{n}.{'enable' if o['enabled'] else 'disable'}")
        if not o["enabled"]:
            continue
        if o["modeId"] and o["modeId"] != p.get("modeId"):
            args.append(f"{n}.mode.{o['modeId']}")
        if o["scale"] != p.get("scale"):
            args.append(f"{n}.scale.{o['scale']:g}")
        if o["rotation"] != p.get("rotation"):
            args.append(f"{n}.rotation.{o['rotation']}")
        if (o["x"], o["y"]) != (p.get("x"), p.get("y")):
            args.append(f"{n}.position.{o['x']},{o['y']}")
    # Hauptbildschirm: Reihenfolge für alle setzen (1 = Haupt, die anderen danach)
    old_primary = next((o["name"] for o in old if o.get("primary")), None)
    new_primary = next((o["name"] for o in new if o["enabled"] and o["primary"]), None)
    if new_primary and new_primary != old_primary:
        rest = [o["name"] for o in sorted(new, key=lambda o: o["x"]) if o["enabled"] and o["name"] != new_primary]
        for i, name in enumerate([new_primary] + rest, 1):
            args.append(f"output.{name}.priority.{i}")
    return args


def tell_shell():
    """Taskleiste/Schreibtisch sofort auf den neuen Hauptbildschirm umstellen."""
    try:
        subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.creativeos.Shell", "--object-path", "/Shell",
                          "--method", "org.creativeos.Shell.refreshScreens"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


class DisplayModel(QObject):
    changed = Signal()
    selectionChanged = Signal()   # eigenes Signal: sonst baut die Vorschau beim Anklicken neu auf und Ziehen geht nicht
    confirmChanged = Signal()
    messageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self)
        self._applied = []     # Stand des Systems
        self._edit = []        # Stand in der Oberfläche
        self._backup = None    # Stand vor „Übernehmen“ (für Zurück)
        self._selected = 0
        self._seconds = 0
        self._message = ""
        self._available = True
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self.changed.connect(self.selectionChanged)    # Details folgen jeder Änderung
        self.refresh()

    # ---- Laden ------------------------------------------------------------------
    @Slot()
    def refresh(self):
        self._run.run(["kscreen-doctor", "-j"], self._on_json)

    def _on_json(self, code, out, _err):
        if code == 127:
            self._available = False
            self._set_message("Die Bildschirm-Steuerung (kscreen-doctor) ist nicht installiert.")
            self.changed.emit()
            return
        try:
            start = out.index("{")
            data = json.loads(out[start:])
        except ValueError:
            self._set_message("Die Bildschirme konnten nicht gelesen werden.")
            return
        self._applied = parse_outputs(data)
        if self._seconds == 0:
            self._edit = copy.deepcopy(self._applied)
        self._selected = min(self._selected, max(0, len(self._edit) - 1))
        self.changed.emit()

    # ---- Bearbeiten ------------------------------------------------------------
    def _cur(self):
        return self._edit[self._selected] if 0 <= self._selected < len(self._edit) else None

    @Slot(int)
    def select(self, i):
        if 0 <= i < len(self._edit) and i != self._selected:
            self._selected = i
            self.selectionChanged.emit()

    @Slot(str)
    def setResolution(self, text):
        o = self._cur()
        if not o:
            return
        w, h = (int(v) for v in text.split(" × "))
        same = [m for m in o["modes"] if m["w"] == w and m["h"] == h]
        if same:
            cur = next((m for m in o["modes"] if m["id"] == o["modeId"]), None)
            best = min(same, key=lambda m: abs(m["hz"] - (cur["hz"] if cur else 60)))
            o["modeId"] = best["id"]
            self.changed.emit()

    @Slot(str)
    def setRate(self, text):
        o = self._cur()
        cur = next((m for m in o["modes"] if m["id"] == o["modeId"]), None) if o else None
        if not cur:
            return
        hz = int(text.split()[0])
        m = next((m for m in o["modes"] if m["w"] == cur["w"] and m["h"] == cur["h"] and m["hz"] == hz), None)
        if m:
            o["modeId"] = m["id"]
            self.changed.emit()

    @Slot(str)
    def setScale(self, text):
        o = self._cur()
        if o:
            o["scale"] = int(text.rstrip(" %")) / 100
            self.changed.emit()

    @Slot(str)
    def setRotation(self, label):
        o = self._cur()
        key = next((k for k, v in ROTATION_LABELS.items() if v == label), None)
        if o and key:
            o["rotation"] = key
            self.changed.emit()

    @Slot()
    def makePrimary(self):
        o = self._cur()
        if o:
            for x in self._edit:
                x["primary"] = x is o
            self.changed.emit()

    @Slot(bool)
    def setEnabled(self, on):
        o = self._cur()
        if not o:
            return
        if not on and sum(1 for x in self._edit if x["enabled"]) <= 1:
            self._set_message("Mindestens ein Bildschirm muss eingeschaltet bleiben.")
            return
        o["enabled"] = on
        if not on and o["primary"]:
            other = next(x for x in self._edit if x["enabled"])
            o["primary"], other["primary"] = False, True
        self.changed.emit()

    @Slot(int, int, int)
    def moveTo(self, i, x, y):
        """Neue Position aus der Vorschau (in Bildschirm-Pixeln)."""
        if 0 <= i < len(self._edit):
            self._edit[i]["x"], self._edit[i]["y"] = int(x), int(y)
            tidy_layout(self._edit)
            self.changed.emit()

    @Slot()
    def reset(self):
        self._edit = copy.deepcopy(self._applied)
        self.changed.emit()

    # ---- Übernehmen mit Rückfrage ---------------------------------------------------
    @Slot()
    def apply(self):
        tidy_layout(self._edit)
        args = build_commands(self._applied, self._edit)
        if not args:
            self._set_message("Es gibt keine Änderungen.")
            return
        self._backup = copy.deepcopy(self._applied)
        self._set_message("")
        self._run.run(["kscreen-doctor"] + args, self._after_apply)

    def _after_apply(self, code, _out, err):
        if code != 0:
            self._set_message("Das hat nicht geklappt – die Einstellung wird nicht unterstützt.")
            self._backup = None
            self.refresh()
            return
        self._seconds = CONFIRM_SECONDS
        self._tick.start()
        self.confirmChanged.emit()
        QTimer.singleShot(800, self.refresh)
        QTimer.singleShot(900, tell_shell)

    def _on_tick(self):
        self._seconds -= 1
        self.confirmChanged.emit()
        if self._seconds <= 0:
            self.revert()

    @Slot()
    def keep(self):
        self._tick.stop()
        self._seconds = 0
        self._backup = None
        self.confirmChanged.emit()
        self.refresh()

    @Slot()
    def revert(self):
        self._tick.stop()
        self._seconds = 0
        self.confirmChanged.emit()
        if self._backup is not None:
            args = build_commands(self._applied, self._backup)
            self._edit = copy.deepcopy(self._backup)
            self._backup = None
            if args:
                self._run.run(["kscreen-doctor"] + args, lambda *_: (QTimer.singleShot(800, self.refresh),
                                                                      QTimer.singleShot(900, tell_shell)))
            self._set_message("Die vorherige Einstellung wurde wiederhergestellt.")
        self.changed.emit()

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    # ---- Für die Oberfläche ------------------------------------------------------
    def _screens(self):
        result = []
        for i, o in enumerate(self._edit):
            w, h = logical_size(o)
            mode = next((m for m in o["modes"] if m["id"] == o["modeId"]), None)
            result.append({
                "index": i, "number": o["number"], "name": o["name"], "enabled": o["enabled"],
                "primary": o["primary"], "x": o["x"], "y": o["y"], "w": w, "h": h,
                "resolution": f"{mode['w']} × {mode['h']}" if mode else "",
                # So wie der Bildschirm steht (hochkant: 1080 × 1920)
                "shown": (f"{min(mode['w'], mode['h'])} × {max(mode['w'], mode['h'])}" if h > w
                          else f"{max(mode['w'], mode['h'])} × {min(mode['w'], mode['h'])}") if mode else "",
                "portrait": h > w,
            })
        return result

    def _details(self):
        o = self._cur()
        if not o:
            return {}
        mode = next((m for m in o["modes"] if m["id"] == o["modeId"]), None)
        res = sorted({(m["w"], m["h"]) for m in o["modes"]}, reverse=True)
        rates = sorted({m["hz"] for m in o["modes"] if mode and m["w"] == mode["w"] and m["h"] == mode["h"]}, reverse=True)
        scales = SCALES if o["scale"] in SCALES else sorted(SCALES + [o["scale"]])
        return {
            "number": o["number"], "name": o["name"], "enabled": o["enabled"], "primary": o["primary"],
            "resolution": f"{mode['w']} × {mode['h']}" if mode else "",
            "resolutions": [f"{w} × {h}" for w, h in res],
            "rate": f"{mode['hz']} Hz" if mode else "",
            "rates": [f"{r} Hz" for r in rates],
            "scale": f"{round(o['scale'] * 100)} %",
            "scales": [f"{round(s * 100)} %" for s in scales],
            "rotation": ROTATION_LABELS[o["rotation"]],
            "rotations": list(ROTATION_LABELS.values()),
        }

    screens = Property("QVariantList", _screens, notify=changed)
    selected = Property(int, lambda self: self._selected, notify=selectionChanged)
    details = Property("QVariantMap", _details, notify=selectionChanged)
    dirty = Property(bool, lambda self: bool(build_commands(self._applied, self._edit)), notify=changed)
    confirmSeconds = Property(int, lambda self: self._seconds, notify=confirmChanged)
    message = Property(str, lambda self: self._message, notify=messageChanged)
    available = Property(bool, lambda self: self._available, notify=changed)
