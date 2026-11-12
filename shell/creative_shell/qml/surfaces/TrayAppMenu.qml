import QtQuick
import QtQuick.Controls.Basic
import Creative

// Rechtsklick-Menü eines Tray-Programms (z. B. Steam, Discord) im Creative-Look.
Item {
    id: root
    property string screenName

    function opened() { root.forceActiveFocus() }
    focus: true
    Keys.onEscapePressed: shell.closePopups()

    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }

    Rectangle {
        id: card
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        width: 270
        height: Math.min(parent.height - 10, col.implicitHeight + 16)
        radius: 14
        color: Theme.raised
        border.color: Theme.hairline
        MouseArea { anchors.fill: parent }

        Flickable {
            anchors.fill: parent
            anchors.margins: 8
            contentHeight: col.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: col
                width: parent.width
                spacing: 1
                Text {
                    leftPadding: 10
                    topPadding: 6
                    bottomPadding: 6
                    width: parent.width
                    elide: Text.ElideRight
                    text: trayApps.menuTitle
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                }
                Text {
                    visible: trayApps.menu.length === 0 && trayApps.menuHasItems
                    leftPadding: 10
                    bottomPadding: 8
                    text: "Wird geladen …"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                Repeater {
                    model: trayApps.menu
                    delegate: Item {
                        width: col.width
                        height: modelData.separator ? 9 : 36
                        Rectangle {
                            visible: modelData.separator
                            anchors.centerIn: parent
                            width: parent.width - 16
                            height: 1
                            color: Theme.hairline
                        }
                        Rectangle {
                            visible: !modelData.separator
                            anchors.fill: parent
                            radius: 9
                            opacity: modelData.enabled ? 1 : 0.45
                            color: im.containsMouse && modelData.enabled ? Theme.hover : "transparent"
                            Text {
                                x: 12
                                width: parent.width - 40
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                                text: modelData.label
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.bold: !modelData.enabled && modelData.label.trim().length > 0
                            }
                            SvgIcon {
                                visible: modelData.checked
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                name: "check"
                                size: 14
                            }
                            MouseArea {
                                id: im
                                anchors.fill: parent
                                hoverEnabled: true
                                enabled: modelData.enabled
                                onClicked: { trayApps.menuClick(modelData.id); shell.closePopups() }
                            }
                        }
                    }
                }

                // Programm beenden – nicht bei Systemprogrammen, die ab dem Start immer laufen
                Item {
                    visible: trayApps.menuCanQuit
                    width: col.width
                    height: trayApps.menu.length ? 9 : 0
                    Rectangle { anchors.centerIn: parent; width: parent.width - 16; height: 1; color: Theme.hairline; visible: parent.height > 0 }
                }
                Rectangle {
                    visible: trayApps.menuCanQuit
                    width: col.width
                    height: 36
                    radius: 9
                    color: quitMouse.containsMouse ? Theme.hover : "transparent"
                    SvgIcon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: "power"; size: 15 }
                    Text {
                        x: 34
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Beenden"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                    MouseArea {
                        id: quitMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { trayApps.quit(trayApps.menuKey); shell.closePopups() }
                    }
                    Accessible.role: Accessible.MenuItem
                    Accessible.name: "Beenden"
                    Accessible.onPressAction: { trayApps.quit(trayApps.menuKey); shell.closePopups() }
                }
            }
        }
    }
}
