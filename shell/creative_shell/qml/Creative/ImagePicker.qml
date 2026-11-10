import QtCore
import QtQuick
import QtQuick.Controls.Basic
import Qt.labs.folderlistmodel
import Creative

// Bildauswahl im Creative-OS-Stil (statt des Standard-Dateidialogs von Qt).
// Links Orte, in der Mitte große Vorschaubilder, Ordner per Doppelklick öffnen.
//   ImagePicker { id: picker; title: "Profilbild wählen"; onAccepted: (url) => … }
//   picker.open()
Popup {
    id: picker

    property string title: "Bild wählen"
    property string acceptText: "Auswählen"
    property var nameFilters: ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif",
                               "*.PNG", "*.JPG", "*.JPEG", "*.WEBP", "*.BMP", "*.GIF"]
    property url selected: ""
    signal accepted(url url)

    readonly property url home: StandardPaths.writableLocation(StandardPaths.HomeLocation)
    readonly property var places: [
        { name: "Bilder", icon: "pictures", url: StandardPaths.writableLocation(StandardPaths.PicturesLocation) },
        { name: "Downloads", icon: "download", url: StandardPaths.writableLocation(StandardPaths.DownloadLocation) },
        { name: "Schreibtisch", icon: "pc", url: StandardPaths.writableLocation(StandardPaths.DesktopLocation) },
        { name: "Persönlicher Ordner", icon: "home", url: home }
    ]

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(900, parent ? parent.width - 60 : 900)
    height: Math.min(620, parent ? parent.height - 60 : 620)
    modal: true
    focus: true
    padding: 0
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
    background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }

    property bool started: false
    onAboutToShow: {
        selected = ""
        if (!started) {                 // beim ersten Öffnen im Ordner „Bilder“ beginnen
            folders.folder = places[0].url
            started = true
        }
    }

    function pathText(u) {
        let s = decodeURIComponent(u.toString().replace(/^file:\/\//, ""))
        const h = decodeURIComponent(home.toString().replace(/^file:\/\//, ""))
        return s.indexOf(h) === 0 ? "~" + s.slice(h.length) : s
    }
    function choose() {
        if (selected.toString().length) {
            picker.accepted(selected)
            picker.close()
        }
    }

    FolderListModel {
        id: folders
        nameFilters: picker.nameFilters
        showDirs: true
        showDirsFirst: true
        showDotAndDotDot: false
        showHidden: false
        sortField: FolderListModel.Name
        caseSensitive: false
        onFolderChanged: picker.selected = ""
    }

    contentItem: Item {
        // ---- Kopfzeile ----
        Item {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 60
            Text {
                x: 22
                anchors.verticalCenter: parent.verticalCenter
                text: picker.title
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.bold: true
            }
            IconButton {
                anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                icon: "close"
                iconSize: 18
                label: "Schließen"
                onClicked: picker.close()
            }
        }

        // ---- Orte ----
        Column {
            id: side
            anchors { left: parent.left; top: head.bottom; bottom: foot.top; leftMargin: 12 }
            width: 190
            spacing: 4
            Text {
                leftPadding: 10
                bottomPadding: 4
                text: "ORTE"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1
            }
            Repeater {
                model: picker.places
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool current: folders.folder.toString() === modelData.url.toString()
                    width: side.width
                    height: 40
                    radius: Theme.radiusRow
                    color: current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                   : (placeMouse.containsMouse ? Theme.hover : "transparent")
                    Row {
                        x: 12
                        spacing: 10
                        anchors.verticalCenter: parent.verticalCenter
                        SvgIcon { name: modelData.icon; size: 18; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.name
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: parent.parent.current
                        }
                    }
                    MouseArea {
                        id: placeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: folders.folder = modelData.url
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.name
                }
            }
        }

        // ---- Pfad + Raster ----
        Rectangle {
            id: main
            anchors { left: side.right; right: parent.right; top: head.bottom; bottom: foot.top
                      leftMargin: 12; rightMargin: 12 }
            radius: 14
            color: Theme.ground

            Row {
                id: pathRow
                x: 8
                y: 8
                spacing: 6
                IconButton {
                    icon: "up"
                    iconSize: 16
                    width: 34
                    height: 34
                    label: "Übergeordneter Ordner"
                    opacity: folders.folder.toString() === "file:///" ? 0.4 : 1
                    onClicked: if (folders.parentFolder.toString().length) folders.folder = folders.parentFolder
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: main.width - 70
                    elide: Text.ElideMiddle
                    text: picker.pathText(folders.folder)
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }

            GridView {
                id: grid
                anchors { left: parent.left; right: parent.right; top: pathRow.bottom; bottom: parent.bottom
                          margins: 10 }
                clip: true
                cellWidth: Math.floor(width / Math.max(1, Math.floor(width / 150)))
                cellHeight: 160
                model: folders
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {
                    contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.track }
                }
                delegate: Item {
                    required property string fileName
                    required property url fileUrl
                    required property bool fileIsDir
                    readonly property bool isSelected: picker.selected.toString() === fileUrl.toString()
                    width: grid.cellWidth
                    height: grid.cellHeight

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 5
                        radius: 12
                        color: isSelected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                          : (cellMouse.containsMouse ? Theme.hover : "transparent")
                        border.width: isSelected ? 2 : 0
                        border.color: Theme.accent

                        Rectangle {
                            id: thumbFrame
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 8
                            width: parent.width - 16
                            height: 104
                            radius: 10
                            color: fileIsDir ? "transparent" : Theme.surface
                            clip: true
                            Image {
                                anchors.fill: parent
                                visible: !fileIsDir
                                source: fileIsDir ? "" : fileUrl
                                sourceSize.width: 280
                                sourceSize.height: 200
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                smooth: true
                            }
                            FileIcon {
                                visible: fileIsDir
                                anchors.centerIn: parent
                                isDir: true
                                size: 64
                            }
                        }
                        Text {
                            anchors { left: parent.left; right: parent.right; top: thumbFrame.bottom
                                      topMargin: 7; leftMargin: 8; rightMargin: 8 }
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideMiddle
                            text: fileName
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.bold: isSelected
                        }
                    }
                    MouseArea {
                        id: cellMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (!fileIsDir) picker.selected = fileUrl
                        onDoubleClicked: {
                            if (fileIsDir) {
                                folders.folder = fileUrl
                            } else {
                                picker.selected = fileUrl
                                picker.choose()
                            }
                        }
                    }
                    Accessible.role: Accessible.ListItem
                    Accessible.name: (fileIsDir ? "Ordner " : "Bild ") + fileName
                }
            }

            Column {
                anchors.centerIn: grid
                visible: folders.status === FolderListModel.Ready && folders.count === 0
                spacing: 6
                SvgIcon { name: "image"; size: 36; anchors.horizontalCenter: parent.horizontalCenter; opacity: 0.5 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Keine Bilder in diesem Ordner"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
        }

        // ---- Fußzeile ----
        Item {
            id: foot
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 64
            Text {
                x: 22
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - buttons.width - 50
                elide: Text.ElideMiddle
                text: picker.selected.toString().length ? picker.pathText(picker.selected)
                                                        : "Bild anklicken – Doppelklick öffnet Ordner bzw. wählt das Bild"
                color: picker.selected.toString().length ? Theme.text : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            Row {
                id: buttons
                anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: picker.close() }
                CButton {
                    text: picker.acceptText
                    primary: true
                    enabled: picker.selected.toString().length > 0
                    onClicked: picker.choose()
                }
            }
        }
    }
}
