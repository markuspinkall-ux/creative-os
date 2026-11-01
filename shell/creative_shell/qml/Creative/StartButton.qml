import QtQuick
import Creative

// Startknopf mit der Creative-Rakete. Leuchtet mit einem Ring, solange das
// Startmenü offen ist.
Item {
    id: root

    property bool open: false
    signal clicked()

    implicitWidth: 44
    implicitHeight: 44

    Rectangle {
        anchors.centerIn: parent
        width: 50
        height: 50
        radius: 15
        color: "transparent"
        border.width: 3
        border.color: Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.35)
        visible: root.open
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusButton
        color: mouse.pressed ? Qt.darker(Theme.accent, 1.15)
                             : (mouse.containsMouse ? Qt.lighter(Theme.accent, 1.08) : Theme.accent)

        SvgIcon {
            anchors.centerIn: parent
            name: "rocket"
            size: 26
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Accessible.role: Accessible.Button
    Accessible.name: "Startmenü"
    Accessible.onPressAction: root.clicked()
}
