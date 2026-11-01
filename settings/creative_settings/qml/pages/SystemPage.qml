import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root
    property bool renaming: false

    PageHeader {
        title: "System"
        subtitle: system.info.os
    }

    Message { text: system.message }

    Card {
        title: "Gerätename"
        SettingRow {
            label: system.hostName
            hint: "So heißt der PC im Netzwerk"
            last: !root.renaming
            CButton { text: "Umbenennen"; visible: !root.renaming; onClicked: { root.renaming = true; nameField.text = system.hostName; nameField.forceActiveFocus(); nameField.selectAll() } }
        }
        Column {
            visible: root.renaming
            width: parent.width
            spacing: 8
            bottomPadding: 6
            Row {
                spacing: 8
                TextField {
                    id: nameField
                    width: 260
                    height: 36
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    leftPadding: 12
                    background: Rectangle { radius: 10; color: Theme.ground; border.color: nameField.activeFocus ? Theme.accent : Theme.hairline }
                    onAccepted: saveBtn.clicked()
                }
                CButton {
                    id: saveBtn
                    text: "Speichern"
                    primary: true
                    onClicked: {
                        const err = system.rename(nameField.text)
                        nameError.text = err
                        if (!err) root.renaming = false
                    }
                }
                CButton { text: "Abbrechen"; onClicked: { root.renaming = false; nameError.text = "" } }
            }
            Text { id: nameError; visible: text.length > 0; color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
    }

    Card {
        title: "Gerät"
        SettingRow { label: "Prozessor"; Text { text: system.info.cpu; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow { label: "Arbeitsspeicher"; Text { text: system.info.ram; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow {
            label: "Grafik"
            Text { text: system.info.gpu; width: Math.min(implicitWidth, 520); elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
        }
        SettingRow { label: "Systemlaufwerk"; Text { text: system.info.disk; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow { label: "System"; Text { text: system.info.os; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow { label: "Kernel"; last: true; Text { text: system.info.kernel; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 } }
    }
}
