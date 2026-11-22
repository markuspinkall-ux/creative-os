"""Android-Fenster: Der Vermittler zwischen Waydroid und KWin gibt Fenstern den Gibeon-Rahmen,
rechnet Objekt-IDs richtig um und gibt Fenstergrößen an Android weiter.

Läuft ohne Waydroid und ohne KWin: beide Seiten werden hier über Sockets nachgespielt.
Die Nachrichtenformate stehen unten als kleines XML (Auszug der echten Protokolle,
Reihenfolge der Nachrichten wie im Original).
"""

import array
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "android"))

from gibeon_android import fenster, wayland as wl  # noqa: E402

PROTO = """<protocol name="test">
<interface name="wl_display" version="1">
  <request name="sync"><arg name="callback" type="new_id" interface="wl_callback"/></request>
  <request name="get_registry"><arg name="registry" type="new_id" interface="wl_registry"/></request>
  <event name="error"><arg name="object_id" type="object"/><arg name="code" type="uint"/><arg name="message" type="string"/></event>
  <event name="delete_id"><arg name="id" type="uint"/></event>
</interface>
<interface name="wl_registry" version="1">
  <request name="bind"><arg name="name" type="uint"/><arg name="id" type="new_id"/></request>
  <event name="global"><arg name="name" type="uint"/><arg name="interface" type="string"/><arg name="version" type="uint"/></event>
  <event name="global_remove"><arg name="name" type="uint"/></event>
</interface>
<interface name="wl_callback" version="1">
  <event name="done"><arg name="callback_data" type="uint"/></event>
</interface>
<interface name="wl_compositor" version="6">
  <request name="create_surface"><arg name="id" type="new_id" interface="wl_surface"/></request>
</interface>
<interface name="wl_surface" version="6">
  <request name="destroy" type="destructor"/>
</interface>
<interface name="wl_shm" version="1">
  <request name="create_pool"><arg name="id" type="new_id" interface="wl_shm_pool"/><arg name="fd" type="fd"/><arg name="size" type="int"/></request>
</interface>
<interface name="wl_shm_pool" version="1">
  <request name="destroy" type="destructor"/>
</interface>
<interface name="xdg_wm_base" version="6">
  <request name="destroy" type="destructor"/>
  <request name="create_positioner"><arg name="id" type="new_id" interface="xdg_positioner"/></request>
  <request name="get_xdg_surface"><arg name="id" type="new_id" interface="xdg_surface"/><arg name="surface" type="object" interface="wl_surface"/></request>
  <request name="pong"><arg name="serial" type="uint"/></request>
  <event name="ping"><arg name="serial" type="uint"/></event>
</interface>
<interface name="xdg_surface" version="6">
  <request name="destroy" type="destructor"/>
  <request name="get_toplevel"><arg name="id" type="new_id" interface="xdg_toplevel"/></request>
</interface>
<interface name="xdg_toplevel" version="6">
  <request name="destroy" type="destructor"/>
  <request name="set_parent"><arg name="parent" type="object" interface="xdg_toplevel" allow-null="true"/></request>
  <request name="set_title"><arg name="title" type="string"/></request>
  <request name="set_app_id"><arg name="app_id" type="string"/></request>
  <event name="configure"><arg name="width" type="int"/><arg name="height" type="int"/><arg name="states" type="array"/></event>
  <event name="close"/>
</interface>
<interface name="wp_viewporter" version="1">
  <request name="destroy" type="destructor"/>
  <request name="get_viewport"><arg name="id" type="new_id" interface="wp_viewport"/><arg name="surface" type="object" interface="wl_surface"/></request>
</interface>
<interface name="wp_viewport" version="1">
  <request name="destroy" type="destructor"/>
  <request name="set_source"><arg name="x" type="fixed"/><arg name="y" type="fixed"/><arg name="width" type="fixed"/><arg name="height" type="fixed"/></request>
  <request name="set_destination"><arg name="width" type="int"/><arg name="height" type="int"/></request>
</interface>
<interface name="zxdg_decoration_manager_v1" version="1">
  <request name="destroy" type="destructor"/>
  <request name="get_toplevel_decoration"><arg name="id" type="new_id" interface="zxdg_toplevel_decoration_v1"/><arg name="toplevel" type="object" interface="xdg_toplevel"/></request>
</interface>
<interface name="zxdg_toplevel_decoration_v1" version="1">
  <request name="destroy" type="destructor"/>
  <request name="set_mode"><arg name="mode" type="uint"/></request>
  <request name="unset_mode"/>
  <event name="configure"><arg name="mode" type="uint"/></event>
</interface>
</protocol>
"""


