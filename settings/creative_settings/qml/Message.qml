import QtQuick
import Creative

// Hinweiszeile (blau = Info, orange = Problem)
Rectangle {
    id: msg
    property string text
    property bool warning: false
    visible: text.length > 0
    width: parent ? parent.width : 400
    height: label.implicitHeight + 22
    radius: 12
    color: warning ? Qt.rgba(1, 0.69, 0.48, 0.12) : Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12)
    Text {
        id: label
        x: 14
        width: parent.width - 28
        anchors.verticalCenter: parent.verticalCenter
        text: msg.text
        wrapMode: Text.WordWrap
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
    }
}
