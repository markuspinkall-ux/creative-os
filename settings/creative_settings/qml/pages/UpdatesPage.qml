import QtQuick
import Creative
import ".."

SettingsPage {
    readonly property var u: system.updates

    PageHeader {
        title: "Software & Updates"
        subtitle: u.version ? "Creative OS " + u.version : ""
    }

    Card {
        Item {
            width: parent.width
            height: 76
            Rectangle {
                width: 52; height: 52; radius: 14
                anchors.verticalCenter: parent.verticalCenter
                color: u.state === "reboot" || u.state === "available" ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                       : (u.state === "error" ? Qt.rgba(1, 0.69, 0.48, 0.15) : Qt.rgba(0.43, 0.86, 0.75, 0.15))
                SvgIcon { anchors.centerIn: parent; name: u.state === "available" ? "download" : (u.state === "reboot" ? "power" : "refresh"); size: 24 }
            }
            Column {
                x: 70
                width: parent.width - 70 - buttons.width - 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: u.state === "reboot" ? "Neustart erforderlich" : (u.state === "available" ? "Update verfügbar"
                          : (u.state === "current" ? "Alles aktuell" : (u.state === "classic" ? "Updates" : "Updates")))
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 16
                    font.bold: true
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: u.text
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
            Row {
                id: buttons
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                CButton { visible: u.state === "reboot"; text: "Jetzt neu starten"; primary: true; onClicked: system.reboot() }
                CButton { visible: u.state === "available"; text: "Herunterladen"; primary: true; enabled: !u.busy; onClicked: system.downloadUpdate() }
                CButton {
                    visible: u.state !== "reboot" && u.state !== "available"
                    text: u.state === "classic" ? "Software öffnen" : (u.busy ? "Suche …" : "Nach Updates suchen")
                    enabled: !u.busy
                    primary: u.state === "classic"
                    onClicked: system.checkUpdates()
                }
            }
        }
    }

    Card {
        title: "So funktionieren Updates"
        SettingRow { label: "Automatisch im Hintergrund"; hint: "Creative OS lädt Updates selbst herunter, während du arbeitest."; Item { width: 1; height: 1 } }
        SettingRow { label: "Aktiv nach dem nächsten Neustart"; hint: "Nichts ändert sich mitten in der Arbeit."; Item { width: 1; height: 1 } }
        SettingRow { label: "Immer ein Weg zurück"; hint: "Läuft nach einem Update etwas nicht, im Startmenü beim Einschalten einfach den vorherigen Eintrag wählen."; Item { width: 1; height: 1 } }
        SettingRow {
            label: "Apps aktualisieren"
            hint: "Apps aus „Software“ (Flathub) werden dort aktualisiert."
            last: true
            CButton { text: "Software öffnen"; onClicked: system.openSoftware() }
        }
    }
}
