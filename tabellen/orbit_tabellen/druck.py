"""Drucken: Blatt (oder Auswahl) auf Seiten verteilen, in Hoch- oder Querformat.

Maße rechnen in „Bildschirmpixeln bei 100 %“ (96 dpi) wie die Ansicht; beim Zeichnen
wird auf die Auflösung des Druckers umgerechnet.
"""

from dataclasses import dataclass

PX_PER_MM = 96 / 25.4
FOOTER_PX = 22           # Platz für die Fußzeile (Datei · Blatt · Seite x von y)


@dataclass
class Bereich:
    r0: int
    r1: int              # einschließlich
    c0: int
    c1: int


@dataclass
class Seite:
    rows: list           # sichtbare Zeilen dieser Seite
    cols: list           # sichtbare Spalten dieser Seite
    nummer: int = 0


def ganzes_blatt(sheet):
    """Benutzter Bereich: bis zur letzten Zelle mit Inhalt oder Füllung (wie Excel druckt)."""
    used = [k for k, c in sheet.cells.items() if c.text or c.fill]
    if not used:
        return None
    r1 = max(r for r, _ in used)
    c1 = max(c for _, c in used)
    for r, c, rs, cs in sheet.merged:
        if (r, c) in sheet.cells:
            r1, c1 = max(r1, r + rs - 1), max(c1, c + cs - 1)
    return Bereich(0, r1, 0, c1)


def breite(sheet, c):
    return sheet.widths.get(c, 64)


def hoehe(sheet, r):
    return sheet.heights.get(r, sheet.heights.get(-1, 20))


def massstab(sheet, bereich, seite_b, anpassen):
    """Verkleinerung, damit alle Spalten auf die Seitenbreite passen (nie vergrößern)."""
    if not anpassen:
        return 1.0
    gesamt = sum(breite(sheet, c) for c in range(bereich.c0, bereich.c1 + 1) if c not in sheet.hidden_cols)
    return min(1.0, seite_b / gesamt) if gesamt else 1.0


def _stuecke(items, groesse, platz):
    """Folge in Stücke teilen, die in „platz“ passen (mind. ein Element je Stück)."""
    out, cur, used = [], [], 0.0
    for it in items:
        g = groesse(it)
        if cur and used + g > platz + 0.01:
            out.append(cur)
            cur, used = [], 0.0
        cur.append(it)
        used += g
    if cur:
        out.append(cur)
    return out


def seiten(sheet, bereich, seite_b, seite_h, scale, wiederholen=0):
    """Seiten wie in Excel: erst nach unten, dann nach rechts.

    seite_b/seite_h: nutzbare Fläche in Pixeln (96 dpi). wiederholen: so viele oberste
    Zeilen (fixierte Kopfzeilen) stehen auf jeder Seite noch einmal oben."""
    rows = [r for r in range(bereich.r0, bereich.r1 + 1) if r not in sheet.hidden_rows]
    cols = [c for c in range(bereich.c0, bereich.c1 + 1) if c not in sheet.hidden_cols]
    if not rows or not cols:
        return []
    kopf = [r for r in rows if r < bereich.r0 + wiederholen] if wiederholen else []
    rest = [r for r in rows if r not in kopf]
    kopf_h = sum(hoehe(sheet, r) for r in kopf) * scale
    if kopf and kopf_h > seite_h / 2:             # zu hohe Kopfzeilen nicht wiederholen
        kopf, rest, kopf_h = [], rows, 0
    spalten = _stuecke(cols, lambda c: breite(sheet, c) * scale, seite_b)
    if kopf:
        zeilen = _stuecke(rest, lambda r: hoehe(sheet, r) * scale, seite_h - kopf_h) or [[]]
        zeilen = [kopf + z for z in zeilen]
    else:
        zeilen = _stuecke(rows, lambda r: hoehe(sheet, r) * scale, seite_h)
    out = []
    for sp in spalten:
        for ze in zeilen:
            out.append(Seite(rows=ze, cols=sp, nummer=len(out) + 1))
    return out


