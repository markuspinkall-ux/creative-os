"""Creative Engine – Spiele bauen per Klick: Genre wählen, Ablauf (Splash → Menü → Level) gestalten,
testen und als fertiges Spiel exportieren."""

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import icons, project as proj, runner
from .leveleditor import LevelEditor
from .screens import ScreenEditor
from .style import C, apply_palette, stylesheet

APP_NAME = "Creative Engine"
STEP_ICON = {"splash": "splash", "menu": "menu", "text": "text", "level": "level", "seite": "bubble"}
STEP_NAME = {"splash": "Splash", "menu": "Menü", "text": "Zwischentext", "level": "Level", "seite": "Seite"}
STEP_KINDS = ("level", "seite", "splash", "menu", "text")


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-engine"


def projects_dir():
    return Path.home() / "Creative Engine"


def recent_list():
    try:
        items = json.loads((config_dir() / "zuletzt.json").read_text(encoding="utf-8"))
        return [p for p in items if (Path(p) / "projekt.json").exists()][:8]
    except (OSError, ValueError):
        return []


def remember(folder):
    items = [str(folder)] + [p for p in recent_list() if p != str(folder)]
    config_dir().mkdir(parents=True, exist_ok=True)
    (config_dir() / "zuletzt.json").write_text(json.dumps(items[:8]), encoding="utf-8")


def genre_art(key, w=300, h=150):
    """Kleine Illustration für die Genre-Karten."""
    pm = QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QLinearGradient, QPolygonF
    sky = QLinearGradient(0, 0, 0, h)
    colors = {"jumpnrun": ("#7fb8ff", "#cfe6ff"), "adventure": ("#7ec8a6", "#e3f2d9"),
              "rennen-strecke": ("#ffb07a", "#ffe2c9"), "rennen-welt": ("#c3a6ff", "#ebe0ff")}[key]
    sky.setColorAt(0, QColor(colors[0]))
    sky.setColorAt(1, QColor(colors[1]))
    path_rect = QRectF(0, 0, w, h)
    from PySide6.QtGui import QPainterPath
    clip = QPainterPath()
    clip.addRoundedRect(path_rect, 14, 14)
    p.setClipPath(clip)
    p.fillRect(path_rect, sky)
    p.setPen(Qt.PenStyle.NoPen)
    if key == "jumpnrun":
        p.setBrush(QColor("#9fc7ef"))
        p.drawEllipse(QPointF(70, 150), 110, 70)
        p.drawEllipse(QPointF(240, 160), 120, 80)
        p.setBrush(QColor("#7a5a3a"))
        p.drawRect(QRectF(0, 118, 110, 40))
        p.drawRect(QRectF(150, 118, 160, 40))
        p.setBrush(QColor("#5fb04a"))
        p.drawRect(QRectF(0, 112, 110, 10))
        p.drawRect(QRectF(150, 112, 160, 10))
        p.setBrush(QColor("#a8794a"))
        p.drawRoundedRect(QRectF(170, 72, 70, 12), 3, 3)
        p.setBrush(QColor("#ffd24a"))
        for x in (185, 205, 225):
            p.drawEllipse(QPointF(x, 60), 5, 5)
        p.setBrush(QColor("#ff6b6b"))
        p.drawEllipse(QRectF(250, 96, 20, 16))
        p.setBrush(QColor("#3d6fe0"))
        p.drawRoundedRect(QRectF(118, 64, 18, 30), 8, 8)
        p.setBrush(QColor("#ffffff"))
        p.drawRect(QRectF(285, 60, 3, 52))
        p.setBrush(QColor("#1f9e7f"))
        p.drawRect(QRectF(288, 60, 18, 12))
    elif key == "adventure":
        p.setBrush(QColor("#8fbf8a"))
        p.drawPolygon(QPolygonF([QPointF(0, 120), QPointF(80, 50), QPointF(170, 120)]))
        p.setBrush(QColor("#6da36a"))
        p.drawPolygon(QPolygonF([QPointF(110, 120), QPointF(210, 40), QPointF(320, 120)]))
        p.setBrush(QColor("#5c8f4f"))
        p.drawRect(QRectF(0, 115, w, 40))
        p.setBrush(QColor("#c9b08a"))
        p.drawRect(QRectF(60, 85, 60, 35))
        p.setBrush(QColor("#b0603f"))
        p.drawPolygon(QPolygonF([QPointF(52, 88), QPointF(90, 62), QPointF(128, 88)]))
        p.setBrush(QColor("#8a93a3"))
        p.drawRect(QRectF(170, 95, 90, 20))
    elif key == "rennen-strecke":
        p.setBrush(QColor("#7fbf6a"))
        p.drawRect(QRectF(0, 70, w, 90))
        p.setBrush(QColor("#4a4f5c"))
        p.drawEllipse(QRectF(30, 62, 240, 80))
        p.setBrush(QColor("#7fbf6a"))
        p.drawEllipse(QRectF(80, 82, 140, 40))
        p.setBrush(QColor("#ff6b6b"))
        p.drawRoundedRect(QRectF(140, 128, 26, 12), 4, 4)
    else:
        p.setBrush(QColor("#9a8fc4"))
        for i, (x, hh) in enumerate(((20, 60), (60, 90), (110, 50), (200, 80), (250, 65))):
            p.drawRect(QRectF(x, 120 - hh, 36, hh))
        p.setBrush(QColor("#4a4f5c"))
        p.drawRect(QRectF(0, 118, w, 40))
        p.setBrush(QColor("#ffd24a"))
        p.drawRoundedRect(QRectF(120, 128, 30, 14), 4, 4)
    p.end()
    return pm


