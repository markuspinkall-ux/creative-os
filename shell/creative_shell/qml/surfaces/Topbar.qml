import QtQuick
import Creative

// Obere Leiste (Fluid-Design): links der Tray – WLAN, Ton, Bluetooth, Tastatur und die
// Symbole anderer Programme –, in der Mitte „Gibeon OS“, rechts Uhrzeit, Datum und Akku.
// Klick links öffnet den Schnellzugriff darunter, Klick auf die Uhr den Kalender rechts.
Item {
    id: root

    property string screenName

    // Glas-Feld: durchscheinend, feine Kante, Lichtkante oben
    component Pill: Rectangle {
        property bool lit: false
        height: 34
        radius: 17
        color: lit ? Qt.rgba(Theme.bar.r, Theme.bar.g, Theme.bar.b, 0.98) : Theme.bar
        border.color: Theme.light ? Qt.rgba(1, 1, 1, 0.9) : Qt.rgba(1, 1, 1, 0.12)
        border.width: 1
        Rectangle {
            x: parent.radius
            y: 1
            width: parent.width - 2 * parent.radius
            height: 1
            color: Qt.rgba(1, 1, 1, Theme.light ? 0.95 : 0.18)
        }
    }

    // Klick auf freie Fläche schließt offene Menüs
    MouseArea {
        anchors.fill: parent
        onClicked: shell.closePopups()
    }

    // ---- links: Tray ----
    Pill {
        id: left
        x: 14
        y: 10
        width: leftRow.implicitWidth + 28
        lit: leftMouse.containsMouse || shell.quickPanelOpenOn === root.screenName

        MouseArea {
            id: leftMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: shell.toggleQuickPanel(root.screenName)
        }

        Row {
            id: leftRow
            anchors.centerIn: parent
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
                    onClicked: shell.toggleBluetooth(root.screenName)
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
                            shell.noteScreen(root.screenName)
                            if (mouse.button === Qt.RightButton && (modelData.hasMenu || modelData.canQuit)) {
                                trayApps.loadMenu(modelData.key)
                                shell.toggleTrayAppMenu(root.screenName, modelData.key)
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
                color: (msgMouse.containsMouse || shell.messengerOpenOn === root.screenName) ? Theme.hover : "transparent"
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
                        else shell.toggleMessenger(root.screenName)
                    }
                }
                Accessible.role: Accessible.Button
                Accessible.name: "Messenger" + (messengerBtn.count > 0 ? ", " + messengerBtn.count + " neu" : "")
                Accessible.onPressAction: shell.toggleMessenger(root.screenName)
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

        Accessible.role: Accessible.Button
        Accessible.name: "Schnellzugriff: WLAN, Lautstärke, Bluetooth, Helligkeit"
        Accessible.onPressAction: shell.toggleQuickPanel(root.screenName)
    }

    // ---- Mitte ----
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 10 + (34 - height) / 2
        text: "Gibeon OS"
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 14
        Accessible.ignored: true
    }

    // ---- rechts: Uhrzeit, Datum, Akku ----
    Pill {
        id: right
        anchors.right: parent.right
        anchors.rightMargin: 14
        y: 10
        width: rightRow.implicitWidth + 28
        lit: rightMouse.containsMouse

        MouseArea {
            id: rightMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: shell.toggleCalendar(root.screenName)
        }

        Row {
            id: rightRow
            anchors.centerIn: parent
            spacing: 12
            Text {
                id: clock
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.bold: true
            }
            Text {
                id: date
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            // Akku (nur bei Laptops)
            Row {
                anchors.verticalCenter: parent.verticalCenter
                visible: akku.present && widgetExtras.akkuInstalled
                spacing: 6
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: akku.percent + " %"
                    color: akku.low ? Theme.flame : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                BatteryGlyph {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 24; height: 12
                    level: akku.percent
                    charging: akku.charging
                    low: akku.low
                }
                Accessible.role: Accessible.StaticText
                Accessible.name: "Akku " + akku.percent + " Prozent, " + akku.statusText
            }
        }

        Accessible.role: Accessible.Button
        Accessible.name: "Kalender – " + clock.text + ", " + date.text
        Accessible.onPressAction: shell.toggleCalendar(root.screenName)
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const now = new Date()
            clock.text = Qt.formatTime(now, "HH:mm")
            // z. B. „Sa., 21. Nov.“
            date.text = now.toLocaleDateString(Qt.locale("de_DE"), "ddd, d. MMM")
        }
    }
}
