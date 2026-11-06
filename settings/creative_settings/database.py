"""Local MariaDB workspace using the current user's Unix-socket identity."""

import os
import pwd
import sys

import pymysql
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


def identifier(value):
    return "`" + value.replace("`", "``") + "`"


class DatabaseWindow(QMainWindow):
    def __init__(self, connection, user):
        super().__init__()
        self.db = connection
        self.setWindowTitle("MariaDB-Verwaltung")
        self.resize(1000, 680)
        content = QWidget()
        self.setCentralWidget(content)
        layout = QVBoxLayout(content)
        layout.addWidget(QLabel(f"Angemeldet als {user} · Eigene Datenbanken: creative_{os.getuid()}_…"))
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        self.databases = QComboBox()
        self.tables = QComboBox()
        toolbar.addWidget(self.databases, 1)
        toolbar.addWidget(self.tables, 1)
        for title, action in [("Aktualisieren", self.refresh), ("Tabelle anzeigen", self.show_table)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            toolbar.addWidget(button)
        self.sql = QPlainTextEdit()
        self.sql.setPlaceholderText("SQL-Abfrage eingeben, z. B. SELECT, CREATE TABLE oder UPDATE")
        layout.addWidget(self.sql, 1)
        run = QPushButton("SQL ausführen")
        run.clicked.connect(self.execute_sql)
        layout.addWidget(run)
        self.results = QTableWidget()
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results, 2)
        self.databases.currentTextChanged.connect(self.refresh_tables)
        self.refresh()

    def refresh(self):
        try:
            with self.db.cursor() as cur:
                cur.execute("SHOW DATABASES")
                names = [row[0] for row in cur.fetchall()]
            selected = self.databases.currentText()
            self.databases.blockSignals(True)
            self.databases.clear()
            self.databases.addItems(names)
            if selected in names:
                self.databases.setCurrentText(selected)
            self.databases.blockSignals(False)
            self.refresh_tables()
        except pymysql.MySQLError as exc:
            self.statusBar().showMessage(str(exc))

    def refresh_tables(self):
        self.tables.clear()
        database = self.databases.currentText()
        if database:
            try:
                with self.db.cursor() as cur:
                    cur.execute("SHOW TABLES FROM " + identifier(database))
                    self.tables.addItems([row[0] for row in cur.fetchall()])
            except pymysql.MySQLError as exc:
                self.statusBar().showMessage(str(exc))

    def show_table(self):
        database, table = self.databases.currentText(), self.tables.currentText()
        if database and table:
            self.query(f"SELECT * FROM {identifier(database)}.{identifier(table)} LIMIT 500")

    def execute_sql(self):
        statement = self.sql.toPlainText().strip()
        if not statement:
            return
        if QMessageBox.question(self, "SQL ausführen", "Diese Anweisung kann Daten ändern. Ausführen?") == QMessageBox.StandardButton.Yes:
            self.query(statement)
            self.refresh()

    def query(self, statement):
        try:
            database = self.databases.currentText()
            if database:
                self.db.select_db(database)
            with self.db.cursor(pymysql.cursors.SSCursor) as cur:
                cur.execute(statement)
                columns = [field[0] for field in cur.description or ()]
                rows = cur.fetchmany(501) if columns else []
                message = ("Anzeige auf 500 Zeilen begrenzt." if len(rows) > 500 else
                           f"{len(rows)} Zeilen." if columns else f"Betroffene Zeilen: {cur.rowcount}")
            self.results.clear()
            self.results.setColumnCount(len(columns))
            self.results.setHorizontalHeaderLabels(columns)
            self.results.setRowCount(min(500, len(rows)))
            for i, row in enumerate(rows[:500]):
                for j, value in enumerate(row):
                    self.results.setItem(i, j, QTableWidgetItem("NULL" if value is None else str(value)))
            self.statusBar().showMessage(message)
        except pymysql.MySQLError as exc:
            QMessageBox.warning(self, "SQL-Fehler", str(exc))


def main():
    app = QApplication(sys.argv)
    user = pwd.getpwuid(os.getuid()).pw_name
    try:
        connection = pymysql.connect(user=user, unix_socket="/var/lib/mysql/mysql.sock",
                                     autocommit=True, connect_timeout=3, read_timeout=10)
    except pymysql.MySQLError as exc:
        QMessageBox.warning(None, "MariaDB", "Bitte zuerst unter Mein Server auf „MariaDB starten“ klicken.\n\n" + str(exc))
        return 1
    with connection:
        window = DatabaseWindow(connection, user)
        window.show()
        return app.exec()


if __name__ == "__main__":
    sys.exit(main())