class FakeHelper:
    def __init__(self):
        self.lines = []

    def send(self, line):
        self.lines.append(line)


class Side:
    """Nachgespielte Gegenseite: liest und schreibt Wayland-Nachrichten."""

    def __init__(self, sock, ifaces, kind):
        self.sock = sock
        self.sock.settimeout(0.05)
        self.ifaces = ifaces
        self.kind = kind            # "request" (wir sind Waydroid) oder "event" (wir sind KWin)
        self.types = {1: "wl_display"}
        self.buf = b""
        self.fds = []

    def send(self, obj, iface, name, values, fds=()):
        i = self.ifaces[iface]
        msgs = i.requests if self.kind == "request" else i.events
        op = i.opcode(self.kind, name)
        data, _ = wl.encode(obj, op, msgs[op], values)
        for (typ, ai), v in zip(msgs[op].args, values):
            if typ == "new_id":
                self.types[v if ai else v[2]] = ai or v[0]
        anc = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))] if fds else []
        self.sock.sendmsg([data], anc)

    def read(self, proxy, want=1, rounds=40):
        """Nachrichten der anderen Richtung: [(obj, interface, name, werte)]."""
        out = []
        for _ in range(rounds):
            proxy.step(0.01)
            try:
                data, anc, _, _ = self.sock.recvmsg(65536, socket.CMSG_SPACE(16 * 4))
                self.buf += data
                for _l, _t, payload in anc:
                    a = array.array("i")
                    a.frombytes(payload)
                    self.fds.extend(a)
            except (socket.timeout, BlockingIOError):
                pass
            while len(self.buf) >= 8:
                obj, word = wl.HEADER.unpack_from(self.buf, 0)
                size, op = word >> 16, word & 0xFFFF
                if len(self.buf) < size:
                    break
                iname = self.types[obj]
                i = self.ifaces[iname]
                msg = (i.events if self.kind == "request" else i.requests)[op]
                vals, nfd = wl.decode(msg, self.buf[8:size], self.fds)
                del self.fds[:nfd]
                self.buf = self.buf[size:]
                for (typ, ai), v in zip(msg.args, vals):
                    if typ == "new_id":
                        if ai:
                            self.types[v] = ai
                        else:
                            self.types[v[2]] = v[0]
                out.append((obj, iname, msg.name, vals))
            if len(out) >= want:
                break
        return out


class FensterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "proto").mkdir()
        (d / "proto" / "test.xml").write_text(PROTO, encoding="utf-8")
        os.environ["XDG_CONFIG_HOME"] = str(d / "config")
        self.ifaces = wl.load_protocols([d / "proto"])
        self.helper = FakeHelper()
        self.proxy = fenster.Proxy(str(d / "sock"), str(d / "up"), self.ifaces, helper=self.helper)
        c_ours, c_proxy = socket.socketpair()
        s_ours, s_proxy = socket.socketpair()
        conn = fenster.Conn(self.proxy, c_proxy, s_proxy)
        self.proxy.conns.add(conn)
        self.proxy.sel.register(conn.c.sock, 1, ("c", conn))
        self.proxy.sel.register(conn.s.sock, 1, ("s", conn))
        self.conn = conn
        self.app = Side(c_ours, self.ifaces, "request")      # spielt Waydroid
        self.kwin = Side(s_ours, self.ifaces, "event")       # spielt KWin
        self.old = (fenster.TABLET_DELAY, fenster.RESIZE_DELAY)
        fenster.TABLET_DELAY = fenster.RESIZE_DELAY = 0.05

    def tearDown(self):
        fenster.TABLET_DELAY, fenster.RESIZE_DELAY = self.old
        self.conn.close()
        self.app.sock.close()
        self.kwin.sock.close()
        self.tmp.cleanup()

    def _window(self):
        """Waydroid legt ein Fenster an, wie es der Hardware-Composer tut."""
        self.app.send(1, "wl_display", "get_registry", [2])
        self.app.types[2] = "wl_registry"
        got = self.kwin.read(self.proxy)
        self.assertEqual(got, [(1, "wl_display", "get_registry", [2])])
        for name, iface, ver in ((1, "wl_compositor", 6), (2, "xdg_wm_base", 7),
                                 (3, "zxdg_decoration_manager_v1", 1), (4, "neu_unbekannt", 1)):
            self.kwin.send(2, "wl_registry", "global", [name, iface, ver])
        got = self.app.read(self.proxy, want=3)
        # unbekannte Schnittstellen bleiben verborgen, Versionen nie höher als beschrieben
        self.assertEqual([v for *_, v in got], [[1, "wl_compositor", 6], [2, "xdg_wm_base", 6],
                                                [3, "zxdg_decoration_manager_v1", 1]])
        self.app.send(2, "wl_registry", "bind", [2, ("xdg_wm_base", 6, 3)])
        self.app.send(2, "wl_registry", "bind", [1, ("wl_compositor", 6, 4)])
        self.app.send(4, "wl_compositor", "create_surface", [5])
        self.app.send(3, "xdg_wm_base", "get_xdg_surface", [6, 5])
        self.app.send(6, "xdg_surface", "get_toplevel", [7])
        return self.kwin.read(self.proxy, want=8)

    def test_rahmen_wird_angefordert(self):
        got = self._window()
        names = [(o, n, v) for o, _i, n, v in got]
        self.assertEqual(names[:5], [(2, "bind", [2, ("xdg_wm_base", 6, 3)]),
                                     (2, "bind", [1, ("wl_compositor", 6, 4)]),
                                     (4, "create_surface", [5]),
                                     (3, "get_xdg_surface", [6, 5]),
                                     (6, "get_toplevel", [7])])
        # eigene Objekte mit den nächsten freien IDs: Rahmen-Verwalter 8, Rahmen 9
        self.assertEqual(names[5:], [(2, "bind", [3, ("zxdg_decoration_manager_v1", 1, 8)]),
                                     (8, "get_toplevel_decoration", [9, 7]),
                                     (9, "set_mode", [fenster.MODE_SERVER_SIDE])])

    def test_ids_werden_umgerechnet(self):
        self._window()
        self.app.send(1, "wl_display", "sync", [8])           # Waydroid kennt die 8 noch als frei
        self.app.types[8] = "wl_callback"
        got = self.kwin.read(self.proxy)
        self.assertEqual(got, [(1, "wl_display", "sync", [10])])
        self.kwin.send(9, "zxdg_toplevel_decoration_v1", "configure", [2])   # nur für uns
        self.kwin.send(10, "wl_callback", "done", [42])
        self.kwin.send(1, "wl_display", "delete_id", [10])
        got = self.app.read(self.proxy, want=2)
        self.assertEqual([(o, n, v) for o, _i, n, v in got], [(8, "done", [42]), (1, "delete_id", [8])])
        # freigegebene 10 wird wiederverwendet
        self.app.send(1, "wl_display", "sync", [8])
        self.assertEqual(self.kwin.read(self.proxy), [(1, "wl_display", "sync", [10])])

    def test_tablet_und_groesse(self):
        self._window()
        self.app.send(7, "xdg_toplevel", "set_app_id", ["waydroid.com.example.app"])
        self.kwin.read(self.proxy)
        deadline = time.monotonic() + 1
        while not self.helper.lines and time.monotonic() < deadline:
            self.proxy.step(0.02)
        self.assertEqual(self.helper.lines, ["tablet com.example.app"])
        # Maximieren: KWin wünscht 1600×900 → Waydroid bekommt 0×0, Android die neue Größe
        self.kwin.send(7, "xdg_toplevel", "configure", [1600, 900, b"\x01\x00\x00\x00"])
        got = self.app.read(self.proxy)
        self.assertEqual(got, [(7, "xdg_toplevel", "configure", [0, 0, b"\x01\x00\x00\x00"])])
        deadline = time.monotonic() + 1
        while len(self.helper.lines) < 2 and time.monotonic() < deadline:
            self.proxy.step(0.02)
        self.assertEqual(self.helper.lines[1], "groesse com.example.app 1600 900")

    def test_gleiche_groesse_wird_nicht_gemeldet(self):
        self._window()
        self.app.send(7, "xdg_toplevel", "set_app_id", ["waydroid.com.example.app"])
        self.app.send(1, "wl_display", "get_registry", [8])
        self.kwin.read(self.proxy, want=2)
        self.helper.lines.clear()
        self.conn.dest[5] = (1280, 800)
        self.conn.on_configure(self.conn.tops[7], 1281, 800)
        for _ in range(10):
            self.proxy.step(0.02)
        self.assertNotIn("groesse com.example.app 1281 800", self.helper.lines)

    def test_vollbild_fenster_unveraendert(self):
        """Das Fenster „Waydroid“ (ganze Android-Oberfläche) behält die Größen von KWin."""
        self._window()
        self.app.send(7, "xdg_toplevel", "set_app_id", ["Waydroid"])
        self.kwin.read(self.proxy)
        self.kwin.send(7, "xdg_toplevel", "configure", [1920, 1040, b""])
        self.assertEqual(self.app.read(self.proxy), [(7, "xdg_toplevel", "configure", [1920, 1040, b""])])

    def test_rahmen_vor_fenster_entfernt(self):
        self._window()
        self.app.send(7, "xdg_toplevel", "destroy", [])
        got = self.kwin.read(self.proxy, want=2)
        self.assertEqual([(o, n) for o, _i, n, _v in got], [(9, "destroy"), (7, "destroy")])

    def test_ohne_rahmen_einstellung(self):
        fenster.save_config({"rahmen": False, "tablet": True})
        self.proxy._cfg = (0.0, {})
        got = self._window()
        self.assertEqual(len(got), 5)
        self.assertNotIn("set_mode", [n for _o, _i, n, _v in got])

    def test_dateideskriptor_wird_durchgereicht(self):
        self.app.send(1, "wl_display", "get_registry", [2])
        self.app.types[2] = "wl_registry"
        self.kwin.read(self.proxy)
        self.kwin.send(2, "wl_registry", "global", [5, "wl_shm", 1])
        self.app.read(self.proxy)
        self.app.send(2, "wl_registry", "bind", [5, ("wl_shm", 1, 3)])
        r, w = os.pipe()
        self.app.send(3, "wl_shm", "create_pool", [4, r, 4096], fds=[r])
        os.close(r)
        got = self.kwin.read(self.proxy, want=2)
        self.assertEqual(got[1][2], "create_pool")
        fd = got[1][3][1]
        os.write(w, b"ok")
        self.assertEqual(os.read(fd, 2), b"ok")
        os.close(fd)
        os.close(w)

    def test_konfiguration(self):
        self.assertEqual(fenster.load_config(), fenster.DEFAULTS)
        fenster.save_config({"rahmen": False, "tablet": True})
        self.assertEqual(fenster.load_config(), {"rahmen": False, "tablet": True})


