"""Charakter-Editor: GLB-Figur laden, Skelett-Punkte setzen, Bewegungen per KI-Beschreibung oder Reglern
erstellen, in der Vorschau ansehen und festen Plätzen (Stehen, Gehen, Springen …) zuweisen."""

import copy
import math
import os
import shutil
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QProcess, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from . import icons, project as proj, skeleton as S
from .style import C

CLAUDE_CANDIDATES = (Path.home() / ".local/share/creative-claude/bin/claude", Path.home() / ".local/bin/claude")


def claude_command():
    """Befehl für Claude (Creative Claude) – im Flatpak über den Host."""
    in_flatpak = os.path.exists("/.flatpak-info")
    for candidate in CLAUDE_CANDIDATES:
        if candidate.is_file():
            return (["flatpak-spawn", "--host", str(candidate)] if in_flatpak else [str(candidate)])
    found = shutil.which("claude")
    if found and not in_flatpak:
        return [found]
    if in_flatpak and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host", "claude"]
    return None


def guess(description):
    """Regler aus einer Beschreibung schätzen (wenn keine KI da ist)."""
    d = description.lower()
    p = {"tempo": 1.0, "stride": 28.0, "arms": 24.0, "waddle": 0.0, "flap": 0.0, "bounce": 1.0, "lean": 0.0}
    if any(w in d for w in ("ente", "watschel", "pinguin", "wackel")):
        p.update(waddle=16, stride=16, tempo=1.25, arms=8)
    if any(w in d for w in ("schlacker", "flatter", "fuchtel", "wedel", "schlenker")):
        p.update(flap=45, arms=40)
    if any(w in d for w in ("schnell", "hektisch", "eilig", "flink")):
        p["tempo"] *= 1.4
    if any(w in d for w in ("langsam", "gemütlich", "müde", "schlurf")):
        p.update(tempo=p["tempo"] * 0.7, stride=p["stride"] * 0.7, bounce=0.5)
    if any(w in d for w in ("stolz", "aufrecht", "soldat", "marsch")):
        p.update(stride=36, arms=40, lean=-4)
    if any(w in d for w in ("gebückt", "schleich", "geduckt", "alt")):
        p.update(lean=18, stride=18)
    if any(w in d for w in ("hüpf", "federnd", "fröhlich", "beschwingt")):
        p["bounce"] = 2.5
    if any(w in d for w in ("roboter", "steif", "zombie")):
        p.update(arms=4, bounce=0.2, stride=20)
    return p


