"""Creative Shots – Bildschirmfotos wie mit dem Windows-11-Snipping-Tool.

Ablauf: Bildschirm „einfrieren“ (ganzer Bildschirm wird aufgenommen), darüber
eine Auswahl-Ebene je Monitor (Rechteck, Fenster, Vollbild, Freihand). Der
gewählte Ausschnitt wird automatisch in „Bilder/Bildschirmfotos“ gespeichert,
in die Zwischenablage kopiert und im Editor geöffnet (Stift, Textmarker,
Pfeil, Rechteck, Radierer, Zuschneiden).

Aufgenommen wird mit Spectacle im Hintergrund (das darf unter Wayland bei
KWin Bilder anfordern), ersatzweise über das Bildschirmfoto-Portal.
"""

import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QPointF,
    QRect,
    QRectF,
    SLOT,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)


def shots_dir():
    """~/Bilder/Bildschirmfotos (Ordnername wie in xdg-user-dirs)."""
    pictures = None
    try:
        r = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip() and r.stdout.strip() != str(Path.home()):
            pictures = Path(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    if pictures is None:
        pictures = Path.home() / ("Bilder" if (Path.home() / "Bilder").exists() else "Pictures")
    d = pictures / "Bildschirmfotos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def windows_file():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "creative-shell" / "windows.json"


def _runtime_tmp():
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    d = Path(base) / "creative-shots"
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


# ---- Anmerkungen auf das Bild malen (gleiche Regeln wie die Vorschau in QML) -----------------
def paint_strokes(img, strokes):
    if not strokes:
        return img
    out = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for s in strokes:
        pts = s.get("pts") or []
        if len(pts) < 2:
            continue
        color = QColor(s.get("color") or "#ff5a5a")
        width = float(s.get("width") or 4)
        tool = s.get("tool")
        if tool == "marker":
            color.setAlphaF(0.38)
            pen = QPen(color, width * 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin)
        else:
            pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        points = [QPointF(pts[i], pts[i + 1]) for i in range(0, len(pts) - 1, 2)]
        if tool in ("pen", "marker"):
            path = QPainterPath(points[0])
            for q in points[1:]:
                path.lineTo(q)
            p.drawPath(path)
        elif tool == "rect":
            a, b = points[0], points[-1]
            p.drawRoundedRect(QRectF(a, b).normalized(), 3, 3)
        elif tool == "arrow":
            a, b = points[0], points[-1]
            p.drawLine(a, b)
            ang = math.atan2(b.y() - a.y(), b.x() - a.x())
            head = max(12.0, width * 4)
            left = QPointF(b.x() - head * math.cos(ang - 0.45), b.y() - head * math.sin(ang - 0.45))
            right = QPointF(b.x() - head * math.cos(ang + 0.45), b.y() - head * math.sin(ang + 0.45))
            p.setBrush(QBrush(color))
            p.drawPolygon(QPolygonF([b, left, right]))
    p.end()
    return out


class Shots(QObject):
    changed = Signal()
    overlayChanged = Signal()
    messageChanged = Signal()
    showEditor = Signal()
    hideEditor = Signal()
    _captured = Signal(str, str)        # Pfad, Fehler

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "rect"
        self._delay = 0
        self._full = None              # QImage des ganzen Bildschirms
        self._full_path = ""
        self._image = None             # aktueller Ausschnitt (QImage)
        self._image_url = ""
        self._saved = ""
        self._overlay = False
        self._windows = []
        self._message = ""
        self._busy = False
        self._close_after = False
        self._union = QRect()
        self._captured.connect(self._on_captured)
        self._msg_timer = QTimer(self)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(lambda: self._set_message(""))
        self._portal_token = ""

    # ---- Aufnahme ---------------------------------------------------------------------------
    @Slot()
    def newCapture(self):
        """Aus dem Fenster: ausblenden, Verzögerung abwarten, aufnehmen."""
        if self._busy:
            return
        self.hideEditor.emit()
        wait = 450 + self._delay * 1000
        if self._delay:
            self._set_message(f"Aufnahme in {self._delay} Sekunden …")
        QTimer.singleShot(wait, self._capture)

    @Slot()
    def startSnip(self):
        """Win+Umschalt+S / Druck-Taste: sofort Auswahl zeigen."""
        self._capture()

    def _capture(self):
        if self._busy:
            return
        self._busy = True
        path = str(_runtime_tmp() / f"voll-{uuid.uuid4().hex[:8]}.png")

        def work():
            err = ""
            if shutil.which("spectacle"):
                try:
                    subprocess.run(["spectacle", "-b", "-n", "-f", "-o", path],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                except (OSError, subprocess.SubprocessError) as exc:
                    err = str(exc)
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                self._captured.emit("", err or "portal")
                return
            self._captured.emit(path, "")
        threading.Thread(target=work, daemon=True).start()

    def _on_captured(self, path, err):
        if not path and err == "portal":
            if self._portal_capture():
                return
            err = "keine Aufnahme möglich"
        self._busy = False
        if not path:
            self._set_message("Das Bildschirmfoto hat nicht geklappt (" + err + ").")
            self.showEditor.emit()
            return
        img = QImage(path)
        if img.isNull():
            self._set_message("Das Bildschirmfoto ließ sich nicht lesen.")
            self.showEditor.emit()
            return
        self._full, self._full_path = img, path
        union = QRect()
        for s in QGuiApplication.screens():
            union = union.united(s.geometry())
        self._union = union
        self._windows = self._read_windows()
        self._overlay = True
        self.overlayChanged.emit()

    # Ersatzweg über xdg-desktop-portal (fragt beim ersten Mal ggf. nach Erlaubnis)
    def _portal_capture(self):
        try:
            from PySide6.QtDBus import QDBusConnection, QDBusMessage
        except ImportError:
            return False
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return False
        self._portal_token = "creativeshots" + uuid.uuid4().hex[:8]
        sender = bus.baseService().lstrip(":").replace(".", "_")
        handle = f"/org/freedesktop/portal/desktop/request/{sender}/{self._portal_token}"
        bus.connect("org.freedesktop.portal.Desktop", handle, "org.freedesktop.portal.Request", "Response",
                    self, SLOT("_portal_response(uint,QVariantMap)"))
        msg = QDBusMessage.createMethodCall("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                                            "org.freedesktop.portal.Screenshot", "Screenshot")
        msg.setArguments(["", {"handle_token": self._portal_token, "interactive": False}])
        reply = bus.call(msg)
        return reply.type() != QDBusMessage.MessageType.ErrorMessage

    @Slot(int, "QVariantMap")
    def _portal_response(self, code, results):
        uri = (results or {}).get("uri", "")
        path = QUrl(uri).toLocalFile() if uri else ""
        self._captured.emit(path if code == 0 and path else "", "" if path else "Portal abgelehnt")

    def _read_windows(self):
        try:
            data = json.loads(windows_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for w in data.get("windows", []):
            geo = w.get("geo") or [0, 0, 0, 0]
            if w.get("minimized") or geo[2] < 20 or geo[3] < 20:
                continue
            if (w.get("app") or "").startswith("creative-shots"):
                continue
            out.append({"x": geo[0], "y": geo[1], "w": geo[2], "h": geo[3], "z": w.get("z", 0),
                        "title": w.get("title") or ""})
        out.sort(key=lambda w: -w["z"])           # oberstes Fenster zuerst
        return out

    # ---- Auswahl aus der Ebene (logische, globale Koordinaten) ----------------------------------------
    def _scale(self):
        if not self._full or self._union.width() <= 0:
            return 1.0
        return self._full.width() / self._union.width()

    def _to_image_rect(self, x, y, w, h):
        k = self._scale()
        r = QRect(round((x - self._union.x()) * k), round((y - self._union.y()) * k), round(w * k), round(h * k))
        return r.intersected(self._full.rect())

    @Slot(float, float, float, float)
    def selectRect(self, x, y, w, h):
        if not self._full or w < 3 or h < 3:
            return
        self._finish(self._full.copy(self._to_image_rect(x, y, w, h)))

    @Slot(int)
    def selectWindow(self, index):
        if 0 <= index < len(self._windows):
            w = self._windows[index]
            self.selectRect(w["x"], w["y"], w["w"], w["h"])

    @Slot(float, float, float, float)
    def selectScreen(self, x, y, w, h):
        self.selectRect(x, y, w, h)

    @Slot("QVariantList")
    def selectFree(self, pts):
        """Freihand: alles außerhalb der gezeichneten Form wird durchsichtig."""
        if not self._full or len(pts) < 6:
            return
        k = self._scale()
        poly = QPolygonF([QPointF((pts[i] - self._union.x()) * k, (pts[i + 1] - self._union.y()) * k)
                          for i in range(0, len(pts) - 1, 2)])
        box = poly.boundingRect().toAlignedRect().intersected(self._full.rect())
        if box.width() < 3 or box.height() < 3:
            return
        out = QImage(box.size(), QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addPolygon(poly.translated(-box.x(), -box.y()))
        path.closeSubpath()
        p.setClipPath(path)
        p.drawImage(0, 0, self._full, box.x(), box.y(), box.width(), box.height())
        p.end()
        self._finish(out)

    @Slot()
    def cancel(self):
        self._overlay = False
        self.overlayChanged.emit()
        self._drop_full()
        if self._close_after and self._image is None:
            QGuiApplication.quit()
            return
        self.showEditor.emit()

    def _drop_full(self):
        if self._full_path:
            try:
                os.unlink(self._full_path)
            except OSError:
                pass
        self._full, self._full_path = None, ""

    def _finish(self, img):
        self._overlay = False
        self.overlayChanged.emit()
        self._drop_full()
        name = time.strftime("Bildschirmfoto %Y-%m-%d %H%M%S.png")
        target = shots_dir() / name
        if img.save(str(target), "PNG"):
            self._saved = str(target)
        else:
            self._saved = ""
        QGuiApplication.clipboard().setImage(img)
        self._set_image(img)
        self._set_message("In die Zwischenablage kopiert und unter „Bilder › Bildschirmfotos“ gespeichert.")
        self.showEditor.emit()

    def _set_image(self, img):
        self._image = img
        path = _runtime_tmp() / f"bild-{uuid.uuid4().hex[:8]}.png"
        old = QUrl(self._image_url).toLocalFile() if self._image_url else ""
        img.save(str(path), "PNG")
        self._image_url = QUrl.fromLocalFile(str(path)).toString()
        if old and old.startswith(str(_runtime_tmp())):
            try:
                os.unlink(old)
            except OSError:
                pass
        self.changed.emit()

    # ---- Editor ------------------------------------------------------------------------------------------
    def _rendered(self, strokes):
        return paint_strokes(self._image, strokes or []) if self._image is not None else None

    @Slot("QVariantList")
    def copy(self, strokes):
        img = self._rendered(strokes)
        if img is not None:
            QGuiApplication.clipboard().setImage(img)
            self._set_message("In die Zwischenablage kopiert.")

    @Slot("QVariantList", result=bool)
    def save(self, strokes):
        img = self._rendered(strokes)
        if img is None:
            return False
        target = self._saved or str(shots_dir() / time.strftime("Bildschirmfoto %Y-%m-%d %H%M%S.png"))
        if img.save(target):
            self._saved = target
            self._set_message(f"Gespeichert: {Path(target).name}")
            self.changed.emit()
            return True
        self._set_message("Speichern hat nicht geklappt.")
        return False

    @Slot("QVariantList", str, result=bool)
    def saveAs(self, strokes, url):
        img = self._rendered(strokes)
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        if img is None or not path:
            return False
        if not os.path.splitext(path)[1]:
            path += ".png"
        if img.save(path):
            self._saved = path
            self._set_message(f"Gespeichert: {Path(path).name}")
            self.changed.emit()
            return True
        self._set_message("Speichern hat nicht geklappt.")
        return False

    @Slot("QVariantList", float, float, float, float)
    def crop(self, strokes, x, y, w, h):
        """Zuschneiden (Bild-Koordinaten). Anmerkungen werden vorher eingebrannt."""
        img = self._rendered(strokes)
        if img is None:
            return
        r = QRect(round(x), round(y), round(w), round(h)).intersected(img.rect())
        if r.width() < 2 or r.height() < 2:
            return
        self._set_image(img.copy(r))

    @Slot()
    def openFolder(self):
        folder = str(Path(self._saved).parent) if self._saved else str(shots_dir())
        for cmd in (["creative-files", folder], ["xdg-open", folder]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return

    @Slot()
    def openInPictures(self):
        if self._saved and shutil.which("creative-pictures"):
            subprocess.Popen(["creative-pictures", self._saved], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()
        if text:
            self._msg_timer.start(4500)

    # ---- Eigenschaften -------------------------------------------------------------------------------------
    def _set_mode(self, m):
        if m != self._mode:
            self._mode = m
            self.changed.emit()

    def _set_delay(self, d):
        if d != self._delay:
            self._delay = int(d)
            self.changed.emit()

    def set_close_after(self, on):
        self._close_after = on

    mode = Property(str, lambda self: self._mode, _set_mode, notify=changed)
    delay = Property(int, lambda self: self._delay, _set_delay, notify=changed)
    imageUrl = Property(str, lambda self: self._image_url, notify=changed)
    imageWidth = Property(int, lambda self: self._image.width() if self._image is not None else 0, notify=changed)
    imageHeight = Property(int, lambda self: self._image.height() if self._image is not None else 0, notify=changed)
    hasImage = Property(bool, lambda self: self._image is not None, notify=changed)
    savedName = Property(str, lambda self: Path(self._saved).name if self._saved else "", notify=changed)
    overlay = Property(bool, lambda self: self._overlay, notify=overlayChanged)
    fullUrl = Property(str, lambda self: QUrl.fromLocalFile(self._full_path).toString() if self._full_path else "", notify=overlayChanged)
    fullWidth = Property(int, lambda self: self._full.width() if self._full else 0, notify=overlayChanged)
    unionX = Property(int, lambda self: self._union.x(), notify=overlayChanged)
    unionY = Property(int, lambda self: self._union.y(), notify=overlayChanged)
    scale = Property(float, _scale, notify=overlayChanged)
    windows = Property("QVariantList", lambda self: self._windows, notify=overlayChanged)
    message = Property(str, lambda self: self._message, notify=messageChanged)
