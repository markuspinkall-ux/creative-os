import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timedelta, timezone
from threading import Thread

from PySide6.QtCore import (QLockFile, QObject, Property, QStandardPaths, QTimer, QUrl, QtMsgType,
                            Signal, Slot, qInstallMessageHandler)
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from . import extract, web
from .store import Store, issue_label

HERE = Path(__file__).resolve().parent
REFRESH_SECONDS = 30 * 60


def load_body(article):
    """Volltext eines Artikels: aus dem Feed, wenn er dort vollständig steht, sonst von der Seite."""
    title = article["title"]
    from_feed = None
    if article["content"]:
        from_feed = extract.extract(f"<div>{article['content']}</div>", article["link"], title)
        if not from_feed["short"]:
            return from_feed
    try:
        data, final, charset = web.fetch(article["link"], timeout=20)
        from_page = extract.extract(web.decode(data, charset), final, title)
    except Exception:
        if from_feed and from_feed["blocks"]:
            return from_feed
        raise
    if from_feed and from_page["short"] and len(from_feed["blocks"]) > len(from_page["blocks"]):
        return from_feed
    return from_page


def demo_image():
    for path in (HERE.parents[1] / "magazin/creative-magazin.svg",
                 Path("/usr/share/icons/hicolor/scalable/apps/creative-magazin.svg")):
        if path.is_file():
            return QUrl.fromLocalFile(str(path)).toString()
    return ""


def demo(store):
    """Beispielausgabe für den Selbsttest beim Bauen (ohne Internet)."""
    now = datetime.now(timezone.utc)
    store.add_source("https://example.org/feed", "Beispielseite", "https://example.org/")
    entries = []
    for number, (title, rubric) in enumerate([
            ("Grafikkarte im Test: leise und schnell", "Tests"), ("Review: Das neue Rollenspiel", "Reviews"),
            ("Neue Treiber erschienen", "News"), ("Ratgeber: Der richtige Monitor", "Artikel"),
            ("Prozessor im Test", "Tests"), ("Kurzmeldung", "News")]):
        entries.append(dict(id=f"demo{number}", title=title, link=f"https://example.org/{number}",
                            summary="Ein kurzer Anriss des Artikels. " * 4, content="",
                            image="", author="Redaktion", published=now - timedelta(minutes=number),
                            categories=[], rubric=rubric))
    store.add_articles("https://example.org/feed", entries)
    store.save_body("demo0", dict(blocks=[
        dict(type="p", text="Erster Absatz des Artikels. " * 10, src=""),
        dict(type="h", text="Zwischenüberschrift", src=""),
        dict(type="img", text="Bildunterschrift", src=demo_image()),
        dict(type="quote", text="Ein Zitat.", src=""),
        dict(type="li", text="Ein Punkt", src="")], image="", author="", site="", short=False))