# ---- Zeichnen (Qt) ------------------------------------------------------------------------------

def zeichnen(printer, sheet, bereich, anpassen=True, gitter=True, kopfzeilen=True, titel=""):
    """Alle Seiten auf den Drucker (oder ins PDF) zeichnen. Gibt die Seitenzahl zurück."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

    layout = printer.pageLayout()
    dpi = printer.resolution()
    k_dev = dpi / 96.0
    paint_rect = layout.paintRectPixels(dpi)
    seite_b = paint_rect.width() / k_dev
    seite_h = paint_rect.height() / k_dev - FOOTER_PX
    scale = massstab(sheet, bereich, seite_b, anpassen)
    wdh = sheet.freeze[0] if kopfzeilen and sheet.freeze[0] > bereich.r0 else 0
    wdh = max(0, wdh - bereich.r0)
    pages = seiten(sheet, bereich, seite_b, seite_h, scale, wdh)
    painter = QPainter()
    if not painter.begin(printer):
        return 0
    k = k_dev * scale
    merged = {(r, c): (rs, cs) for r, c, rs, cs in sheet.merged}
    inside = set()
    for (r, c), (rs, cs) in merged.items():
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                if (rr, cc) != (r, c):
                    inside.add((rr, cc))
    fonts = {}

    def font(cell):
        key = (cell.bold, cell.italic, cell.underline, cell.strike, cell.size)
        f = fonts.get(key)
        if f is None:
            f = QFont("Arial")
            f.setPointSizeF(max(4.0, cell.size * scale * 0.92))
            f.setBold(cell.bold)
            f.setItalic(cell.italic)
            f.setUnderline(bool(cell.underline))
            f.setStrikeOut(cell.strike)
            fonts[key] = f
        return f

    grid_pen = QPen(QColor("#c9ced8"))
    grid_pen.setWidthF(max(1.0, 0.6 * k_dev))
    foot_font = QFont("Arial")
    foot_font.setPointSizeF(8)
    try:
        for i, pg in enumerate(pages):
            if i:
                printer.newPage()
            # Positionen der Zeilen/Spalten auf dieser Seite
            xs, x = {}, 0.0
            for c in pg.cols:
                xs[c] = x
                x += breite(sheet, c) * k
            ys, y = {}, 0.0
            for r in pg.rows:
                ys[r] = y
                y += hoehe(sheet, r) * k
            total_w, total_h = x, y
            painter.save()
            painter.setClipRect(QRectF(0, 0, total_w + 1, total_h + 1))

            def rect_of(r, c):
                rs, cs = merged.get((r, c), (1, 1))
                w = sum(breite(sheet, cc) for cc in range(c, c + cs) if cc not in sheet.hidden_cols) * k
                h = sum(hoehe(sheet, rr) for rr in range(r, r + rs) if rr not in sheet.hidden_rows) * k
                return QRectF(xs[c], ys[r], w, h)

            # 1) Füllungen
            for r in pg.rows:
                for c in pg.cols:
                    cell = sheet.cells.get((r, c))
                    if cell and cell.fill and (r, c) not in inside:
                        painter.fillRect(rect_of(r, c), QColor(cell.fill))
            # 2) Gitter
            if gitter:
                painter.setPen(grid_pen)
                for r in pg.rows:
                    for c in pg.cols:
                        if (r, c) in inside:
                            continue
                        painter.drawRect(rect_of(r, c))
            # 3) Text
            for r in pg.rows:
                for c in pg.cols:
                    cell = sheet.cells.get((r, c))
                    if not cell or not cell.text or (r, c) in inside:
                        continue
                    rect = rect_of(r, c)
                    f = font(cell)
                    painter.setFont(f)
                    color = cell.color or ("#0563c1" if cell.link else "#000000")
                    painter.setPen(QColor(color))
                    h = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                         "right": Qt.AlignmentFlag.AlignRight}.get(cell.align)
                    if h is None:
                        h = Qt.AlignmentFlag.AlignRight if cell.number else Qt.AlignmentFlag.AlignLeft
                    v = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter}.get(
                        cell.valign, Qt.AlignmentFlag.AlignBottom)
                    pad = 3 * k
                    flags = int(h | v)
                    if cell.wrap:
                        flags |= int(Qt.TextFlag.TextWordWrap)
                    elif h == Qt.AlignmentFlag.AlignLeft and (r, c) not in merged:
                        # langer Text läuft wie in Excel in leere Nachbarzellen weiter
                        need = QFontMetricsF(f, printer).horizontalAdvance(cell.text) + 2 * pad
                        cc = c
                        while rect.width() < need:
                            cc += 1
                            if cc not in xs or (sheet.cells.get((r, cc)) and sheet.cells[(r, cc)].text) \
                                    or (r, cc) in inside or (r, cc) in merged:
                                break
                            rect.setWidth(rect.width() + breite(sheet, cc) * k)
                    painter.drawText(rect.adjusted(pad, pad * 0.5, -pad, -pad * 0.5), flags, cell.text)
            painter.restore()
            # Fußzeile
            painter.setFont(foot_font)
            painter.setPen(QColor("#6b7385"))
            fy = paint_rect.height() - FOOTER_PX * k_dev * 0.8
            links = f"{titel} · {sheet.name}" if titel else sheet.name
            painter.drawText(QRectF(0, fy, paint_rect.width(), FOOTER_PX * k_dev * 0.8),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), links)
            painter.drawText(QRectF(0, fy, paint_rect.width(), FOOTER_PX * k_dev * 0.8),
                             int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                             f"Seite {i + 1} von {len(pages)}")
    finally:
        painter.end()
    return len(pages)


# ---- Dialog ---------------------------------------------------------------------------------

def dialog(parent, sheet, titel, auswahl=None):
    """Druckvorschau mit Hoch-/Querformat, Anpassen, Gitter; „Drucken …“ und „Als PDF …“."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewWidget
    from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                                   QPushButton, QVBoxLayout)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape if sheet.landscape
                               else QPageLayout.Orientation.Portrait)
    from PySide6.QtCore import QMarginsF
    printer.setPageMargins(QMarginsF(12, 12, 12, 10), QPageLayout.Unit.Millimeter)
    printer.setDocName(titel or "Tabelle")

    dlg = QDialog(parent)
    dlg.setWindowTitle("Drucken – " + (titel or sheet.name))
    dlg.resize(1080, 760)
    root = QHBoxLayout(dlg)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    preview = QPrintPreviewWidget(printer)
    preview.setStyleSheet("QGraphicsView { background: #12151b; border: 0; }")
    root.addWidget(preview, 1)

    side = QFrame(objectName="bar")
    side.setFixedWidth(270)
    sl = QVBoxLayout(side)
    sl.setContentsMargins(18, 18, 18, 18)
    sl.setSpacing(10)
    head = QLabel("Drucken", objectName="title")
    sl.addWidget(head)
    info = QLabel("", objectName="muted")
    sl.addWidget(info)
    sl.addSpacing(6)

    def group(label, options, current):
        sl.addWidget(QLabel(label, objectName="muted"))
        row = QHBoxLayout()
        row.setSpacing(6)
        g = QButtonGroup(dlg)
        for i, text in enumerate(options):
            b = QPushButton(text, objectName="seg")
            b.setCheckable(True)
            b.setChecked(i == current)
            g.addButton(b, i)
            row.addWidget(b, 1)
        sl.addLayout(row)
        return g

    g_orient = group("Ausrichtung", ["Hochformat", "Querformat"], 1 if sheet.landscape else 0)
    g_bereich = None
    if auswahl:
        g_bereich = group("Bereich", ["Ganzes Blatt", "Auswahl"], 0)
    cb_fit = QCheckBox("Alle Spalten auf eine Seitenbreite")
    cb_fit.setChecked(True)
    cb_grid = QCheckBox("Gitternetzlinien")
    cb_grid.setChecked(True)
    cb_head = QCheckBox("Fixierte Kopfzeilen auf jeder Seite")
    cb_head.setChecked(True)
    cb_head.setVisible(sheet.freeze[0] > 0)
    sl.addSpacing(4)
    for cb in (cb_fit, cb_grid, cb_head):
        sl.addWidget(cb)
    sl.addStretch(1)
    btn_pdf = QPushButton("Als PDF speichern …")
    btn_print = QPushButton("Drucken …", objectName="primary")
    btn_close = QPushButton("Schließen")
    for b in (btn_print, btn_pdf, btn_close):
        sl.addWidget(b)
    root.addWidget(side)

    state = {"pages": 0}

    def bereich():
        if g_bereich is not None and g_bereich.checkedId() == 1:
            return auswahl
        return ganzes_blatt(sheet) or Bereich(0, 0, 0, 0)

    def paint(dev):
        state["pages"] = zeichnen(dev, sheet, bereich(), cb_fit.isChecked(), cb_grid.isChecked(),
                                  cb_head.isChecked(), titel)
        n = state["pages"]
        info.setText(f"A4 · {n} Seite{'n' if n != 1 else ''}")

    def refresh(*_):
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if g_orient.checkedId() == 1
                                   else QPageLayout.Orientation.Portrait)
        preview.updatePreview()
        preview.fitInView()

    preview.paintRequested.connect(paint)
    g_orient.idClicked.connect(refresh)
    if g_bereich is not None:
        g_bereich.idClicked.connect(refresh)
    for cb in (cb_fit, cb_grid, cb_head):
        cb.toggled.connect(refresh)

    def do_print():
        pd = QPrintDialog(printer, dlg)
        pd.setWindowTitle("Drucker wählen")
        if pd.exec() == QDialog.DialogCode.Accepted:
            paint(printer)
            dlg.accept()

    def do_pdf():
        from pathlib import Path
        start = str(Path.home() / ((titel.rsplit(".", 1)[0] if titel else sheet.name) + ".pdf"))
        path, _ = QFileDialog.getSaveFileName(dlg, "Als PDF speichern", start, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        pdf = QPrinter(QPrinter.PrinterMode.HighResolution)
        pdf.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        pdf.setOutputFileName(path)
        pdf.setPageLayout(printer.pageLayout())
        pdf.setDocName(printer.docName())
        paint(pdf)
        info.setText(f"Gespeichert: {Path(path).name}")

    btn_print.clicked.connect(do_print)
    btn_pdf.clicked.connect(do_pdf)
    btn_close.clicked.connect(dlg.reject)
    preview.fitInView()
    dlg._preview = preview
    dlg._orient = g_orient
    return dlg


def pdf_speichern(path, sheet, titel="", quer=None, anpassen=True):
    """Ohne Dialog als PDF – für Prüfungen und die Kommandozeile."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtPrintSupport import QPrinter
    pdf = QPrinter(QPrinter.PrinterMode.HighResolution)
    pdf.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pdf.setOutputFileName(str(path))
    pdf.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    land = sheet.landscape if quer is None else quer
    pdf.setPageOrientation(QPageLayout.Orientation.Landscape if land else QPageLayout.Orientation.Portrait)
    pdf.setPageMargins(QMarginsF(12, 12, 12, 10), QPageLayout.Unit.Millimeter)
    return zeichnen(pdf, sheet, ganzes_blatt(sheet) or Bereich(0, 0, 0, 0), anpassen, True, True, titel)


__all__ = ["Bereich", "Seite", "ganzes_blatt", "massstab", "seiten", "zeichnen", "dialog", "pdf_speichern",
           "PX_PER_MM"]
