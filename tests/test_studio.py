"""Studio: Mischpult-Beschreibung, Aufnahme mit Testquellen (wenn GStreamer da ist) und Konten-Logik."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "studio"))

try:
    from gibeon_studio import gst
    gst.init()
    HAVE_GST = gst.has("compositor") and gst.has("audiomixer") and gst.has("h264parse") and \
        any(gst.has(f) for f, _ in __import__("gibeon_studio.engine", fromlist=["x"]).VIDEO_ENCODERS)
except (OSError, RuntimeError):
    HAVE_GST = False

from gibeon_studio import engine, konten  # noqa: E402


class Beschreibung(unittest.TestCase):
    def test_kamera_ecken(self):
        x, y, w, h = engine.cam_rect(1920, 1080, "unten-rechts", "mittel")
        self.assertEqual((w, h), (576, 324))
        self.assertEqual(x + w + 37, 1920)
        x, y, _, _ = engine.cam_rect(1920, 1080, "oben-links", "klein")
        self.assertEqual((x, y), (37, 37))

    def test_quellen(self):
        desc, size, pads = engine.build_description(
            {"canvas": "720p60"},
            [{"key": "video:/dev/video2", "type": "video", "device": "/dev/video2"},
             {"key": "image:/a.png", "type": "image", "file": "/tmp/a.png", "w": 400, "h": 200}],
            {"mic": {"type": "mic", "device": "", "volume": 0.5},
             "desktop": {"type": "desktop", "device": "alsa_output.usb.monitor"}},
            {"image:/a.png": (10, 20, 300, 150, 2)})
        self.assertEqual(size, (1280, 720, 60))
        self.assertEqual(pads, {"video:/dev/video2": "sink_1", "image:/a.png": "sink_2"})
        self.assertIn("appsrc name=feed_1", desc)               # Kamera kommt über einen Feeder
        self.assertIn("cairooverlay name=round_1", desc)         # … und kann abgerundet werden
        self.assertIn("sink_1::alpha=0.0", desc)                 # nicht in der Szene → unsichtbar
        self.assertIn("sink_2::xpos=10 sink_2::ypos=20 sink_2::width=300 sink_2::height=150", desc)
        self.assertIn('device="alsa_output.usb.monitor"', desc)  # gewählte Desktop-Tonquelle
        self.assertIn("volume name=vol_mic volume=0.500", desc)
        self.assertIn("level name=lvl_desktop", desc)

    def test_feeder_gruen(self):
        d = engine.feeder_description({"type": "video", "device": "/dev/video42", "green": True}, 1920, 1080, 30)
        self.assertIn('v4l2src device="/dev/video42"', d)
        if engine.gst.has("alpha"):
            self.assertIn("alpha method=green", d)
        self.assertNotIn("alpha method", engine.feeder_description({"type": "video", "device": "/dev/video0"}, 1920, 1080, 30))

    def test_bildschirm(self):
        d = engine.video_source({"type": "screen", "fd": 7, "node": 42})
        self.assertIn("pipewiresrc fd=7 path=42", d)
        self.assertIsNone(engine.video_source({"type": "screen"}))

    def test_anfuehrungszeichen(self):
        self.assertEqual(engine._q('a"b'), '"a\\"b"')


HAVE_MIX = False
try:
    HAVE_MIX = gst.has("compositor") and gst.has("cairooverlay") and gst.has("imagefreeze") and gst.has("pngdec")
except NameError:
    pass


@unittest.skipUnless(HAVE_MIX, "GStreamer fehlt")
class Szenen(unittest.TestCase):
    """Anordnung im laufenden Betrieb, abgerundete Ecken, Grünschlüssel, ausfallende Kamera."""

    def px(self, m, x, y):
        time.sleep(0.35)
        d, w, h = m.frame()
        i = (int(y * h) * w + int(x * w)) * 4
        return tuple(d[i:i + 3])          # B, G, R

    def test_anordnung(self):
        import struct
        import zlib
        png = os.path.join(tempfile.mkdtemp(), "g.png")
        raw = b"".join(b"\x00" + b"\x00\xff\x00" * 64 for _ in range(32))

        def ch(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        with open(png, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", 64, 32, 8, 2, 0, 0, 0))
                    + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))
        m = engine.Mixer()
        lay = {"bg": (0, 0, 1280, 720, 1), "cam": (640, 360, 640, 360, 2)}
        m.build({"canvas": "720p30"},
                [{"key": "bg", "type": "test", "pattern": "white"}, {"key": "cam", "type": "test", "pattern": "red"},
                 {"key": "img", "type": "image", "file": png, "w": 64, "h": 32},
                 {"key": "gs", "type": "test", "pattern": "green", "green": True},
                 {"key": "weg", "type": "video", "device": "/dev/video-gibt-es-nicht"}],
                {}, lay, {"cam": 0.2})
        try:
            time.sleep(1.0)
            self.assertEqual(self.px(m, 0.502, 0.503), (255, 255, 255))       # Ecke der Kamera: rund → weiß
            self.assertEqual(self.px(m, 0.75, 0.75)[2] > 240, True)           # Mitte: rot
            lay["img"] = (0, 0, 640, 320, 3)
            m.apply_layout(lay)
            self.assertEqual(self.px(m, 0.1, 0.1), (0, 255, 0))
            lay["img"] = (0, 400, 320, 160, 3)                                 # verschieben
            m.apply_layout(lay)
            self.assertEqual(self.px(m, 0.1, 0.1), (255, 255, 255))
            lay["gs"] = (0, 0, 640, 360, 4)                                    # Grün wird durchsichtig
            m.apply_layout(lay)
            self.assertEqual(self.px(m, 0.2, 0.2), (255, 255, 255))
            t = time.time()
            while time.time() - t < 1:
                m.poll()
                time.sleep(0.05)
            self.assertTrue(any(e.startswith("feeder:video") for e in m.errors))   # Kamera fehlt …
            self.assertIsNotNone(m.frame())                                         # … Mischpult läuft
            self.assertTrue(m.add_live({"key": "neu", "type": "image", "file": png, "w": 64, "h": 32},
                                       {"neu": (960, 0, 320, 160, 9)}))
            time.sleep(0.6)
            self.assertEqual(self.px(m, 0.85, 0.1), (0, 255, 0))
        finally:
            m.stop()


@unittest.skipUnless(HAVE_MIX, "GStreamer fehlt")
class Mithoeren(unittest.TestCase):
    def test_capture_ton_kommt_beim_mithoeren_an(self):
        class Fake:
            n = 0

            def push(self, sink):
                engine.gst.relay_sample(sink, None)
                Fake.n += 1

            def poll(self):
                return True

            def close(self):
                pass
        m = engine.Mixer()
        m.build({"canvas": "720p30"}, [], {"extra": {"type": "test", "monitorable": True},
                                           "mic": {"type": "test"}}, {}, {})
        try:
            self.assertIn("mon_extra", engine.build_description({}, [], {"extra": {"type": "test", "monitorable": True}})[0])
            self.assertNotIn("mon_mic", engine.build_description({}, [], {"mic": {"type": "test"}})[0])
            m.monitors["extra"] = Fake()
            time.sleep(0.8)
            m.poll()
            self.assertGreater(Fake.n, 5)
            self.assertGreater(m.levels.get("extra", -90), -60)        # Stream-Ton läuft weiter
        finally:
            m.stop()


@unittest.skipUnless(HAVE_GST, "GStreamer fehlt")
class Mischpult(unittest.TestCase):
    def test_multistream_einmal_kodiert(self):
        m = engine.Mixer()
        m.build({"canvas": "720p30"}, [{"key": "a", "type": "test"}], {"mic": {"type": "test"}},
                {"a": (0, 0, 1280, 720, 1)}, {})
        try:
            d = tempfile.mkdtemp()
            time.sleep(0.6)
            enc = m.start_live({"twitch": f"file://{d}/t.flv", "kick": f"file://{d}/k.flv",
                                "custom": "rtmp://127.0.0.1:9/app/key"}, 2000)
            self.assertEqual(sorted(enc.senders), ["custom", "kick", "twitch"])
            ended = {}
            t = time.time()
            while time.time() - t < 3:
                for key, err, _ in m.poll():
                    ended[key] = err
                time.sleep(0.05)
            self.assertIn("custom", ended)                     # ein Ziel bricht ab …
            self.assertEqual(sorted(enc.senders), ["kick", "twitch"])   # … die anderen senden weiter
            health = enc.health()
            self.assertEqual(health["kick"][0], "gut")              # Datei schreibt schnell genug
            m.stop_output("live")
            t = time.time()
            while m.outputs and time.time() - t < 10:
                for key, err, _ in m.poll():
                    ended[key] = err
                time.sleep(0.05)
            self.assertFalse(m.outputs)
            self.assertEqual(ended.get("kick"), "")
            for name in ("t.flv", "k.flv"):
                self.assertGreater(os.path.getsize(os.path.join(d, name)), 20000, name)
        finally:
            m.stop()

    def test_aufnahme_und_abgebrochener_stream(self):
        m = engine.Mixer()
        m.build({"canvas": "720p30"}, [{"key": "a", "type": "test"}, {"key": "b", "type": "test", "pattern": "ball"}],
                {"mic": {"type": "test"}, "desktop": {"type": "test", "freq": 880}},
                {"a": (0, 0, 1280, 720, 1), "b": (800, 400, 400, 225, 2)}, {"b": engine.ROUND})
        try:
            path = os.path.join(tempfile.mkdtemp(), "t.mp4")
            time.sleep(0.6)
            m.start_output("record", path, 2000, "mp4")
            m.start_output("custom", "rtmp://127.0.0.1:9/app/key", 2000)
            ended = {}
            t = time.time()
            while time.time() - t < 2.5:
                for key, err, _ in m.poll():
                    ended[key] = err
                time.sleep(0.05)
            self.assertIn("custom", ended)            # Stream ins Leere bricht ab …
            self.assertIn("record", m.outputs)        # … die Aufnahme läuft weiter
            self.assertGreater(m.levels.get("mic", -90), -60)
            self.assertIsNotNone(m.frame())
            m.stop_output("record")
            t = time.time()
            while m.outputs and time.time() - t < 10:
                m.poll()
                time.sleep(0.05)
            self.assertFalse(m.outputs)
            self.assertGreater(os.path.getsize(path), 20000)
        finally:
            m.stop()


class Konten(unittest.TestCase):
    def setUp(self):
        self.saved = 0

    def save(self):
        self.saved += 1

    def test_geraetecode_wartet_und_speichert(self):
        acc = konten.Twitch({}, self.save, "abc")
        answers = [
            {"device_code": "d", "user_code": "ABCD-EFGH", "verification_uri": "https://www.twitch.tv/activate",
             "interval": 0, "expires_in": 30},
            konten.ApiError(400, {"message": "authorization_pending"}),
            {"access_token": "tok", "refresh_token": "ref", "expires_in": 3600},
            {"login": "markus", "user_id": "42"},
        ]

        def fake(method, url, data=None, headers=None, form=False):
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a

        shown = []
        with mock.patch.object(konten, "http", fake):
            acc.login(lambda code, url: shown.append((code, url)))
        self.assertEqual(shown, [("ABCD-EFGH", "https://www.twitch.tv/activate")])
        self.assertEqual(acc.store["login"], "markus")
        self.assertTrue(acc.connected)
        self.assertEqual(acc.chat_url(), "https://www.twitch.tv/popout/markus/chat?darkpopout")

    def test_abgelaufen_wird_aufgefrischt(self):
        acc = konten.YouTube({"access_token": "alt", "refresh_token": "r", "expires_at": 0}, self.save, "id", "geheim")
        with mock.patch.object(konten, "http", return_value={"access_token": "neu", "expires_in": 3600}) as h:
            self.assertEqual(acc.token(), "neu")
            self.assertEqual(h.call_args.args[2]["grant_type"], "refresh_token")

    def test_ungueltige_anmeldung_meldet_ab(self):
        acc = konten.YouTube({"access_token": "alt", "refresh_token": "r", "expires_at": 0}, self.save, "id", "geheim")
        with mock.patch.object(konten, "http", side_effect=konten.ApiError(400, {"error": "invalid_grant"})):
            with self.assertRaises(konten.ApiError):
                acc.token()
        self.assertFalse(acc.connected)

    def test_youtube_stream_ziel(self):
        acc = konten.YouTube({"access_token": "t", "expires_at": time.time() + 999}, self.save, "id", "s")
        answers = [{"items": [{"id": "vid", "snippet": {"title": "T", "liveChatId": "c"},
                               "contentDetails": {"boundStreamId": "s1"}}]},
                   {"items": [{"cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
                                                          "streamName": "abcd-1234"}}}]}]
        with mock.patch.object(konten, "http", side_effect=lambda *a, **k: answers.pop(0)):
            self.assertEqual(acc.stream_target(), "rtmp://a.rtmp.youtube.com/live2/abcd-1234")

    def test_dienste_ohne_kennung(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": d}):
            self.assertEqual(konten.services()["twitch_client_id"], "")


class Abbild(unittest.TestCase):
    def test_eingebaut(self):
        cf = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
        for part in ("COPY studio/gibeon_studio", "/usr/bin/gibeon-studio --selftest", "pipewire-gstreamer"):
            self.assertIn(part, cf)
        self.assertIn('"gibeon-studio.desktop"', (ROOT / "shell/creative_shell/apps.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class Elgato(unittest.TestCase):
    """Capture-Karten: bestes Format fest einstellen, Karten ohne Treiber erkennen."""

    def test_format_auswahl(self):
        from gibeon_studio import geraete
        hd60x = [{"format": "YUYV", "width": 1920, "height": 1080, "fps": 60.0},
                 {"format": "NV12", "width": 1920, "height": 1080, "fps": 60.0},
                 {"format": "NV12", "width": 3840, "height": 2160, "fps": 30.0},
                 {"format": "P010", "width": 3840, "height": 2160, "fps": 60.0}]
        self.assertEqual(geraete.pick_capture_mode(hd60x), {"format": "NV12", "width": 1920, "height": 1080, "fps": 60.0})
        camlink = [{"format": "NV12", "width": 3840, "height": 2160, "fps": 29.97},
                   {"format": "YUYV", "width": 1920, "height": 1080, "fps": 59.94}]
        self.assertEqual(geraete.pick_capture_mode(camlink)["fps"], 59.94)
        self.assertIsNone(geraete.pick_capture_mode([]))

    def test_caps(self):
        self.assertEqual(engine.mode_caps({"format": "NV12", "width": 1920, "height": 1080, "fps": 59.94}),
                         " ! video/x-raw,format=NV12,width=1920,height=1080,framerate=60000/1001")
        self.assertIn("image/jpeg", engine.mode_caps({"format": "MJPG", "width": 1920, "height": 1080, "fps": 60}))
        self.assertIn("format=YUY2", engine.video_source({"type": "video", "device": "/dev/video3",
                                                          "mode": {"format": "YUYV", "width": 1920, "height": 1080, "fps": 60}}))

    def test_karte_ohne_treiber(self):
        from gibeon_studio import geraete
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            usb = root / "bus/usb/devices/2-1"
            usb.mkdir(parents=True)
            (usb / "idVendor").write_text("0fd9\n")
            (usb / "product").write_text("Game Capture HD60 S\n")
            deck = root / "bus/usb/devices/2-2"                 # Stream Deck: kein Capture-Gerät
            deck.mkdir(parents=True)
            (deck / "idVendor").write_text("0fd9\n")
            (deck / "product").write_text("Stream Deck MK.2\n")
            pci = root / "bus/pci/devices/0000:05:00.0"
            pci.mkdir(parents=True)
            (pci / "vendor").write_text("0x1cfa\n")
            (pci / "device").write_text("0x000e\n")
            (root / "class/video4linux").mkdir(parents=True)
            with mock.patch.object(geraete, "SYS", root):
                msgs = geraete.unsupported()
        self.assertEqual(len(msgs), 2)
        self.assertTrue(msgs[0].startswith("Game Capture HD60 S:"))
        self.assertIn("4K60 Pro MK.2", msgs[1])


@unittest.skipUnless(HAVE_MIX, "GStreamer fehlt")
class FesteEinstellung(unittest.TestCase):
    def test_rueckfall_ohne_format(self):
        f = engine.Feeder("k", {"type": "video", "device": "/dev/video-nicht-da",
                                "mode": {"format": "NV12", "width": 1920, "height": 1080, "fps": 60}}, None, (1280, 720, 30))
        try:
            for _ in range(20):
                f.poll()
                if f.no_mode:
                    break
                time.sleep(0.05)
            self.assertTrue(f.no_mode)            # klappt nicht → nochmal ohne feste Einstellung
        finally:
            f.stop()


class StreamDeck(unittest.TestCase):
    """Deck-Tasten für Studio: Befehle, Beispielseite, Umstellung der alten OBS-Seite."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "deck"))

    def test_befehle(self):
        from creative_deck import studio
        self.assertEqual(studio.command("szene", "Pause"), "szene Pause")
        self.assertEqual(studio.command("mikrofon"), "stumm mic")
        self.assertEqual(studio.command("live"), "live")
        with self.assertRaises(studio.StudioError):
            studio.command("szene", "")

    def test_studio_antwortet(self):
        import socket
        import threading
        from creative_deck import studio
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": d}):
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(studio.socket_path())
            srv.listen(1)
            got = []

            def serve():
                c, _ = srv.accept()
                got.append(c.recv(100).decode())
                c.sendall(b"fehler Die Szene gibt es nicht\n")
                c.close()
            t = threading.Thread(target=serve)
            t.start()
            with self.assertRaises(studio.StudioError) as cm:
                studio.run("szene", "Gibtsnicht", start=False)
            t.join(2)
            srv.close()
        self.assertEqual(got, ["szene Gibtsnicht\n"])
        self.assertIn("gibt es nicht", str(cm.exception))

    def test_alte_obs_seite_wird_studio(self):
        from creative_deck import config
        cfg = config.default_config()
        cfg["seiten"][1] = {"name": "OBS", "tasten": config.old_obs_page()}
        cfg["seiten"][0]["tasten"]["4"]["text"] = "OBS"
        cfg = config._to_studio(cfg)
        self.assertEqual(cfg["seiten"][1]["name"], "Studio")
        self.assertEqual(cfg["seiten"][1]["tasten"]["1"]["aktion"], {"typ": "studio", "was": "live"})
        self.assertEqual(cfg["seiten"][0]["tasten"]["4"]["text"], "Studio")
        # selbst angepasste OBS-Seite bleibt, wie sie ist
        cfg["seiten"][1] = {"name": "OBS", "tasten": {"0": config._key("X", "", {"typ": "obs", "was": "stream"})}}
        self.assertEqual(config._to_studio(cfg)["seiten"][1]["name"], "OBS")


