"""Magnetische Zeitleiste für Creative Cut (wie bei Final Cut).

Drei Spuren übereinander:
  Titel  – frei verschiebbare Titel-Blöcke
  Video  – Hauptspur: Clips liegen lückenlos hintereinander; Ziehen ordnet um
  Musik  – frei verschiebbare Musikstücke
Oben ein Zeitlineal; Klick ins Lineal oder auf eine leere Stelle setzt den Abspielkopf.
Strg + Mausrad zoomt.
"""

import hashlib
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from cut_project import LOOKS, layout, transition_lengths

GROUND = QColor("#12151b")
SURFACE = QColor("#1c2029")
RAISED = QColor("#232836")
TRACK = QColor("#3a4252")
TEXT = QColor("#dce6ff")
MUTED = QColor(220, 230, 255, 150)
ACCENT = QColor("#8fb3ff")
TITLE_COLOR = QColor("#ffb07a")
MUSIC_COLOR = QColor("#6fdcc0")
HAIR = QColor(255, 255, 255, 22)

RULER = 24
TITLE_Y, TITLE_H = 30, 30
VIDEO_Y, VIDEO_H = 66, 74
MUSIC_Y, MUSIC_H = 146, 38
HEIGHT = 194
PAD = 16                       # linker Rand in px
THUMB_W = 128
SNAP_PX = 8
CACHE = Path.home() / ".cache" / "creative-cut" / "thumbs"


def thumb_path(media_path, ms):
    key = hashlib.sha1(f"{media_path}|{ms}".encode()).hexdigest()[:20]
    return CACHE / f"{key}.jpg"


