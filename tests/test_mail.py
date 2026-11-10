"""Creative Mail: Nachrichten zerlegen und bauen (ohne Netz, ohne Qt)."""

import sys
import unittest
from email import policy
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mail"))
import gmail  # noqa: E402


def sample_mail():
    m = EmailMessage()
    m["From"] = "Anna Beispiel <anna@example.org>"
    m["To"] = "ich@example.org, Bert <bert@example.org>"
    m["Cc"] = "carla@example.org"
    m["Subject"] = "Grüße aus München"
    m["Message-ID"] = "<abc@example.org>"
    m.set_content("Hallo!\nText-Teil")
    m.add_alternative('<p>Hallo <b>du</b> <img src="cid:logo1"></p>', subtype="html")
    m.get_payload()[1].add_related(b"\x89PNG-bild", maintype="image", subtype="png", cid="<logo1>")
    m.add_attachment(b"%PDF-1.4 daten", maintype="application", subtype="pdf", filename="Rechnung März.pdf")
    return m.as_bytes(policy=policy.SMTP)


class ParseTest(unittest.TestCase):
    def test_parts(self):
        mail = gmail.parse_message(sample_mail())
        self.assertEqual(mail["subject"], "Grüße aus München")
        self.assertIn("Text-Teil", mail["text"])
        self.assertIn("<b>du</b>", mail["html"])
        self.assertEqual([a["name"] for a in mail["attachments"]], ["Rechnung März.pdf"])
        self.assertEqual(mail["attachments"][0]["data"], b"%PDF-1.4 daten")
        self.assertEqual(mail["inline"]["logo1"], ("image/png", b"\x89PNG-bild"))
        self.assertEqual(mail["cc"], "carla@example.org")
        self.assertEqual(mail["message_id"], "<abc@example.org>")

    def test_plain_only(self):
        m = EmailMessage()
        m["Subject"] = ""
        m.set_content("nur Text")
        mail = gmail.parse_message(m.as_bytes())
        self.assertEqual(mail["subject"], "(Ohne Betreff)")
        self.assertEqual(mail["html"], "")
        self.assertIn("nur Text", mail["text"])


class BuildTest(unittest.TestCase):
    def test_reply_with_attachments(self):
        reply = {"message_id": "<abc@example.org>", "references": "<x@y>", "threadId": "t1"}
        msg = gmail.build_message("ich@example.org", "anna@example.org", "Re: Hallo", "Text", cc="b@example.org",
                                  bcc="geheim@example.org", html="<p>Text</p>",
                                  attachments=[{"name": "foto.jpg", "data": b"jpgdaten"}], reply=reply)
        self.assertEqual(msg["In-Reply-To"], "<abc@example.org>")
        self.assertEqual(msg["References"], "<x@y> <abc@example.org>")
        self.assertEqual(msg["Bcc"], "geheim@example.org")
        parsed = gmail.parse_message(msg.as_bytes(policy=policy.SMTP))
        self.assertEqual(parsed["attachments"][0]["name"], "foto.jpg")
        self.assertEqual(parsed["attachments"][0]["type"], "image/jpeg")
        self.assertIn("<p>Text</p>", parsed["html"])

    def test_file_attachment(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "notiz.txt")
            path.write_bytes(b"inhalt")
            msg = gmail.build_message("a@b.c", "d@e.f", "x", "y", attachments=[str(path)])
            self.assertEqual(gmail.parse_message(msg.as_bytes())["attachments"][0]["data"], b"inhalt")


class SummaryTest(unittest.TestCase):
    def test_summary(self):
        message = {"id": "1", "threadId": "t", "internalDate": "1700000000000", "snippet": "Tom &amp; Jerry",
                   "labelIds": ["UNREAD", "STARRED", "INBOX"],
                   "payload": {"headers": [{"name": "From", "value": "A <a@x>"}, {"name": "To", "value": "B <b@x>"},
                                           {"name": "Subject", "value": "Hi"}]}}
        row = gmail.summary(message, "INBOX")
        self.assertEqual((row["from"], row["subject"], row["snippet"]), ("A <a@x>", "Hi", "Tom & Jerry"))
        self.assertTrue(row["unread"] and row["starred"])
        self.assertEqual(row["date"], 1700000000)
        self.assertEqual(gmail.summary(message, "SENT")["from"], "B <b@x>")
        self.assertEqual(gmail.summary({"payload": {"headers": []}})["subject"], "(Ohne Betreff)")


class FakeApiTest(unittest.TestCase):
    def test_labels_and_listing(self):
        g = gmail.Gmail.__new__(gmail.Gmail)
        g.address = "ich@example.org"
        g.expires = float("inf")
        import threading
        g._lock = threading.Lock()
        calls = []

        def api(path, params=None, data=None):
            calls.append((path, params, data))
            if path == "labels":
                return {"labels": [{"id": "Label_2", "name": "zeta", "type": "user"},
                                   {"id": "Label_1", "name": "Alpha", "type": "user"},
                                   {"id": "INBOX", "name": "INBOX", "type": "system"}]}
            if path.startswith("labels/"):
                return {"messagesUnread": 2, "threadsUnread": 5}
            if path == "messages":
                return {"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "p2"}
            if path.startswith("messages/"):
                return {"id": path.split("/")[1], "labelIds": [], "payload": {"headers": []}}
            return {}

        g.api = api
        labels = g.labels()
        self.assertEqual(labels[0], ("INBOX", "Posteingang", 5, True))
        self.assertEqual([l[1] for l in labels if not l[3]], ["Alpha", "zeta"])
        rows, page = g.listing("TRASH", "", None)
        self.assertEqual(([r["id"] for r in rows], page), (["m1", "m2"], "p2"))
        self.assertIn(("messages", {"maxResults": 30, "labelIds": "TRASH", "includeSpamTrash": "true"}, None), calls)
        g.modify("m1", add=["STARRED"])
        self.assertIn(("messages/m1/modify", None, {"addLabelIds": ["STARRED"], "removeLabelIds": []}), calls)


if __name__ == "__main__":
    unittest.main()