class Qualitaet(unittest.TestCase):
    def test_leinwand_und_stream(self):
        self.assertEqual(engine.canvas_size("1440p50"), (2560, 1440, 50))
        self.assertEqual(engine.canvas_size("2160p30"), (3840, 2160, 30))
        self.assertEqual(engine.canvas_size("quatsch"), (1920, 1080, 30))
        self.assertEqual(engine.size_for_height(936), (1664, 936))

    def test_capture_karte_passend_zur_leinwand(self):
        from gibeon_studio import geraete
        k = [{"format": "NV12", "width": 3840, "height": 2160, "fps": 30.0},
             {"format": "NV12", "width": 1920, "height": 1080, "fps": 60.0},
             {"format": "NV12", "width": 2560, "height": 1440, "fps": 60.0}]
        self.assertEqual(geraete.pick_capture_mode(k, 30, 2160)["height"], 2160)
        self.assertEqual(geraete.pick_capture_mode(k, 60, 1080)["height"], 1080)
        self.assertEqual(geraete.pick_capture_mode(k, 60, 1440)["height"], 1440)
        self.assertEqual(geraete.pick_capture_mode(k[:2], 60, 1440)["height"], 1080)   # nie unnötig größer

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "ffmpeg fehlt")
    def test_hochskalieren_schnell(self):
        import subprocess
        d = tempfile.mkdtemp()
        src, dst = os.path.join(d, "a.mp4"), os.path.join(d, "a_4K.mp4")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=640x360:rate=25", "-f", "lavfi", "-i", "sine", "-t", "1",
                        "-c:v", "libx264", "-c:a", "aac", src], check=True)
        out = subprocess.run([sys.executable, "-m", "gibeon_studio.hochskalieren", "--art", "schnell", src, dst],
                             capture_output=True, text=True, cwd=ROOT / "studio", timeout=600)
        self.assertIn("fertig", out.stdout, out.stdout + out.stderr)
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout
        self.assertEqual(info.strip(), "3840,2160")
        self.assertFalse(any(n.startswith(".teil-") for n in os.listdir(d)))


