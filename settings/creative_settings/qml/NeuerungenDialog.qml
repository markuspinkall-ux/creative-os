import QtQuick
import QtQuick.Controls.Basic
import Creative

// „Was ist neu?“ – alle Neuerungen, Verbesserungen und Fehlerbehebungen als Graphit-Fenster.
//   NeuerungenDialog { id: news; entries: system.changelog }
//   news.open()
Popup {
    id: dialog
    property var entries: []
    property string version: ""

    readonly property var groups: [
        { key: "neu", label: "Neu", color: Theme.accent },
        { key: "verbessert", label: "Verbessert", color: Theme.ok },
        { key: "behoben", label: "Behoben", color: Theme.flame }
    ]

    function count(key) {
        let n = 0
        for (const e of entries) n += (e[key] || []).length
        return n
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(760, parent ? parent.width - 60 : 760)
    height: Math.min(parent ? parent.height - 60 : 700, 820)
    modal: true
    focus: true
    padding: 0
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.55) }
    background: Rectangle { radius: 20; color: Theme.surface; border.color: Theme.hairline }
    onOpened: list.positionViewAtBeginning()

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140 }
        NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: 160; easing.type: Easing.OutCubic }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100 } }

    contentItem: Item {
        // ---- Kopf ----
        Item {
            id: head
            width: parent.width
            height: 118
            Rectangle {
                x: 26; y: 26
                width: 48; height: 48; radius: 14
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                SvgIcon { anchors.centerIn: parent; name: "rocket"; size: 24 }
            }
            Column {
                x: 90; y: 26
                width: parent.width - 90 - 70
                spacing: 4
                Text {
                    text: "Was ist neu in Creative OS"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 20
                    font.bold: true
                }
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: dialog.version ? "Du nutzt Creative OS " + dialog.version : "Alle Neuerungen und Überarbeitungen"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
            IconButton {
                anchors.right: parent.right
                anchors.rightMargin: 20
                y: 22
                icon: "close"
                iconSize: 18
                onClicked: dialog.close()
                Accessible.name: "Schließen"
            }
            // Zusammenfassung
            Row {
                x: 90; y: 84
                spacing: 8
                Repeater {
                    model: dialog.groups
                    delegate: Rectangle {
                        height: 24
                        width: chip.implicitWidth + 20
                        radius: 12
                        color: Qt.rgba(modelData.color.r, modelData.color.g, modelData.color.b, 0.14)
                        Text {
                            id: chip
                            anchors.centerIn: parent
                            text: dialog.count(modelData.key) + " " + modelData.label.toLowerCase()
                            color: modelData.color
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hairline }
        }

        // ---- Liste ----
        ListView {
            id: list
            anchors.top: head.bottom
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            width: parent.width
            clip: true
            model: dialog.entries
            topMargin: 18
            bottomMargin: 20
            spacing: 14
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.track }
            }

            delegate: Item {
              id: day
              required property var modelData
              required property int index
              width: list.width
              height: card.height
              Rectangle {
                id: card
                x: 22
                width: parent.width - 44
                height: body.implicitHeight + 36
                radius: 16
                color: Qt.rgba(1, 1, 1, 0.03)
                border.color: index === 0 ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.35) : "transparent"

                Column {
                    id: body
                    x: 20; y: 18
                    width: parent.width - 40
                    spacing: 10

                    Row {
                        spacing: 10
                        width: parent.width
                        Text {
                            id: dateText
                            anchors.verticalCenter: parent.verticalCenter
                            text: day.modelData.tag
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.bold: true
                            font.capitalization: Font.AllUppercase
                            font.letterSpacing: 0.6
                        }
                        Rectangle {
                            visible: day.index === 0
                            anchors.verticalCenter: parent.verticalCenter
                            height: 20
                            width: latest.implicitWidth + 16
                            radius: 10
                            color: Theme.accent
                            Text {
                                id: latest
                                anchors.centerIn: parent
                                text: "Neueste"
                                color: Theme.accentText
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: day.modelData.titel
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 16
                        font.bold: true
                    }

                    Repeater {
                        model: dialog.groups
                        delegate: Column {
                            id: group
                            required property var modelData
                            readonly property var items: day.modelData[modelData.key] || []
                            visible: items.length > 0
                            width: body.width
                            spacing: 6
                            topPadding: 4
                            Rectangle {
                                height: 22
                                width: label.implicitWidth + 18
                                radius: 7
                                color: Qt.rgba(group.modelData.color.r, group.modelData.color.g, group.modelData.color.b, 0.15)
                                Text {
                                    id: label
                                    anchors.centerIn: parent
                                    text: group.modelData.label
                                    color: group.modelData.color
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                            }
                            Repeater {
                                model: group.items
                                delegate: Item {
                                    required property string modelData
                                    width: group.width
                                    height: line.implicitHeight + 2
                                    Rectangle {
                                        x: 4; y: 7
                                        width: 5; height: 5; radius: 2.5
                                        color: group.modelData.color
                                    }
                                    Text {
                                        id: line
                                        x: 18
                                        width: parent.width - 18
                                        wrapMode: Text.WordWrap
                                        text: parent.modelData
                                        color: Theme.text
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 13
                                        lineHeight: 1.25
                                    }
                                }
                            }
                        }
                    }
                }
              }
            }

            Text {
                visible: dialog.entries.length === 0
                anchors.centerIn: parent
                text: "Keine Neuerungen gefunden."
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
        }
    }
}
