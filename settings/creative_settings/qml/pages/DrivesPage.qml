import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root
    property var setupDisk: null       // Platte, die gerade eingerichtet werden soll

    PageHeader {
        title: "Laufwerke"
        subtitle: "Festplatten, SSDs und M2 – Zustand, einrichten, beim Start verbinden"
        CButton { text: "Aktualisieren"; onClicked: drives.refresh() }
        CButton { visible: drives.expertAvailable; text: "Erweitert …"; onClicked: drives.openExpert() }
    }

    Message { text: drives.message; warning: drives.message.indexOf("nicht") >= 0 || drives.message.indexOf("benutzt") >= 0 }

    Repeater {
        model: drives.disks
        delegate: Card {
            id: dcard
            readonly property var d: modelData
            title: d.kind + " · " + d.size
            subtitle: (d.model ? d.model + " · " : "") + (d.system ? "Hier läuft Creative OS – geschützt" : (d.removable ? "Wechseldatenträger" : d.device))

            // Zustand
            SettingRow {
                visible: !d.removable
                label: "Zustand"
                hint: d.health === "unknown" ? "Diese Platte meldet keinen Zustand (z. B. in einer VM)." : ""
                last: d.system || (d.empty && false)
                Row {
                    spacing: 8
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10; height: 10; radius: 5
                        color: d.health === "ok" ? Theme.ok : (d.health === "warn" ? Theme.flame : (d.health === "bad" ? "#e5484d" : Theme.textMuted))
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: d.healthText || "Keine Angabe"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: d.health === "bad" || d.health === "warn"
                    }
                }
            }

            // Leere Platte → einrichten
            SettingRow {
                visible: d.empty && !d.system
                label: "Noch nicht eingerichtet"
                hint: "Neue Platte? Mit einem Klick einrichten – danach erscheint sie in „Dateien › Dieser PC“."
                last: true
                CButton { text: "Einrichten …"; primary: true; enabled: !drives.busy; onClicked: { root.setupDisk = d; nameField.text = d.kind === "M2" ? "M2" : (d.kind === "SSD" ? "SSD" : "Daten"); confirm.checked = false; windowsBox.checked = false; setupDialog.open() } }
            }

            // Partitionen
            Repeater {
                model: d.parts
                delegate: Column {
                    width: parent.width
                    SettingRow {
                        label: (modelData.label || "Ohne Namen") + "  ·  " + modelData.fstype
                        hint: modelData.mount ? modelData.usage + "  ·  " + modelData.mount : "Nicht verbunden"
                        CButton { visible: modelData.mount !== ""; text: "Öffnen"; onClicked: drives.openFolder(modelData.mount) }
                    }
                    SettingRow {
                        label: "Beim Start verbinden"
                        hint: "Fester Ort schon vor der Anmeldung – gut für Spiele-Bibliotheken"
                        CSwitch {
                            checked: modelData.automount
                            enabled: !drives.busy
                            label: "Beim Start verbinden"
                            onToggled: (v) => drives.setAutomount(modelData.device, v)
                        }
                    }
                }
            }

            // Bereits eingerichtete Platte trotzdem neu einrichten
            SettingRow {
                visible: !d.system && !d.empty && !d.removable
                label: "Neu einrichten"
                hint: "Löscht alles auf dieser Platte und richtet sie neu ein."
                last: true
                CButton { text: "Neu einrichten …"; enabled: !drives.busy; onClicked: { root.setupDisk = d; nameField.text = (d.parts[0] && d.parts[0].label) || "Daten"; confirm.checked = false; windowsBox.checked = false; setupDialog.open() } }
            }
        }
    }

    // ---- Rückfrage beim Einrichten -------------------------------------------------------
    Popup {
        id: setupDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 460
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }

        contentItem: Column {
            spacing: 14
            Text {
                text: root.setupDisk ? root.setupDisk.kind + " · " + root.setupDisk.size + " einrichten" : ""
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true
            }
            Rectangle {
                width: parent.width
                height: warnText.implicitHeight + 20
                radius: 10
                color: Qt.rgba(0.9, 0.28, 0.3, 0.14)
                Text {
                    id: warnText
                    x: 12; width: parent.width - 24
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: "Achtung: Alles, was auf dieser Platte" + (root.setupDisk && root.setupDisk.model ? " (" + root.setupDisk.model + ")" : "") + " liegt, wird gelöscht."
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
                }
            }
            Text { text: "Name"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
            TextField {
                id: nameField
                width: parent.width
                height: 38
                maximumLength: 16
                leftPadding: 12
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                background: Rectangle { radius: 10; color: Theme.ground; border.color: nameField.activeFocus ? Theme.accent : Theme.hairline }
            }
            Row {
                spacing: 10
                CSwitch { id: windowsBox; checked: false; label: "Auch unter Windows lesbar"; onToggled: (v) => checked = v }
                Column {
                    Text { text: "Auch unter Windows lesbar (exFAT)"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                    Text { text: "Für Spiele unter Creative OS besser ausgeschaltet lassen"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
            }
            Row {
                spacing: 10
                CSwitch { id: confirm; checked: false; label: "Löschen bestätigen"; onToggled: (v) => checked = v }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Ja, alle Daten darauf dürfen gelöscht werden"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: setupDialog.close() }
                CButton {
                    text: "Einrichten"
                    primary: true
                    enabled: confirm.checked && nameField.text.trim().length > 0
                    onClicked: { setupDialog.close(); drives.setup(root.setupDisk.device, nameField.text, windowsBox.checked) }
                }
            }
        }
    }

    Component.onCompleted: drives.refresh()
}
