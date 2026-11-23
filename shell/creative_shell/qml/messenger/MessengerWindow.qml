import QtQuick
import QtQuick.Templates as GibeonT
import QtQuick.Controls.Basic
import QtQuick.Window
import Creative

// Messenger-Fenster: links Ich und Kontakte, rechts der Chat. Schließen → läuft im Tray weiter.
ApplicationWindow {
    id: win
    width: 1040
    height: 700
    minimumWidth: 720
    minimumHeight: 480
    visible: true
    title: messenger.chat && messenger.chatInfo.name ? messenger.chatInfo.name + " – Messenger" : "Messenger"
    color: Theme.ground

    property bool addOpen: false

    Component.onCompleted: if (startChat) messenger.openChat(startChat)
    onActiveChanged: messenger.setVisibleChat(messenger.chat, active)
    Connections {
        target: messenger
        function onMessagesChanged() {
            messenger.setVisibleChat(messenger.chat, win.active)
            Qt.callLater(() => list.positionViewAtEnd())
        }
    }

    component Avatar: Rectangle {
        property string letter
        property string tint: Theme.accent
        property bool online: false
        property bool showDot: true
        property int size: 38
        width: size; height: size; radius: size / 2; color: tint
        Text {
            anchors.centerIn: parent; text: letter; color: "#12151b"
            font.family: Theme.fontFamily; font.pixelSize: Math.round(size * 0.4); font.bold: true
        }
        Rectangle {
            visible: showDot
            width: 11; height: 11; radius: 6
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: -1
            color: online ? Theme.ok : "#5b6474"; border.width: 2; border.color: Theme.surface
        }
    }

    // ---- Dienst nicht erreichbar ----------------------------------------------------------
    Column {
        visible: !messenger.connected
        anchors.centerIn: parent; spacing: 10
        SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "chat"; size: 40 }
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Messenger startet …"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true }
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Der Hintergrunddienst wird verbunden."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 }
    }

    // ---- Erster Start: Name wählen --------------------------------------------------------
    Rectangle {
        visible: messenger.connected && !messenger.ready
        anchors.centerIn: parent
        width: 460; height: setupCol.implicitHeight + 56
        radius: Theme.radiusMenu; color: Theme.surface; border.color: Theme.hairline
        Column {
            id: setupCol
            x: 28; y: 28; width: parent.width - 56; spacing: 16
            SvgIcon { name: "chat"; size: 36 }
            Text { text: "Willkommen im Messenger"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 22; font.bold: true }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: "Schreib direkt mit anderen Gibeon-OS-Nutzern – ohne Telefonnummer, ohne Konto. Wähle den Namen, unter dem man dich findet."
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
            }
            TextField {
                GibeonT.ContextMenu.menu: CTextMenu {}
                id: nameField
                width: parent.width; height: 44
                placeholderTextColor: Theme.textMuted
                placeholderText: "Dein Name"
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 15
                background: Rectangle { radius: 12; color: Theme.ground; border.color: nameField.activeFocus ? Theme.accent : Theme.hairline }
                onAccepted: if (text.trim()) messenger.setup(text)
                Component.onCompleted: forceActiveFocus()
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: "Deine Gibeon-ID wird dein Name mit vier Ziffern, z. B. „" + (nameField.text.trim() ? nameField.text.trim().toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss").replace(/[^a-z0-9]+/g, "") : "markus") + ".gibeonos2801“. Sie gehört fest zu diesem Rechner."
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
            Text { visible: messenger.error !== ""; width: parent.width; wrapMode: Text.WordWrap; text: messenger.error; color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 12 }
            CButton { text: "Los geht's"; primary: true; enabled: nameField.text.trim().length > 0; onClicked: messenger.setup(nameField.text) }
        }
    }

    // ---- Hauptansicht ---------------------------------------------------------------------
    Row {
        visible: messenger.connected && messenger.ready
        anchors.fill: parent

        // Seitenleiste
        Rectangle {
            id: side
            width: 300; height: parent.height
            color: Theme.footer
            Column {
                id: sideTop
                x: 14; y: 16; width: parent.width - 28; spacing: 12
                Rectangle {
                    width: parent.width; height: 64; radius: 14; color: Theme.raised
                    Avatar { x: 12; anchors.verticalCenter: parent.verticalCenter; letter: messenger.myName.charAt(0).toUpperCase(); online: true; size: 40 }
                    Column {
                        x: 64; anchors.verticalCenter: parent.verticalCenter; spacing: 3; width: parent.width - 108
                        Text { width: parent.width; elide: Text.ElideRight; text: messenger.myName; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                        Text { width: parent.width; elide: Text.ElideRight; text: messenger.myId; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                    }
                    IconButton { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 32; height: 32; iconSize: 16; icon: "copy"; label: "Gibeon-ID kopieren"; onClicked: messenger.copyId() }
                }
                CButton {
                    width: parent.width; height: 40
                    text: messenger.requests.length > 0 ? "Kontakt hinzufügen · " + messenger.requests.length + " Anfrage" + (messenger.requests.length > 1 ? "n" : "") : "Kontakt hinzufügen"
                    onClicked: { messenger.clearError(); win.addOpen = true }
                }
                Text { text: "KONTAKTE"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true; leftPadding: 8; topPadding: 4 }
            }
            ListView {
                anchors.top: sideTop.bottom; anchors.topMargin: 6
                anchors.bottom: parent.bottom; anchors.bottomMargin: 10
                x: 14; width: parent.width - 28
                clip: true; spacing: 4
                model: messenger.contacts
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width; height: 60; radius: 12
                    color: messenger.chat === modelData.id ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16) : (rowMouse.containsMouse ? Theme.hover : "transparent")
                    Avatar { x: 10; anchors.verticalCenter: parent.verticalCenter; letter: modelData.initial; tint: modelData.color; online: modelData.online; showDot: modelData.status === "accepted" }
                    Column {
                        x: 60; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 70; spacing: 4
                        Item {
                            width: parent.width; height: 16
                            Text { width: parent.width - 50; elide: Text.ElideRight; text: modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                            Text { anchors.right: parent.right; text: modelData.time; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                        }
                        Item {
                            width: parent.width; height: 18
                            Text { width: parent.width - 30; elide: Text.ElideRight; text: modelData.preview; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12; font.italic: modelData.status === "outgoing" }
                            Rectangle {
                                visible: modelData.unread > 0
                                anchors.right: parent.right; width: Math.max(18, badge.implicitWidth + 10); height: 18; radius: 9; color: Theme.accent
                                Text { id: badge; anchors.centerIn: parent; text: modelData.unread; color: Theme.accentText; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
                            }
                        }
                    }
                    MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: messenger.openChat(modelData.id) }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.name + (modelData.unread > 0 ? ", " + modelData.unread + " ungelesen" : "")
                }
                Text {
                    visible: messenger.contacts.length === 0
                    width: parent.width; wrapMode: Text.WordWrap; topPadding: 12; leftPadding: 8
                    text: "Noch keine Kontakte. Gib deine Gibeon-ID weiter oder füge jemanden über seine ID hinzu."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                }
            }
        }
        Rectangle { width: 1; height: parent.height; color: Theme.hairline }

        // Chat
        Item {
            width: parent.width - side.width - 1; height: parent.height
            Column {
                visible: !messenger.chat
                anchors.centerIn: parent; spacing: 10
                SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "chat"; size: 44; opacity: 0.6 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Wähle links einen Kontakt"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 14 }
            }
            Item {
                visible: !!messenger.chat
                anchors.fill: parent
                Rectangle {
                    id: head
                    width: parent.width; height: 68; color: Theme.surface
                    Avatar { x: 22; anchors.verticalCenter: parent.verticalCenter; letter: messenger.chatInfo.initial || ""; tint: messenger.chatInfo.color || Theme.accent; online: !!messenger.chatInfo.online; showDot: false; size: 40 }
                    Column {
                        x: 76; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                        Text { text: messenger.chatInfo.name || ""; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 15; font.bold: true }
                        Text {
                            text: (messenger.chatInfo.id || "") + " · " + (messenger.chatInfo.status === "outgoing" ? "Anfrage gesendet" : (messenger.chatInfo.online ? "online" : "offline – Nachrichten warten, bis ihr beide online seid"))
                            color: messenger.chatInfo.online ? Theme.ok : Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                        }
                    }
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: messenger.chatInfo.status === "accepted"
                            height: 30; width: lockRow.implicitWidth + 24; radius: 15
                            color: Qt.rgba(Theme.ok.r, Theme.ok.g, Theme.ok.b, 0.12)
                            Row {
                                id: lockRow; anchors.centerIn: parent; spacing: 6
                                SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "lock"; size: 13 }
                                Text { anchors.verticalCenter: parent.verticalCenter; text: "Verschlüsselt · " + (messenger.chatInfo.fingerprint || ""); color: Theme.ok; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
                            }
                            ToolTip.visible: lockMouse.containsMouse
                            ToolTip.text: "Direkte, Ende-zu-Ende-verschlüsselte Verbindung. Der Schlüssel dieses Kontakts ist gemerkt (Fingerabdruck)."
                            MouseArea { id: lockMouse; anchors.fill: parent; hoverEnabled: true }
                        }
                        IconButton { width: 32; height: 32; iconSize: 16; icon: "trash"; label: "Kontakt entfernen"; onClicked: removeConfirm.open() }
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hairline }
                }
                ListView {
                    id: list
                    anchors.top: head.bottom; anchors.bottom: composer.top
                    width: parent.width; clip: true; spacing: 10
                    topMargin: 18; bottomMargin: 12; leftMargin: 24; rightMargin: 24
                    model: messenger.messages
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Item {
                        required property var modelData
                        width: list.width - 48; height: bubble.height + meta.height + 4
                        Rectangle {
                            id: bubble
                            anchors.right: modelData.me ? parent.right : undefined
                            width: Math.min(msgText.implicitWidth + 28, parent.width * 0.7)
                            height: msgText.implicitHeight + 20; radius: 16
                            color: modelData.me ? Theme.accent : Theme.raised
                            TextEdit {
                                id: msgText
                                x: 14; y: 10; width: Math.min(implicitWidth, list.width * 0.7 - 76)
                                readOnly: true; selectByMouse: true; wrapMode: Text.Wrap
                                text: modelData.text; textFormat: TextEdit.PlainText
                                color: modelData.me ? Theme.accentText : Theme.text
                                font.family: Theme.fontFamily; font.pixelSize: 14
                            }
                        }
                        Text {
                            id: meta
                            anchors.top: bubble.bottom; anchors.topMargin: 4
                            anchors.right: modelData.me ? parent.right : undefined
                            text: modelData.time + (modelData.me && modelData.stateLabel ? " · " + modelData.stateLabel : "")
                            color: modelData.state === "queued" ? Theme.flame : Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                        }
                    }
                }
                Rectangle {
                    id: composer
                    anchors.bottom: parent.bottom; width: parent.width; height: 74; color: "transparent"
                    Row {
                        x: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 10; width: parent.width - 40
                        TextField {
                            GibeonT.ContextMenu.menu: CTextMenu {}
                            id: input
                            width: parent.width - 52; height: 44
                            enabled: messenger.chatInfo.status === "accepted"
                            placeholderTextColor: Theme.textMuted
                            placeholderText: messenger.chatInfo.status === "accepted" ? "Nachricht an " + (messenger.chatInfo.name || "") : "Erst schreiben, wenn die Anfrage angenommen ist"
                            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14
                            background: Rectangle { radius: 12; color: Theme.raised; border.color: input.activeFocus ? Theme.accent : Theme.hairline }
                            onAccepted: { messenger.send(messenger.chat, text); text = "" }
                        }
                        Rectangle {
                            width: 42; height: 42; radius: 12; color: Theme.accent; opacity: input.enabled && input.text.trim() ? 1 : 0.5
                            Text { anchors.centerIn: parent; text: "➜"; color: Theme.accentText; font.pixelSize: 18; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: input.enabled; onClicked: { messenger.send(messenger.chat, input.text); input.text = "" } }
                            Accessible.role: Accessible.Button
                            Accessible.name: "Senden"
                        }
                    }
                }
            }
        }
    }

    ConfirmDialog {
        id: removeConfirm
        danger: true
        title: "Kontakt entfernen?"
        text: (messenger.chatInfo.name || "") + " und der ganze Verlauf werden von diesem Rechner gelöscht."
        confirmText: "Entfernen"
        onConfirmed: messenger.remove(messenger.chat)
    }

    // ---- Kontakt hinzufügen ----------------------------------------------------------------
    Rectangle {
        visible: win.addOpen
        anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.45)
        MouseArea { anchors.fill: parent; onClicked: win.addOpen = false }
        Rectangle {
            anchors.centerIn: parent
            width: 480; height: addCol.implicitHeight + 56
            radius: Theme.radiusMenu; color: Theme.surface; border.color: Theme.hairline
            MouseArea { anchors.fill: parent }
            Column {
                id: addCol
                x: 28; y: 28; width: parent.width - 56; spacing: 16
                Item {
                    width: parent.width; height: 32
                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Kontakt hinzufügen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true }
                    IconButton { anchors.right: parent.right; width: 32; height: 32; iconSize: 14; icon: "close"; label: "Schließen"; onClicked: win.addOpen = false }
                }
                Rectangle {
                    width: parent.width; height: myCol.implicitHeight + 32; radius: 14; color: Theme.raised
                    Column {
                        id: myCol; x: 16; y: 16; width: parent.width - 32; spacing: 6
                        Text { text: "DEINE ORBIT-ID"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
                        Text { text: messenger.myId; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true }
                        Text { width: parent.width; wrapMode: Text.WordWrap; text: "Gib sie weiter – nur Gibeon-OS-Nutzer können dich damit finden."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                        CButton { id: copyBtn; text: "ID kopieren"; onClicked: { messenger.copyId(); text = "Kopiert" } }
                    }
                }
                Text { text: "Gibeon-ID der anderen Person"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                Row {
                    width: parent.width; spacing: 10
                    TextField {
                        GibeonT.ContextMenu.menu: CTextMenu {}
                        id: idField
                        width: parent.width - sendReq.width - 10; height: 44
                        placeholderTextColor: Theme.textMuted
                        placeholderText: "z. B. jonas.gibeonos4417"
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14
                        background: Rectangle { radius: 12; color: Theme.ground; border.color: idField.activeFocus ? Theme.accent : Theme.hairline }
                        onAccepted: sendReq.clicked()
                    }
                    CButton {
                        id: sendReq; height: 44; text: "Anfrage senden"; primary: true; enabled: idField.text.trim().length > 0
                        onClicked: { messenger.add(idField.text); idField.text = "" }
                    }
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: messenger.error !== "" ? messenger.error : "Die Person sieht deine Anfrage und muss sie annehmen. Erst dann könnt ihr schreiben."
                    color: messenger.error !== "" ? Theme.flame : Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                }
                Text { visible: messenger.requests.length > 0; text: "ANFRAGEN AN DICH"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
                Repeater {
                    model: messenger.requests
                    delegate: Rectangle {
                        required property var modelData
                        width: addCol.width; height: 62; radius: 14; color: Theme.subtle; border.color: Theme.hairline
                        Avatar { x: 12; anchors.verticalCenter: parent.verticalCenter; letter: modelData.initial; tint: modelData.color; showDot: false }
                        Column {
                            x: 62; anchors.verticalCenter: parent.verticalCenter; spacing: 3; width: parent.width - 250
                            Text { width: parent.width; elide: Text.ElideRight; text: modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                            Text { width: parent.width; elide: Text.ElideRight; text: modelData.id + " · " + modelData.fingerprint; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                        }
                        Row {
                            anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                            CButton { text: "Ablehnen"; onClicked: messenger.decline(modelData.id) }
                            CButton { text: "Annehmen"; primary: true; onClicked: { messenger.accept(modelData.id); messenger.openChat(modelData.id); win.addOpen = false } }
                        }
                    }
                }
            }
        }
    }
}
