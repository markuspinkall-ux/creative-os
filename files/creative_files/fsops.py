"""Reine Datei-Logik ohne Oberfläche (dadurch auch ohne Qt testbar).

Grundsätze, damit man nichts kaputt machen kann:
- Es wird nie etwas überschrieben. Gibt es einen Namen schon, entsteht
  „Name (2).ext“ – wie bei Windows.
- Löschen heißt immer: in den Papierkorb (freedesktop-Standard, derselbe
  Papierkorb wie in allen anderen Linux-Programmen).
- Jede Aktion merkt sich, wie sie rückgängig gemacht wird.
"""

import datetime
import json
import os
import shutil
import subprocess
import urllib.parse
from pathlib import Path

HOME = Path.home()


# ---------------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------------
def format_size(size):
    if size is None:
        return ""
    units = ["Bytes", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "Bytes":
                return f"{int(value)} {'Byte' if int(value) == 1 else 'Bytes'}"
            text = f"{value:.1f}".replace(".", ",")
            if text.endswith(",0"):
                text = text[:-2]
            return f"{text} {unit}"
        value /= 1024
    return ""


def format_date(timestamp, now=None):
    now = now or datetime.datetime.now()
    dt = datetime.datetime.fromtimestamp(timestamp)
    if dt.date() == now.date():
        return f"Heute, {dt:%H:%M}"
    if dt.date() == (now - datetime.timedelta(days=1)).date():
        return f"Gestern, {dt:%H:%M}"
    return f"{dt:%d.%m.%Y}"


# ---------------------------------------------------------------------------
# Namen
# ---------------------------------------------------------------------------
INVALID_CHARS = set('/\0')


def check_name(name):
    """Gibt eine Fehlermeldung zurück oder "" wenn der Name in Ordnung ist."""
    name = name.strip()
    if not name:
        return "Bitte einen Namen eingeben."
    if name in (".", ".."):
        return "Dieser Name ist nicht erlaubt."
    if any(c in INVALID_CHARS for c in name):
        return "Der Name darf kein „/“ enthalten."
    if len(name.encode()) > 255:
        return "Der Name ist zu lang."
    return ""


def unique_path(folder, name):
    """Freier Pfad im Ordner: „Name.ext“, sonst „Name (2).ext“, „Name (3).ext“ …"""
    folder = Path(folder)
    candidate = folder / name
    if not candidate.exists() and not candidate.is_symlink():
        return candidate
    stem, suffix = name, ""
    if "." in name[1:] and not (folder / name).is_dir():
        stem, _, ext = name.rpartition(".")
        suffix = "." + ext
    n = 2
    while True:
        candidate = folder / f"{stem} ({n}){suffix}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Ordner lesen
# ---------------------------------------------------------------------------
def list_folder(path, show_hidden=False):
    entries = []
    with os.scandir(path) as it:
        for e in it:
            if not show_hidden and e.name.startswith("."):
                continue
            try:
                is_dir = e.is_dir()
                st = e.stat()
                size = None if is_dir else st.st_size
                mtime = st.st_mtime
            except OSError:  # z. B. kaputter Link
                is_dir, size, mtime = False, None, 0
            entries.append({"name": e.name, "path": e.path, "isDir": is_dir, "size": size, "mtime": mtime})
    entries.sort(key=lambda x: (not x["isDir"], x["name"].casefold()))
    return entries


def folder_size(path, limit_files=200000):
    total, count = 0, 0
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
            count += 1
            if count >= limit_files:
                return total, count, True
    return total, count, False


# ---------------------------------------------------------------------------
# Kopieren / Verschieben (nie überschreiben)
# ---------------------------------------------------------------------------
def copy_into(sources, target_dir):
    """Kopiert Dateien/Ordner in target_dir. Gibt [(quelle, ziel)] zurück."""
    done = []
    for src in sources:
        src = Path(src)
        dst = unique_path(target_dir, src.name)
        if src.is_dir() and not src.is_symlink():
            if Path(target_dir).resolve().is_relative_to(src.resolve()):
                raise ValueError(f"„{src.name}“ kann nicht in sich selbst kopiert werden.")
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst, follow_symlinks=False)
        done.append((str(src), str(dst)))
    return done


