"""Hintergrunddienst: findet Stream Decks (auch beim Ein- und Ausstecken), zeigt die Tasten
und führt beim Drücken die Aktionen aus. Startet mit der Sitzung (creative-shell-supervisor).

Änderungen aus dem Editor (config.json) werden innerhalb einer Sekunde übernommen.
Status für den Editor: $XDG_RUNTIME_DIR/creative-deck/status.json
"""

import io
import queue
import threading
import time

from PySide6.QtCore import QTimer

from . import config
from .actions import DECK_ACTIONS, Runner
from .render import render_key, to_png

try:
    from PIL import Image
    from StreamDeck.DeviceManager import DeviceManager
    from StreamDeck.ImageHelpers import PILHelper
    LIB_ERROR = ""
except Exception as exc:  # noqa: BLE001 – Bibliothek oder hidapi fehlt
    DeviceManager = PILHelper = Image = None
    LIB_ERROR = f"Stream-Deck-Bibliothek fehlt ({exc})"

POLL_MS = 2000


def model_name(deck):
    name = deck.deck_type() or "Stream Deck"
    return {"Stream Deck Plus": "Stream Deck +"}.get(name, name)


class DeckState:
    def __init__(self, deck):
        self.deck = deck
        self.page = 0
        self.history = []
        self.serial = ""
        self.asleep = False
        self.last_input = time.monotonic()