class Magazine(QObject):
    changed = Signal()
    sourcesChanged = Signal()
    issuesChanged = Signal()
    articlesChanged = Signal()
    readerChanged = Signal()
    completed = Signal(object, object, str)

    def __init__(self, store, offline=False):
        super().__init__()
        self.store = store
        self.offline = offline
        self._sources = store.sources()
        self._issues = store.issues()
        self._issue = self._issues[0]["date"] if self._issues else ""
        self._articles = store.articles(self._issue) if self._issue else []
        self._reader = {}
        self._message = ""
        self._busy = ""
        self.completed.connect(self.finish)
        self.timer = QTimer(self)
        self.timer.setInterval(15 * 60 * 1000)
        self.timer.timeout.connect(self.autoRefresh)
        if not offline:
            self.timer.start()
            QTimer.singleShot(400, self.autoRefresh)

    # ------------------------------------------------------------ Hilfen
    def run(self, work, done, label):
        def task():
            try:
                result = work()
            except Exception as exc:
                self.completed.emit(done, None, f"{label}: {exc}")
            else:
                self.completed.emit(done, result, "")
        Thread(target=task, daemon=True).start()

    @Slot(object, object, str)
    def finish(self, done, result, error):
        if error:
            self._message = error
        done(result)
        self.changed.emit()

    def reload(self, follow_latest=False):
        latest = self._issues[0]["date"] if self._issues else ""
        self._sources = self.store.sources()
        self._issues = self.store.issues()
        dates = [item["date"] for item in self._issues]
        if not self._issue or (follow_latest and self._issue == latest) or \
                (self._issue != "gemerkt" and self._issue not in dates):
            self._issue = dates[0] if dates else ""
        self._articles = self.store.articles(self._issue) if self._issue else []
        self.sourcesChanged.emit()
        self.issuesChanged.emit()
        self.articlesChanged.emit()
        self.changed.emit()

    # ------------------------------------------------------------ Eigenschaften
    @Property("QVariantList", notify=sourcesChanged)
    def sources(self):
        return self._sources

    @Property("QVariantList", notify=sourcesChanged)
    def catalogue(self):
        added = {source["home"].rstrip("/") for source in self._sources} | {source["url"] for source in self._sources}
        return [dict(name=site["name"], home=site["home"],
                     added=site["home"].rstrip("/") in added or site["feed"] in added)
                for site in web.CATALOGUE]

    @Property("QVariantList", notify=issuesChanged)
    def issues(self):
        return self._issues

    @Property(str, notify=articlesChanged)
    def issue(self):
        return self._issue

    @Property(str, notify=articlesChanged)
    def issueLabel(self):
        if self._issue == "gemerkt":
            return "Gemerkte Artikel"
        return issue_label(self._issue) if self._issue else ""

    @Property("QVariantList", notify=articlesChanged)
    def articles(self):
        return self._articles

    @Property("QVariantMap", notify=readerChanged)
    def reader(self):
        return self._reader

    @Property(str, notify=changed)
    def status(self):
        return self._message

    @Property(str, notify=changed)
    def busy(self):
        return self._busy

    # ------------------------------------------------------------ Aktionen
    @Slot()
    def autoRefresh(self):
        last = float(self.store.get("refreshed", "0") or 0)
        if time.time() - last >= REFRESH_SECONDS:
            self.refresh()

    @Slot()
    def refresh(self):
        if self._busy or not self._sources:
            return
        self._busy = "refresh"
        self._message = "Neue Artikel werden geholt …"
        self.changed.emit()
        sources = list(self._sources)

        def one(source):
            data, final, _ = web.fetch(source["url"])
            _, _, entries = web.parse_feed(data, final)
            return self.store.add_articles(source["url"], entries[:60])

        def work():
            new, failed = 0, []
            with ThreadPoolExecutor(max_workers=6) as pool:
                for source, future in [(s, pool.submit(one, s)) for s in sources]:
                    try:
                        new += future.result()
                    except Exception:
                        failed.append(source["title"])
            self.store.put("refreshed", time.time())
            return new, failed

        def done(result):
            self._busy = ""
            if result is None:
                return
            new, failed = result
            self._message = (f"{new} neue Artikel." if new else "Keine neuen Artikel.")
            if failed:
                self._message += " Nicht erreichbar: " + ", ".join(failed) + "."
            self.reload(follow_latest=True)

        self.run(work, done, "Aktualisieren fehlgeschlagen")

    @Slot(str)
    def addSource(self, query):
        query = query.strip()
        if not query or self._busy:
            return
        self._busy = "add"
        self._message = "Seite wird gesucht …"
        self.changed.emit()

        def work():
            info = web.discover(query)
            if any(source["url"] == info["url"] for source in self._sources):
                raise ValueError(f"{info['title']} ist schon in deinem Magazin.")
            data, final, _ = web.fetch(info["url"])
            _, _, entries = web.parse_feed(data, final)
            self.store.add_source(info["url"], info["title"], info["home"])
            self.store.add_articles(info["url"], entries[:60])
            return info

        def done(info):
            self._busy = ""
            if info is not None:
                self._message = f"{info['title']} wurde hinzugefügt."
                self.reload(follow_latest=True)

        self.run(work, done, "Hinzufügen fehlgeschlagen")

    @Slot(str)
    def removeSource(self, url):
        self.store.remove_source(url)
        self._message = "Quelle entfernt. Gemerkte Artikel bleiben erhalten."
        self.reload()

    @Slot(str)
    def openIssue(self, date):
        self._issue = date
        self._articles = self.store.articles(date)
        self.articlesChanged.emit()

    @Slot(str)
    def openArticle(self, key):
        article = self.store.article(key)
        if article is None:
            return
        self.store.set_flag(key, "read", True)
        for item in self._articles:
            if item["id"] == key:
                item["read"] = True
        reader = dict(id=key, title=article["title"], rubric=article["rubric"], link=article["link"],
                      site=article["site"] or web.site_name(article["link"]),
                      home=article["home"] or article["link"], author=article["author"],
                      date=self.store._public(article)["date"], image=article["image"],
                      summary=article["summary"], saved=bool(article["saved"]),
                      blocks=[], loading=True, short=False, error="")
        cached = self.store.body(key)
        if cached is not None:
            self._reader = self._merge(reader, cached)
            self.readerChanged.emit()
            return
        self._reader = reader
        self.readerChanged.emit()

        def work():
            body = load_body(article)
            self.store.save_body(key, body)
            return body

        def done(body):
            if self._reader.get("id") != key:
                return
            if body is None:
                self._reader = dict(self._reader, loading=False, short=True,
                                    error="Der Artikel konnte nicht geladen werden. Du kannst ihn im Original lesen.")
            else:
                self._reader = self._merge(self._reader, body)
            self.readerChanged.emit()

        self.run(work, done, "Artikel laden fehlgeschlagen")

    @staticmethod
    def _merge(reader, body):
        return dict(reader, blocks=body["blocks"], short=body["short"], loading=False,
                    author=reader["author"] or body.get("author", ""),
                    image=body.get("image") or reader["image"], error="")

    @Slot()
    def closeArticle(self):
        self._reader = {}
        self.readerChanged.emit()
        self.articlesChanged.emit()

    @Slot(str)
    def toggleSaved(self, key):
        article = self.store.article(key)
        if article is None:
            return
        saved = not article["saved"]
        self.store.set_flag(key, "saved", saved)
        if self._reader.get("id") == key:
            self._reader = dict(self._reader, saved=saved)
            self.readerChanged.emit()
        self._message = "Artikel gemerkt." if saved else "Nicht mehr gemerkt."
        self._articles = self.store.articles(self._issue) if self._issue else []
        self.articlesChanged.emit()
        self.changed.emit()

    @Slot(str, str)
    def setRubric(self, key, value):
        if value in web.RUBRICS:
            self.store.set_rubric(key, value)
            self._articles = self.store.articles(self._issue)
            self.articlesChanged.emit()

    @Slot(str)
    def openOriginal(self, url):
        if web.web_url(url):
            QDesktopServices.openUrl(QUrl(url))


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("Creative OS")
    app.setApplicationName("Creative Magazin")
    app.setDesktopFileName("creative-magazin")
    app.setWindowIcon(QIcon.fromTheme("creative-magazin"))

    data = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    data.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        return 1
    selftest = "--selftest" in sys.argv
    problems = []
    if selftest:
        # Jede QML-Warnung lässt den Selbsttest scheitern.
        def handler(kind, context, message):
            print(message, file=sys.stderr)
            if kind != QtMsgType.QtDebugMsg and kind != QtMsgType.QtInfoMsg and ".qml" in message:
                problems.append(message)
        qInstallMessageHandler(handler)
        store = Store(data / "selftest.sqlite")
        demo(store)
    else:
        store = Store(data / "magazin.sqlite")
    magazine = Magazine(store, offline=selftest)
    engine = QQmlApplicationEngine()
    for location in (
        HERE.parents[1] / "shell/creative_shell/qml",
        Path("/usr/lib/creative-shell/creative_shell/qml"),
    ):
        if (location / "Creative/qmldir").is_file():
            engine.addImportPath(str(location))
            break
    engine.setInitialProperties({"magazine": magazine, "selftest": selftest})
    engine.load(QUrl.fromLocalFile(str(HERE / "qml/Main.qml")))
    if not engine.rootObjects():
        return 1
    if selftest:
        def timeout():
            problems.append("Zeitüberschreitung: Der QML-Selbsttest wurde nicht beendet.")
            app.quit()
        QTimer.singleShot(30000, timeout)
    result = app.exec()
    del engine
    if selftest:
        for suffix in ("", "-wal", "-shm"):
            (data / f"selftest.sqlite{suffix}").unlink(missing_ok=True)
        if problems:
            print(f"Selbsttest: {len(problems)} QML-Warnung(en).", file=sys.stderr)
            return 1
        print("Creative Magazin: Selbsttest bestanden")
    return result


if __name__ == "__main__":
    sys.exit(main())