def clock(ms):
    s = max(0, ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


class TimelineView(QWidget):
    selected = Signal(str, int)          # ("clip"|"title"|"music"|"", index)
    seek = Signal(int)                   # ms in der Zeitleiste
    moved = Signal(int, int)             # Clip von → nach
    shifted = Signal(str, int, int)      # ("title"|"music", index, neue Startzeit ms)
    wantThumb = Signal(str, int, str)    # Quelle, ms, Zieldatei

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor             # liefert clips, titles, music
        self.pps = 60.0                  # Pixel pro Sekunde
        self.playhead = 0
        self.selection = ("", -1)
        self.drag = None                 # {"kind", "index", "x0", "orig", "x"}
        self.requested = set()
        self.pixmaps = {}
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMinimumHeight(HEIGHT)
        self.setAccessibleName("Zeitleiste")

    # ---- Umrechnung -------------------------------------------------------------------
    def x_of(self, ms):
        return PAD + ms * self.pps / 1000

    def ms_of(self, x):
        return max(0, round((x - PAD) * 1000 / self.pps))

    def total(self):
        _, total = layout(self.editor.clips)
        ends = [t.at + t.duration for t in self.editor.titles] + [m.at + m.duration for m in self.editor.music]
        return max([total] + ends)

    def sizeHint(self):
        return QSize(int(self.x_of(self.total())) + 400, HEIGHT)

    def relayout(self):
        self.setMinimumWidth(int(self.x_of(self.total())) + 400)
        self.updateGeometry()
        self.update()

    def set_zoom(self, pps):
        self.pps = min(400.0, max(8.0, pps))
        self.relayout()

    def set_playhead(self, ms):
        if ms != self.playhead:
            self.playhead = ms
            self.update()

    def thumb_ready(self, path):
        self.pixmaps.pop(path, None)
        self.update()

    # ---- Zeichnen ---------------------------------------------------------------------
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), GROUND)
        self.paint_ruler(p)
        for y, h, label in ((TITLE_Y, TITLE_H, "Titel"), (VIDEO_Y, VIDEO_H, "Video"), (MUSIC_Y, MUSIC_H, "Musik")):
            p.fillRect(QRectF(0, y - 2, self.width(), h + 4), SURFACE)
        clips = self.editor.clips
        starts, _ = layout(clips)
        trans = transition_lengths(clips)
        dragging_clip = self.drag and self.drag["kind"] == "clip" and self.drag.get("active")
        for i, (clip, start) in enumerate(zip(clips, starts)):
            rect = QRectF(self.x_of(start), VIDEO_Y, clip.length * self.pps / 1000, VIDEO_H)
            if dragging_clip and self.drag["index"] == i:
                p.setOpacity(0.35)
            self.paint_clip(p, rect, clip, ("clip", i) == self.selection)
            p.setOpacity(1)
        for i, t in enumerate(trans):
            if t:
                self.paint_transition(p, starts[i], t, clips[i].transition)
        if dragging_clip:
            self.paint_drop_marker(p)
        for i, title in enumerate(self.editor.titles):
            at = self.drag_at("title", i, title.at)
            rect = QRectF(self.x_of(at), TITLE_Y, max(6, title.duration * self.pps / 1000), TITLE_H)
            self.paint_block(p, rect, TITLE_COLOR, "T  " + title.text, ("title", i) == self.selection)
        for i, music in enumerate(self.editor.music):
            at = self.drag_at("music", i, music.at)
            rect = QRectF(self.x_of(at), MUSIC_Y, max(6, music.duration * self.pps / 1000), MUSIC_H)
            self.paint_music(p, rect, music, ("music", i) == self.selection)
        if not clips and not self.editor.titles and not self.editor.music:
            p.setPen(MUTED)
            p.setFont(QFont("Arial", 11))
            p.drawText(QRectF(PAD, VIDEO_Y, 600, VIDEO_H), Qt.AlignmentFlag.AlignVCenter,
                       "Videos importieren und mit „Zur Zeitleiste“ hinzufügen")
        # Abspielkopf
        x = self.x_of(self.playhead)
        p.setPen(QPen(ACCENT, 2))
        p.drawLine(QPointF(x, 4), QPointF(x, self.height()))
        p.setBrush(ACCENT)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(x - 6, 2), QPointF(x + 6, 2), QPointF(x, 12)]))
        p.end()

    def paint_ruler(self, p):
        p.fillRect(QRectF(0, 0, self.width(), RULER), GROUND)
        step = next(s for s in (1, 2, 5, 10, 15, 30, 60, 120, 300) if s * self.pps >= 70)
        p.setFont(QFont("Arial", 8))
        last = self.ms_of(self.width()) // 1000 + 1
        for s in range(0, last + step, step):
            x = self.x_of(s * 1000)
            p.setPen(QPen(HAIR, 1))
            p.drawLine(QPointF(x, RULER - 7), QPointF(x, RULER))
            p.setPen(MUTED)
            p.drawText(QPointF(x + 3, RULER - 9), clock(s * 1000))

    def rounded(self, rect, r=8):
        path = QPainterPath()
        path.addRoundedRect(rect, r, r)
        return path

    def paint_clip(self, p, rect, clip, selected):
        path = self.rounded(rect)
        p.fillPath(path, RAISED)
        # Filmstreifen aus Vorschaubildern
        p.save()
        p.setClipPath(path)
        n = max(1, min(12, int(rect.width() // THUMB_W) + 1))
        for k in range(n):
            x = rect.x() + k * THUMB_W
            if x > rect.right():
                break
            ms = clip.start + int(clip.duration * (k + 0.5) / n)
            ms -= ms % 500
            pix = self.thumb(clip.media.path, ms)
            if pix is not None and not pix.isNull():
                target = QRectF(x, rect.y(), THUMB_W, rect.height())
                p.drawPixmap(target, pix, QRectF(pix.rect()))
        p.fillRect(QRectF(rect.x(), rect.bottom() - 22, rect.width(), 22), QColor(18, 21, 27, 190))
        p.restore()
        # Beschriftung + Effekt-Abzeichen
        badges = []
        if clip.look:
            badges.append(LOOKS[clip.look])
        if clip.speed != 100:
            badges.append(f"{clip.speed / 100:g}×")
        if clip.reverse:
            badges.append("rückwärts")
        if clip.kenburns:
            badges.append("Zoom")
        if clip.title:
            badges.append("Titel")
        p.setPen(TEXT)
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        label = clip.media.name + ("   ·   " + " · ".join(badges) if badges else "")
        p.drawText(rect.adjusted(8, 0, -6, -4), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                   p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(rect.width() - 14)))
        p.setPen(QPen(ACCENT if selected else HAIR, 2.5 if selected else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def paint_transition(self, p, start, length, kind):
        rect = QRectF(self.x_of(start), VIDEO_Y + 6, max(10, length * self.pps / 1000), VIDEO_H - 34)
        path = self.rounded(rect, 6)
        p.fillPath(path, QColor(143, 179, 255, 70))
        p.setPen(QPen(ACCENT, 1.2))
        p.drawPath(path)
        p.setPen(TEXT)
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "⧓" if rect.width() < 60 else "⧓ Übergang")

    def paint_block(self, p, rect, color, text, selected):
        path = self.rounded(rect, 7)
        fill = QColor(color)
        fill.setAlpha(225)
        p.fillPath(path, fill)
        p.setPen(GROUND)
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.drawText(rect.adjusted(8, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width() - 14)))
        if selected:
            p.setPen(QPen(TEXT, 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

    def paint_music(self, p, rect, music, selected):
        self.paint_block(p, rect, MUSIC_COLOR, "♪  " + music.media.name, selected)
        # Ein-/Ausblend-Rampen
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 21, 27, 110))
        fi = music.fade_in * self.pps / 1000
        fo = music.fade_out * self.pps / 1000
        if fi > 2:
            p.drawPolygon(QPolygonF([rect.topLeft(), QPointF(rect.x() + fi, rect.y()), rect.bottomLeft()]))
        if fo > 2:
            p.drawPolygon(QPolygonF([rect.topRight(), QPointF(rect.right() - fo, rect.y()), rect.bottomRight()]))

    def paint_drop_marker(self, p):
        target = self.drop_index(self.drag["x"])
        starts, total = layout(self.editor.clips)
        ms = starts[target] if target < len(starts) else total
        x = self.x_of(ms)
        p.setPen(QPen(ACCENT, 3))
        p.drawLine(QPointF(x, VIDEO_Y - 4), QPointF(x, VIDEO_Y + VIDEO_H + 4))

    def thumb(self, media_path, ms):
        path = thumb_path(media_path, ms)
        key = str(path)
        if key in self.pixmaps:
            return self.pixmaps[key]
        if path.exists():
            pix = QPixmap(key)
            self.pixmaps[key] = pix
            return pix
        if key not in self.requested:
            self.requested.add(key)
            self.wantThumb.emit(media_path, ms, key)
        return None

    # ---- Maus ---------------------------------------------------------------------------
    def hit(self, pos):
        x, y = pos.x(), pos.y()
        if TITLE_Y <= y <= TITLE_Y + TITLE_H:
            for i in reversed(range(len(self.editor.titles))):
                t = self.editor.titles[i]
                if self.x_of(t.at) <= x <= self.x_of(t.at + t.duration):
                    return "title", i
        elif VIDEO_Y <= y <= VIDEO_Y + VIDEO_H:
            starts, _ = layout(self.editor.clips)
            for i in reversed(range(len(starts))):
                if self.x_of(starts[i]) <= x <= self.x_of(starts[i] + self.editor.clips[i].length):
                    return "clip", i
        elif MUSIC_Y <= y <= MUSIC_Y + MUSIC_H:
            for i in reversed(range(len(self.editor.music))):
                m = self.editor.music[i]
                if self.x_of(m.at) <= x <= self.x_of(m.at + m.duration):
                    return "music", i
        return "", -1

    def drop_index(self, x):
        starts, _ = layout(self.editor.clips)
        ms = self.ms_of(x)
        for i, (start, clip) in enumerate(zip(starts, self.editor.clips)):
            if ms < start + clip.length / 2:
                return i
        return len(starts)

    def drag_at(self, kind, index, at):
        d = self.drag
        if d and d.get("active") and d["kind"] == kind and d["index"] == index:
            return self.snap(max(0, d["orig"] + round((d["x"] - d["x0"]) * 1000 / self.pps)))
        return at

    def snap(self, ms):
        """Magnetisch: an Clip-Anfänge, Abspielkopf und Gesamtende einrasten."""
        starts, total = layout(self.editor.clips)
        for point in starts + [total, self.playhead]:
            if abs((point - ms) * self.pps / 1000) <= SNAP_PX:
                return point
        return ms - ms % 100

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        kind, index = self.hit(pos)
        self.selection = (kind, index)
        self.selected.emit(kind, index)
        if kind:
            orig = {"title": lambda: self.editor.titles[index].at,
                    "music": lambda: self.editor.music[index].at,
                    "clip": lambda: 0}[kind]()
            self.drag = {"kind": kind, "index": index, "x0": pos.x(), "x": pos.x(), "orig": orig, "active": False}
        else:
            self.seek.emit(self.ms_of(pos.x()))
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self.drag:
            self.drag["x"] = pos.x()
            if abs(pos.x() - self.drag["x0"]) > 4:
                self.drag["active"] = True
            self.update()
        elif event.buttons() & Qt.MouseButton.LeftButton and pos.y() < VIDEO_Y:
            self.seek.emit(self.ms_of(pos.x()))
        kind, _ = self.hit(pos)
        self.setCursor(Qt.CursorShape.OpenHandCursor if kind else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        d, self.drag = self.drag, None
        if not d:
            return
        if not d["active"]:
            if d["kind"] == "clip":           # Klick auf Clip: Abspielkopf dorthin
                self.seek.emit(self.ms_of(event.position().x()))
            self.update()
            return
        if d["kind"] == "clip":
            target = self.drop_index(d["x"])
            if target > d["index"]:
                target -= 1
            if target != d["index"]:
                self.moved.emit(d["index"], target)
        else:
            at = self.snap(max(0, d["orig"] + round((d["x"] - d["x0"]) * 1000 / self.pps)))
            if at != d["orig"]:
                self.shifted.emit(d["kind"], d["index"], at)
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.pps * (1.15 if event.angleDelta().y() > 0 else 1 / 1.15))
            event.accept()
        else:
            event.ignore()
