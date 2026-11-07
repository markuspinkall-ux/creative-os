import json
import sys
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, Property, QLockFile, QSettings, QStandardPaths, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from . import feeds

HERE = Path(__file__).resolve().parent


class Podcasts(QObject):
    changed = Signal()
    catalogueChanged = Signal()
    playlistChanged = Signal()
    followingChanged = Signal()
    offlineChanged = Signal()
    completed = Signal(object, object, str)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.settings = QSettings()
        self.subscriptions = self.read("subscriptions")
        self.downloads = {key: item for key, item in self.read("downloads").items()
                          if Path(item["file"]).is_file()}
        self.pending = set()
        self.results = []
        self.episodes = []
        self.show = {}
        self.message = ""
        self.busy = False
        self.completed.connect(self.finish)

    def read(self, key):
        try:
            return json.loads(self.settings.value(key, "{}"))
        except (ValueError, TypeError):
            return {}

    def save(self, key, value):
        self.settings.setValue(key, json.dumps(value, ensure_ascii=False))
        self.settings.sync()

    def run(self, work, done, label):
        def task():
            try:
                result = work()
            except Exception as exc:
                self.completed.emit(done, None, f"{label} fehlgeschlagen: {exc}")
            else:
                self.completed.emit(done, result, "")
        Thread(target=task, daemon=True).start()

    @Slot(object, object, str)
    def finish(self, done, result, error):
        self.message = error
        done(result)
        self.changed.emit()

    @Property("QVariantList", notify=catalogueChanged)
    def catalogue(self):
        return self.results

    @Property("QVariantList", notify=followingChanged)
    def following(self):
        return list(self.subscriptions.values())

    @Property("QVariantList", notify=playlistChanged)
    def playlist(self):
        return self.episodes

    @Property("QVariantList", notify=offlineChanged)
    def offline(self):
        return list(self.downloads.values())

    @Property("QVariantMap", notify=changed)
    def selected(self):
        return self.show

    @Property(bool, notify=changed)
    def followed(self):
        return self.show.get("url") in self.subscriptions

    @Property(bool, notify=changed)
    def loading(self):
        return self.busy

    @Property(str, notify=changed)
    def status(self):
        return self.message

    @Property("QStringList", notify=changed)
    def downloadedKeys(self):
        return list(self.downloads)

    @Property("QStringList", notify=changed)
    def pendingKeys(self):
        return list(self.pending)

    @Slot(str)
    def search(self, term):
        term = term.strip()
        if not term or self.busy:
            return
        self.busy = True
        self.message = "Suche läuft …"
        self.changed.emit()

        def done(result):
            self.busy = False
            if result is not None:
                self.results = result
                self.catalogueChanged.emit()
                self.message = "" if result else "Keine Podcasts gefunden."

        self.run(lambda: feeds.search(term), done, "Suche")

    @Slot("QVariantMap")
    def openShow(self, show):
        if self.busy:
            return
        self.busy = True
        self.message = "Folgen werden geladen …"
        self.changed.emit()

        def done(result):
            self.busy = False
            if result is not None:
                self.show, self.episodes = result
                self.playlistChanged.emit()
                self.message = "" if self.episodes else "Dieser Feed enthält keine abspielbaren Folgen."

        self.run(lambda: feeds.playlist(show), done, "Feed laden")

    @Slot(str)
    def openFeed(self, url):
        self.openShow(dict(url=url.strip(), title="Podcast", author=""))

    @Slot()
    def toggleFollow(self):
        url = self.show["url"]
        if url in self.subscriptions:
            self.subscriptions.pop(url)
        else:
            self.subscriptions[url] = self.show
        self.save("subscriptions", self.subscriptions)
        self.followingChanged.emit()
        self.changed.emit()

    @Slot("QVariantMap")
    def download(self, episode):
        key = episode["key"]
        if key in self.downloads or key in self.pending:
            return
        self.pending.add(key)
        self.changed.emit()

        def done(result):
            self.pending.remove(key)
            if result is not None:
                self.downloads[key] = result
                self.save("downloads", self.downloads)
                self.message = "Folge heruntergeladen."
                self.offlineChanged.emit()

        self.run(lambda: feeds.download(episode, self.directory), done, "Download")

    @Slot(str)
    def removeDownload(self, key):
        try:
            Path(self.downloads[key]["file"]).unlink(missing_ok=True)
        except OSError as exc:
            self.message = f"Download konnte nicht gelöscht werden: {exc}"
        else:
            self.downloads.pop(key)
            self.save("downloads", self.downloads)
            self.message = "Download gelöscht."
            self.offlineChanged.emit()
        self.changed.emit()

    @Slot("QVariantMap", result=QUrl)
    def playbackUrl(self, episode):
        saved = self.downloads.get(episode["key"])
        if saved and Path(saved["file"]).is_file():
            return QUrl.fromLocalFile(saved["file"])
        return QUrl(episode["url"])


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("Creative OS")
    app.setApplicationName("Creative Podcast")
    app.setDesktopFileName("creative-podcast")
    app.setWindowIcon(QIcon.fromTheme("creative-podcast"))

    data = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    data.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        return 1
    downloads = data / "episodes"
    for partial in downloads.glob("*.part"):
        partial.unlink(missing_ok=True)
    podcasts = Podcasts(downloads)
    engine = QQmlApplicationEngine()
    for location in (
        HERE.parent.parent / "shell/creative_shell/qml",
        Path("/usr/lib/creative-shell/creative_shell/qml"),
    ):
        if (location / "Creative/qmldir").is_file():
            engine.addImportPath(str(location))
            break
    engine.setInitialProperties({"podcasts": podcasts})
    engine.load(QUrl.fromLocalFile(str(HERE / "qml/Main.qml")))
    if not engine.rootObjects():
        return 1
    if "--selftest" in sys.argv:
        QTimer.singleShot(200, app.quit)
    result = app.exec()
    del engine
    return result


if __name__ == "__main__":
    sys.exit(main())
