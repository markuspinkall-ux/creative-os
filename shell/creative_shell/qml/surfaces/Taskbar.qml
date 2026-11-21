import QtQuick
import QtQuick.Window
import Creative

// Die Taskleiste: links Startmenü und Apps, Mitte „Gerade läuft“, rechts der Papierkorb.
// Tray (WLAN, Ton, Bluetooth, Programme) und Uhrzeit sitzen in der oberen Leiste (Topbar.qml).
Item {
    id: root

    property string screenName

    // Fluid-Glas: KWin zeichnet den Hintergrund hinter der Leiste weich
    function updateBlur() {
        shell.setBlur(Window.window, [{ x: bar.x, y: bar.y, w: bar.width, h: bar.height, r: 0 }])
    }
    Component.onCompleted: Qt.callLater(updateBlur)
    onWidthChanged: Qt.callLater(updateBlur)
    onHeightChanged: Qt.callLater(updateBlur)

    // Fluid-Design: Glasleiste über die ganze Breite, bündig am unteren Rand,
    // oben eine feine Kante und darunter eine Lichtkante wie bei Glas.
    Rectangle {
        id: bar
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        height: 52
        radius: 0
        color: shell.blurAvailable ? Theme.glass : Theme.glassSolid

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1
            color: Theme.glassEdge
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 1 }
            height: 1
            color: Theme.glassShine
        }

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
            anchors.leftMargin: 4
            anchors.rightMargin: 4
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
                    // dunkles Orbit-Blau, nach oben heller
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
                    color: Theme.tint(0.1)
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
                    badge: modelData.badge || 0
                    onClicked: {
                        shell.closePopups()
                        tasks.activate(root.screenName, modelData.key, modelData.desktopId)
                    }
                    onMiddleClicked: tasks.launchNew(modelData.desktopId)
                    // Programmname beim Drüberfahren (eigene, durchlässige Fläche über der Leiste)
                    onHoveredChanged: {
                        if (hovered)
                            shell.showTaskTip(root.screenName, modelData.name || modelData.title || "",
                                              mapToItem(null, width / 2, 0).x, modelData.count || 0)
                        else
                            shell.hideTaskTip(root.screenName)
                    }
                    onRightClicked: shell.toggleTaskMenu(root.screenName, {
                        key: modelData.key, desktopId: modelData.desktopId, name: modelData.name,
                        running: modelData.running, count: modelData.count,
                        pinned: !!modelData.pinned   // ohne das zeigte das Menü nie „Von der Taskleiste lösen“
                    }, mapToItem(null, width / 2, 0).x)
                }
            }
        }

        // Gerade läuft: Interpret – Titel, mittig im freien Platz der Taskleiste
        Item {
            id: nowPlaying
            readonly property real freeL: appsRow.x + appsRow.width + 18
            readonly property real freeR: trashBtn.x - 26
            // Breite aus dem Text selbst (nicht aus der Zeile – sonst bleibt sie bei 0 hängen)
            width: Math.max(0, Math.min(15 + 9 + npText.implicitWidth + 24, freeR - freeL, 460))
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
                    id: npText
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

        // Papierkorb ganz rechts (Tray, Uhrzeit und WLAN sitzen jetzt oben in der Leiste)
        Rectangle {
            id: trashBtn
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 40
            height: 40
            radius: 12
            color: (trashMouse.containsMouse || shell.trashMenuOpenOn === root.screenName)
                   ? Theme.hover : "transparent"
            SvgIcon {
                anchors.centerIn: parent
                name: trash.full ? "trash-full" : "trash"
                size: 20
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
            anchors.right: trashBtn.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: 24
            color: Theme.tint(0.1)
        }
    }

}