class Daemon:
    def __init__(self, manager=None):
        self.cfg = config.load()
        self.mtime = config.mtime()
        self.runner = Runner()
        self.events = queue.Queue()
        self.decks = {}          # id → DeckState
        self.error = LIB_ERROR
        self.message = ""
        self.manager = manager
        if self.manager is None and DeviceManager is not None:
            try:
                self.manager = DeviceManager()
            except Exception as exc:  # noqa: BLE001 – hidapi-Bibliothek nicht ladbar
                self.error = f"USB-Zugriff nicht möglich ({exc})"

    # ---- Geräte -----------------------------------------------------------------
    def poll(self):
        if self.manager is None:
            self.write_status()
            return
        try:
            found = self.manager.enumerate()
        except Exception as exc:  # noqa: BLE001
            self.error = f"Suche nach Stream Decks fehlgeschlagen ({exc})"
            found = []
        ids = set()
        for deck in found:
            did = deck.id()
            ids.add(did)
            if did in self.decks:
                continue
            self.open(deck)
        for did in list(self.decks):
            st = self.decks[did]
            alive = did in ids
            try:
                alive = alive and st.deck.connected()
            except Exception:  # noqa: BLE001
                alive = False
            if not alive:
                self.drop(did)
        self.check_sleep()
        self.write_status()

    def open(self, deck):
        try:
            deck.open()
            deck.reset()
            st = DeckState(deck)
            try:
                st.serial = deck.get_serial_number()
            except Exception:  # noqa: BLE001
                st.serial = deck.id()
            did = deck.id()
            deck.set_key_callback(lambda d, key, state, did=did: self.events.put((did, key, state)))
            self.decks[did] = st
            self.apply_brightness(st)
            self.draw_page(st)
            cols, rows = self.layout(deck)
            self.cfg["letztes_geraet"] = {"modell": model_name(deck), "spalten": cols, "zeilen": rows}
            self.error = ""
        except Exception as exc:  # noqa: BLE001 – meist fehlende Rechte (udev)
            self.error = f"{model_name(deck)} gefunden, aber kein Zugriff ({exc}). Einmal aus- und einstecken."
            try:
                deck.close()
            except Exception:  # noqa: BLE001
                pass

    def drop(self, did):
        st = self.decks.pop(did, None)
        if st:
            try:
                st.deck.close()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def layout(deck):
        rows, cols = deck.key_layout()
        return cols, rows

    # ---- Anzeige ------------------------------------------------------------------
    def pages(self):
        return self.cfg.get("seiten") or [{"name": "Start", "tasten": {}}]

    def apply_brightness(self, st, value=None):
        try:
            st.deck.set_brightness(self.cfg["helligkeit"] if value is None else value)
        except Exception:  # noqa: BLE001
            pass

    def key_image(self, deck, key, pressed=False):
        size = deck.key_image_format()["size"][0]
        a = (key or {}).get("aktion") or {}
        img = render_key(key, size, pressed=pressed, folder=a.get("typ") == "seite")
        pil = Image.open(io.BytesIO(to_png(img))).convert("RGB")
        return PILHelper.to_native_key_format(deck, pil)

    def draw_key(self, st, index, pressed=False):
        deck = st.deck
        if not deck.is_visual():
            return
        page = self.pages()[min(st.page, len(self.pages()) - 1)]
        key = page["tasten"].get(str(index))
        try:
            with deck:
                deck.set_key_image(index, self.key_image(deck, key, pressed))
        except Exception:  # noqa: BLE001 – Gerät gerade abgezogen
            pass

    def draw_page(self, st):
        if st.page >= len(self.pages()):
            st.page = 0
        for i in range(st.deck.key_count()):
            self.draw_key(st, i)

    # ---- Eingaben ---------------------------------------------------------------
    def tick(self):
        if config.mtime() != self.mtime:
            self.mtime = config.mtime()
            last = self.cfg.get("letztes_geraet")
            self.cfg = config.load()
            if self.decks and last:
                self.cfg["letztes_geraet"] = last
            for st in self.decks.values():
                self.apply_brightness(st)
                self.draw_page(st)
        while True:
            try:
                did, index, pressed = self.events.get_nowait()
            except queue.Empty:
                break
            st = self.decks.get(did)
            if st:
                self.on_key(st, index, pressed)

    def on_key(self, st, index, pressed):
        st.last_input = time.monotonic()
        if st.asleep:
            if not pressed:             # Aufwecken verbraucht den Tastendruck
                st.asleep = False
                self.apply_brightness(st)
            return
        page = self.pages()[st.page]
        key = page["tasten"].get(str(index)) or {}
        action = key.get("aktion") or {}
        if pressed:
            self.draw_key(st, index, pressed=True)
            return
        typ = action.get("typ")
        if typ in DECK_ACTIONS:
            self.deck_action(st, action)
            return
        self.draw_key(st, index)
        if typ and typ != "keine":
            threading.Thread(target=self._run, args=(action,), daemon=True).start()

    def _run(self, action):
        err = self.runner.run(action, self.cfg)
        self.message = err
        if err:
            print("Creative Deck:", err, flush=True)

    def deck_action(self, st, action):
        typ = action.get("typ")
        if typ == "seite":
            target = action.get("seite", 0)
            if isinstance(target, int) and 0 <= target < len(self.pages()) and target != st.page:
                st.history.append(st.page)
                st.page = target
        elif typ == "zurueck":
            st.page = st.history.pop() if st.history else 0
        elif typ == "helligkeit":
            step = 15 if action.get("was") == "hoch" else -15
            self.cfg["helligkeit"] = max(5, min(100, self.cfg["helligkeit"] + step))
            self.apply_brightness(st)
        self.draw_page(st)
        self.write_status()

    def check_sleep(self):
        minutes = self.cfg.get("aus_nach_min") or 0
        if not minutes:
            return
        for st in self.decks.values():
            if not st.asleep and time.monotonic() - st.last_input > minutes * 60:
                st.asleep = True
                self.apply_brightness(st, 0)

    # ---- Status für den Editor ------------------------------------------------------
    def write_status(self):
        devices = []
        for st in self.decks.values():
            cols, rows = self.layout(st.deck)
            devices.append({"modell": model_name(st.deck), "seriennummer": st.serial,
                            "spalten": cols, "zeilen": rows, "seite": st.page,
                            "bildschirm": bool(st.deck.is_visual())})
        config.write_status({"zeit": int(time.time()), "geraete": devices, "fehler": self.error,
                             "meldung": self.message})

    def close(self):
        for did in list(self.decks):
            st = self.decks[did]
            try:
                with st.deck:
                    st.deck.reset()
            except Exception:  # noqa: BLE001
                pass
            self.drop(did)
        self.runner.keyboard.close()
        config.write_status({"zeit": int(time.time()), "geraete": [], "fehler": "", "beendet": True})


def run(app):
    daemon = Daemon()
    poll = QTimer()
    poll.timeout.connect(daemon.poll)
    poll.start(POLL_MS)
    tick = QTimer()
    tick.timeout.connect(daemon.tick)
    tick.start(30)
    QTimer.singleShot(0, daemon.poll)
    app.aboutToQuit.connect(daemon.close)
    return app.exec()