def move_into(sources, target_dir):
    done = []
    for src in sources:
        src = Path(src)
        if src.parent.resolve() == Path(target_dir).resolve():
            continue  # schon da
        if src.is_dir() and Path(target_dir).resolve().is_relative_to(src.resolve()):
            raise ValueError(f"„{src.name}“ kann nicht in sich selbst verschoben werden.")
        dst = unique_path(target_dir, src.name)
        shutil.move(str(src), str(dst))
        done.append((str(src), str(dst)))
    return done


# ---------------------------------------------------------------------------
# Papierkorb (freedesktop Trash-Spezifikation, Heimat-Papierkorb)
# ---------------------------------------------------------------------------
def trash_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(HOME / ".local" / "share")
    return Path(base) / "Trash"


def google_drive_path():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return Path(runtime) / "creative-drive" / "drive" if runtime else None


def is_google_drive(path):
    mount = google_drive_path()
    return mount is not None and Path(os.path.abspath(path)).is_relative_to(mount)


def move_to_trash(path):
    """Legt eine Datei in den Papierkorb. Gibt den Namen im Papierkorb zurück."""
    path = Path(path)
    if is_google_drive(path):
        mount = google_drive_path()
        if path == mount or not mount.is_mount():
            raise OSError("Google Drive ist nicht erreichbar.")
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        return ""  # Wiederherstellung erfolgt im Google-Drive-Papierkorb.
    # gio kennt auch Papierkörbe auf anderen Laufwerken (USB-Stick usw.)
    if shutil.which("gio"):
        before = set(trash_items_raw())
        r = subprocess.run(["gio", "trash", "--", str(path)], capture_output=True, text=True)
        if r.returncode == 0:
            after = trash_items_raw()
            new = [k for k in after if k not in before and after[k]["original"] == str(path)]
            return new[0] if new else ""
        raise OSError(r.stderr.strip() or "Konnte nicht in den Papierkorb verschieben.")
    td = trash_dir()
    (td / "files").mkdir(parents=True, exist_ok=True)
    (td / "info").mkdir(parents=True, exist_ok=True)
    target = unique_path(td / "files", path.name)
    info = td / "info" / (target.name + ".trashinfo")
    info.write_text(
        "[Trash Info]\n"
        f"Path={urllib.parse.quote(str(path.resolve()))}\n"
        f"DeletionDate={datetime.datetime.now():%Y-%m-%dT%H:%M:%S}\n",
        encoding="utf-8",
    )
    shutil.move(str(path), str(target))
    return target.name


def trash_items_raw():
    """{name_im_papierkorb: {original, deleted}}"""
    result = {}
    info_dir = trash_dir() / "info"
    if not info_dir.is_dir():
        return result
    for info in info_dir.glob("*.trashinfo"):
        original, deleted = "", ""
        try:
            for line in info.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Path="):
                    original = urllib.parse.unquote(line[5:])
                elif line.startswith("DeletionDate="):
                    deleted = line[13:]
        except OSError:
            continue
        result[info.name[: -len(".trashinfo")]] = {"original": original, "deleted": deleted}
    return result


def trash_items():
    items = []
    files = trash_dir() / "files"
    for name, meta in trash_items_raw().items():
        p = files / name
        if not p.exists() and not p.is_symlink():
            continue
        try:
            is_dir = p.is_dir()
            size = None if is_dir else p.lstat().st_size
        except OSError:
            is_dir, size = False, None
        items.append({"trashName": name, "name": Path(meta["original"]).name or name, "path": str(p),
                      "original": meta["original"], "deleted": meta["deleted"], "isDir": is_dir, "size": size})
    items.sort(key=lambda x: x["deleted"], reverse=True)
    return items


def restore_from_trash(trash_name):
    """Holt eine Datei aus dem Papierkorb zurück an ihren alten Ort."""
    meta = trash_items_raw().get(trash_name)
    if not meta:
        raise FileNotFoundError("Nicht mehr im Papierkorb.")
    original = Path(meta["original"])
    original.parent.mkdir(parents=True, exist_ok=True)
    target = unique_path(original.parent, original.name)
    shutil.move(str(trash_dir() / "files" / trash_name), str(target))
    try:
        (trash_dir() / "info" / (trash_name + ".trashinfo")).unlink()
    except OSError:
        pass
    return str(target)


def empty_trash():
    """Empty mounted trash via GIO and remove remaining local entries."""
    if shutil.which("gio"):
        subprocess.run(["gio", "trash", "--empty"], capture_output=True)
    root = trash_dir()
    for sub in ("files", "info"):
        folder = root / sub
        if root.is_symlink() or folder.is_symlink():
            raise OSError("Der Papierkorbordner ist eine symbolische Verknüpfung.")
        try:
            entries = list(folder.iterdir())
        except FileNotFoundError:
            continue
        for entry in entries:
            try:
                if not entry.is_symlink() and entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except FileNotFoundError:
                continue


