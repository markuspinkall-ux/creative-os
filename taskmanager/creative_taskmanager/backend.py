"""Daten für das Taskmanager-Fenster: Prozesse, Leistung, Autostart, Details."""

import os
import shlex
import subprocess
import threading
import time
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
)

from creative_shell import sysstats
from creative_shell.sysstats import fmt_bits, fmt_bytes, fmt_rate, fmt_uptime

from . import procs

STATUS_DE = {"running": "Wird ausgeführt", "sleeping": "Bereit", "disk-sleep": "Wartet auf Datenträger",
             "stopped": "Angehalten", "zombie": "Beendet (Zombie)", "idle": "Leerlauf", "tracing-stop": "Angehalten"}


def fmt_pct(v):
    return f"{v:.1f} %".replace(".", ",")


def fmt_mem(n):
    return fmt_bytes(n, 1)


class RowsModel(QAbstractListModel):
    """Liste aus dicts; gleich bleibende Zeilen werden nur aktualisiert (Scrollposition bleibt)."""

    def __init__(self, roles, parent=None):
        super().__init__(parent)
        self._roles = roles
        self._names = {Qt.ItemDataRole.UserRole + i + 1: r for i, r in enumerate(roles)}
        self._rows = []

    def roleNames(self):
        return {k: QByteArray(v.encode()) for k, v in self._names.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        name = self._names.get(role)
        return self._rows[index.row()].get(name) if name else None

    def set_rows(self, rows):
        old_keys = [r.get("key") for r in self._rows]
        new_keys = [r.get("key") for r in rows]
        if old_keys == new_keys:
            self._rows = rows
            if rows:
                self.dataChanged.emit(self.index(0), self.index(len(rows) - 1))
            return
        # Kopf/Ende gleich lassen, nur die Mitte austauschen (ruhiges Scrollen)
        pre = 0
        while pre < min(len(old_keys), len(new_keys)) and old_keys[pre] == new_keys[pre]:
            pre += 1
        post = 0
        while (post < min(len(old_keys), len(new_keys)) - pre
               and old_keys[-1 - post] == new_keys[-1 - post]):
            post += 1
        old_mid = len(old_keys) - pre - post
        new_mid = len(new_keys) - pre - post
        if old_mid > 0:
            self.beginRemoveRows(QModelIndex(), pre, pre + old_mid - 1)
            self._rows = self._rows[:pre] + self._rows[pre + old_mid:]
            self.endRemoveRows()
        if new_mid > 0:
            self.beginInsertRows(QModelIndex(), pre, pre + new_mid - 1)
            self._rows = self._rows[:pre] + rows[pre:pre + new_mid] + self._rows[pre:]
            self.endInsertRows()
        self._rows = rows
        if rows:
            self.dataChanged.emit(self.index(0), self.index(len(rows) - 1))

    @Slot(int, result="QVariant")
    def get(self, row):
        return self._rows[row] if 0 <= row < len(self._rows) else None


PROC_ROLES = ["key", "type", "kind", "name", "icon", "count", "expanded", "depth", "cpu", "mem", "disk",
              "cpuText", "memText", "diskText", "cpuHeat", "memHeat", "diskHeat", "pids", "status", "label", "canExpand"]
DETAIL_ROLES = ["key", "name", "pid", "status", "user", "cpu", "mem", "cpuText", "memText", "threads", "command", "icon"]


class TaskManager(QObject):
    changed = Signal()
    perfChanged = Signal()
    autostartChanged = Signal()
    messageChanged = Signal()
    _sampled = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = procs.ProcessTable()
        self.sampler = sysstats.Sampler()
        self.procModel = RowsModel(PROC_ROLES, self)
        self.detailModel = RowsModel(DETAIL_ROLES, self)
        self._groups = ([], [], [])
        self._rows = {}
        self._expanded = set()
        self._filter = ""
        self._sort, self._desc = "", True
        self._dsort, self._ddesc = "cpu", True
        self._summary = {"cpu": "0 %", "mem": "0 %", "disk": "0 %", "net": ""}
        self._tiles = []
        self._detail = {}
        self._sel = "cpu"
        self._last = {}
        self._autostart = []
        self._message = ""
        self._busy = False
        self._paused = False
        self._interval = 1500
        self._sampled.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._msg_timer = QTimer(self)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(lambda: self._set_message(""))
        self.table.snapshot()
        QTimer.singleShot(250, self._tick)
        self.refreshAutostart()

    # ---- Abfragen im Hintergrund -----------------------------------------------------------
    def _tick(self):
        if self._busy or self._paused:
            return
        self._busy = True

        def work():
            try:
                rows = self.table.snapshot()
                groups = self.table.grouped(rows)
                sample = self.sampler.sample()
                self._sampled.emit((rows, groups, sample))
            except Exception as exc:
                print(f"creative-taskmanager: {exc}")
                self._sampled.emit(None)
        threading.Thread(target=work, daemon=True).start()

    def _apply(self, data):
        self._busy = False
        if not data:
            return
        rows, groups, sample = data
        self._rows, self._groups, self._last = rows, groups, sample
        self._build_proc_rows()
        self._build_detail_rows()
        self._summary = {
            "cpu": f"{sample.get('cpu', 0):.0f} %",
            "mem": f"{sample.get('mem', {}).get('percent', 0):.0f} %",
            "disk": f"{max([d['busy'] for d in sample.get('disks', [])] or [0]):.0f} %",
            "net": fmt_bits((sample.get("net") or {}).get("down", 0) + (sample.get("net") or {}).get("up", 0)),
            "procs": str(len(rows)),
            "apps": str(len(groups[0])),
        }
        self._tiles = sysstats.tiles(sample, self.sampler, all_disks=True)
        if self._sel not in [t["key"] for t in self._tiles] and self._tiles:
            self._sel = self._tiles[0]["key"]
        self._detail = self._make_detail(sample)
        self.changed.emit()
        self.perfChanged.emit()

    # ---- Prozesse --------------------------------------------------------------------------
    def _sorted(self, items):
        if not self._sort:
            return sorted(items, key=lambda g: g["name"].casefold())
        if self._sort == "name":
            return sorted(items, key=lambda g: g["name"].casefold(), reverse=self._desc)
        return sorted(items, key=lambda g: g[self._sort], reverse=self._desc)

    def _heat(self, g):
        total = self.table.total_mem or 1
        return (min(1.0, g["cpu"] / 50), min(1.0, g["mem"] / (total * 0.15)), min(1.0, g["disk"] / (20 * 1024 * 1024)))

    def _row(self, g, key, depth=0, expanded=False, kind=""):
        ch, mh, dh = self._heat(g)
        return {"key": key, "type": "group" if depth == 0 else "member", "kind": kind or g.get("kind", ""),
                "name": g["name"], "icon": g.get("icon", ""), "count": g.get("count", 1), "expanded": expanded,
                "depth": depth, "cpu": g["cpu"], "mem": g["mem"], "disk": g["disk"],
                "cpuText": fmt_pct(g["cpu"]), "memText": fmt_mem(g["mem"]),
                "diskText": ("0 MB/s" if g["disk"] < 50 * 1024 else fmt_rate(g["disk"])),
                "cpuHeat": ch, "memHeat": mh, "diskHeat": dh, "pids": g.get("pids") or [g.get("pid")],
                "status": STATUS_DE.get(g.get("status", ""), "") if g.get("status") in ("stopped", "zombie") else "",
                "label": "", "canExpand": g.get("count", 1) > 1}

    def _build_proc_rows(self):
        apps, bg, sysp = self._groups
        flt = self._filter.casefold()
        out = []
        for title, kind, items in (("Apps", "app", apps), ("Hintergrundprozesse", "bg", bg), ("Systemprozesse", "sys", sysp)):
            items = [g for g in items if not flt or flt in g["name"].casefold()
                     or any(flt in m["name"].casefold() or flt == str(m["pid"]) for m in g["members"])]
            if not items:
                continue
            out.append({"key": "h:" + kind, "type": "header", "kind": kind, "name": title, "label": f"{title} ({len(items)})",
                        "count": len(items), "depth": 0, "cpu": 0, "mem": 0, "disk": 0, "pids": [], "canExpand": False,
                        "expanded": False, "icon": "", "cpuText": "", "memText": "", "diskText": "",
                        "cpuHeat": 0, "memHeat": 0, "diskHeat": 0, "status": ""})
            for g in self._sorted(items):
                key = f"{kind}:{g['name']}"
                exp = key in self._expanded and g["count"] > 1
                out.append(self._row(g, key, 0, exp, kind))
                if exp:
                    members = sorted(g["members"], key=lambda m: -m["cpu"] - m["mem"] / 1e9)
                    for m in members:
                        out.append(self._row(dict(m, count=1, pids=[m["pid"]]), f"{key}:{m['pid']}", 1, False, kind))
        self.procModel.set_rows(out)

    def _build_detail_rows(self):
        flt = self._filter.casefold()
        items = []
        for r in self._rows.values():
            dn, raw = procs.display_name(r)
            if flt and flt not in dn.casefold() and flt not in raw.casefold() and flt != str(r["pid"]):
                continue
            items.append({"key": str(r["pid"]), "name": raw, "pid": r["pid"], "status": STATUS_DE.get(r["status"], r["status"]),
                          "user": r["user"], "cpu": r["cpu"], "mem": r["mem"], "cpuText": fmt_pct(r["cpu"]),
                          "memText": fmt_mem(r["mem"]), "threads": r["threads"],
                          "command": " ".join(r["cmdline"])[:300] or r["name"], "icon": ""})
        key = {"name": lambda x: x["name"].casefold(), "pid": lambda x: x["pid"], "user": lambda x: x["user"],
               "cpu": lambda x: x["cpu"], "mem": lambda x: x["mem"], "status": lambda x: x["status"]}.get(self._dsort, lambda x: x["cpu"])
        items.sort(key=key, reverse=self._ddesc)
        self.detailModel.set_rows(items)

    @Slot(str)
    def toggleExpand(self, key):
        if key in self._expanded:
            self._expanded.discard(key)
        else:
            self._expanded.add(key)
        self._build_proc_rows()

    @Slot(str)
    def sortBy(self, col):
        if self._sort == col:
            if self._desc:
                self._desc = False
            else:
                self._sort = ""          # dritter Klick: wieder nach Gruppen/Namen
        else:
            self._sort, self._desc = col, col != "name"
        self._build_proc_rows()
        self.changed.emit()

    @Slot(str)
    def sortDetails(self, col):
        if self._dsort == col:
            self._ddesc = not self._ddesc
        else:
            self._dsort, self._ddesc = col, col in ("cpu", "mem")
        self._build_detail_rows()
        self.changed.emit()

    @Slot(str)
    def setFilter(self, text):
        self._filter = text.strip()
        self._build_proc_rows()
        self._build_detail_rows()

    # ---- Beenden ---------------------------------------------------------------------------------
    @Slot("QVariantList", str, bool)
    def endTask(self, pids, name, force):
        pids = [int(p) for p in pids if p]
        if os.getpid() in pids:
            pids.remove(os.getpid())
        if not pids:
            return
        admin = procs.end_pids(pids, force)
        if admin:
            ok = procs.end_pids_admin(admin, force)
            if not ok:
                self._set_message(f"„{name}“ wurde nicht beendet (keine Berechtigung).")
                return
        self._set_message(f"„{name}“ wird beendet …")
        if not force:
            # Reagiert ein Programm nicht, wird es nach 4 Sekunden erzwungen beendet
            def later():
                rest = procs.alive(pids)
                if rest:
                    left = procs.end_pids(rest, True)
                    if left:
                        procs.end_pids_admin(left, True)
            QTimer.singleShot(4000, later)
        QTimer.singleShot(600, self._tick)

    @Slot("QVariantList")
    def openLocation(self, pids):
        for pid in pids:
            r = self._rows.get(int(pid))
            if r and r["exe"]:
                folder = str(Path(r["exe"]).parent)
                subprocess.Popen(["creative-files", folder], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        self._set_message("Der Speicherort ist nicht bekannt.")

    @Slot(str, result=bool)
    def runTask(self, command):
        command = command.strip()
        if not command:
            return False
        try:
            args = shlex.split(command)
        except ValueError:
            args = [command]
        try:
            subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            try:
                subprocess.Popen(["xdg-open", command], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self._set_message(f"„{command}“ wurde nicht gefunden.")
                return False
        self._set_message(f"„{command}“ wird gestartet …")
        return True

    @Slot(bool)
    def setPaused(self, on):
        self._paused = on
        self.changed.emit()

    @Slot(int)
    def setInterval(self, ms):
        self._interval = ms
        self._timer.setInterval(ms)
        self.changed.emit()

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()
        if text:
            self._msg_timer.start(5000)

    # ---- Leistung ----------------------------------------------------------------------------------
    @Slot(str)
    def selectPerf(self, key):
        self._sel = key
        if self._last:
            self._detail = self._make_detail(self._last)
        self.perfChanged.emit()

    def _make_detail(self, s):
        key = self._sel
        if not s or "model" not in s:
            return {}
        tile = next((t for t in self._tiles if t["key"] == key), None)
        if not tile:
            return {}
        stats, extra = [], []
        title, subtitle, unit = tile["title"], "", "Auslastung in %"
        hist = tile["history"]
        if key == "cpu":
            subtitle = s.get("model", "")
            threads = sum(r["threads"] for r in self._rows.values())
            stats = [("Auslastung", f"{s['cpu']:.0f} %"),
                     ("Geschwindigkeit", f"{(s.get('freq') or 0) / 1000:.2f} GHz".replace(".", ",")),
                     ("Prozesse", str(len(self._rows))), ("Threads", f"{threads:,}".replace(",", ".")),
                     ("Betriebszeit", fmt_uptime(s.get("uptime", 0)))]
            extra = [("Max. Geschwindigkeit", f"{(s.get('maxfreq') or 0) / 1000:.2f} GHz".replace(".", ",") if s.get("maxfreq") else "–"),
                     ("Kerne", str(s.get("physical", ""))), ("Logische Prozessoren", str(s.get("logical", ""))),
                     ("Temperatur", f"{s['temp']:.0f} °C" if s.get("temp") else "–")]
            unit = f"Auslastung in % über 60 Sekunden · {s.get('logical', '')} logische Prozessoren"
        elif key == "mem":
            m = s["mem"]
            subtitle = fmt_bytes(m["total"])
            stats = [("In Verwendung", fmt_bytes(m["used"])), ("Verfügbar", fmt_bytes(m["available"])),
                     ("Zwischengespeichert", fmt_bytes(m["cached"]))]
            extra = [("Gesamt", fmt_bytes(m["total"])),
                     ("Auslagerung", f"{fmt_bytes(m['swapUsed'])} / {fmt_bytes(m['swapTotal'])}" if m["swapTotal"] else "keine")]
            unit = "Speichernutzung in %"
        elif key.startswith("disk:"):
            d = next((x for x in s["disks"] if "disk:" + x["name"] == key), None)
            if d:
                title = f"{tile['title']} ({'Creative OS' if d['system'] else d['kind']})"
                subtitle = d["model"] or d["name"]
                stats = [("Aktive Zeit", f"{d['busy']:.0f} %"), ("Lesegeschwindigkeit", fmt_rate(d["read"])),
                         ("Schreibgeschwindigkeit", fmt_rate(d["write"]))]
                extra = [("Kapazität", fmt_bytes(d["size"], 0)), ("Typ", d["kind"]),
                         ("Systemdatenträger", "Ja" if d["system"] else "Nein"), ("Gerät", "/dev/" + d["name"])]
                unit = "Aktive Zeit in %"
        elif key == "net":
            n = s.get("net") or {}
            subtitle = n.get("name", "")
            addrs = []
            try:
                for a in psutil.net_if_addrs().get(n.get("name", ""), []):
                    if a.family.name in ("AF_INET", "AF_INET6") and not a.address.startswith("fe80"):
                        addrs.append(a.address.split("%")[0])
            except Exception:
                pass
            stats = [("Senden", fmt_bits(n.get("up", 0))), ("Empfangen", fmt_bits(n.get("down", 0)))]
            extra = [("Adapter", n.get("name", "")), ("Verbindungstyp", n.get("label", "")),
                     ("Geschwindigkeit", f"{n['speed']} Mbit/s" if n.get("speed") else "–")]
            extra += [("IPv4-Adresse" if ":" not in a else "IPv6-Adresse", a) for a in addrs[:2]]
            unit = "Durchsatz (relativ zum Höchstwert)"
        elif key == "gpu":
            g = s.get("gpu") or {}
            subtitle = g.get("name", "")
            stats = [("Auslastung", f"{g.get('util') or 0:.0f} %")]
            if g.get("total"):
                stats.append(("Grafikspeicher", f"{fmt_bytes(g.get('used') or 0)} / {fmt_bytes(g['total'])}"))
            extra = [("Temperatur", f"{g['temp']:.0f} °C" if g.get("temp") else "–")]
            unit = "Auslastung in %"
        return {"key": key, "title": title, "subtitle": subtitle, "unit": unit, "history": hist, "color": tile["color"],
                "stats": [{"label": a, "value": b} for a, b in stats],
                "extra": [{"label": a, "value": b} for a, b in extra],
                "cores": s.get("cores", []) if key == "cpu" else []}

    # ---- Autostart ---------------------------------------------------------------------------------
    @Slot()
    def refreshAutostart(self):
        try:
            self._autostart = procs.list_autostart()
        except Exception as exc:
            print(f"creative-taskmanager: Autostart: {exc}")
            self._autostart = []
        self.autostartChanged.emit()

    @Slot(str, bool)
    def setAutostart(self, fname, on):
        if procs.set_autostart(fname, on):
            self._set_message("Beim nächsten Anmelden " + ("wird es mitgestartet." if on else "startet es nicht mehr mit."))
        self.refreshAutostart()

    # ---- Eigenschaften -------------------------------------------------------------------------------
    summary = Property("QVariantMap", lambda self: self._summary, notify=changed)
    sortColumn = Property(str, lambda self: self._sort, notify=changed)
    sortDesc = Property(bool, lambda self: self._desc, notify=changed)
    detailSort = Property(str, lambda self: self._dsort, notify=changed)
    detailDesc = Property(bool, lambda self: self._ddesc, notify=changed)
    tiles = Property("QVariantList", lambda self: self._tiles, notify=perfChanged)
    selectedPerf = Property(str, lambda self: self._sel, notify=perfChanged)
    perfDetail = Property("QVariantMap", lambda self: self._detail, notify=perfChanged)
    autostart = Property("QVariantList", lambda self: self._autostart, notify=autostartChanged)
    message = Property(str, lambda self: self._message, notify=messageChanged)
    paused = Property(bool, lambda self: self._paused, notify=changed)
    interval = Property(int, lambda self: self._interval, notify=changed)
    processes = Property(QObject, lambda self: self.procModel, constant=True)
    details = Property(QObject, lambda self: self.detailModel, constant=True)
