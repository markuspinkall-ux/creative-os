"""Word-Dokumente (.docx) für Creative Writer lesen und schreiben (über python-docx).

Unterstützt: Absätze, Formatvorlagen (Überschriften, Titel, Zitat), Ausrichtung, Einzüge,
Abstände, Zeilenabstand, Fett/Kursiv/Unterstrichen/Durchgestrichen, Hoch-/Tiefgestellt,
Schriftart/-größe/-farbe, Hervorhebung, Links, Aufzählungen und Nummerierungen,
Tabellen, Bilder, Seitenumbrüche, Seitenformat und -ränder, Kopf-/Fußzeile, Seitenzahlen.
Was Word sonst noch kann (Kommentare, Änderungen nachverfolgen, Textfelder …), wird
beim Öffnen übersprungen – der Text bleibt erhalten.
"""

import base64
import io
import re

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QImage, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument,
    QTextFormat, QTextImageFormat, QTextLength, QTextListFormat, QTextTableFormat,
)

try:
    import docx
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Emu, Pt, RGBColor
    AVAILABLE = True
except ImportError:  # python3-docx fehlt – Word-Dateien sind dann nicht verfügbar
    AVAILABLE = False

PX_PER_PT = 96 / 72
EMU_PER_PX = 9525
MM_PER_PX = 25.4 / 96

# Überschriften: Formatvorlage in Word → Ebene (0 = Titel-Sonderfall)
HEADING_STYLES = {"title": -1, "titel": -1, "subtitle": -2, "untertitel": -2, "quote": -3, "zitat": -3,
                  "intense quote": -3, "intensives zitat": -3}

LIST_STYLES_ORDERED = {
    "decimal": QTextListFormat.Style.ListDecimal, "lowerLetter": QTextListFormat.Style.ListLowerAlpha,
    "upperLetter": QTextListFormat.Style.ListUpperAlpha, "lowerRoman": QTextListFormat.Style.ListLowerRoman,
    "upperRoman": QTextListFormat.Style.ListUpperRoman,
}
BULLET_STYLES = (QTextListFormat.Style.ListDisc, QTextListFormat.Style.ListCircle, QTextListFormat.Style.ListSquare)


# ---------------------------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------------------------
def _image_bytes(doc, name):
    """Bilddaten aus einem QTextImageFormat-Namen (data:-URL oder Ressource)."""
    if name.startswith("data:"):
        try:
            return base64.b64decode(name.split(",", 1)[1])
        except (ValueError, IndexError):
            return None
    res = doc.resource(QTextDocument.ResourceType.ImageResource, name)
    image = res if isinstance(res, QImage) else None
    if image is None or image.isNull():
        return None
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data)


def _hex(color):
    return "%02X%02X%02X" % (color.red(), color.green(), color.blue())