class GenreCard(QPushButton):
    def __init__(self, key, name, text, enabled):
        super().__init__()
        self.setObjectName("card")
        self.setFixedSize(QSize(316, 268))
        self.setEnabled(enabled)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 14)
        v.setSpacing(6)
        art = QLabel()
        art.setPixmap(genre_art(key))
        art.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if not enabled:
            art.setGraphicsEffect(None)
        v.addWidget(art)
        t = QLabel(name + ("" if enabled else "  ·  bald"))
        t.setStyleSheet("font-size:16px;font-weight:700;padding:2px 6px" + ("" if enabled else f";color:{C['dim']}"))
        d = QLabel(text)
        d.setWordWrap(True)
        d.setStyleSheet(f"color:{C['muted'] if enabled else C['dim']};padding:0 6px")
        for l in (t, d):
            l.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            v.addWidget(l)
        v.addStretch(1)


class Welcome(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(56, 40, 56, 40)
        v.setSpacing(10)
        title = QLabel("Was für ein Spiel baust du?")
        title.setObjectName("heading")
        v.addWidget(title)
        sub = QLabel("Wähle ein Genre – die Creative Engine richtet Kamera, Steuerung und Spielregeln passend ein.")
        sub.setObjectName("sub")
        v.addWidget(sub)
        v.addSpacing(12)
        grid = QGridLayout()
        grid.setSpacing(18)
        for i, (key, (name, text, enabled)) in enumerate(proj.GENRES.items()):
            card = GenreCard(key, name, text, enabled)
            card.clicked.connect(lambda _=False, k=key: self.win.new_project(k))
            grid.addWidget(card, i // 4, i % 4)
        grid.setColumnStretch(4, 1)
        v.addLayout(grid)
        v.addSpacing(26)
        self.recent_label = QLabel("ZULETZT GEÖFFNET", objectName="section")
        v.addWidget(self.recent_label)
        self.recent = QListWidget()
        self.recent.setMaximumWidth(720)
        self.recent.itemClicked.connect(lambda it: self.win.open_project(it.data(Qt.ItemDataRole.UserRole)))
        v.addWidget(self.recent)
        row = QHBoxLayout()
        open_btn = QPushButton("Projekt öffnen …")
        open_btn.setIcon(icons.icon("open", C["text"]))
        open_btn.clicked.connect(self.win.ask_open)
        row.addWidget(open_btn)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)

    def refresh(self):
        self.recent.clear()
        items = recent_list()
        self.recent_label.setVisible(bool(items))
        self.recent.setVisible(bool(items))
        for folder in items:
            try:
                data = json.loads((Path(folder) / "projekt.json").read_text(encoding="utf-8"))
                name = data.get("name", Path(folder).name)
                genre = proj.GENRES.get(data.get("genre"), ("",))[0]
            except (OSError, ValueError):
                continue
            it = QListWidgetItem(icons.icon("gamepad", C["accent"]), f"{name}    ·    {genre}    ·    {folder}")
            it.setData(Qt.ItemDataRole.UserRole, folder)
            self.recent.addItem(it)
        self.recent.setFixedHeight(min(6, max(1, len(items))) * 40 + 8)


class Timeline(QListWidget):
    """Ablauf des Spiels: Karten von links nach rechts, per Ziehen umsortierbar."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("timeline")
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setFixedHeight(84)
        self.setIconSize(QSize(22, 22))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.menu)
        self.model().rowsMoved.connect(self.moved)

    def fill(self, flow, current=None):
        self.blockSignals(True)
        self.clear()
        for i, step in enumerate(flow):
            name = step.get("name") or STEP_NAME[step["type"]]
            kind = STEP_NAME[step["type"]]
            sub = "" if name.startswith(kind) else kind
            if step["type"] in ("seite", "text", "splash"):
                dur = float(step.get("duration", 0) or 0)
                sub = (sub + " · " if sub else "") + (f"{dur:g} s".replace(".", ",") if dur > 0 else "bis Taste")
            label = f"{i + 1} · {name}" + (f"\n{sub}" if sub else "")
            it = QListWidgetItem(icons.icon(STEP_ICON[step["type"]], C["text"], C["accent"]), label)
            it.setData(Qt.ItemDataRole.UserRole, step["id"])
            it.setSizeHint(QSize(178, 62))
            self.addItem(it)
            if step["id"] == current:
                self.setCurrentItem(it)
        self.blockSignals(False)

    def moved(self, *_):
        order = [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]
        flow = self.win.project["flow"]
        flow.sort(key=lambda s: order.index(s["id"]))
        self.win.touched()
        QTimer.singleShot(0, lambda: self.win.refresh_timeline())

    def menu(self, pos):
        it = self.itemAt(pos)
        m = QMenu(self)
        if it is not None:
            index = self.row(it)
            m.addAction(icons.icon("play", C["text"], C["accent"]), "Ab hier testen", lambda: self.win.play(index))
            m.addAction(icons.icon("text", C["text"]), "Umbenennen …", lambda: self.win.rename_step(index))
            m.addAction(icons.icon("duplicate", C["text"]), "Duplizieren", lambda: self.win.duplicate_step(index))
            m.addSeparator()
            m.addAction(icons.icon("trash", C["danger"]), "Entfernen", lambda: self.win.remove_step(index))
            m.addSeparator()
        add = m.addMenu(icons.icon("plus", C["text"]), "Schritt hinzufügen")
        for kind in STEP_KINDS:
            add.addAction(icons.icon(STEP_ICON[kind], C["text"], C["accent"]), STEP_NAME[kind],
                          lambda k=kind: self.win.add_step(k))
        m.exec(self.mapToGlobal(pos))


class GameSettings(QWidget):
    """Spielfigur und Fenster: Modell, Tempo, Sprungkraft, Leben, Auflösung."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)
        title = QLabel("Spieleinstellungen")
        title.setObjectName("heading")
        outer.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.player_box = QWidget(objectName="panel")
        self.window_box = QWidget(objectName="panel")
        row.addWidget(self.player_box)
        row.addWidget(self.window_box)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.pf = QFormLayout(self.player_box)
        self.pf.setContentsMargins(20, 18, 20, 18)
        self.wf = QFormLayout(self.window_box)
        self.wf.setContentsMargins(20, 18, 20, 18)
        self.player_box.setMinimumWidth(380)
        self.window_box.setMinimumWidth(320)

    def load(self, data):
        for form in (self.pf, self.wf):
            while form.rowCount():
                form.removeRow(0)
        pl, st = data["player"], data["settings"]
        head = QLabel("SPIELFIGUR", objectName="section")
        self.pf.addRow(head)
        self.model_btn = QPushButton(Path(pl.get("model", "")).name or "Standardfigur")
        self.model_btn.setIcon(icons.icon("model", C["accent"]))
        self.model_btn.clicked.connect(lambda: self.win.choose_model_for(pl, self.model_btn))
        self.pf.addRow("3D-Modell (GLB)", self.model_btn)
        char = QPushButton("Charakter-Editor öffnen …")
        char.setIcon(icons.icon("bone", C["text"], C["accent"]))
        char.clicked.connect(self.win.open_character_editor)
        self.pf.addRow("Bewegungen", char)
        for key, label, lo, hi, step, default in (("height", "Größe (Meter)", 0.3, 6, 0.1, 1.6),
                                                  ("speed", "Lauftempo", 1, 30, 0.5, 7.0),
                                                  ("jump", "Sprungkraft", 2, 40, 0.5, 12.0)):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setValue(float(pl.get(key, default)))
            s.valueChanged.connect(lambda v, k=key: self.set(pl, k, v))
            self.pf.addRow(label, s)
        lives = QSpinBox()
        lives.setRange(1, 99)
        lives.setValue(int(pl.get("lives", 3)))
        lives.valueChanged.connect(lambda v: self.set(pl, "lives", v))
        self.pf.addRow("Leben", lives)

        self.wf.addRow(QLabel("FENSTER", objectName="section"))
        res = QComboBox()
        for w, h in ((1280, 720), (1600, 900), (1920, 1080), (2560, 1440)):
            res.addItem(f"{w} × {h}", (w, h))
        idx = res.findData((st.get("width", 1280), st.get("height", 720)))
        res.setCurrentIndex(max(0, idx))
        res.currentIndexChanged.connect(lambda _i: (self.set(st, "width", res.currentData()[0]),
                                                    self.set(st, "height", res.currentData()[1])))
        self.wf.addRow("Auflösung", res)
        full = QCheckBox("Im Vollbild starten")
        full.setChecked(bool(st.get("fullscreen")))
        full.toggled.connect(lambda v: self.set(st, "fullscreen", v))
        self.wf.addRow("", full)
        keys = QLabel("<b>Steuerung im Spiel</b><br>← → oder A D: laufen<br>Leertaste, W oder ↑: springen<br>"
                      "Esc: Pause<br>Gamepad wird automatisch erkannt.")
        keys.setObjectName("sub")
        self.wf.addRow(keys)

    def set(self, target, key, value):
        target[key] = value
        self.win.touched()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.icon("gamepad", C["accent"]))
        self.resize(1440, 900)
        self.folder = None
        self.project = None
        self.dirty = False
        self.current = None
        self.player = runner.Player(self)
        self.player.message.connect(self.status_msg)
        self.player.stopped.connect(lambda: self.play_btn.setText("Testen"))

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Kopfzeile
        top = QWidget(objectName="topBar")
        th = QHBoxLayout(top)
        th.setContentsMargins(14, 10, 14, 10)
        th.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("gamepad", C["accent"], 24))
        th.addWidget(logo)
        name = QLabel(APP_NAME, objectName="appTitle")
        th.addWidget(name)
        self.project_label = QLabel("", objectName="projectName")
        th.addWidget(self.project_label)
        th.addStretch(1)
        self.file_btn = QToolButton()
        self.file_btn.setText("Datei")
        self.file_btn.setIcon(icons.icon("folder", C["text"]))
        self.file_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.file_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        fm = QMenu(self)
        fm.addAction(icons.icon("new", C["text"]), "Neues Spiel …", self.go_home)
        fm.addAction(icons.icon("open", C["text"]), "Öffnen …", self.ask_open)
        fm.addAction(icons.icon("save", C["text"]), "Speichern", self.save)
        fm.addAction(icons.icon("folder", C["text"]), "Projektordner anzeigen",
                     lambda: self.folder and __import__("subprocess").Popen(["xdg-open", str(self.folder)]))
        self.file_btn.setMenu(fm)
        th.addWidget(self.file_btn)
        self.nav = {}
        for key, icon, text in (("flow", "level", "Ablauf"), ("settings", "settings", "Spieleinstellungen"),
                                ("character", "bone", "Charakter-Editor")):
            b = QToolButton()
            b.setText(text)
            b.setIcon(icons.icon(icon, C["text"], C["accent"]))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setCheckable(key != "character")
            b.clicked.connect(lambda _=False, k=key: self.show_section(k))
            th.addWidget(b)
            self.nav[key] = b
        th.addSpacing(10)
        self.play_btn = QPushButton("Testen")
        self.play_btn.setObjectName("primary")
        self.play_btn.setIcon(icons.icon("play", C["accentText"], C["accentText"]))
        self.play_btn.clicked.connect(lambda: self.play())
        self.export_btn = QPushButton("Exportieren")
        self.export_btn.setIcon(icons.icon("export", C["text"]))
        self.export_btn.clicked.connect(self.export)
        th.addWidget(self.play_btn)
        th.addWidget(self.export_btn)
        v.addWidget(top)
        self.project_only = [self.file_btn.menu().actions()[2], self.play_btn, self.export_btn] + list(self.nav.values())

        # Ablauf-Leiste
        self.flow_bar = QWidget(objectName="topBar")
        fh = QHBoxLayout(self.flow_bar)
        fh.setContentsMargins(14, 0, 14, 8)
        fh.setSpacing(8)
        self.timeline = Timeline(self)
        self.timeline.currentRowChanged.connect(self.select_step)
        fh.addWidget(self.timeline, 1)
        add = QToolButton()
        add.setIcon(icons.icon("plus", C["text"]))
        add.setToolTip("Schritt hinzufügen")
        add.setIconSize(QSize(22, 22))
        add.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        am = QMenu(self)
        for kind in STEP_KINDS:
            am.addAction(icons.icon(STEP_ICON[kind], C["text"], C["accent"]), STEP_NAME[kind],
                         lambda k=kind: self.add_step(k))
        add.setMenu(am)
        fh.addWidget(add)
        v.addWidget(self.flow_bar)

        self.stack = QStackedWidget()
        self.welcome = Welcome(self)
        self.screens = ScreenEditor(self)
        self.levels = LevelEditor(self)
        self.settings = GameSettings(self)
        for w in (self.welcome, self.screens, self.levels, self.settings):
            self.stack.addWidget(w)
        self.screens.changed.connect(self.touched)
        self.screens.changed.connect(lambda: self.project and self.refresh_timeline())
        self.levels.changed.connect(self.touched)
        self.levels.importModel.connect(self.import_decor)
        self.levels.view.status.connect(self.status_msg)
        v.addWidget(self.stack, 1)

        bar = QWidget(objectName="statusBar")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(14, 5, 14, 5)
        self.status = QLabel("")
        self.problems = QLabel("")
        bh.addWidget(self.status, 1)
        bh.addWidget(self.problems)
        v.addWidget(bar)

        save = QAction(self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        undo = QAction(self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.triggered.connect(lambda: self.stack.currentWidget() is self.levels and self.levels.view.undo())
        redo = QAction(self)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.triggered.connect(lambda: self.stack.currentWidget() is self.levels and self.levels.view.redo())
        play = QAction(self)
        play.setShortcut(QKeySequence("F5"))
        play.triggered.connect(lambda: self.project and self.play())
        self.addActions([save, undo, redo, play])
        self.autosave = QTimer(self)
        self.autosave.setInterval(30000)
        self.autosave.timeout.connect(lambda: self.dirty and self.save(quiet=True))
        self.autosave.start()
        self.go_home()

    # ---- Projekt ------------------------------------------------------------------------
    def go_home(self):
        if not self.maybe_save():
            return
        self.project = None
        self.folder = None
        self.welcome.refresh()
        self.stack.setCurrentWidget(self.welcome)
        self.flow_bar.hide()
        for w in self.project_only:
            w.setEnabled(False)
        self.project_label.setText("")
        self.status_msg("Wähle ein Genre oder öffne ein Projekt.")

    def new_project(self, genre):
        name, ok = QInputDialog.getText(self, "Neues Spiel", "Wie soll dein Spiel heißen?", text="Mein Spiel")
        if not ok or not name.strip():
            return
        name = name.strip()
        base = projects_dir() / proj.slug(name)
        folder, n = base, 2
        while folder.exists():
            folder = Path(f"{base} {n}")
            n += 1
        data = proj.new_project(name, genre)
        proj.save(folder, data)
        self.load(folder, data)

    def ask_open(self):
        d = QFileDialog.getExistingDirectory(self, "Projektordner öffnen", str(projects_dir()))
        if d:
            self.open_project(d)

    def open_project(self, folder):
        if not self.maybe_save():
            return
        try:
            data = proj.load(folder)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, APP_NAME, f"Das Projekt lässt sich nicht öffnen:\n{exc}")
            return
        self.load(Path(folder), data)

    def load(self, folder, data):
        self.folder, self.project = Path(folder), data
        self.dirty = False
        remember(self.folder)
        for w in self.project_only:
            w.setEnabled(True)
        self.flow_bar.show()
        self.project_label.setText(f"·  {data['name']}")
        self.settings.load(data)
        self.refresh_models()
        first_level = next((s for s in data["flow"] if s["type"] == "level"), data["flow"][0] if data["flow"] else None)
        self.current = first_level["id"] if first_level else None
        self.refresh_timeline()
        self.show_section("flow")
        self.check()
        self.status_msg("Projekt geöffnet – Ablauf oben, Werkzeuge links, Eigenschaften rechts. F5 testet.")

    def maybe_save(self):
        if self.project and self.dirty:
            self.save(quiet=True)
        return True

    def save(self, quiet=False):
        if not self.project:
            return
        proj.save(self.folder, self.project)
        self.dirty = False
        self.setWindowTitle(f"{self.project['name']} – {APP_NAME}")
        if not quiet:
            self.status_msg("Gespeichert.")

    def touched(self):
        self.dirty = True
        self.setWindowTitle(f"{self.project['name']} • – {APP_NAME}")
        self.check()

    def check(self):
        problems = proj.validate(self.project) if self.project else []
        if problems:
            self.problems.setText("⚠ " + problems[0] + (f"  (+{len(problems) - 1})" if len(problems) > 1 else ""))
            self.problems.setStyleSheet(f"color:{C['flame']}")
        else:
            self.problems.setText("✓ Spielbereit" if self.project else "")
            self.problems.setStyleSheet(f"color:{C['ok']}")
        return problems

    def status_msg(self, text):
        self.status.setText(text)

    # ---- Ablauf -------------------------------------------------------------------------
    def refresh_timeline(self):
        self.timeline.fill(self.project["flow"], self.current)

    def step_index(self, sid):
        return next((i for i, s in enumerate(self.project["flow"]) if s["id"] == sid), -1)

    def select_step(self, row):
        if not self.project or row < 0 or row >= len(self.project["flow"]):
            return
        step = self.project["flow"][row]
        self.current = step["id"]
        self.nav["flow"].setChecked(True)
        self.nav["settings"].setChecked(False)
        if step["type"] == "level":
            self.levels.set_level(self.project["levels"][step["id"]])
            self.stack.setCurrentWidget(self.levels)
        else:
            self.screens.set_step(step)
            self.stack.setCurrentWidget(self.screens)

    def show_section(self, key):
        if key == "character":
            self.open_character_editor()
            return
        for k, b in self.nav.items():
            if b.isCheckable():
                b.setChecked(k == key)
        if key == "settings":
            self.timeline.clearSelection()
            self.settings.load(self.project)
            self.stack.setCurrentWidget(self.settings)
        else:
            row = max(0, self.step_index(self.current))
            self.timeline.setCurrentRow(row)
            self.select_step(row)

    def add_step(self, kind):
        index = self.step_index(self.current)
        step = proj.add_step(self.project, kind, index if index >= 0 else None)
        self.current = step["id"]
        self.touched()
        self.refresh_timeline()
        self.select_step(self.step_index(step["id"]))

    def remove_step(self, index):
        step = self.project["flow"][index]
        if QMessageBox.question(self, APP_NAME, f"„{step.get('name')}“ entfernen?") != QMessageBox.StandardButton.Yes:
            return
        proj.remove_step(self.project, index)
        flow = self.project["flow"]
        self.current = flow[min(index, len(flow) - 1)]["id"] if flow else None
        self.touched()
        self.refresh_timeline()
        if flow:
            self.select_step(self.step_index(self.current))

    def duplicate_step(self, index):
        step = proj.duplicate_step(self.project, index)
        self.current = step["id"]
        self.touched()
        self.refresh_timeline()
        self.select_step(index + 1)

    def rename_step(self, index):
        step = self.project["flow"][index]
        name, ok = QInputDialog.getText(self, "Umbenennen", "Name", text=step.get("name", ""))
        if ok and name.strip():
            step["name"] = name.strip()
            if step["type"] == "level":
                self.project["levels"][step["id"]]["name"] = step["name"]
            self.touched()
            self.refresh_timeline()

    # ---- Dateien ------------------------------------------------------------------------
    def import_file(self, title, filt):
        path, _ = QFileDialog.getOpenFileName(self, title, str(Path.home()), filt)
        if not path:
            return None
        rel = proj.import_asset(self.folder, path)
        self.touched()
        return rel

    def models(self):
        d = self.folder / "assets" if self.folder else None
        if not d or not d.exists():
            return []
        return sorted(f"assets/{p.name}" for p in d.iterdir() if p.suffix.lower() in (".glb", ".gltf"))

    def refresh_models(self):
        self.levels.refresh_models(self.models())

    def import_decor(self):
        rel = self.import_file("3D-Modell wählen", "3D-Modelle (*.glb)")
        if rel:
            self.refresh_models()
            self.levels.set_brush(("decor", rel))
            self.status_msg(f"{Path(rel).name} hinzugefügt – jetzt ins Level klicken.")

    def choose_model_for(self, target, button):
        m = QMenu(self)
        m.addAction("Standardfigur", lambda: self._set_model(target, button, ""))
        models = self.models()
        if models:
            m.addSeparator()
        for rel in models:
            m.addAction(icons.icon("model", C["accent"]), Path(rel).name, lambda r=rel: self._set_model(target, button, r))
        m.addSeparator()
        m.addAction(icons.icon("plus", C["text"]), "GLB-Datei laden …", lambda: self._import_model(target, button))
        m.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _import_model(self, target, button):
        rel = self.import_file("3D-Modell wählen", "3D-Modelle (*.glb)")
        if rel:
            self.refresh_models()
            self._set_model(target, button, rel)

    def _set_model(self, target, button, rel):
        target["model"] = rel
        button.setText(Path(rel).name or "Standardfigur")
        self.touched()

    def open_character_editor(self):
        if not self.project:
            return
        from .character import CharacterEditor
        dlg = CharacterEditor(self, self.folder, self.project)
        dlg.exec()
        self.refresh_models()
        self.settings.load(self.project)
        self.nav["character"].setChecked(False)

    # ---- Testen & Export ------------------------------------------------------------------
    def ready(self):
        problems = self.check()
        if problems:
            QMessageBox.information(self, APP_NAME, "Bevor es losgeht:\n\n• " + "\n• ".join(problems))
            return False
        return True

    def play(self, index=None):
        if not self.project or not self.ready():
            return
        if not runner.ensure_godot(self):
            return
        self.save(quiet=True)
        start = None
        if index is not None:
            start = self.project["flow"][index]["id"]
        elif self.stack.currentWidget() is self.levels:
            start = self.current
        self.player.play(self.folder, self.project, start)
        self.play_btn.setText("Neu starten")

    def export(self):
        if not self.project or not self.ready():
            return
        self.save(quiet=True)
        runner.ExportDialog(self, self.folder, self.project).exec()

    def closeEvent(self, event):
        self.maybe_save()
        self.player.stop()
        super().closeEvent(event)


def main():
    if "--selftest" in sys.argv:
        from . import selftest
        sys.exit(selftest.run())
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("org.creativeos.Engine")
    from PySide6.QtCore import QLocale
    QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Germany))
    app.setStyle("Fusion")
    apply_palette(app)
    app.setStyleSheet(stylesheet())
    win = Window()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and (Path(args[0]) / "projekt.json").exists():
        win.open_project(args[0])
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
