"""Creative Art – Krita mit Aufbau, Namen und Arbeitsweise von Photoshop CS2.

- Programmname „Creative Art“ in Titelleiste und Dialogen
- Menüeinträge mit den deutschen CS2-Begriffen
- Paletten wie bei CS2: Werkzeuge links (einspaltig), rechts Navigator/Histogramm,
  Farbe/Farbfelder, Protokoll, Ebenen/Kanäle
- „Für Web speichern …“ (Strg+Alt+Umschalt+S)
- „Arbeitsbereich zurücksetzen“ stellt die Anordnung wieder her

Creative Art basiert auf Krita (GPL v3, krita.org). Die Original-Infos zu
Krita bleiben unter Hilfe › „Über Krita“ erreichbar.
"""

from krita import Extension, Krita

import sys

# Wichtig: genau die Qt-Bindung nehmen, die Krita selbst geladen hat.
# PyQt5 (Qt 5) in Krita 6 (Qt 6) zu laden, bringt Krita sofort zum Absturz.
if "PyQt5.QtCore" in sys.modules and "PyQt6.QtCore" not in sys.modules:
    from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer
    from PyQt5.QtGui import QImage
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget,
                                 QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QSlider,
                                 QSpinBox, QVBoxLayout, QWidget)
else:  # Krita 6 (Qt 6)
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer
    from PyQt6.QtGui import QImage
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget,
                                 QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QSlider,
                                 QSpinBox, QVBoxLayout, QWidget)

APP = "Creative Art"
LAYOUT_VERSION = "1"