def _shade(element, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element.append(shd)


def _add_field(paragraph, code):
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, code), ("separate", None), (None, "1"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        elif text == code:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = f" {code} "
        else:
            el = OxmlElement("w:t")
            el.text = text
        run._r.append(el)


def _add_text_with_fields(paragraph, text, title=""):
    """Kopf-/Fußzeilentext mit Platzhaltern {seite}, {seiten}, {titel}."""
    parts = re.split(r"(\{seite\}|\{seiten\})", text.replace("{titel}", title))
    for part in parts:
        if part == "{seite}":
            _add_field(paragraph, "PAGE")
        elif part == "{seiten}":
            _add_field(paragraph, "NUMPAGES")
        elif part:
            paragraph.add_run(part)


# ---------------------------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------------------------
def _write_runs(paragraph, block, qdoc):
    for rng in block.textFormats():
        text = block.text()[rng.start:rng.start + rng.length]
        fmt = rng.format
        if fmt.isImageFormat():
            img = fmt.toImageFormat()
            data = _image_bytes(qdoc, img.name())
            if data:
                run = paragraph.add_run()
                try:
                    width = img.width() or QImage.fromData(data).width()
                    run.add_picture(io.BytesIO(data), width=Emu(int(width * EMU_PER_PX)))
                except Exception:  # unbekanntes Bildformat – überspringen
                    pass
            continue
        text = text.replace(" ", "\n").replace("￼", "")
        if not text:
            continue
        if fmt.isAnchor() and fmt.anchorHref():
            _add_hyperlink(paragraph, text, fmt.anchorHref(), fmt)
            continue
        _style_run(paragraph.add_run(text), fmt)


def _style_run(run, fmt):
    font = run.font
    if fmt.fontWeight() >= QFont.Weight.DemiBold:
        font.bold = True
    if fmt.fontItalic():
        font.italic = True
    if fmt.fontUnderline():
        font.underline = True
    if fmt.fontStrikeOut():
        font.strike = True
    va = fmt.verticalAlignment()
    if va == QTextCharFormat.VerticalAlignment.AlignSubScript:
        font.subscript = True
    elif va == QTextCharFormat.VerticalAlignment.AlignSuperScript:
        font.superscript = True
    if fmt.fontPointSize() > 0:
        font.size = Pt(round(fmt.fontPointSize() * 2) / 2)
    families = fmt.fontFamilies()
    if families:
        font.name = families[0] if isinstance(families, list) else str(families)
    if fmt.hasProperty(QTextFormat.Property.ForegroundBrush):
        color = fmt.foreground().color()
        if color.isValid() and color.alpha():
            font.color.rgb = RGBColor.from_string(_hex(color))
    if fmt.hasProperty(QTextFormat.Property.BackgroundBrush):
        color = fmt.background().color()
        if color.isValid() and color.alpha():
            rpr = run._r.get_or_add_rPr()
            _shade(rpr, _hex(color))


def _add_hyperlink(paragraph, text, url, fmt):
    part = paragraph.part
    rid = part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    rpr.append(style)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "2B5FD9")
    rpr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _paragraph_format(paragraph, bf):
    pf = paragraph.paragraph_format
    align = bf.alignment()
    if align & Qt.AlignmentFlag.AlignHCenter:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align & Qt.AlignmentFlag.AlignRight:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align & Qt.AlignmentFlag.AlignJustify:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if bf.leftMargin() or bf.indent():
        pf.left_indent = Emu(int((bf.leftMargin() + bf.indent() * 40) * EMU_PER_PX))
    if bf.rightMargin():
        pf.right_indent = Emu(int(bf.rightMargin() * EMU_PER_PX))
    if bf.textIndent():
        pf.first_line_indent = Emu(int(bf.textIndent() * EMU_PER_PX))
    pf.space_before = Pt(bf.topMargin() / PX_PER_PT)
    pf.space_after = Pt(bf.bottomMargin() / PX_PER_PT)
    if bf.lineHeightType() == QTextBlockFormat.LineHeightTypes.ProportionalHeight.value and bf.lineHeight() > 0:
        pf.line_spacing = bf.lineHeight() / 100
    if bf.hasProperty(QTextFormat.Property.BackgroundBrush):
        color = bf.background().color()
        if color.isValid() and color.alpha():
            _shade(paragraph._p.get_or_add_pPr(), _hex(color))
    if bf.pageBreakPolicy() & QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore:
        pf.page_break_before = True


def _style_for(block, wdoc):
    """Word-Formatvorlage für einen Absatz."""
    kind = block.blockFormat().property(QTextFormat.Property.UserProperty + 1)
    names = {"titel": "Title", "untertitel": "Subtitle", "zitat": "Quote"}
    if isinstance(kind, str) and kind in names:
        return names[kind]
    level = block.blockFormat().headingLevel()
    if 1 <= level <= 6:
        return f"Heading {level}"
    lst = block.textList()
    if lst is not None:
        indent = max(1, min(3, lst.format().indent()))
        base = "List Bullet" if lst.format().style() in BULLET_STYLES else "List Number"
        return base if indent == 1 else f"{base} {indent}"
    return None


