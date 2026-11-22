"""Bildschirm aufnehmen (Video) – eigener kleiner Prozess, gestartet von Shots.

    python3 -m creative_shots.recorder --out DATEI.mp4 [--no-audio]

Ablauf: Über das xdg-desktop-portal einen Bildschirm (oder ein Fenster) freigeben lassen –
KDE fragt kurz, welcher Monitor –, dann nimmt GStreamer das Bild samt Mauszeiger und den Ton
des Desktops (alles, was gerade zu hören ist) auf. Die Freigabe gilt nur, solange diese
D-Bus-Verbindung besteht, deshalb läuft das hier als eigener Prozess.

Auf stdout kommen JSON-Zeilen: {"recording": true} sobald es läuft, {"error": "…"} bei
Problemen und zum Schluss {"done": "Pfad"}. Schließt Shots stdin (Stopp), wird die Aufnahme
sauber beendet (EOS), damit die Datei vollständig ist.
"""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import uuid

TYPE_MONITOR, TYPE_WINDOW = 1, 2
CURSOR_EMBEDDED = 2

# Grafikkarte zuerst, dann Prozessor (wie in Studio)
VIDEO_ENCODERS = (
    ("nvh264enc", "NV12", "nvh264enc bitrate={k}"),
    ("vah264enc", "NV12", "vah264enc bitrate={k}"),
    ("vaapih264enc", "NV12", "vaapih264enc bitrate={k}"),
    ("x264enc", "I420", "x264enc bitrate={k} speed-preset=veryfast tune=zerolatency key-int-max=60"),
    ("openh264enc", "I420", "openh264enc bitrate={b} rate-control=bitrate"),
)
AUDIO_ENCODERS = ("avenc_aac", "fdkaacenc", "voaacenc")
GPU = {"nvh264enc", "vah264enc", "vaapih264enc"}


