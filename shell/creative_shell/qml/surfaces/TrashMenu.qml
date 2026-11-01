import QtQuick
import Creative

// Rechtsklick-Menü des Papierkorbs im Tray: öffnen oder leeren (mit Rückfrage).
Item {
    id: root

    property string screenName
    property bool confirm: false

    function opened() {
        confirm = false
        trash.refresh()
        root.forceActiveFocus()
    }

    focus: true
    Keys.onEscapePressed: confirm ? (confirm = false) : shell.closePopups()

    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }

    Rectangle {
        id: card
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        width: 270
        height: col.implicitHeight + 16
        radius: 14
        color: Theme.raised
        border.color: Theme.hairline
        border.width: 1

        MouseArea { anchors.fill: parent }

        Column {
            id: col
            x: 8
            y: 8
            width: parent.width - 16
            spacing: 2

            // Kopf
            Item {
                width: parent.width
                height: 50
                SvgIcon {
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    name: trash.full ? "trash-full" : "trash"
                    size: 22
                }
                Column {
                    x: 44
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Text {
                        text: "Papierkorb"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        font.bold: true
                    }
                    Text {
                        text: trash.count === 0 ? "Leer"
                              : (trash.count === 1 ? "1 Element" : trash.count + " Elemente")
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                    }
                }
            }
            Divider { width: parent.width }

            // Normale Einträge
            MenuRow {
                visible: !root.confirm
                icon: "files"
                label: "Papierkorb öffnen"
                onActivated: { shell.closePopups(); trash.open() }
            }
            MenuRow {
                visible: !root.confirm
                icon: "trash"
                label: "Papierkorb leeren"
                enabled: trash.full
                onActivated: root.confirm = true
            }

            // Rückfrage – endgültiges Löschen nie aus Versehen
            Column {
                visible: root.confirm
                width: parent.width
                spacing: 10
                topPadding: 8
                bottomPadding: 4
                Text {
                    x: 10
                    width: parent.width - 20
                    wrapMode: Text.WordWrap
                    text: (trash.count === 1 ? "Das Element wird" : "Alle " + trash.count + " Elemente werden")
                          + " endgültig gelöscht. Das kann nicht rückgängig gemacht werden."
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    lineHeight: 1.25
                }
                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    spacing: 8
                    CButton { text: "Abbrechen"; onClicked: root.confirm = false }
                    CButton {
                        text: "Endgültig löschen"
                        primary: true
                        onClicked: { trash.empty(); shell.closePopups() }
                    }
                }
            }
        }
    }

    component MenuRow: Rectangle {
        id: row
        property string icon
        property string label
        signal activated()
        width: parent ? parent.width : 250
        height: 40
        radius: 9
        opacity: enabled ? 1 : 0.4
        color: rowMouse.containsMouse && enabled ? Theme.hover : "transparent"
        SvgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: row.icon; size: 16 }
        Text {
            x: 42
            anchors.verticalCenter: parent.verticalCenter
            text: row.label
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
        MouseArea {
            id: rowMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: row.enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: row.activated()
        }
        Accessible.role: Accessible.MenuItem
        Accessible.name: label
        Accessible.onPressAction: if (enabled) row.activated()
    }
}
