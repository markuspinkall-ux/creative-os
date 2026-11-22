import QtQuick
import Creative

// Die Tray-Symbole (WLAN, Ton, Bluetooth, Drucker, Tastatur, Programme, Messenger, Broadcast,
// Deck). Sitzt je nach Einstellung oben links in der oberen Leiste oder in der Taskleiste vor
// der Uhr (Systemsteuerung › Darstellung › Systemtray).
Row {
    id: tray
    // Monitor, auf dem diese Tray-Symbole sitzen (für die Menüs)
    property string screenName
    spacing: 12

    SvgIcon {
        anchors.verticalCenter: parent.verticalCenter
        name: network.wired ? "wired" : (network.connected ? "wifi" : "wifi-off")
        size: 17
    }
    SvgIcon {
        anchors.verticalCenter: parent.verticalCenter
        name: audioOutput.muted || audioOutput.value === 0 ? "volume-off" : "volume"
        size: 17
    }
    Item {
        anchors.verticalCenter: parent.verticalCenter
        width: 17
        height: 17
        opacity: bluetooth.powered ? 1 : 0.5
        SvgIcon { anchors.centerIn: parent; name: "bluetooth"; size: 17 }
        MouseArea {
            anchors.fill: parent
            anchors.margins: -6
            cursorShape: Qt.PointingHandCursor
            onClicked: shell.toggleBluetooth(tray.screenName)
        }
        Accessible.role: Accessible.Button
        Accessible.name: bluetooth.powered ? "Bluetooth eingeschaltet" : "Bluetooth ausgeschaltet"
    }
    SvgIcon {
        anchors.verticalCenter: parent.verticalCenter
        visible: printers.available
        name: printers.attention ? "printer-alert" : "printer"
        size: 16
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: "DE"
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        font.bold: true
        Accessible.name: "Tastatur Deutsch"
    }
    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        visible: trayApps.items.length > 0 || messenger.available || broadcast.available || deckTray.available
        width: 1
        height: 18
        color: Theme.tint(0.14)
    }
    // Tray-Symbole anderer Programme (Steam, Discord …) im Gibeon-Look
    Repeater {
        model: trayApps.items
        delegate: Rectangle {
            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            width: 30
            height: 30
            radius: 8
            color: am.containsMouse ? Theme.hover : "transparent"
            SvgIcon {
                anchors.centerIn: parent
                visible: modelData.creative !== ""
                name: modelData.creative
                size: 17
            }
            Image {
                anchors.centerIn: parent
                visible: modelData.creative === ""
                width: 17; height: 17
                sourceSize.width: 34; sourceSize.height: 34
                source: modelData.creative === "" && modelData.icon ? iconFiles.url(modelData.icon) : ""
            }
            MouseArea {
                id: am
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                cursorShape: Qt.PointingHandCursor
                onClicked: (mouse) => {
                    shell.noteScreen(tray.screenName)
                    if (mouse.button === Qt.RightButton && (modelData.hasMenu || modelData.canQuit)) {
                        trayApps.loadMenu(modelData.key)
                        shell.toggleTrayAppMenu(tray.screenName, modelData.key)
                    } else {
                        shell.closePopups()
                        trayApps.activate(modelData.key)
                    }
                }
            }
            Accessible.role: Accessible.Button
            Accessible.name: modelData.title
        }
    }

    // Messenger: Sprechblase mit Zähler ungelesener Nachrichten und Anfragen
    Rectangle {
        id: messengerBtn
        visible: messenger.available
        anchors.verticalCenter: parent.verticalCenter
        width: 30
        height: 30
        radius: 8
        readonly property int count: messenger.unread + messenger.requests.length
        color: (msgMouse.containsMouse || shell.messengerOpenOn === tray.screenName) ? Theme.hover : "transparent"
        SvgIcon {
            anchors.centerIn: parent
            name: "chat"
            size: 17
            opacity: messenger.connected ? 1 : 0.5
        }
        Rectangle {
            visible: messengerBtn.count > 0
            anchors.right: parent.right; anchors.top: parent.top
            anchors.rightMargin: -3; anchors.topMargin: -3
            width: Math.max(16, msgBadge.implicitWidth + 8); height: 16; radius: 8
            color: messenger.dnd ? Theme.track : Theme.flame
            Text {
                id: msgBadge
                anchors.centerIn: parent
                text: messengerBtn.count > 99 ? "99+" : messengerBtn.count
                color: Theme.accentText
                font.family: Theme.fontFamily; font.pixelSize: 10; font.bold: true
            }
        }
        MouseArea {
            id: msgMouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
            cursorShape: Qt.PointingHandCursor
            onClicked: (mouse) => {
                if (mouse.button === Qt.MiddleButton) { shell.closePopups(); messenger.openWindow() }
                else shell.toggleMessenger(tray.screenName)
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: "Messenger" + (messengerBtn.count > 0 ? ", " + messengerBtn.count + " neu" : "")
        Accessible.onPressAction: shell.toggleMessenger(tray.screenName)
    }

    // Broadcast: blau hinterlegt, wenn Mikrofon-Filter oder Kamera-Effekt an sind
    Rectangle {
        id: broadcastBtn
        visible: broadcast.available
        anchors.verticalCenter: parent.verticalCenter
        width: 30
        height: 30
        radius: 8
        color: broadcast.active ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, bcMouse.containsMouse ? 0.3 : 0.2)
                                : (bcMouse.containsMouse ? Theme.hover : "transparent")
        SvgIcon {
            anchors.centerIn: parent
            name: "broadcast"
            size: 17
            opacity: broadcast.active ? 1 : 0.8
        }
        // Punkt: eine App benutzt gerade die Gibeon Kamera
        Rectangle {
            visible: broadcast.cameraInUse
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 3
            width: 6; height: 6; radius: 3
            color: Theme.ok
        }
        MouseArea {
            id: bcMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                shell.closePopups()
                // schon offen → nur nach vorn holen
                if (!tasks.focusApp("creative-broadcast.desktop"))
                    broadcast.open()
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: broadcast.tooltip
    }

    // Deck: öffnet den Stream-Deck-Editor; Punkt = Gerät verbunden
    Rectangle {
        id: deckBtn
        visible: deckTray.available
        anchors.verticalCenter: parent.verticalCenter
        width: 30
        height: 30
        radius: 8
        color: deckMouse.containsMouse ? Theme.hover : "transparent"
        SvgIcon {
            anchors.centerIn: parent
            name: "deck"
            size: 17
            opacity: deckTray.connected ? 1 : 0.8
        }
        Rectangle {
            visible: deckTray.connected
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 3
            width: 6; height: 6; radius: 3
            color: Theme.ok
        }
        MouseArea {
            id: deckMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                shell.closePopups()
                if (!tasks.focusApp("creative-deck.desktop"))
                    deckTray.open()
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: deckTray.tooltip
    }

}
