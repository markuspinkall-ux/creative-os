import QtQuick
import Creative

// Kleiner Hinweis unter einem Knopf (erscheint nach kurzem Zeigen).
Rectangle {
    id: t
    property string text
    property bool shown: false

    visible: opacity > 0
    opacity: 0
    z: 100
    anchors.top: parent.bottom
    anchors.topMargin: 6
    anchors.horizontalCenter: parent.horizontalCenter
    width: label.implicitWidth + 16
    height: 26
    radius: 7
    color: Theme.raised
    border.color: Theme.hairline

    Text {
        id: label
        anchors.centerIn: parent
        text: t.text
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }

    Timer { id: delay; interval: 600; onTriggered: t.opacity = 1 }
    onShownChanged: { if (shown) delay.start(); else { delay.stop(); opacity = 0 } }
    Behavior on opacity { NumberAnimation { duration: 120 } }
}
