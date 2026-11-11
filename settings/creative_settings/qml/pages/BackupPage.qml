import QtQuick
import Creative
import ".."

SettingsPage {
    id: root

    PageHeader {
        title: "Datensicherung"
        subtitle: "Deine Dateien auf eine externe Platte sichern – nichts geht verloren"
    }

    // ---- Status und Knopf -----------------------------------------------------------------
    Card {
        Item {
            width: parent.width
            height: 76
            Rectangle {
                width: 52; height: 52; radius: 14
                anchors.verticalCenter: parent.verticalCenter
                color: backup.target ? Qt.rgba(0.43, 0.86, 0.75, 0.15) : Theme.tint(0.06)
                SvgIcon { anchors.centerIn: parent; name: "save"; size: 24 }
            }
            Column {
                x: 70
                width: parent.width - 70 - btns.width - 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Text {
                    width: parent.width
                    text: backup.running ? "Sicherung läuft …" : (backup.target ? "Bereit zum Sichern" : (backup.targetLabel ? "Laufwerk „" + backup.targetLabel + "“ einstecken" : "Noch kein Ziel gewählt"))
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: backup.running ? backup.text : (backup.text && backup.text.indexOf("Sicher") === 0 ? backup.text + " · " + backup.lastText : backup.lastText)
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
                }
            }
            Row {
                id: btns
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                CButton { visible: backup.target !== "" && !backup.running; text: "Gesicherte Dateien"; onClicked: backup.openBackup() }
                CButton { visible: backup.running; text: "Abbrechen"; onClicked: backup.stop() }
                CButton { visible: !backup.running; text: "Jetzt sichern"; primary: true; enabled: backup.target !== ""; onClicked: backup.start() }
            }
        }
        Column {
            visible: backup.running
            width: parent.width
            topPadding: 6
            bottomPadding: 12
            Rectangle {
                width: parent.width
                height: 8
                radius: 4
                color: Theme.tint(0.08)
                Rectangle {
                    width: parent.width * Math.max(0.02, backup.percent / 100)
                    height: parent.height
                    radius: 4
                    color: Theme.accent
                    Behavior on width { NumberAnimation { duration: 400 } }
                }
            }
        }
    }

    // ---- Ziel ------------------------------------------------------------------------------
    Card {
        title: "Wohin sichern?"
        subtitle: "Externe Festplatte, USB-Stick oder eine zweite Platte im PC"
        Repeater {
            model: backup.drives
            delegate: SettingRow {
                required property var modelData
                required property int index
                label: modelData.label
                hint: modelData.text
                last: index === backup.drives.length - 1
                CButton {
                    text: backup.target === modelData.path ? "Ausgewählt" : "Als Ziel wählen"
                    primary: backup.target === modelData.path
                    enabled: backup.target !== modelData.path && !backup.running
                    onClicked: backup.setTarget(modelData.path)
                }
            }
        }
        SettingRow {
            visible: backup.drives.length === 0
            label: "Kein passendes Laufwerk gefunden"
            hint: "Externe Platte einstecken – oder unter „Laufwerke“ eine zweite Platte einrichten."
            last: true
            Item { width: 1; height: 1 }
        }
    }

    // ---- Automatisch ------------------------------------------------------------------------
    Card {
        title: "Automatisch sichern"
        SettingRow {
            label: "Einmal am Tag sichern"
            hint: "Sobald das Ziel-Laufwerk angeschlossen ist und die letzte Sicherung länger als einen Tag her ist. Du bekommst eine Meldung."
            last: true
            CSwitch {
                checked: backup.auto
                label: "Automatisch sichern"
                onToggled: (v) => backup.setAuto(v)
            }
        }
    }

    Card {
        title: "So funktioniert die Sicherung"
        SettingRow { label: "Was gesichert wird"; hint: "Dein ganzer Benutzerordner: Dokumente, Bilder, Musik, Videos, Schreibtisch, Downloads und Einstellungen."; Item { width: 1; height: 1 } }
        SettingRow { label: "Was ausgelassen wird"; hint: "Zwischenspeicher, Papierkorb und Steam-Spiele (die lassen sich jederzeit neu laden)."; Item { width: 1; height: 1 } }
        SettingRow { label: "Nichts geht verloren"; hint: "Was du löschst oder änderst, landet bei der nächsten Sicherung im Ordner „Ältere Versionen“ auf dem Laufwerk."; last: true; Item { width: 1; height: 1 } }
    }
}