def export_docx(qdoc, path, page, title=""):
    """QTextDocument → .docx. page: dict mit width_mm, height_mm, margins_mm (o, r, u, l), header, footer, numbers."""
    if not AVAILABLE:
        raise OSError("Für Word-Dateien fehlt python3-docx.")
    wdoc = docx.Document()
    section = wdoc.sections[0]
    w, h = page["width_mm"], page["height_mm"]
    section.orientation = WD_ORIENT.LANDSCAPE if w > h else WD_ORIENT.PORTRAIT
    section.page_width = Emu(int(w * 36000))
    section.page_height = Emu(int(h * 36000))
    top, right, bottom, left = page["margins_mm"]
    section.top_margin, section.right_margin = Emu(int(top * 36000)), Emu(int(right * 36000))
    section.bottom_margin, section.left_margin = Emu(int(bottom * 36000)), Emu(int(left * 36000))
    if page.get("header"):
        _add_text_with_fields(section.header.paragraphs[0], page["header"], title)
    footer = page.get("footer", "")
    numbers = page.get("numbers", "")
    if footer or numbers:
        para = section.footer.paragraphs[0]
        if footer:
            _add_text_with_fields(para, footer, title)
        if numbers and "{seite}" not in footer:
            if footer:
                para.add_run("    ")
            _add_field(para, "PAGE")
        para.alignment = WD_ALIGN_PARAGRAPH.RIGHT if numbers == "rechts" else WD_ALIGN_PARAGRAPH.CENTER
    default = qdoc.defaultFont()
    normal = wdoc.styles["Normal"].font
    normal.name = default.family()
    normal.size = Pt(default.pointSizeF() if default.pointSizeF() > 0 else 11)

    # Den leeren Startabsatz von python-docx wiederverwenden wäre fummelig – er ist nicht da.
    block = qdoc.begin()
    while block.isValid():
        cursor = QTextCursor(block)
        table = cursor.currentTable()
        if table is not None:
            _write_table(wdoc, table, qdoc)
            block = qdoc.findBlock(table.lastPosition() + 1)
            if not block.isValid():
                break
            continue
        style = _style_for(block, wdoc)
        try:
            paragraph = wdoc.add_paragraph(style=style) if style else wdoc.add_paragraph()
        except KeyError:
            paragraph = wdoc.add_paragraph()
        _paragraph_format(paragraph, block.blockFormat())
        _write_runs(paragraph, block, qdoc)
        if block.blockFormat().pageBreakPolicy() & QTextFormat.PageBreakFlag.PageBreak_AlwaysAfter:
            paragraph.add_run().add_break(WD_BREAK.PAGE)
        block = block.next()
    wdoc.save(str(path))


def _write_table(wdoc, table, qdoc):
    rows, cols = table.rows(), table.columns()
    wt = wdoc.add_table(rows=rows, cols=cols)
    try:
        wt.style = "Table Grid"
    except KeyError:
        pass
    for r in range(rows):
        for c in range(cols):
            cell = table.cellAt(r, c)
            wcell = wt.cell(r, c)
            first = True
            block = cell.firstCursorPosition().block()
            end = cell.lastCursorPosition().position()
            while block.isValid() and block.position() <= end:
                para = wcell.paragraphs[0] if first else wcell.add_paragraph()
                first = False
                _paragraph_format(para, block.blockFormat())
                _write_runs(para, block, qdoc)
                block = block.next()
            bg = cell.format().background().color()
            if cell.format().hasProperty(QTextFormat.Property.BackgroundBrush) and bg.isValid() and bg.alpha():
                _shade(wcell._tc.get_or_add_tcPr(), _hex(bg))


# ---------------------------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------------------------
def _char_format(run, base=None):
    fmt = QTextCharFormat(base) if base is not None else QTextCharFormat()
    font = run.font
    if run.bold or font.bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if run.italic or font.italic:
        fmt.setFontItalic(True)
    if run.underline or font.underline:
        fmt.setFontUnderline(True)
    if font.strike:
        fmt.setFontStrikeOut(True)
    if font.subscript:
        fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
    if font.superscript:
        fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
    if font.size:
        fmt.setFontPointSize(font.size.pt)
    if font.name:
        fmt.setFontFamilies([font.name])
    try:
        if font.color is not None and font.color.type is not None and font.color.rgb is not None:
            fmt.setForeground(QBrush(QColor("#" + str(font.color.rgb))))
    except (AttributeError, ValueError):
        pass
    rpr = run._r.rPr
    if rpr is not None:
        shd = rpr.find(qn("w:shd"))
        fill = shd.get(qn("w:fill")) if shd is not None else None
        if fill and fill.lower() != "auto":
            fmt.setBackground(QColor("#" + fill))
        hl = rpr.find(qn("w:highlight"))
        if hl is not None:
            names = {"yellow": "#fff176", "green": "#a5e7a0", "cyan": "#9de5f2", "magenta": "#f3a6e6",
                     "blue": "#9cb8ff", "red": "#ff9a9a", "lightGray": "#d9dce3", "darkYellow": "#e0c46c"}
            color = names.get(hl.get(qn("w:val")))
            if color:
                fmt.setBackground(QColor(color))
    return fmt


def _images_in_run(run, wdoc):
    out = []
    for blip in run._r.findall(".//" + qn("a:blip")):
        rid = blip.get(qn("r:embed"))
        part = wdoc.part.related_parts.get(rid) if rid else None
        if part is None:
            continue
        width = None
        extent = run._r.find(".//" + qn("wp:extent"))
        if extent is not None:
            try:
                width = int(int(extent.get("cx")) / EMU_PER_PX)
            except (TypeError, ValueError):
                width = None
        out.append((part.blob, width))
    return out


