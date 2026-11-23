import QtQuick
import Creative

// Startknopf mit der Rakete – rund im Fluid-Design. Leuchtet sanft in der
// Akzentfarbe, stärker, solange das Startmenü offen ist.
Item {
    id: root

    property bool open: false
    signal clicked()
    function fly() { launch.restart() }
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

        // Rakete im Kreis; beim Klick schießt sie nach oben hinaus und kommt von unten wieder herein
        Item {
            id: flight
            anchors.fill: parent
            clip: true
            property real lift: 0          // Versatz nach oben (Pixel)
            property real streak: 0        // Stärke der Geschwindigkeitsstriche (0…1)

            // Geschwindigkeitsstriche unter der Rakete
            Repeater {
                model: [-5, 0, 5]
                delegate: Rectangle {
                    required property var modelData
                    x: flight.width / 2 + modelData - 1
                    y: flight.height / 2 + 6 - flight.lift + (modelData === 0 ? 2 : 6)
                    width: 2
                    height: 6 + 10 * flight.streak
                    radius: 1
                    color: Theme.accentText
                    opacity: 0.55 * flight.streak
                }
            }
            SvgIcon {
                id: rocketIcon
                anchors.horizontalCenter: parent.horizontalCenter
                y: (parent.height - height) / 2 - flight.lift
                name: "rocket"
                size: 19
            }
        }
    }

    SequentialAnimation {
        id: launch
        ParallelAnimation {
            NumberAnimation { target: flight; property: "lift"; from: 0; to: 4; duration: 90; easing.type: Easing.OutQuad }
            NumberAnimation { target: flight; property: "streak"; from: 0; to: 0.6; duration: 90 }
        }
        ParallelAnimation {
            NumberAnimation { target: flight; property: "lift"; from: 4; to: root.disc; duration: 200; easing.type: Easing.InQuad }
            NumberAnimation { target: flight; property: "streak"; from: 0.6; to: 1; duration: 200 }
        }
        PropertyAction { target: flight; property: "lift"; value: -root.disc }
        ParallelAnimation {
            NumberAnimation { target: flight; property: "lift"; from: -root.disc; to: 0; duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
            NumberAnimation { target: flight; property: "streak"; from: 1; to: 0; duration: 320; easing.type: Easing.OutQuad }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.fly(); root.clicked() }
    }

    Accessible.role: Accessible.Button
    Accessible.name: "Startmenü"
    Accessible.onPressAction: root.clicked()
}