# Krita-Aktion → Beschriftung wie im deutschen Photoshop CS2
LABELS = {
    # Datei
    "file_new": "Neu …", "file_open": "Öffnen …", "file_open_recent": "Letzte Dateien öffnen",
    "file_close": "Schließen", "file_close_all": "Alle schließen", "file_save": "Speichern",
    "file_save_as": "Speichern unter …", "save_incremental_version": "Version speichern",
    "file_reload_file": "Zurück zur letzten Version", "import_layer_from_file": "Platzieren …",
    "file_import_file": "Datei importieren …", "file_export_file": "Exportieren …",
    "file_export_pdf": "Als PDF exportieren …", "save_groups_as_images": "Ebenengruppen als Dateien …",
    "create_template": "Als Vorlage speichern …", "file_documentinfo": "Dateiinformationen …",
    "file_print": "Drucken …", "file_print_preview": "Druckvorschau", "file_quit": "Beenden",
    # Bearbeiten
    "edit_undo": "Rückgängig", "edit_redo": "Schritt vorwärts", "edit_cut": "Ausschneiden",
    "edit_copy": "Kopieren", "copy_merged": "Auf eine Ebene reduziert kopieren", "edit_paste": "Einfügen",
    "paste_into": "In die Auswahl einfügen", "paste_new": "Als neue Datei einfügen", "clear": "Löschen",
    "fill_selection_foreground_color": "Mit Vordergrundfarbe", "fill_selection_background_color": "Mit Hintergrundfarbe",
    "fill_selection_pattern": "Mit Muster", "stroke_selection": "Kontur füllen …",
    "KisToolTransform": "Frei transformieren", "rotateLayer180": "180° drehen", "rotateLayerCW90": "90° im UZS drehen",
    "rotateLayerCCW90": "90° gegen UZS drehen", "rotatelayer": "Drehen …", "shearlayer": "Neigen …",
    "mirrorNodeX": "Horizontal spiegeln", "mirrorNodeY": "Vertikal spiegeln", "layersize": "Skalieren …",
    "paste_as_reference": "Als Referenzbild einfügen", "options_configure": "Allgemein …",
    "options_configure_keybinding": "Tastaturbefehle …", "manage_resources": "Vorgaben-Manager …",
    "manage_bundles": "Vorgaben-Pakete …", "options_configure_toolbars": "Werkzeugleisten …",
    # Bild
    "imagecolorspaceconversion": "Modus …", "krita_filter_levels": "Tonwertkorrektur …",
    "krita_filter_autocontrast": "Auto-Kontrast", "krita_filter_perchannel": "Gradationskurven …",
    "krita_filter_colorbalance": "Farbbalance …", "krita_filter_hsvadjustment": "Farbton/Sättigung …",
    "krita_filter_desaturate": "Sättigung verringern …", "krita_filter_crosschannel": "Kanalmixer …",
    "krita_filter_gradientmap": "Verlaufsumsetzung …", "krita_filter_colortransfer": "Gleiche Farbe …",
    "krita_filter_invert": "Umkehren", "krita_filter_normalize": "Tonwertangleichung",
    "krita_filter_threshold": "Schwellenwert …", "krita_filter_posterize": "Tontrennung …",
    "krita_filter_colortoalpha": "Farbe in Transparenz …", "krita_filter_asc-cdl": "Farbkorrektur (ASC CDL) …",
    "duplicate_image": "Duplizieren …", "imagesize": "Bildgröße …", "canvassize": "Arbeitsfläche …",
    "imageresolution": "Auflösung …", "rotateImage180": "180°", "rotateImageCW90": "90° im UZS",
    "rotateImageCCW90": "90° gegen UZS", "rotateimage": "Per Eingabe …",
    "mirrorImageHorizontal": "Arbeitsfläche horizontal spiegeln", "mirrorImageVertical": "Arbeitsfläche vertikal spiegeln",
    "resizeimagetoselection": "Freistellen", "trim_to_image": "Zuschneiden", "resizeimagetolayer": "An Ebene anpassen",
    "shearimage": "Neigen …", "offsetimage": "Verschiebungseffekt …", "separate": "Kanäle teilen …",
    "imagesplit": "Bild aufteilen …", "histogram": "Histogramm …", "image_properties": "Bildeigenschaften …",
    # Ebene
    "add_new_paint_layer": "Ebene …", "add_new_group_layer": "Gruppe …",
    "copy_selection_to_new_layer": "Ebene durch Kopie", "cut_selection_to_new_layer": "Ebene durch Ausschneiden",
    "add_new_shape_layer": "Vektorebene …", "add_new_file_layer": "Verknüpfte Datei …", "add_new_clone_layer": "Klon-Ebene",
    "duplicatelayer": "Ebene duplizieren", "remove_layer": "Ebene löschen", "layer_properties": "Ebeneneigenschaften …",
    "layer_style": "Ebenenstil …", "add_new_fill_layer": "Neue Füllebene …", "add_new_adjustment_layer": "Neue Einstellungsebene …",
    "add_new_transparency_mask": "Ebenenmaske hinzufügen", "add_new_filter_mask": "Filtermaske hinzufügen",
    "add_new_selection_mask": "Auswahlmaske hinzufügen", "add_new_transform_mask": "Transformationsmaske hinzufügen",
    "add_new_colorize_mask": "Kolorierungsmaske hinzufügen", "create_quick_clipping_group": "Schnittmaske erstellen",
    "create_quick_group": "Ebenen gruppieren", "quick_ungroup": "Ebenengruppierung aufheben",
    "move_layer_up": "Schrittweise nach vorne", "move_layer_down": "Schrittweise nach hinten",
    "convert_to_paint_layer": "Rastern (in Pixelebene umwandeln)", "merge_layer": "Auf eine Ebene reduzieren",
    "merge_selected_layers": "Ausgewählte Ebenen zusammenfügen", "new_from_visible": "Sichtbare auf neue Ebene",
    "flatten_image": "Auf Hintergrundebene reduzieren", "save_node_as_image": "Ebene als Datei speichern …",
    "layersplit": "Ebene nach Farben teilen …", "EditLayerMetaData": "Ebenen-Metadaten …",
    # Auswahl
    "select_all": "Alles auswählen", "deselect": "Auswahl aufheben", "reselect": "Erneut wählen",
    "invert_selection": "Auswahl umkehren", "colorrange": "Farbbereich …", "featherselection": "Weiche Auswahlkante …",
    "borderselection": "Umrandung …", "smoothselection": "Abrunden …", "growselection": "Erweitern …",
    "shrinkselection": "Verkleinern …", "similar": "Ähnliches auswählen", "selectionscale": "Auswahl transformieren",
    "edit_selection": "Auswahl bearbeiten", "toggle-selection-overlay-mode": "Im Maskierungsmodus bearbeiten",
    "toggle_display_selection": "Auswahlkante anzeigen",
    # Filter
    "filter_apply_again": "Letzter Filter", "filter_apply_reprompt": "Letzten Filter mit Einstellungen",
    "filter_gallery": "Filtergalerie …", "krita_filter_oilpaint": "Ölfarbe …", "krita_filter_halftone": "Farbraster …",
    "krita_filter_raindrops": "Regentropfen …", "krita_filter_smalltiles": "Kacheln …",
    "krita_filter_roundcorners": "Ecken abrunden …", "krita_filter_gaussian blur": "Gaußscher Weichzeichner …",
    "krita_filter_motion blur": "Bewegungsunschärfe …", "krita_filter_lens blur": "Tiefenschärfe abmildern …",
    "krita_filter_blur": "Weichzeichnen …", "krita_filter_wave": "Wellen …", "krita_filter_phongbumpmap": "Beleuchtungseffekte …",
    "krita_filter_noise": "Rauschen hinzufügen …", "krita_filter_gaussiannoisereducer": "Rauschen reduzieren …",
    "krita_filter_waveletnoisereducer": "Rauschen entfernen …", "krita_filter_randompick": "Streuen …",
    "krita_filter_pixelize": "Mosaikeffekt …", "krita_filter_indexcolors": "Indizierte Farben …",
    "krita_filter_palettize": "Farbpalette anwenden …", "krita_filter_unsharp": "Unscharf maskieren …",
    "krita_filter_sharpen": "Scharfzeichnen", "krita_filter_mean removal": "Stärker scharfzeichnen",
    "krita_filter_emboss": "Relief …", "krita_filter_edge detection": "Konturen finden …",
    "krita_filter_gaussianhighpass": "Hochpass …", "krita_filter_maximize": "Helle Bereiche vergrößern",
    "krita_filter_minimize": "Dunkle Bereiche vergrößern", "QMic": "G'MIC …",
    # Ansicht / Fenster / Hilfe
    "softProof": "Proof", "gamutCheck": "Farbumfang-Warnung", "view_zoom_in": "Einzoomen",
    "view_zoom_out": "Auszoomen", "zoom_to_fit": "Ganzes Bild", "zoom_to_100pct": "Tatsächliche Pixel",
    "view_print_size": "Ausgabegröße", "view_show_canvas_only": "Vollbildmodus mit Menüleiste aus",
    "fullscreen": "Vollbildmodus", "view_ruler": "Lineale", "view_show_guides": "Hilfslinien",
    "view_lock_guides": "Hilfslinien sperren", "view_grid": "Raster", "view_pixel_grid": "Pixelraster",
    "view_snap_to_guides": "Hilfslinien", "view_snap_to_grid": "Raster", "view_snap_to_pixel": "Pixel",
    "view_snap_image_bounds": "Dokumentbegrenzung", "view_snap_image_center": "Dokumentmitte",
    "showStatusBar": "Statusleiste", "view_toggledockers": "Bedienfelder ein/aus",
    "help_contents": "Creative Art Hilfe (Krita-Handbuch)", "help_about_app": "Über Krita (Grundlage) …",
}

