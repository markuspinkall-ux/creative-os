"""Startpunkt: `creative-notes [Datei …]`.

Läuft Creative Notes schon, öffnen weitere Aufrufe ihre Dateien als neue
Reiter im vorhandenen Fenster (wie bei Notepad++).
"""

import json
import os
import signal
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QByteArray, QLibraryInfo, QLocale, QTimer, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .style import stylesheet

SERVER = f"creative-notes-{os.getuid()}"


def _args(argv):
    files, line = [], None
    for a in argv:
        if a.startswith("+") and a[1:].isdigit():
            line = int(a[1:])
        elif not a.startswith("-"):
            if a.startswith("file://"):
                from urllib.parse import unquote, urlparse
                a = unquote(urlparse(a).path)
            files.append(os.path.abspath(a))
    return files, line


def _hand_over(files):
    """An ein laufendes Fenster übergeben. True = erledigt."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(QByteArray(json.dumps({"files": files}).encode()))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


def selftest():
    """Kurzer Funktionstest ohne Bildschirm (wird beim Bauen des Abbilds ausgeführt)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    tmp = tempfile.mkdtemp(prefix="notes-test-")
    os.environ["XDG_CONFIG_HOME"] = tmp
    os.environ["XDG_DATA_HOME"] = tmp
    app = QApplication(sys.argv[:1])
    app.setStyleSheet(stylesheet())
    from .window import NotesWindow
    w = NotesWindow()
    d = w.new_doc("def f(x):\n    return x  # Kommentar\n")
    ed = d.editor
    ed.set_language("python")
    ed.selectAll()
    ed.toggle_comment()
    assert ed.toPlainText().startswith("# def f"), ed.toPlainText()
    ed.toggle_comment()
    assert ed.toPlainText().startswith("def f"), ed.toPlainText()
    ed.duplicate_line()
    w.findbar.find.setText("return")
    w.findbar.replace.setText("yield")
    w.findbar.show()
    w.findbar.replace_all()
    assert "yield x" in ed.toPlainText() and "return" not in ed.toPlainText(), ed.toPlainText()
    path = os.path.join(tmp, "probe.txt")
    d.encoding, d.eol = "utf-8", "crlf"
    d.path = path
    assert w.save(d)
    assert Path(path).read_bytes().count(b"\r\n") >= 2
    w.close_tab(w.tabs.indexOf(ed))
    d2 = w.open_file(path)
    assert d2 and d2.eol == "crlf" and "yield" in d2.editor.toPlainText()
    w.save_session()
    w2 = NotesWindow()
    assert w2.restore_session()
    w.show()
    app.processEvents()
    print("Creative Notes: Selbsttest bestanden")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    files, line = _args(sys.argv[1:])

    app = QApplication(sys.argv)
    app.setApplicationName("Creative Notes")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-notes")
    app.setWindowIcon(QIcon.fromTheme("creative-notes"))
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    # Knöpfe in Dialogen auf Deutsch („Speichern“, „Verwerfen“, „Abbrechen“)
    tr = QTranslator(app)
    if tr.load(QLocale("de_DE"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(tr)

    if "--new-window" not in sys.argv and _hand_over(files):
        return 0

    from .window import NotesWindow
    win = NotesWindow()
    restored = win.restore_session()
    if files:
        d = win.open_paths(files)
        if d and line:
            block = d.editor.document().findBlockByNumber(line - 1)
            c = d.editor.textCursor()
            c.setPosition(block.position())
            d.editor.setTextCursor(c)
            QTimer.singleShot(0, d.editor.centerCursor)
    if win.tabs.count() == 0:
        win.new_doc()
    elif not restored and not files:
        win.new_doc()
    win.show()

    server = QLocalServer()
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def incoming():
        sock = server.nextPendingConnection()
        if sock is None:
            return

        def read():
            try:
                msg = json.loads(bytes(sock.readAll()).decode() or "{}")
            except ValueError:
                return
            if msg.get("files"):
                win.open_paths(msg["files"])
            win.showNormal() if win.isMinimized() else None
            win.raise_()
            win.activateWindow()
        sock.readyRead.connect(read)
        sock.disconnected.connect(sock.deleteLater)
    server.newConnection.connect(incoming)

    signal.signal(signal.SIGINT, lambda *_: win.close())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    rc = app.exec()
    server.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
