"""Bildschirm oder Fenster freigeben – über das xdg-desktop-portal (so wie es Wayland vorsieht).

Läuft als eigener kleiner Prozess, weil die Freigabe nur so lange gilt, wie die D-Bus-Verbindung,
die sie angefragt hat, besteht:

    python3 -m gibeon_studio.portal --sock FD [--token RESTORE_TOKEN]

Ablauf: CreateSession → SelectSources (Bildschirm oder Fenster, Mauszeiger im Bild, merken)
→ Start (KDE fragt beim ersten Mal, danach dank restore_token nicht mehr) → OpenPipeWireRemote.
Über den Socket FD gehen eine JSON-Zeile ({"node":…, "token":…} oder {"error":…}) und der
PipeWire-Dateideskriptor an Studio. Der Prozess bleibt, bis Studio stdin schließt.
"""

import json
import os
import socket
import sys
import uuid

TYPE_MONITOR, TYPE_WINDOW = 1, 2
CURSOR_EMBEDDED = 2
PERSIST_UNTIL_REVOKED = 2


def main(argv):
    sock_fd = int(argv[argv.index("--sock") + 1])
    token = argv[argv.index("--token") + 1] if "--token" in argv else ""
    out = socket.socket(fileno=sock_fd)

    def send(obj, fds=()):
        data = (json.dumps(obj) + "\n").encode()
        if fds:
            socket.send_fds(out, [data], list(fds))
        else:
            out.sendall(data)

    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
    except ImportError as e:
        send({"error": f"Bildschirmfreigabe nicht verfügbar ({e})"})
        return 1

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    loop = GLib.MainLoop()
    try:
        obj = bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
    except dbus.DBusException as e:
        send({"error": f"Bildschirmfreigabe nicht erreichbar ({e.get_dbus_message()})"})
        return 1
    sc = dbus.Interface(obj, "org.freedesktop.portal.ScreenCast")
    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
    sender = bus.get_unique_name()[1:].replace(".", "_")
    state = {"session": None}

    def fail(text):
        send({"error": text})
        loop.quit()

    def request(method, args, options, on_ok):
        tok = "gibeon" + uuid.uuid4().hex[:10]
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{tok}"

        def on_response(code, results):
            if code == 0:
                on_ok(results)
            elif code == 1:
                fail("abgebrochen")
            else:
                fail("Die Freigabe wurde nicht erteilt.")

        bus.add_signal_receiver(on_response, "Response", "org.freedesktop.portal.Request",
                                "org.freedesktop.portal.Desktop", path)
        options = dict(options)
        options["handle_token"] = tok
        try:
            method(*args, dbus.Dictionary(options, signature="sv"))
        except dbus.DBusException as e:
            fail(f"Bildschirmfreigabe: {e.get_dbus_message()}")

    def created(results):
        state["session"] = results["session_handle"]
        try:
            cursors = int(props.Get("org.freedesktop.portal.ScreenCast", "AvailableCursorModes"))
        except dbus.DBusException:
            cursors = 0
        opts = {"types": dbus.UInt32(TYPE_MONITOR | TYPE_WINDOW), "multiple": False,
                "persist_mode": dbus.UInt32(PERSIST_UNTIL_REVOKED)}
        if cursors & CURSOR_EMBEDDED:
            opts["cursor_mode"] = dbus.UInt32(CURSOR_EMBEDDED)
        if token:
            opts["restore_token"] = token
        request(sc.SelectSources, (state["session"],), opts, selected)

    def selected(_results):
        request(sc.Start, (state["session"], ""), {}, started)

    def started(results):
        streams = results.get("streams") or []
        if not streams:
            fail("Es wurde nichts zum Freigeben gewählt.")
            return
        node, info = streams[0]
        size = info.get("size") or (0, 0)
        try:
            fd = sc.OpenPipeWireRemote(state["session"], dbus.Dictionary({}, signature="sv")).take()
        except dbus.DBusException as e:
            fail(f"Bildschirmfreigabe: {e.get_dbus_message()}")
            return
        send({"node": int(node), "token": str(results.get("restore_token") or token),
              "width": int(size[0]), "height": int(size[1])}, [fd])
        os.close(fd)

    def on_stdin(*_a):
        loop.quit()
        return False

    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_HUP | GLib.IO_IN | GLib.IO_ERR, on_stdin)
    request(sc.CreateSession, (), {"session_handle_token": "gibeon" + uuid.uuid4().hex[:10]}, created)
    loop.run()
    if state["session"]:
        try:
            dbus.Interface(bus.get_object("org.freedesktop.portal.Desktop", state["session"]),
                           "org.freedesktop.portal.Session").Close()
        except dbus.DBusException:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
