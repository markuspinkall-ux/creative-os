"""Akku-Anzeige für Laptops prüfen – mit nachgebautem /sys/class/power_supply (ohne Laptop).

    QT_QPA_PLATFORM=offscreen python3 tools/akku-test.py [ordner-für-fake-akku]

Mit Ordnerangabe wird dort ein Laptop-Akku (64 %, entlädt) angelegt und stehen gelassen –
für die Bildschirmfotos der Shell (CREATIVE_POWER_SUPPLY).
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shell"))
from PySide6.QtCore import QCoreApplication  # noqa: E402

app = QCoreApplication(sys.argv[:1])
from creative_shell import akku as A  # noqa: E402


def write(root, name, **values):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    for k, v in values.items():
        (d / k).write_text(f"{v}\n")


def laptop(root, status="Discharging", now=41_600_000, full=65_000_000, power=10_400_000, ac=0):
    write(root, "AC", type="Mains", online=ac)
    write(root, "BAT0", type="Battery", present=1, status=status, energy_now=now, energy_full=full,
          power_now=power, capacity=round(100 * now / full))


root = Path(tempfile.mkdtemp())
# Desktop-PC: kein Akku → nichts anzeigen
assert A.read_state(root) == {"present": False}
write(root, "hidpp_battery_0", type="Battery", present=1, scope="Device", capacity=50, status="Discharging")
assert not A.read_state(root)["present"], "Maus-Akku darf nicht als Laptop-Akku zählen"

laptop(root)
s = A.read_state(root)
assert s["present"] and s["percent"] == 64 and s["discharging"] and not s["charging"] and not s["plugged"], s
assert s["minutes"] == 240, s                                  # 41,6 Wh / 10,4 W = 4 h
assert A.status_text(s) == "Noch etwa 4 h 00 min", A.status_text(s)

laptop(root, status="Charging", power=26_000_000, ac=1)
s = A.read_state(root)
assert s["charging"] and s["plugged"] and s["minutes"] == 54, s  # (65-41,6)/26 h ≈ 54 min
assert A.status_text(s).startswith("Lädt – voll in 54 min"), A.status_text(s)

laptop(root, status="Full", now=65_000_000, power=0, ac=1)
s = A.read_state(root)
assert s["full"] and A.status_text(s) == "Voll geladen", s

laptop(root, status="Not charging", now=52_000_000, power=0, ac=1)   # Ladegrenze 80 %
assert A.status_text(A.read_state(root)) == "Voll geladen"

# Ladung statt Energie (µAh/µA) und zwei Akkus (ThinkPad)
shutil.rmtree(root / "BAT0")
write(root, "BAT0", type="Battery", present=1, status="Discharging", charge_now=2_000_000, charge_full=4_000_000,
      current_now=1_000_000, capacity=50)
write(root, "BAT1", type="Battery", present=1, status="Discharging", charge_now=3_000_000, charge_full=4_000_000,
      current_now=0, capacity=75)
(root / "AC" / "online").write_text("0\n")
s = A.read_state(root)
assert s["percent"] == 62 and s["minutes"] == 300, s
print("Akku lesen: ok (kein Akku, Maus-Akku, Entladen, Laden, voll, Ladegrenze, Ladung, zwei Akkus)")

# Warnungen bei 15 % und 5 % – je einmal, nach dem Einstecken wieder scharf
shutil.rmtree(root / "BAT1")
shutil.rmtree(root / "BAT0")
laptop(root, now=13_000_000)                                    # 20 %
m = A.Akku(root=root, interval=100000)
m._notify = lambda title, body, critical: m.notifications.append((title, body))
assert m.present and m.percent == 20 and not m.low and not m.notifications
laptop(root, now=9_100_000)                                     # 14 %
m.refresh()
assert m.low and [t for t, _ in m.notifications] == ["Akku schwach"], m.notifications
m.refresh()
laptop(root, now=8_000_000)
m.refresh()
assert len(m.notifications) == 1, "Warnung doppelt"
laptop(root, now=2_600_000)                                     # 4 %
m.refresh()
assert [t for t, _ in m.notifications] == ["Akku schwach", "Akku fast leer"], m.notifications
laptop(root, status="Charging", now=2_600_000, ac=1)
m.refresh()
assert m.charging and not m.low
laptop(root, now=9_000_000)
m.refresh()
assert m.notifications[-1][0] == "Akku schwach" and len(m.notifications) == 3, m.notifications
print("Warnungen: ok (15 % und 5 % je einmal, nach dem Laden wieder)")

if len(sys.argv) > 1:
    fake = Path(sys.argv[1])
    laptop(fake)
    print("Testakku für Fotos:", fake)
print("Akku: alles in Ordnung")
