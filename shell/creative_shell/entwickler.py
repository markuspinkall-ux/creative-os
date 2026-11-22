"""Entwickler-Widget (nur für den Betreiber von Gibeon OS): Besuche, Downloads, Fehlermeldungen.

Das Widget erscheint nur, wenn ein GitHub-Zugang des Repo-Besitzers eingetragen ist:

    gibeon-entwickler an        Zugang (GitHub-Token) eintragen – geprüft wird, dass er dem
                                Besitzer des Repos gehört; sonst bleibt das Widget aus
    gibeon-entwickler aus       Widget abschalten, Zugang löschen

Gespeichert in ~/.config/creative-os/entwickler.json (nur für diesen Benutzer lesbar).

Angezeigt wird:
* Besuche der GitHub-Seite (Repo) in den letzten 14 Tagen – mehr hebt GitHub nicht auf
* Wie oft das System geladen wurde: Downloads des System-Abbilds (Updates und Installationen,
  ghcr.io) und der Installations-ISOs
* Downloads der AppImages (Studio, 3D Studio)
* Offene Fehlermeldungen (GitHub-Issues mit dem Label „fehlermeldung“) – aus dem OS
  („Fehler melden“ im Startmenü) und von der Webseite
"""

import json
import os
import re
import stat
import threading
import urllib.error
import urllib.request
from pathlib import Path

REPO = "markuspinkall-ux/creative-os"
LABEL = "fehlermeldung"
API = "https://api.github.com"
PACKAGE_PAGE = "https://github.com/{repo}/pkgs/container/creative-os"


def conf_path():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "entwickler.json"


def load_conf():
    try:
        data = json.loads(conf_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_conf(data):
    path = conf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".neu")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)


def _get(url, token="", accept="application/vnd.github+json", raw=False):
    headers = {"User-Agent": "GibeonOS-Entwickler", "Accept": accept}
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read(3_000_001)
    if raw:
        return data.decode("utf-8", "replace")
    return json.loads(data)


def owner_of(repo):
    return repo.split("/", 1)[0].lower()


def check_token(token, repo=REPO):
    """Gehört der Zugang dem Besitzer des Repos? → (True, Login) oder (False, Grund)."""
    try:
        login = (_get(f"{API}/user", token).get("login") or "").lower()
    except urllib.error.HTTPError as e:
        return False, f"GitHub lehnt den Zugang ab ({e.code})."
    except (OSError, ValueError) as e:
        return False, f"GitHub nicht erreichbar ({e})."
    if login != owner_of(repo):
        return False, f"Der Zugang gehört „{login}“ – das Widget ist nur für den Besitzer von {repo}."
    return True, login


def parse_count(text):
    """„1.85K“ / „2,345“ / „3M“ → Zahl."""
    text = (text or "").strip().replace(",", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KkMm]?)", text)
    if not m:
        return None
    n = float(m.group(1))
    return int(round(n * {"": 1, "k": 1000, "m": 1_000_000}[m.group(2).lower()]))


def package_downloads(html):
    """Gesamt-Downloads des System-Abbilds von der Paketseite (GitHub hat dafür keine API)."""
    m = re.search(r"Total downloads.{0,400}?<h3([^>]*)>\s*([\d.,]+\s*[KkMm]?)\s*<", html, re.S)
    if not m:
        return None
    exact = re.search(r'title="([\d,]+)"', m.group(1))
    return parse_count(exact.group(1)) if exact else parse_count(m.group(2))


def release_downloads(releases):
    """Downloads aus den Releases: ISOs (Installationen) und AppImages."""
    iso = 0
    apps = {}
    for rel in releases or []:
        for a in rel.get("assets") or []:
            name = a.get("name") or ""
            n = int(a.get("download_count") or 0)
            if name.endswith(".iso"):
                iso += n
            elif name.endswith(".AppImage"):
                label = "Studio" if name.startswith("Gibeon-Studio") else (
                    "3D Studio" if name.startswith("Gibeon-3D-Studio") else name.removesuffix(".AppImage"))
                apps[label] = apps.get(label, 0) + n
    return iso, apps


