import QtCore
import QtQuick
import QtQuick.Controls.Basic
import Qt.labs.folderlistmodel
import Creative

// Datei- und Ordnerauswahl im Creative-OS-Stil (statt der Standard-Dialoge von Qt).
//   mode: "open"   Datei öffnen         → accepted(Datei-URL)
//         "save"   Speichern unter      → accepted(Datei-URL), mit Dateiname und Überschreiben-Rückfrage
//         "folder" Ordner wählen        → accepted(Ordner-URL)
// Bilder bekommen große Vorschaubilder, andere Dateien ein Symbol.
//   FilePicker { id: p; mode: "save"; nameFilters: ["*.png"]; fileName: "Bild.png"; onAccepted: (url) => … }
//   p.open()
Popup {
    id: picker

    property string mode: "open"
    property string title: mode === "save" ? "Speichern unter" : mode === "folder" ? "Ordner wählen" : "Datei öffnen"
    property string acceptText: mode === "save" ? "Speichern" : mode === "folder" ? "Diesen Ordner nehmen" : "Öffnen"
    property var nameFilters: []
    property url startFolder: ""
    property string fileName: ""                 // Vorschlag beim Speichern
    property string defaultSuffix: ""            // ohne Punkt, z. B. "png"
    property url selected: ""
    property bool confirmOverwrite: false
    signal accepted(url url)

    readonly property url home: StandardPaths.writableLocation(StandardPaths.HomeLocation)
    readonly property var places: [
        { name: "Persönlicher Ordner", icon: "home", url: home },
        { name: "Bilder", icon: "pictures", url: StandardPaths.writableLocation(StandardPaths.PicturesLocation) },
        { name: "Dokumente", icon: "files", url: StandardPaths.writableLocation(StandardPaths.DocumentsLocation) },
        { name: "Downloads", icon: "download", url: StandardPaths.writableLocation(StandardPaths.DownloadLocation) },
        { name: "Musik", icon: "music", url: StandardPaths.writableLocation(StandardPaths.MusicLocation) },
        { name: "Videos", icon: "video", url: StandardPaths.writableLocation(StandardPaths.MoviesLocation) },
        { name: "Schreibtisch", icon: "pc", url: StandardPaths.writableLocation(StandardPaths.DesktopLocation) }
    ]
    readonly property var imageTypes: ["png", "jpg", "jpeg", "webp", "bmp", "gif", "svg"]

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(900, parent ? parent.width - 60 : 900)
    height: Math.min(620, parent ? parent.height - 60 : 620)
    modal: true
    focus: true
    padding: 0
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
    background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }

    onAboutToShow: {
        selected = ""
        confirmOverwrite = false
        folders.folder = startFolder.toString().length ? startFolder
                       : (folders.folder.toString().length && started ? folders.folder : places[mode === "open" ? 1 : 0].url)
        started = true
        nameField.text = fileName
        if (mode === "save")
            nameField.forceActiveFocus()
    }
    property bool started: false

    function pathText(u) {
        const s = decodeURIComponent(u.toString().replace("file://", ""))
        const h = decodeURIComponent(home.toString().replace("file://", ""))
        return s.indexOf(h) === 0 ? "~" + s.slice(h.length) : s
    }
    function suffix(name) {
        const i = name.lastIndexOf(".")
        return i > 0 ? name.slice(i + 1).toLowerCase() : ""
    }
    function saveTarget() {
        let name = nameField.text.trim().replace(/\//g, "-")
        if (!name.length)
            return ""
        if (defaultSuffix.length && !suffix(name).length)
            name += "." + defaultSuffix
        let dir = folders.folder.toString()
        if (!dir.endsWith("/"))
            dir += "/"
        return dir + encodeURIComponent(name)
    }
    function canAccept() {
        if (mode === "save") return nameField.text.trim().length > 0
        if (mode === "folder") return true
        return selected.toString().length > 0
    }
    function choose() {
        if (!canAccept())
            return
        if (mode === "save") {
            const target = saveTarget()
            const exists = folders.indexOf(target) >= 0
            if (exists && !confirmOverwrite) {
                confirmOverwrite = true
                return
            }
            picker.accepted(target)
        } else if (mode === "folder") {
            picker.accepted(selected.toString().length ? selected : folders.folder)
        } else {
            picker.accepted(selected)
        }
        picker.close()
    }

    FolderListModel {
        id: folders
        nameFilters: picker.mode === "folder" ? [] : picker.nameFilters
        showFiles: picker.mode !== "folder"
        showDirs: true
        showDirsFirst: true
        showDotAndDotDot: false
        showHidden: false
        sortField: FolderListModel.Name
        caseSensitive: false
        onFolderChanged: { picker.selected = ""; picker.confirmOverwrite = false }
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
            anchors { left: parent.left; top: head.bottom; leftMargin: 12 }
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
                    height: 38
                    radius: Theme.radiusRow
                    color: current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                   : (placeMouse.containsMouse ? Theme.hover : "transparent")
                    Row {
                        x: 12
                        spacing: 10
                        anchors.verticalCenter: parent.verticalCenter
                        SvgIcon { name: modelData.icon; size: 17; anchors.verticalCenter: parent.verticalCenter }
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
                cellHeight: 156
                model: folders
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {
                    contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.track }
                }
                delegate: Item {
                    id: cell
                    required property string fileName
                    required property url fileUrl
                    required property bool fileIsDir
                    readonly property bool isImage: !fileIsDir && picker.imageTypes.indexOf(picker.suffix(fileName)) >= 0
                    readonly property bool isSelected: picker.selected.toString() === fileUrl.toString()
                    width: grid.cellWidth
                    height: grid.cellHeight

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 5
                        radius: 12
                        color: cell.isSelected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                               : (cellMouse.containsMouse ? Theme.hover : "transparent")
                        border.width: cell.isSelected ? 2 : 0
                        border.color: Theme.accent

                        Rectangle {
                            id: thumbFrame
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 8
                            width: parent.width - 16
                            height: 100
                            radius: 10
                            color: cell.isImage ? Theme.surface : "transparent"
                            clip: true
                            Image {
                                anchors.fill: parent
                                visible: cell.isImage
                                source: cell.isImage ? cell.fileUrl : ""
                                sourceSize.width: 280
                                sourceSize.height: 200
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                smooth: true
                            }
                            FileIcon {
                                visible: !cell.isImage
                                anchors.centerIn: parent
                                isDir: cell.fileIsDir
                                ext: picker.suffix(cell.fileName)
                                size: 60
                            }
                        }
                        Text {
                            anchors { left: parent.left; right: parent.right; top: thumbFrame.bottom
                                      topMargin: 7; leftMargin: 8; rightMargin: 8 }
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideMiddle
                            text: cell.fileName
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.bold: cell.isSelected
                        }
                    }
                    MouseArea {
                        id: cellMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (cell.fileIsDir) {
                                if (picker.mode === "folder")
                                    picker.selected = cell.fileUrl
                            } else if (picker.mode === "save") {
                                nameField.text = cell.fileName          // vorhandene Datei als Namen übernehmen
                                picker.confirmOverwrite = false
                            } else {
                                picker.selected = cell.fileUrl
                            }
                        }
                        onDoubleClicked: {
                            if (cell.fileIsDir) {
                                folders.folder = cell.fileUrl
                            } else if (picker.mode === "open") {
                                picker.selected = cell.fileUrl
                                picker.choose()
                            }
                        }
                    }
                    Accessible.role: Accessible.ListItem
                    Accessible.name: (cell.fileIsDir ? "Ordner " : "Datei ") + cell.fileName
                }
            }

            Column {
                anchors.centerIn: grid
                visible: folders.status === FolderListModel.Ready && folders.count === 0
                spacing: 6
                SvgIcon { name: "files"; size: 34; anchors.horizontalCenter: parent.horizontalCenter; opacity: 0.5 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: picker.mode === "folder" ? "Keine Unterordner" : "Keine passenden Dateien in diesem Ordner"
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
            height: picker.mode === "save" ? 104 : 64

            // Dateiname (nur Speichern)
            Row {
                id: nameRow
                visible: picker.mode === "save"
                x: 22
                y: 14
                spacing: 10
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Dateiname"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                TextField {
                    id: nameField
                    width: foot.width - 140
                    height: 38
                    leftPadding: 12
                    color: Theme.text
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.accentText
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    background: Rectangle { radius: 10; color: Theme.ground; border.color: nameField.activeFocus ? Theme.accent : Theme.hairline }
                    onTextEdited: picker.confirmOverwrite = false
                    onAccepted: picker.choose()
                }
            }

            Text {
                x: 22
                anchors { bottom: parent.bottom; bottomMargin: 22 }
                width: parent.width - buttons.width - 50
                elide: Text.ElideMiddle
                text: picker.confirmOverwrite ? "Diese Datei gibt es schon – nochmal klicken zum Überschreiben."
                    : picker.mode === "save" ? "Speichern in " + picker.pathText(folders.folder)
                    : picker.mode === "folder" ? "Ordner: " + picker.pathText(picker.selected.toString().length ? picker.selected : folders.folder)
                    : picker.selected.toString().length ? picker.pathText(picker.selected)
                    : "Datei anklicken – Doppelklick öffnet Ordner bzw. die Datei"
                color: picker.confirmOverwrite ? Theme.flame
                     : (picker.selected.toString().length || picker.mode !== "open") ? Theme.text : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            Row {
                id: buttons
                anchors { right: parent.right; rightMargin: 16; bottom: parent.bottom; bottomMargin: 14 }
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: picker.close() }
                CButton {
                    text: picker.confirmOverwrite ? "Überschreiben" : picker.acceptText
                    primary: true
                    enabled: picker.canAccept()
                    onClicked: picker.choose()
                }
            }
        }
    }
}
