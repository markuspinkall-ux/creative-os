import QtQuick
import Creative

// Knopf der Werkzeugleiste: Symbol + optional Text.
Rectangle {
    id: b
    property string icon
    property string text
    property string tip
    property bool primary: false
    property bool checked: false
    signal clicked()

    implicitHeight: 34
    implicitWidth: row.implicitWidth + (text.length ? 24 : 0) + (text.length ? 0 : 34 - row.implicitWidth)
    radius: 9
    opacity: enabled ? 1 : 0.4
    color: primary ? (mouse.pressed ? Qt.darker(Theme.accent, 1.15) : Theme.accent)
                   : (mouse.pressed ? Theme.pressed : ((mouse.containsMouse || checked) && enabled ? Theme.hover : "transparent"))

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 8
        SvgIcon { name: b.icon; size: 15; anchors.verticalCenter: parent.verticalCenter; visible: b.icon.length > 0 }
        Text {
            visible: b.text.length > 0
            text: b.text
            anchors.verticalCenter: parent.verticalCenter
            color: b.primary ? Theme.accentText : Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.bold: b.primary
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: b.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: b.clicked()
    }

    Tip { text: b.tip; shown: mouse.containsMouse && b.tip.length > 0 }

    Accessible.role: Accessible.Button
    Accessible.name: text.length ? text : tip
    Accessible.onPressAction: if (enabled) b.clicked()
}
