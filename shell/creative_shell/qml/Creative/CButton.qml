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
        : (mouse.pressed ? Theme.pressed : (mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06)))

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
