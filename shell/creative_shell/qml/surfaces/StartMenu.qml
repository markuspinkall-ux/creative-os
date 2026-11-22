import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Schlankes Startmenü: Suche oben, alle Apps alphabetisch darunter,
// unten Benutzer, Sperren und Ein/Aus.
Item {
    id: root

    property string screenName

    // Wird beim Öffnen aufgerufen
    // Fluid-Glas unter dem Menü
    // Startmenü-Stil (Kategorien / A–Z / Kacheln) aus der Systemsteuerung beim Öffnen übernehmen
    Connections {
        target: Window.window
        function onVisibleChanged() { if (Window.window && Window.window.visible) apps.refreshStyle() }
    }
    Component.onCompleted: apps.refreshStyle()

    // Fenster wachsen aus dem angeklickten Eintrag (KWin-Effekt „gibeon-fenster“).
    // Das Startmenü sitzt links unten direkt über der Taskleiste (52 px, BAR_HEIGHT).
    function noteLaunch(item) {
        const win = Window.window
        const geo = shell.screenGeometry(root.screenName)
        if (!item || !win || geo.width === undefined) return
        const p = item.mapToItem(null, 32, item.height / 2)
        windowAnim.noteLaunch(geo.x + p.x, geo.y + geo.height - 52 - win.height + p.y)
    }

    function updateBlur() {
        shell.setBlur(Window.window, [{ x: menu.x, y: menu.y, w: menu.width, h: menu.height, r: menu.radius }])
    }

    function opened() {
        Qt.callLater(updateBlur)
        apps.closeFolder()
        search.text = ""
        powerMenu.visible = false
        powerMenu.confirmServer = false
        session.refreshServer()
        session.refreshAvatar()
        appMenu.visible = false
        list.currentIndex = -1
        list.positionViewAtBeginning()
        search.forceActiveFocus()
    }

    Keys.onEscapePressed: root.back()

    // Esc: erst aus dem Ordner „Gibeon OS Suite“ zurück, dann Menü schließen
    function back() {
        if (apps.folder !== "") {
            apps.closeFolder()
            list.currentIndex = -1
            search.forceActiveFocus()
        } else {
            shell.closePopups()
        }
    }

    // Fluid-Design: Glasfläche mit runden Ecken und Lichtkante oben
    Rectangle {
        id: menu
        x: 8
        width: 380
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        radius: 30
        color: shell.blurAvailable ? Qt.rgba(Theme.glass.r, Theme.glass.g, Theme.glass.b, Theme.light ? 0.62 : 0.62)
                                   : Theme.glassSolid
        border.color: Theme.glassEdge
        border.width: 1

        Rectangle {
            x: menu.radius
            y: 1
            width: menu.width - 2 * menu.radius
            height: 1
            color: Theme.glassShine
        }
        // Fluid-Glas: durchscheinend, KWin zeichnet den Hintergrund dahinter weich
        onHeightChanged: Qt.callLater(root.updateBlur)

        TextField {
            id: search
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 18
                leftMargin: 18
                rightMargin: 18
            }
            height: 42
            leftPadding: 42
            rightPadding: 14
            placeholderText: "Suchen"
            placeholderTextColor: Theme.textMuted
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.accentText
            font.family: Theme.fontFamily
            font.pixelSize: 14
            selectByMouse: true
            background: Rectangle {
                radius: 21
                color: Qt.rgba(Theme.ground.r, Theme.ground.g, Theme.ground.b, 0.55)
                border.color: Theme.accent
                border.width: 1.5
            }

            SvgIcon {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                name: "search"
                size: 16
            }

            onTextChanged: {
                if (text.length > 0)
                    apps.closeFolder()
                apps.filterText = text
                list.currentIndex = (text.length > 0 && list.count > 0) ? 0 : -1
            }
            Keys.onDownPressed: {
                list.forceActiveFocus()
                if (list.currentIndex < 0 && list.count > 0)
                    list.currentIndex = 0
            }
            Keys.onReturnPressed: list.launchCurrent()
            Keys.onEnterPressed: list.launchCurrent()
            Keys.onEscapePressed: root.back()

            Accessible.name: "Apps suchen"
        }

        Item {
            id: heading
            anchors.top: search.bottom
            anchors.topMargin: 12
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            height: 26

            // Zurück aus dem Ordner
            Rectangle {
                id: backButton
                visible: apps.folder !== ""
                width: 26
                height: 26
                radius: 13
                anchors.verticalCenter: parent.verticalCenter
                color: backMouse.containsMouse ? Theme.hover : "transparent"
                SvgIcon {
                    anchors.centerIn: parent
                    name: "chevron-left"
                    size: 14
                }
                MouseArea {
                    id: backMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.back()
                }
                Accessible.role: Accessible.Button
                Accessible.name: "Zurück zu allen Apps"
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: backButton.visible ? backButton.width + 6 : 8
                text: search.text.length > 0 ? "Ergebnisse" : (apps.folder !== "" ? apps.folderName : "Alle Apps")
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.bold: true
            }
        }

        // Kachel-Ansicht: Kategorien zum Antippen (Systemsteuerung › Darstellung › Startmenü)
        readonly property bool tilesMode: apps.style === "kacheln" && search.text.length === 0 && apps.folder === ""
        Flickable {
            id: chips
            visible: menu.tilesMode
            anchors.top: heading.bottom
            anchors.topMargin: 6
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            height: visible ? 32 : 0
            clip: true
            contentWidth: chipRow.width
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            Row {
                id: chipRow
                spacing: 6
                Repeater {
                    model: [""].concat(apps.categories)
                    delegate: Rectangle {
                        required property string modelData
                        readonly property bool on: apps.category === modelData
                        height: 28
                        width: chipText.implicitWidth + 22
                        radius: 14
                        color: on ? Theme.accent : (chipMouse.containsMouse ? Theme.hover : Theme.tint(0.06))
                        Text {
                            id: chipText
                            anchors.centerIn: parent
                            text: parent.modelData === "" ? "Alle" : parent.modelData
                            color: parent.on ? Theme.accentText : Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.bold: parent.on
                        }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: apps.setCategory(parent.modelData)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Kategorie " + chipText.text
                    }
                }
            }
        }

        GridView {
            id: tiles
            objectName: "startTiles"
            visible: menu.tilesMode
            anchors {
                top: chips.bottom
                topMargin: 8
                left: parent.left
                right: parent.right
                bottom: footer.top
                leftMargin: 10
                rightMargin: 10
                bottomMargin: 6
            }
            clip: true
            model: menu.tilesMode ? apps : null
            cellWidth: Math.floor(width / 3)
            cellHeight: 92
            boundsBehavior: Flickable.StopAtBounds
            delegate: Item {
                id: tile
                required property int index
                required property string name
                required property string icon
                required property string desktopId
                width: tiles.cellWidth
                height: tiles.cellHeight
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 3
                    radius: 14
                    color: tileMouse.pressed ? Theme.pressed : (tileMouse.containsMouse ? Theme.tint(Theme.light ? 0.06 : 0.10) : "transparent")
                }
                Image {
                    id: tileIcon
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 12
                    width: 40; height: 40
                    sourceSize.width: 80; sourceSize.height: 80
                    source: iconFiles.app(tile.icon)
                    asynchronous: true
                    smooth: true
                }
                Text {
                    anchors.top: tileIcon.bottom
                    anchors.topMargin: 6
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    horizontalAlignment: Text.AlignHCenter
                    text: tile.name
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                }
                MouseArea {
                    id: tileMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (mouse) => {
                        if (mouse.button === Qt.RightButton) {
                            appMenu.desktopId = tile.desktopId
                            appMenu.appName = tile.name
                            appMenu.pinned = apps.isPinned(tile.desktopId)
                            appMenu.autostart = apps.isAutostart(tile.desktopId)
                            appMenu.confirming = false
                            const p = tile.mapToItem(menu, mouse.x, mouse.y)
                            appMenu.x = Math.min(p.x, menu.width - appMenu.width - 8)
                            appMenu.y = Math.min(p.y, menu.height - appMenu.height - 8)
                            appMenu.visible = true
                            return
                        }
                        root.noteLaunch(tile)
                        if (apps.launchAt(tile.index))
                            shell.closePopups()
                    }
                }
                Accessible.role: Accessible.Button
                Accessible.name: tile.name
            }
        }

        ListView {
            id: list
            visible: !menu.tilesMode

            function launchCurrent() {
                if (count === 0)
                    return
                root.noteLaunch(currentItem)
                if (apps.launchAt(currentIndex >= 0 ? currentIndex : 0))
                    shell.closePopups()
                else
                    currentIndex = 0
            }

            anchors {
                top: heading.bottom
                topMargin: 4
                left: parent.left
                right: parent.right
                bottom: footer.top
                leftMargin: 10
                rightMargin: 10
                bottomMargin: 6
            }
            clip: true
            model: apps
            spacing: 4
            keyNavigationEnabled: true
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0

            section.property: "letter"
            section.criteria: ViewSection.FullString
            section.delegate: Item {
                required property string section
                width: ListView.view.width
                height: section.length > 0 ? 34 : 0
                visible: section.length > 0
                Text {
                    x: 12
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 6
                    text: parent.section
                    color: Theme.accent
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.bold: true
                }
            }

            delegate: Rectangle {
                id: row
                required property int index
                required property string name
                required property string icon
                required property string comment
                required property string desktopId
                required property bool isFolder
                required property var folderIcons
                required property int folderCount

                width: ListView.view.width
                height: 46
                radius: 16
                color: rowMouse.pressed ? Theme.pressed
                       : ((rowMouse.containsMouse || ListView.isCurrentItem) ? Theme.tint(Theme.light ? 0.06 : 0.10) : "transparent")
                // Auswahl als leuchtende Glasfläche: Lichtkante oben
                Rectangle {
                    visible: rowMouse.containsMouse || row.ListView.isCurrentItem
                    x: 12
                    y: 0
                    width: parent.width - 24
                    height: 1
                    color: Qt.rgba(1, 1, 1, Theme.light ? 0.9 : 0.2)
                }

                // Ordner „Gibeon OS Suite“: kleine Vorschau der Apps darin
                Rectangle {
                    visible: row.isFolder
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30
                    height: 30
                    radius: 8
                    color: Theme.raised
                    border.color: Theme.hairline
                    Grid {
                        anchors.centerIn: parent
                        columns: 2
                        spacing: 2
                        Repeater {
                            model: row.folderIcons
                            delegate: Image {
                                required property string modelData
                                width: 11
                                height: 11
                                sourceSize.width: 24
                                sourceSize.height: 24
                                source: iconFiles.app(modelData)
                                asynchronous: true
                                smooth: true
                            }
                        }
                    }
                }

                Text {
                    visible: row.isFolder
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.folderCount + "  ›"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }

                Image {
                    id: appIcon
                    visible: !row.isFolder
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 26
                    height: 26
                    sourceSize.width: 52
                    sourceSize.height: 52
                    source: iconFiles.app(row.icon)
                    asynchronous: true
                    smooth: true
                }

                Text {
                    anchors.left: appIcon.right
                    anchors.leftMargin: 14
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.name
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                }

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (mouse) => {
                        if (mouse.button === Qt.RightButton) {
                            if (row.isFolder)
                                return
                            appMenu.desktopId = row.desktopId
                            appMenu.appName = row.name
                            appMenu.pinned = apps.isPinned(row.desktopId)
                            appMenu.autostart = apps.isAutostart(row.desktopId)
                            appMenu.confirming = false
                            const p = row.mapToItem(menu, mouse.x, mouse.y)
                            appMenu.x = Math.min(p.x, menu.width - appMenu.width - 8)
                            appMenu.y = Math.min(p.y, menu.height - appMenu.height - 8)
                            appMenu.visible = true
                            return
                        }
                        root.noteLaunch(row)
                        if (apps.launchAt(row.index))
                            shell.closePopups()
                        else
                            list.positionViewAtBeginning()
                    }
                }

                Accessible.role: Accessible.ListItem
                Accessible.name: row.name
                Accessible.description: row.comment
            }

            Keys.onReturnPressed: launchCurrent()
            Keys.onEnterPressed: launchCurrent()
            Keys.onUpPressed: {
                if (currentIndex <= 0)
                    search.forceActiveFocus()
                else
                    decrementCurrentIndex()
            }
            Keys.onPressed: (event) => {
                // Einfach lostippen springt zurück in die Suche
                if (event.text.length > 0 && event.text.trim().length > 0 && !(event.modifiers & Qt.ControlModifier)) {
                    search.forceActiveFocus()
                    search.text += event.text
                    event.accepted = true
                }
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                // Scrollbalken passend zum Design, beim Drüberfahren in Akzentfarbe
                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: parent.hovered || parent.pressed ? Theme.accent : Theme.tint(Theme.light ? 0.22 : 0.28)
                }
            }

            Text {
                anchors.centerIn: parent
                visible: list.count === 0
                text: "Keine App gefunden"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
            }
        }

        // Ein/Aus-Menü
        Rectangle {
            id: powerMenu
            // Server-Modus fragt erst nach, weil dabei alle Programme schließen
            property bool confirmServer: false
            visible: false
            onVisibleChanged: if (!visible) confirmServer = false
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.bottom: footer.top
            anchors.bottomMargin: 8
            width: confirmServer ? 300 : 200
            height: confirmServer ? serverConfirm.implicitHeight + 28 : powerColumn.implicitHeight + 12
            radius: 14
            color: Theme.raised
            border.color: Theme.hairline
            border.width: 1
            z: 2

            Column {
                id: powerColumn
                visible: !powerMenu.confirmServer
                anchors.fill: parent
                anchors.margins: 6
                spacing: 2

                Repeater {
                    model: [
                        { label: "Bereitschaft", action: "suspend" },
                        { label: "Neu starten", action: "reboot" },
                        { label: "Ausschalten", action: "poweroff" },
                        { label: "Abmelden", action: "logout" }
                    ].concat(session.serverModeAvailable
                             ? [{ label: "Server-Modus", action: "serverMode", icon: "server" }] : [])
                    delegate: Rectangle {
                        required property var modelData
                        width: powerColumn.width
                        height: 40
                        radius: 10
                        color: pm.containsMouse ? Theme.hover : "transparent"
                        SvgIcon {
                            visible: !!parent.modelData.icon
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            name: parent.modelData.icon || "server"
                            size: 15
                        }
                        Text {
                            x: 14
                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.modelData.label
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: pm
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (parent.modelData.action === "serverMode") {
                                    powerMenu.confirmServer = true
                                    return
                                }
                                shell.closePopups()
                                session[parent.modelData.action]()
                            }
                        }
                        Accessible.role: Accessible.MenuItem
                        Accessible.name: modelData.label
                    }
                }
            }

            // Rückfrage für den Server-Modus
            Column {
                id: serverConfirm
                visible: powerMenu.confirmServer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                Row {
                    spacing: 10
                    SvgIcon { name: "server"; size: 18; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Server-Modus starten?"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                        font.bold: true
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Alle Programme werden geschlossen – speichere vorher deine Arbeit. "
                          + "Nur „Mein Server“ bleibt online, der PC geht nicht in Bereitschaft. "
                          + "Zurück geht es über den Anmeldebildschirm."
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    lineHeight: 1.25
                }
                Row {
                    anchors.right: parent.right
                    spacing: 8
                    bottomPadding: 2
                    CButton { text: "Abbrechen"; onClicked: powerMenu.confirmServer = false }
                    CButton {
                        text: "Starten"
                        primary: true
                        onClicked: {
                            shell.closePopups()
                            session.serverMode()
                        }
                    }
                }
            }
        }

        // Rechtsklick auf eine App
        // Angeheftete Apps lassen sich nur in der Taskleiste lösen (Rechtsklick dort) – hier steht dann
        // nur ein Hinweis. „Aus Startmenü entfernen“ fragt vorher nach.
        Rectangle {
            id: appMenu
            property string desktopId: ""
            property string appName: ""
            property bool pinned: false
            property bool autostart: false
            property bool confirming: false
            visible: false
            z: 3
            width: 270
            height: confirming ? confirmCol.implicitHeight + 24 : menuCol.implicitHeight + 8
            radius: 12
            color: Theme.raised
            border.color: Theme.hairline
            onVisibleChanged: if (!visible) confirming = false

            component MenuRow: Rectangle {
                id: mrow
                property string icon: ""
                property string label: ""
                property bool active: true
                property bool danger: false
                signal triggered()
                width: appMenu.width - 8
                height: 36
                radius: 9
                color: active && mrowMouse.containsMouse ? Theme.tint(0.08) : "transparent"
                SvgIcon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: mrow.icon; size: 15; visible: mrow.icon.length > 0; opacity: mrow.active ? 1 : 0.5 }
                Text {
                    x: mrow.icon.length > 0 ? 36 : 12
                    width: parent.width - x - 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: mrow.label
                    color: mrow.danger ? Theme.flame : (mrow.active ? Theme.text : Theme.textMuted)
                    elide: Text.ElideRight
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                MouseArea {
                    id: mrowMouse
                    anchors.fill: parent
                    enabled: mrow.active
                    hoverEnabled: true
                    cursorShape: mrow.active ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: mrow.triggered()
                }
                Accessible.role: Accessible.MenuItem
                Accessible.name: mrow.label
                Accessible.onPressAction: if (mrow.active) mrow.triggered()
            }

            Column {
                id: menuCol
                visible: !appMenu.confirming
                x: 4; y: 4
                spacing: 4
                MenuRow {
                    icon: "plus"
                    label: "Zur Ablage hinzufügen"
                    onTriggered: { shelf.addApp(appMenu.desktopId); appMenu.visible = false }
                }
                MenuRow {
                    objectName: "pinRow"
                    icon: "pin"
                    active: !appMenu.pinned
                    label: appMenu.pinned ? "In der Taskleiste angeheftet" : "An die Taskleiste anheften"
                    onTriggered: { apps.pin(appMenu.desktopId); appMenu.visible = false }
                }
                MenuRow {
                    objectName: "autostartRow"
                    icon: appMenu.autostart ? "check" : "power"
                    label: appMenu.autostart ? "Startet beim Anmelden – ausschalten" : "Beim Anmelden starten (Autostart)"
                    onTriggered: {
                        apps.setAutostart(appMenu.desktopId, !appMenu.autostart)
                        appMenu.visible = false
                    }
                }
                MenuRow {
                    objectName: "hideRow"
                    label: "Aus Startmenü entfernen …"
                    onTriggered: appMenu.confirming = true
                }
            }

            // Nachfrage vor dem Entfernen
            Column {
                id: confirmCol
                visible: appMenu.confirming
                x: 12; y: 12
                width: appMenu.width - 24
                spacing: 10
                Text {
                    width: parent.width
                    text: "„" + appMenu.appName + "“ aus dem Startmenü entfernen?"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    font.bold: true
                    wrapMode: Text.Wrap
                }
                Text {
                    width: parent.width
                    text: "Die App bleibt installiert. Wieder einblenden: Systemsteuerung › Darstellung › Startmenü."
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
                Row {
                    anchors.right: parent.right
                    spacing: 8
                    CButton {
                        objectName: "hideCancel"
                        text: "Abbrechen"
                        onClicked: appMenu.confirming = false
                    }
                    CButton {
                        objectName: "hideConfirm"
                        text: "Entfernen"
                        primary: true
                        onClicked: {
                            appMenu.visible = false
                            apps.hideFromStartMenu(appMenu.desktopId)
                        }
                    }
                }
            }
        }

        Rectangle {
            id: footer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 1
            height: 56
            radius: menu.radius - 1
            color: "transparent"

            // eckige Oberkante, runde Unterkante
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: parent.radius
                color: "transparent"
            }
            Divider {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Avatar {
                    size: 30
                    source: session.avatar
                    initials: session.initials
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: session.userName
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                IconButton {
                    width: 40
                    height: 40
                    icon: "lock"
                    iconSize: 16
                    label: "Sperren"
                    onClicked: {
                        shell.closePopups()
                        session.lock()
                    }
                }
                IconButton {
                    width: 40
                    height: 40
                    icon: "power"
                    iconSize: 16
                    label: "Ein/Aus"
                    active: powerMenu.visible
                    onClicked: powerMenu.visible = !powerMenu.visible
                }
            }
        }
    }
}