def reports_from(issues):
    out = []
    for i in issues or []:
        if "pull_request" in i:
            continue
        body = i.get("body") or ""
        m = re.search(r"###\s*Quelle\s*\n+\s*([^\n]+)", body)
        q = (m.group(1) if m else "").strip().lower()
        quelle = "Webseite" if "web" in q else ("OS" if ("gibeon" in q or q == "os") else "")
        out.append({"title": (i.get("title") or "").strip()[:140], "url": i.get("html_url") or "",
                    "number": int(i.get("number") or 0), "quelle": quelle,
                    "datum": (i.get("created_at") or "")[:10]})
    return out


def fetch(token, repo=REPO, regionen_url="", regionen_key=""):
    """Alle Zahlen auf einmal (läuft im Hintergrund). Fehler einzelner Teile stören die anderen nicht."""
    data = {"views": None, "uniques": None, "image": None, "iso": None, "apps": {}, "reports": [],
            "regionen": None, "fehler": []}
    if regionen_url and regionen_key:
        try:
            data["regionen"] = regionen(regionen_url, regionen_key)
        except (OSError, ValueError) as e:
            data["fehler"].append(f"Regionen: {e}")
    try:
        v = _get(f"{API}/repos/{repo}/traffic/views", token)
        data["views"], data["uniques"] = int(v.get("count") or 0), int(v.get("uniques") or 0)
    except (OSError, ValueError) as e:
        data["fehler"].append(f"Besuche: {e}")
    try:
        rels = _get(f"{API}/repos/{repo}/releases?per_page=100", token)
        data["iso"], data["apps"] = release_downloads(rels)
    except (OSError, ValueError) as e:
        data["fehler"].append(f"Downloads: {e}")
    try:
        data["image"] = package_downloads(_get(PACKAGE_PAGE.format(repo=repo), raw=True, accept="text/html"))
    except (OSError, ValueError) as e:
        data["fehler"].append(f"System-Abbild: {e}")
    try:
        issues = _get(f"{API}/repos/{repo}/issues?state=open&labels={LABEL}&per_page=30", token)
        data["reports"] = reports_from(issues)
    except (OSError, ValueError) as e:
        data["fehler"].append(f"Fehlermeldungen: {e}")
    return data


LAENDER = {
    "DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz", "NL": "Niederlande", "BE": "Belgien",
    "LU": "Luxemburg", "FR": "Frankreich", "IT": "Italien", "ES": "Spanien", "PT": "Portugal",
    "GB": "Großbritannien", "IE": "Irland", "PL": "Polen", "CZ": "Tschechien", "SK": "Slowakei",
    "HU": "Ungarn", "DK": "Dänemark", "SE": "Schweden", "NO": "Norwegen", "FI": "Finnland",
    "GR": "Griechenland", "RO": "Rumänien", "BG": "Bulgarien", "HR": "Kroatien", "SI": "Slowenien",
    "RS": "Serbien", "TR": "Türkei", "UA": "Ukraine", "RU": "Russland", "US": "USA", "CA": "Kanada",
    "MX": "Mexiko", "BR": "Brasilien", "AR": "Argentinien", "AU": "Australien", "NZ": "Neuseeland",
    "JP": "Japan", "CN": "China", "KR": "Südkorea", "IN": "Indien", "ZA": "Südafrika",
}


def land_name(code):
    return LAENDER.get(code, code)


