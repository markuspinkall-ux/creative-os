import QtQuick
import QtQuick.Window
import Creative

// Obere Leiste (Fluid-Design): links der Tray – WLAN, Ton, Bluetooth, Tastatur und die
// Symbole anderer Programme –, in der Mitte „Gibeon OS“. Uhrzeit, Datum und Akku sitzen
// unten in der Taskleiste hinter dem Papierkorb. Klick links öffnet den Schnellzugriff.
Item {
    id: root

    property string screenName

    // ---- Einfahren bei maximiertem Fenster ------------------------------------------------
    // Ist auf diesem Monitor ein Fenster maximiert, reserviert die Leiste keinen Platz und fährt
    // nach oben weg. Nur ein schmaler Streifen am oberen Rand nimmt dann die Maus an: geht sie
    // dorthin, fährt die Leiste herein; verlässt sie die Leiste, fährt sie wieder ein.
    readonly property bool autoHide: !!(Window.window && Window.window.autoHide)
    readonly property bool hovered: !!(Window.window && Window.window.hovered)
    readonly property bool menuOpen: shell.trayMenuOpenOn === root.screenName
                                     || shell.quickPanelOpenOn === root.screenName
    property bool peek: false
    readonly property bool shown: !autoHide || peek || menuOpen
    readonly property int edge: 3            // Streifen, der die Maus fängt
    property real shift: shown ? 0 : -height
    Behavior on shift { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    transform: Translate { y: root.shift }

    onHoveredChanged: {
        if (hovered) {
            leaveTimer.stop()
            peek = true
        } else {
            leaveTimer.restart()
        }
    }
    Timer { id: leaveTimer; interval: 500; onTriggered: root.peek = root.hovered }
    onAutoHideChanged: { if (!autoHide) peek = false; updateInput() }
    onShownChanged: { updateInput(); blurTimer.restart() }
    Timer { id: blurTimer; interval: 240; onTriggered: root.updateBlur() }

    function updateInput() {
        if (!Window.window) return
        if (!autoHide || shown)
            shell.setInputRect(Window.window, 0, 0, 0, 0)          // ganze Fläche
        else
            shell.setInputRect(Window.window, 0, 0, width, edge)   // nur der Streifen oben
    }

    // Fluid-Glas: nur unter den beiden Feldern weichzeichnen
    function updateBlur() {
        if (!shown) {
            shell.setBlur(Window.window, [])
            return
        }
        shell.setBlur(Window.window, [
            { x: left.x, y: left.y, w: left.width, h: left.height, r: 17 }
        ])
    }
    Component.onCompleted: Qt.callLater(updateBlur)
    onWidthChanged: { Qt.callLater(updateBlur); updateInput() }

    // Glas-Feld: durchscheinend, feine Kante, Lichtkante oben
    component Pill: Rectangle {
        property bool lit: false
        height: 34
        radius: 17
        readonly property color base: shell.blurAvailable ? Theme.glass : Theme.glassSolid
        color: lit ? Qt.rgba(base.r, base.g, base.b, Math.min(1, base.a + 0.18)) : base
        border.color: Theme.glassEdge
        border.width: 1
        Rectangle {
            x: parent.radius
            y: 1
            width: parent.width - 2 * parent.radius
            height: 1
            color: Theme.glassShine
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
        onWidthChanged: Qt.callLater(root.updateBlur)
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
}
