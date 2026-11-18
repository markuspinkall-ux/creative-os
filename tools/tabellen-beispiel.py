"""Beispiel-Mappe für Tests und Vorschau: python3 tools/tabellen-beispiel.py ziel.xlsx"""
import datetime as dt
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

wb = Workbook()
ws = wb.active
ws.title = "Haushalt 2026"
ws["A1"] = "Haushaltsbuch 2026"
ws["A1"].font = Font(bold=True, size=16, color="1F3864")
ws.merge_cells("A1:E1")
head = ["Monat", "Einnahmen", "Ausgaben", "Saldo", "Sparquote"]
for i, h in enumerate(head, start=1):
    c = ws.cell(3, i, h)
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="4472C4")
    c.alignment = Alignment(horizontal="center")
months = ["Januar", "Februar", "März", "April", "Mai", "Juni"]
inc = [3250.0, 3250.0, 3400.5, 3250.0, 3550.0, 3250.0]
out = [2810.4, 2955.1, 3102.0, 2780.9, 3399.99, 2650.0]
for r, (m, a, b) in enumerate(zip(months, inc, out), start=4):
    ws.cell(r, 1, m)
    ws.cell(r, 2, a).number_format = '#,##0.00 "€"'
    ws.cell(r, 3, b).number_format = '#,##0.00 "€"'
    ws.cell(r, 4, f"=B{r}-C{r}").number_format = '#,##0.00 "€"'
    ws.cell(r, 5, f"=D{r}/B{r}").number_format = "0.0%"
ws["A11"] = "Summe"
ws["A11"].font = Font(bold=True)
ws["B11"] = "=SUM(B4:B9)"
ws["C11"] = "=SUM(C4:C9)"
ws["D11"] = "=SUM(D4:D9)"
for col in "BCD":
    ws[f"{col}11"].number_format = '#,##0.00 "€"'
    ws[f"{col}11"].font = Font(bold=True)
ws["A11"].fill = ws["B11"].fill = ws["C11"].fill = ws["D11"].fill = PatternFill("solid", fgColor="E2EFDA")
ws["A13"] = "Stand"
ws["B13"] = dt.date(2026, 11, 17)
ws["B13"].number_format = "dd.mm.yyyy"
ws["A14"] = "Notiz"
ws["B14"] = "Juni: Urlaub schon bezahlt – Rücklage für Dezember einplanen."
ws["B14"].alignment = Alignment(wrap_text=True, vertical="top")
ws.merge_cells("B14:E15")
ws.column_dimensions["A"].width = 14
for col in "BCD":
    ws.column_dimensions[col].width = 14
ws.column_dimensions["E"].width = 12
ws.freeze_panes = "A4"
ws2 = wb.create_sheet("Spiele")
ws2.append(["Titel", "Plattform", "Gespielt", "Bewertung"])
for row in [("Hollow Knight", "PC", True, 9.5), ("Hades II", "PC", False, None), ("Zelda TotK", "Switch", True, 10)]:
    ws2.append(list(row))
# Breite Liste im Querformat über mehrere Seiten (Druckprüfung)
ws3 = wb.create_sheet("Inventar")
ws3.page_setup.orientation = "landscape"
cols = ["Nr.", "Artikel", "Kategorie", "Lagerort", "Menge", "Einheit", "Einkauf", "Verkauf", "Lieferant", "Bemerkung"]
for i, h in enumerate(cols, start=1):
    c = ws3.cell(1, i, h)
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="4472C4")
for n in range(1, 81):
    ws3.append([n, f"Artikel {n:03d}", ["Kabel", "Werkzeug", "Büro", "Technik"][n % 4], f"Regal {1 + n % 7}",
                (n * 37) % 120, "Stück", round(2.5 + n * 1.17, 2), round(4.9 + n * 1.83, 2),
                ["Conrad", "Reichelt", "Amazon", "Würth"][n % 4], "Nachbestellen" if n % 9 == 0 else ""])
for col, w in zip("ABCDEFGHIJ", (6, 18, 14, 12, 9, 9, 11, 11, 14, 22)):
    ws3.column_dimensions[col].width = w
for r in range(2, 82):
    for col in "GH":
        ws3[f"{col}{r}"].number_format = '#,##0.00 "€"'
ws3.freeze_panes = "A2"
wb.save(sys.argv[1] if len(sys.argv) > 1 else "beispiel.xlsx")
