"""„Öffnen mit“: installierte Apps zu einer Datei finden und damit öffnen.

Liest die .desktop-Dateien (System, eigene unter ~/.local/share, Flatpak) und
die mimeapps.list-Dateien. Ohne Qt, damit es auch der Schreibtisch nutzen kann
und sich ohne Bildschirm testen lässt.

- apps_for(mimes): passende Apps zuerst (Standard-App ganz oben), dann alle
  anderen Apps, die eine Datei annehmen können.
- set_default(mime, desktop_id): „Immer mit dieser App öffnen“ – schreibt wie
  `xdg-mime default` in ~/.config/mimeapps.list.
- launch(desktop_id, paths): startet die App mit den Dateien.
"""

import configparser
import locale
import os
import shlex
import shutil
import subprocess
from pathlib import Path

FILE_CODES = ("%f", "%F", "%u", "%U")
DESKTOPS = {"kde", "creative", "gibeon"}       # für OnlyShowIn/NotShowIn
OWN_PREFIXES = ("creative-", "gibeon-", "orbit-")


def data_dirs():
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    dirs = [home] + (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    dirs += [str(Path.home() / ".local/share/flatpak/exports/share"), "/var/lib/flatpak/exports/share"]
    seen, result = set(), []
    for d in dirs:
        if d and d not in seen:
            seen.add(d)
            result.append(Path(d))
    return result


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))


def _langs():
    lang = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG")
            or (locale.getlocale()[0] or "de_DE"))
    lang = lang.split(".")[0].split("@")[0]
    result = [lang, lang.split("_")[0]]
    return result if "de" in result else result + ["de"]


def _localized(section, key, langs):
    for lang in langs:
        value = section.get(f"{key}[{lang}]")
        if value:
            return value
    return section.get(key, "")


