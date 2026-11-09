"""Quellen, Ausgaben und zwischengespeicherte Artikel (SQLite)."""

import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone

KEEP_DAYS = 60
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    url TEXT PRIMARY KEY, title TEXT NOT NULL, home TEXT NOT NULL, added REAL NOT NULL);
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, link TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '', published REAL NOT NULL, issue TEXT NOT NULL,
    rubric TEXT NOT NULL, rubric_fixed INTEGER NOT NULL DEFAULT 0,
    read INTEGER NOT NULL DEFAULT 0, saved INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS articles_issue ON articles(issue);
CREATE TABLE IF NOT EXISTS bodies (
    id TEXT PRIMARY KEY, data TEXT NOT NULL, fetched REAL NOT NULL);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def local_day(moment):
    return moment.astimezone().strftime("%Y-%m-%d")


def issue_label(day):
    date = datetime.strptime(day, "%Y-%m-%d")
    return f"{WEEKDAYS[date.weekday()]}, {date.day}. {MONTHS[date.month - 1]} {date.year}"


def short_date(stamp):
    moment = datetime.fromtimestamp(stamp)
    return f"{moment.day}.{moment.month}.{moment.year}, {moment:%H:%M} Uhr"


class Store:
    def __init__(self, path):
        self.path = str(path)
        with closing(connect(self.path)):
            pass

    def _db(self):
        return closing(connect(self.path))

    # ------------------------------------------------------------ Quellen
    def sources(self):
        with self._db() as db:
            rows = db.execute("""SELECT s.url, s.title, s.home, COUNT(a.id) AS count FROM sources s
                                 LEFT JOIN articles a ON a.source = s.url GROUP BY s.url
                                 ORDER BY s.title COLLATE NOCASE""").fetchall()
        return [dict(row) for row in rows]

    def add_source(self, url, title, home):
        with self._db() as db, db:
            db.execute("INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?)", (url, title, home, time.time()))

    def remove_source(self, url):
        with self._db() as db, db:
            db.execute("DELETE FROM sources WHERE url = ?", (url,))
            db.execute("DELETE FROM bodies WHERE id IN (SELECT id FROM articles WHERE source = ? AND saved = 0)", (url,))
            db.execute("DELETE FROM articles WHERE source = ? AND saved = 0", (url,))

    # ------------------------------------------------------------ Artikel
    def add_articles(self, source, entries):
        now = datetime.now(timezone.utc)
        oldest = now - timedelta(days=KEEP_DAYS)
        new = 0
        with self._db() as db, db:
            for entry in entries:
                published = entry["published"] or now
                if published > now:
                    published = now
                if published < oldest:
                    continue
                known = db.execute("SELECT 1 FROM articles WHERE id = ?", (entry["id"],)).fetchone()
                db.execute("""
                    INSERT INTO articles (id, source, title, link, summary, content, image, author,
                                          published, issue, rubric)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title, summary = excluded.summary, content = excluded.content,
                        image = CASE WHEN excluded.image != '' THEN excluded.image ELSE articles.image END,
                        author = CASE WHEN excluded.author != '' THEN excluded.author ELSE articles.author END,
                        rubric = CASE WHEN articles.rubric_fixed THEN articles.rubric ELSE excluded.rubric END
                    """, (entry["id"], source, entry["title"], entry["link"], entry["summary"],
                          entry["content"], entry["image"], entry["author"], published.timestamp(),
                          local_day(published), entry["rubric"]))
                if not known:
                    new += 1
            db.execute("""DELETE FROM bodies WHERE id IN (SELECT id FROM articles
                          WHERE saved = 0 AND published < ?)""", (oldest.timestamp(),))
            db.execute("DELETE FROM articles WHERE saved = 0 AND published < ?", (oldest.timestamp(),))
        return new

    def issues(self):
        with self._db() as db:
            rows = db.execute("""SELECT a.issue, COUNT(*) AS count FROM articles a
                                 JOIN sources s ON s.url = a.source
                                 GROUP BY a.issue ORDER BY a.issue DESC""").fetchall()
        return [dict(date=row["issue"], label=issue_label(row["issue"]), count=row["count"]) for row in rows]

    def articles(self, issue):
        query = """SELECT a.*, COALESCE(s.title, '') AS site, COALESCE(s.home, '') AS home
                   FROM articles a LEFT JOIN sources s ON s.url = a.source """
        with self._db() as db:
            if issue == "gemerkt":
                rows = db.execute(query + "WHERE a.saved = 1 ORDER BY a.published DESC").fetchall()
            else:
                rows = db.execute(query + "WHERE a.issue = ? AND s.url IS NOT NULL ORDER BY a.published DESC",
                                  (issue,)).fetchall()
        return [self._public(row) for row in rows]

    def article(self, key):
        with self._db() as db:
            row = db.execute("""SELECT a.*, COALESCE(s.title, '') AS site, COALESCE(s.home, '') AS home
                                FROM articles a LEFT JOIN sources s ON s.url = a.source
                                WHERE a.id = ?""", (key,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _public(row):
        return dict(id=row["id"], title=row["title"], link=row["link"], summary=row["summary"],
                    image=row["image"], author=row["author"], date=short_date(row["published"]),
                    site=row["site"], home=row["home"], rubric=row["rubric"],
                    read=bool(row["read"]), saved=bool(row["saved"]))

    def set_flag(self, key, column, value):
        if column not in ("read", "saved"):
            raise ValueError(column)
        with self._db() as db, db:
            db.execute(f"UPDATE articles SET {column} = ? WHERE id = ?", (int(value), key))

    def set_rubric(self, key, value):
        with self._db() as db, db:
            db.execute("UPDATE articles SET rubric = ?, rubric_fixed = 1 WHERE id = ?", (value, key))

    def body(self, key):
        with self._db() as db:
            row = db.execute("SELECT data FROM bodies WHERE id = ?", (key,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_body(self, key, data):
        with self._db() as db, db:
            db.execute("INSERT OR REPLACE INTO bodies VALUES (?, ?, ?)",
                       (key, json.dumps(data, ensure_ascii=False), time.time()))

    # ------------------------------------------------------------ Zustand
    def get(self, key, default=""):
        with self._db() as db:
            row = db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def put(self, key, value):
        with self._db() as db, db:
            db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, str(value)))
