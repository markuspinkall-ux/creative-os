"""Creative Mail: E-Mail-Konten über IMAP (Lesen) und SMTP (Senden).

Anmeldung wie in jedem Mailprogramm: Adresse + Passwort (bei Gmail, Yahoo, iCloud und AOL
ein App-Passwort). Die Serverdaten der bekanntesten Anbieter sind eingebaut; für alle
anderen lassen sie sich von Hand eintragen. Das Passwort liegt im Schlüsselbund des PCs.
"""

import base64
import email.utils
import html as _html
import imaplib
import re
import smtplib
import ssl
import subprocess
import threading
import time
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

# ── Anbieter ─────────────────────────────────────────────────────────────────
# smtp_mode: "ssl" (Port 465) oder "starttls" (Port 587)
PROVIDERS = {
    "gmail": {"name": "Gmail", "domains": ["gmail.com", "googlemail.com"],
              "imap": ("imap.gmail.com", 993), "smtp": ("smtp.gmail.com", 465, "ssl"), "saves_sent": True,
              "help": "Gmail braucht ein App-Passwort (nicht dein normales Passwort): myaccount.google.com → "
                      "Sicherheit → Bestätigung in zwei Schritten einschalten → App-Passwörter → neues anlegen.",
              "link": "https://myaccount.google.com/apppasswords"},
    "gmx": {"name": "GMX", "domains": ["gmx.de", "gmx.net", "gmx.at", "gmx.ch", "gmx.com"],
            "imap": ("imap.gmx.net", 993), "smtp": ("mail.gmx.net", 587, "starttls"),
            "help": "Bei GMX einmalig freischalten: E-Mail-Einstellungen → POP3 & IMAP Abruf → "
                    "„E-Mails über externe Programme senden und empfangen“ aktivieren.",
            "link": "https://www.gmx.net/"},
    "webde": {"name": "WEB.DE", "domains": ["web.de"],
              "imap": ("imap.web.de", 993), "smtp": ("smtp.web.de", 587, "starttls"),
              "help": "Bei WEB.DE einmalig freischalten: Einstellungen → POP3/IMAP Abruf → "
                      "„POP3 und IMAP Zugriff erlauben“ aktivieren.",
              "link": "https://web.de/"},
    "tonline": {"name": "T-Online", "domains": ["t-online.de", "magenta.de"],
                "imap": ("secureimap.t-online.de", 993), "smtp": ("securesmtp.t-online.de", 465, "ssl"),
                "help": "T-Online braucht ein eigenes E-Mail-Passwort für Mailprogramme: E-Mail-Center → "
                        "Einstellungen → Passwörter → E-Mail-Passwort anlegen.",
                "link": "https://email.t-online.de/"},
    "yahoo": {"name": "Yahoo", "domains": ["yahoo.com", "yahoo.de", "ymail.com", "rocketmail.com"],
              "imap": ("imap.mail.yahoo.com", 993), "smtp": ("smtp.mail.yahoo.com", 465, "ssl"),
              "help": "Yahoo braucht ein App-Passwort: Kontosicherheit → App-Passwort generieren.",
              "link": "https://login.yahoo.com/account/security"},
    "icloud": {"name": "iCloud", "domains": ["icloud.com", "me.com", "mac.com"],
               "imap": ("imap.mail.me.com", 993), "smtp": ("smtp.mail.me.com", 587, "starttls"),
               "user": "local",
               "help": "iCloud braucht ein app-spezifisches Passwort: account.apple.com → Anmeldung und "
                       "Sicherheit → App-spezifische Passwörter.",
               "link": "https://account.apple.com/"},
    "aol": {"name": "AOL", "domains": ["aol.com", "aol.de", "aim.com"],
            "imap": ("imap.aol.com", 993), "smtp": ("smtp.aol.com", 465, "ssl"),
            "help": "AOL braucht ein App-Passwort: Kontosicherheit → App-Passwort generieren.",
            "link": "https://login.aol.com/account/security"},
    "freenet": {"name": "freenet", "domains": ["freenet.de"],
                "imap": ("mx.freenet.de", 993), "smtp": ("mx.freenet.de", 587, "starttls"),
                "help": "Bei freenet einmalig in den Mail-Einstellungen den Zugriff über externe Programme (IMAP) erlauben.",
                "link": "https://www.freenet.de/"},
    "ionos": {"name": "IONOS / 1&1", "domains": ["online.de", "onlinehome.de", "ionos.de"],
              "imap": ("imap.ionos.de", 993), "smtp": ("smtp.ionos.de", 465, "ssl"),
              "help": "Benutzername ist die volle E-Mail-Adresse, Passwort das des Postfachs.",
              "link": "https://mail.ionos.de/"},
    "posteo": {"name": "Posteo", "domains": ["posteo.de", "posteo.net"],
               "imap": ("posteo.de", 993), "smtp": ("posteo.de", 587, "starttls"),
               "help": "Normales Posteo-Passwort.", "link": "https://posteo.de/"},
    "mailboxorg": {"name": "mailbox.org", "domains": ["mailbox.org"],
                   "imap": ("imap.mailbox.org", 993), "smtp": ("smtp.mailbox.org", 465, "ssl"),
                   "help": "Normales mailbox.org-Passwort.", "link": "https://mailbox.org/"},
    "outlook": {"name": "Outlook / Hotmail", "domains": ["outlook.com", "outlook.de", "hotmail.com", "hotmail.de",
                                                         "live.com", "live.de", "msn.com"],
                "imap": ("outlook.office365.com", 993), "smtp": ("smtp-mail.outlook.com", 587, "starttls"),
                "unsupported": "Microsoft erlaubt seit September 2024 keine Anmeldung mit Passwort mehr "
                               "(auch nicht mit App-Passwort). Outlook-/Hotmail-Konten gehen in Creative Mail "
                               "deshalb im Moment nicht – bitte outlook.live.com im Browser nutzen.",
                "help": "", "link": "https://outlook.live.com/"},
    "custom": {"name": "Anderer Anbieter", "domains": [], "imap": ("", 993), "smtp": ("", 587, "starttls"),
               "help": "Die Serverdaten findest du in der Hilfe deines Anbieters (Stichwort „IMAP“ und „SMTP“).",
               "link": ""},
}
ORDER = ["gmail", "gmx", "webde", "tonline", "outlook", "yahoo", "icloud", "aol", "freenet", "ionos",
         "posteo", "mailboxorg", "custom"]