def _numbering_format(wdoc, num_id, ilvl):
    try:
        numbering = wdoc.part.numbering_part.element
    except (KeyError, NotImplementedError, AttributeError):
        return "bullet"
    abstract = numbering.xpath(f'./w:num[@w:numId="{num_id}"]/w:abstractNumId/@w:val')
    if not abstract:
        return "bullet"
    fmt = numbering.xpath(f'./w:abstractNum[@w:abstractNumId="{abstract[0]}"]/w:lvl[@w:ilvl="{ilvl}"]/w:numFmt/@w:val')
    return fmt[0] if fmt else "bullet"


class _Reader:
    def __init__(self, wdoc, qdoc):
        self.wdoc = wdoc
        self.qdoc = qdoc
        self.cursor = QTextCursor(qdoc)
        self.first = True
        self.lists = {}

    def block_format(self, para):
        bf = QTextBlockFormat()
        style = (para.style.name if para.style is not None else "") or ""
        lower = style.lower()
        m = re.match(r"(heading|überschrift)\s*(\d)", lower)
        if m:
            bf.setHeadingLevel(int(m.group(2)))
        elif lower in HEADING_STYLES:
            bf.setProperty(QTextFormat.Property.UserProperty + 1,
                           {-1: "titel", -2: "untertitel", -3: "zitat"}[HEADING_STYLES[lower]])
        align = para.alignment if para.alignment is not None else para.paragraph_format.alignment
        if align is not None:
            mapping = {WD_ALIGN_PARAGRAPH.CENTER: Qt.AlignmentFlag.AlignHCenter,
                       WD_ALIGN_PARAGRAPH.RIGHT: Qt.AlignmentFlag.AlignRight,
                       WD_ALIGN_PARAGRAPH.JUSTIFY: Qt.AlignmentFlag.AlignJustify}
            bf.setAlignment(mapping.get(align, Qt.AlignmentFlag.AlignLeft))
        pf = para.paragraph_format
        if pf.left_indent:
            bf.setLeftMargin(pf.left_indent / EMU_PER_PX)
        if pf.right_indent:
            bf.setRightMargin(pf.right_indent / EMU_PER_PX)
        if pf.first_line_indent:
            bf.setTextIndent(pf.first_line_indent / EMU_PER_PX)
        if pf.space_before is not None:
            bf.setTopMargin(pf.space_before.pt * PX_PER_PT)
        bf.setBottomMargin((pf.space_after.pt if pf.space_after is not None else 8) * PX_PER_PT)
        if isinstance(pf.line_spacing, float) and pf.line_spacing > 0:
            bf.setLineHeight(pf.line_spacing * 100, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        if pf.page_break_before:
            bf.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        return bf, style

    def heading_char(self, bf):
        fmt = QTextCharFormat()
        level = bf.headingLevel()
        kind = bf.property(QTextFormat.Property.UserProperty + 1)
        sizes = {1: 16, 2: 13, 3: 12, 4: 11, 5: 11, 6: 11}
        if level:
            fmt.setFontPointSize(sizes.get(level, 11))
            fmt.setForeground(QColor("#2b4f9e" if level < 3 else "#1f3763"))
        elif kind == "titel":
            fmt.setFontPointSize(28)
        elif kind == "untertitel":
            fmt.setFontPointSize(14)
            fmt.setForeground(QColor("#5d6884"))
        elif kind == "zitat":
            fmt.setFontItalic(True)
            fmt.setForeground(QColor("#5d6884"))
        return fmt

    def new_block(self, bf, cf):
        if self.first:
            self.cursor.setBlockFormat(bf)
            self.cursor.setBlockCharFormat(cf)
            self.first = False
        else:
            self.cursor.insertBlock(bf, cf)

    def list_for(self, para, style):
        ppr = para._p.pPr
        num = ppr.numPr if ppr is not None else None
        if num is not None and num.numId is not None:
            num_id = num.numId.val
            ilvl = num.ilvl.val if num.ilvl is not None else 0
            kind = _numbering_format(self.wdoc, num_id, ilvl)
        elif "list bullet" in style.lower() or "aufzählung" in style.lower():
            num_id, ilvl, kind = "bullet-style", int(style[-1]) - 1 if style[-1].isdigit() else 0, "bullet"
        elif "list number" in style.lower() or "nummer" in style.lower():
            num_id, ilvl, kind = "number-style", int(style[-1]) - 1 if style[-1].isdigit() else 0, "decimal"
        else:
            return None
        if kind == "none":
            return None
        key = (num_id, ilvl)
        lst = self.lists.get(key)
        if lst is None:
            lf = QTextListFormat()
            lf.setStyle(LIST_STYLES_ORDERED.get(kind, BULLET_STYLES[min(ilvl, 2)]))
            lf.setIndent(ilvl + 1)
            lst = self.cursor.createList(lf)
            self.lists[key] = lst
            return True
        lst.add(self.cursor.block())
        return True

    def paragraph(self, para):
        bf, style = self.block_format(para)
        base = self.heading_char(bf)
        self.new_block(bf, base)
        self.list_for(para, style)
        self.inline(para, base)

    def inline(self, para, base):
        items = list(para.iter_inner_content()) if hasattr(para, "iter_inner_content") else para.runs
        for item in items:
            href = None
            runs = [item]
            if not hasattr(item, "font"):  # Hyperlink
                href = getattr(item, "address", None) or getattr(item, "url", None)
                runs = item.runs
            for run in runs:
                fmt = _char_format(run, base)
                if href:
                    fmt.setAnchor(True)
                    fmt.setAnchorHref(href)
                    fmt.setForeground(QColor("#2b5fd9"))
                    fmt.setFontUnderline(True)
                for blob, width in _images_in_run(run, self.wdoc):
                    image = QImage.fromData(blob)
                    if image.isNull():
                        continue
                    png = QByteArray()
                    buf = QBuffer(png)
                    buf.open(QIODevice.OpenModeFlag.WriteOnly)
                    image.save(buf, "PNG")
                    img = QTextImageFormat()
                    img.setName("data:image/png;base64," + bytes(png.toBase64()).decode("ascii"))
                    w = width or image.width()
                    img.setWidth(w)
                    img.setHeight(image.height() * w / max(1, image.width()))
                    self.cursor.insertImage(img)
                text = run.text
                if text:
                    self.cursor.insertText(text.replace("\n", " ").replace("\t", "\t"), fmt)
                for br in run._r.findall(qn("w:br")):
                    if br.get(qn("w:type")) == "page":
                        bf = self.cursor.blockFormat()
                        bf.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysAfter)
                        self.cursor.setBlockFormat(bf)

    def table(self, tbl):
        from docx.table import Table
        table = Table(tbl, self.wdoc.part) if not hasattr(tbl, "rows") else tbl
        rows = len(table.rows)
        cols = max((len(r.cells) for r in table.rows), default=0)
        if not rows or not cols:
            return
        if self.first:
            self.first = False
        tf = QTextTableFormat()
        tf.setBorder(1)
        tf.setBorderBrush(QColor("#9aa3b5"))
        tf.setCellPadding(5)
        tf.setCellSpacing(0)
        tf.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        qtable = self.cursor.insertTable(rows, cols, tf)
        for r, row in enumerate(table.rows):
            for c, cell in enumerate(row.cells[:cols]):
                cur = qtable.cellAt(r, c).firstCursorPosition()
                for i, para in enumerate(cell.paragraphs):
                    if i:
                        cur.insertBlock()
                    for run in para.runs:
                        if run.text:
                            cur.insertText(run.text, _char_format(run))
        self.cursor = QTextCursor(self.qdoc)
        self.cursor.movePosition(QTextCursor.MoveOperation.End)