def regionen(url, key, token_unused=None):
    """Zahlen von der Regionen-Sammelstelle (Cloudflare Worker)."""
    req = urllib.request.Request(url.rstrip("/") + "/zahlen",
                                 headers={"Authorization": f"Bearer {key}", "User-Agent": "GibeonOS-Entwickler"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read(1_000_000))


def regionen_rows(data, limit=8):
    inst = data.get("installationen") or {}
    aktiv = data.get("aktiv") or {}
    codes = sorted(set(inst) | set(aktiv), key=lambda c: (-int(inst.get(c, 0)), -int(aktiv.get(c, 0)), c))
    rows = [{"land": land_name(c), "code": c, "inst": int(inst.get(c, 0)), "aktiv": int(aktiv.get(c, 0))}
            for c in codes[:limit]]
    rest = codes[limit:]
    if rest:
        rows.append({"land": f"{len(rest)} weitere Länder", "code": "",
                     "inst": sum(int(inst.get(c, 0)) for c in rest), "aktiv": sum(int(aktiv.get(c, 0)) for c in rest)})
    return rows


def _fmt(n):
    return "–" if n is None else f"{n:,}".replace(",", ".")


def rows_from(data):
    rows = [
        {"label": "GitHub-Seite (14 Tage)", "value": f"{_fmt(data.get('views'))} Besuche"
                                                    + (f" · {_fmt(data['uniques'])} Personen" if data.get("uniques") is not None else "")},
        {"label": "System geladen (Updates + Installationen)", "value": _fmt(data.get("image"))},
        {"label": "Installations-ISOs", "value": _fmt(data.get("iso"))},
    ]
    for name, n in sorted((data.get("apps") or {}).items()):
        rows.append({"label": f"AppImage {name}", "value": _fmt(n)})
    return rows


try:
    from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
except ImportError:          # Kommandozeile ohne Qt
    QObject = None

if QObject is not None:
    from .mainthread import post

    class DevStats(QObject):
        changed = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._conf = load_conf()
            self._rows, self._reports, self._message = [], [], ""
            self._regions, self._regions_month = [], ""
            self._busy = False
            self._timer = QTimer(self)
            self._timer.setInterval(30 * 60 * 1000)
            self._timer.timeout.connect(self.refresh)
            self._timer.start()
            # Ein-/Ausschalten über die Kommandozeile: Datei beobachten
            self._poll = QTimer(self)
            self._poll.setInterval(10_000)
            self._poll.timeout.connect(self._reload)
            self._poll.start()
            QTimer.singleShot(3000, self.refresh)

        def _reload(self):
            conf = load_conf()
            if conf != self._conf:
                self._conf = conf
                self.changed.emit()
                self.refresh()

        def _enabled(self):
            return bool(self._conf.get("token")) and self._conf.get("login", "").lower() == owner_of(
                self._conf.get("repo") or REPO)

        @Slot()
        def refresh(self):
            if self._busy or not self._enabled():
                return
            self._busy = True
            self._message = "Wird geladen …" if not self._rows else ""
            self.changed.emit()
            token, repo = self._conf["token"], self._conf.get("repo") or REPO
            rurl, rkey = self._conf.get("regionen_url", ""), self._conf.get("regionen_key", "")

            def run():
                try:
                    result = fetch(token, repo, rurl, rkey)
                except Exception as e:  # noqa: BLE001
                    result = {"fehler": [str(e)]}
                post(self._done, result)

            threading.Thread(target=run, daemon=True).start()

        def _done(self, data):
            self._busy = False
            self._rows = rows_from(data)
            self._reports = data.get("reports") or []
            reg = data.get("regionen")
            self._regions = regionen_rows(reg) if reg else []
            self._regions_month = (reg or {}).get("monat", "")
            self._message = "; ".join(data.get("fehler") or [])[:200]
            self.changed.emit()

        @Slot(float, float)
        def setPos(self, x, y):
            self._conf["x"], self._conf["y"] = x, y
            try:
                save_conf(self._conf)
            except OSError:
                pass
            self.changed.emit()

        @Slot()
        def openReports(self):
            import subprocess
            repo = self._conf.get("repo") or REPO
            subprocess.Popen(["xdg-open", f"https://github.com/{repo}/issues?q=is%3Aopen+label%3A{LABEL}"],
                             start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        enabled = Property(bool, _enabled, notify=changed)
        busy = Property(bool, lambda self: self._busy, notify=changed)
        rows = Property("QVariantList", lambda self: self._rows, notify=changed)
        reports = Property("QVariantList", lambda self: self._reports, notify=changed)
        message = Property(str, lambda self: self._message, notify=changed)
        regions = Property("QVariantList", lambda self: self._regions, notify=changed)
        regionsMonth = Property(str, lambda self: self._regions_month, notify=changed)
        regionsSetup = Property(bool, lambda self: bool(self._conf.get("regionen_url")), notify=changed)
        posX = Property(float, lambda self: float(self._conf.get("x", -1.0)), notify=changed)
        posY = Property(float, lambda self: float(self._conf.get("y", -1.0)), notify=changed)
