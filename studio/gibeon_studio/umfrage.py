"""Umfragen in Studio: Frage + 2–5 Antworten, Zeitlimit, Abstimmen im Twitch-Chat, Ergebnis im Bild.

Abgestimmt wird im Twitch-Chat mit der Nummer der Antwort („1“, „2“ …, auch „!vote 2“ oder der
Antworttext). Jede Person zählt einmal – wer sich umentscheidet, dessen letzte Stimme gilt.
Zum Mitlesen reicht der Kanalname (anonym, ohne Anmeldung). Ist man angemeldet und Affiliate/Partner,
kann Studio zusätzlich eine echte Twitch-Umfrage starten; deren Stimmen werden dann mitgezählt.
"""

import random
import re
import socket
import ssl
import threading
import time

DEFAULT_CSS = """/* Eigene Gestaltung: diese Regeln überschreiben das Standard-Aussehen.
   Bausteine: .umfrage  .frage  .antwort  .nummer  .text  .balken  .fuellung  .prozent
              .zeit  .zeitbalken  .hinweis  .ergebnis (am Ende)  .gewinner (vorne liegende Antwort) */
.umfrage { }
"""


class ChatReader:
    """Liest einen Twitch-Chat anonym mit (IRC über TLS, ohne Anmeldung). Läuft im Hintergrund,
    verbindet sich bei Abbrüchen neu."""

    HOST = ("irc.chat.twitch.tv", 6697)

    def __init__(self, channel, on_message):
        self.channel = channel.lower().lstrip("#@").strip()
        self.on_message = on_message
        self.stop_flag = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()

    def _run(self):
        while not self.stop_flag.is_set():
            try:
                raw = socket.create_connection(self.HOST, timeout=10)
                with ssl.create_default_context().wrap_socket(raw, server_hostname=self.HOST[0]) as s:
                    s.settimeout(1.0)
                    nick = f"justinfan{random.randint(10000, 99999)}"
                    s.sendall(f"NICK {nick}\r\nJOIN #{self.channel}\r\n".encode())
                    buf = b""
                    while not self.stop_flag.is_set():
                        try:
                            chunk = s.recv(4096)
                        except socket.timeout:
                            continue
                        if not chunk:
                            break
                        buf += chunk
                        while b"\r\n" in buf:
                            line, buf = buf.split(b"\r\n", 1)
                            text = line.decode("utf-8", "replace")
                            if text.startswith("PING"):
                                s.sendall(b"PONG :tmi.twitch.tv\r\n")
                                continue
                            m = re.match(r"^:([^!]+)![^ ]+ PRIVMSG #[^ ]+ :(.*)$", text)
                            if m:
                                self.on_message(m.group(1).lower(), m.group(2))
            except OSError:
                pass
            self.stop_flag.wait(5)            # kurz warten, dann neu verbinden


class Poll:
    def __init__(self, question, options, duration, show_result):
        self.question = question.strip()[:140]
        self.options = [o.strip()[:60] for o in options if o.strip()][:5]
        self.duration = max(10, min(1800, int(duration)))
        self.show_result = max(0, min(600, int(show_result)))
        self.started = time.monotonic()
        self.ended = None
        self.votes = {}                       # Person → Antwort (0-basiert)
        self.extra = [0] * len(self.options)  # Stimmen aus der echten Twitch-Umfrage
        self.twitch_poll = ""                 # Kennung der Twitch-Umfrage, falls gestartet
        self.lock = threading.Lock()

    def vote(self, user, text):
        """Chatnachricht als Stimme werten. True, wenn sie gezählt hat."""
        if self.ended:
            return False
        t = text.strip().lower()
        m = re.match(r"^(?:!vote\s*|!umfrage\s*|#)?(\d)\s*$", t)
        idx = int(m.group(1)) - 1 if m else next((i for i, o in enumerate(self.options) if o.lower() == t), -1)
        if not 0 <= idx < len(self.options):
            return False
        with self.lock:
            self.votes[user] = idx
        return True

    def counts(self):
        with self.lock:
            c = list(self.extra)
            for idx in self.votes.values():
                c[idx] += 1
        return c

    def remaining(self):
        return max(0, int(round(self.duration - (time.monotonic() - self.started))))

    def phase(self):
        if not self.ended:
            return "laeuft"
        if time.monotonic() - self.ended < self.show_result:
            return "ergebnis"
        return "vorbei"

    def state(self, hint=""):
        c = self.counts()
        total = sum(c)
        best = max(c) if total else -1
        return {
            "phase": self.phase(), "question": self.question, "total": total,
            "remaining": self.remaining(), "duration": self.duration, "hint": hint,
            "options": [{"text": o, "votes": c[i], "pct": round(100 * c[i] / total) if total else 0,
                         "lead": total > 0 and c[i] == best} for i, o in enumerate(self.options)],
        }

    def result_text(self):
        c = self.counts()
        total = sum(c)
        if not total:
            return f"Umfrage „{self.question}“ beendet – leider keine Stimmen."
        parts = [f"{o}: {round(100 * c[i] / total)} %" for i, o in enumerate(self.options)]
        return f"Ergebnis „{self.question}“ ({total} Stimmen): " + " · ".join(parts)
