import QtQuick
import Creative

// Kristall-Glanz für Glasflächen: weicher Glanz an der Oberkante und auf Wunsch ein
// feiner schräger Lichtstreif. Liegt über dem Glas und unter dem Inhalt, nimmt keine Klicks an.
//   Rectangle { radius: 18; …; GlassSheen { radius: parent.radius } }
Item {
    id: sheen

    property real radius: 0
    property bool streak: true                 // Lichtstreif (große Flächen: Startmenü, Widgets)
    property real strength: 1.0

    anchors.fill: parent
    enabled: false

    // Glanz von oben, läuft nach etwa 60 px aus
    Rectangle {
        anchors.fill: parent
        radius: sheen.radius
        visible: Theme.sheenTop > 0
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, Theme.sheenTop * sheen.strength) }
            GradientStop { position: Math.min(0.45, 60 / Math.max(1, sheen.height)); color: Qt.rgba(1, 1, 1, 0) }
        }
    }

    // Schräger Lichtstreif – bleibt von den runden Ecken weg
    Item {
        anchors.fill: parent
        anchors.leftMargin: sheen.radius
        anchors.rightMargin: sheen.radius
        clip: true
        visible: sheen.streak && Theme.sheenStreak > 0 && sheen.width > 2 * sheen.radius + 40
        Rectangle {
            width: Math.max(40, parent.width * 0.22)
            height: sheen.height * 2.4
            x: parent.width * 0.36
            y: -sheen.height * 0.7
            rotation: 24
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0) }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, Theme.sheenStreak * sheen.strength) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0) }
            }
        }
    }
}
