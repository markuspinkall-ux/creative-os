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

        Row {
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
