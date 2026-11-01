import QtQuick
import Creative

// Eine Zeile: links Bezeichnung (+ Hinweis), rechts Bedienelement.
Item {
    id: row
    property string label
    property string hint
    property bool last: false
    default property alias control: slot.data

    width: parent ? parent.width : 500
    implicitHeight: Math.max(50, texts.implicitHeight + 20, slot.childrenRect.height + 16)

    Column {
        id: texts
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - slot.childrenRect.width - 24
        spacing: 2
        Text {
            width: parent.width
            text: row.label
            wrapMode: Text.WordWrap
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
        Text {
            visible: row.hint.length > 0
            width: parent.width
            text: row.hint
            wrapMode: Text.WordWrap
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 11
        }
    }
    Item {
        id: slot
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: childrenRect.width
        height: childrenRect.height
    }
    Rectangle {
        visible: !row.last
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Qt.rgba(1, 1, 1, 0.05)
    }
}
