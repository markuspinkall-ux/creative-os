"""Benutzerkonten: anzeigen (ohne Rechte), anlegen/löschen/ändern über /usr/libexec/creative-users-helper (pkexec)."""

import grp
import os
import pwd
import re
import subprocess
import unicodedata
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, Signal, Slot

HELPER = "/usr/libexec/creative-users-helper"
ICONS = Path("/var/lib/AccountsService/icons")
LOGIN_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def admins():
    try:
        return set(grp.getgrnam("wheel").gr_mem)
    except KeyError:
        return set()


def logged_in():
    try:
        out = subprocess.run(["loginctl", "list-users", "--no-legend"], capture_output=True, text=True, timeout=3).stdout
        return {line.split()[1] for line in out.splitlines() if len(line.split()) > 1}
    except (OSError, subprocess.SubprocessError):
        return set()


def initials(name):
    parts = [p for p in re.split(r"[\s._-]+", name) if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def accounts():
    me = pwd.getpwuid(os.getuid()).pw_name
    adm, active = admins(), logged_in()
    out = []
    for p in pwd.getpwall():
        if not 1000 <= p.pw_uid < 60000 or p.pw_shell.endswith(("nologin", "false")):
            continue
        name = p.pw_gecos.split(",")[0].strip() or p.pw_name
        icon = ICONS / p.pw_name
        face = Path(p.pw_dir) / ".face"
        picture = ""
        for f in (icon, face):
            try:
                if f.is_file() and os.access(f, os.R_OK):
                    picture = f.as_uri()
                    break
            except OSError:
                pass
        out.append({"login": p.pw_name, "name": name, "initials": initials(name), "picture": picture,
                    "admin": p.pw_name in adm, "me": p.pw_name == me, "active": p.pw_name in active,
                    "home": p.pw_dir})
    out.sort(key=lambda a: (not a["me"], a["name"].lower()))
    return out


def suggest_login(name):
    """„Anna Müller“ → „anna“ (bzw. „annam“, wenn „anna“ schon existiert)."""
    plain = unicodedata.normalize("NFKD", name.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe")
                                  .replace("ü", "ue").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue"))
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    words = re.findall(r"[a-z0-9]+", plain)
    if not words:
        return ""
    base = words[0] if words[0][0].isalpha() else "u" + words[0]
    taken = {p.pw_name for p in pwd.getpwall()}
    candidates = [base] + ([base + words[-1][0]] if len(words) > 1 else []) + [f"{base}{i}" for i in range(2, 20)]
    return next((c[:32] for c in candidates if c[:32] not in taken), base[:32])


class UsersModel(QObject):
    changed = Signal()
    done = Signal(bool, str)       # Erfolg, Meldung

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts = []
        self._busy = False
        self._message = ""
        self._proc = None
        self.refresh()

    @Slot()
    def refresh(self):
        self._accounts = accounts()
        self.changed.emit()

    @Slot(str, result=str)
    def suggest(self, name):
        return suggest_login(name)

    @Slot(str, result=str)
    def check(self, login):
        """Leer = in Ordnung, sonst ein Hinweis zum Benutzernamen."""
        if not login:
            return "Bitte einen Benutzernamen eingeben."
        if not LOGIN_RE.match(login):
            return "Nur Kleinbuchstaben, Ziffern, - und _, Anfang mit einem Buchstaben."
        try:
            pwd.getpwnam(login)
            return "Diesen Benutzernamen gibt es schon."
        except KeyError:
            return ""

    def _helper(self, args, stdin="", ok_text=""):
        if self._busy:
            return
        if not Path(HELPER).exists():
            self._finish(False, "Die Kontenverwaltung fehlt – bitte Creative OS aktualisieren.")
            return
        self._busy = True
        self._message = ""
        self.changed.emit()
        proc = QProcess(self)
        self._proc = proc

        def finished(code, _status):
            out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace").strip()
            err = bytes(proc.readAllStandardError()).decode("utf-8", "replace").strip()
            self._busy = False
            if code == 0:
                self._finish(True, out.splitlines()[-1] if out else ok_text)
            elif code in (126, 127):   # pkexec: abgebrochen / nicht berechtigt
                self._finish(False, "Abgebrochen – ohne Administrator-Passwort geht es nicht.")
            else:
                self._finish(False, err.splitlines()[-1] if err else "Das hat nicht geklappt.")
        proc.finished.connect(finished)
        proc.start("pkexec", [HELPER, *args])
        if stdin:
            proc.write((stdin + "\n").encode())
        proc.closeWriteChannel()

    def _finish(self, ok, text):
        self._message = text
        self.refresh()
        self.done.emit(ok, text)

    @Slot(str, str, str, bool)
    def add(self, name, login, password, admin):
        self._helper(["add", login, name.strip() or login, "1" if admin else "0"], password)

    @Slot(str, bool)
    def remove(self, login, keep_files):
        self._helper(["delete", login, "1" if keep_files else "0"])

    @Slot(str, str)
    def setPassword(self, login, password):
        self._helper(["password", login], password)

    @Slot(str, bool)
    def setAdmin(self, login, on):
        self._helper(["admin", login, "1" if on else "0"])

    accounts = Property("QVariantList", lambda self: self._accounts, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    adminCount = Property(int, lambda self: sum(1 for a in self._accounts if a["admin"]), notify=changed)
