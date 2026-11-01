import QtQuick
import Creative

// Ein/Aus-Schalter im Graphit-Look.
Rectangle {
    id: sw

    property bool checked: false
    property string label
    signal toggled(bool value)

    implicitWidth: 40
    implicitHeight: 22
    radius: 11
    color: checked ? Theme.accent : Theme.track
    Behavior on color { ColorAnimation { duration: 120 } }

    Rectangle {
        width: 16
        height: 16
        radius: 8
        y: 3
        x: sw.checked ? 21 : 3
        color: "white"
        Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -8   // größere Klickfläche
        cursorShape: Qt.PointingHandCursor
        onClicked: sw.toggled(!sw.checked)
    }

    Accessible.role: Accessible.CheckBox
    Accessible.name: label
    Accessible.checkable: true
    Accessible.checked: checked
    Accessible.onToggleAction: sw.toggled(!sw.checked)
}