@unittest.skipUnless(HAVE_MIX, "GStreamer fehlt")
class Browserquelle(unittest.TestCase):
    def test_durchsichtig_im_bild(self):
        m = engine.Mixer()
        m.build({"canvas": "720p30"}, [{"key": "bg", "type": "test", "pattern": "white"},
                                       {"key": "w", "type": "browser", "w": 200, "h": 100}], {},
                {"bg": (0, 0, 1280, 720, 1), "w": (0, 0, 640, 320, 2)}, {})
        try:
            half = b"".join(b"\x00\x00\xff\xff" * 100 + b"\x00\x00\x00\x00" * 100 for _ in range(100))
            for _ in range(8):
                self.assertTrue(m.push_web("w", half, 200, 100))
                time.sleep(0.05)
            self.assertFalse(m.push_web("w", half, 100, 100))            # falsche Größe wird abgelehnt
            time.sleep(0.4)
            d, w, h = m.frame()

            def px(x, y):
                i = (int(y * h) * w + int(x * w)) * 4
                return tuple(d[i:i + 3])
            self.assertEqual(px(0.1, 0.2), (0, 0, 255))      # roter Teil der Seite
            self.assertEqual(px(0.4, 0.2), (255, 255, 255))  # durchsichtiger Teil zeigt das Bild darunter
        finally:
            m.stop()


