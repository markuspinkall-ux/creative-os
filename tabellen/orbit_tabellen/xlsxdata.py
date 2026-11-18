"""Excel-Dateien (.xlsx/.xlsm/.xltx/.xltm) lesen – ohne Qt, damit es sich einfach prüfen lässt.

Liefert je Blatt: Zellwerte als fertigen Text (deutsche Zahlen- und Datumsformate), Formeln,
Schrift/Farben/Ausrichtung, Spaltenbreiten, Zeilenhöhen, verbundene Zellen, ausgeblendete
Zeilen/Spalten. Nur lesen – die Datei wird nie verändert.
"""

import datetime as dt
import re
from dataclasses import dataclass, field

from openpyxl import load_workbook
from openpyxl.styles.colors import COLOR_INDEX
from openpyxl.utils import get_column_letter

MAX_CELLS = 2_000_000          # größere Blätter werden gekürzt angezeigt (Hinweis in der Statuszeile)

# Excel-Standardfarben (Office-Design), falls die Datei kein eigenes Design mitbringt.
# Reihenfolge wie in Excel: 0 hell1, 1 dunkel1, 2 hell2, 3 dunkel2, 4–9 Akzente, 10/11 Links
OFFICE_THEME = ["FFFFFF", "000000", "E7E6E6", "44546A", "4472C4", "ED7D31",
                "A5A5A5", "FFC000", "5B9BD5", "70AD47", "0563C1", "954F72"]


def theme_colors(wb):
    """Farben des Datei-Designs (clrScheme), in Excel-Reihenfolge."""
    raw = getattr(wb, "loaded_theme", None)
    if not raw:
        return list(OFFICE_THEME)
    text = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw)
    m = re.search(r"<a:clrScheme[^>]*>(.*?)</a:clrScheme>", text, re.S)
    if not m:
        return list(OFFICE_THEME)
    order = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5",
             "accent6", "hlink", "folHlink"]
    found = {}
    for name in order:
        mm = re.search(rf"<a:{name}>(.*?)</a:{name}>", m.group(1), re.S)
        if not mm:
            continue
        c = re.search(r'srgbClr val="([0-9A-Fa-f]{6})"', mm.group(1)) \
            or re.search(r'lastClr="([0-9A-Fa-f]{6})"', mm.group(1))
        if c:
            found[name] = c.group(1).upper()
    if len(found) < 10:
        return list(OFFICE_THEME)
    # Excel tauscht hell/dunkel: Index 0 = lt1, 1 = dk1, 2 = lt2, 3 = dk2
    seq = [found["lt1"], found["dk1"], found["lt2"], found["dk2"]] + \
          [found[f"accent{i}"] for i in range(1, 7)] + [found.get("hlink", "0563C1"), found.get("folHlink", "954F72")]
    return seq


def _tint(hex6, tint):
    """Excel-Tönung: >0 aufhellen, <0 abdunkeln (über HLS-Helligkeit, wie Excel)."""
    import colorsys
    if not tint:
        return hex6
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    r, g, b = colorsys.hls_to_rgb(h, max(0, min(1, l)), s)
    return "".join(f"{round(v * 255):02X}" for v in (r, g, b))


def resolve_color(color, theme):
    """openpyxl-Farbe → '#RRGGBB' oder None (automatisch/unbekannt)."""
    if color is None:
        return None
    try:
        kind = color.type
        if kind == "rgb":
            v = color.rgb
            if not isinstance(v, str) or len(v) < 6:
                return None
            if len(v) == 8 and v[:2] == "00" and v[2:] == "000000":
                return None                       # „leer“ von manchen Programmen
            return "#" + v[-6:].upper()
        if kind == "theme":
            idx = int(color.theme)
            if 0 <= idx < len(theme):
                return "#" + _tint(theme[idx], float(color.tint or 0))
        if kind == "indexed":
            idx = int(color.indexed)
            if idx in (64, 65):                   # System-Vordergrund/-Hintergrund
                return None
            if 0 <= idx < len(COLOR_INDEX):
                return "#" + COLOR_INDEX[idx][-6:].upper()
    except (TypeError, ValueError, AttributeError):
        return None
    return None