def provider_for(address):
    domain = (address or "").rsplit("@", 1)[-1].strip().lower()
    for key in ORDER:
        if domain in PROVIDERS[key]["domains"]:
            return key
    return "custom"


def account_settings(address, provider=None, imap_host="", imap_port=0, smtp_host="", smtp_port=0, smtp_mode=""):
    """Vollständige Kontodaten (für QSettings) aus Adresse/Anbieter, optional mit eigenen Servern."""
    key = provider or provider_for(address)
    p = PROVIDERS.get(key, PROVIDERS["custom"])
    user = address.split("@", 1)[0] if p.get("user") == "local" else address
    return {
        "address": address.strip(), "provider": key, "user": user.strip(),
        "imap_host": imap_host or p["imap"][0], "imap_port": int(imap_port or p["imap"][1]),
        "smtp_host": smtp_host or p["smtp"][0], "smtp_port": int(smtp_port or p["smtp"][1]),
        "smtp_mode": smtp_mode or p["smtp"][2], "saves_sent": bool(p.get("saves_sent")),
    }


# ── IMAP-Hilfen (ohne Netz, testbar) ─────────────────────────────────────────

def utf7_decode(name):
    """IMAP-Ordnernamen (modifiziertes UTF-7, RFC 3501) lesbar machen: Entw&APw-rfe → Entwürfe"""
    def repl(m):
        chunk = m.group(1)
        if not chunk:
            return "&"
        data = chunk.replace(",", "/")
        data += "=" * (-len(data) % 4)
        return base64.b64decode(data).decode("utf-16-be", "replace")
    return re.sub(r"&([A-Za-z0-9+,]*)-", repl, name)


