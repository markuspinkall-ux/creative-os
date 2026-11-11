import QtQuick
import Creative

// Eine Zeile in der Seitenleiste.
Rectangle {
    id: r
    property string text
    property string icon
    property color chip: "transparent"
    property bool current: false
    property int indent: 0
    property bool ejectable: false
    property string dropTarget: ""     // Ordner (oder "trash"), in den man hier ablegen kann
    signal clicked()
    signal ejectClicked()

    width: parent ? parent.width : 210
    height: 34
    radius: 9
    color: drop.containsDrag ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22)
           : current ? Theme.tint(0.07) : (mouse.containsMouse ? Theme.subtle : "transparent")
    border.color: drop.containsDrag ? Theme.accent : "transparent"

    DropArea {
        id: drop
        anchors.fill: parent
        enabled: r.dropTarget.length > 0
        onEntered: (drag) => { drag.accepted = drag.hasUrls }
        onDropped: (d) => {
            const mode = ((d.modifiers & Qt.ControlModifier) || d.proposedAction === Qt.CopyAction) ? "copy"
                         : ((d.modifiers & Qt.ShiftModifier) ? "move" : "auto")
            fm.dropUrls(d.urls, r.dropTarget, mode)
            d.accept(Qt.CopyAction)
        }
    }

    Row {
        x: 12 + r.indent
        anchors.verticalCenter: parent.verticalCenter
        spacing: 11
        Rectangle {
            visible: r.icon.length === 0
            width: 16; height: 13; radius: 3
            color: r.chip
            anchors.verticalCenter: parent.verticalCenter
        }
        SvgIcon { visible: r.icon.length > 0; name: r.icon; size: 16; anchors.verticalCenter: parent.verticalCenter }
        Text {
            width: r.width - 60 - r.indent - (r.ejectable ? 26 : 0)
            elide: Text.ElideRight
            text: r.text
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.bold: r.current
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: r.clicked() }

    Rectangle {
        visible: r.ejectable
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        width: 26; height: 26; radius: 7
        color: ejectMouse.containsMouse ? Theme.hover : "transparent"
        SvgIcon { anchors.centerIn: parent; name: "eject"; size: 14 }
        MouseArea { id: ejectMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: r.ejectClicked() }
        Accessible.role: Accessible.Button
        Accessible.name: "Auswerfen"
    }

    Accessible.role: Accessible.Button
    Accessible.name: text
}
