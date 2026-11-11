import QtQuick
import QtQuick.Controls.Basic
import Creative

// „Dieser PC“: Ordner und Laufwerke auf einen Blick.
Flickable {
    id: pc
    contentHeight: col.height + 44
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}

    Column {
        id: col
        x: 28
        y: 22
        width: pc.width - 56
        spacing: 14

        Heading { text: "Ordner" }
        Grid {
            id: folderGrid
            width: parent.width
            columns: Math.max(2, Math.min(6, Math.floor(width / 170)))
            spacing: 12
            Repeater {
                model: [{ name: "Persönlich", path: fm.homePath, color: "#5a6b8c" }].concat(fm.quickPlaces)
                delegate: Rectangle {
                    width: (folderGrid.width - (folderGrid.columns - 1) * 12) / folderGrid.columns
                    height: 56
                    radius: 12
                    color: m.containsMouse ? Theme.tint(0.07) : Theme.tint(0.03)
                    Row {
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12
                        FileGlyph { isDir: true; tint: modelData.color; size: 34; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modelData.name
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: fm.navigate(modelData.path) }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.name
                }
            }
        }

        Heading { text: "Geräte und Laufwerke"; topPadding: 10 }
        Grid {
            id: driveGrid
            width: parent.width
            columns: width > 760 ? 2 : 1
            spacing: 12
            Repeater {
                model: fm.drives
                delegate: Rectangle {
                    id: card
                    readonly property bool usb: modelData.removable
                    width: (driveGrid.width - (driveGrid.columns - 1) * 12) / driveGrid.columns
                    height: 84
                    radius: 14
                    color: dm.containsMouse ? Theme.tint(0.06) : (usb ? Theme.tint(0.05) : Theme.tint(0.03))
                    border.color: usb ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.4) : Theme.tint(0.06)

                    MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: fm.openDrive(index) }

                    Rectangle {
                        x: 18
                        anchors.verticalCenter: parent.verticalCenter
                        width: 48; height: 48; radius: 12
                        color: Theme.tint(0.06)
                        SvgIcon { anchors.centerIn: parent; name: card.usb ? "usb" : "drive"; size: 24 }
                    }
                    Column {
                        x: 82
                        width: card.width - 100
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 7
                        Item {
                            width: parent.width
                            height: 22
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - tag.width - 10
                                elide: Text.ElideRight
                                text: modelData.name
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                font.bold: true
                            }
                            Rectangle {
                                id: tag
                                visible: modelData.tag.length > 0
                                readonly property bool eject: modelData.tag === "Auswerfen"
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: tagText.implicitWidth + 16
                                height: 22
                                radius: 6
                                color: eject ? (tm.containsMouse ? Qt.lighter(Theme.accent, 1.1) : Theme.accent) : Theme.tint(0.08)
                                Text {
                                    id: tagText
                                    anchors.centerIn: parent
                                    text: modelData.tag
                                    color: tag.eject ? Theme.accentText : Theme.text
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                                MouseArea {
                                    id: tm
                                    anchors.fill: parent
                                    enabled: tag.eject
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: fm.ejectDrive(index)
                                }
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: 6
                            radius: 3
                            color: Theme.tint(0.1)
                            Rectangle {
                                width: parent.width * Math.min(1, modelData.usedFraction)
                                height: parent.height
                                radius: 3
                                color: modelData.usedFraction > 0.9 ? Theme.flame : (card.usb ? Theme.ok : Theme.accent)
                            }
                        }
                        Text {
                            text: modelData.info
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                        }
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.name + ", " + modelData.info
                }
            }
        }
    }

    component Heading: Text {
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 14
        font.bold: true
    }
}
