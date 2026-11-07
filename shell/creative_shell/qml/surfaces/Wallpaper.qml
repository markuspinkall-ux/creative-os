import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import Creative

// Hintergrundbild – liegt hinter allen Fenstern, auf jedem Monitor.
// Auf dem Hauptbildschirm zeigt es die Dateien vom Schreibtisch (wie bei Windows).
Item {
    id: root
    focus: true

    // Tastatur auf dem Schreibtisch: Entf = in den Papierkorb, Eingabe = öffnen
    Keys.onDeletePressed: desktop.trashSelected()
    Keys.onReturnPressed: desktop.openSelected()
    Keys.onEnterPressed: desktop.openSelected()
    Keys.onEscapePressed: desktop.clearSelection()
    Keys.onPressed: (event) => {
        if (!root.showIcons) return
        if (event.matches(StandardKey.Copy)) {
            desktop.copySelected()
            event.accepted = true
        } else if (event.matches(StandardKey.Paste)) {
            desktop.paste()
            event.accepted = true
        }
    }

    property string screenName
    readonly property bool showIcons: shell.primaryScreen === "" || shell.primaryScreen === screenName
    readonly property int barSpace: 74

    // Ziehen: Schreibtisch-Symbol → Ablage, oder Ablage-Eintrag heraus (= entfernen)
    property string dragPath: ""
    property bool dragIsDir: false
    property string dragTint: ""
    property string dragExt: ""
    property string dragShelfKey: ""
    property var dragShelfItem: null

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
        id: backgroundMouse
        property point origin
        property bool selecting: false
        anchors.fill: parent
        onPressed: (mouse) => {
            if (mouse.button !== Qt.LeftButton || !root.showIcons) return
            marquee.width = 0
            marquee.height = 0
            origin = Qt.point(mouse.x, mouse.y)
        }
        onPositionChanged: (mouse) => {
            if (!(mouse.buttons & Qt.LeftButton) || !root.showIcons) return
            if (!selecting && Math.abs(mouse.x - origin.x) + Math.abs(mouse.y - origin.y) < 6) return
            if (!selecting) {
                root.forceActiveFocus()
                shell.closePopups()
                selecting = true
            }
            marquee.x = Math.min(origin.x, mouse.x)
            marquee.y = Math.min(origin.y, mouse.y)
            marquee.width = Math.abs(mouse.x - origin.x)
            marquee.height = Math.abs(mouse.y - origin.y)
            const rows = []
            for (let i = 0; i < icons.count; ++i) {
                const item = icons.itemAtIndex(i)
                if (!item) continue
                const p = item.mapToItem(root, 3, 3)
                if (p.x < marquee.x + marquee.width && p.x + item.width - 6 > marquee.x
                        && p.y < marquee.y + marquee.height && p.y + item.height - 6 > marquee.y)
                    rows.push(i)
            }
            desktop.selectRows(rows)
        }
        onReleased: (mouse) => {
            if (mouse.button === Qt.LeftButton) selecting = false
        }
        onCanceled: selecting = false
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => {
            if (marquee.width > 0 || marquee.height > 0) {
                marquee.width = 0
                marquee.height = 0
                if (mouse.button === Qt.LeftButton) return
            }
            root.forceActiveFocus()
            shell.closePopups()
            if (mouse.button === Qt.RightButton && root.showIcons) {
                if (desktop.selectedCount > 0) itemMenu.openAt(mouse.x, mouse.y)
                else bgMenu.openAt(mouse.x, mouse.y)
            } else {
                desktop.clearSelection()
            }
        }
        // Doppelklick auf den freien Schreibtisch: alle Fenster minimieren (nochmal: zurückholen)
        onDoubleClicked: (mouse) => { if (mouse.button === Qt.LeftButton) tasks.showDesktop() }
    }

    Rectangle {
        id: marquee
        z: 4
        visible: backgroundMouse.selecting
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2)
        border.color: Theme.accent
    }

    component WidgetGrip: Item {
        property bool highlighted: false
        implicitWidth: dots.implicitWidth
        implicitHeight: dots.implicitHeight
        opacity: highlighted ? 0.8 : 0.35
        Grid {
            id: dots
            columns: 2
            spacing: 3
            Repeater { model: 6; Rectangle { width: 3; height: 3; radius: 1.5; color: Theme.text } }
        }
    }

    DesktopFeed {
        source: rssWidget
        title: "RSS-Nachrichten"
        hint: "Eine Feed-Adresse pro Zeile"
        defaultY: 230
    }

    DesktopFeed {
        source: weatherWidget
        title: "Wetter"
        hint: "Ort oder Postleitzahl"
        defaultY: 430
        isWeather: true
    }

    component DesktopFeed: Rectangle {
        id: widget
        required property var source
        required property string title
        required property string hint
        required property int defaultY
        property bool isWeather: false
        readonly property real maxX: Math.max(8, root.width - width - 8)
        readonly property real maxY: Math.max(8, root.height - root.barSpace - height - 8)
        function homeX() { return source.posX < 0 ? maxX : 8 + source.posX * (maxX - 8) }
        function homeY() { return source.posY < 0 ? Math.min(defaultY, maxY) : 8 + source.posY * (maxY - 8) }
        function restorePosition() {
            x = Qt.binding(() => widget.homeX())
            y = Qt.binding(() => widget.homeY())
        }
        x: homeX()
        y: homeY()
        width: 320
        height: content.implicitHeight + 24
        visible: root.showIcons && source.enabled
        radius: 22
        color: Qt.rgba(Theme.bar.r, Theme.bar.g, Theme.bar.b, Math.min(Theme.bar.a, 0.85))
        border.color: Theme.hairline

        WidgetGrip {
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            highlighted: handle.containsMouse || handle.pressed
            MouseArea {
                id: handle
                anchors.fill: parent
                anchors.margins: -7
                hoverEnabled: true
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                drag.target: widget
                drag.minimumX: 8
                drag.minimumY: 8
                drag.maximumX: widget.maxX
                drag.maximumY: widget.maxY
                onReleased: {
                    if (drag.active)
                        widget.source.setPos(widget.maxX > 8 ? (widget.x - 8) / (widget.maxX - 8) : 0,
                                             widget.maxY > 8 ? (widget.y - 8) / (widget.maxY - 8) : 0)
                    widget.restorePosition()
                }
                onCanceled: widget.restorePosition()
            }
        }

        Column {
            id: content
            x: 30
            y: 12
            width: parent.width - x - 12
            spacing: 5
            RowLayout {
                width: parent.width
                spacing: 6
                Text {
                    Layout.fillWidth: true
                    text: widget.title
                    color: Theme.text
                    font.bold: true
                    elide: Text.ElideRight
                }
                CButton {
                    text: "Einstellen"
                    onClicked: widgetEditor.edit(widget.source, widget.title, widget.hint, widget.isWeather)
                }
                IconButton {
                    icon: "refresh"
                    label: "Aktualisieren"
                    iconSize: 18
                    Layout.preferredWidth: 32
                    Layout.preferredHeight: 36
                    onClicked: widget.source.refresh()
                }
            }
            Text {
                width: parent.width
                visible: text.length > 0
                text: widget.source.message || (widget.source.value ? "" : widget.hint)
                textFormat: Text.PlainText
                color: Theme.textMuted
                wrapMode: Text.Wrap
            }
            Repeater {
                model: widget.source.rows
                delegate: Text {
                    required property var modelData
                    width: content.width
                    text: modelData.title
                    textFormat: Text.PlainText
                    color: modelData.url ? Theme.accent : Theme.text
                    elide: Text.ElideRight
                    MouseArea {
                        anchors.fill: parent
                        enabled: !!parent.modelData.url
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: Qt.openUrlExternally(parent.modelData.url)
                    }
                }
            }
            Text { visible: widget.isWeather; text: "Wetterdaten: Open-Meteo"; color: Theme.textMuted }
        }
    }

    // Ein normales Fenster bekommt Tastaturfokus. Der Wayland-Hintergrund
    // selbst bleibt eine Layer-Shell-Fläche ohne Tastaturinteraktion.
    Window {
        id: widgetEditor
        transientParent: null
        visible: false
        flags: Qt.Dialog
        width: 440
        height: 250
        minimumWidth: 320
        minimumHeight: 230
        color: Theme.surface

        property var source
        property bool isWeather: false

        function edit(model, heading, hint, weather) {
            source = model
            title = heading + " einstellen"
            isWeather = weather
            field.placeholderText = hint
            field.text = model.value
            error.text = ""
            show()
            requestActivate()
            field.forceActiveFocus()
        }

        function save() {
            error.text = source.saveInput(field.text)
            if (!error.text)
                close()
        }

        Shortcut { sequence: "Escape"; onActivated: widgetEditor.close() }
        Shortcut { sequence: "Ctrl+Return"; onActivated: widgetEditor.save() }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            Label {
                Layout.fillWidth: true
                text: widgetEditor.title
                color: Theme.text
                font.bold: true
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                TextArea {
                    id: field
                    selectByMouse: true
                    color: Theme.text
                    placeholderTextColor: Theme.textMuted
                    wrapMode: TextEdit.WrapAnywhere
                    Accessible.name: placeholderText
                    Keys.onReturnPressed: (event) => {
                        if (widgetEditor.isWeather) widgetEditor.save()
                        else event.accepted = false
                    }
                    background: Rectangle {
                        color: Theme.ground
                        radius: 8
                        border.color: field.activeFocus ? Theme.accent : Theme.hairline
                    }
                }
            }

            Label {
                id: error
                Layout.fillWidth: true
                visible: text.length > 0
                color: Theme.flame
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }

            RowLayout {
                Layout.fillWidth: true
                CButton { text: "Einfügen"; enabled: field.canPaste; onClicked: { field.paste(); field.forceActiveFocus() } }
                Item { Layout.fillWidth: true }
                CButton { text: "Abbrechen"; onClicked: widgetEditor.close() }
                CButton { text: "Speichern"; primary: true; onClicked: widgetEditor.save() }
            }
        }
    }

    // Leistungsanzeige über dem Hintergrund und unter den Schreibtisch-Symbolen.
    Rectangle {
        id: statsBox
        visible: root.showIcons && desktopStats.enabled && desktopStats.tiles.length > 0
        readonly property real maxX: Math.max(8, root.width - width - 8)
        readonly property real maxY: Math.max(8, root.height - root.barSpace - height - 8)
        x: homeX()
        y: homeY()
        function homeX() {
            return desktopStats.posX < 0 ? Math.max(8, maxX - 10) : 8 + desktopStats.posX * (maxX - 8)
        }
        function homeY() {
            return desktopStats.posY < 0 ? Math.min(16, maxY) : 8 + desktopStats.posY * (maxY - 8)
        }
        function restoreBindings() {
            x = Qt.binding(() => statsBox.homeX())
            y = Qt.binding(() => statsBox.homeY())
        }
        width: stats.implicitWidth + 42
        height: stats.implicitHeight + 24
        radius: 22
        color: Qt.rgba(Theme.bar.r, Theme.bar.g, Theme.bar.b, Math.min(Theme.bar.a, 0.85))
        border.width: 1
        border.color: Theme.hairline

        WidgetGrip {
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            highlighted: statsMove.containsMouse || statsMove.pressed
            MouseArea {
                id: statsMove
                anchors.fill: parent
                anchors.margins: -7
                hoverEnabled: true
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                drag.target: statsBox
                drag.minimumX: 8
                drag.maximumX: statsBox.maxX
                drag.minimumY: 8
                drag.maximumY: statsBox.maxY
                onReleased: {
                    if (drag.active)
                        desktopStats.setPos(statsBox.maxX > 8 ? (statsBox.x - 8) / (statsBox.maxX - 8) : 0,
                                            statsBox.maxY > 8 ? (statsBox.y - 8) / (statsBox.maxY - 8) : 0)
                    statsBox.restoreBindings()
                }
                onCanceled: statsBox.restoreBindings()
            }
        }

        Grid {
            id: stats
            x: 30
            y: 12
            columns: 2           // CPU | Arbeitsspeicher  –  Datenträger | Netzwerk  (–  GPU)
            spacing: 6
            Repeater {
                model: desktopStats.tiles
                delegate: PerfTile {
                    plain: true
                    width: 196
                    height: 58
                    graphWidth: 64
                    title: modelData.title
                    value: modelData.value
                    sub: modelData.sub
                    history: modelData.history
                    color: modelData.color
                    onClicked: desktopStats.openTaskManager()
                }
            }
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
                property point pressPos
                onPositionChanged: (mouse) => {
                    if (!(mouse.buttons & Qt.LeftButton))
                        return
                    if (root.dragPath === "" && Math.abs(mouse.x - pressPos.x) + Math.abs(mouse.y - pressPos.y) > 12) {
                        root.dragPath = model.path
                        root.dragIsDir = model.isDir
                        root.dragTint = model.tint
                        root.dragExt = model.ext
                    }
                    if (root.dragPath !== "") {
                        const p = cell.mapToItem(root, mouse.x, mouse.y)
                        ghost.x = p.x - ghost.width / 2
                        ghost.y = p.y - ghost.height / 2
                    }
                }
                onReleased: (mouse) => {
                    if (root.dragPath === "")
                        return
                    const p = cell.mapToItem(shelfBox, mouse.x, mouse.y)
                    if (shelfBox.visible && p.x >= 0 && p.y >= 0 && p.x <= shelfBox.width && p.y <= shelfBox.height + 20)
                        shelf.addPath(root.dragPath)
                    root.dragPath = ""
                }
                onPressed: (mouse) => {
                    pressPos = Qt.point(mouse.x, mouse.y)
                    root.forceActiveFocus()
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

    // ---- Ablage oben mittig (wie das Dock bei macOS) ------------------------------------
    Rectangle {
        id: shelfBox
        visible: root.showIcons && shelf.enabled
        readonly property bool dropHover: shelfDrop.containsDrag || (root.dragPath !== "" && ghost.y < y + height + 30
                                          && ghost.x + ghost.width > x && ghost.x < x + width)
        // frei verschiebbar (am Griff links oder an einer freien Stelle ziehen); Position bleibt gespeichert
        readonly property real maxX: root.width - width - 8
        readonly property real maxY: root.height - root.barSpace - height - 8
        property bool moving: false
        function homeX() { return shelf.posX >= 0 ? 8 + shelf.posX * (maxX - 8) : (root.width - width) / 2 }
        function homeY() { return shelf.posY >= 0 ? 8 + shelf.posY * (maxY - 8) : 12 }
        function rebind() {
            x = Qt.binding(() => shelfBox.homeX())
            y = Qt.binding(() => shelfBox.homeY())
        }
        x: homeX()
        y: homeY()
        z: 5
        height: 66
        width: shelf.items.length ? shelfRow.implicitWidth + 44 : emptyHint.implicitWidth + 64
        Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        radius: 22
        color: Theme.bar
        border.width: 1
        border.color: dropHover ? Theme.accent : Theme.hairline
        scale: dropHover ? 1.04 : 1
        Behavior on scale { NumberAnimation { duration: 140 } }

        // Verschieben: freie Fläche der Ablage ziehen (liegt unter den Symbolen)
        MouseArea {
            id: shelfMove
            anchors.fill: parent
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            property point start
            property point origin
            onPressed: (mouse) => {
                shell.closePopups()
                if (mouse.button !== Qt.LeftButton) return
                const p = mapToItem(root, mouse.x, mouse.y)
                start = p
                origin = Qt.point(shelfBox.x, shelfBox.y)
                shelfBox.moving = true
            }
            onPositionChanged: (mouse) => {
                if (!shelfBox.moving) return
                const p = mapToItem(root, mouse.x, mouse.y)
                shelfBox.x = Math.max(8, Math.min(shelfBox.maxX, origin.x + p.x - start.x))
                shelfBox.y = Math.max(8, Math.min(shelfBox.maxY, origin.y + p.y - start.y))
            }
            onReleased: (mouse) => {
                if (!shelfBox.moving) return
                const fx = shelfBox.maxX > 8 ? (shelfBox.x - 8) / (shelfBox.maxX - 8) : 0
                const fy = shelfBox.maxY > 8 ? (shelfBox.y - 8) / (shelfBox.maxY - 8) : 0
                shelfBox.moving = false
                if (Math.abs(shelfBox.x - origin.x) + Math.abs(shelfBox.y - origin.y) > 3)
                    shelf.setPos(fx, fy)
                shelfBox.rebind()
            }
            onClicked: (mouse) => {
                if (mouse.button === Qt.RightButton) {
                    const p = mapToItem(root, mouse.x, mouse.y)
                    shelfBgMenu.openAt(p.x, p.y)
                }
            }
        }
        // Griff links (zeigt, dass man die Ablage verschieben kann)
        WidgetGrip {
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            highlighted: shelfMove.containsMouse || shelfMove.pressed
        }

        // leer: Hinweis
        Row {
            id: emptyHint
            visible: shelf.items.length === 0
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: 8
            spacing: 10
            opacity: 0.75
            SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "plus"; size: 16 }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Ablage – Apps, Ordner und Dateien hierher ziehen"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
        }

        Row {
            id: shelfRow
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: 8
            spacing: 6
            Repeater {
                model: shelf.items
                delegate: Item {
                    id: slot
                    required property var modelData
                    readonly property bool dragged: root.dragShelfKey === modelData.key
                    width: 52
                    height: 52
                    opacity: dragged ? 0.25 : (modelData.missing ? 0.45 : 1)

                    Rectangle {
                        anchors.fill: parent
                        radius: 14
                        color: sm.containsMouse ? Qt.rgba(1, 1, 1, 0.09) : "transparent"
                    }
                    Item {
                        id: slotIcon
                        anchors.centerIn: parent
                        width: 38; height: 38
                        scale: sm.containsMouse && !sm.pressed ? 1.15 : 1
                        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                        Image {
                            visible: slot.modelData.kind === "app"
                            anchors.fill: parent
                            sourceSize.width: 76
                            sourceSize.height: 76
                            source: slot.modelData.kind === "app" ? "image://icon/" + slot.modelData.icon : ""
                            // The icon provider creates QPixmaps on the GUI thread.
                            asynchronous: false
                            smooth: true
                        }
                        FileIcon {
                            visible: slot.modelData.kind !== "app"
                            anchors.centerIn: parent
                            size: 36
                            isDir: slot.modelData.kind === "dir"
                            tint: slot.modelData.tint
                            ext: slot.modelData.ext
                        }
                    }
                    // Entfernen-Knopf beim Darüberfahren (alternativ: herausziehen oder Rechtsklick)
                    Rectangle {
                        id: removeBadge
                        visible: (sm.containsMouse || rmMouse.containsMouse) && root.dragShelfKey === ""
                        z: 3
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: -3
                        width: 18; height: 18; radius: 9
                        color: rmMouse.containsMouse ? "#e5484d" : Theme.raised
                        border.color: Theme.hairline
                        Text { anchors.centerIn: parent; text: "×"; color: "white"; font.pixelSize: 13; font.bold: true }
                        MouseArea {
                            id: rmMouse
                            anchors.fill: parent
                            anchors.margins: -3
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: shelf.remove(slot.modelData.key)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Von der Ablage entfernen"
                    }
                    // Name unter der Ablage beim Darüberfahren
                    Rectangle {
                        visible: sm.containsMouse && root.dragShelfKey === ""
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: parent.height + 14
                        width: tipText.implicitWidth + 18
                        height: 26
                        radius: 9
                        color: Theme.raised
                        border.color: Theme.hairline
                        Text {
                            id: tipText
                            anchors.centerIn: parent
                            text: slot.modelData.name
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                        }
                    }
                    MouseArea {
                        id: sm
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        property point pressPos
                        onPressed: (mouse) => { pressPos = Qt.point(mouse.x, mouse.y); shell.closePopups() }
                        onPositionChanged: (mouse) => {
                            if (!(mouse.buttons & Qt.LeftButton))
                                return
                            if (root.dragShelfKey === "" && Math.abs(mouse.x - pressPos.x) + Math.abs(mouse.y - pressPos.y) > 12) {
                                root.dragShelfKey = slot.modelData.key
                                root.dragShelfItem = slot.modelData
                            }
                            if (root.dragShelfKey !== "") {
                                const p = slot.mapToItem(root, mouse.x, mouse.y)
                                ghost.x = p.x - ghost.width / 2
                                ghost.y = p.y - ghost.height / 2
                            }
                        }
                        onReleased: (mouse) => {
                            if (root.dragShelfKey === "")
                                return
                            const p = slot.mapToItem(shelfBox, mouse.x, mouse.y)
                            const inside = p.x >= 0 && p.y >= 0 && p.x <= shelfBox.width && p.y <= shelfBox.height + 20
                            if (!inside)
                                shelf.remove(root.dragShelfKey)          // herausgezogen = entfernt
                            else
                                shelf.move(root.dragShelfKey, Math.floor((p.x - shelfRow.x) / (52 + 6)))
                            root.dragShelfKey = ""
                            root.dragShelfItem = null
                        }
                        onClicked: (mouse) => {
                            if (mouse.button === Qt.RightButton) {
                                shelfMenu.key = slot.modelData.key
                                shelfMenu.isApp = slot.modelData.kind === "app"
                                const p = slot.mapToItem(root, mouse.x, mouse.y)
                                shelfMenu.openAt(p.x, p.y + 10)
                            } else if (root.dragShelfKey === "") {
                                shelf.open(slot.modelData.key)
                            }
                        }
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: slot.modelData.name
                }
            }
        }

        // Aus anderen Programmen hineinziehen (z. B. aus „Dateien“)
        DropArea {
            id: shelfDrop
            anchors.fill: parent
            anchors.margins: -12
            onDropped: (drop) => {
                if (drop.hasUrls) {
                    shelf.addUrls(drop.urls)
                    drop.acceptProposedAction()
                }
            }
        }
    }

    // Was gerade gezogen wird
    Item {
        id: ghost
        visible: root.dragPath !== "" || root.dragShelfKey !== ""
        z: 20
        width: 52; height: 52
        opacity: 0.85
        Image {
            visible: root.dragShelfItem !== null && root.dragShelfItem.kind === "app"
            anchors.centerIn: parent
            width: 38; height: 38
            sourceSize.width: 76; sourceSize.height: 76
            source: root.dragShelfItem && root.dragShelfItem.kind === "app" ? "image://icon/" + root.dragShelfItem.icon : ""
        }
        FileIcon {
            visible: root.dragPath !== "" || (root.dragShelfItem !== null && root.dragShelfItem.kind !== "app")
            anchors.centerIn: parent
            size: 38
            isDir: root.dragPath !== "" ? root.dragIsDir : (root.dragShelfItem ? root.dragShelfItem.kind === "dir" : false)
            tint: root.dragPath !== "" ? root.dragTint : (root.dragShelfItem ? root.dragShelfItem.tint : "")
            ext: root.dragPath !== "" ? root.dragExt : (root.dragShelfItem ? root.dragShelfItem.ext : "")
        }
    }

    // ---- Menüs ------------------------------------------------------------------------
    DesktopMenu {
        id: shelfMenu
        property string key: ""
        property bool isApp: false
        entries: isApp ? [
            { label: "Öffnen", icon: "open", act: "open" },
            { sep: true },
            { label: "Von der Ablage entfernen", icon: "trash", act: "remove" }
        ] : [
            { label: "Öffnen", icon: "open", act: "open" },
            { label: "In Dateien zeigen", icon: "files", act: "files" },
            { sep: true },
            { label: "Von der Ablage entfernen", icon: "trash", act: "remove" }
        ]
        onTriggered: (act) => {
            if (act === "open") shelf.open(key)
            else if (act === "files") shelf.showInFiles(key)
            else if (act === "remove") shelf.remove(key)
        }
    }
    DesktopMenu {
        id: shelfBgMenu
        entries: [
            { label: "Ablage oben mittig anordnen", icon: "restore", act: "center" },
            { label: "Ablage ausblenden", icon: "close", act: "hide" }
        ]
        onTriggered: (act) => {
            if (act === "center") shelf.resetPos()
            else if (act === "hide") shelf.setEnabled(false)
        }
    }
    DesktopMenu {
        id: itemMenu
        entries: [
            { label: "Öffnen", icon: "open", act: "open" },
            { label: "In Dateien zeigen", icon: "files", act: "files" },
            { label: "Zur Ablage hinzufügen", icon: "plus", act: "shelf" },
            { sep: true },
            { label: "Kopieren", icon: "files", act: "copy" },
            { label: "Löschen (in den Papierkorb)  ·  Entf", icon: "trash", act: "trash" }
        ].concat(desktop.canPaste ? [{ label: "Einfügen", icon: "plus", act: "paste" }] : [])
        onTriggered: (act) => {
            if (act === "shelf") desktop.selectedPaths().forEach(p => shelf.addPath(p))
            else if (act === "open") desktop.openSelected()
            else if (act === "files") desktop.openInFiles()
            else if (act === "trash") desktop.trashSelected()
            else if (act === "copy") desktop.copySelected()
            else if (act === "paste") desktop.paste()
        }
    }
    DesktopMenu {
        id: bgMenu
        entries: (desktop.canPaste ? [{ label: "Einfügen", icon: "plus", act: "paste" }] : []).concat([
            { label: "Neuer Ordner", icon: "folder-plus", act: "new" },
            { label: "Schreibtisch in Dateien öffnen", icon: "files", act: "folder" },
            { sep: true },
            { label: rssWidget.enabled ? "RSS-Gadget ausblenden" : "RSS-Gadget einblenden", icon: "plus", act: "rss" },
            { label: weatherWidget.enabled ? "Wetter-Gadget ausblenden" : "Wetter-Gadget einblenden", icon: "plus", act: "weather" },
            { label: desktopStats.enabled ? "Leistungsanzeige ausblenden" : "Leistungsanzeige einblenden", icon: "taskmanager", act: "stats" },
            { label: "Taskmanager", icon: "taskmanager", act: "taskmanager" },
            { label: visualizer.enabled ? "Musik-Visualizer ausblenden" : "Musik-Visualizer einblenden", icon: "music", act: "viz" },
            { label: shelf.enabled ? "Ablage ausblenden" : "Ablage einblenden", icon: "plus", act: "shelf" },
            { sep: true },
            { label: "Einstellungen", icon: "settings", act: "settings" }
        ])
        onTriggered: (act) => {
            if (act === "paste") desktop.paste()
            else if (act === "new") desktop.newFolder()
            else if (act === "folder") desktop.openFolder()
            else if (act === "settings") session.openSettings()
            else if (act === "rss") rssWidget.toggle()
            else if (act === "weather") weatherWidget.toggle()
            else if (act === "stats") desktopStats.setEnabled(!desktopStats.enabled)
            else if (act === "taskmanager") desktopStats.openTaskManager()
            else if (act === "viz") visualizer.setEnabled(!visualizer.enabled)
            else if (act === "shelf") shelf.setEnabled(!shelf.enabled)
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
