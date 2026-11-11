import QtQuick
import QtQuick.Controls.Basic
import Creative

// Inhalt eines Ordners oder des Papierkorbs – als Liste oder Kacheln.
Item {
    id: view
    signal itemMenu(Item source, real x, real y)
    signal backgroundMenu(Item source, real x, real y)

    readonly property bool trash: fm.page === "trash"
    readonly property var cols: [2.4, 1.2, 1, 0.8]
    readonly property real colUnit: (list.width - 24) / 5.4

    function modeFor(mouse) {
        if (mouse.modifiers & Qt.ShiftModifier) return "range"
        if (mouse.modifiers & Qt.ControlModifier) return "toggle"
        return "single"
    }

    function pressItem(row, mouse, item) {
        if (mouse.button === Qt.RightButton) {
            fm.select(row, "keep")
            view.itemMenu(item, mouse.x, mouse.y)
        } else {
            fm.select(row, modeFor(mouse))
        }
    }

    // Klick ins Leere hebt die Auswahl auf (liegt unter den Einträgen)
    component EmptyArea: MouseArea {
        id: area
        anchors.fill: parent
        z: -1
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => {
            fm.clearSelection()
            if (mouse.button === Qt.RightButton)
                view.backgroundMenu(area, mouse.x, mouse.y)
        }
    }

    // ---- Liste ---------------------------------------------------------------
    Item {
        id: header
        visible: fm.view === "list"
        x: 20; y: 12
        width: parent.width - 40
        height: 36
        Row {
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            HeaderText { width: view.colUnit * 2.4; text: "Name" }
            HeaderText { width: view.colUnit * 1.2; text: view.trash ? "Gelöscht" : "Geändert" }
            HeaderText { width: view.colUnit * 1.0; text: view.trash ? "Ursprünglicher Ort" : "Typ" }
            HeaderText { width: view.colUnit * 0.8; text: "Größe"; horizontalAlignment: Text.AlignRight }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.tint(0.06) }
    }

    EmptyArea {}

    ListView {
        id: list
        visible: fm.view === "list"
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 52
        anchors.bottomMargin: 8
        clip: true
        spacing: 2
        model: fm.files
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        reuseItems: true
        EmptyArea { parent: list }

        delegate: Rectangle {
            id: row
            width: list.width
            height: 40
            radius: 9
            color: model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                                  : (m.containsMouse ? Theme.subtle : "transparent")
            border.color: model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55) : "transparent"

            Row {
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                Item {
                    width: view.colUnit * 2.4
                    height: 40
                    FileGlyph {
                        size: 20
                        isDir: model.isDir
                        tint: model.tint
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        x: 32
                        width: parent.width - 44
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.name
                        elide: Text.ElideMiddle
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: model.selected
                    }
                }
                Cell { width: view.colUnit * 1.2; text: model.dateText }
                Cell { width: view.colUnit * 1.0; text: view.trash ? model.extra : model.typeName }
                Cell { width: view.colUnit * 0.8; text: model.sizeText; horizontalAlignment: Text.AlignRight }
            }

            MouseArea {
                id: m
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onPressed: (mouse) => view.pressItem(index, mouse, row)
                onDoubleClicked: (mouse) => { if (mouse.button === Qt.LeftButton) fm.activate(index) }
            }
            Accessible.role: Accessible.ListItem
            Accessible.name: model.name
        }
    }

    // ---- Kacheln -------------------------------------------------------------
    GridView {
        id: grid
        visible: fm.view === "tiles"
        anchors.fill: parent
        anchors.margins: 16
        clip: true
        model: fm.files
        cellWidth: Math.floor(width / Math.max(1, Math.floor(width / 128)))
        cellHeight: 132
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        EmptyArea { parent: grid }

        delegate: Item {
            width: grid.cellWidth
            height: grid.cellHeight
            Rectangle {
                id: tile
                anchors.fill: parent
                anchors.margins: 4
                radius: 12
                color: model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                                      : (tm.containsMouse ? Theme.subtle : "transparent")
                border.color: model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55) : "transparent"

                FileGlyph {
                    y: 14
                    anchors.horizontalCenter: parent.horizontalCenter
                    size: 52
                    isDir: model.isDir
                    tint: model.tint
                    ext: model.ext
                }
                Text {
                    y: 76
                    x: 8
                    width: parent.width - 16
                    horizontalAlignment: Text.AlignHCenter
                    text: model.name
                    wrapMode: Text.WrapAnywhere
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.bold: model.selected
                }
                MouseArea {
                    id: tm
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onPressed: (mouse) => view.pressItem(index, mouse, tile)
                    onDoubleClicked: (mouse) => { if (mouse.button === Qt.LeftButton) fm.activate(index) }
                }
            }
        }
    }

    // ---- Leer ----------------------------------------------------------------
    Column {
        anchors.centerIn: parent
        visible: list.count === 0
        spacing: 10
        FileGlyph {
            anchors.horizontalCenter: parent.horizontalCenter
            size: 56
            isDir: !view.trash
            tint: Theme.tint(0.12)
            visible: !view.trash
        }
        SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "trash"; size: 48; visible: view.trash; opacity: 0.5 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: view.trash ? "Der Papierkorb ist leer" : (view.searchActive ? "Nichts gefunden" : "Dieser Ordner ist leer")
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }
    }
    property bool searchActive: false

    component HeaderText: Text {
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 12
        font.bold: true
        elide: Text.ElideRight
        rightPadding: 12
    }
    component Cell: Text {
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        elide: Text.ElideRight
        rightPadding: 12
    }
}
