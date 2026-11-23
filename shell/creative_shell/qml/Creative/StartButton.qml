import QtQuick
import Creative

// Startknopf mit der Rakete – rund im Fluid-Design. Leuchtet sanft in der
// Akzentfarbe, stärker, solange das Startmenü offen ist.
Item {
    id: root

    property bool open: false
    signal clicked()
    // Kreis etwas kleiner als der Platz (40): größer als die App-Symbole (30), aber nicht so wuchtig
    readonly property int disc: 34

    implicitWidth: 40
    implicitHeight: 40

    // weiches Leuchten (zwei Ringe, nach außen schwächer)
    Repeater {
        model: [{ grow: 10, a: 0.10 }, { grow: 5, a: 0.18 }]
        delegate: Rectangle {
            required property var modelData
            anchors.centerIn: parent
            width: root.disc + modelData.grow
            height: width
            radius: width / 2
            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b,
                           modelData.a * (root.open ? 1.8 : (mouse.containsMouse ? 1.2 : 0.7)))
            Behavior on color { ColorAnimation { duration: 160 } }
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: root.disc
        height: root.disc
        radius: width / 2
        color: mouse.pressed ? Qt.darker(Theme.accent, 1.15)
                             : (mouse.containsMouse ? Qt.lighter(Theme.accent, 1.08) : Theme.accent)

        // Lichtkante oben – so schmal und tief, dass sie ganz im Kreis liegt
        // (vorher stand sie oben über den Rand hinaus und sah aus wie ein Strich über dem Knopf)
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 3
            width: parent.width * 0.42
            height: 1
            radius: 1
            color: Qt.rgba(1, 1, 1, 0.4)
        }

        SvgIcon {
            anchors.centerIn: parent
            name: "rocket"
            size: 19
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
