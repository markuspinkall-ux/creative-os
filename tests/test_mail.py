"""Creative Mail: Nachrichten zerlegen und bauen (ohne Netz, ohne Qt)."""

import sys
import unittest
from email import policy
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mail"))
import mailcore as gmail  # noqa: E402
import mailcore  # noqa: E402


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


class ProviderTest(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(mailcore.provider_for("Max@GMX.de"), "gmx")
        self.assertEqual(mailcore.provider_for("a@web.de"), "webde")
        self.assertEqual(mailcore.provider_for("a@googlemail.com"), "gmail")
        self.assertEqual(mailcore.provider_for("a@hotmail.de"), "outlook")
        self.assertEqual(mailcore.provider_for("a@firma.example"), "custom")
        cfg = mailcore.account_settings("max@icloud.com")
        self.assertEqual((cfg["user"], cfg["imap_host"], cfg["smtp_port"], cfg["smtp_mode"]),
                         ("max", "imap.mail.me.com", 587, "starttls"))
        cfg = mailcore.account_settings("a@gmail.com")
        self.assertTrue(cfg["saves_sent"] and cfg["user"] == "a@gmail.com")
        self.assertIn("unsupported", mailcore.PROVIDERS["outlook"])
        for key in mailcore.ORDER:
            self.assertIn(key, mailcore.PROVIDERS)


class ImapHelperTest(unittest.TestCase):
    def test_utf7(self):
        self.assertEqual(mailcore.utf7_decode("Entw&APw-rfe"), "Entwürfe")
        self.assertEqual(mailcore.utf7_decode("A &- B"), "A & B")
        for name in ("Entwürfe", "Gelöschte Elemente", "Tom & Jerry", "日本"):
            self.assertEqual(mailcore.utf7_decode(mailcore.utf7_encode(name)), name)

    def test_list_and_roles(self):
        lines = [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Gesendet"',
                 b'(\\Noselect \\HasChildren) "/" "[Gmail]"', b'(\\HasNoChildren \\All) "/" "[Gmail]/Alle Nachrichten"',
                 b'(\\HasNoChildren \\Flagged) "/" "[Gmail]/Markiert"', b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Papierkorb"',
                 b'(\\HasNoChildren) "/" "Entw&APw-rfe"', b'(\\HasNoChildren) "/" "Spamverdacht"',
                 b'(\\HasNoChildren) "/" "Rechnungen"', b'(\\HasNoChildren) "/" Urlaub']
        lines = [l.replace(b"\\\\", b"\\") for l in lines]
        roles, rest = mailcore.folder_roles(mailcore.parse_list(lines))
        self.assertEqual(roles["SENT"], "[Gmail]/Gesendet")
        self.assertEqual(roles["ALL"], "[Gmail]/Alle Nachrichten")
        self.assertEqual(roles["STARRED"], "[Gmail]/Markiert")
        self.assertEqual(roles["DRAFT"], "Entw&APw-rfe")
        self.assertEqual(roles["SPAM"], "Spamverdacht")
        self.assertEqual(rest, ["Rechnungen", "Urlaub"])

    def test_ids_and_snippet(self):
        mid = mailcore.make_id("Ordner|mit Strich", 42)
        self.assertEqual(mailcore.split_id(mid), ("Ordner|mit Strich", "42"))
        raw = (b"--b1\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n"
               b"Hallo M=C3=BCnchen, <b>wie</b> geht's?\r\n--b1\r\n")
        self.assertEqual(mailcore.snippet_from(raw), "Hallo München, wie geht's?")

    def test_parse_fetch_and_row(self):
        data = [(b'1 (UID 7 FLAGS (\\Seen \\Flagged) INTERNALDATE "17-Jul-2026 10:00:00 +0200" '
                 b'BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)] {60}',
                 b"From: =?utf-8?q?J=C3=BCrgen?= <j@x.de>\r\nSubject: Hallo\r\nTo: ich@x.de\r\n\r\n"), b")"]
        items = mailcore.parse_fetch(data)
        self.assertEqual(items[0]["uid"], 7)
        row = mailcore.summary_row("INBOX", 7, items[0]["flags"], items[0]["date"], items[0]["literal"])
        self.assertEqual((row["from"], row["subject"], row["unread"], row["starred"]),
                         ("Jürgen <j@x.de>", "Hallo", False, True))
        self.assertEqual(row["id"], "7|INBOX")
        self.assertGreater(row["date"], 0)


class FakeConn:
    def __init__(self):
        self.calls = []
        self.capabilities = ("IMAP4REV1", "MOVE", "UIDPLUS")
        self.literal = None

    def noop(self):
        return "OK", [b""]

    def capability(self):
        return "OK", [b"IMAP4rev1 MOVE UIDPLUS"]

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Archive) "/" "Archiv"',
                      b'(\\HasNoChildren \\Trash) "/" "Papierkorb"']

    def select(self, name, readonly=False):
        self.calls.append(("select", name, readonly))
        return "OK", [b"3"]

    def status(self, name, what):
        return "OK", [name.encode() + b" (UNSEEN 2)"]

    def uid(self, cmd, *args):
        self.calls.append((cmd,) + args)
        if cmd == "SEARCH":
            return "OK", [b"1 2 3"]
        if cmd == "FETCH" and "HEADER" in args[1]:
            return "OK", [(f"{i} (UID {u} FLAGS () BODY[HEADER.FIELDS (FROM)] {{20}}".encode(), b"Subject: M%d\r\n\r\n" % u)
                          for i, u in enumerate(int(x) for x in args[0].split(","))] + [b")"]
        return "OK", [b""]


class FakeAccountTest(unittest.TestCase):
    def test_listing_paging_and_actions(self):
        acc = mailcore.MailAccount(mailcore.account_settings("ich@gmx.de"), "pw")
        conn = FakeConn()
        acc._conn = conn
        acc.caps = {"MOVE", "UIDPLUS"}
        labels = acc.labels()
        self.assertEqual(labels[0], ("INBOX", "Posteingang", 2, True))
        self.assertIn(("ARCHIVE", "Archiv", 0, True), labels)
        rows, page = acc.listing("INBOX", "", None, size=2)
        self.assertEqual(([r["subject"] for r in rows], page), (["M3", "M2"], 2))
        rows, page = acc.listing("INBOX", "", page, size=2)
        self.assertEqual(([r["id"] for r in rows], page), (["1|INBOX"], None))
        acc.modify("3|INBOX", add=["STARRED"], remove=["INBOX"])
        self.assertIn(("STORE", "3", "+FLAGS.SILENT", "(\\Flagged)"), conn.calls)
        self.assertIn(("MOVE", "3", '"Archiv"'), conn.calls)
        acc.trash("2|INBOX")
        self.assertIn(("MOVE", "2", '"Papierkorb"'), conn.calls)
        acc.listing("INBOX", "Rechnung März", None)
        self.assertEqual(conn.literal, "Rechnung März".encode())
        self.assertIn(("SEARCH", "CHARSET", "UTF-8", "TEXT"), conn.calls)


if __name__ == "__main__":
    unittest.main()
