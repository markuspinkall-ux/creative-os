import QtQuick
import Creative

// Sprechblase über dem Tray: was gehört wurde und was der Assistent antwortet.
// Verschwindet von selbst, sobald der Assistent fertig ist.
Item {
    id: root
    property string screenName

    readonly property string st: assistant.state
    readonly property bool busy: st === "listening" || st === "thinking" || st === "speaking" || st === "alarm"

    Connections {
        target: assistant
        function onChanged() { hide.restart() }
    }
    Timer {
        id: hide
        interval: 6000
        running: true
        onTriggered: { if (!root.busy) shell.hideBubble(); else restart() }
    }

    Rectangle {
        id: card
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        width: 380
        height: col.implicitHeight + 28
        radius: 16
        color: Theme.raised
        border.color: root.st === "alarm" ? Theme.flame : Theme.hairline

        MouseArea { anchors.fill: parent; onClicked: shell.hideBubble() }

        Column {
            id: col
            x: 16
            y: 14
            width: parent.width - 32
            spacing: 6
            Row {
                spacing: 8
                Rectangle {
                    width: 8; height: 8; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.st === "alarm" ? Theme.flame : (root.busy ? Theme.accent : Theme.ok)
                }
                Text {
                    text: root.st === "listening" ? "Ich höre zu …"
                          : root.st === "thinking" ? "Einen Moment …"
                          : root.st === "alarm" ? "Timer abgelaufen"
                          : "Assistent"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.bold: true
                }
            }
            Text {
                visible: assistant.heard.length > 0 && root.st !== "listening"
                width: parent.width
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                text: "„" + assistant.heard + "“"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.italic: true
            }
            Text {
                visible: assistant.answer.length > 0 && root.st !== "listening"
                width: parent.width
                wrapMode: Text.WordWrap
                maximumLineCount: 4
                elide: Text.ElideRight
                text: assistant.answer
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
            }
            Text {
                visible: root.st === "listening"
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Zum Beispiel: „Wie wird das Wetter morgen?“, „Timer auf 10 Minuten“ oder „Spiele Musik von Queen“"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }
    }
}
