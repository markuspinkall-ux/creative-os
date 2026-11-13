"""Prüfung Game Launcher: Steam-Bibliothek (gebaut) lesen + Fotos in Graphit und Porzellan.

  python3 tools/gamelauncher-test.py <ausgabeordner>
Legt ein künstliches Steam-Verzeichnis an (Manifeste, appinfo.vdf v29, Spielzeiten,
Titelbilder) und startet den Launcher mit --foto.
"""

import os
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
HOME = Path(tempfile.mkdtemp(prefix="gl-home-"))
STEAM = HOME / ".local/share/Steam"

GAMES = [  # appid, Name, installiert, Farbe, Stunden, vor Tagen
    (9100001, "Sternenfahrer", True, (59, 86, 136), 42, 1),
    (9100002, "Nordwind", True, (47, 107, 98), 7, 3),
    (9100003, "Turbo Rallye", True, (138, 74, 47), 120, 6),
    (9100004, "Schattenwald", False, (61, 53, 87), 0, 0),
    (9100005, "Pixel-Bäckerei", True, (122, 90, 42), 3, 20),
    (9100006, "Eiswüste", "lädt", (74, 102, 128), 0, 0),
    (9100007, "Rotor", True, (92, 47, 63), 11, 40),
    (9100008, "Tiefsee", False, (31, 77, 102), 2, 300),
]


def art(path, size, color, name, hero=False):
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    w, h = size
    light = tuple(min(255, c + 60) for c in color)
    dark = tuple(max(0, c - 45) for c in color)
    d.ellipse([w * 0.45, h * 0.08, w * 0.95, h * 0.08 + w * 0.5], fill=light)
    d.polygon([(0, h * 0.78), (w * 0.35, h * 0.55), (w * 0.6, h * 0.7), (w, h * 0.5), (w, h), (0, h)], fill=dark)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=88)


def vdf(d, ind=0):
    out = ""
    for k, v in d.items():
        if isinstance(v, dict):
            out += "\t" * ind + f'"{k}"\n' + "\t" * ind + "{\n" + vdf(v, ind + 1) + "\t" * ind + "}\n"
        else:
            out += "\t" * ind + f'"{k}"\t\t"{v}"\n'
    return out


def appinfo_v29(apps):
    strings = ["appinfo", "appid", "common", "name", "type"]
    sidx = {s: i for i, s in enumerate(strings)}

    def kv(d):
        b = b""
        for k, v in d.items():
            if isinstance(v, dict):
                b += b"\x00" + struct.pack("<i", sidx[k]) + kv(v)
            elif isinstance(v, int):
                b += b"\x02" + struct.pack("<i", sidx[k]) + struct.pack("<i", v)
            else:
                b += b"\x01" + struct.pack("<i", sidx[k]) + v.encode() + b"\x00"
        return b + b"\x08"

    body = b""
    for appid, name, typ in apps:
        data = kv({"appinfo": {"appid": appid, "common": {"name": name, "type": typ}}})
        head = struct.pack("<IIQ", 2, int(time.time()), 0) + b"\x00" * 20 + struct.pack("<I", 1) + b"\x00" * 20
        body += struct.pack("<II", appid, len(head) + len(data)) + head + data
    body += struct.pack("<I", 0)
    table_off = 16 + len(body)
    table = struct.pack("<I", len(strings)) + b"".join(s.encode() + b"\x00" for s in strings)
    return struct.pack("<IIq", 0x07564429, 1, table_off) + body + table


