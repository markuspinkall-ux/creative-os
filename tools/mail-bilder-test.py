"""Mail: Bilder aus dem Netz – gesperrt ohne Erlaubnis, geladen mit Erlaubnis.

Startet einen kleinen HTTP-Server mit einem Bild und lässt die echte WebEngine-Ansicht
der Mail-App eine HTML-Mail anzeigen. Gezählt wird, ob das Bild beim Server abgerufen wurde.
    QT_QPA_PLATFORM=offscreen python3 tools/mail-bilder-test.py
"""
import http.server
import importlib.machinery
import importlib.util
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mail"))
loader = importlib.machinery.SourceFileLoader("creative_mail", str(ROOT / "mail" / "creative-mail"))
spec = importlib.util.spec_from_loader("creative_mail", loader)
cm = importlib.util.module_from_spec(spec)
loader.exec_module(cm)

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e2fd6e9e0000000049454e44ae426082")
hits = []


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        hits.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(PNG)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}"

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
view = cm.make_web_view()
assert view, "Qt WebEngine fehlt"
view.resize(600, 400)
view.show()


def mail(n):
    return {"html": f'<p>Hallo</p><img src="{url}/bild{n}.png" width="50" height="50">', "text": "", "inline": {}}


ergebnis = {}


def schritt1():
    view.show_mail(mail(1), False)
    QTimer.singleShot(4000, schritt2)


def schritt2():
    ergebnis["gesperrt"] = [h for h in hits if "bild1" in h]
    view.show_mail(mail(2), True)
    QTimer.singleShot(4000, schritt3)


def schritt3():
    ergebnis["erlaubt"] = [h for h in hits if "bild2" in h]
    view.show_mail(mail(3), False)
    QTimer.singleShot(4000, schritt4)


def schritt4():
    ergebnis["wieder_gesperrt"] = [h for h in hits if "bild3" in h]
    app.quit()


QTimer.singleShot(500, schritt1)
app.exec()
print("Abrufe:", ergebnis)
assert not ergebnis["gesperrt"], "Bild wurde ohne Erlaubnis geladen"
assert ergebnis["erlaubt"], "Bild wurde trotz Erlaubnis NICHT geladen"
assert not ergebnis["wieder_gesperrt"], "Erlaubnis gilt fälschlich auch für die nächste Mail"
print("Mail-Bilder: ok")