def utf7_encode(name):
    out, buf = [], []

    def flush():
        if buf:
            raw = "".join(buf).encode("utf-16-be")
            out.append("&" + base64.b64encode(raw).decode().rstrip("=").replace("/", ",") + "-")
            buf.clear()
    for ch in name:
        if 0x20 <= ord(ch) <= 0x7e:
            flush()
            out.append("&-" if ch == "&" else ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


LIST_RE = re.compile(r'^\((?P<flags>[^)]*)\)\s+(?P<delim>"[^"]*"|NIL)\s+(?P<name>.+)$')


def parse_list(lines):
    """Antwort von LIST → [(flags-set, roher Name)]"""
    result = []
    pending = None
    for line in lines:
        if isinstance(line, tuple):  # Name als Literal
            meta, literal = line
            m = LIST_RE.match(meta.decode(errors="replace").rsplit("{", 1)[0].strip() + " X")
            if m:
                result.append(({f.lower() for f in m.group("flags").split()}, literal.decode(errors="replace")))
            continue
        if not line:
            continue
        text = line.decode(errors="replace") if isinstance(line, bytes) else str(line)
        m = LIST_RE.match(text)
        if not m:
            continue
        name = m.group("name").strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        result.append(({f.lower() for f in m.group("flags").split()}, name))
    return result


ROLE_FLAGS = {"\\sent": "SENT", "\\drafts": "DRAFT", "\\trash": "TRASH", "\\junk": "SPAM",
              "\\archive": "ARCHIVE", "\\all": "ALL", "\\flagged": "STARRED"}
ROLE_NAMES = {
    "SENT": ["gesendet", "gesendete objekte", "gesendete elemente", "sent", "sent items", "sent messages",
             "inbox.sent", "inbox.gesendet"],
    "DRAFT": ["entwürfe", "drafts", "entwurf", "inbox.drafts", "inbox.entwürfe"],
    "TRASH": ["papierkorb", "gelöscht", "gelöschte objekte", "gelöschte elemente", "trash", "deleted",
              "deleted items", "deleted messages", "inbox.trash"],
    "SPAM": ["spam", "junk", "spamverdacht", "junk-e-mail", "junk e-mail", "inbox.spam", "unerwünscht"],
    "ARCHIVE": ["archiv", "archive", "inbox.archive", "inbox.archiv"],
}
SYSTEM = [("INBOX", "Posteingang"), ("STARRED", "Markiert"), ("SENT", "Gesendet"), ("DRAFT", "Entwürfe"),
          ("ARCHIVE", "Archiv"), ("ALL", "Alle E-Mails"), ("SPAM", "Spam"), ("TRASH", "Papierkorb")]


def folder_roles(entries):
    """[(flags, roher Name)] → ({Rolle: roher Name}, [eigene Ordner (roh)])"""
    roles, rest = {}, []
    for flags, raw in entries:
        if "\\noselect" in flags or "\\nonexistent" in flags:
            continue
        if raw.upper() == "INBOX":
            roles["INBOX"] = raw
            continue
        role = next((ROLE_FLAGS[f] for f in flags if f in ROLE_FLAGS), None)
        if role is None:
            plain = utf7_decode(raw).lower()
            plain_tail = plain.rsplit("/", 1)[-1]
            role = next((r for r, names in ROLE_NAMES.items() if plain in names or plain_tail in names), None)
        if role and role not in roles:
            roles[role] = raw
        elif "\\important" in flags:
            continue  # Gmail „Wichtig“ – nicht nötig
        else:
            rest.append(raw)
    roles.setdefault("INBOX", "INBOX")
    return roles, sorted(rest, key=lambda r: utf7_decode(r).lower())


def make_id(folder, uid):
    return f"{int(uid)}|{folder}"


def split_id(message_id):
    uid, folder = message_id.split("|", 1)
    return folder, uid


def header_text(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return value


def snippet_from(raw):
    """Grobe Vorschau aus dem Anfang des Nachrichtentexts (ohne MIME-Kopfzeilen, HTML, Kodierung)."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else (raw or "")
    lines, skip_headers = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            skip_headers = True
            continue
        if skip_headers:
            if not stripped:
                skip_headers = False
            continue
        if re.fullmatch(r"[A-Za-z0-9+/=]{60,}", stripped):
            continue  # Base64-Block
        lines.append(line)
    text = "\n".join(lines)
    if "=\n" in text or re.search(r"=[0-9A-F]{2}", text):
        import quopri
        text = quopri.decodestring(text.encode("utf-8", "replace")).decode("utf-8", "replace")
    text = re.sub(r"(?is)<(style|script|head)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:160]


def parse_fetch(data):
    """imaplib-FETCH-Antwort → [{uid, flags, date, literal}] (je Nachricht ein Literal)."""
    items, current = [], None
    for part in data or []:
        if isinstance(part, tuple):
            current = {"meta": part[0].decode(errors="replace"), "literal": part[1]}
            items.append(current)
        elif isinstance(part, bytes) and current is not None:
            current["meta"] += part.decode(errors="replace")
    result = []
    for item in items:
        meta = item["meta"]
        uid = re.search(r"UID (\d+)", meta)
        if not uid:
            continue
        flags = re.search(r"FLAGS \(([^)]*)\)", meta)
        date = re.search(r'INTERNALDATE "([^"]+)"', meta)
        when = 0
        if date:
            tup = imaplib.Internaldate2tuple(f'INTERNALDATE "{date.group(1)}"'.encode())
            when = time.mktime(tup) if tup else 0
        result.append({"uid": int(uid.group(1)), "flags": (flags.group(1).split() if flags else []),
                       "date": when, "literal": item["literal"]})
    return result


def summary_row(folder, uid, flags, when, header_bytes, snippet="", role=""):
    head = BytesParser(policy=policy.compat32).parsebytes(header_bytes or b"", headersonly=True)
    correspondent = head.get("To", "") if role in ("SENT", "DRAFT") else head.get("From", "")
    if not when and head.get("Date"):
        try:
            when = email.utils.parsedate_to_datetime(head["Date"]).timestamp()
        except (TypeError, ValueError):
            when = 0
    flags = {f.lower() for f in flags}
    return {
        "id": make_id(folder, uid), "threadId": "",
        "from": header_text(correspondent), "subject": header_text(head.get("Subject", "")) or "(Ohne Betreff)",
        "snippet": snippet, "date": when, "unread": "\\seen" not in flags,
        "starred": "\\flagged" in flags, "important": False,
        "labels": (["STARRED"] if "\\flagged" in flags else []) + ([] if "\\seen" in flags else ["UNREAD"]),
    }


def quote(name):
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ── Konto ────────────────────────────────────────────────────────────────────

class MailAccount:
    SYSTEM = SYSTEM

    def __init__(self, settings, password=None):
        self.cfg = dict(settings)
        self.address = self.cfg.get("address", "")
        self._password = password
        self._conn = None
        self._selected = None
        self._lock = threading.RLock()
        self.roles, self.user_folders = {}, []
        self.caps = set()

    # Schlüsselbund
    def _keyring(self, action, value=None):
        args = ["secret-tool", action]
        if action == "store":
            args += ["--label=Creative Mail – " + self.address]
        args += ["application", "creative-mail", "account", self.address, "protocol", "imap"]
        try:
            result = subprocess.run(args, input=value, text=True, capture_output=True, timeout=45)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("Der Schlüsselbund dieses PCs ist nicht erreichbar.") from None
        if result.returncode != 0 and action != "clear":
            raise RuntimeError("Das Passwort ist nicht im Schlüsselbund. Bitte erneut anmelden.")
        return result.stdout.strip()

    def password(self):
        if not self._password:
            self._password = self._keyring("lookup")
        if not self._password:
            raise RuntimeError("Das Passwort fehlt. Bitte erneut anmelden.")
        return self._password

    def forget(self):
        try:
            self._keyring("clear")
        except RuntimeError:
            pass

    # Verbindung
    def _open(self):
        ctx = ssl.create_default_context()
        try:
            conn = imaplib.IMAP4_SSL(self.cfg["imap_host"], int(self.cfg["imap_port"]), ssl_context=ctx, timeout=30)
        except (OSError, imaplib.IMAP4.error) as exc:
            raise RuntimeError(f"Der Mailserver {self.cfg['imap_host']} ist nicht erreichbar ({exc}).") from None
        try:
            conn.login(self.cfg.get("user") or self.address, self.password())
        except imaplib.IMAP4.error:
            raise RuntimeError(self._login_hint()) from None
        self.caps = {c.upper() for c in (conn.capabilities or ())}
        try:
            typ, caps = conn.capability()
            if typ == "OK" and caps and caps[0]:
                self.caps |= set(caps[0].decode().upper().split())
        except imaplib.IMAP4.error:
            pass
        if "ENABLE" in self.caps and "UTF8=ACCEPT" in self.caps:
            pass  # Ordnernamen bleiben in modifiziertem UTF-7 – das versteht jeder Server
        self._conn, self._selected = conn, None
        return conn

    def _login_hint(self):
        p = PROVIDERS.get(self.cfg.get("provider"), PROVIDERS["custom"])
        hint = "Anmeldung abgelehnt – Adresse oder Passwort stimmen nicht."
        if p.get("help"):
            hint += "\n\n" + p["help"]
        return hint

    def _imap(self):
        if self._conn is not None:
            try:
                self._conn.noop()
                return self._conn
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError):
                self._conn = None
        return self._open()

    def _select(self, folder, readonly=False):
        conn = self._imap()
        if self._selected != (folder, readonly):
            typ, data = conn.select(quote(folder), readonly=readonly)
            if typ != "OK":
                raise RuntimeError(f"Ordner „{utf7_decode(folder)}“ lässt sich nicht öffnen.")
            self._selected = (folder, readonly)
        return conn

    def _load_folders(self):
        conn = self._imap()
        typ, data = conn.list()
        if typ != "OK":
            raise RuntimeError("Die Ordnerliste lässt sich nicht laden.")
        self.roles, self.user_folders = folder_roles(parse_list(data))

    def folder_for(self, folder_id):
        if not self.roles:
            self._load_folders()
        if folder_id.startswith("F:"):
            return folder_id[2:]
        return self.roles.get(folder_id or "INBOX")

    def connect(self):
        """Anmeldung prüfen (IMAP und SMTP) und Passwort im Schlüsselbund ablegen."""
        with self._lock:
            self._open()
            self._load_folders()
        self._smtp().quit()
        self._keyring("store", self._password)
        return self.address

    # Ordner
    def labels(self):
        with self._lock:
            self._load_folders()
            conn = self._imap()
            out = []
            for role, name in SYSTEM:
                if role == "STARRED" or role in self.roles:
                    out.append((role, name, self._unseen(conn, role), True))
            for raw in self.user_folders[:60]:
                out.append(("F:" + raw, utf7_decode(raw).replace("INBOX.", "").replace("[Gmail]/", ""),
                            self._unseen(conn, "F:" + raw), False))
            return out

    def _unseen(self, conn, folder_id):
        if folder_id in ("SENT", "DRAFT", "TRASH", "ALL", "ARCHIVE", "STARRED"):
            return 0
        raw = self.folder_for(folder_id)
        if not raw:
            return 0
        try:
            typ, data = conn.status(quote(raw), "(UNSEEN)")
            m = re.search(rb"UNSEEN (\d+)", data[0] or b"") if typ == "OK" else None
            return int(m.group(1)) if m else 0
        except (imaplib.IMAP4.error, IndexError):
            return 0

    # Liste
    def listing(self, folder, query, page, size=30):
        with self._lock:
            starred_virtual = folder == "STARRED" and "STARRED" not in self.roles
            raw = self.roles.get("INBOX", "INBOX") if starred_virtual else self.folder_for(folder or "INBOX")
            if not raw:
                return [], None
            conn = self._select(raw, readonly=True)
            criteria = ["FLAGGED"] if starred_virtual else []
            if query and "X-GM-EXT-1" in self.caps:
                conn.literal = query.encode()
                typ, data = conn.uid("SEARCH", "CHARSET", "UTF-8", "X-GM-RAW", *criteria)
            elif query:
                conn.literal = query.encode()
                typ, data = conn.uid("SEARCH", "CHARSET", "UTF-8", *criteria, "TEXT")
            else:
                typ, data = conn.uid("SEARCH", *(criteria or ["ALL"]))
            if typ != "OK":
                raise RuntimeError("Die Suche ist fehlgeschlagen.")
            uids = sorted((int(x) for x in (data[0] or b"").split()), reverse=True)
            start = int(page or 0)
            chunk = uids[start:start + size]
            if not chunk:
                return [], None
            ids = ",".join(str(u) for u in chunk)
            typ, head = conn.uid("FETCH", ids, "(UID FLAGS INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            heads = {h["uid"]: h for h in parse_fetch(head)} if typ == "OK" else {}
            snippets = {}
            try:
                typ, body = conn.uid("FETCH", ids, "(UID BODY.PEEK[TEXT]<0.1500>)")
                if typ == "OK":
                    snippets = {b["uid"]: snippet_from(b["literal"]) for b in parse_fetch(body)}
            except imaplib.IMAP4.error:
                pass
            role = folder if folder in ("SENT", "DRAFT") else ""
            rows = [summary_row(raw, u, heads[u]["flags"], heads[u]["date"], heads[u]["literal"],
                                snippets.get(u, ""), role) for u in chunk if u in heads]
            following = start + size
            return rows, (following if following < len(uids) else None)

    # Lesen
    def message(self, message_id, unread):
        with self._lock:
            folder, uid = split_id(message_id)
            conn = self._select(folder)
            typ, data = conn.uid("FETCH", uid, "(UID FLAGS BODY.PEEK[])")
            items = parse_fetch(data) if typ == "OK" else []
            if not items:
                raise RuntimeError("Die E-Mail ist nicht mehr da.")
            mail = parse_message(items[0]["literal"])
            flags = {f.lower() for f in items[0]["flags"]}
            if unread:
                conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Seen)")
            mail.update(id=message_id, threadId="",
                        labels=(["STARRED"] if "\\flagged" in flags else []))
            return mail

    # Ändern
    def modify(self, message_id, add=(), remove=()):
        with self._lock:
            folder, uid = split_id(message_id)
            conn = self._select(folder)
            if "UNREAD" in add:
                conn.uid("STORE", uid, "-FLAGS.SILENT", "(\\Seen)")
            if "UNREAD" in remove:
                conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Seen)")
            if "STARRED" in add:
                conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Flagged)")
            if "STARRED" in remove:
                conn.uid("STORE", uid, "-FLAGS.SILENT", "(\\Flagged)")
            if "INBOX" in remove:  # Archivieren
                target = self.roles.get("ARCHIVE") or self.roles.get("ALL") or self._ensure_folder("Archiv")
                self._move(conn, uid, target)
            return message_id

    def _ensure_folder(self, name):
        raw = utf7_encode(name)
        conn = self._imap()
        conn.create(quote(raw))
        conn.subscribe(quote(raw))
        self.roles["ARCHIVE"] = raw
        return raw

    def _move(self, conn, uid, target):
        if "MOVE" in self.caps:
            typ, _ = conn.uid("MOVE", uid, quote(target))
            if typ == "OK":
                return
        typ, _ = conn.uid("COPY", uid, quote(target))
        if typ != "OK":
            raise RuntimeError(f"Verschieben nach „{utf7_decode(target)}“ hat nicht geklappt.")
        conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Deleted)")
        if "UIDPLUS" in self.caps:
            conn.uid("EXPUNGE", uid)
        else:
            conn.expunge()

    def trash(self, message_id):
        with self._lock:
            folder, uid = split_id(message_id)
            conn = self._select(folder)
            target = self.roles.get("TRASH")
            if target and target != folder:
                self._move(conn, uid, target)
            else:  # schon im Papierkorb (oder keiner vorhanden): endgültig löschen
                conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Deleted)")
                conn.expunge()
            return message_id

    def untrash(self, message_id):
        with self._lock:
            folder, uid = split_id(message_id)
            self._move(self._select(folder), uid, self.roles.get("INBOX", "INBOX"))
            return message_id

    # Senden
    def _smtp(self):
        host, port, mode = self.cfg["smtp_host"], int(self.cfg["smtp_port"]), self.cfg.get("smtp_mode", "starttls")
        ctx = ssl.create_default_context()
        try:
            if mode == "ssl":
                smtp = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
            else:
                smtp = smtplib.SMTP(host, port, timeout=30)
                smtp.starttls(context=ctx)
            smtp.login(self.cfg.get("user") or self.address, self.password())
            return smtp
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError("Der Postausgang (SMTP) lehnt die Anmeldung ab.\n\n" + self._login_hint()) from None
        except (OSError, smtplib.SMTPException) as exc:
            raise RuntimeError(f"Der Postausgang {host} ist nicht erreichbar ({exc}).") from None

    def send(self, recipient, subject, body, cc="", bcc="", html=None, attachments=(), reply=None):
        message = build_message(self.address, recipient, subject, body, cc, bcc, html, attachments, reply)
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain=self.address.rsplit("@", 1)[-1] or None)
        smtp = self._smtp()
        try:
            smtp.send_message(message)
        except smtplib.SMTPException as exc:
            raise RuntimeError(f"Senden fehlgeschlagen: {exc}") from None
        finally:
            try:
                smtp.quit()
            except smtplib.SMTPException:
                pass
        if not self.cfg.get("saves_sent"):
            del message["Bcc"]
            with self._lock:
                sent = self.folder_for("SENT")
                if sent:
                    try:
                        self._imap().append(quote(sent), "(\\Seen)", imaplib.Time2Internaldate(time.time()),
                                            message.as_bytes(policy=policy.SMTP))
                    except imaplib.IMAP4.error:
                        pass


# ── Nachrichten zerlegen und bauen ──────────────────────────────────────────

def html_unescape(text):
    import html
    return html.unescape(text or "")


def parse_message(raw):
    """RFC-822-Bytes → dict mit Kopfzeilen, Text, HTML, Anhängen und eingebetteten Bildern."""
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    html_part = mail.get_body(preferencelist=("html",))
    text_part = mail.get_body(preferencelist=("plain",))
    attachments, inline = [], {}
    for part in mail.walk():
        if part.is_multipart() or part in (html_part, text_part):
            continue
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        cid = (part.get("Content-ID") or "").strip("<> ")
        try:
            payload = part.get_payload(decode=True) or b""
        except (ValueError, TypeError):
            payload = b""
        if cid and part.get_content_maintype() == "image" and disposition != "attachment":
            inline[cid] = (part.get_content_type(), payload)
        elif filename or disposition == "attachment":
            attachments.append({"name": filename or "Anhang", "type": part.get_content_type(),
                                "size": len(payload), "data": payload})

    def content(part):
        if not part:
            return ""
        try:
            return part.get_content()
        except (LookupError, ValueError, KeyError):
            return (part.get_payload(decode=True) or b"").decode("utf-8", "replace")

    return {
        "subject": str(mail["Subject"] or "") or "(Ohne Betreff)",
        "from": str(mail["From"] or ""), "to": str(mail["To"] or ""), "cc": str(mail["Cc"] or ""),
        "reply_to": str(mail["Reply-To"] or ""), "date": str(mail["Date"] or ""),
        "message_id": str(mail["Message-ID"] or ""), "references": str(mail["References"] or ""),
        "text": content(text_part), "html": content(html_part),
        "attachments": attachments, "inline": inline,
    }


def build_message(sender, to, subject, text, cc="", bcc="", html=None, attachments=(), reply=None):
    import mimetypes
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc
    message["Subject"] = subject
    if reply:
        if reply.get("message_id"):
            message["In-Reply-To"] = reply["message_id"]
            message["References"] = " ".join(x for x in (reply.get("references", ""), reply["message_id"]) if x)
    message.set_content(text or "")
    if html:
        message.add_alternative(html, subtype="html")
    for item in attachments:
        if isinstance(item, (str, Path)):
            path = Path(item)
            name, data = path.name, path.read_bytes()
        else:
            name, data = item["name"], item["data"]
        kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
        main, sub = kind.split("/", 1)
        message.add_attachment(data, maintype=main, subtype=sub, filename=name)
    return message
