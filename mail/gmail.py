"""Desktop OAuth and the Gmail API. Mail and credentials stay on the PC."""

import base64
import hashlib
import json
import secrets
import subprocess
import time
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from webbrowser import open as open_browser

SCOPE = "https://www.googleapis.com/auth/gmail.modify"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me/"


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def unb64(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def load_client(path):
    try:
        data = json.loads(Path(path).read_text())["installed"]
        client_id, secret = data["client_id"], data["client_secret"]
        if isinstance(client_id, str) and client_id.endswith(".apps.googleusercontent.com") and isinstance(secret, str) and secret:
            return client_id, secret
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise ValueError("Bitte eine Google-OAuth-JSON-Datei vom Typ Desktop-App auswählen.")


def request(url, data=None, token=None, form=False):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        data = (urlencode(data) if form else json.dumps(data)).encode()
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 401:
            message = "Google hat den Zugang abgelehnt. Bitte erneut anmelden."
        elif exc.code == 403:
            message = "Google verweigert den Zugriff. Gmail API, Freigabe und Testnutzer prüfen."
        else:
            message = f"Google-Anfrage fehlgeschlagen (HTTP {exc.code})."
        raise RuntimeError(message) from None


def browser_code(client_id, verifier):
    state = secrets.token_urlsafe(32)
    result = {}

    class Callback(BaseHTTPRequestHandler):
        timeout = 3

        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = urlsplit(self.path)
            params = parse_qs(path.query)
            if path.path != "/" or params.get("state") != [state]:
                self.send_error(400)
                return
            result["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Anmeldung abgeschlossen. Zurück zu Creative Mail.".encode())

    with HTTPServer(("127.0.0.1", 0), Callback) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/"
        params = {
            "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
            "scope": SCOPE, "state": state, "access_type": "offline",
            "prompt": "consent select_account", "code_challenge_method": "S256",
            "code_challenge": b64(hashlib.sha256(verifier.encode()).digest()),
        }
        if not open_browser("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)):
            raise RuntimeError("Der Standardbrowser ließ sich nicht öffnen.")
        deadline = time.monotonic() + 180
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result.get("code"):
        raise RuntimeError("Google-Anmeldung abgebrochen oder Zeit abgelaufen.")
    return result["code"], redirect


class Gmail:
    def __init__(self, client_file, address=""):
        self.client_id, self.secret = load_client(client_file)
        self.address = address
        self.access = ""
        self.expires = 0

    def keyring(self, action, value=None):
        args = ["secret-tool", action]
        if action == "store":
            args += ["--label=Creative Mail – " + self.address]
        args += ["application", "creative-mail", "client", self.client_id, "account", self.address]
        result = subprocess.run(args, input=value, text=True, capture_output=True, timeout=45)
        if result.returncode != 0:
            raise RuntimeError("Der Zugang im System-Schlüsselbund ist nicht verfügbar. Bitte entsperren oder erneut anmelden.")
        return result.stdout.strip()

    def token(self, fields):
        result = request(TOKEN_URL, {
            "client_id": self.client_id, "client_secret": self.secret, **fields,
        }, form=True)
        self.access = result["access_token"]
        self.expires = time.monotonic() + result.get("expires_in", 3600) - 60
        return result

    def connect(self):
        verifier = secrets.token_urlsafe(64)
        code, redirect = browser_code(self.client_id, verifier)
        result = self.token({
            "grant_type": "authorization_code", "code": code, "code_verifier": verifier,
            "redirect_uri": redirect,
        })
        self.address = self.api("profile")["emailAddress"]
        if not result.get("refresh_token"):
            raise RuntimeError("Google hat keinen dauerhaften Zugang erteilt. Bitte erneut anmelden.")
        self.keyring("store", result["refresh_token"])
        return self.address

    def api(self, path, params=None, data=None):
        if time.monotonic() >= self.expires:
            refresh = self.keyring("lookup")
            if not refresh:
                raise RuntimeError("Bitte das Google-Konto erneut verbinden.")
            self.token({"grant_type": "refresh_token", "refresh_token": refresh})
        return request(API + path + ("?" + urlencode(params) if params else ""), data, self.access)

    def listing(self, folder, query, page):
        params = {"maxResults": 20}
        if folder:
            params["labelIds"] = folder
        if query:
            params["q"] = query
        if page:
            params["pageToken"] = page
        response = self.api("messages", params)
        rows = []
        for item in response.get("messages", []):
            message = self.api("messages/" + item["id"], [
                ("format", "metadata"), ("metadataHeaders", "From"),
                ("metadataHeaders", "To"), ("metadataHeaders", "Subject"),
            ])
            headers = {h["name"].lower(): h["value"] for h in message["payload"]["headers"]}
            correspondent = "to" if folder == "SENT" else "from"
            rows.append((item["id"], headers.get(correspondent, ""), headers.get("subject", "(Ohne Betreff)"),
                         "UNREAD" in message.get("labelIds", [])))
        return rows, response.get("nextPageToken")

    def message(self, message_id, unread):
        raw = self.api("messages/" + message_id, {"format": "raw"})["raw"]
        message = BytesParser(policy=policy.default).parsebytes(unb64(raw))
        part = message.get_body(preferencelist=("plain", "html"))
        body = part.get_content(errors="replace") if part else ""
        if unread:
            self.api(f"messages/{message_id}/modify", data={"removeLabelIds": ["UNREAD"]})
        return str(message["Subject"] or "(Ohne Betreff)"), str(message["From"] or ""), body, bool(
            part and part.get_content_type() == "text/html"
        )

    def send(self, recipient, subject, body):
        message = EmailMessage()
        message["From"] = self.address
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        self.api("messages/send", data={"raw": b64(message.as_bytes(policy=policy.SMTP))})