def _split(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


class App:
    __slots__ = ("id", "path", "name", "icon", "exec", "terminal", "mimes", "takes_files", "listed")

    def as_dict(self, default=False):
        return {"id": self.id, "name": self.name, "icon": self.icon, "isDefault": default}


def parse(path, desktop_id, langs=None):
    langs = langs or _langs()
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    if "Desktop Entry" not in parser:
        return None
    s = parser["Desktop Entry"]
    if s.get("Type") != "Application" or s.get("Hidden", "").lower() == "true":
        return None
    only = {x.lower() for x in _split(s.get("OnlyShowIn"))}
    if only and not only & DESKTOPS:
        return None
    if {x.lower() for x in _split(s.get("NotShowIn"))} & DESKTOPS:
        return None
    try_exec = s.get("TryExec")
    if try_exec and shutil.which(try_exec) is None and not os.path.exists(try_exec):
        return None
    name, exec_line = _localized(s, "Name", langs), s.get("Exec", "")
    if not name or not exec_line:
        return None
    app = App()
    app.id, app.path, app.name = desktop_id, str(path), name
    app.icon = s.get("Icon", "")
    app.exec = exec_line
    app.terminal = s.get("Terminal", "").lower() == "true"
    app.mimes = _split(s.get("MimeType"))
    app.takes_files = any(code in exec_line for code in FILE_CODES)
    # Im Startmenü versteckte Apps (z. B. Bildbetrachter) nur dort zeigen, wo sie zur Datei passen
    app.listed = s.get("NoDisplay", "").lower() != "true"
    return app


def installed_apps(dirs=None):
    """Alle Apps, nach Desktop-ID (die erste Fundstelle gewinnt, wie bei XDG)."""
    apps, langs = {}, _langs()
    for base in dirs or data_dirs():
        root = base / "applications"
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.desktop")):
            desktop_id = str(path.relative_to(root)).replace(os.sep, "-")
            if desktop_id in apps:
                continue
            app = parse(path, desktop_id, langs)
            apps[desktop_id] = app            # None merkt sich: versteckt/ungültig, nicht weitersuchen
    return {k: v for k, v in apps.items() if v is not None}


def _mimeapps_files(dirs=None):
    files = [config_home() / "mimeapps.list"]
    for d in (os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg").split(":"):
        if d:
            files.append(Path(d) / "mimeapps.list")
    for base in dirs or data_dirs():
        files.append(base / "applications" / "mimeapps.list")
    return files


def _read_list(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    return parser


def default_app(mimes, apps, dirs=None):
    """Desktop-ID der Standard-App für den ersten Dateityp, der eine hat."""
    lists = [p for p in (_read_list(f) for f in _mimeapps_files(dirs)) if p is not None]
    for mime in mimes:
        for parser in lists:
            if parser.has_section("Default Applications"):
                for desktop_id in _split(parser["Default Applications"].get(mime)):
                    if desktop_id in apps:
                        return desktop_id
    return ""


def _matches(app, mimes):
    for want in app.mimes:
        if want in mimes:
            return mimes.index(want)
        if want.endswith("/*") and any(m.startswith(want[:-1]) for m in mimes):
            return len(mimes)
    return None


def apps_for(mimes, apps=None, dirs=None):
    """{'recommended': [...], 'others': [...]} – mimes: Dateityp zuerst, dann seine Obertypen."""
    apps = installed_apps(dirs) if apps is None else apps
    mimes = [m for m in mimes if m]
    default = default_app(mimes, apps, dirs)
    recommended, others = [], []
    for app in apps.values():
        rank = _matches(app, mimes)
        if rank is not None:
            recommended.append((app.id != default, rank, not app.id.startswith(OWN_PREFIXES), app.name.casefold(), app))
        elif app.takes_files and app.listed and not app.terminal:
            others.append((app.name.casefold(), app))
    recommended.sort(key=lambda t: t[:4])
    others.sort(key=lambda t: t[0])
    return {"recommended": [t[-1].as_dict(t[-1].id == default) for t in recommended],
            "others": [t[-1].as_dict() for t in others]}


def set_default(mime, desktop_id):
    """Wie `xdg-mime default`: Standard-App für einen Dateityp festlegen."""
    path = config_home() / "mimeapps.list"
    parser = _read_list(path) or configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    parser.optionxform = str
    for section in ("Default Applications", "Added Associations"):
        if not parser.has_section(section):
            parser.add_section(section)
    parser["Default Applications"][mime] = desktop_id + ";"
    added = [x for x in _split(parser["Added Associations"].get(mime)) if x != desktop_id]
    parser["Added Associations"][mime] = ";".join([desktop_id] + added) + ";"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".list.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        parser.write(fh, space_around_delimiters=False)
    tmp.replace(path)


def exec_args(app, paths):
    """Exec-Zeile nach der Desktop-Spezifikation mit Dateien füllen."""
    uris = [Path(p).resolve().as_uri() for p in paths]
    out, used = [], False
    for arg in shlex.split(app.exec):
        if arg in ("%f", "%u"):
            out.append((paths if arg == "%f" else uris)[0] if paths else "")
            used = True
        elif arg in ("%F", "%U"):
            out.extend(paths if arg == "%F" else uris)
            used = True
        elif arg == "%i":
            if app.icon:
                out += ["--icon", app.icon]
        elif arg == "%c":
            out.append(app.name)
        elif arg == "%k":
            out.append(app.path)
        elif len(arg) == 2 and arg.startswith("%"):
            continue                                  # veraltete Feldcodes (%d, %n …)
        else:
            out.append(arg.replace("%%", "%"))
    out = [a for a in out if a != ""]
    if not used and paths:
        out += list(paths)                            # App ohne Feldcode: Datei trotzdem mitgeben
    if app.terminal:
        out = ["x-terminal-emulator", "-e"] + out
    return out


def launch(desktop_id, paths, apps=None):
    """App mit den Dateien starten. Liefert True, wenn der Start geklappt hat."""
    apps = installed_apps() if apps is None else apps
    app = apps.get(desktop_id)
    if app is None:
        return False
    if not app.takes_files and len(paths) > 1:
        paths = paths[:1]
    for cmd in (["gio", "launch", app.path, *paths], exec_args(app, paths)):
        if cmd[0] == "gio" and shutil.which("gio") is None:
            continue
        try:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True, cwd=str(Path.home()))
            return True
        except OSError:
            continue
    return False