class Umfragen(unittest.TestCase):
    def test_abstimmen(self):
        from gibeon_studio import umfrage
        p = umfrage.Poll("Welches Spiel?", ["Mario Kart", "Zelda", "", "Tetris"], 60, 20)
        self.assertEqual(p.options, ["Mario Kart", "Zelda", "Tetris"])
        self.assertTrue(p.vote("anna", "1"))
        self.assertTrue(p.vote("ben", "!vote 2"))
        self.assertTrue(p.vote("cem", "tetris"))
        self.assertTrue(p.vote("anna", "2"))              # umentschieden: letzte Stimme zählt
        self.assertFalse(p.vote("dora", "7"))             # gibt es nicht
        self.assertFalse(p.vote("emil", "ich finde 2 gut"))
        st = p.state()
        self.assertEqual([o["votes"] for o in st["options"]], [0, 2, 1])
        self.assertEqual(st["total"], 3)
        self.assertEqual([o["pct"] for o in st["options"]], [0, 67, 33])
        self.assertTrue(st["options"][1]["lead"])
        self.assertEqual(st["phase"], "laeuft")
        p.ended = time.monotonic()
        self.assertEqual(p.state()["phase"], "ergebnis")
        self.assertFalse(p.vote("fritz", "1"))           # nach dem Ende zählt nichts mehr
        self.assertIn("Zelda: 67 %", p.result_text())
        p.ended -= 30
        self.assertEqual(p.state()["phase"], "vorbei")

    def test_einblendung_vorhanden(self):
        html = (ROOT / "studio/gibeon_studio/umfrage.html").read_text(encoding="utf-8")
        for part in ("window.gibeonUmfrage", 'id="eigen"', ".umfrage", ".antwort", ".fuellung", "background: transparent"):
            self.assertIn(part, html)


def test_spiel_aufnahme_eigenes_mischpult():
    """„Nur das Spiel“: die Aufnahme bekommt ein zweites Mischpult ohne Overlays."""
    import sys
    sys.path.insert(0, str(ROOT / "studio"))
    from gibeon_studio import engine
    srcs = [{"key": "screen", "type": "test"}, {"key": "image:/x.png", "type": "image", "file": "/x.png", "w": 100, "h": 100}]
    lay = {"screen": (0, 0, 1920, 1080, 1), "image:/x.png": (10, 10, 100, 100, 2)}
    desc, _size, pads = engine.build_description({"canvas": "1080p30"}, srcs, {}, lay)
    assert "rmix" not in desc
    desc, _size, pads = engine.build_description({"canvas": "1080p30"}, srcs, {}, lay, {"screen": lay["screen"]})
    assert "compositor name=rmix" in desc and "appsink name=rvout" in desc
    n = pads["image:/x.png"][5:]
    assert f"rmix.sink_{n}" in desc and f"sink_{n}::alpha=0.0" in desc.split("compositor name=rmix")[1]
