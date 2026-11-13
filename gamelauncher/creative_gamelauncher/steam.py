"""Steam-Bibliothek lesen – ohne Internet und ohne Steam-Konto-Zugang.

Installierte Spiele: steamapps/appmanifest_*.acf in allen Bibliotheksordnern.
Weitere Spiele aus der Bibliothek: Steams eigener Bild-Zwischenspeicher
(appcache/librarycache) und die zuletzt gespielten Spiele (localconfig.vdf);
Namen und Art („game“) stehen in appcache/appinfo.vdf (Binärformat).
"""

import os
import re
import struct
from pathlib import Path

TOOLS = re.compile(r"proton|steam linux runtime|steamworks common|steamvr|redistributable|soundtrack|dedicated server|sdk$",
                   re.I)
TOOL_IDS = {228980, 1070560, 1391110, 1628350, 1493710, 2180100, 2348590, 961940, 1161040, 1580130, 1887720}


def steam_root():
    home = Path.home()
    for p in (home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root",
              home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"):
        if (p / "steamapps").is_dir():
            return p.resolve()
    return None


# ---- Text-VDF ---------------------------------------------------------------------------------

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


def parse_vdf(text):
    stack = [{}]
    key = None
    for m in _TOKEN.finditer(text):
        s, brace = m.group(1), m.group(2)
        if brace == "{":
            new = {}
            stack[-1][key if key is not None else ""] = new
            stack.append(new)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif key is None:
            key = s.replace('\\\\', '\\')
        else:
            stack[-1][key] = s.replace('\\\\', '\\')
            key = None
    return stack[0]


def _read_vdf(path):
    try:
        return parse_vdf(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def _lower(d):
    return {k.lower(): v for k, v in d.items()} if isinstance(d, dict) else {}


def library_folders(root):
    folders = [root / "steamapps"]
    data = _lower(_read_vdf(root / "steamapps/libraryfolders.vdf")).get("libraryfolders", {})
    for v in (data or {}).values():
        path = v.get("path") if isinstance(v, dict) else (v if isinstance(v, str) and v.startswith("/") else None)
        if path:
            p = Path(path) / "steamapps"
            if p.is_dir() and p.resolve() not in [f.resolve() for f in folders]:
                folders.append(p)
    return folders


def installed_games(root):
    games = {}
    for folder in library_folders(root):
        for acf in folder.glob("appmanifest_*.acf"):
            st = _lower(_read_vdf(acf).get("AppState", {}))
            try:
                appid = int(st.get("appid", "0"))
            except ValueError:
                continue
            name = st.get("name", "")
            if not appid or appid in TOOL_IDS or TOOLS.search(name):
                continue
            flags = int(st.get("stateflags", "0") or 0)
            todo = int(st.get("bytestodownload", "0") or 0)
            done = int(st.get("bytesdownloaded", "0") or 0)
            ready = bool(flags & 4) and not (flags & 1024 and todo and done < todo)
            games[appid] = {
                "appid": appid, "name": name, "installed": True, "ready": ready,
                "size": int(st.get("sizeondisk", "0") or 0),
                "progress": (done / todo) if todo and not ready else (1.0 if ready else 0.0),
                "lastPlayed": int(st.get("lastplayed", "0") or 0),
            }
    return games


def current_user(root):
    """userdata-Ordner des zuletzt angemeldeten Kontos."""
    users = _lower(_read_vdf(root / "config/loginusers.vdf")).get("users", {})
    best = None
    for sid, u in (users or {}).items():
        u = _lower(u)
        try:
            account = int(sid) - 76561197960265728
        except ValueError:
            continue
        stamp = int(u.get("timestamp", "0") or 0) + (10 ** 12 if u.get("mostrecent") == "1" else 0)
        if best is None or stamp > best[0]:
            best = (stamp, account)
    if best:
        p = root / "userdata" / str(best[1])
        if p.is_dir():
            return p
    dirs = [d for d in (root / "userdata").glob("*") if d.name.isdigit() and d.name != "0"]
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def play_stats(root):
    """{appid: (zuletzt gespielt, Minuten)} aus localconfig.vdf."""
    user = current_user(root)
    if user is None:
        return {}
    data = _read_vdf(user / "config/localconfig.vdf")
    node = data
    for key in ("UserLocalConfigStore", "Software", "Valve", "Steam"):
        node = next((v for k, v in node.items() if k.lower() == key.lower() and isinstance(v, dict)), {})
    apps = next((v for k, v in node.items() if k.lower() == "apps" and isinstance(v, dict)), {})
    out = {}
    for sid, v in apps.items():
        if sid.isdigit() and isinstance(v, dict):
            v = _lower(v)
            out[int(sid)] = (int(v.get("lastplayed", "0") or 0), int(v.get("playtime", "0") or 0))
    return out


# ---- appinfo.vdf (Binär) ------------------------------------------------------------------------

def _read_cstr(buf, pos):
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def _parse_kv(buf, pos, strings):
    """Binäres KeyValues ab pos; gibt (dict, neue Position)."""
    out = {}
    while True:
        t = buf[pos]
        pos += 1
        if t == 0x08:
            return out, pos
        if strings is not None:
            idx = struct.unpack_from("<i", buf, pos)[0]
            pos += 4
            key = strings[idx] if 0 <= idx < len(strings) else str(idx)
        else:
            key, pos = _read_cstr(buf, pos)
        if t == 0x00:
            val, pos = _parse_kv(buf, pos, strings)
        elif t == 0x01:
            val, pos = _read_cstr(buf, pos)
        elif t in (0x02, 0x04, 0x06):
            val = struct.unpack_from("<i", buf, pos)[0]
            pos += 4
        elif t == 0x03:
            val = struct.unpack_from("<f", buf, pos)[0]
            pos += 4
        elif t in (0x07, 0x0A):
            val = struct.unpack_from("<Q", buf, pos)[0]
            pos += 8
        else:
            raise ValueError(f"unbekannter Typ {t}")
        out[key] = val


def appinfo(root, wanted):
    """{appid: {"name", "type"}} für die gewünschten appids aus appcache/appinfo.vdf."""
    path = root / "appcache/appinfo.vdf"
    try:
        buf = path.read_bytes()
    except OSError:
        return {}
    magic, _universe = struct.unpack_from("<II", buf, 0)
    version = magic & 0xFF
    pos = 8
    strings = None
    if version >= 0x29:
        table = struct.unpack_from("<q", buf, pos)[0]
        pos += 8
        count = struct.unpack_from("<I", buf, table)[0]
        p = table + 4
        strings = []
        for _ in range(count):
            s, p = _read_cstr(buf, p)
            strings.append(s)
    out = {}
    while pos + 8 <= len(buf):
        appid, size = struct.unpack_from("<II", buf, pos)
        if appid == 0:
            break
        start = pos + 8
        end = start + size
        if appid in wanted:
            # info_state, last_updated, access_token, sha1, change_number, (binary_sha1)
            kv_pos = start + 4 + 4 + 8 + 20 + 4 + (20 if version >= 0x28 else 0)
            try:
                kv, _ = _parse_kv(buf, kv_pos, strings)
                info = _lower(kv.get("appinfo", kv))
                common = _lower(info.get("common", {}))
                out[appid] = {"name": str(common.get("name", "")), "type": str(common.get("type", "")).lower()}
            except (ValueError, IndexError, struct.error):
                pass
        pos = end
    return out


# ---- Bilder -----------------------------------------------------------------------------------------

def _cached_ids(root):
    ids = set()
    lc = root / "appcache/librarycache"
    if lc.is_dir():
        for entry in os.scandir(lc):
            m = re.match(r"^(\d+)(?:_|$)", entry.name)
            if m:
                ids.add(int(m.group(1)))
    return ids


def image(root, appid, kind):
    """Lokales Bild aus Steams Zwischenspeicher: kind = cover | hero | header."""
    names = {"cover": ("library_600x900_2x", "library_600x900", "library_capsule"),
             "hero": ("library_hero", "library_hero_blur"),
             "header": ("header", "library_header")}[kind]
    lc = root / "appcache/librarycache"
    folder = lc / str(appid)
    for n in names:
        for ext in (".jpg", ".png"):
            p = lc / f"{appid}_{n}{ext}"
            if p.is_file():
                return str(p)
        if folder.is_dir():
            for ext in (".jpg", ".png"):
                p = folder / f"{n}{ext}"
                if p.is_file():
                    return str(p)
                hits = sorted(folder.glob(f"*/{n}{ext}"))
                if hits:
                    return str(hits[0])
    return ""


CDN = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/{name}"
CDN_NAMES = {"cover": "library_600x900_2x.jpg", "hero": "library_hero.jpg", "header": "header.jpg"}


# ---- Gesamtliste -------------------------------------------------------------------------------------

def library(root=None):
    """Alle Spiele: installierte + weitere aus der Bibliothek, sortiert nach zuletzt gespielt."""
    root = root or steam_root()
    if root is None:
        return None, []
    games = installed_games(root)
    stats = play_stats(root)
    candidates = (_cached_ids(root) | set(stats)) - set(games) - TOOL_IDS
    info = appinfo(root, candidates | set(g for g in games if not games[g]["name"]))
    for appid in candidates:
        meta = info.get(appid)
        if not meta or meta["type"] != "game" or not meta["name"] or TOOLS.search(meta["name"]):
            continue
        games[appid] = {"appid": appid, "name": meta["name"], "installed": False, "ready": False,
                        "size": 0, "progress": 0.0, "lastPlayed": 0}
    for appid, g in games.items():
        if not g["name"] and appid in info:
            g["name"] = info[appid]["name"]
        last, minutes = stats.get(appid, (0, 0))
        g["lastPlayed"] = max(g["lastPlayed"], last)
        g["minutes"] = minutes
    out = sorted(games.values(), key=lambda g: (-g["lastPlayed"], g["name"].casefold()))
    return root, [g for g in out if g["name"]]
