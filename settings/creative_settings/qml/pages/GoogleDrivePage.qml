import QtQuick
import Creative
import ".."

SettingsPage {
    PageHeader {
        title: "Google Drive"
        subtitle: "Dateien aus deinem Google-Konto als Laufwerk einbinden."
    }

    Text {
        width: parent.width
        wrapMode: Text.WordWrap
        color: Theme.text
        text: googleDrive.mounted ? "Eingebunden" : googleDrive.connected ? "Konto verbunden, Laufwerk ausgehängt" : "Kein Konto verbunden"
    }

    Row {
        spacing: 8
        CButton {
            text: googleDrive.connected ? "Einbinden" : "Mit Google anmelden"
            enabled: !googleDrive.busy && !googleDrive.mounted
            onClicked: googleDrive.connectDrive()
        }
        CButton {
            text: "Abbrechen"
            visible: googleDrive.busy && !googleDrive.connected
            onClicked: googleDrive.cancel()
        }
        CButton {
            text: "Aushängen"
            enabled: !googleDrive.busy && googleDrive.mounted
            onClicked: googleDrive.unmountDrive()
        }
        CButton {
            text: "Drive im Browser"
            onClicked: Qt.openUrlExternally("https://drive.google.com/")
        }
    }

    Text {
        width: parent.width
        wrapMode: Text.WordWrap
        color: Theme.textMuted
        text: googleDrive.message
    }

    Text {
        width: parent.width
        wrapMode: Text.WordWrap
        color: Theme.textMuted
        text: "Kopiere Dateien in das Laufwerk oder heraus. Speichere bearbeitete Dateien direkt dort. Uploads können nach dem Speichern noch im Hintergrund laufen. Google Docs, Tabellen und Präsentationen bearbeitest du im Browser."
    }
}