# ---------------------------------------------------------------------------
# Laufwerke (lsblk)
# ---------------------------------------------------------------------------
HIDDEN_MOUNTS = {"/boot", "/boot/efi", "/efi"}
SKIP_FS = {"swap", "LVM2_member", "crypto_LUKS", "linux_raid_member", "squashfs", ""}


def drive_kind(tran, rota, name=""):
    """Bauart: „M2“ (NVMe), „SSD“ oder „Festplatte“ (dreht sich)."""
    tran = (tran or "").lower()
    if tran == "nvme" or name.startswith("nvme"):
        return "M2"
    if rota in (False, 0, "0"):
        return "SSD"
    if rota in (True, 1, "1"):
        return "Festplatte"
    return "Laufwerk"


def parse_lsblk(data, user=None):
    """Wandelt `lsblk -J -b -o …` in eine Liste von Laufwerken für „Dieser PC“.
    Das System heißt immer „Creative OS“, weitere Laufwerke nach Bauart:
    „Festplatte“, „SSD“ oder „M2“ (bei mehreren gleicher Art durchnummeriert)."""
    drives = []

    def walk(nodes, removable_parent=False, tran="", rota=None, disk=""):
        for n in nodes or []:
            removable = bool(n.get("rm")) or bool(n.get("hotplug")) or removable_parent
            if n.get("type") == "disk":
                tran, rota, disk = n.get("tran") or "", n.get("rota"), n.get("name", "")
            fstype = n.get("fstype") or ""
            mps = [m for m in (n.get("mountpoints") or [n.get("mountpoint")]) if m]
            if fstype not in SKIP_FS and n.get("type") in ("part", "disk", "crypt", "lvm"):
                if not any(m in HIDDEN_MOUNTS for m in mps):
                    system = "/" in mps or "/sysroot" in mps
                    size = n.get("fssize") or n.get("size")
                    used = n.get("fsused")
                    label = n.get("label") or ""
                    if system:
                        name, tag = "Creative OS", "System"
                    elif removable:
                        name, tag = label or "USB-Stick", "Auswerfen" if mps else "Wechseldatenträger"
                    else:
                        name = drive_kind(tran, n.get("rota", rota), disk)
                        tag = label if label and label.lower() not in (name.lower(), "creative os") else ""
                    mount = ("/sysroot" if "/sysroot" in mps else "/") if system else (mps[0] if mps else "")
                    drives.append({
                        "device": n.get("path") or "/dev/" + n.get("name", ""),
                        "name": name, "tag": tag, "system": system, "removable": removable,
                        "mounted": bool(mps), "mountPath": mount,
                        "size": int(size) if size else None, "used": int(used) if used else None,
                    })
            walk(n.get("children"), removable, tran, rota, disk)

    walk(data.get("blockdevices"))
    drives.sort(key=lambda d: (not d["system"], d["removable"], d["name"].casefold()))
    # Gleich benannte durchnummerieren: „SSD“, „SSD 2“, …
    count = {}
    for d in drives:
        if d["system"] or d["removable"]:
            continue
        count[d["name"]] = count.get(d["name"], 0) + 1
        if count[d["name"]] > 1:
            d["name"] = f"{d['name']} {count[d['name']]}"
    return drives


def list_drives():
    if not shutil.which("lsblk"):
        return []
    r = subprocess.run(
        ["lsblk", "-J", "-b", "-o", "NAME,PATH,LABEL,SIZE,FSTYPE,MOUNTPOINTS,RM,HOTPLUG,TYPE,FSSIZE,FSUSED,ROTA,TRAN"],
        capture_output=True, text=True, timeout=5,
    )
    if r.returncode != 0:
        return []
    drives = parse_lsblk(json.loads(r.stdout))
    for d in drives:
        if d["mounted"]:
            try:
                # Atomic deployments can expose a tiny read-only image at /.
                # Query the backing filesystem, not that deployment image.
                path = d["mountPath"]
                if d["system"] and Path("/run/ostree-booted").exists():
                    path = "/sysroot" if os.path.ismount("/sysroot") else "/var"
                usage = shutil.disk_usage(path)
                d["size"], d["used"], d["free"] = usage.total, usage.used, usage.free
            except OSError:
                pass
    return drives
