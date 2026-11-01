"""Creative Pictures – Bilder ansehen wie mit „Fotos“ von Windows 11.

Sammlung: alle Bilder aus „Bilder“ (mit Unterordnern), „Downloads“ und
„Schreibtisch“, nach Monaten gruppiert; Favoriten; Ordner.
Ansicht: Zoom, Drehen (wird gespeichert), Löschen (Papierkorb),
Infos (Abmessungen, Kamera, Aufnahmedatum), Diashow, als Hintergrund.
"""

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Property, QFile, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage, QImageReader, QTransform

try:
    from PIL import ExifTags, Image as PILImage
except ImportError:
    PILImage = None

EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "svg", "heic", "heif", "avif", "jxl", "ico", "tga", "jfif"}
ANIMATED = {"gif", "webp"}
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def _user_dir(kind, fallback):
    try:
        r = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=3)
        p = r.stdout.strip()
        if r.returncode == 0 and p and p != str(Path.home()):
            return Path(p)
    except (OSError, subprocess.SubprocessError):
        pass
    for name in fallback:
        if (Path.home() / name).exists():
            return Path.home() / name
    return Path.home() / fallback[0]


def library_folders():
    return [("Bilder", _user_dir("PICTURES", ["Bilder", "Pictures"])),
            ("Downloads", _user_dir("DOWNLOAD", ["Downloads"])),
            ("Schreibtisch", _user_dir("DESKTOP", ["Schreibtisch", "Desktop"]))]


def is_image(path):
    return path.rsplit(".", 1)[-1].lower() in EXTS if "." in path else False


def _config():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os"


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return (f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}").replace(".", ",")
        n /= 1024


