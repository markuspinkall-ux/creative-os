import QtQuick
import Creative

Item {
    id: head
    property string title
    property string subtitle
    default property alias actions: actionRow.data

    width: parent ? parent.width : 800
    height: 56

    Column {
        anchors.verticalCenter: parent.verticalCenter
        spacing: 3
        Text { text: head.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 24; font.bold: true }
        Text {
            visible: head.subtitle.length > 0
            text: head.subtitle
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
    }
    Row {
        id: actionRow
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
    }
}