def import_docx(path, qdoc):
    """.docx → QTextDocument (wird geleert). Rückgabe: Seiteneinstellungen (dict) oder {}."""
    if not AVAILABLE:
        raise OSError("Für Word-Dateien fehlt python3-docx.")
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    wdoc = docx.Document(str(path))
    qdoc.clear()
    reader = _Reader(wdoc, qdoc)
    for child in wdoc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            reader.paragraph(Paragraph(child, wdoc.part))
        elif tag == "tbl":
            reader.table(Table(child, wdoc.part))
    page = {}
    try:
        s = wdoc.sections[0]
        page = {"width_mm": round(s.page_width / 36000, 1), "height_mm": round(s.page_height / 36000, 1),
                "margins_mm": [round(m / 36000, 1) for m in (s.top_margin, s.right_margin, s.bottom_margin, s.left_margin)]}
        header = " ".join(p.text for p in s.header.paragraphs if p.text.strip())
        footer_xml = s.footer._element.xml if s.footer is not None else ""
        footer = " ".join(p.text for p in s.footer.paragraphs if p.text.strip())
        page["header"] = header
        has_page = "PAGE" in footer_xml
        page["footer"] = re.sub(r"\b1\b", "", footer).strip() if has_page else footer
        page["numbers"] = "mitte" if has_page else ""
    except Exception:
        pass
    return page
