"""Twitch und YouTube: Anmelden, Stream-Schlüssel holen, Titel und Kategorie ändern, Chat senden.

Anmeldung über den „Gerätecode“-Weg (OAuth Device Flow): Studio zeigt einen kurzen Code, man
bestätigt ihn im Browser (oder am Handy) bei Twitch bzw. Google. Das Passwort sieht Studio nie.
So klappt die Anmeldung auch dort, wo Google eingebettete Browser abweist.

Die App-Kennungen (Client-IDs) stehen in dienste.json (bei Twitch und Google einmal registriert):
  /usr/lib/gibeon-studio/dienste.json  oder  ~/.config/gibeon-studio/dienste.json
Die Anmeldedaten liegen nur für den Benutzer lesbar in ~/.local/share/gibeon-studio/konten.json.
Nur Standardbibliothek (urllib, ssl).
"""

import json
import os
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TWITCH_SCOPES = "channel:manage:broadcast channel:read:stream_key chat:read chat:edit"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
TIMEOUT = 15


def _xdg(var, fallback):
    return Path(os.environ.get(var) or Path.home() / fallback)


def services():
    cfg = {"twitch_client_id": "", "youtube_client_id": "", "youtube_client_secret": ""}
    for p in (HERE.parent / "dienste.json", HERE / "dienste.json",
              _xdg("XDG_CONFIG_HOME", ".config") / "gibeon-studio" / "dienste.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cfg.update({k: str(v) for k, v in data.items() if k in cfg and v})
        except (OSError, ValueError, AttributeError):
            pass
    return cfg


def store_path():
    return _xdg("XDG_DATA_HOME", ".local/share") / "gibeon-studio" / "konten.json"


def load_store():
    try:
        data = json.loads(store_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_store(data):
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, p)


class ApiError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status = status


def http(method, url, data=None, headers=None, form=False):
    body = None
    headers = dict(headers or {})
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            info = json.loads(raw)
        except ValueError:
            info = {"message": raw.decode("utf-8", "replace")[:200]}
        raise ApiError(e.code, info) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        raise ApiError(0, {"message": f"keine Verbindung ({getattr(e, 'reason', e)})"}) from None


def _msg(err):
    info = err.args[0] if err.args else {}
    if isinstance(info, dict):
        e = info.get("error")
        if isinstance(e, dict):
            return e.get("message") or str(e)
        return info.get("message") or info.get("error_description") or e or str(info)
    return str(info)


# ---------------------------------------------------------------------------------------------
class Account:
    """Gemeinsames: Anmeldung per Gerätecode, Zugangsschlüssel auffrischen."""
    name = ""

    def __init__(self, store, save):
        self.store = store            # dict aus konten.json (Teil für diesen Dienst)
        self.save = save
        self.cancel = threading.Event()

    @property
    def connected(self):
        return bool(self.store.get("refresh_token") or self.store.get("access_token"))

    def logout(self):
        self.store.clear()
        self.save()

    def _token_ok(self):
        return self.store.get("access_token") and time.time() < self.store.get("expires_at", 0) - 60

    def _set_tokens(self, tok):
        self.store["access_token"] = tok["access_token"]
        if tok.get("refresh_token"):
            self.store["refresh_token"] = tok["refresh_token"]
        self.store["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
        self.save()

    def login(self, show_code):
        """Blockiert, bis bestätigt (oder abgebrochen). show_code(code, adresse)."""
        self.cancel.clear()
        dev = self._device_start()
        show_code(dev["user_code"], dev.get("verification_uri") or dev.get("verification_url"))
        interval = int(dev.get("interval", 5))
        deadline = time.time() + int(dev.get("expires_in", 600))
        while time.time() < deadline:
            if self.cancel.wait(interval):
                raise ApiError(0, {"message": "abgebrochen"})
            try:
                tok = self._device_poll(dev["device_code"])
            except ApiError as e:
                m = _msg(e)
                if "pending" in m:
                    continue
                if "slow_down" in m:
                    interval += 5
                    continue
                raise
            self._set_tokens(tok)
            self.after_login()
            return
        raise ApiError(0, {"message": "Der Code ist abgelaufen. Bitte noch einmal anmelden."})

    def token(self):
        if self._token_ok():
            return self.store["access_token"]
        if not self.store.get("refresh_token"):
            raise ApiError(401, {"message": "Bitte neu anmelden."})
        try:
            self._set_tokens(self._refresh(self.store["refresh_token"]))
        except ApiError as e:
            if e.status in (400, 401):
                self.logout()
                raise ApiError(401, {"message": "Die Anmeldung ist abgelaufen. Bitte neu anmelden."}) from None
            raise
        return self.store["access_token"]

    def after_login(self):
        pass


class Twitch(Account):
    name = "twitch"
    ID = "https://id.twitch.tv/oauth2"
    API = "https://api.twitch.tv/helix"

    def __init__(self, store, save, client_id):
        super().__init__(store, save)
        self.client_id = client_id

    def _device_start(self):
        return http("POST", f"{self.ID}/device", {"client_id": self.client_id, "scopes": TWITCH_SCOPES}, form=True)

    def _device_poll(self, code):
        return http("POST", f"{self.ID}/token", {
            "client_id": self.client_id, "scopes": TWITCH_SCOPES, "device_code": code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, form=True)

    def _refresh(self, refresh):
        return http("POST", f"{self.ID}/token", {"client_id": self.client_id, "grant_type": "refresh_token",
                                                 "refresh_token": refresh}, form=True)

    def after_login(self):
        info = http("GET", f"{self.ID}/validate", headers={"Authorization": f"OAuth {self.token()}"})
        self.store["login"] = info.get("login", "")
        self.store["user_id"] = info.get("user_id", "")
        self.save()

    def _api(self, method, path, data=None):
        h = {"Authorization": f"Bearer {self.token()}", "Client-Id": self.client_id}
        return http(method, f"{self.API}/{path}", data, h)

    @property
    def login_name(self):
        return self.store.get("login", "")

    def channel(self):
        d = self._api("GET", f"channels?broadcaster_id={self.store['user_id']}").get("data") or [{}]
        return {"title": d[0].get("title", ""), "category": d[0].get("game_name", ""),
                "category_id": d[0].get("game_id", "")}

    def set_channel(self, title, category_id=None):
        body = {"title": title[:140]}
        if category_id:
            body["game_id"] = category_id
        self._api("PATCH", f"channels?broadcaster_id={self.store['user_id']}", body)

    def search_categories(self, query):
        q = urllib.parse.quote(query)
        return [{"id": c["id"], "name": c["name"]}
                for c in self._api("GET", f"search/categories?query={q}&first=8").get("data", [])]

    def stream_target(self):
        d = self._api("GET", f"streams/key?broadcaster_id={self.store['user_id']}").get("data") or [{}]
        key = d[0].get("stream_key", "")
        return f"rtmp://live.twitch.tv/app/{key}" if key else ""

    def chat_url(self, dark=True):
        login = self.login_name
        return f"https://www.twitch.tv/popout/{login}/chat?{'darkpopout' if dark else 'popout'}" if login else ""


class YouTube(Account):
    name = "youtube"
    OAUTH = "https://oauth2.googleapis.com"
    API = "https://www.googleapis.com/youtube/v3"

    def __init__(self, store, save, client_id, client_secret):
        super().__init__(store, save)
        self.client_id = client_id
        self.client_secret = client_secret

    def _device_start(self):
        return http("POST", f"{self.OAUTH}/device/code", {"client_id": self.client_id, "scope": YOUTUBE_SCOPE}, form=True)

    def _device_poll(self, code):
        return http("POST", f"{self.OAUTH}/token", {
            "client_id": self.client_id, "client_secret": self.client_secret, "device_code": code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, form=True)

    def _refresh(self, refresh):
        return http("POST", f"{self.OAUTH}/token", {"client_id": self.client_id, "client_secret": self.client_secret,
                                                    "grant_type": "refresh_token", "refresh_token": refresh}, form=True)

    def _api(self, method, path, data=None):
        return http(method, f"{self.API}/{path}", data, {"Authorization": f"Bearer {self.token()}"})

    def after_login(self):
        items = self._api("GET", "channels?part=snippet&mine=true").get("items") or [{}]
        self.store["login"] = items[0].get("snippet", {}).get("title", "")
        self.save()

    @property
    def login_name(self):
        return self.store.get("login", "")

    def broadcast(self):
        """Aktuelle Übertragung: läuft gerade eine, sonst die Standard-Übertragung („Jetzt streamen“)."""
        for query in ("broadcastStatus=active&broadcastType=all", "mine=true&broadcastType=persistent",
                      "broadcastStatus=upcoming&broadcastType=all"):
            items = self._api("GET", f"liveBroadcasts?part=id,snippet,contentDetails,status&{query}&maxResults=5"
                              ).get("items") or []
            if items:
                return items[0]
        return None

    def channel(self):
        b = self.broadcast()
        if not b:
            return {"title": "", "category": "", "category_id": "", "chat": "", "video": ""}
        sn = b.get("snippet", {})
        return {"title": sn.get("title", ""), "category": "", "category_id": "",
                "chat": sn.get("liveChatId", ""), "video": b.get("id", "")}

    def set_channel(self, title, category_id=None):
        b = self.broadcast()
        if not b:
            raise ApiError(404, {"message": "Keine YouTube-Übertragung gefunden. Ist Livestreaming im Kanal freigeschaltet?"})
        sn = b.get("snippet", {})
        snippet = {"title": title[:100], "description": sn.get("description", "")}
        if sn.get("scheduledStartTime"):
            snippet["scheduledStartTime"] = sn["scheduledStartTime"]
        self._api("PUT", "liveBroadcasts?part=snippet", {"id": b["id"], "snippet": snippet})

    def stream_target(self):
        b = self.broadcast()
        sid = (b or {}).get("contentDetails", {}).get("boundStreamId")
        if not sid:
            return ""
        items = self._api("GET", f"liveStreams?part=cdn&id={sid}").get("items") or [{}]
        ing = items[0].get("cdn", {}).get("ingestionInfo", {})
        if not ing.get("streamName"):
            return ""
        return f"{ing.get('ingestionAddress', 'rtmp://a.rtmp.youtube.com/live2')}/{ing['streamName']}"

    def send_chat(self, chat_id, text):
        self._api("POST", "liveChat/messages?part=snippet", {"snippet": {
            "liveChatId": chat_id, "type": "textMessageEvent", "textMessageDetails": {"messageText": text[:200]}}})

    @staticmethod
    def chat_url(video, dark=True):
        return f"https://www.youtube.com/live_chat?is_popout=1&v={video}{'&dark_theme=1' if dark else ''}" if video else ""


# ---------------------------------------------------------------------------------------------
class TwitchChat:
    """Nachrichten in den eigenen Twitch-Chat schreiben (IRC über TLS, je Nachricht kurz verbinden)."""

    HOST = ("irc.chat.twitch.tv", 6697)

    def __init__(self, account):
        self.account = account
        self.lock = threading.Lock()

    def send(self, text):
        text = " ".join(text.split())[:480]
        if not text:
            return
        login = self.account.login_name
        token = self.account.token()
        with self.lock:
            try:
                raw = socket.create_connection(self.HOST, timeout=TIMEOUT)
                with ssl.create_default_context().wrap_socket(raw, server_hostname=self.HOST[0]) as s:
                    s.sendall(f"PASS oauth:{token}\r\nNICK {login}\r\n".encode())
                    buf = b""
                    while b" 001 " not in buf:
                        chunk = s.recv(4096)
                        if not chunk or b"Login authentication failed" in chunk or b"Improperly formatted" in chunk:
                            raise ApiError(401, {"message": "Twitch-Chat: Anmeldung abgelehnt"})
                        buf += chunk
                    s.sendall(f"PRIVMSG #{login} :{text}\r\n".encode())
                    time.sleep(0.3)
                    s.sendall(b"QUIT\r\n")
            except OSError as e:
                raise ApiError(0, {"message": f"Twitch-Chat nicht erreichbar ({e})"}) from None
