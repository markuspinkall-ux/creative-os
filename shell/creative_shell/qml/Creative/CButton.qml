import QtQuick
import Creative

// Textknopf; "primary" für die Hauptaktion in Akzentfarbe.
Rectangle {
    id: btn

    property string text
    property bool primary: false
    property bool danger: false                  // für Löschen u. Ä.: rot
    signal clicked()

    implicitWidth: label.implicitWidth + 28
    implicitHeight: 36
    radius: Theme.radiusRow
    opacity: enabled ? 1 : 0.5
    color: danger
        ? (mouse.pressed ? Qt.darker("#e5484d", 1.15) : (mouse.containsMouse ? "#ec5d62" : "#e5484d"))
        : primary
        ? (mouse.pressed ? Qt.darker(Theme.accent, 1.15) : Theme.accent)
        : (mouse.pressed ? Theme.pressed : (mouse.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06)))

    // Kristall: weicher Glanz von oben und feine Lichtkante
    Rectangle {
        anchors.fill: parent
        radius: btn.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, btn.primary || btn.danger ? 0.20 : (Theme.light ? 0.35 : 0.05)) }
            GradientStop { position: 0.6; color: Qt.rgba(1, 1, 1, 0) }
        }
    }
    Rectangle {
        x: btn.radius
        y: 1
        width: Math.max(0, btn.width - 2 * btn.radius)
        height: 1
        color: Qt.rgba(1, 1, 1, btn.primary || btn.danger ? 0.30 : (Theme.light ? 0.7 : 0.08))
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: btn.text
        color: btn.danger ? "white" : btn.primary ? Theme.accentText : Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        font.bold: true
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: btn.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }

    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: if (enabled) btn.clicked()
}