def build():
    apps = STEAM / "steamapps"
    apps.mkdir(parents=True)
    (apps / "libraryfolders.vdf").write_text(vdf({"libraryfolders": {"0": {"path": str(STEAM)}}}))
    # Proton darf nicht als Spiel erscheinen
    (apps / "appmanifest_1493710.acf").write_text(vdf({"AppState": {"appid": "1493710", "name": "Proton Experimental",
                                                                     "StateFlags": "4", "SizeOnDisk": "1000"}}))
    now = int(time.time())
    local_apps = {}
    info = []
    lc = STEAM / "appcache/librarycache"
    for appid, name, inst, color, hours, ago in GAMES:
        if inst:
            st = {"appid": str(appid), "name": name, "StateFlags": "4" if inst is True else "1026",
                  "SizeOnDisk": str(int((5 + appid % 7 * 6.3) * 1e9))}
            if inst == "lädt":
                st.update(BytesToDownload="10000000000", BytesDownloaded="6400000000")
            (apps / f"appmanifest_{appid}.acf").write_text(vdf({"AppState": st}))
        else:
            info.append((appid, name, "game"))
        if hours:
            local_apps[str(appid)] = {"LastPlayed": str(now - ago * 86400 - 3600), "Playtime": str(hours * 60)}
        art(lc / str(appid) / "library_600x900.jpg", (600, 900), color, name)
        if appid % 2:
            art(lc / str(appid) / "abc123" / "library_hero.jpg", (1920, 620), color, name, hero=True)
        else:
            art(lc / f"{appid}_library_hero.jpg", (1920, 620), color, name, hero=True)
    info.append((9100099, "Ein Soundtrack", "music"))
    (lc / "9100099").mkdir()
    (STEAM / "appcache/appinfo.vdf").write_bytes(appinfo_v29(info))
    (STEAM / "config").mkdir()
    (STEAM / "config/loginusers.vdf").write_text(vdf({"users": {"76561198000000001": {"AccountName": "markus",
                                                                                       "MostRecent": "1", "Timestamp": str(now)}}}))
    cfg = STEAM / "userdata/39734273/config"
    cfg.mkdir(parents=True)
    (cfg / "localconfig.vdf").write_text(vdf({"UserLocalConfigStore": {"Software": {"Valve": {"Steam": {"apps": local_apps}}}}}))


def check():
    sys.path.insert(0, str(ROOT / "gamelauncher"))
    os.environ["HOME"] = str(HOME)
    from creative_gamelauncher import steam
    root, games = steam.library()
    names = [g["name"] for g in games]
    print("Spiele:", names)
    assert root is not None
    assert "Proton Experimental" not in names and "Ein Soundtrack" not in names
    assert set(names) == {g[1] for g in GAMES}, names
    assert names[0] == "Sternenfahrer", "zuletzt gespielt zuerst"
    by = {g["name"]: g for g in games}
    assert not by["Schattenwald"]["installed"] and by["Tiefsee"]["minutes"] == 120
    assert by["Eiswüste"]["installed"] and not by["Eiswüste"]["ready"] and abs(by["Eiswüste"]["progress"] - 0.64) < 0.01
    assert steam.image(root, 9100001, "hero").endswith("abc123/library_hero.jpg")
    assert steam.image(root, 9100002, "hero").endswith("9100002_library_hero.jpg")
    assert steam.image(root, 9100004, "cover").endswith("library_600x900.jpg")
    print("Steam-Bibliothek: Prüfung bestanden")


def photos():
    env = dict(os.environ, HOME=str(HOME), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               PYTHONPATH=f"{ROOT / 'gamelauncher'}:{ROOT / 'shell'}")
    rc = 0
    for design in ("graphit", "porzellan"):
        for view in ("kacheln", "liste"):
            conf = HOME / f"conf-{design}-{view}"
            (conf / "creative-os").mkdir(parents=True, exist_ok=True)
            (conf / "creative-os/look.conf").write_text(f"[Look]\ndesign={design}\naccent=blau\n")
            (conf / "creative-os/gamelauncher-ansicht.conf").write_text(f"[Ansicht]\nview={view}\n")
            env["XDG_CONFIG_HOME"] = str(conf)
            name = f"launcher-{design}" + ("" if view == "kacheln" else "-liste") + ".png"
            r = subprocess.run([sys.executable, "-m", "creative_gamelauncher", "--foto", str(OUT / name)],
                               env=env, capture_output=True, text=True, timeout=120)
            print(r.stdout[-3000:], r.stderr[-3000:])
            if "QML:" in r.stdout or r.returncode != 0 or not (OUT / name).is_file():
                rc = 1
    return rc


if __name__ == "__main__":
    build()
    check()
    sys.exit(0 if os.environ.get("NUR_PRUEFEN") else photos())
