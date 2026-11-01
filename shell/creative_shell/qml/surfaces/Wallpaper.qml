import QtQuick
import QtQuick.Controls.Basic
import Creative

// Hintergrundbild – liegt hinter allen Fenstern, auf jedem Monitor.
// Auf dem Hauptbildschirm zeigt es die Dateien vom Schreibtisch (wie bei Windows).
Item {
    id: root

    property string screenName
    readonly property bool showIcons: shell.primaryScreen === "" || shell.primaryScreen === screenName
    readonly property int barSpace: 74

    Rectangle {
        anchors.fill: parent
        color: Theme.ground
    }

    Image {
        anchors.fill: parent
        source: wallpaperUrl
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: width
        sourceSize.height: height
        asynchronous: true
        smooth: true
        cache: true
    }

    // Klick auf den freien Desktop: Menüs schließen, Auswahl aufheben, Rechtsklick-Menü
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => {
            shell.closePopups()
            desktop.clearSelection()
            if (mouse.button === Qt.RightButton && root.showIcons)
                bgMenu.openAt(mouse.x, mouse.y)
        }
    }

    // ---- Schreibtisch-Symbole ------------------------------------------------------
    GridView {
        id: icons
        visible: root.showIcons
        x: 12
        y: 12
        width: parent.width - 24
        height: parent.height - root.barSpace - 24
        flow: GridView.FlowTopToBottom
        cellWidth: 104
        cellHeight: 108
        interactive: false
        model: root.showIcons ? desktop : null

        delegate: Item {
            id: cell
            width: icons.cellWidth
            height: icons.cellHeight

            Rectangle {
                anchors.fill: parent
                anchors.margins: 3
                radius: 10
                color: model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.28)
                                      : (m.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent")
                border.color: model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.7) : "transparent"
            }
            FileIcon {
                y: 12
                anchors.horizontalCenter: parent.horizontalCenter
                size: 46
                isDir: model.isDir
                tint: model.tint
                ext: model.ext
            }
            Text {
                y: 64
                x: 6
                width: parent.width - 12
                horizontalAlignment: Text.AlignHCenter
                text: model.name
                wrapMode: Text.WrapAnywhere
                maximumLineCount: 2
                elide: Text.ElideRight
                color: "white"
                style: Text.Outline
                styleColor: Qt.rgba(0, 0, 0, 0.55)
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
            MouseArea {
                id: m
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onPressed: (mouse) => {
                    shell.closePopups()
                    if (mouse.button === Qt.RightButton) {
                        desktop.selectKeep(index)
                        const p = cell.mapToItem(root, mouse.x, mouse.y)
                        itemMenu.openAt(p.x, p.y)
                    } else {
                        desktop.select(index, (mouse.modifiers & Qt.ControlModifier) !== 0)
                    }
                }
                onDoubleClicked: (mouse) => { if (mouse.button === Qt.LeftButton) desktop.open(index) }
            }
            Accessible.role: Accessible.ListItem
            Accessible.name: model.name
        }
    }

    // ---- Menüs ------------------------------------------------------------------------
    DesktopMenu {
        id: itemMenu
        entries: [
            { label: "Öffnen", icon: "open", act: "open" },
            { label: "In Dateien zeigen", icon: "files", act: "files" },
            { sep: true },
            { label: "In den Papierkorb", icon: "trash", act: "trash" }
        ]
        onTriggered: (act) => {
            if (act === "open") desktop.openSelected()
            else if (act === "files") desktop.openInFiles()
            else if (act === "trash") desktop.trashSelected()
        }
    }
    DesktopMenu {
        id: bgMenu
        entries: [
            { label: "Neuer Ordner", icon: "folder-plus", act: "new" },
            { label: "Schreibtisch in Dateien öffnen", icon: "files", act: "folder" },
            { sep: true },
            { label: "Einstellungen", icon: "settings", act: "settings" }
        ]
        onTriggered: (act) => {
            if (act === "new") desktop.newFolder()
            else if (act === "folder") desktop.openFolder()
            else if (act === "settings") session.openSettings()
        }
    }

    component DesktopMenu: Popup {
        id: menu
        property var entries: []
        signal triggered(string act)

        function openAt(px, py) {
            x = Math.min(px, root.width - width - 8)
            y = Math.min(py, root.height - root.barSpace - implicitHeight - 8)
            open()
        }

        padding: 6
        width: 250
        closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape
        background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Column {
            spacing: 1
            Repeater {
                model: menu.entries
                delegate: Item {
                    width: menu.width - 12
                    height: modelData.sep ? 9 : 36
                    Rectangle {
                        visible: !!modelData.sep
                        anchors.centerIn: parent
                        width: parent.width - 16
                        height: 1
                        color: Theme.hairline
                    }
                    Rectangle {
                        visible: !modelData.sep
                        anchors.fill: parent
                        radius: 9
                        color: rm.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                        SvgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: modelData.icon || ""; size: 15 }
                        Text {
                            x: 39
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label || ""
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                        }
                        MouseArea {
                            id: rm
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: { menu.close(); menu.triggered(modelData.act) }
                        }
                    }
                }
            }
        }
    }
}