class Preview(QWidget):
    """Einfache 3D-Vorschau (Dreiecke, sanft beleuchtet), Maus ziehen = drehen."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 420)
        self.mesh = None
        self.joints = None
        self.base = None
        self.weights = None
        self.anim = None
        self.t = 0.0
        self.yaw = math.radians(35)
        self.pitch = math.radians(8)
        self.drag = None
        self.show_bones = True
        self.label = ""
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)

    def set_mesh(self, mesh, joints):
        v, f, c = S.simplify(mesh["vertices"], mesh["faces"], mesh["colors"], 2600)
        self.mesh = (v, f, c)
        self.set_joints(joints)

    def set_joints(self, joints):
        self.joints = joints
        if joints is not None and self.mesh is not None:
            self.base = S.base_pose(joints)
            self.weights = S.R.skin_weights(self.mesh[0], joints)
        self.update()

    def play(self, anim, label=""):
        self.anim = anim
        self.label = label
        self.t = 0.0
        if anim and not self.timer.isActive():
            self.timer.start()
        if not anim:
            self.timer.stop()
        self.update()

    def tick(self):
        self.t += 0.033
        if self.anim and not self.anim.get("loop", True) and self.t > self.anim["length"] + 0.6:
            self.t = 0.0
        self.update()

    def mousePressEvent(self, e):
        self.drag = e.position()

    def mouseMoveEvent(self, e):
        if self.drag is not None:
            d = e.position() - self.drag
            self.drag = e.position()
            self.yaw += d.x() * 0.01
            self.pitch = max(-1.2, min(1.2, self.pitch + d.y() * 0.01))
            self.update()

    def mouseReleaseEvent(self, e):
        self.drag = None

    def posed(self):
        v, f, c = self.mesh
        if self.joints is None or self.weights is None:
            return v, None
        rots, dy = ({}, 0.0)
        if self.anim:
            rots, dy = S.rotations_at(self.anim, min(self.t, self.anim["length"]) if not self.anim.get("loop", True) else self.t)
        height = float(self.joints["HeadTop_End"][1])
        wr, wt = S.pose_matrices(self.joints, rots, self.base, dy * height)
        return S.skin(v, self.joints, self.weights, wr, wt), wt

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(C["view"]))
        if self.mesh is None:
            p.setPen(QColor(C["muted"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Lade eine Figur (GLB), um loszulegen.")
            return
        v, f, c = self.mesh
        verts, joint_pos = self.posed()
        rot = S.rot_x(self.pitch) @ S.rot_y(self.yaw)
        lo, hi = self.mesh[0].min(0), self.mesh[0].max(0)
        center = np.array([0, (lo[1] + hi[1]) / 2, 0])
        size = max(hi - lo) * 1.25
        r = QRectF(self.rect()).adjusted(20, 20, -20, -20)
        scale = min(r.width(), r.height()) / size
        cam = (verts - center) @ rot.T
        sx = r.center().x() + cam[:, 0] * scale
        sy = r.center().y() - cam[:, 1] * scale
        # Boden
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        floor_y = r.center().y() - ((np.array([0, lo[1], 0]) - center) @ rot.T)[1] * scale
        p.drawEllipse(QPointF(r.center().x(), floor_y), size * 0.32 * scale, size * 0.32 * scale * abs(math.sin(self.pitch) + 0.15))
        tri = cam[f]
        normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nl = np.linalg.norm(normal, axis=1)
        normal = normal / np.maximum(nl[:, None], 1e-12)
        light = np.array([-0.4, 0.6, 0.7])
        light /= np.linalg.norm(light)
        shade = 0.35 + 0.65 * np.abs(normal @ light)
        col = c[f].mean(1)[:, :3] * shade[:, None]
        depth = tri[:, :, 2].mean(1)
        order = np.argsort(depth)
        for i in order:
            a, b, d = f[i]
            rgb = np.clip(col[i] * 255, 0, 255).astype(int)
            qc = QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
            p.setBrush(qc)
            p.setPen(QPen(qc, 0.6))
            p.drawPolygon(QPolygonF([QPointF(sx[a], sy[a]), QPointF(sx[b], sy[b]), QPointF(sx[d], sy[d])]))
        if self.show_bones and joint_pos is not None:
            pts = {}
            for name, pos in joint_pos.items():
                q = (pos - center) @ rot.T
                pts[name] = QPointF(r.center().x() + q[0] * scale, r.center().y() - q[1] * scale)
            p.setPen(QPen(QColor(C["accent"]), 2))
            for name, parent in S.PARENT.items():
                if parent:
                    p.drawLine(pts[parent], pts[name])
            p.setBrush(QColor(C["accent"]))
            for pt in pts.values():
                p.drawEllipse(pt, 3, 3)
        if self.label:
            p.setPen(QColor(C["muted"]))
            p.drawText(QRectF(self.rect()).adjusted(14, 10, -14, -10),
                       Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self.label)


class CharacterEditor(QDialog):
    def __init__(self, win, folder, data):
        super().__init__(win)
        self.win, self.folder, self.project = win, Path(folder), data
        self.setWindowTitle("Charakter-Editor")
        self.resize(1320, 820)
        self.store = data.setdefault("characters", {})
        self.source = None
        self.mesh = None
        self.oriented = None
        self.joints = None
        self.current = None
        self.proc = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Kopf
        top = QWidget(objectName="topBar")
        th = QHBoxLayout(top)
        th.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Charakter-Editor")
        title.setStyleSheet("font-size:18px;font-weight:700")
        th.addWidget(title)
        th.addSpacing(16)
        th.addWidget(QLabel("Figur"))
        self.models = QComboBox()
        self.models.setMinimumWidth(240)
        self.models.activated.connect(lambda _i: self.load(self.models.currentData()))
        th.addWidget(self.models)
        add = QPushButton("GLB laden …")
        add.setIcon(icons.icon("plus", C["text"]))
        add.clicked.connect(self.import_model)
        th.addWidget(add)
        turn = QPushButton("Drehen 90°")
        turn.setToolTip("Falls die Figur nicht nach vorn schaut")
        turn.clicked.connect(self.turn)
        th.addWidget(turn)
        self.rig_btn = QPushButton("Skelett-Punkte setzen …")
        self.rig_btn.setIcon(icons.icon("bone", C["text"], C["accent"]))
        self.rig_btn.clicked.connect(self.edit_rig)
        th.addWidget(self.rig_btn)
        th.addStretch(1)
        self.bones = QCheckBox("Skelett zeigen")
        self.bones.setChecked(True)
        self.bones.toggled.connect(lambda on: (setattr(self.preview, "show_bones", on), self.preview.update()))
        th.addWidget(self.bones)
        root.addWidget(top)

        body = QHBoxLayout()
        body.setSpacing(0)
        root.addLayout(body, 1)

        # Feste Plätze (links)
        slots = QWidget(objectName="side")
        slots.setFixedWidth(300)
        sv = QVBoxLayout(slots)
        sv.setContentsMargins(14, 14, 14, 14)
        sv.setSpacing(8)
        sv.addWidget(QLabel("FESTE PLÄTZE", objectName="section"))
        hint = QLabel("Das Spiel spielt diese Bewegungen automatisch: Stehen, wenn die Figur still ist, "
                      "Gehen/Rennen je nach Tempo, Springen und Fallen in der Luft, Jubeln im Ziel, Treffer bei Schaden.")
        hint.setWordWrap(True)
        hint.setObjectName("sub")
        sv.addWidget(hint)
        self.slot_rows = {}
        grid = QGridLayout()
        grid.setSpacing(6)
        attack_names = [a.get("name", "") for a in data["player"].get("attacks", [])]
        row_no = 0
        for key, name in S.SLOTS + S.ATTACK_SLOTS:
            if key == "attack1":
                head = QLabel("ANGRIFFE", objectName="section")
                head.setContentsMargins(0, 10, 0, 0)
                grid.addWidget(head, row_no, 0, 1, 3)
                tip = QLabel("Taste, Reichweite und Schaden stellst du unter Spieleinstellungen → Angriffe ein.")
                tip.setWordWrap(True)
                tip.setObjectName("sub")
                grid.addWidget(tip, row_no + 1, 0, 1, 3)
                row_no += 2
            if key.startswith("attack"):
                n = int(key[-1]) - 1
                if n < len(attack_names) and attack_names[n]:
                    name = f"{name}: {attack_names[n]}"
            row_no += 2
            label = QLabel(name)
            label.setStyleSheet("font-weight:700")
            state = QLabel("–")
            state.setObjectName("sub")
            play = QPushButton()
            play.setObjectName("ghost")
            play.setIcon(icons.icon("play", C["text"], C["accent"]))
            play.setToolTip("Ansehen")
            play.clicked.connect(lambda _=False, k=key: self.show_slot(k))
            assign = QPushButton("Zuweisen")
            assign.setToolTip("Die Bewegung aus der Vorschau hier speichern")
            assign.clicked.connect(lambda _=False, k=key: self.assign(k))
            r0 = row_no - 2
            grid.addWidget(label, r0, 0)
            grid.addWidget(play, r0, 1)
            grid.addWidget(assign, r0, 2)
            grid.addWidget(state, r0 + 1, 0, 1, 3)
            self.slot_rows[key] = (state, play, assign)
        sv.addLayout(grid)
        sv.addStretch(1)
        slot_scroll = QScrollArea()
        slot_scroll.setWidgetResizable(True)
        slot_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        slot_scroll.setFixedWidth(310)
        slot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        slot_scroll.setWidget(slots)
        body.addWidget(slot_scroll)

        # Vorschau (Mitte)
        mid = QVBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        self.preview = Preview()
        mid.addWidget(self.preview, 1)
        body.addLayout(mid, 1)

        # Bewegung erstellen (rechts)
        side = QWidget(objectName="props")
        side.setFixedWidth(360)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setFixedWidth(360)
        scroll.setWidget(side)
        rv = QVBoxLayout(side)
        rv.setContentsMargins(16, 14, 16, 14)
        rv.setSpacing(8)
        rv.addWidget(QLabel("NEUE BEWEGUNG", objectName="section"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Für"))
        self.kind = QComboBox()
        for key, name in S.SLOTS:
            self.kind.addItem(name, key)
        for key, name in S.ATTACK_SLOTS:
            self.kind.addItem(f"{name} ({S.ATTACK_STYLE[key]})", key)
        self.kind.setCurrentIndex(1)
        self.kind.currentIndexChanged.connect(lambda _i: self.from_sliders())
        row.addWidget(self.kind, 1)
        rv.addLayout(row)
        self.desc = QPlainTextEdit()
        self.desc.setPlaceholderText("Beschreibe die Bewegung, z. B.: „watschelt wie eine Ente und schlackert mit den Armen“")
        self.desc.setFixedHeight(92)
        rv.addWidget(self.desc)
        self.ai_btn = QPushButton("Mit KI erstellen")
        self.ai_btn.setObjectName("primary")
        self.ai_btn.setIcon(icons.icon("ai", C["accentText"]))
        self.ai_btn.clicked.connect(self.ask_ai)
        rv.addWidget(self.ai_btn)
        self.ai_state = QLabel("")
        self.ai_state.setWordWrap(True)
        self.ai_state.setObjectName("sub")
        rv.addWidget(self.ai_state)
        rv.addSpacing(8)
        rv.addWidget(QLabel("ODER MIT REGLERN", objectName="section"))
        self.sliders = {}
        form = QFormLayout()
        for key, label, lo, hi, default, factor in (("tempo", "Tempo", 30, 250, 100, 100), ("stride", "Schrittweite", 0, 60, 28, 1),
                                                    ("arms", "Armschwung", 0, 80, 24, 1), ("waddle", "Watscheln", 0, 30, 0, 1),
                                                    ("flap", "Arme schlackern", 0, 80, 0, 1), ("bounce", "Federn", 0, 40, 10, 10),
                                                    ("lean", "Vorbeugen", -15, 30, 0, 1)):
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(lo, hi)
            s.setValue(default)
            s.valueChanged.connect(lambda _v: self.from_sliders())
            self.sliders[key] = (s, factor)
            form.addRow(label, s)
        rv.addLayout(form)
        guess_btn = QPushButton("Regler aus Beschreibung schätzen")
        guess_btn.clicked.connect(self.guess_from_text)
        rv.addWidget(guess_btn)
        rv.addStretch(1)
        body.addWidget(scroll)

        bottom = QWidget(objectName="statusBar")
        bh = QHBoxLayout(bottom)
        bh.setContentsMargins(16, 10, 16, 10)
        self.state = QLabel("")
        bh.addWidget(self.state, 1)
        self.as_player = QCheckBox("Als Spielfigur verwenden")
        self.as_player.setChecked(True)
        bh.addWidget(self.as_player)
        cancel = QPushButton("Schließen")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Figur speichern")
        self.save_btn.setObjectName("primary")
        self.save_btn.setIcon(icons.icon("save", C["accentText"]))
        self.save_btn.clicked.connect(self.save)
        bh.addWidget(cancel)
        bh.addWidget(self.save_btn)
        root.addWidget(bottom)

        self.fill_models()
        start = data["player"].get("model", "")
        src = next((k for k, v in self.store.items() if v.get("output") == start), None)
        if src or self.models.count():
            self.load(src or self.models.itemData(0))
        self.enable()

    # ---- Figur --------------------------------------------------------------------------
    def fill_models(self):
        self.models.clear()
        outputs = {v.get("output") for v in self.store.values()}
        d = self.folder / "assets"
        if d.exists():
            for f in sorted(d.iterdir()):
                rel = f"assets/{f.name}"
                if f.suffix.lower() == ".glb" and rel not in outputs:
                    self.models.addItem(icons.icon("model", C["accent"]), f.stem, rel)

    def import_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Figur wählen", str(Path.home()), "3D-Figuren (*.glb)")
        if path:
            rel = proj.import_asset(self.folder, path)
            self.fill_models()
            self.load(rel)

    def load(self, rel):
        if not rel:
            return
        try:
            self.mesh = S.load_mesh(self.folder / rel)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Charakter-Editor", f"Die Figur lässt sich nicht laden:\n{exc}")
            return
        self.source = rel
        i = self.models.findData(rel)
        if i >= 0:
            self.models.setCurrentIndex(i)
        entry = self.store.setdefault(rel, {"turns": 0, "slots": {}})
        self.oriented = S.orient(self.mesh, entry.get("turns", 0))
        if entry.get("joints"):
            self.joints = {k: np.array(v, float) for k, v in entry["joints"].items()}
        else:
            self.joints = S.fit(self.oriented["vertices"])
        self.preview.set_mesh(self.oriented, self.joints)
        self.from_sliders()
        self.refresh_slots()
        tris = len(self.mesh["faces"])
        self.state.setText(f"{Path(rel).name}: {tris:,} Dreiecke".replace(",", ".")
                           + ("" if entry.get("joints") else " – Skelett automatisch eingepasst, bitte prüfen."))
        self.enable()

    def enable(self):
        has = self.mesh is not None
        for w in (self.rig_btn, self.ai_btn, self.save_btn):
            w.setEnabled(has)

    def turn(self):
        if not self.source:
            return
        entry = self.store[self.source]
        entry["turns"] = (entry.get("turns", 0) + 1) % 4
        entry.pop("joints", None)
        self.oriented = S.orient(self.mesh, entry["turns"])
        self.joints = S.fit(self.oriented["vertices"])
        self.preview.set_mesh(self.oriented, self.joints)

    def edit_rig(self):
        from creative3d_rigeditor import RigDialog
        dlg = RigDialog(self, self.oriented["vertices"], self.joints, probe=False)
        dlg.probe.hide()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.joints = {k: np.array(v, float) for k, v in dlg.joints.items()}
            self.store[self.source]["joints"] = {k: [round(float(x), 5) for x in v] for k, v in self.joints.items()}
            self.preview.set_joints(self.joints)
            self.state.setText("Skelett übernommen.")

    # ---- Bewegungen ---------------------------------------------------------------------
    def slider_values(self):
        return {k: s.value() / f for k, (s, f) in self.sliders.items()}

    def from_sliders(self):
        if self.joints is None:
            return
        kind = self.kind.currentData()
        anim = S.preset(kind, **self.slider_values())
        anim["name"] = f"{S.SLOT_NAME[kind]} (Regler)"
        anim["source"] = {"regler": self.slider_values()}
        self.current = anim
        self.preview.play(anim, f"Vorschau: {anim['name']}")

    def guess_from_text(self):
        values = guess(self.desc.toPlainText())
        for k, v in values.items():
            s, f = self.sliders[k]
            s.blockSignals(True)
            s.setValue(int(round(v * f)))
            s.blockSignals(False)
        self.from_sliders()

    def ask_ai(self):
        text = self.desc.toPlainText().strip()
        if not text:
            self.ai_state.setText("Schreib zuerst, wie sich die Figur bewegen soll.")
            return
        cmd = claude_command()
        if not cmd:
            self.guess_from_text()
            self.ai_state.setText("Claude ist nicht eingerichtet (Creative Claude). Ich habe die Regler aus deiner "
                                  "Beschreibung geschätzt – feinjustieren und zuweisen.")
            return
        prompt = S.ai_prompt(text, self.kind.currentData(), self.joints)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.finished.connect(self.ai_done)
        self.proc.errorOccurred.connect(lambda _e: self.ai_failed("Claude ließ sich nicht starten."))
        self.proc.start(cmd[0], cmd[1:] + ["-p", prompt, "--output-format", "text"])
        self.ai_btn.setEnabled(False)
        self.ai_btn.setText("KI denkt nach …")
        self.ai_state.setText("Claude entwirft die Bewegung (dauert meist 10–40 Sekunden).")
        self.ai_timeout = QTimer.singleShot(240000, lambda: self.proc and self.proc.state() != QProcess.ProcessState.NotRunning
                                            and self.proc.kill())

    def ai_failed(self, why):
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("Mit KI erstellen")
        self.ai_state.setText(why)
        self.ai_state.setStyleSheet(f"color:{C['danger']}")

    def ai_done(self, code, _status):
        out = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(self.proc.readAllStandardError()).decode("utf-8", "replace")
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("Mit KI erstellen")
        try:
            anim = S.parse_ai(out)
        except (ValueError, TypeError) as exc:
            hint = err.strip().splitlines()[-1] if err.strip() else str(exc)
            if "login" in (out + err).lower() or "auth" in (out + err).lower():
                hint = "Bitte zuerst in Creative Claude anmelden."
            self.ai_failed(f"Das hat nicht geklappt: {hint[:200]}")
            return
        anim["source"] = {"ki": self.desc.toPlainText().strip()}
        self.ai_state.setStyleSheet("")
        self.ai_state.setText(f"Fertig: „{anim['name']}“ – sieh dir die Vorschau an und weise sie einem Platz zu.")
        self.current = anim
        self.preview.play(anim, f"Vorschau: {anim['name']} (KI)")

    def assign(self, slot):
        if not self.current or not self.source:
            return
        anim = copy.deepcopy(self.current)
        anim["loop"] = slot in S.LOOPING
        self.store[self.source]["slots"][slot] = anim
        self.refresh_slots()
        self.state.setText(f"„{anim['name']}“ ist jetzt {S.SLOT_NAME[slot]}.")

    def show_slot(self, slot):
        anim = self.store.get(self.source, {}).get("slots", {}).get(slot)
        if anim:
            self.preview.play(anim, f"{S.SLOT_NAME[slot]}: {anim.get('name', '')}")
            self.current = anim

    def refresh_slots(self):
        slots = self.store.get(self.source, {}).get("slots", {}) if self.source else {}
        for key, (state, play, _assign) in self.slot_rows.items():
            anim = slots.get(key)
            state.setText(anim.get("name", "") if anim else "– noch leer")
            play.setEnabled(bool(anim))

    # ---- Speichern ------------------------------------------------------------------------
    def save(self):
        if not self.source:
            return
        entry = self.store[self.source]
        entry["joints"] = {k: [round(float(x), 5) for x in v] for k, v in self.joints.items()}
        slots = dict(entry.get("slots", {}))
        if "idle" not in slots:
            slots["idle"] = S.preset("idle")
        out = f"assets/{Path(self.source).stem}-figur.glb"
        try:
            S.export(self.folder / out, self.oriented, self.joints, slots)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Charakter-Editor", f"Speichern fehlgeschlagen:\n{exc}")
            return
        entry["output"] = out
        if self.as_player.isChecked():
            self.project["player"]["model"] = out
        self.win.touched()
        self.win.save(quiet=True)
        names = ", ".join(S.SLOT_NAME[k] for k in slots)
        self.state.setText(f"Gespeichert als {Path(out).name} mit {names}.")

    def reject(self):
        self.preview.timer.stop()
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
        super().reject()
