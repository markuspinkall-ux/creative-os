import QtQuick
import QtQuick.Controls.Basic
import Creative

// Liste für Musik oder Videos: Suche, Spaltenkopf, ein Klick spielt ab.
Item {
    id: root

    property var model
    property string heading
    property string emptyText
    property string playingUrl
    property bool showAlbum: true

    signal play(int row)

    Text {
        id: title
        x: 28
        y: 24
        text: root.heading
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 24
        font.bold: true
    }
    Text {
        anchors.left: title.left
        anchors.top: title.bottom
        anchors.topMargin: 4
        text: root.model.scanning ? "Wird eingelesen …"
            : (root.model.filterText.length > 0 ? root.model.count + " von " + root.model.total + " Einträgen"
                                                 : root.model.total + (root.model.total === 1 ? " Eintrag" : " Einträge"))
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 28
        y: 26
        spacing: 8

        TextField {
            id: search
            width: 280
            height: 38
            leftPadding: 38
            placeholderText: root.showAlbum ? "Titel, Künstler, Album" : "Video suchen"
            placeholderTextColor: Theme.textMuted
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            selectByMouse: true
            background: Rectangle { radius: 19; color: Theme.ground; border.color: search.activeFocus ? Theme.accent : Theme.hairline; border.width: 1 }
            SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 15 }
            onTextChanged: root.model.filterText = text
            Accessible.name: "Suchen"
        }
        IconButton {
            width: 38
            height: 38
            icon: "refresh"
            iconSize: 17
            label: "Neu einlesen"
            onClicked: root.model.rescan()
        }
    }

    // Spaltenkopf
    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        y: 92
        height: 30
        Row {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            Text { width: 48; text: "#"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
            Text { width: (parent.width - 128) * 0.5; text: "Titel"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
            Text { width: (parent.width - 128) * 0.5; text: root.showAlbum ? "Künstler · Album" : "Ordner"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
            Text { width: 80; horizontalAlignment: Text.AlignRight; text: "Dauer"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    ListView {
        id: list
        anchors.left: header.left
        anchors.right: header.right
        anchors.top: header.bottom
        anchors.topMargin: 6
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 8
        clip: true
        model: root.model
        spacing: 2
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.2) }
        }

        delegate: Rectangle {
            id: row
            required property int index
            required property string title
            required property string subtitle
            required property string duration
            required property string url
            readonly property bool current: url === root.playingUrl

            width: ListView.view.width
            height: 42
            radius: Theme.radiusRow
            color: current ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.12)
                           : (rowMouse.containsMouse ? Theme.hover : "transparent")

            Row {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                Item {
                    width: 48
                    height: parent.height
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !row.current
                        text: row.index + 1
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    SvgIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: row.current
                        name: "play"
                        size: 14
                    }
                }
                Text {
                    width: (parent.width - 128) * 0.5
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.title
                    elide: Text.ElideRight
                    color: row.current ? Theme.accent : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: row.current
                }
                Text {
                    width: (parent.width - 128) * 0.5
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.subtitle
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                Text {
                    width: 80
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignRight
                    text: row.duration
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }

            MouseArea {
                id: rowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.play(row.index)
            }
            Accessible.role: Accessible.ListItem
            Accessible.name: row.title + ", " + row.subtitle
            Accessible.onPressAction: root.play(row.index)
        }
    }

    Column {
        anchors.centerIn: list
        width: Math.min(420, list.width - 40)
        spacing: 14
        visible: list.count === 0 && !root.model.scanning

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.model.filterText.length > 0 ? "Nichts gefunden." : root.emptyText
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }
        CButton {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.model.filterText.length === 0
            text: "Ordner öffnen"
            onClicked: Qt.openUrlExternally("file://" + root.model.folder)
        }
    }
}
