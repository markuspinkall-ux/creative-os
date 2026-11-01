import QtQuick
import Creative

// Die Taskleiste: links Startmenü, Dateien, Browser, Terminal –
// rechts der Tray mit Papierkorb, Helligkeit, Drucker, WLAN und Uhr.
Item {
    id: root

    property string screenName

    Rectangle {
        id: bar
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            leftMargin: 24
            rightMargin: 24
            bottomMargin: 14
        }
        height: 60
        radius: Theme.radiusBar
        color: Theme.bar
        border.color: Theme.hairline
        border.width: 1

        // Klick auf freie Fläche schließt offene Menüs
        MouseArea {
            anchors.fill: parent
            onClicked: shell.closePopups()
        }

        // Musik-Visualizer: dunkelblaue Balken über die ganze Breite, hinter allen Knöpfen.
        // Nimmt keine Klicks an – die Taskleiste bleibt voll bedienbar.
        Item {
            id: viz
            anchors.fill: parent
            anchors.leftMargin: bar.radius - 4
            anchors.rightMargin: bar.radius - 4
            anchors.topMargin: 6
            anchors.bottomMargin: 3
            enabled: false
            opacity: visualizer.active && visualizer.enabled ? visualizer.strength : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
            readonly property int count: visualizer.bars
            readonly property real step: width / count
            Repeater {
                model: viz.count
                delegate: Rectangle {
                    required property int index
                    readonly property real level: visualizer.levels[index] || 0
                    x: index * viz.step + 1
                    width: Math.max(2, viz.step - 3)
                    height: Math.max(2, viz.height * level)
                    anchors.bottom: parent.bottom
                    radius: Math.min(3, width / 2)
                    // dunkles Creative-Blau, nach oben heller
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0.40, 0.55, 0.92, 0.62) }
                        GradientStop { position: 1.0; color: Qt.rgba(0.16, 0.27, 0.55, 0.45) }
                    }
                    Behavior on height { NumberAnimation { duration: 60 } }
                }
            }
        }

        Row {
            id: appsRow
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            StartButton {
                open: shell.startMenuOpenOn === root.screenName
                onClicked: shell.toggleStartMenu(root.screenName)
            }

            Item {
                width: 13
                height: 44
                Rectangle {
                    anchors.centerIn: parent
                    width: 1
                    height: 28
                    color: Qt.rgba(1, 1, 1, 0.1)
                }
            }

            Repeater {
                // Angeheftete Apps + laufende Programme auf diesem Monitor
                model: {
                    tasks.revision
                    return tasks.taskbarItems(root.screenName)
                }
                delegate: TaskButton {
                    required property var modelData
                    icon: modelData.icon
                    themeIcon: modelData.themeIcon
                    label: modelData.title
                    running: modelData.running
                    active: modelData.active
                    count: modelData.count
                    onClicked: {
                        shell.closePopups()
                        tasks.activate(root.screenName, modelData.key, modelData.desktopId)
                    }
                    onMiddleClicked: tasks.launchNew(modelData.desktopId)
                }
            }
        }

        // Gerade läuft: Interpret – Titel, mittig im freien Platz der Taskleiste
        Item {
            id: nowPlaying
            readonly property real freeL: appsRow.x + appsRow.width + 18
            readonly property real freeR: tray.x - 18
            width: Math.max(0, Math.min(npRow.implicitWidth + 24, freeR - freeL, 460))
            x: Math.max(freeL, Math.min(bar.width / 2 - width / 2, freeR - width))
            height: 40
            anchors.verticalCenter: parent.verticalCenter
            opacity: nowplaying.active && width > 90 ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 250 } }

            Rectangle {
                anchors.fill: parent
                radius: 20
                color: npMouse.containsMouse ? Theme.hover : "transparent"
            }
            Row {
                id: npRow
                anchors.centerIn: parent
                width: Math.min(implicitWidth, nowPlaying.width - 24)
                spacing: 9
                SvgIcon { id: npIcon; anchors.verticalCenter: parent.verticalCenter; name: "music"; size: 15 }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, Math.max(0, nowPlaying.width - 24 - npIcon.width - 9))
                    elide: Text.ElideRight
                    text: nowplaying.artist.length ? nowplaying.artist + "  –  " + nowplaying.title : nowplaying.title
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
            MouseArea {
                id: npMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: nowplaying.raiseSource()
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Gerade läuft: " + nowplaying.artist + " – " + nowplaying.title
        }

        Rectangle {
            id: tray
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            height: 44
            width: trayRow.implicitWidth + 28
            radius: Theme.radiusButton
            color: (trayMouse.containsMouse || shell.quickPanelOpenOn === root.screenName)
                   ? Theme.hover : Theme.subtle

            Row {
                id: trayRow
                anchors.centerIn: parent
                spacing: 14

                // Tray-Symbole anderer Programme (Steam, Discord …) im Creative-Look
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
                            source: modelData.creative === "" && modelData.icon ? "image://icon/" + modelData.icon : ""
                        }
                        MouseArea {
                            id: am
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            cursorShape: Qt.PointingHandCursor
                            onClicked: (mouse) => {
                                shell.noteScreen(root.screenName)
                                if (mouse.button === Qt.RightButton && modelData.hasMenu) {
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

                // Creative Broadcast: blau hinterlegt, wenn Mikrofon-Filter oder Kamera-Effekt an sind
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
                    // Punkt: eine App benutzt gerade die Creative Kamera
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
                            broadcast.open()
                        }
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: broadcast.tooltip
                }

                // Sprachassistent: Klick = zuhören, Rechtsklick = Mikrofon und Stimme
                Rectangle {
                    id: assistantBtn
                    visible: assistant.available
                    anchors.verticalCenter: parent.verticalCenter
                    readonly property string st: assistant.state
                    readonly property bool active: st === "listening" || st === "thinking" || st === "speaking" || st === "alarm"
                    width: 30
                    height: 30
                    radius: 8
                    color: st === "alarm" ? Qt.rgba(1, 0.69, 0.48, 0.25)
                           : (active ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22)
                              : ((asMouse.containsMouse || shell.assistantMenuOpenOn === root.screenName
                                  || shell.chatOpenOn === root.screenName) ? Theme.hover : "transparent"))

                    // Ruhezustand: Mikrofon
                    SvgIcon {
                        anchors.centerIn: parent
                        visible: !assistantBtn.active
                        name: "mic"
                        size: 17
                        opacity: assistant.music ? 1 : 0.95
                    }
                    // Visualizer: fünf Balken folgen der Stimme
                    Row {
                        anchors.centerIn: parent
                        visible: assistantBtn.active
                        spacing: 2
                        Repeater {
                            model: 5
                            delegate: Rectangle {
                                readonly property real shape: [0.55, 0.85, 1.0, 0.8, 0.5][index]
                                property real phase: 0
                                width: 2.5
                                radius: 1.25
                                anchors.verticalCenter: parent.verticalCenter
                                color: assistantBtn.st === "alarm" ? Theme.flame : Theme.accent
                                height: assistantBtn.st === "thinking"
                                        ? 4 + 10 * Math.abs(Math.sin(phase + index * 0.7))
                                        : 4 + 14 * shape * Math.min(1, assistant.level * 2.2 + 0.08 * Math.abs(Math.sin(phase + index)))
                                Behavior on height { NumberAnimation { duration: 70 } }
                                NumberAnimation on phase {
                                    running: assistantBtn.active
                                    from: 0; to: Math.PI * 2
                                    duration: 900
                                    loops: Animation.Infinite
                                }
                            }
                        }
                    }
                    // Kleiner Punkt: Musik oder Timer läuft
                    Rectangle {
                        visible: !assistantBtn.active && (assistant.music !== "" || assistant.timer > 0)
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 3
                        width: 6; height: 6; radius: 3
                        color: assistant.timer > 0 ? Theme.flame : Theme.ok
                    }
                    MouseArea {
                        id: asMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (mouse) => {
                            shell.noteScreen(root.screenName)
                            if (mouse.button === Qt.RightButton) {
                                assistant.refresh()
                                shell.toggleAssistantMenu(root.screenName)
                            } else {
                                // Klick: Chat-Fenster öffnen und gleich zuhören
                                const opening = shell.chatOpenOn !== root.screenName
                                shell.toggleChat(root.screenName)
                                if (opening && assistant.state === "idle")
                                    assistant.activate()
                                else if (opening && assistant.state === "alarm")
                                    assistant.stopTimer()
                            }
                        }
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Sprachassistent"
                    Accessible.onPressAction: assistant.activate()
                }

                // Papierkorb: Klick öffnet ihn, Rechtsklick zeigt „Leeren“
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30
                    height: 30
                    radius: 8
                    color: (trashMouse.containsMouse || shell.trashMenuOpenOn === root.screenName)
                           ? Theme.hover : "transparent"
                    SvgIcon {
                        anchors.centerIn: parent
                        name: trash.full ? "trash-full" : "trash"
                        size: 17
                    }
                    MouseArea {
                        id: trashMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (mouse) => {
                            if (mouse.button === Qt.RightButton) {
                                shell.toggleTrashMenu(root.screenName)
                            } else {
                                shell.closePopups()
                                trash.open()
                            }
                        }
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: trash.full ? "Papierkorb (" + trash.count + " Elemente)" : "Papierkorb (leer)"
                    Accessible.onPressAction: trash.open()
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 1
                    height: 20
                    color: Qt.rgba(1, 1, 1, 0.1)
                }

                SvgIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: "brightness"
                    size: 16
                }
                SvgIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: printers.available
                    name: printers.attention ? "printer-alert" : "printer"
                    size: 16
                }
                SvgIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: network.wired ? "wired" : (network.connected ? "wifi" : "wifi-off")
                    size: 16
                }
                // Uhr und Datum – Klick öffnet den Kalender
                Item {
                    anchors.verticalCenter: parent.verticalCenter
                    width: clockCol.implicitWidth
                    height: clockCol.implicitHeight
                    Column {
                        id: clockCol
                        Text {
                            id: clock
                            anchors.right: parent.right
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            id: date
                            anchors.right: parent.right
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -7
                        cursorShape: Qt.PointingHandCursor
                        onClicked: shell.toggleCalendar(root.screenName)
                    }
                }
            }

            MouseArea {
                id: trayMouse
                z: -1          // liegt unter dem Papierkorb-Knopf
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: shell.toggleQuickPanel(root.screenName)
            }

            Accessible.role: Accessible.Button
            Accessible.name: "Schnellzugriff: Helligkeit, Drucker, WLAN – " + clock.text
            Accessible.onPressAction: shell.toggleQuickPanel(root.screenName)
        }
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const now = new Date()
            clock.text = Qt.formatTime(now, "HH:mm")
            date.text = Qt.formatDate(now, "dd.MM.yyyy")
        }
    }
}
