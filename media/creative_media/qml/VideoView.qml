import QtQuick
import QtMultimedia
import Creative

// Video-Wiedergabe im Fenster. Doppelklick → Vollbild.
Item {
    id: root

    property string title
    property alias videoOutput: video

    signal back()
    signal fullscreenRequested()

    Rectangle {
        anchors.fill: parent
        anchors.margins: 20
        radius: 14
        color: "#0b0d11"
        clip: true

        VideoOutput {
            id: video
            anchors.fill: parent
            fillMode: VideoOutput.PreserveAspectFit
        }

        MouseArea {
            anchors.fill: parent
            onDoubleClicked: root.fullscreenRequested()
        }

        Row {
            x: 16
            y: 16
            spacing: 8
            CButton {
                text: "‹  Zur Liste"
                onClicked: root.back()
            }
            CButton {
                text: "Vollbild"
                onClicked: root.fullscreenRequested()
            }
        }

        Text {
            anchors.right: parent.right
            anchors.rightMargin: 20
            y: 26
            width: parent.width * 0.5
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideLeft
            text: root.title
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 14
            font.bold: true
        }
    }
}
