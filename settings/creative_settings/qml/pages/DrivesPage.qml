import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root
    property var setupDisk: null       // Platte, die gerade eingerichtet werden soll
    property string setupFs: "ext4"
    property var renamePart: null

    PageHeader {
        title: "Laufwerke"
        subtitle: "Festplatten, SSDs, M2 und USB – Zustand, einrichten, umbenennen, auswerfen"
        CButton { text: "Aktualisieren"; onClicked: drives.refresh() }
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
                CButton { text: "Einrichten …"; primary: true; enabled: !drives.busy; onClicked: { root.setupDisk = d; nameField.text = d.kind === "M2" ? "M2" : (d.kind === "SSD" ? "SSD" : (d.removable ? "USB" : "Daten")); confirm.checked = false; root.setupFs = d.removable ? "exfat" : "ext4"; setupDialog.open() } }
            }

            // Partitionen
            Repeater {
                model: d.parts
                delegate: Column {
                    width: parent.width
                    SettingRow {
                        label: (modelData.label || "Ohne Namen") + "  ·  " + modelData.fstype
                        hint: modelData.mount ? modelData.usage + "  ·  " + modelData.mount : "Nicht verbunden"
                        Row {
                            spacing: 8
                            CButton { visible: modelData.mount !== ""; text: "Öffnen"; onClicked: drives.openFolder(modelData.mount) }
                            CButton {
                                visible: !modelData.automount
                                text: modelData.mount !== "" ? "Trennen" : "Verbinden"
                                enabled: !drives.busy
                                onClicked: modelData.mount !== "" ? drives.unmount(modelData.device) : drives.mount(modelData.device)
                            }
                            CButton {
                                text: "Umbenennen …"
                                enabled: !drives.busy
                                onClicked: { root.renamePart = modelData; renameField.text = modelData.label || ""; renameDialog.open() }
                            }
                        }
                    }
                    SettingRow {
                        visible: !dcard.d.removable
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

            // Bereits eingerichtete Platte trotzdem neu einrichten (formatieren)
            SettingRow {
                visible: !d.system && !d.empty
                label: d.removable ? "Formatieren" : "Neu einrichten"
                hint: "Löscht alles auf " + (d.removable ? "diesem Laufwerk" : "dieser Platte") + " und richtet es neu ein."
                last: !d.removable
                CButton { text: d.removable ? "Formatieren …" : "Neu einrichten …"; enabled: !drives.busy; onClicked: { root.setupDisk = d; nameField.text = (d.parts[0] && d.parts[0].label) || (d.removable ? "USB" : "Daten"); confirm.checked = false; root.setupFs = d.removable ? "exfat" : "ext4"; setupDialog.open() } }
            }

            // USB-Sticks und externe Platten sicher entfernen
            SettingRow {
                visible: d.removable && !d.system
                label: "Sicher entfernen"
                hint: "Trennt das Laufwerk und schaltet es ab – danach kann es abgezogen werden."
                last: true
                CButton { text: "Auswerfen"; primary: true; enabled: !drives.busy; onClicked: drives.eject(d.device) }
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
            Text { text: "Format"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
            Column {
                width: parent.width
                spacing: 6
                Repeater {
                    model: [
                        { k: "ext4", t: "Nur Creative OS (ext4)", h: "Am schnellsten – ideal für Spiele und interne Platten" },
                        { k: "exfat", t: "Überall lesbar (exFAT)", h: "Windows, Mac, Fernseher – ideal für USB-Sticks" },
                        { k: "ntfs", t: "Windows (NTFS)", h: "Für Platten, die oft an Windows-PCs hängen" }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool cur: root.setupFs === modelData.k
                        width: parent.width
                        height: 48
                        radius: 10
                        color: cur ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18) : (fsMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.04))
                        border.color: cur ? Theme.accent : "transparent"
                        Column {
                            x: 12
                            anchors.verticalCenter: parent.verticalCenter
                            Text { text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: parent.parent.cur }
                            Text { text: modelData.h; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                        }
                        MouseArea { id: fsMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.setupFs = modelData.k }
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: modelData.t
                    }
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
                    onClicked: { setupDialog.close(); drives.setup(root.setupDisk.device, nameField.text, root.setupFs) }
                }
            }
        }
    }

    // ---- Umbenennen -------------------------------------------------------------------------
    Popup {
        id: renameDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 400
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Column {
            spacing: 14
            Text { text: "Laufwerk umbenennen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Die Daten darauf bleiben erhalten."
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
            TextField {
                id: renameField
                width: parent.width
                height: 38
                maximumLength: 16
                leftPadding: 12
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                background: Rectangle { radius: 10; color: Theme.ground; border.color: renameField.activeFocus ? Theme.accent : Theme.hairline }
                onAccepted: if (text.trim().length) { renameDialog.close(); drives.rename(root.renamePart.device, text) }
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: renameDialog.close() }
                CButton {
                    text: "Umbenennen"
                    primary: true
                    enabled: renameField.text.trim().length > 0
                    onClicked: { renameDialog.close(); drives.rename(root.renamePart.device, renameField.text) }
                }
            }
        }
    }

    Component.onCompleted: drives.refresh()
}
