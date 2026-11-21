"""Android-Fenster wie alle anderen Fenster: Gibeon-Rahmen und Tablet-Format.

Waydroid zeichnet jede Android-App als eigenes Wayland-Fenster, fordert dafür aber keinen
Fensterrahmen an (das Protokoll „xdg-decoration“ nutzt es nicht). KWin zeichnet deshalb keinen
Rahmen. Außerdem öffnet Android neue Fenster fest im Handy-Hochformat.

Dieser kleine Vermittler sitzt zwischen Waydroid und KWin (eigener Wayland-Socket
$XDG_RUNTIME_DIR/gibeon-android-0, den der waydroid-Wrapper beim Start einträgt):

* Für jedes Fenster fordert er bei KWin den normalen Fensterrahmen an (server-side).
* Neue App-Fenster stellt er aufs Tablet-Querformat um, Maximieren und Größe-Ziehen am
  Rahmen gibt er als neue Fenstergröße an Android weiter. Das erledigt
  /usr/libexec/gibeon-android-fenster-helper (über pkexec, ohne Passwort).
* Alles andere reicht er unverändert durch. Objekt-IDs werden umgerechnet, weil der Vermittler
  selbst Objekte (den Rahmen) anlegt, von denen Waydroid nichts weiß.

Aufruf:  gibeon-android-fenster --ensure   → läuft er (sonst starten)? gibt den Socket-Namen aus
         gibeon-android-fenster --serve    → Vermittler selbst
"""

import array
import fcntl
import heapq
import itertools
import json
import os
import re
import selectors
import socket
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from . import wayland as wl

NAME = "gibeon-android-0"
HELPER = "/usr/libexec/gibeon-android-fenster-helper"
DEFAULTS = {"rahmen": True, "tablet": True}
APP_RE = re.compile(r"^waydroid\.([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)$")
DECO_MANAGER = "zxdg_decoration_manager_v1"
DECO = "zxdg_toplevel_decoration_v1"
MODE_SERVER_SIDE = 2
TABLET_DELAY = 0.8          # Sekunden nach dem Öffnen: Fenster aufs Tablet-Format stellen
RESIZE_DELAY = 0.4          # Größe ziehen: erst nach dem Loslassen an Android weitergeben
MAX_FDS = 64            # Wayland schickt höchstens 28 pro Nachricht


def _xdg(var, fallback):
    return Path(os.environ.get(var) or Path.home() / fallback)


def conf_path():
    return _xdg("XDG_CONFIG_HOME", ".config") / "gibeon-android" / "fenster.json"


def load_config():
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(conf_path().read_text(encoding="utf-8"))
        for k in DEFAULTS:
            if isinstance(data.get(k), bool):
                cfg[k] = data[k]
    except (OSError, ValueError, AttributeError):
        pass
    return cfg


def save_config(cfg):
    p = conf_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: bool(cfg.get(k, v)) for k, v in DEFAULTS.items()}), encoding="utf-8")
    tmp.replace(p)


class Log:
    def __init__(self, path=None):
        self.path = path
        self.f = None
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.stat().st_size > 1_000_000:
                    path.replace(path.with_suffix(".log.alt"))
                self.f = open(path, "a", buffering=1, encoding="utf-8")
            except OSError:
                self.f = None

    def __call__(self, text):
        if self.f:
            self.f.write(time.strftime("%H:%M:%S ") + text + "\n")