# Paletten wie bei CS2: rechts von oben nach unten, je Gruppe als Reiter
RIGHT_GROUPS = [
    ["sharedtooldocker"],
    ["OverviewDocker", "HistogramDocker"],
    ["ColorSelectorNg", "SmallColorSelector", "PaletteDocker"],
    ["History", "Snapshot"],
    ["KisLayerBox", "ChannelDocker"],
]


def _qwin(window):
    try:
        return window.qwindow()
    except Exception:
        return None


class SaveForWeb(QDialog):
    """Für Web speichern: Format, Qualität, Größe – mit Dateigröße vorab."""

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Für Web speichern – " + APP)
        self.doc = doc
        self.src = doc.projection(0, 0, doc.width(), doc.height())
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.fmt = QComboBox()
        self.fmt.addItems(["JPEG", "PNG-24", "PNG-8", "WebP"])
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(1, 100)
        self.quality.setValue(80)
        self.qlabel = QLabel("80")
        qrow = QHBoxLayout()
        qrow.addWidget(self.quality, 1)
        qrow.addWidget(self.qlabel)
        qw = QWidget()
        qw.setLayout(qrow)
        self.w = QSpinBox()
        self.h = QSpinBox()
        for s in (self.w, self.h):
            s.setRange(1, 30000)
            s.setSuffix(" px")
        self.w.setValue(doc.width())
        self.h.setValue(doc.height())
        self.keep = QCheckBox("Proportionen beibehalten")
        self.keep.setChecked(True)
        self.meta = QCheckBox("Metadaten (Profil) einbetten")
        self.info = QLabel("")
        form.addRow("Format:", self.fmt)
        form.addRow("Qualität:", qw)
        form.addRow("Breite:", self.w)
        form.addRow("Höhe:", self.h)
        form.addRow("", self.keep)
        form.addRow("Ergebnis:", self.info)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Speichern …")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._lock = False
        self.fmt.currentIndexChanged.connect(self.update_info)
        self.quality.valueChanged.connect(lambda v: (self.qlabel.setText(str(v)), self.update_info()))
        self.w.valueChanged.connect(lambda v: self._ratio("w"))
        self.h.valueChanged.connect(lambda v: self._ratio("h"))
        self.update_info()

    def _ratio(self, which):
        if self._lock:
            return
        if self.keep.isChecked() and self.doc.width() and self.doc.height():
            self._lock = True
            if which == "w":
                self.h.setValue(max(1, round(self.w.value() * self.doc.height() / self.doc.width())))
            else:
                self.w.setValue(max(1, round(self.h.value() * self.doc.width() / self.doc.height())))
            self._lock = False
        self.update_info()

    def _encode(self):
        img = self.src
        if (self.w.value(), self.h.value()) != (img.width(), img.height()):
            img = img.scaled(self.w.value(), self.h.value(), Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        fmt = self.fmt.currentText()
        self.quality.setEnabled(fmt in ("JPEG", "WebP"))
        if fmt == "JPEG":
            img = img.convertToFormat(QImage.Format.Format_RGB32)
        elif fmt == "PNG-8":
            img = img.convertToFormat(QImage.Format.Format_Indexed8, Qt.ImageConversionFlag.ThresholdDither)
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        kind = {"JPEG": "JPG", "PNG-24": "PNG", "PNG-8": "PNG", "WebP": "WEBP"}[fmt]
        img.save(buf, kind, self.quality.value() if fmt in ("JPEG", "WebP") else -1)
        buf.close()
        return data, kind

    def update_info(self):
        data, _ = self._encode()
        n = data.size()
        size = f"{n / 1024:.1f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.2f} MB"
        self.info.setText(f"{size.replace('.', ',')}  ·  {self.w.value()} × {self.h.value()} px")

    def save(self):
        data, kind = self._encode()
        ext = {"JPG": "jpg", "PNG": "png", "WEBP": "webp"}[kind]
        base = (self.doc.fileName() or "Unbenannt").rsplit(".", 1)[0]
        path, _ = QFileDialog.getSaveFileName(self, "Für Web speichern", f"{base}.{ext}",
                                              f"{kind}-Bild (*.{ext})")
        if not path:
            return
        if not path.lower().endswith("." + ext):
            path += "." + ext
        with open(path, "wb") as fh:
            fh.write(bytes(data))
        self.accept()


class CreativeArt(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        QApplication.setApplicationDisplayName(APP)
        Krita.instance().notifier().windowCreated.connect(self._on_window)

    def createActions(self, window):
        a = window.createAction("creative_save_for_web", "Für Web speichern …", "")
        a.triggered.connect(self.save_for_web)
        b = window.createAction("creative_reset_layout", "Arbeitsbereich zurücksetzen (CS2)", "")
        b.triggered.connect(lambda: self.arrange(Krita.instance().activeWindow(), force=True))
        c = window.createAction("creative_about", "Über Creative Art …", "")
        c.triggered.connect(self.about)

    # ---- Fenster ------------------------------------------------------------------------------
    def _on_window(self):
        win = Krita.instance().activeWindow()
        if win is None:
            return
        qw = _qwin(win)
        if qw is not None:
            qw.windowTitleChanged.connect(lambda t, q=qw: self._fix_title(q, t))
            self._fix_title(qw, qw.windowTitle())
        # Filter-Aktionen entstehen etwas später – Beschriftungen danach setzen
        for delay in (0, 800, 2500):
            QTimer.singleShot(delay, self.relabel)
        QTimer.singleShot(400, lambda: self.arrange(win))
        QTimer.singleShot(1500, lambda: self._fix_welcome(qw))

    @staticmethod
    def _fix_title(qw, title):
        if "Krita" in title:
            qw.setWindowTitle(title.replace("Krita", APP))

    def _fix_welcome(self, qw):
        if qw is None:
            return
        for lab in qw.findChildren(QLabel):
            t = lab.text()
            if "Krita" in t and len(t) < 200:
                lab.setText(t.replace("Krita", APP))

    def relabel(self):
        k = Krita.instance()
        for name, text in LABELS.items():
            act = k.action(name)
            if act is not None:
                act.setText(text)
                act.setIconText(text.replace(" …", ""))

    # ---- Paletten wie CS2 ------------------------------------------------------------------------
    def arrange(self, window, force=False):
        k = Krita.instance()
        if not force and k.readSetting("creative_art", "layout", "") == LAYOUT_VERSION:
            return
        qw = _qwin(window) if window else None
        if qw is None:
            return
        docks = {d.objectName(): d for d in qw.findChildren(QDockWidget)}
        wanted = {"ToolBox"} | {n for g in RIGHT_GROUPS for n in g}
        for name, d in docks.items():
            if name not in wanted:
                d.hide()
        tb = docks.get("ToolBox")
        if tb is not None:
            qw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tb)
            tb.show()
        firsts = []
        for group in RIGHT_GROUPS:
            present = [docks[n] for n in group if n in docks]
            # Bei den Farbwählern nur einen nehmen
            if group[0] == "ColorSelectorNg" and "ColorSelectorNg" in docks and "SmallColorSelector" in docks:
                docks["SmallColorSelector"].hide()
                present = [d for d in present if d.objectName() != "SmallColorSelector"]
            if not present:
                continue
            first = present[0]
            qw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, first, Qt.Orientation.Vertical)
            first.show()
            for other in present[1:]:
                qw.tabifyDockWidget(first, other)
                other.show()
            first.raise_()
            firsts.append(first)
        try:
            if tb is not None:
                qw.resizeDocks([tb], [56], Qt.Orientation.Horizontal)
            if firsts:
                qw.resizeDocks(firsts, [300] * len(firsts), Qt.Orientation.Horizontal)
        except Exception:
            pass
        k.writeSetting("creative_art", "layout", LAYOUT_VERSION)

    # ---- Dialoge ------------------------------------------------------------------------------------
    def save_for_web(self):
        doc = Krita.instance().activeDocument()
        win = Krita.instance().activeWindow()
        parent = _qwin(win) if win else None
        if doc is None:
            QMessageBox.information(parent, APP, "Bitte zuerst ein Bild öffnen.")
            return
        SaveForWeb(doc, parent).exec()

    def about(self):
        win = Krita.instance().activeWindow()
        QMessageBox.about(_qwin(win) if win else None, "Über " + APP,
                          f"<b>{APP}</b><br>Bildbearbeitung für Creative OS – Aufbau und Arbeitsweise "
                          "wie bei klassischer Bildbearbeitung.<br><br>"
                          f"{APP} basiert auf <b>Krita {Krita.instance().version()}</b> "
                          "(GNU GPL v3, krita.org). Vielen Dank an das Krita-Team!")


Krita.instance().addExtension(CreativeArt(Krita.instance()))