def scan(folders, recursive=True, limit=30000):
    out = []
    for root in folders:
        root = Path(root)
        if not root.is_dir():
            continue
        depth0 = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            if not recursive or len(Path(dirpath).parts) - depth0 >= 4:
                dirnames[:] = []
            for f in filenames:
                if f.startswith(".") or not is_image(f):
                    continue
                p = os.path.join(dirpath, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out.append((p, st.st_mtime, st.st_size))
                if len(out) >= limit:
                    return out
    return out


def group_by_month(items):
    """[(pfad, mtime, size)] → [{label, items:[{path,url,name}]}], neueste zuerst."""
    items = sorted(items, key=lambda x: -x[1])
    groups, cur = [], None
    for p, mt, _ in items:
        d = datetime.fromtimestamp(mt)
        label = f"{MONTHS[d.month - 1]} {d.year}"
        if cur is None or cur["label"] != label:
            cur = {"label": label, "items": []}
            groups.append(cur)
        cur["items"].append({"path": p, "url": QUrl.fromLocalFile(p).toString(), "name": os.path.basename(p)})
    return groups


def image_info(path):
    """Infos für die Seitenleiste."""
    info = []
    try:
        st = os.stat(path)
    except OSError:
        return []
    reader = QImageReader(path)
    size = reader.size()
    taken = None
    exif = {}
    if PILImage is not None:
        try:
            with PILImage.open(path) as im:
                if not size.isValid() or size.width() <= 0:
                    from PySide6.QtCore import QSize
                    size = QSize(*im.size)
                raw = im.getexif()
                if raw:
                    tags = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
                    try:
                        tags.update({ExifTags.TAGS.get(k, k): v for k, v in raw.get_ifd(0x8769).items()})
                    except Exception:
                        pass
                    exif = tags
        except Exception:
            pass
    dt = exif.get("DateTimeOriginal") or exif.get("DateTime")
    if isinstance(dt, str):
        try:
            taken = datetime.strptime(dt.strip(), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            taken = None
    d = taken or datetime.fromtimestamp(st.st_mtime)
    info.append(("Aufgenommen" if taken else "Geändert", d.strftime("%d.%m.%Y, %H:%M")))
    if size.isValid() and size.width() > 0:
        mp = size.width() * size.height() / 1e6
        info.append(("Abmessungen", f"{size.width()} × {size.height()} Pixel" + (f"  ·  {mp:.1f} MP".replace(".", ",") if mp >= 0.5 else "")))
    info.append(("Dateigröße", fmt_size(st.st_size)))
    info.append(("Format", path.rsplit(".", 1)[-1].upper() if "." in path else "?"))
    cam = " ".join(str(x).strip() for x in (exif.get("Make"), exif.get("Model")) if x)
    if cam:
        info.append(("Kamera", cam))
    parts = []
    if exif.get("FNumber"):
        try:
            parts.append(f"f/{float(exif['FNumber']):.1f}".replace(".", ","))
        except (TypeError, ValueError):
            pass
    if exif.get("ExposureTime"):
        try:
            t = float(exif["ExposureTime"])
            parts.append(f"1/{round(1 / t)} s" if 0 < t < 1 else f"{t:g} s")
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    if exif.get("ISOSpeedRatings") or exif.get("PhotographicSensitivity"):
        parts.append(f"ISO {exif.get('ISOSpeedRatings') or exif.get('PhotographicSensitivity')}")
    if exif.get("FocalLength"):
        try:
            parts.append(f"{float(exif['FocalLength']):.0f} mm")
        except (TypeError, ValueError):
            pass
    if parts:
        info.append(("Belichtung", "  ·  ".join(parts)))
    info.append(("Ordner", str(Path(path).parent)))
    return [{"label": a, "value": b} for a, b in info]


def rotate_file(path, degrees):
    """Dreht die Datei selbst (wie bei Windows). JPEG-Metadaten bleiben erhalten."""
    ext = path.rsplit(".", 1)[-1].lower()
    if ext in ("jpg", "jpeg", "jfif") and PILImage is not None:
        with PILImage.open(path) as im:
            exif = im.getexif()
            from PIL import ImageOps
            im2 = ImageOps.exif_transpose(im)               # vorhandene Drehung erst einrechnen
            im2 = im2.rotate(-degrees, expand=True)
            if exif:
                exif[0x0112] = 1                            # Ausrichtung: normal
            tmp = path + ".creative-tmp"
            im2.save(tmp, "JPEG", quality=95, exif=exif.tobytes() if exif else b"",
                     icc_profile=im.info.get("icc_profile"))
        os.replace(tmp, path)
        return True
    if ext in ("svg", "gif"):
        return False
    img = QImage(path)
    if img.isNull():
        return False
    img = img.transformed(QTransform().rotate(degrees))
    tmp = path + ".creative-tmp." + ext
    if not img.save(tmp):
        return False
    os.replace(tmp, path)
    return True


class Pictures(QObject):
    libraryChanged = Signal()
    viewChanged = Signal()
    infoChanged = Signal()
    favoritesChanged = Signal()
    messageChanged = Signal()
    _scanned = Signal(object, int)
    _info = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collection = "all"
        self._groups = []
        self._count = 0
        self._scanning = False
        self._scan_id = 0
        self._list = []          # Navigationsliste der Ansicht
        self._index = -1
        self._info_data = []
        self._rev = 0             # neu laden nach Drehen
        self._message = ""
        self._favs = self._load_favs()
        self._scanned.connect(self._on_scanned)
        self._info.connect(self._on_info)

    # ---- Favoriten ------------------------------------------------------------------------
    def _fav_file(self):
        return _config() / "pictures-favoriten.json"

    def _load_favs(self):
        try:
            data = json.loads(self._fav_file().read_text(encoding="utf-8"))
            return [p for p in data if isinstance(p, str)] if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save_favs(self):
        try:
            self._fav_file().parent.mkdir(parents=True, exist_ok=True)
            self._fav_file().write_text(json.dumps(self._favs, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    @Slot(str, result=bool)
    def isFavorite(self, path):
        return path in self._favs

    @Slot(str)
    def toggleFavorite(self, path):
        if path in self._favs:
            self._favs.remove(path)
        else:
            self._favs.insert(0, path)
        self._save_favs()
        self.favoritesChanged.emit()
        if self._collection == "favorites":
            self.loadCollection("favorites")

    # ---- Sammlung -----------------------------------------------------------------------------
    @Slot(str)
    def loadCollection(self, key):
        self._collection = key
        self._scanning = True
        self._scan_id += 1
        sid = self._scan_id
        self.libraryChanged.emit()

        def work():
            if key == "favorites":
                items = []
                for p in self._favs:
                    try:
                        st = os.stat(p)
                        items.append((p, st.st_mtime, st.st_size))
                    except OSError:
                        pass
            elif key.startswith("folder:"):
                items = scan([key[7:]], recursive=False)
            else:
                items = scan([p for _, p in library_folders()])
            self._scanned.emit(group_by_month(items), sid)
        threading.Thread(target=work, daemon=True).start()

    def _on_scanned(self, groups, sid):
        if sid != self._scan_id:
            return
        self._groups = groups
        self._count = sum(len(g["items"]) for g in groups)
        self._scanning = False
        self.libraryChanged.emit()

    @Slot()
    def reload(self):
        self.loadCollection(self._collection)

    @Slot(result="QVariantList")
    def folders(self):
        return [{"label": a, "key": "folder:" + str(p), "path": str(p)} for a, p in library_folders() if p.is_dir()] + \
               ([{"label": "Bildschirmfotos", "key": "folder:" + str(library_folders()[0][1] / "Bildschirmfotos"),
                  "path": str(library_folders()[0][1] / "Bildschirmfotos")}]
                if (library_folders()[0][1] / "Bildschirmfotos").is_dir() else [])

    # ---- Ansicht -------------------------------------------------------------------------------------
    @Slot(str)
    def openFromLibrary(self, path):
        self._list = [it["path"] for g in self._groups for it in g["items"]]
        self._show(path)

    def open_file(self, path):
        """Start mit einer Datei: Nachbarn im selben Ordner zum Blättern."""
        path = os.path.abspath(path)
        folder = os.path.dirname(path)
        try:
            names = sorted((f for f in os.listdir(folder) if is_image(f) and not f.startswith(".")), key=str.casefold)
        except OSError:
            names = []
        self._list = [os.path.join(folder, n) for n in names] or [path]
        self._show(path)

    def _show(self, path):
        self._index = self._list.index(path) if path in self._list else 0
        self._load_info()
        self.viewChanged.emit()

    @Slot(int)
    def step(self, delta):
        if not self._list:
            return
        self._index = (self._index + delta) % len(self._list)
        self._load_info()
        self.viewChanged.emit()

    @Slot(int)
    def goTo(self, i):
        if 0 <= i < len(self._list):
            self._index = i
            self._load_info()
            self.viewChanged.emit()

    @Slot()
    def closeView(self):
        self._index = -1
        self.viewChanged.emit()

    def _current(self):
        return self._list[self._index] if 0 <= self._index < len(self._list) else ""

    def _load_info(self):
        path = self._current()
        self._info_data = []
        self.infoChanged.emit()
        if not path:
            return

        def work():
            try:
                self._info.emit(path, image_info(path))
            except Exception:
                self._info.emit(path, [])
        threading.Thread(target=work, daemon=True).start()

    def _on_info(self, path, data):
        if path == self._current():
            self._info_data = data
            self.infoChanged.emit()

    # ---- Aktionen ---------------------------------------------------------------------------------------
    @Slot(int)
    def rotate(self, degrees):
        path = self._current()
        if not path:
            return
        try:
            ok = rotate_file(path, degrees)
        except Exception as exc:
            ok = False
            print(f"creative-pictures: Drehen fehlgeschlagen ({exc})")
        if ok:
            self._rev += 1
            self._load_info()
            self.viewChanged.emit()
        else:
            self._set_message("Dieses Bild lässt sich nicht drehen.")

    @Slot()
    def deleteCurrent(self):
        path = self._current()
        if not path:
            return
        ok = QFile.moveToTrash(path)
        ok = ok[0] if isinstance(ok, tuple) else ok
        if not ok:
            self._set_message("Das Bild konnte nicht in den Papierkorb gelegt werden.")
            return
        self._list.pop(self._index)
        if path in self._favs:
            self._favs.remove(path)
            self._save_favs()
            self.favoritesChanged.emit()
        self._set_message("In den Papierkorb gelegt.")
        if not self._list:
            self._index = -1
        else:
            self._index = min(self._index, len(self._list) - 1)
            self._load_info()
        self.viewChanged.emit()
        self.reload()

    @Slot()
    def copyImage(self):
        img = QImage(self._current())
        if not img.isNull():
            QGuiApplication.clipboard().setImage(img)
            self._set_message("Bild kopiert.")

    @Slot()
    def setWallpaper(self):
        path = self._current()
        if not path:
            return
        cfg = _config() / "shell.json"
        try:
            data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        data["wallpaper"] = path
        try:
            cfg.parent.mkdir(parents=True, exist_ok=True)
            tmp = cfg.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(cfg)
            self._set_message("Als Hintergrundbild festgelegt.")
        except OSError:
            self._set_message("Hintergrundbild konnte nicht gesetzt werden.")

    @Slot()
    def showInFolder(self):
        path = self._current()
        folder = str(Path(path).parent) if path else str(library_folders()[0][1])
        for cmd in (["creative-files", folder], ["xdg-open", folder]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return

    @Slot(str, result=bool)
    def rename(self, new_name):
        path = self._current()
        new_name = new_name.strip().replace("/", "")
        if not path or not new_name:
            return False
        ext = os.path.splitext(path)[1]
        if not os.path.splitext(new_name)[1]:
            new_name += ext
        target = os.path.join(os.path.dirname(path), new_name)
        if os.path.exists(target):
            self._set_message("Diesen Namen gibt es schon.")
            return False
        try:
            os.rename(path, target)
        except OSError as exc:
            self._set_message(f"Umbenennen nicht möglich: {exc.strerror}")
            return False
        self._list[self._index] = target
        if path in self._favs:
            self._favs[self._favs.index(path)] = target
            self._save_favs()
        self.viewChanged.emit()
        self._load_info()
        return True

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    @Slot()
    def clearMessage(self):
        self._set_message("")

    # ---- Eigenschaften ---------------------------------------------------------------------------------------
    def _cur_url(self):
        p = self._current()
        return (QUrl.fromLocalFile(p).toString() + (f"?r={self._rev}" if self._rev else "")) if p else ""

    collection = Property(str, lambda self: self._collection, notify=libraryChanged)
    groups = Property("QVariantList", lambda self: self._groups, notify=libraryChanged)
    count = Property(int, lambda self: self._count, notify=libraryChanged)
    scanning = Property(bool, lambda self: self._scanning, notify=libraryChanged)
    viewing = Property(bool, lambda self: self._index >= 0, notify=viewChanged)
    currentPath = Property(str, _current, notify=viewChanged)
    currentUrl = Property(str, _cur_url, notify=viewChanged)
    currentName = Property(str, lambda self: os.path.basename(self._current()), notify=viewChanged)
    currentAnimated = Property(bool, lambda self: self._current().rsplit(".", 1)[-1].lower() in ANIMATED, notify=viewChanged)
    index = Property(int, lambda self: self._index, notify=viewChanged)
    total = Property(int, lambda self: len(self._list), notify=viewChanged)
    strip = Property("QVariantList", lambda self: [QUrl.fromLocalFile(p).toString() for p in self._list], notify=viewChanged)
    info = Property("QVariantList", lambda self: self._info_data, notify=infoChanged)
    favorites = Property("QVariantList", lambda self: list(self._favs), notify=favoritesChanged)
    message = Property(str, lambda self: self._message, notify=messageChanged)