# ---------------------------------------------------------------------------------------------
class Peer:
    """Eine Seite der Verbindung (Waydroid oder KWin) mit Ein- und Ausgabepuffer."""

    def __init__(self, sock):
        self.sock = sock
        sock.setblocking(False)
        self.inbuf = bytearray()
        self.infds = []
        self.out = deque()          # [bytes, [fds]]

    def recv(self):
        """False = Verbindung zu."""
        try:
            data, anc, _flags, _addr = self.sock.recvmsg(65536, socket.CMSG_SPACE(MAX_FDS * 4))
        except (BlockingIOError, InterruptedError):
            return True
        except OSError:
            return False
        for level, typ, payload in anc:
            if level == socket.SOL_SOCKET and typ == socket.SCM_RIGHTS:
                fds = array.array("i")
                fds.frombytes(payload[:len(payload) - len(payload) % fds.itemsize])
                self.infds.extend(fds)
        if not data and not anc:
            return False
        self.inbuf += data
        return True

    def queue(self, data, fds):
        self.out.append([data, list(fds)])

    def flush(self):
        """True = alles gesendet."""
        while self.out:
            data, fds = self.out[0]
            anc = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))] if fds else []
            try:
                n = self.sock.sendmsg([data], anc)
            except (BlockingIOError, InterruptedError):
                return False
            for fd in fds:
                _close(fd)
            if n < len(data):
                self.out[0] = [data[n:], []]
                return False
            self.out.popleft()
        return True

    def close(self):
        for fd in self.infds:
            _close(fd)
        self.infds = []
        for _data, fds in self.out:
            for fd in fds:
                _close(fd)
        self.out.clear()
        try:
            self.sock.close()
        except OSError:
            pass


def _close(fd):
    try:
        os.close(fd)
    except OSError:
        pass


class Broken(Exception):
    pass


class Top:
    """Ein Fenster (xdg_toplevel) von Waydroid."""
    __slots__ = ("cid", "sid", "surface", "deco", "app_id", "pkg", "last_size", "timer")

    def __init__(self, cid, sid, surface):
        self.cid, self.sid, self.surface = cid, sid, surface
        self.deco = None
        self.app_id = ""
        self.pkg = ""
        self.last_size = None
        self.timer = None


