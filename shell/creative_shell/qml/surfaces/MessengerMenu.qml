import QtQuick
import QtQuick.Controls.Basic
import Creative

// Messenger im Tray: letzte Chats, Anfragen, Schnellantwort, Nicht stören.
Item {
    id: root
    property string screenName
    focus: true
    Keys.onEscapePressed: shell.closePopups()
    function opened() { root.forceActiveFocus() }
    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }

    readonly property var recent: messenger.contacts.filter((c) => c.status === "accepted").slice(0, 5)
    readonly property var replyTo: recent.find((c) => c.unread > 0) || recent[0] || null

    function openChat(id) { shell.closePopups(); messenger.openWindow(id) }

    component Avatar: Rectangle {
        property string letter
        property string tint: Theme.accent
        property bool online: false
        width: 34; height: 34; radius: 17; color: tint
        Text { anchors.centerIn: parent; text: letter; color: "#12151b"; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
        Rectangle {
            width: 10; height: 10; radius: 5
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: -1
            color: online ? Theme.ok : "#5b6474"; border.width: 2; border.color: Theme.surface
        }
    }

    Rectangle {
        anchors.right: parent.right; anchors.rightMargin: 24
        anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        width: 380; height: Math.min(parent.height - 10, content.implicitHeight + 36)
        radius: Theme.radiusMenu; color: Theme.surface; border.color: Theme.hairline
        MouseArea { anchors.fill: parent }
        Flickable {
            id: flick
            anchors.fill: parent; anchors.margins: 18
            contentHeight: content.implicitHeight; clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            Column {
                id: content
                width: flick.width; spacing: 12

                Item {
                    width: parent.width; height: 40
                    Row {
                        spacing: 10; anchors.verticalCenter: parent.verticalCenter
                        SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "chat"; size: 20 }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Text { text: "Messenger"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
                            Text {
                                text: !messenger.connected ? "Dienst startet …" : (messenger.ready ? messenger.myId : "noch nicht eingerichtet")
                                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                            }
                        }
                    }
                    CButton {
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        text: messenger.ready ? "Öffnen" : "Einrichten"
                        primary: !messenger.ready
                        onClicked: root.openChat("")
                    }
                }

                // Anfragen
                Repeater {
                    model: messenger.requests
                    delegate: Rectangle {
                        required property var modelData
                        width: content.width; height: 92; radius: 12; color: Theme.subtle; border.color: Theme.hairline
                        Column {
                            x: 12; y: 10; width: parent.width - 24; spacing: 8
                            Text { width: parent.width; elide: Text.ElideRight; text: "Anfrage von " + modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                            Text { text: modelData.id; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                            Row {
                                spacing: 8
                                CButton { height: 30; text: "Annehmen"; primary: true; onClicked: messenger.accept(modelData.id) }
                                CButton { height: 30; text: "Ablehnen"; onClicked: messenger.decline(modelData.id) }
                            }
                        }
                    }
                }

                // Letzte Chats
                Repeater {
                    model: root.recent
                    delegate: Rectangle {
                        required property var modelData
                        width: content.width; height: 52; radius: 12
                        color: chatMouse.containsMouse ? Theme.hover : (modelData.unread > 0 ? Theme.subtle : "transparent")
                        Avatar { x: 8; anchors.verticalCenter: parent.verticalCenter; letter: modelData.initial; tint: modelData.color; online: modelData.online }
                        Column {
                            x: 52; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 92; spacing: 3
                            Text { width: parent.width; elide: Text.ElideRight; text: modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                            Text { width: parent.width; elide: Text.ElideRight; text: modelData.preview; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                        }
                        Rectangle {
                            visible: modelData.unread > 0
                            anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(18, n.implicitWidth + 10); height: 18; radius: 9; color: Theme.accent
                            Text { id: n; anchors.centerIn: parent; text: modelData.unread; color: Theme.accentText; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
                        }
                        MouseArea { id: chatMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.openChat(modelData.id) }
                    }
                }
                Text {
                    visible: messenger.ready && root.recent.length === 0 && messenger.requests.length === 0
                    width: parent.width; wrapMode: Text.WordWrap
                    text: "Noch keine Chats. Öffne den Messenger und füge jemanden über seine Orbit-ID hinzu."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                }

                // Schnellantwort
                Rectangle {
                    visible: root.replyTo !== null
                    width: parent.width; height: 42; radius: 12; color: Theme.raised
                    TextField {
                        id: quick
                        x: 12; width: parent.width - 54; height: parent.height
                        placeholderTextColor: Theme.textMuted
                        placeholderText: root.replyTo ? "Schnell an " + root.replyTo.name + " antworten" : ""
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
                        background: Item {}
                        onAccepted: if (root.replyTo) { messenger.send(root.replyTo.id, text); text = "" }
                    }
                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                        width: 30; height: 30; radius: 9; color: Theme.accent; opacity: quick.text.trim() ? 1 : 0.5
                        Text { anchors.centerIn: parent; text: "➜"; color: Theme.accentText; font.pixelSize: 14; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: quick.accepted() }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Senden"
                    }
                }
                Text {
                    visible: messenger.queued > 0
                    width: parent.width; wrapMode: Text.WordWrap
                    text: messenger.queued === 1 ? "1 Nachricht wartet, bis der Empfänger online ist." : messenger.queued + " Nachrichten warten, bis die Empfänger online sind."
                    color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 12
                }

                Divider { width: parent.width; visible: messenger.ready }
                Item {
                    visible: messenger.ready
                    width: parent.width; height: 30
                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Nicht stören"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                    CSwitch {
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        label: "Nicht stören"; checked: messenger.dnd
                        onToggled: (v) => messenger.setDnd(v)
                    }
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: "Läuft immer im Hintergrund mit. Nachrichten gehen direkt von Rechner zu Rechner."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                }
            }
        }
    }
}
