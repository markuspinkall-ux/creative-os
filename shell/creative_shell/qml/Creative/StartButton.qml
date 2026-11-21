import QtQuick
import Creative

// Startknopf mit der Rakete – rund im Fluid-Design. Leuchtet sanft in der
// Akzentfarbe, stärker, solange das Startmenü offen ist.
Item {
    id: root

    property bool open: false
    signal clicked()

    implicitWidth: 40
    implicitHeight: 40

    // weiches Leuchten (zwei Ringe, nach außen schwächer)
    Repeater {
        model: [{ grow: 12, a: 0.10 }, { grow: 6, a: 0.18 }]
        delegate: Rectangle {
            required property var modelData
            anchors.centerIn: parent
            width: root.width + modelData.grow
            height: width
            radius: width / 2
            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b,
                           modelData.a * (root.open ? 1.8 : (mouse.containsMouse ? 1.2 : 0.7)))
            Behavior on color { ColorAnimation { duration: 160 } }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: mouse.pressed ? Qt.darker(Theme.accent, 1.15)
                             : (mouse.containsMouse ? Qt.lighter(Theme.accent, 1.08) : Theme.accent)

        // Lichtkante oben
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 1
            width: parent.width * 0.55
            height: 1
            radius: 1
            color: Qt.rgba(1, 1, 1, 0.45)
        }

        SvgIcon {
            anchors.centerIn: parent
            name: "rocket"
            size: 22
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
