"""Profilbild und Kürzel der angemeldeten Person.

- Kürzel: Anfangsbuchstaben von Vor- und Nachname („Markus Pinkall“ → „MP“),
  sonst der erste Buchstabe des Namens bzw. Benutzernamens.
- Profilbild: ~/.face (Linux-Standard, ~/.face.icon zeigt darauf). Es wird
  quadratisch aus der Mitte zugeschnitten, rund ausgestanzt und als PNG
  gespeichert, damit Startmenü, Systemsteuerung, Sperr- und Anmeldebildschirm
  es ohne eigene Maske anzeigen können. Zusätzlich bekommt der Kontodienst
  (AccountsService) das Bild – daher kommt es auf den Anmeldebildschirm.
"""

import getpass
import json
import os
import pwd
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath

SIZE = 256
HOME = Path.home()
FACE = HOME / ".face"
FACE_ICON = HOME / ".face.icon"
PREVIEW = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache") / "creative-os" / "avatar-preview.png"


def full_name():
    try:
        gecos = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].strip()
    except KeyError:
        gecos = ""
    return gecos or getpass.getuser()


def initials(name=None):
    words = [w for w in (name if name is not None else full_name()).replace("-", " ").split() if w[:1].isalnum()]
    if len(words) >= 2:
        return (words[0][0] + words[-1][0]).upper()
    if words:
        return words[0][0].upper()
    return "?"


def avatar_path():
    return str(FACE) if FACE.is_file() and FACE.stat().st_size > 0 else ""


def round_image(source):
    """Datei → rundes 256×256-Bild (QImage) oder None, wenn kein Bild."""
    image = QImage(str(source))
    if image.isNull():
        return None
    side = min(image.width(), image.height())
    square = image.copy((image.width() - side) // 2, (image.height() - side) // 2, side, side)
    square = square.scaled(SIZE, SIZE, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    out = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, SIZE, SIZE))
    painter.setClipPath(path)
    painter.drawImage(0, 0, square)
    painter.end()
    return out


def make_preview(source):
    """Rundes Vorschaubild erzeugen → Pfad oder Fehlertext (beginnt mit „!“)."""
    image = round_image(source)
    if image is None:
        return "!Diese Datei ist kein Bild, das sich öffnen lässt."
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(PREVIEW), "PNG"):
        return "!Die Vorschau konnte nicht gespeichert werden."
    return str(PREVIEW)


def _accounts_service(icon_file):
    """Bild beim Kontodienst hinterlegen ("" = entfernen) – im Hintergrund, Fehler sind nicht schlimm."""
    if shutil.which("busctl"):
        threading.Thread(target=_accounts_call, args=(icon_file,), daemon=True).start()


def _accounts_call(icon_file):
    try:
        found = subprocess.run(
            ["busctl", "--system", "--json=short", "call", "org.freedesktop.Accounts", "/org/freedesktop/Accounts",
             "org.freedesktop.Accounts", "FindUserById", "x", str(os.getuid())],
            capture_output=True, text=True, timeout=5)
        user_path = json.loads(found.stdout)["data"][0] if found.returncode == 0 else ""
        if user_path:
            subprocess.run(["busctl", "--system", "call", "org.freedesktop.Accounts", user_path,
                            "org.freedesktop.Accounts.User", "SetIconFile", "s", icon_file],
                           capture_output=True, timeout=10)
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        pass


def apply_preview():
    """Vorschau als Profilbild übernehmen → Fehlertext oder ""."""
    if not PREVIEW.is_file():
        return "Bitte zuerst ein Bild wählen."
    try:
        tmp = FACE.with_name(".face.creative-tmp")
        shutil.copyfile(PREVIEW, tmp)
        os.chmod(tmp, 0o644)
        os.replace(tmp, FACE)
        if FACE_ICON.is_symlink() or FACE_ICON.exists():
            FACE_ICON.unlink()
        FACE_ICON.symlink_to(".face")
        PREVIEW.unlink(missing_ok=True)
    except OSError as error:
        return f"Das Bild konnte nicht gespeichert werden: {error.strerror or error}"
    _accounts_service(str(FACE))
    return ""


def discard_preview():
    PREVIEW.unlink(missing_ok=True)


def remove_avatar():
    for path in (FACE_ICON, FACE):
        try:
            if path.is_symlink() or path.exists():
                path.unlink()
        except OSError:
            pass
    _accounts_service("")
