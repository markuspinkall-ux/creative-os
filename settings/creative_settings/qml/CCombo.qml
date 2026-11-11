import QtQuick
import QtQuick.Controls.Basic
import Creative

// Auswahlfeld (z. B. Auflösung). model: Liste von Texten.
Rectangle {
    id: box
    property var model: []
    property string value
    property string label
    signal activated(string text)

    implicitWidth: Math.max(170, valueText.implicitWidth + 50)
    implicitHeight: 34
    radius: 8
    opacity: enabled ? 1 : 0.45
    color: mouse.containsMouse && enabled ? Theme.tint(0.1) : Theme.tint(0.06)

    Text {
        id: valueText
        x: 12
        anchors.verticalCenter: parent.verticalCenter
        text: box.value
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        font.bold: true
    }
    SvgIcon {
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        name: "chevron-down"
        size: 11
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: box.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: list.open()
    }

    Popup {
        id: list
        y: box.height + 4
        width: Math.max(box.width, 180)
        padding: 6
        height: Math.min(contentCol.implicitHeight + 12, 320)
        background: Rectangle { radius: 12; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Flickable {
            contentHeight: contentCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            Column {
                id: contentCol
                width: parent.width
                Repeater {
                    model: box.model
                    delegate: Rectangle {
                        width: contentCol.width
                        height: 34
                        radius: 8
                        color: im.containsMouse ? Theme.tint(0.08)
                                                : (modelData === box.value ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14) : "transparent")
                        Text {
                            x: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: modelData === box.value
                        }
                        MouseArea {
                            id: im
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: { list.close(); if (modelData !== box.value) box.activated(modelData) }
                        }
                    }
                }
            }
        }
    }

    Accessible.role: Accessible.ComboBox
    Accessible.name: label + ": " + value
}
