import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative Dateien – der Dateimanager von Creative OS.
ApplicationWindow {
    id: win

    width: 1280
    height: 780
    minimumWidth: 820
    minimumHeight: 520
    visible: true
    color: Theme.surface
    title: (fm.page === "pc" ? "Dieser PC" : fm.page === "trash" ? "Papierkorb" : fm.crumbs[fm.crumbs.length - 1].name) + " – Dateien"
    font.family: Theme.fontFamily

    readonly property bool inFolder: fm.page === "folder"
    readonly property bool inTrash: fm.page === "trash"
    readonly property bool hasSel: fm.selectedCount > 0
    // Solange ein Dialog offen ist, gelten die Tastenkürzel nicht
    readonly property bool free: !nameDialog.opened && !confirmDialog.opened && !propsDialog.opened

    // ---- Aktionen --------------------------------------------------------------
    function newFolder() {
        if (inFolder)
            nameDialog.ask("Neuer Ordner", "Anlegen", "Neuer Ordner", (n) => fm.newFolder(n))
    }
    function newTextFile() {
        if (inFolder)
            nameDialog.ask("Neues Textdokument", "Anlegen", "Neues Dokument.txt", (n) => fm.newTextFile(n))
    }
    function rename() {
        if (inFolder && fm.selectedCount === 1)
            nameDialog.ask("Umbenennen", "Umbenennen", fm.selectedName, (n) => fm.renameSelected(n))
    }
    function properties() {
        if (hasSel) {
            fm.requestProperties()
            propsDialog.open()
        }
    }
    function emptyTrash() {
        confirmDialog.ask("Papierkorb leeren?",
                          "Alle Dateien im Papierkorb werden endgültig gelöscht. Das kann nicht rückgängig gemacht werden.",
                          "Endgültig löschen", () => fm.emptyTrash())
    }

    Connections {
        target: fm
        function onPropertiesReady(info) { propsDialog.info = info }
        function onLocationChanged() { search.text = "" }
    }

    // ---- Tastenkürzel (wie bei Windows) ------------------------------------------
    Shortcut { sequences: ["Ctrl+C"]; enabled: win.free && (inFolder && hasSel); onActivated: fm.copySelection() }
    Shortcut { sequences: ["Ctrl+X"]; enabled: win.free && (inFolder && hasSel); onActivated: fm.cutSelection() }
    Shortcut { sequences: ["Ctrl+V"]; enabled: win.free && (fm.canPaste); onActivated: fm.paste() }
    Shortcut { sequences: ["Ctrl+Z"]; enabled: win.free; onActivated: fm.undo() }
    Shortcut { sequences: ["Ctrl+A"]; enabled: win.free; onActivated: fm.selectAll() }
    Shortcut { sequences: ["F2"]; enabled: win.free; onActivated: win.rename() }
    Shortcut { sequences: ["Delete"]; enabled: win.free && (inFolder && hasSel); onActivated: fm.trashSelection() }
    Shortcut { sequences: ["Return", "Enter"]; enabled: win.free && (hasSel && !search.activeFocus); onActivated: inTrash ? fm.restoreSelection() : fm.openSelection() }
    Shortcut { sequences: ["Alt+Return"]; enabled: win.free; onActivated: win.properties() }
    Shortcut { sequences: ["Ctrl+Shift+N"]; enabled: win.free; onActivated: win.newFolder() }
    Shortcut { sequences: ["Alt+Left", "Back"]; enabled: win.free; onActivated: fm.back() }
    Shortcut { sequences: ["Alt+Right", "Forward"]; enabled: win.free; onActivated: fm.forward() }
    Shortcut { sequences: ["Alt+Up", "Backspace"]; enabled: win.free && (!search.activeFocus); onActivated: fm.up() }
    Shortcut { sequences: ["F5", "Ctrl+R"]; enabled: win.free; onActivated: fm.refresh() }
    Shortcut { sequences: ["Ctrl+F"]; enabled: win.free; onActivated: search.forceActiveFocus() }
    Shortcut { sequences: ["Ctrl+L"]; enabled: win.free; onActivated: search.forceActiveFocus() }
    Shortcut { sequences: ["Escape"]; enabled: win.free; onActivated: { if (search.text.length) search.text = ""; else fm.clearSelection() } }
    Shortcut { sequences: ["Ctrl+W", "Ctrl+Q"]; enabled: win.free; onActivated: win.close() }

    // ---- Kopfzeile: Navigation, Pfad, Suche ----------------------------------------
    header: Column {
        Rectangle {
            width: win.width
            height: 50
            color: Theme.raised

            Row {
                id: nav
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                CToolButton { icon: "back"; tip: "Zurück (Alt+←)"; enabled: fm.canBack; onClicked: fm.back() }
                CToolButton { icon: "forward"; tip: "Vor (Alt+→)"; enabled: fm.canForward; onClicked: fm.forward() }
                CToolButton { icon: "up"; tip: "Übergeordneter Ordner"; enabled: fm.canUp; onClicked: fm.up() }
            }

            // Pfad als anklickbare Stationen
            Rectangle {
                id: crumbBox
                anchors.left: nav.right
                anchors.leftMargin: 10
                anchors.right: searchBox.left
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                height: 34
                radius: 10
                color: Theme.ground
                clip: true

                Row {
                    id: crumbRow
                    x: Math.min(14, crumbBox.width - width - 14)
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4
                    SvgIcon {
                        name: inTrash ? "trash" : (fm.page === "pc" ? "pc" : "files")
                        size: 15
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Item { width: 4; height: 1 }
                    Repeater {
                        model: fm.crumbs
                        delegate: Row {
                            spacing: 4
                            anchors.verticalCenter: parent.verticalCenter
                            Text {
                                visible: index > 0
                                text: "›"
                                color: Theme.textMuted
                                font.pixelSize: 13
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Rectangle {
                                readonly property bool last: index === fm.crumbs.length - 1
                                width: ct.implicitWidth + 12
                                height: 26
                                radius: 7
                                color: cm.containsMouse && !last ? Theme.hover : "transparent"
                                Text {
                                    id: ct
                                    anchors.centerIn: parent
                                    text: modelData.name
                                    color: Theme.text
                                    font.pixelSize: 13
                                    font.bold: parent.last
                                }
                                MouseArea {
                                    id: cm
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: modelData.path.length ? fm.navigate(modelData.path) : fm.openPage(index === 0 && fm.page === "folder" ? "pc" : fm.page)
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                id: searchBox
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(280, win.width * 0.24)
                height: 34
                radius: 10
                color: Theme.ground
                border.color: search.activeFocus ? Theme.accent : "transparent"
                visible: fm.page !== "pc"

                SvgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 14 }
                TextField {
                    id: search
                    anchors.fill: parent
                    leftPadding: 34
                    rightPadding: 10
                    color: Theme.text
                    placeholderText: inTrash ? "Papierkorb durchsuchen" : (fm.crumbs[fm.crumbs.length - 1].name + " durchsuchen")
                    placeholderTextColor: Theme.textMuted
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.accentText
                    font.pixelSize: 13
                    background: null
                    onTextChanged: fm.setFilter(text)
                    Keys.onEscapePressed: { text = ""; focus = false }
                }
            }
        }

        // ---- Werkzeugleiste --------------------------------------------------------
        Rectangle {
            width: win.width
            height: 48
            color: Theme.surface
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.tint(0.05) }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.tint(0.05) }

            Row {
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                visible: !inTrash

                CToolButton {
                    id: newBtn
                    icon: "plus-dark"
                    text: "Neu"
                    primary: true
                    enabled: inFolder
                    onClicked: newMenu.openAt(newBtn, 0, newBtn.height + 6)
                }
                Rectangle { width: 1; height: 22; color: Theme.tint(0.1); anchors.verticalCenter: parent.verticalCenter }
                Item { width: 4; height: 1 }
                CToolButton { icon: "cut"; text: "Ausschneiden"; enabled: inFolder && hasSel; onClicked: fm.cutSelection() }
                CToolButton { icon: "copy"; text: "Kopieren"; enabled: inFolder && hasSel; onClicked: fm.copySelection() }
                CToolButton { icon: "paste"; text: "Einfügen"; enabled: fm.canPaste && !fm.busy; onClicked: fm.paste() }
                CToolButton { icon: "rename"; text: "Umbenennen"; enabled: inFolder && fm.selectedCount === 1; onClicked: win.rename() }
                CToolButton { icon: "trash"; text: "Löschen"; enabled: inFolder && hasSel; onClicked: fm.trashSelection() }
            }

            Row {
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                visible: inTrash
                CToolButton { icon: "restore"; text: "Wiederherstellen"; enabled: hasSel; onClicked: fm.restoreSelection() }
                CToolButton { icon: "trash"; text: "Papierkorb leeren"; onClicked: win.emptyTrash() }
            }

            CToolButton {
                id: viewBtn
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                visible: fm.page !== "pc"
                icon: fm.view === "list" ? "grid" : "list"
                text: fm.view === "list" ? "Kacheln" : "Liste"
                color: Theme.tint(0.06)
                onClicked: fm.view = (fm.view === "list" ? "tiles" : "list")
            }
        }
    }

    // ---- Inhalt -----------------------------------------------------------------
    Sidebar {
        id: sidebar
        width: 230
        anchors.top: parent.top
        anchors.bottom: status.top
        anchors.left: parent.left
    }

    Item {
        id: content
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: status.top

        PcView {
            anchors.fill: parent
            visible: fm.page === "pc"
        }

        FolderView {
            id: folder
            anchors.fill: parent
            visible: fm.page !== "pc"
            searchActive: search.text.length > 0
            onItemMenu: (src, x, y) => {
                itemMenu.items = inTrash ? win.trashItemMenu() : win.fileItemMenu()
                itemMenu.openAt(src, x, y)
            }
            onBackgroundMenu: (src, x, y) => {
                if (inTrash) return
                bgMenu.openAt(src, x, y)
            }
        }

        // Rückmeldung „… wurde in den Papierkorb verschoben  [Rückgängig]“
        Rectangle {
            id: toast
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: fm.toast.length ? 18 : -60
            visible: opacity > 0
            opacity: fm.toast.length ? 1 : 0
            width: Math.min(parent.width - 40, toastRow.implicitWidth + 28)
            height: 50
            radius: 12
            color: "#2a3040"
            border.color: Theme.hairline
            Behavior on anchors.bottomMargin { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: 180 } }

            Row {
                id: toastRow
                anchors.centerIn: parent
                spacing: 16
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: fm.toast
                    color: Theme.text
                    font.pixelSize: 13
                    width: Math.min(implicitWidth, content.width - 200)
                    elide: Text.ElideMiddle
                }
                CButton {
                    visible: fm.toastCanUndo
                    text: "Rückgängig"
                    primary: true
                    implicitHeight: 30
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: fm.undo()
                }
            }
        }

        // Laufende Kopie
        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            visible: fm.busy
            width: busyRow.implicitWidth + 24
            height: 36
            radius: 10
            color: "#2a3040"
            border.color: Theme.hairline
            Row {
                id: busyRow
                anchors.centerIn: parent
                spacing: 10
                BusyIndicator {
                    width: 18; height: 18
                    running: fm.busy
                    anchors.verticalCenter: parent.verticalCenter
                    contentItem: Item {
                        RotationAnimator on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: fm.busy }
                        Rectangle {
                            anchors.fill: parent
                            radius: width / 2
                            color: "transparent"
                            border.width: 2
                            border.color: Theme.accent
                            Rectangle { width: 6; height: 6; radius: 3; color: "#2a3040"; x: parent.width / 2 - 3; y: -2 }
                        }
                    }
                }
                Text { text: fm.busyText; color: Theme.text; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
            }
        }
    }

    // ---- Statuszeile ------------------------------------------------------------
    Rectangle {
        id: status
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 30
        color: Theme.surface
        Rectangle { width: parent.width; height: 1; color: Theme.tint(0.05) }
        Text {
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            text: fm.page === "pc" ? (fm.drives.length + (fm.drives.length === 1 ? " Laufwerk" : " Laufwerke")) : fm.status
            color: Theme.text
            font.pixelSize: 12
        }
    }

    // ---- Menüs ------------------------------------------------------------------
    function fileItemMenu() {
        const one = fm.selectedCount === 1
        return [
            { label: "Öffnen", icon: "open", key: "Enter", act: "fm.openSelection()" },
            { sep: true },
            { label: "Ausschneiden", icon: "cut", key: "Strg+X", act: "fm.cutSelection()" },
            { label: "Kopieren", icon: "copy", key: "Strg+C", act: "fm.copySelection()" },
            { sep: true },
            { label: "Umbenennen", icon: "rename", key: "F2", enabled: one, act: "win.rename()" },
            { label: "In den Papierkorb", icon: "trash", key: "Entf", act: "fm.trashSelection()" },
            { sep: true },
            { label: "Eigenschaften", icon: "info", key: "Alt+Enter", act: "win.properties()" }
        ]
    }
    function trashItemMenu() {
        return [
            { label: "Wiederherstellen", icon: "restore", key: "Enter", act: "fm.restoreSelection()" },
            { label: "Eigenschaften", icon: "info", key: "Alt+Enter", act: "win.properties()" }
        ]
    }

    // Menü-Einträge tragen den auszuführenden Befehl als Text
    function run(act) {
        const f = new Function("fm", "win", act)
        f(fm, win)
    }

    MenuPopup { id: itemMenu; onTriggered: (act) => win.run(act) }

    MenuPopup {
        id: bgMenu
        onTriggered: (act) => win.run(act)
        items: [
            { label: "Neuer Ordner", icon: "folder-plus", key: "Strg+⇧+N", act: "win.newFolder()" },
            { label: "Neues Textdokument", icon: "file-plus", act: "win.newTextFile()" },
            { sep: true },
            { label: "Einfügen", icon: "paste", key: "Strg+V", enabled: fm.canPaste, act: "fm.paste()" },
            { label: "Alles auswählen", icon: "select-all", key: "Strg+A", act: "fm.selectAll()" },
            { sep: true },
            { label: "Terminal hier öffnen", icon: "terminal", act: "fm.openTerminalHere()" },
            { label: "Aktualisieren", icon: "refresh", key: "F5", act: "fm.refresh()" }
        ]
    }

    MenuPopup {
        id: newMenu
        onTriggered: (act) => win.run(act)
        width: 230
        items: [
            { label: "Ordner", icon: "folder-plus", key: "Strg+⇧+N", act: "win.newFolder()" },
            { label: "Textdokument", icon: "file-plus", act: "win.newTextFile()" }
        ]
    }

    NameDialog { id: nameDialog }
    ConfirmDialog { id: confirmDialog }
    PropertiesDialog { id: propsDialog }
}