# ---------------------------------------------------------------------------------------------
class Conn:
    """Eine Waydroid-Verbindung samt eigener Verbindung zu KWin.

    IDs: Waydroid vergibt seine Objekt-IDs selbst (Client-Bereich). Zu KWin hin vergibt der
    Vermittler eigene, lückenlose IDs, weil er zusätzlich die Rahmen-Objekte anlegt.
    Vom Server angelegte Objekte (ab 0xFF000000) behalten ihre ID.
    """

    def __init__(self, proxy, csock, ssock):
        self.p = proxy
        self.ifaces = proxy.ifaces
        self.log = proxy.log
        self.c = Peer(csock)
        self.s = Peer(ssock)
        self.c2s = {1: 1}
        self.s2c = {1: 1}
        self.obj = {1: ("wl_display", 1)}       # Client-ID → (Schnittstelle, Version)
        self.next_sid = 2
        self.free_sids = []
        self.injected = {}                     # Server-ID → Schnittstelle (eigene Objekte)
        self.registry_sid = None
        self.deco_global = None                # (name, version)
        self.deco_mgr = None
        self.xdg_surface = {}                  # xdg_surface → wl_surface (Client-IDs)
        self.viewport = {}                     # wp_viewport → wl_surface
        self.dest = {}                         # wl_surface → (breite, höhe) laut Waydroid
        self.tops = {}                         # xdg_toplevel (Client-ID) → Top

    # ---- IDs -------------------------------------------------------------------------------
    def alloc(self):
        if self.free_sids:
            return heapq.heappop(self.free_sids)
        sid = self.next_sid
        self.next_sid += 1
        return sid

    def release(self, sid):
        if sid < wl.SERVER_ID_START:
            heapq.heappush(self.free_sids, sid)

    def _iface(self, name):
        return self.ifaces.get(name) if name else None

    # ---- Senden ----------------------------------------------------------------------------
    def to_server(self, sid, iface, name, values):
        i = self.ifaces[iface]
        op = i.opcode("request", name)
        data, fds = wl.encode(sid, op, i.requests[op], values)
        self.s.queue(data, fds)

    # ---- Waydroid → KWin -------------------------------------------------------------------
    def from_client(self):
        buf = self.c.inbuf
        while len(buf) >= 8:
            obj, word = wl.HEADER.unpack_from(buf, 0)
            size, op = word >> 16, word & 0xFFFF
            if size < 8 or size % 4:
                raise Broken("kaputte Nachricht von Waydroid")
            if len(buf) < size:
                return
            info = self.obj.get(obj)
            iface = self._iface(info[0]) if info else None
            msg = iface.requests[op] if iface and op < len(iface.requests) else None
            if msg is None:
                raise Broken(f"unbekannte Anfrage an Objekt {obj} ({info and info[0]}) #{op}")
            try:
                vals, nfd = wl.decode(msg, bytes(buf[8:size]), self.c.infds)
            except wl.Incomplete:
                return                          # Dateideskriptor kommt gleich
            except (ValueError, IndexError) as e:
                raise Broken(f"{iface.name}.{msg.name}: {e}")
            del self.c.infds[:nfd]
            del buf[:size]
            self.request(obj, op, iface, msg, vals)

    def request(self, cid, op, iface, msg, vals):
        sid = self.c2s.get(cid)
        if sid is None:
            self.log(f"Anfrage {iface.name}.{msg.name} an unbekanntes Objekt {cid} verworfen")
            _close_fds(msg, vals)
            return
        key = (iface.name, msg.name)
        if key == ("xdg_toplevel", "destroy"):
            top = self.tops.pop(cid, None)
            if top:
                self.p.cancel(top.timer)
                if top.deco:                    # erst der Rahmen, sonst meldet KWin einen Fehler
                    self.to_server(top.deco, DECO, "destroy", [])
        version = self.obj.get(cid, (None, 1))[1]
        out = []
        for (typ, ai), v in zip(msg.args, vals):
            if typ == "object":
                out.append(self.c2s.get(v, 0) if v else 0)
            elif typ == "new_id":
                nsid = self.alloc()
                if ai:
                    self._bind(v, nsid, ai, version)
                    out.append(nsid)
                else:
                    name, ver, nid = v
                    self._bind(nid, nsid, name, ver)
                    out.append((name, ver, nsid))
            else:
                out.append(v)
        data, fds = wl.encode(sid, op, msg, out)
        self.s.queue(data, fds)
        self.after_request(cid, key, vals)

    def _bind(self, cid, sid, iface, version):
        self.c2s[cid] = sid
        self.s2c[sid] = cid
        self.obj[cid] = (iface, version)

    def after_request(self, cid, key, vals):
        if key == ("xdg_wm_base", "get_xdg_surface"):
            self.xdg_surface[vals[0]] = vals[1]
        elif key == ("xdg_surface", "get_toplevel"):
            top = Top(vals[0], self.c2s[vals[0]], self.xdg_surface.get(cid))
            self.tops[vals[0]] = top
            if self.p.config()["rahmen"]:
                self.decorate(top)
        elif key == ("xdg_toplevel", "set_app_id"):
            top = self.tops.get(cid)
            if top is not None:
                top.app_id = vals[0] or ""
                m = APP_RE.match(top.app_id)
                if m and not top.pkg:
                    top.pkg = m.group(1)
                    if self.p.config()["tablet"]:
                        self.p.later(TABLET_DELAY, lambda pkg=top.pkg: self.p.helper.send(f"tablet {pkg}"))
        elif key == ("wp_viewporter", "get_viewport"):
            self.viewport[vals[0]] = vals[1]
        elif key == ("wp_viewport", "set_destination"):
            surface = self.viewport.get(cid)
            if surface is not None:
                self.dest[surface] = (vals[0], vals[1])
        elif key == ("wl_surface", "destroy"):
            self.dest.pop(cid, None)

    def decorate(self, top):
        """Bei KWin den normalen Fensterrahmen für dieses Fenster anfordern."""
        if not self.deco_global or self.registry_sid is None or DECO not in self.ifaces:
            return
        if self.deco_mgr is None:
            name, ver = self.deco_global
            self.deco_mgr = self.alloc()
            self.injected[self.deco_mgr] = DECO_MANAGER
            self.to_server(self.registry_sid, "wl_registry", "bind",
                           [name, (DECO_MANAGER, min(ver, 1), self.deco_mgr)])
        top.deco = self.alloc()
        self.injected[top.deco] = DECO
        self.to_server(self.deco_mgr, DECO_MANAGER, "get_toplevel_decoration", [top.deco, top.sid])
        self.to_server(top.deco, DECO, "set_mode", [MODE_SERVER_SIDE])

    # ---- KWin → Waydroid -------------------------------------------------------------------
    def from_server(self):
        buf = self.s.inbuf
        while len(buf) >= 8:
            obj, word = wl.HEADER.unpack_from(buf, 0)
            size, op = word >> 16, word & 0xFFFF
            if size < 8 or size % 4:
                raise Broken("kaputte Nachricht von KWin")
            if len(buf) < size:
                return
            if obj in self.injected:
                name = self.injected[obj]
            else:
                cid = self.s2c.get(obj)
                name = self.obj.get(cid, (None,))[0] if cid is not None else None
            iface = self._iface(name)
            msg = iface.events[op] if iface and op < len(iface.events) else None
            if msg is None:
                raise Broken(f"unbekannte Meldung von Objekt {obj} ({name}) #{op}")
            try:
                vals, nfd = wl.decode(msg, bytes(buf[8:size]), self.s.infds)
            except wl.Incomplete:
                return
            except (ValueError, IndexError) as e:
                raise Broken(f"{iface.name}.{msg.name}: {e}")
            del self.s.infds[:nfd]
            del buf[:size]
            self.event(obj, op, iface, msg, vals)

    def event(self, sid, op, iface, msg, vals):
        if sid in self.injected:                # Antworten an die eigenen Rahmen-Objekte
            _close_fds(msg, vals)
            return
        key = (iface.name, msg.name)
        if key == ("wl_display", "delete_id"):
            did = vals[0]
            if did in self.injected:
                del self.injected[did]
                self.release(did)
                return
            cid = self.s2c.pop(did, None)
            if cid is None:
                return
            if self.c2s.get(cid) == did:
                del self.c2s[cid]
            self.release(did)
            vals = [cid]
        elif key == ("wl_display", "error"):
            self.log(f"KWin meldet Fehler {vals[1]} an Objekt {vals[0]}: {vals[2]}")
        elif key == ("wl_registry", "global"):
            gname, giface, gver = vals
            if self.registry_sid is None:
                self.registry_sid = sid
            if giface == DECO_MANAGER and sid == self.registry_sid:
                self.deco_global = (gname, gver)
            known = self.ifaces.get(giface)
            if known is None:                   # unbekannt → Waydroid sieht es nicht
                return
            vals = [gname, giface, min(gver, known.version)]
        cid = self.s2c.get(sid)
        if key == ("xdg_toplevel", "configure"):
            top = self.tops.get(cid)
            if top is not None and top.pkg:
                self.on_configure(top, vals[0], vals[1])
                # Größe nicht an Waydroid geben: sonst stellt es den ganzen Android-Bildschirm um
                vals = [0, 0, vals[2]]
        version = self.obj.get(cid, (None, 1))[1]
        out = []
        for (typ, ai), v in zip(msg.args, vals):
            if typ == "object":
                out.append(self.s2c.get(v, 0) if v else 0)
            elif typ == "new_id":              # vom Server angelegt: ID bleibt
                self.c2s[v] = v
                self.s2c[v] = v
                self.obj[v] = (ai, version)
                out.append(v)
            else:
                out.append(v)
        data, fds = wl.encode(cid, op, msg, out)
        self.c.queue(data, fds)

    def on_configure(self, top, w, h):
        """KWin wünscht eine Größe (Maximieren, am Rahmen ziehen) → an Android weitergeben."""
        if w <= 0 or h <= 0:
            return
        cur = self.dest.get(top.surface)
        if cur and abs(cur[0] - w) <= 2 and abs(cur[1] - h) <= 2:
            self.p.cancel(top.timer)
            top.timer = None
            top.last_size = None
            return
        if top.last_size == (w, h):
            return
        top.last_size = (w, h)
        self.p.cancel(top.timer)
        top.timer = self.p.later(RESIZE_DELAY, lambda: self.p.helper.send(f"groesse {top.pkg} {w} {h}"))

    def close(self):
        for top in self.tops.values():
            self.p.cancel(top.timer)
        self.c.close()
        self.s.close()