# ---- Zahlen und Datum im deutschen Format --------------------------------------------------------

def _de_number(value, decimals, thousands):
    text = f"{value:,.{decimals}f}" if thousands else f"{value:.{decimals}f}"
    return text.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def _decimals(fmt):
    m = re.search(r"0\.(0+)", fmt)
    return len(m.group(1)) if m else 0


DATE_MAP = [("yyyy", "%Y"), ("yy", "%y"), ("mmmm", "%B"), ("mmm", "%b"), ("dddd", "%A"), ("ddd", "%a"),
            ("dd", "%d"), ("hh", "%H"), ("ss", "%S")]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]
DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def format_date(value, fmt):
    """Datum/Zeit – Format aus der Datei grob übernehmen, sonst deutsch (TT.MM.JJJJ)."""
    if isinstance(value, dt.time):
        return value.strftime("%H:%M:%S" if value.second else "%H:%M")
    if isinstance(value, dt.timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600}:{total % 3600 // 60:02d}"
    has_time = isinstance(value, dt.datetime) and (value.hour or value.minute or value.second)
    f = (fmt or "").lower()
    f = re.sub(r"\[[^\]]*\]", "", f).replace("\\", "").replace('"', "")
    if not f or f == "general" or not any(k in f for k in ("d", "m", "y")):
        return value.strftime("%d.%m.%Y %H:%M" if has_time else "%d.%m.%Y")
    if "mmmm" in f:
        month = MONTHS[value.month - 1]
        day = f"{value.day}." if "d" in f else ""
        year = f" {value.year}" if "y" in f else ""
        return f"{day} {month}{year}".strip()
    if "dddd" in f:
        return f"{DAYS[value.weekday()]}, {value.strftime('%d.%m.%Y')}"
    out = value.strftime("%d.%m.%Y") if "d" in f and "y" in f else (
        value.strftime("%m/%Y") if "y" in f else value.strftime("%d.%m."))
    if ("h" in f or has_time) and isinstance(value, dt.datetime):
        out += value.strftime(" %H:%M")
    return out


def format_value(value, fmt):
    """Zellwert → Anzeigetext wie in Excel (deutsche Schreibweise)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "WAHR" if value else "FALSCH"
    if isinstance(value, (dt.datetime, dt.date, dt.time, dt.timedelta)):
        return format_date(value, fmt)
    if isinstance(value, (int, float)):
        f = fmt or "General"
        if f == "@":
            return str(value)
        if "%" in f:
            return _de_number(value * 100, _decimals(f), "," in f.split(".")[0]) + " %"
        if f.lower() in ("general", "standard", ""):
            if isinstance(value, float):
                if value.is_integer() and abs(value) < 1e15:
                    return _de_number(value, 0, False)
                text = f"{value:.10g}"
                return text.replace(".", ",") if "e" not in text else text.replace(".", ",").upper()
            return str(value)
        if "e+" in f.lower():
            return f"{value:.{_decimals(f)}E}".replace(".", ",")
        section = f.split(";")[0]
        thousands = "#,#" in section or "#.#" in section and "," in section
        text = _de_number(abs(value) if ";" in f and value < 0 else value, _decimals(section), thousands)
        if ";" in f and value < 0:
            text = "-" + text
        if "€" in f or "eur" in f.lower():
            text += " €"
        elif "$" in f:
            text = "$" + text
        return text
    text = str(value)
    if text.startswith("#") and text.endswith(("!", "?", "/0!", "A")):
        return text                                        # Fehlerwerte wie #DIV/0!, #NV
    return text


# ---- Blatt / Mappe ------------------------------------------------------------------------------

@dataclass
class Cell:
    text: str = ""
    formula: str = ""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    size: float = 11.0
    color: str = None
    fill: str = None
    align: str = ""        # left/center/right/"" (automatisch)
    valign: str = ""       # top/center/bottom
    wrap: bool = False
    number: bool = False   # Zahl → rechtsbündig, wenn keine Ausrichtung gesetzt
    link: str = ""
    value: object = None   # Rohwert (zum Nachrechnen von Formeln)
    fmt: str = "General"
    computed: bool = False # Wert selbst nachgerechnet (Datei hatte keinen gespeicherten)


@dataclass
class Sheet:
    name: str
    rows: int = 0
    cols: int = 0
    cells: dict = field(default_factory=dict)       # (r, c) 0-basiert → Cell
    widths: dict = field(default_factory=dict)      # Spalte → Breite in Pixeln
    heights: dict = field(default_factory=dict)     # Zeile → Höhe in Pixeln
    hidden_rows: set = field(default_factory=set)
    hidden_cols: set = field(default_factory=set)
    merged: list = field(default_factory=list)      # (r, c, rowspan, colspan)
    freeze: tuple = (0, 0)                          # fixierte Zeilen, Spalten
    truncated: bool = False
    images: int = 0
    charts: int = 0
    state: str = "visible"
    landscape: bool = False                         # Seiteneinrichtung der Datei: Querformat


@dataclass
class Workbook:
    path: str
    sheets: list
    active: int = 0
    charts: int = 0       # Diagramme in der Datei (werden nicht angezeigt)
    images: int = 0       # Bilder in der Datei (werden nicht angezeigt)


def column_px(width):
    """Excel-Spaltenbreite (Zeichen) → Pixel, wie Excel bei 100 %."""
    if width is None:
        return 64
    return max(8, int(round(width * 7 + 5)))


def load(path):
    """Mappe lesen. Wirft ValueError mit verständlicher Meldung."""
    try:
        wb_val = load_workbook(path, data_only=True, rich_text=False)
        wb_for = load_workbook(path, data_only=False, rich_text=False)
    except Exception as exc:                                  # noqa: BLE001 – Meldung für den Menschen
        msg = str(exc)
        if "encrypt" in msg.lower() or "zip" in msg.lower() and "not a zip" in msg.lower():
            raise ValueError("Die Datei ist kennwortgeschützt oder keine Excel-Datei (.xlsx).") from exc
        raise ValueError(f"Die Datei lässt sich nicht lesen: {msg}") from exc
    theme = theme_colors(wb_for)
    sheets = []
    for ws_v, ws_f in zip(wb_val.worksheets, wb_for.worksheets):
        sheets.append(_read_sheet(ws_v, ws_f, theme))
    active = 0
    try:
        active = wb_val.worksheets.index(wb_val.active)
    except ValueError:
        pass
    if sheets and sheets[active].state != "visible":
        active = next((i for i, s in enumerate(sheets) if s.state == "visible"), 0)
    charts = images = 0
    try:
        import zipfile
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        charts = sum(1 for n in names if re.match(r"xl/charts/chart\d+\.xml$", n))
        images = sum(1 for n in names if n.startswith("xl/media/"))
    except (OSError, zipfile.BadZipFile):
        pass
    return Workbook(path=str(path), sheets=sheets, active=active, charts=charts, images=images)


def _read_sheet(ws, ws_formula, theme):
    sh = Sheet(name=ws.title, state=getattr(ws, "sheet_state", "visible") or "visible")
    try:
        sh.landscape = (ws.page_setup.orientation or "").lower() == "landscape"
    except AttributeError:
        pass
    rows, cols = ws.max_row or 0, ws.max_column or 0
    if rows == 1 and cols == 1 and ws.cell(1, 1).value is None:
        rows = cols = 0
    if rows * cols > MAX_CELLS:
        rows = max(1, MAX_CELLS // max(cols, 1))
        sh.truncated = True
    sh.rows, sh.cols = rows, cols

    default_w = ws.sheet_format.defaultColWidth or (ws.sheet_format.baseColWidth or 8) + 0.71
    for c in range(cols):
        dim = ws.column_dimensions.get(get_column_letter(c + 1))
        sh.widths[c] = column_px(dim.width if dim is not None and dim.width else default_w)
    # Spaltenbereiche (min..max) aus <cols>
    for key, dim in ws.column_dimensions.items():
        lo, hi = dim.min or 0, dim.max or 0
        for c in range(max(lo, 1), min(hi, cols) + 1):
            if dim.width:
                sh.widths[c - 1] = column_px(dim.width)
            if dim.hidden:
                sh.hidden_cols.add(c - 1)
    default_h = ws.sheet_format.defaultRowHeight or 15
    for r, dim in ws.row_dimensions.items():
        if r - 1 >= rows:
            continue
        if dim.height:
            sh.heights[r - 1] = max(6, int(round(dim.height * 4 / 3)))
        if dim.hidden:
            sh.hidden_rows.add(r - 1)
    sh.heights.setdefault(-1, int(round(default_h * 4 / 3)))      # Standardhöhe

    formulas = {}
    for row in ws_formula.iter_rows(min_row=1, max_row=rows, max_col=cols):
        for c in row:
            v = c.value
            if isinstance(v, str) and v.startswith("="):
                formulas[(c.row - 1, c.column - 1)] = v
            elif v is not None and type(v).__name__ in ("ArrayFormula", "DataTableFormula"):
                formulas[(c.row - 1, c.column - 1)] = getattr(v, "text", "") or "{Matrixformel}"

    for row in ws.iter_rows(min_row=1, max_row=rows, max_col=cols):
        for c in row:
            if type(c).__name__ == "MergedCell":
                continue
            value = c.value
            key = (c.row - 1, c.column - 1)
            font, fill, al = c.font, c.fill, c.alignment
            has_style = c.has_style
            if value is None and key not in formulas and not (has_style and fill is not None
                                                              and fill.fill_type == "solid"):
                continue
            cell = Cell()
            cell.text = format_value(value, c.number_format)
            if key in formulas and value is None:
                cell.text = ""                                 # nie berechnet gespeichert
            cell.formula = formulas.get(key, "")
            cell.value = value
            cell.fmt = c.number_format or "General"
            cell.number = isinstance(value, (int, float, dt.date, dt.datetime, dt.time)) and not isinstance(value, bool)
            if font is not None:
                cell.bold = bool(font.b)
                cell.italic = bool(font.i)
                cell.underline = bool(font.u)
                cell.strike = bool(font.strike)
                cell.size = float(font.sz or 11)
                cell.color = resolve_color(font.color, theme)
            if fill is not None and fill.fill_type == "solid":
                cell.fill = resolve_color(fill.fgColor, theme) or resolve_color(fill.start_color, theme)
            if al is not None:
                h = al.horizontal or ""
                cell.align = {"centerContinuous": "center", "general": "", "fill": "left",
                              "justify": "left", "distributed": "center"}.get(h, h)
                cell.valign = {"center": "center", "top": "top"}.get(al.vertical or "", "bottom")
                cell.wrap = bool(al.wrap_text)
            if c.hyperlink is not None:
                cell.link = c.hyperlink.target or ""
            sh.cells[key] = cell

    # Zeilen ohne feste Höhe wachsen mit der größten Schrift (wie Excel)
    tallest = {}
    for (r, _c), cell in sh.cells.items():
        if cell.size > 11.5:
            tallest[r] = max(tallest.get(r, 0), cell.size)
    for r, size in tallest.items():
        if r not in sh.heights:
            sh.heights[r] = int(round(size * 4 / 3 * 1.35 + 4))

    for rng in ws.merged_cells.ranges:
        r0, c0 = rng.min_row - 1, rng.min_col - 1
        if r0 < rows and c0 < cols:
            sh.merged.append((r0, c0, rng.max_row - rng.min_row + 1, rng.max_col - rng.min_col + 1))

    _fill_missing_formulas(sh)

    pane = ws.freeze_panes
    if pane:
        m = re.match(r"([A-Z]+)(\d+)", pane)
        if m:
            from openpyxl.utils import column_index_from_string
            sh.freeze = (int(m.group(2)) - 1, column_index_from_string(m.group(1)) - 1)
    return sh


def cell_name(r, c):
    return f"{get_column_letter(c + 1)}{r + 1}"


# ---- Formeln nachrechnen (nur wenn die Datei keinen gespeicherten Wert hat) ----------------------
# Dateien aus Skripten oder manchen Programmen enthalten nur die Formel. Häufige Formeln rechnen
# wir selbst: + - * / ^, Klammern, Zellbezüge, SUMME/MITTELWERT/MIN/MAX/ANZAHL/RUNDEN/WENN/ABS.

_REF = r"\$?([A-Z]{1,3})\$?(\d+)"
_TOKEN = re.compile(rf"\s*(?:(?P<range>{_REF}:{_REF})|(?P<ref>{_REF})|(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
                    r"|(?P<str>\"[^\"]*\")|(?P<func>[A-Z][A-Z0-9.]*)\s*\(|(?P<op><>|<=|>=|[-+*/^(),<>=&%]))")
_FUNCS = {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "COUNTA", "ROUND", "ABS", "IF", "PRODUCT"}


def _col(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _translate(formula):
    """Excel-Formel → Python-Ausdruck mit Hilfsfunktionen; None, wenn etwas Unbekanntes vorkommt."""
    src = formula[1:].strip()
    out, pos = [], 0
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            return None
        pos = m.end()
        if m.group("range"):
            a, b = re.findall(_REF, m.group("range"))
            out.append(f"_rng({int(a[1]) - 1},{_col(a[0])},{int(b[1]) - 1},{_col(b[0])})")
        elif m.group("ref"):
            ref = re.findall(_REF, m.group("ref"))[0]
            out.append(f"_ref({int(ref[1]) - 1},{_col(ref[0])})")
        elif m.group("num"):
            out.append(m.group("num"))
        elif m.group("str"):
            out.append(repr(m.group("str")[1:-1]))
        elif m.group("func"):
            name = m.group("func").upper()
            if name not in _FUNCS:
                return None
            out.append(f"_f_{name}(")
        else:
            op = m.group("op")
            out.append({"^": "**", "=": "==", "<>": "!=", "&": "+", "%": "/100"}.get(op, op))
    return "".join(out)


def _flat(args):
    for a in args:
        if isinstance(a, list):
            yield from a
        else:
            yield a


def _nums(args):
    return [v for v in _flat(args) if isinstance(v, (int, float)) and not isinstance(v, bool)]


_HELPERS = {
    "_f_SUM": lambda *a: sum(_nums(a)),
    "_f_PRODUCT": lambda *a: __import__("math").prod(_nums(a)) if _nums(a) else 0,
    "_f_AVERAGE": lambda *a: (sum(_nums(a)) / len(_nums(a))) if _nums(a) else "#DIV/0!",
    "_f_MIN": lambda *a: min(_nums(a)) if _nums(a) else 0,
    "_f_MAX": lambda *a: max(_nums(a)) if _nums(a) else 0,
    "_f_COUNT": lambda *a: len(_nums(a)),
    "_f_COUNTA": lambda *a: sum(1 for v in _flat(a) if v not in (None, "")),
    "_f_ROUND": lambda v, d=0: round(v, int(d)),
    "_f_ABS": lambda v: abs(v),
    "_f_IF": lambda c, a=True, b=False: a if c else b,
}


def _fill_missing_formulas(sh):
    todo = {k: c for k, c in sh.cells.items() if c.formula and c.value is None}
    if not todo:
        return
    cache, busy = {}, set()

    def value(r, c):
        key = (r, c)
        if key in cache:
            return cache[key]
        cell = sh.cells.get(key)
        if cell is None:
            return None
        if key not in todo:
            return cell.value
        if key in busy:
            raise ValueError("Zirkelbezug")
        busy.add(key)
        try:
            expr = _translate(cell.formula)
            if expr is None:
                raise ValueError("unbekannt")
            env = dict(_HELPERS)
            env["_ref"] = lambda rr, cc: value(rr, cc) if value(rr, cc) is not None else 0
            env["_rng"] = lambda r0, c0, r1, c1: [value(rr, cc) for rr in range(r0, r1 + 1) for cc in range(c0, c1 + 1)]
            result = eval(expr, {"__builtins__": {}}, env)   # nur übersetzte, geprüfte Ausdrücke
        except ZeroDivisionError:
            result = "#DIV/0!"
        finally:
            busy.discard(key)
        cache[key] = result
        return result

    for (r, c), cell in todo.items():
        try:
            v = value(r, c)
        except (ValueError, TypeError, SyntaxError, RecursionError):
            continue
        cell.value = v
        cell.text = format_value(v, cell.fmt)
        cell.number = isinstance(v, (int, float)) and not isinstance(v, bool)
        cell.computed = True
