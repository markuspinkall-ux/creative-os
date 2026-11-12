"""Creative Widgets desktop settings and curated widget downloads."""

import json
import sys
import threading

from PySide6.QtCore import QSignalBlocker, QTimer, Qt, Signal
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from .dbus_service import PATH, SERVICE
from .widget_extras import CLOCK_URL, clock_descriptor, read_small

try:  # Design (Graphit/Porzellan) und Akzentfarbe von Creative OS
    from creative_look import install as _look_install, themed as T
    _look_install()
except ImportError:
    def T(value):
        return value



class WidgetWindow(QMainWindow):
    downloaded = Signal(str, str)

    def __init__(self, check=False):
        super().__init__()
        self.setWindowTitle("Creative Widgets")
        self.resize(640, 660)
        self.bus = QDBusInterface(SERVICE, PATH, SERVICE, QDBusConnection.sessionBus())
        self.bus.setTimeout(1200)
        self.loading = False
        self.installed = False
        self.available = False
        self.last_channels = None
        self.switches = {}
        self.monitors = {}
        self.monitor_options = {}
        self.downloaded.connect(self.finish_download)
        page = QWidget()
        self.setCentralWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        title = QLabel("Creative Widgets")
        title.setFont(QFont("Sans Serif", 22, QFont.Weight.DemiBold))
        layout.addWidget(title)
        layout.addWidget(QLabel("Desktop-Widgets verwalten und neue Widgets hinzufügen."))

        desktop = self.section(layout, "Auf dem Desktop")
        for name, label in (
            ("shelf", "Ablage"), ("stats", "Leistungsanzeige"), ("rss", "RSS-Nachrichten"),
            ("weather", "Wetter"), ("clock", "Analoge Uhr"), ("twitch", "Twitch-Favoriten"),
            ("ki", "KI-Helfer (lokale KI, Open Source)"),
        ):
            switch = QCheckBox(label)
            switch.toggled.connect(lambda enabled, key=name: self.set_enabled(key, enabled))
            row = QHBoxLayout()
            row.addWidget(switch, 1)
            monitor = QComboBox()
            monitor.setAccessibleName(f"Zielmonitor für {label}")
            monitor.setMinimumWidth(190)
            monitor.activated.connect(lambda index, key=name, combo=monitor:
                                      self.apply("setWidgetMonitor", key, combo.itemData(index)))
            row.addWidget(monitor)
            desktop.addLayout(row)
            self.switches[name] = switch
            self.monitors[name] = monitor

        twitch = self.section(layout, "Twitch-Favoriten")
        twitch.addWidget(QLabel("Bis zu acht Benutzernamen oder Kanal-Links, je einer pro Zeile."))
        self.channels = QPlainTextEdit()
        self.channels.setPlaceholderText("riotgames\nhttps://www.twitch.tv/monstercat")
        self.channels.setFixedHeight(76)
        self.channels.setAccessibleName("Twitch-Kanäle")
        twitch.addWidget(self.channels)
        note = QLabel("Für den Live-Status fragt das Widget die Kanalnamen bei DecAPI ab.")
        note.setWordWrap(True)
        twitch.addWidget(note)
        self.save_button = QPushButton("Kanäle speichern")
        self.save_button.clicked.connect(self.save_channels)
        twitch.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignRight)

        catalog = self.section(layout, "Widget-Katalog")
        row = QHBoxLayout()
        detail = QVBoxLayout()
        detail.addWidget(QLabel("Analoge Uhr"))
        detail.addWidget(QLabel("Uhr mit Stunden-, Minuten- und Sekundenzeiger"))
        row.addLayout(detail, 1)
        self.download_button = QPushButton("Herunterladen")
        self.download_button.clicked.connect(self.download_clock)
        row.addWidget(self.download_button)
        catalog.addLayout(row)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        if not check:
            self.refresh()
            timer = QTimer(self)
            timer.timeout.connect(self.refresh)
            timer.start(2000)

    def section(self, parent, heading):
        card = QFrame()
        card.setObjectName("widgetCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel(heading)
        title.setFont(QFont("Sans Serif", 12, QFont.Weight.DemiBold))
        layout.addWidget(title)
        parent.addWidget(card)
        return layout

    def call(self, method, *args):
        if not self.bus.isValid():
            self.bus = QDBusInterface(SERVICE, PATH, SERVICE, QDBusConnection.sessionBus())
            self.bus.setTimeout(1200)
        reply = self.bus.call(method, *args)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage or not reply.arguments():
            raise ValueError("Die Creative-Shell ist gerade nicht erreichbar.")
        return reply.arguments()[0]

    def refresh(self):
        try:
            state = json.loads(self.call("widgetState"))
        except ValueError as exc:
            if self.available or not self.message.text():
                self.message.setText(str(exc))
            self.available = False
            state = {}
        else:
            if not self.available:
                self.message.clear()
            self.available = True
        self.installed = state.get("clockInstalled", False)
        for name, switch in self.switches.items():
            enabled = self.available and (name != "clock" or self.installed)
            switch.setEnabled(enabled)
            monitor = self.monitors[name]
            monitor.setEnabled(enabled)
            if self.available:
                with QSignalBlocker(switch):
                    switch.setChecked(state.get(name, False))
                self.update_monitors(name, state["screens"], state["targets"].get(name, ""))
        if self.available:
            channels = "\n".join(state["channels"])
            current = self.channels.toPlainText()
            if current != channels and (self.last_channels is None or current == self.last_channels):
                self.channels.setPlainText(channels)
            self.last_channels = channels
        self.save_button.setEnabled(self.available)
        self.update_download_button()

    def update_monitors(self, name, screens, target):
        monitor = self.monitors[name]
        options = (("Hauptmonitor (automatisch)", ""),) + tuple((screen, screen) for screen in screens)
        if target and target not in screens:
            options += ((f"{target} (getrennt)", target),)
        with QSignalBlocker(monitor):
            if self.monitor_options.get(name) != options:
                monitor.clear()
                for label, screen in options:
                    monitor.addItem(label, screen)
                self.monitor_options[name] = options
            monitor.setCurrentIndex(monitor.findData(target))

    def set_enabled(self, name, enabled):
        self.apply("setWidgetEnabled", name, enabled)

    def save_channels(self):
        if self.apply("setTwitchChannels", self.channels.toPlainText()):
            self.last_channels = None
            self.refresh()
            self.message.setText("Twitch-Kanäle gespeichert.")

    def apply(self, method, *args):
        try:
            error = self.call(method, *args)
        except ValueError as exc:
            error = str(exc)
        self.refresh()
        if error:
            self.message.setText(error)
        return not error

    def update_download_button(self):
        self.download_button.setEnabled(self.available and not self.loading and not self.installed)
        self.download_button.setText("Installiert" if self.installed else "Lädt …" if self.loading else "Herunterladen")

    def download_clock(self):
        self.loading = True
        self.update_download_button()

        def work():
            try:
                raw = read_small(CLOCK_URL)
                clock_descriptor(raw)
            except (OSError, ValueError) as exc:
                self.downloaded.emit("", str(exc))
            else:
                self.downloaded.emit(raw, "")

        threading.Thread(target=work, daemon=True).start()

    def finish_download(self, raw, error):
        self.loading = False
        self.update_download_button()
        if error:
            self.message.setText("Download fehlgeschlagen. " + error)
        elif self.apply("installClockWidget", raw):
            self.message.setText("Die analoge Uhr wurde installiert und auf dem Desktop aktiviert.")


def main():
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Creative Widgets")
    app.setDesktopFileName("creative-widgets")
    app.setWindowIcon(QIcon.fromTheme("creative-widgets"))
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in {
        QPalette.ColorRole.Window: T("#161922"), QPalette.ColorRole.WindowText: T("#dce6ff"),
        QPalette.ColorRole.Base: T("#131722"), QPalette.ColorRole.Text: T("#dce6ff"),
        QPalette.ColorRole.Button: T("#293246"), QPalette.ColorRole.ButtonText: T("#dce6ff"),
        QPalette.ColorRole.Highlight: T("#84a9f7"), QPalette.ColorRole.HighlightedText: T("#111827"),
    }.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet("QFrame#widgetCard { background: #202634; border-radius: 12px; }")
    check = "--selftest" in sys.argv[1:]
    window = WidgetWindow(check)
    window.show()
    if check:
        app.processEvents()
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
