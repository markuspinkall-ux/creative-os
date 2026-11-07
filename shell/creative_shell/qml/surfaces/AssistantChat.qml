import QtQuick
import QtQuick.Controls.Basic
import Creative

// Chat-Fenster des Assistenten: sprechen (Mikrofon) oder schreiben.
Item {
    id: root
    property string screenName

    readonly property string st: assistant.state
    readonly property bool busy: st === "listening" || st === "thinking" || st === "speaking"

    function opened() {
        input.text = ""
        input.forceActiveFocus()
        Qt.callLater(() => list.positionViewAtEnd())
    }
    function send() {
        const t = input.text.trim()
        if (!t.length)
            return
        assistant.say(t)
        input.text = ""
    }

    focus: true
    Keys.onEscapePressed: shell.closePopups()

    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }

    Rectangle {
        id: card
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        width: 380
        height: Math.min(parent.height - 10, 540)
        radius: 18
        color: Theme.surface
        border.color: Theme.hairline
        MouseArea { anchors.fill: parent }

        // ---- Kopf ----------------------------------------------------------------
        Item {
            id: head
            x: 16
            y: 12
            width: parent.width - 32
            height: 40
            Rectangle {
                id: logo
                anchors.verticalCenter: parent.verticalCenter
                width: 34; height: 34; radius: 11
                color: root.busy ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22) : Qt.rgba(1, 1, 1, 0.07)
                SvgIcon { anchors.centerIn: parent; visible: !root.busy; name: "mic"; size: 17 }
                // kleiner Visualizer
                Row {
                    anchors.centerIn: parent
                    visible: root.busy
                    spacing: 2
                    Repeater {
                        model: 5
                        delegate: Rectangle {
                            readonly property real shape: [0.55, 0.85, 1.0, 0.8, 0.5][index]
                            property real phase: 0
                            width: 2.5; radius: 1.25
                            anchors.verticalCenter: parent.verticalCenter
                            color: Theme.accent
                            height: root.st === "thinking" ? 4 + 10 * Math.abs(Math.sin(phase + index * 0.7))
                                    : 4 + 14 * shape * Math.min(1, assistant.level * 2.2 + 0.08 * Math.abs(Math.sin(phase + index)))
                            Behavior on height { NumberAnimation { duration: 70 } }
                            NumberAnimation on phase { running: root.busy; from: 0; to: Math.PI * 2; duration: 900; loops: Animation.Infinite }
                        }
                    }
                }
            }
            Column {
                anchors.left: logo.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                Text { text: "Assistent"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                Text {
                    text: root.st === "listening" ? "Ich höre zu …"
                          : root.st === "thinking" ? "Einen Moment …"
                          : root.st === "speaking" ? "Spricht …"
                          : "Sprechen oder schreiben"
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                }
            }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                IconButton { width: 30; height: 30; icon: "refresh"; iconSize: 14; label: "Verlauf leeren"; onClicked: assistant.clearHistory() }
                IconButton { width: 30; height: 30; icon: "close"; iconSize: 14; label: "Schließen"; onClicked: shell.closePopups() }
            }
        }

        Rectangle { y: head.y + head.height + 10; width: parent.width; height: 1; color: Theme.hairline }

        // ---- Verlauf ----------------------------------------------------------------
        ListView {
            id: list
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: head.bottom
            anchors.bottom: inputBar.top
            anchors.margins: 14
            anchors.topMargin: 22
            spacing: 8
            clip: true
            model: assistant.history
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            onCountChanged: Qt.callLater(() => positionViewAtEnd())

            delegate: Item {
                readonly property bool mine: modelData.who === "user"
                width: list.width
                height: bubble.height
                Rectangle {
                    id: bubble
                    anchors.right: parent.mine ? parent.right : undefined
                    anchors.left: parent.mine ? undefined : parent.left
                    width: Math.min(list.width * 0.82, Math.max(msg.implicitWidth, sourceLink.visible ? sourceLink.implicitWidth : 0) + 24)
                    height: msg.implicitHeight + (sourceLink.visible ? sourceLink.implicitHeight + 5 : 0) + 16
                    radius: 14
                    color: parent.mine ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2) : Theme.raised
                    Text {
                        id: msg
                        x: 12
                        y: 8
                        width: Math.min(list.width * 0.82 - 24, implicitWidth)
                        text: modelData.text
                        wrapMode: Text.Wrap
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        textFormat: Text.PlainText
                    }
                    Text {
                        id: sourceLink
                        x: 12
                        y: msg.y + msg.implicitHeight + 5
                        visible: typeof modelData.source === "string"
                                 && /^https:\/\/de\.wikipedia\.org\/\?curid=\d+$/.test(modelData.source)
                        text: "Artikel auf Wikipedia öffnen"
                        color: Theme.accent
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.underline: true
                        Accessible.role: Accessible.Link
                        Accessible.name: text
                        Accessible.onPressAction: if (visible) Qt.openUrlExternally(modelData.source)
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.openUrlExternally(modelData.source)
                        }
                    }
                }
            }
        }

        // ---- Eingabe -------------------------------------------------------------------
        Item {
            id: inputBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 12
            height: 44

            Rectangle {
                anchors.left: parent.left
                anchors.right: micBtn.left
                anchors.rightMargin: 8
                height: parent.height
                radius: 22
                color: Theme.ground
                border.color: input.activeFocus ? Theme.accent : Theme.hairline
                TextField {
                    id: input
                    anchors.fill: parent
                    anchors.rightMargin: 44
                    leftPadding: 16
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    placeholderText: "Schreib z. B. „Wetter morgen“ …"
                    placeholderTextColor: Theme.textMuted
                    background: null
                    onAccepted: root.send()
                    onTextEdited: if (assistant.state === "listening") assistant.cancel()
                }
                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: 5
                    anchors.verticalCenter: parent.verticalCenter
                    width: 34; height: 34; radius: 17
                    color: input.text.trim().length ? Theme.accent : Qt.rgba(1, 1, 1, 0.06)
                    Text {
                        anchors.centerIn: parent
                        text: "↑"
                        color: input.text.trim().length ? Theme.accentText : Theme.textMuted
                        font.pixelSize: 17
                        font.bold: true
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.send() }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Senden"
                }
            }
            Rectangle {
                id: micBtn
                anchors.right: parent.right
                width: 44; height: 44; radius: 22
                color: root.st === "listening" ? Theme.accent : (mm.containsMouse ? Theme.hover : Qt.rgba(1, 1, 1, 0.06))
                SvgIcon { anchors.centerIn: parent; name: root.st === "listening" ? "mic-dark" : "mic"; size: 18 }
                MouseArea {
                    id: mm
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: assistant.activate()
                }
                Accessible.role: Accessible.Button
                Accessible.name: root.st === "listening" ? "Zuhören beenden" : "Sprechen"
            }
        }
    }
}
