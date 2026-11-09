import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Creative

// Lieblingsseiten hinzufügen (Name, Adresse oder RSS-Link) und verwalten.
Item {
    id: sources

    required property QtObject magazine
    signal done()

    component Hint: Label {
        color: Theme.textMuted
        font.pixelSize: 13
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    function add() {
        const value = field.text.trim()
        if (value.length === 0 || magazine.busy !== "")
            return
        magazine.addSource(value)
    }

    Connections {
        target: sources.magazine
        function onSourcesChanged() { field.text = "" }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        Label {
            text: "Deine Quellen"
            color: Theme.text
            font.pixelSize: 26
            font.bold: true
        }
        Hint {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Gib den Namen einer Seite (z. B. ComputerBase), ihre Adresse (z. B. golem.de) oder einen RSS-Link ein. Creative Magazin findet den Feed selbst."
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            TextField {
                id: field
                Layout.fillWidth: true
                implicitHeight: 38
                placeholderText: "Seite suchen oder Adresse eingeben"
                color: Theme.text
                placeholderTextColor: Theme.textMuted
                selectByMouse: true
                leftPadding: 12
                background: Rectangle {
                    color: Theme.surface
                    radius: Theme.radiusRow
                    border.color: field.activeFocus ? Theme.accent : Theme.hairline
                }
                onAccepted: sources.add()
            }
            CButton {
                text: sources.magazine.busy === "add" ? "Sucht …" : "Hinzufügen"
                primary: true
                enabled: sources.magazine.busy === "" && field.text.trim().length > 0
                onClicked: sources.add()
            }
        }

        Hint {
            Layout.fillWidth: true
            visible: text.length > 0
            text: sources.magazine.status
            color: Theme.text
        }

        Label {
            Layout.topMargin: 8
            text: "Beliebte Seiten"
            color: Theme.text
            font.pixelSize: 15
            font.bold: true
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: sources.magazine.catalogue
                delegate: CButton {
                    required property var modelData
                    text: (modelData.added ? "✓  " : "+  ") + modelData.name
                    enabled: !modelData.added && sources.magazine.busy === ""
                    onClicked: sources.magazine.addSource(modelData.name)
                }
            }
        }

        Label {
            Layout.topMargin: 8
            text: "In deinem Magazin"
            color: Theme.text
            font.pixelSize: 15
            font.bold: true
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.surface
            radius: Theme.radiusMenu

            ListView {
                id: list
                anchors.fill: parent
                anchors.margins: 10
                clip: true
                spacing: 4
                model: sources.magazine.sources
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    width: ListView.view.width - 10
                    height: 56
                    radius: Theme.radiusRow
                    color: Theme.subtle
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 12
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Label {
                                Layout.fillWidth: true
                                text: row.modelData.title
                                color: Theme.text
                                font.pixelSize: 14
                                font.bold: true
                                elide: Text.ElideRight
                                textFormat: Text.PlainText
                            }
                            Hint {
                                Layout.fillWidth: true
                                text: row.modelData.home
                                font.pixelSize: 12
                            }
                        }
                        Hint { text: row.modelData.count + " Artikel" }
                        CButton {
                            text: "Entfernen"
                            onClicked: sources.magazine.removeSource(row.modelData.url)
                        }
                    }
                }
                Hint {
                    anchors.centerIn: parent
                    visible: list.count === 0
                    text: "Noch keine Quellen – wähle oben eine beliebte Seite aus."
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            CButton {
                visible: sources.magazine.sources.length > 0
                primary: true
                text: "Zum Heft"
                onClicked: sources.done()
            }
        }
    }
}
