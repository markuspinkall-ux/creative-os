import QtQuick
import QtQuick.Window
import Creative
import org.kde.layershell 1.0 as LayerShell

// Benachrichtigungen unten rechts über der Taskleiste (wie bei Windows 11)
Window {
    id: win
    width: 392
    height: Math.max(1, stack.implicitHeight + 16)
    visible: center.items.length > 0
    color: "transparent"
    title: "Creative Benachrichtigungen"

    LayerShell.Window.scope: "creative-notifications"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorRight | LayerShell.Window.AnchorBottom
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    Column {
        id: stack
        x: 6
        y: 8
        width: parent.width - 12
        spacing: 10

        Repeater {
            model: center.items
            delegate: Rectangle {
                id: toast
                required property var modelData
                width: stack.width
                height: body.implicitHeight + 28
                radius: 16
                color: Theme.raised
                border.color: modelData.critical ? Qt.rgba(1, 0.69, 0.48, 0.6) : Theme.hairline
                border.width: 1

                // hereingleiten
                property real slide: 40
                transform: Translate { x: toast.slide }
                opacity: 1 - toast.slide / 60
                Component.onCompleted: slideIn.start()
                NumberAnimation { id: slideIn; target: toast; property: "slide"; from: 40; to: 0; duration: 220; easing.type: Easing.OutCubic }

                // läuft ab (pausiert, solange die Maus darauf liegt)
                Timer {
                    interval: Math.max(1500, toast.modelData.timeout)
                    running: toast.modelData.timeout > 0 && !hover.containsMouse
                    onTriggered: center.expire(toast.modelData.id)
                }

                MouseArea {
                    id: hover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: toast.modelData.hasDefault ? center.invoke(toast.modelData.id, "default") : center.close(toast.modelData.id)
                }

                Row {
                    id: body
                    x: 14
                    y: 14
                    width: parent.width - 28
                    spacing: 12

                    Item {
                        id: appIcon
                        width: 34; height: 34
                        readonly property bool known: center.iconOk(toast.modelData.icon)
                        Image {
                            visible: appIcon.known
                            anchors.fill: parent
                            sourceSize.width: 68; sourceSize.height: 68
                            source: appIcon.known ? "image://icon/" + toast.modelData.icon : ""
                            asynchronous: true
                            smooth: true
                        }
                        // ohne Symbol: Glocke auf Creative-Kachel
                        Rectangle {
                            visible: !appIcon.known
                            anchors.fill: parent
                            radius: 10
                            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2)
                            SvgIcon { anchors.centerIn: parent; name: "info"; size: 18 }
                        }
                    }
                    Column {
                        width: parent.width - appIcon.width - 12 - 22
                        spacing: 3
                        Text {
                            visible: toast.modelData.app.length > 0
                            width: parent.width
                            text: toast.modelData.app
                            elide: Text.ElideRight
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                        }
                        Text {
                            width: parent.width
                            text: toast.modelData.summary
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                        }
                        Text {
                            visible: toast.modelData.body.length > 0
                            width: parent.width
                            text: toast.modelData.body
                            textFormat: Text.StyledText
                            wrapMode: Text.WordWrap
                            maximumLineCount: 4
                            elide: Text.ElideRight
                            color: Theme.text
                            opacity: 0.85
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                        }
                        Flow {
                            visible: toast.modelData.actions.length > 0
                            width: parent.width
                            spacing: 6
                            topPadding: 6
                            Repeater {
                                model: toast.modelData.actions
                                delegate: CButton {
                                    required property var modelData
                                    text: modelData.label
                                    onClicked: center.invoke(toast.modelData.id, modelData.key)
                                }
                            }
                        }
                    }
                }

                // Schließen
                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 8
                    width: 22; height: 22; radius: 11
                    visible: hover.containsMouse || closeMouse.containsMouse
                    color: closeMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.07)
                    Text { anchors.centerIn: parent; text: "×"; color: Theme.text; font.pixelSize: 15 }
                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: center.close(toast.modelData.id)
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Benachrichtigung schließen"
                }

                Accessible.role: Accessible.AlertMessage
                Accessible.name: modelData.summary + ". " + modelData.body
            }
        }
    }
}