class HelperTest(unittest.TestCase):
    def setUp(self):
        import importlib.machinery
        import importlib.util
        path = str(ROOT / "android/gibeon-android-fenster-helper")
        loader = importlib.machinery.SourceFileLoader("fenster_helper", path)
        spec = importlib.util.spec_from_loader("fenster_helper", loader)
        self.h = importlib.util.module_from_spec(spec)
        loader.exec_module(self.h)

    def test_tablet_quer_und_mittig(self):
        left, top, right, bottom = self.h.bounds_tablet(1920, 1080)
        w, h = right - left, bottom - top
        self.assertGreater(w, h)
        self.assertLessEqual(h, 1080 * 0.86)
        self.assertEqual(left, (1920 - w) // 2)
        self.assertAlmostEqual(w / h, 1.6, places=1)

    def test_groesse_begrenzt(self):
        self.assertEqual(self.h.bounds_size(1920, 1080, 5000, 50), (0, 420, 1920, 660))

    def test_nur_gueltige_pakete(self):
        for bad in ("com.x'; reboot", "x", "com..x", "-com.x"):
            self.assertIsNone(self.h.PKG.match(bad), bad)
        self.assertTrue(self.h.PKG.match("com.android.vending"))

    def test_skripte(self):
        script = self.h.INFO % "com.example.app"
        res = subprocess.run(["sh", "-n"], input=script, text=True, capture_output=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_wrapper_und_abbild(self):
        res = subprocess.run(["sh", "-n", str(ROOT / "android/waydroid-wrapper")], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        cf = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
        for part in ("/usr/libexec/gibeon-android-fenster", "/usr/libexec/gibeon-android-fenster-helper",
                     "wayland-protocols-devel", "@WAYDROID@"):
            self.assertIn(part, cf)
        policy = (ROOT / "android/org.creativeos.android.policy").read_text(encoding="utf-8")
        self.assertIn("/usr/libexec/gibeon-android-fenster-helper", policy)


if __name__ == "__main__":
    unittest.main()


class AppStartImHintergrund(unittest.TestCase):
    """App anklicken, Android läuft noch nicht: Android unsichtbar starten, dann nur die App öffnen
    (statt der ganzen LineageOS-Oberfläche)."""

    def test_erst_hochfahren_dann_app(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            log = d / "log"
            fake = d / "waydroid-echt"
            # Falsches waydroid: läuft nach „session start“, ist zwei Abfragen später hochgefahren
            fake.write_text(f"""#!/bin/sh
echo "$*" >> {log}
case "$1 $2" in
  "session start") touch {d}/laeuft ;;
  "status ") [ -e {d}/laeuft ] && echo "Session:	RUNNING" || echo "Session:	STOPPED" ;;
  "prop get") if [ "$3" = init.svc.bootanim ]; then
                b=$(cat {d}/anim 2>/dev/null || echo 0); b=$((b+1)); echo $b > {d}/anim
                [ $b -ge 2 ] && echo stopped || echo running
              else
                n=$(cat {d}/zaehler 2>/dev/null || echo 0); n=$((n+1)); echo $n > {d}/zaehler
                [ $n -ge 2 ] && echo 1 || echo 0
              fi ;;
esac
""")
            fake.chmod(0o755)
            wrapper = d / "waydroid"
            wrapper.write_text((ROOT / "android/waydroid-wrapper").read_text().replace("@WAYDROID@", str(fake)))
            wrapper.chmod(0o755)
            env = dict(os.environ, XDG_RUNTIME_DIR=str(d), GIBEON_WAYDROID_TEST="1")
            env.pop("WAYLAND_DISPLAY", None)
            res = subprocess.run(["sh", str(wrapper), "app", "launch", "com.beispiel"], env=env,
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(res.returncode, 0, res.stderr)
            lines = log.read_text().splitlines()
            self.assertIn("session start", lines)
            self.assertNotIn("show-full-ui", lines)
            self.assertEqual(lines[-1], "app launch com.beispiel")          # App erst ganz zum Schluss
            self.assertLess(lines.index("session start"), lines.index("app launch com.beispiel"))
            # erst nach dem Ende der Boot-Animation (Startbildschirm fertig)
            self.assertGreaterEqual(int((d / "anim").read_text()), 2)
            import time
            time.sleep(5)                       # zweiter Aufruf holt die App nach vorn
            self.assertEqual(log.read_text().splitlines().count("app launch com.beispiel"), 2)
            # läuft Android schon, geht es sofort los
            log.write_text("")
            subprocess.run(["sh", str(wrapper), "app", "launch", "com.zwei"], env=env, timeout=30)
            self.assertNotIn("session start", log.read_text())