def say(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def has(element):
    try:
        return subprocess.run(["gst-inspect-1.0", "--exists", element],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# gst-launch nimmt die Pipeline Wort für Wort (ein Wort mit Leerzeichen, z. B. der Dateiname,
# bleibt dabei ein Wort) – deshalb mit shlex aufteilen statt als eine lange Zeichenkette.
def build_pipeline(fd, node, out, audio, kbps=12000, test=False):
    """gst-launch-Beschreibung und tatsächlicher Dateiname (ohne H.264 → WebM)."""
    venc = next((e for e in VIDEO_ENCODERS if has(e[0])), None)
    src = (f"pipewiresrc fd={int(fd)} path={int(node)} always-copy=true keepalive-time=1000 "
           "do-timestamp=true ! queue ! videoconvert ! videorate")
    if test:                                   # Selbsttest ohne Bildschirmfreigabe
        src = "videotestsrc is-live=true pattern=ball ! video/x-raw,width=1280,height=720 ! videoconvert ! videorate"
    if venc:
        fps = 60 if venc[0] in GPU else 30
        video = (f"{src} ! video/x-raw,format={venc[1]},framerate={fps}/1 ! queue ! "
                 + venc[2].format(k=kbps, b=kbps * 1000) + " ! h264parse ! queue ! mux.")
        aenc = next((a for a in AUDIO_ENCODERS if has(a)), None) if audio else None
        mux = "mp4mux name=mux fragment-duration=1000"
        out = os.path.splitext(out)[0] + ".mp4"
    else:
        video = (f"{src} ! video/x-raw,framerate=30/1 ! queue ! "
                 f"vp8enc deadline=1 cpu-used=8 target-bitrate={kbps * 1000} ! queue ! mux.")
        aenc = "opusenc" if audio and has("opusenc") else None
        mux = "webmmux name=mux"
        out = os.path.splitext(out)[0] + ".webm"
    sound = ""
    if aenc:
        tone = ("audiotestsrc is-live=true wave=ticks" if test else
                "pulsesrc device=@DEFAULT_MONITOR@ do-timestamp=true client-name=Shots")
        sound = (f" {tone} ! queue ! "
                 "audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! "
                 f"{aenc} ! queue ! mux.")
    loc = out.replace("\\", "\\\\").replace('"', '\\"')
    return f'{video}{sound} {mux} ! filesink location="{loc}"', out


def selftest(out, seconds=4):
    """Pipeline mit Testbild und Testton ein paar Sekunden laufen lassen und sauber beenden."""
    import time
    desc, out = build_pipeline(0, 0, out, True, test=True)
    proc = subprocess.Popen(["gst-launch-1.0", "-e", "-q", *shlex.split(desc)], stderr=subprocess.PIPE, text=True)
    time.sleep(seconds)
    proc.send_signal(signal.SIGINT)
    try:
        _o, err = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        _o, err = proc.communicate()
    ok = os.path.exists(out) and os.path.getsize(out) > 10000
    say({"done": out} if ok else {"error": (err or "").strip()[-400:] or "keine Datei"})
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest(argv[argv.index("--selftest") + 1])
    out = argv[argv.index("--out") + 1]
    audio = "--no-audio" not in argv
    if not shutil.which("gst-launch-1.0"):
        say({"error": "GStreamer fehlt – Aufnehmen geht nicht."})
        return 1
    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
    except ImportError as e:
        say({"error": f"Bildschirmfreigabe nicht verfügbar ({e})"})
        return 1

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    loop = GLib.MainLoop()
    try:
        obj = bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
    except dbus.DBusException as e:
        say({"error": f"Bildschirmfreigabe nicht erreichbar ({e.get_dbus_message()})"})
        return 1
    sc = dbus.Interface(obj, "org.freedesktop.portal.ScreenCast")
    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
    sender = bus.get_unique_name()[1:].replace(".", "_")
    state = {"session": None, "proc": None, "stopping": False, "file": out, "code": 0}

    def fail(text):
        state["code"] = 1
        say({"error": text})
        loop.quit()

    def request(method, args, options, on_ok):
        tok = "shots" + uuid.uuid4().hex[:10]
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{tok}"

        def on_response(code, results):
            if code == 0:
                on_ok(results)
            elif code == 1:
                fail("abgebrochen")
            else:
                fail("Die Bildschirmfreigabe wurde nicht erteilt.")

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
        opts = {"types": dbus.UInt32(TYPE_MONITOR | TYPE_WINDOW), "multiple": False}
        if cursors & CURSOR_EMBEDDED:
            opts["cursor_mode"] = dbus.UInt32(CURSOR_EMBEDDED)
        request(sc.SelectSources, (state["session"],), opts, selected)

    def selected(_results):
        request(sc.Start, (state["session"], ""), {}, started)

    def started(results):
        streams = results.get("streams") or []
        if not streams:
            fail("Es wurde kein Bildschirm gewählt.")
            return
        node = int(streams[0][0])
        try:
            fd = sc.OpenPipeWireRemote(state["session"], dbus.Dictionary({}, signature="sv")).take()
        except dbus.DBusException as e:
            fail(f"Bildschirmfreigabe: {e.get_dbus_message()}")
            return
        desc, state["file"] = build_pipeline(fd, node, out, audio)
        try:
            state["proc"] = subprocess.Popen(["gst-launch-1.0", "-e", "-q", *shlex.split(desc)],
                                             pass_fds=(fd,), stdout=subprocess.DEVNULL,
                                             stderr=subprocess.PIPE, text=True)
        except OSError as e:
            os.close(fd)
            fail(f"Aufnahme konnte nicht starten ({e})")
            return
        os.close(fd)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, state["proc"].pid, ended)
        say({"recording": True, "file": state["file"]})

    def ended(_pid, status):
        proc = state["proc"]
        err = ""
        try:
            err = (proc.stderr.read() or "").strip().splitlines()
            err = err[-1] if err else ""
        except (OSError, ValueError):
            err = ""
        ok = os.path.exists(state["file"]) and os.path.getsize(state["file"]) > 0
        if not state["stopping"] and not ok:
            fail("Die Aufnahme ist abgebrochen." + (f" ({err})" if err else ""))
            return
        say({"done": state["file"]} if ok else {"error": "Die Aufnahme ist leer geblieben."})
        loop.quit()

    def stop(*_a):
        if state["stopping"]:
            return False
        state["stopping"] = True
        proc = state["proc"]
        if proc is None or proc.poll() is not None:
            loop.quit()
            return False
        proc.send_signal(signal.SIGINT)         # -e: sauberes Ende, Datei wird fertig geschrieben
        GLib.timeout_add_seconds(15, lambda: (proc.poll() is None and proc.kill()) and False)
        return False

    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_HUP | GLib.IO_IN | GLib.IO_ERR, stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, stop)
    request(sc.CreateSession, (), {"session_handle_token": "shots" + uuid.uuid4().hex[:10]}, created)
    loop.run()
    if state["session"]:
        try:
            dbus.Interface(bus.get_object("org.freedesktop.portal.Desktop", state["session"]),
                           "org.freedesktop.portal.Session").Close()
        except dbus.DBusException:
            pass
    return state["code"]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
