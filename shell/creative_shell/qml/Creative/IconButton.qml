import QtQuick
import Creative

// Quadratischer Knopf mit Symbol, z. B. für angeheftete Apps.
Rectangle {
    id: btn

    property string icon
    property int iconSize: 22
    property bool active: false
    property string label

    signal clicked()

    implicitWidth: 44
    implicitHeight: 44
    radius: Theme.radiusButton
    color: mouse.pressed ? Theme.pressed : ((mouse.containsMouse || active) ? Theme.hover : "transparent")

    SvgIcon {
        anchors.centerIn: parent
        name: btn.icon
        size: btn.iconSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }

    Accessible.role: Accessible.Button
    Accessible.name: label
    Accessible.onPressAction: btn.clicked()
}