def _close_fds(msg, vals):
    for (typ, _), v in zip(msg.args, vals):
        if typ == "fd":
            _close(v)


# ---------------------------------------------------------------------------------------------
class Helper:
    """Hilfsprogramm mit Administratorrechten – stellt die Größe von Android-Fenstern ein."""

    def __init__(self, log, logfile=None, cmd=None):
        self.log = log
        self.logfile = logfile
        self.cmd = cmd or ["pkexec", HELPER]
        self.proc = None
        self.fails = 0

    def send(self, line):
        if self.proc is None or self.proc.poll() is not None:
            if self.proc is not None:
                self.fails += 1
            if self.fails >= 3:
                return
            try:
                self.proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, text=True,
                                             stdout=self.logfile or subprocess.DEVNULL,
                                             stderr=self.logfile or subprocess.DEVNULL)
            except OSError as e:
                self.log(f"Hilfsprogramm startet nicht: {e}")
                self.fails += 1
                self.proc = None
                return
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            self.log(f"→ {line}")
        except (BrokenPipeError, OSError):
            self.proc = None
            self.fails += 1


class Proxy:
    def __init__(self, listen_path, upstream, ifaces=None, log=None, helper=None):
        self.listen_path = listen_path
        self.upstream = upstream
        self.ifaces = ifaces if ifaces is not None else wl.load_protocols()
        self.log = log or Log()
        self.helper = helper or Helper(self.log)
        self.sel = selectors.DefaultSelector()
        self.conns = set()
        self.timers = []
        self._seq = itertools.count()
        self._cfg = (0.0, dict(DEFAULTS))
        self.lsock = None
        self.running = True

    def config(self):
        t, cfg = self._cfg
        if time.monotonic() - t > 2:
            cfg = load_config()
            self._cfg = (time.monotonic(), cfg)
        return cfg

    # ---- Zeitgeber ----------------------------------------------------------------------------
    def later(self, delay, fn):
        t = [time.monotonic() + delay, next(self._seq), fn]
        heapq.heappush(self.timers, t)
        return t

    def cancel(self, t):
        if t is not None:
            t[2] = None

    def _run_timers(self):
        now = time.monotonic()
        while self.timers and self.timers[0][0] <= now:
            _, _, fn = heapq.heappop(self.timers)
            if fn:
                try:
                    fn()
                except Exception as e:      # ein Zeitgeber darf den Vermittler nicht beenden
                    self.log(f"Zeitgeber: {e}")

    # ---- Verbindungen -------------------------------------------------------------------------
    def listen(self):
        try:
            os.unlink(self.listen_path)
        except FileNotFoundError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(self.listen_path)
        os.chmod(self.listen_path, 0o777)       # Waydroid greift aus dem Android-Container zu
        s.listen(8)
        s.setblocking(False)
        self.lsock = s
        self.sel.register(s, selectors.EVENT_READ, ("listen", None))

    def _accept(self):
        try:
            csock, _ = self.lsock.accept()
        except (BlockingIOError, InterruptedError):
            return
        ssock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            ssock.connect(self.upstream)
        except OSError as e:
            self.log(f"KWin nicht erreichbar ({self.upstream}): {e}")
            csock.close()
            ssock.close()
            return
        conn = Conn(self, csock, ssock)
        self.conns.add(conn)
        self.sel.register(conn.c.sock, selectors.EVENT_READ, ("c", conn))
        self.sel.register(conn.s.sock, selectors.EVENT_READ, ("s", conn))
        self.log("Waydroid verbunden")

    def _drop(self, conn, why):
        if conn not in self.conns:
            return
        self.log(f"Verbindung beendet: {why}")
        self.conns.discard(conn)
        for p in (conn.c, conn.s):
            try:
                self.sel.unregister(p.sock)
            except (KeyError, ValueError):
                pass
        conn.close()

    def _update_write(self, conn):
        for side, p in (("c", conn.c), ("s", conn.s)):
            ev = selectors.EVENT_READ | (selectors.EVENT_WRITE if p.out else 0)
            try:
                self.sel.modify(p.sock, ev, (side, conn))
            except (KeyError, ValueError):
                pass

    def step(self, timeout=1.0):
        if self.timers:
            timeout = max(0.0, min(timeout, self.timers[0][0] - time.monotonic()))
        for key, mask in self.sel.select(timeout):
            side, conn = key.data
            if side == "listen":
                self._accept()
                continue
            if conn not in self.conns:
                continue
            try:
                if mask & selectors.EVENT_READ:
                    peer = conn.c if side == "c" else conn.s
                    if not peer.recv():
                        self._drop(conn, "Waydroid beendet" if side == "c" else "KWin beendet")
                        continue
                    conn.from_client() if side == "c" else conn.from_server()
                conn.c.flush()
                conn.s.flush()
            except Broken as e:
                self._drop(conn, str(e))
                continue
            except OSError as e:
                self._drop(conn, f"Fehler: {e}")
                continue
            self._update_write(conn)
        self._run_timers()

    def serve_forever(self):
        last_check = time.monotonic()
        while self.running:
            self.step()
            if time.monotonic() - last_check > 30:
                last_check = time.monotonic()
                if not os.path.exists(self.upstream) and not self.conns:
                    self.log("Sitzung beendet – Vermittler hört auf")
                    break
        try:
            os.unlink(self.listen_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------
def runtime_dir():
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def upstream_path():
    disp = os.environ.get("WAYLAND_DISPLAY") or "wayland-0"
    return disp if disp.startswith("/") else os.path.join(runtime_dir(), disp)


def _alive(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(path)
        return True
    except OSError:
        return False
    finally:
        s.close()


def ensure():
    """Vermittler bereitstellen. Ausgabe: Name für WAYLAND_DISPLAY, sonst Rückgabe 1."""
    cfg = load_config()
    if not (cfg["rahmen"] or cfg["tablet"]):
        return 1
    if os.environ.get("WAYLAND_DISPLAY") == NAME:
        print(NAME)
        return 0
    if not os.path.exists(upstream_path()) or not wl.load_protocols():
        return 1
    path = os.path.join(runtime_dir(), NAME)
    if not _alive(path):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        subprocess.Popen([sys.executable, "-m", "gibeon_android.fenster", "--serve"], env=env, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        for _ in range(30):
            time.sleep(0.1)
            if _alive(path):
                break
        else:
            return 1
    print(NAME)
    return 0


def serve():
    path = os.path.join(runtime_dir(), NAME)
    upstream = upstream_path()
    if upstream == path:
        return 1
    lock = open(path + ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                # läuft schon
    state = _xdg("XDG_STATE_HOME", ".local/state") / "gibeon-android" / "fenster.log"
    log = Log(state)
    ifaces = wl.load_protocols()
    log(f"Vermittler startet: {len(ifaces)} Wayland-Schnittstellen, KWin unter {upstream}")
    proxy = Proxy(path, upstream, ifaces, log, Helper(log, log.f))
    proxy.listen()
    proxy.serve_forever()
    return 0


def main(argv):
    if "--ensure" in argv:
        return ensure()
    if "--serve" in argv:
        return serve()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
