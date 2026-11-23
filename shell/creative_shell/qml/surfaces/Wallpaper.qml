import QtQuick
import QtQuick.Templates as GibeonT
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects
import Creative

// Hintergrundbild – liegt hinter allen Fenstern, auf jedem Monitor.
// Die Schreibtisch-Symbole werden nach ihrem Zielmonitor gefiltert.
Item {
    id: root
    focus: true

    // Tastatur auf dem Schreibtisch: Entf = in den Papierkorb, Eingabe = öffnen
    Keys.onDeletePressed: desktop.trashSelected()
    Keys.onReturnPressed: desktop.openSelected()
    Keys.onEnterPressed: desktop.openSelected()
    Keys.onEscapePressed: { if (root.movePath !== "") root.cancelMove(); else desktop.clearSelection() }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_F2) {
            root.startRename()
            event.accepted = true
        } else if (event.matches(StandardKey.Copy)) {
            desktop.copySelected()
            event.accepted = true
        } else if (event.matches(StandardKey.Paste)) {
            desktop.paste()
            event.accepted = true
        }
    }

    // ---- Umbenennen (F2, Rechtsklick › Umbenennen, neuer Ordner) ----
    property string renamePath: ""
    property string renameError: ""
    function startRename() {
        const sel = desktop.selectedPaths()
        if (sel.length === 1) { root.renameError = ""; root.renamePath = sel[0] }
    }
    function commitRename(path, text) {
        if (root.renamePath !== path) return
        const err = desktop.rename(path, text)
        if (err) root.renameError = err
        else { root.renamePath = ""; root.renameError = ""; root.takeKeyboard() }
    }
    function cancelRename() { root.renamePath = ""; root.renameError = ""; root.takeKeyboard() }
    Connections {
        target: desktop
        function onRenameRequested(path) { root.renameError = ""; root.renamePath = path }
    }

    // Tastatur holen (Entf, Strg+C …): Fenster aktivieren + Fokus aufs Schreibtisch-Element
    function takeKeyboard() {
        if (root.Window.window && !root.Window.window.active) root.Window.window.requestActivate()
        root.forceActiveFocus()
    }

    property string screenName
    readonly property string iconDragFormat: "application/x-creative-desktop-icon"
    readonly property int barSpace: 52
    // obere Leiste mit dem Systemtray: Widgets und Symbole bleiben darunter. Sitzt der Tray in der
    // Taskleiste, gibt es oben keine Leiste – dann docken Widgets direkt am oberen Bildschirmrand an.
    // Kommt der Tray wieder nach oben, rücken sie automatisch darunter (Positionen sind relativ gespeichert).
    readonly property int topSpace: (typeof shell !== "undefined" && shell && shell.trayInTaskbar) ? 0 : 50
    readonly property int minY: topSpace + 8
    // Fluid-Glas der Widgets: diese Ebene liegt weichgezeichnet hinter jedem Widget
    readonly property Item wallLayer: wallLayerItem

    // Milchglas hinter einem Widget: weichgezeichneter Hintergrund, Glas-Tönung, heller Rand,
    // Lichtkante oben. Das Widget selbst ist durchsichtig; diese Fläche liegt ganz unten darin.
    component GlassBackdrop: Item {
        id: gb
        required property Item target
        property color edge: Theme.glassEdge
        property int edgeWidth: 1
        anchors.fill: parent
        z: -1
        ShaderEffectSource {
            id: gbSrc
            anchors.fill: parent
            sourceItem: root.wallLayer
            sourceRect: Qt.rect(gb.target.x, gb.target.y, gb.target.width, gb.target.height)
            live: true
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            source: gbSrc
            blurEnabled: true
            blur: 1.0
            blurMax: 48
            saturation: 0.15
            maskEnabled: true
            maskSource: gbMask
        }
        Item {
            id: gbMask
            anchors.fill: parent
            layer.enabled: true
            visible: false
            Rectangle { anchors.fill: parent; radius: gb.target.radius; color: "black" }
        }
        Rectangle {
            anchors.fill: parent
            radius: gb.target.radius
            color: Theme.light ? Qt.rgba(1, 1, 1, 0.45) : Qt.rgba(28 / 255, 33 / 255, 46 / 255, 0.42)
            border.color: gb.edge
            border.width: gb.edgeWidth
        }
        Rectangle {
            x: gb.target.radius
            y: 1
            width: Math.max(0, parent.width - 2 * gb.target.radius)
            height: 1
            color: Theme.glassShine
        }
    }

    // Eine Position auf dem Ersatzmonitor ändert die gespeicherte Zielposition nicht.
    property var fallbackPositions: ({})

    function onFallback(key) {
        const target = shell.widgetScreens[key]
        return !!target && !shell.screenNames.includes(target)
    }

    function widgetOnScreen(key) {
        const target = shell.widgetScreens[key]
        const screens = shell.screenNames
        if (target && screens.includes(target))
            return root.screenName === target
        const primary = shell.primaryScreen
        return root.screenName === (screens.includes(primary) ? primary : screens[0])
    }

    function widgetPosition(key, source, axis) {
        const fallback = onFallback(key) ? fallbackPositions[key] : undefined
        return fallback ? fallback[axis] : (axis === "x" ? source.posX : source.posY)
    }

    function setFallbackPosition(key, x, y) {
        fallbackPositions = Object.assign({}, fallbackPositions, { [key]: { x: x, y: y } })
    }

    function saveWidgetPosition(key, source, item) {
        const x = item.maxX > 8 ? (item.x - 8) / (item.maxX - 8) : 0
        const y = item.maxY > root.minY ? (item.y - root.minY) / (item.maxY - root.minY) : 0
        if (onFallback(key))
            setFallbackPosition(key, x, y)
        else
            source.setPos(x, y)
    }

    // ---- Widget auf einen anderen Monitor ziehen ----------------------------------------------
    // Beim Ziehen am Griff bekommt diese Fläche die Maus auch außerhalb ihres Monitors (Wayland).
    // Liegt der Zeiger über einem anderen Monitor, zeigt der dort einen Umriss; beim Loslassen
    // wandert das Widget an genau diese Stelle (Position bleibt wie gewohnt gespeichert).
    function crossTarget(item, handle, mouse) {
        const p = handle.mapToItem(root, mouse.x, mouse.y)
        if (p.x >= 0 && p.y >= 0 && p.x < root.width && p.y < root.height)
            return null
        const here = shell.screenGeometry(root.screenName)
        if (here.width === undefined)
            return null
        const gx = here.x + p.x, gy = here.y + p.y
        const name = shell.screenAt(gx, gy)
        if (!name || name === root.screenName)
            return null
        const g = shell.screenGeometry(name)
        const grab = handle.mapToItem(item, mouse.x, mouse.y)
        const maxX = Math.max(8, g.width - item.width - 8)
        const maxY = Math.max(root.minY, g.height - root.barSpace - item.height - 8)
        const x = Math.max(8, Math.min(maxX, gx - g.x - grab.x))
        const y = Math.max(root.minY, Math.min(maxY, gy - g.y - grab.y))
        return { screen: name, x: x, y: y, nx: maxX > 8 ? (x - 8) / (maxX - 8) : 0,
                 ny: maxY > root.minY ? (y - root.minY) / (maxY - root.minY) : 0 }
    }

    function crossDragMove(key, item, handle, mouse) {
        const t = crossTarget(item, handle, mouse)
        item.opacity = t ? 0.35 : 1
        if (t)
            shell.setWidgetGhost({ key: key, screen: t.screen, x: t.x, y: t.y, w: item.width, h: item.height })
        else if (shell.widgetGhost.key === key)
            shell.setWidgetGhost({})
    }

    // true = Widget ist auf einen anderen Monitor gewandert
    function crossDragDrop(key, item, handle, mouse, setPos) {
        const t = crossTarget(item, handle, mouse)
        item.opacity = 1
        shell.setWidgetGhost({})
        if (!t)
            return false
        setPos(t.nx, t.ny)
        const err = shell.setWidgetScreen(key, t.screen)
        if (err) {
            console.warn(err)
            return false
        }
        const positions = Object.assign({}, root.fallbackPositions)
        delete positions[key]
        root.fallbackPositions = positions
        return true
    }

    function crossDragCancel(key, item) {
        item.opacity = 1
        if (shell.widgetGhost.key === key)
            shell.setWidgetGhost({})
    }

    // Umriss des Widgets, das gerade von einem anderen Monitor hierher gezogen wird
    Rectangle {
        z: 50
        readonly property var g: shell.widgetGhost
        visible: g.screen === root.screenName
        x: g.x || 0
        y: g.y || 0
        width: g.w || 0
        height: g.h || 0
        radius: g.icon ? 10 : 22
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
        border.color: Theme.accent
        border.width: 2
    }

    // Ziehen: Schreibtisch-Symbol → Ablage, oder Ablage-Eintrag heraus (= entfernen)
    property string dragPath: ""
    property bool dragIsDir: false
    property string dragTint: ""
    property string dragExt: ""
    property string dragShelfKey: ""
    property var dragShelfItem: null
    property string dragUris: ""        // text/uri-list für andere Programme (Dateien, Brave …)
    property int pendingRow: -1          // Klick auf Ausgewähltes: erst beim Loslassen nur dieses wählen

    // Ziehen einer Datei beenden – auch wenn das Betriebssystem kein „fertig“ meldet
    function endFileDrag() {
        dragPath = ""
        dragUris = ""
    }

    // ---- Symbole auf dem Schreibtisch verschieben (ohne System-Ziehen, damit es immer klappt) ----
    property string movePath: ""          // gerade verschobenes Symbol
    property var moveCell: null           // Zielplatz [Spalte, Zeile] (Vorschau)
    property string moveFolder: ""        // Ordner unter dem Mauszeiger
    property bool moveShelf: false        // über der Ablage

    function cellBlocked(c, r) { return !!icons.blocked[c + ":" + r] }
    function nearestFree(c, r) {
        if (!cellBlocked(c, r)) return [c, r]
        let best = null, bestD = 1e9
        for (let cc = 0; cc < icons.cols; ++cc)
            for (let rr = 0; rr < icons.rows; ++rr) {
                if (cellBlocked(cc, rr)) continue
                const d = (cc - c) * (cc - c) * 1.2 + (rr - r) * (rr - r)
                if (d < bestD) { bestD = d; best = [cc, rr] }
            }
        return best || [c, r]
    }
    function folderAt(px, py) {
        for (let i = 0; i < icons.count; ++i) {
            const it = icons.itemAtIndex(i)
            if (!it || !it.visible || !it.isDir || it.path === movePath) continue
            const q = it.mapToItem(root, 0, 0)
            if (px >= q.x + 6 && px < q.x + it.width - 6 && py >= q.y + 6 && py < q.y + it.height - 6)
                return it.path
        }
        return ""
    }
    function overShelf(px, py) {
        return shelfBox.visible && px > shelfBox.x - 12 && px < shelfBox.x + shelfBox.width + 12
               && py > shelfBox.y - 12 && py < shelfBox.y + shelfBox.height + 12
    }
    function updateMove(px, py) {
        ghost.x = px - ghost.width / 2
        ghost.y = py - ghost.height / 2
        moveShelf = overShelf(px, py)
        moveFolder = moveShelf ? "" : folderAt(px, py)
        moveCell = (moveShelf || moveFolder !== "") ? null : nearestFree.apply(null, icons.cellAt(px, py))
    }
    // ---- Symbol auf einen anderen Monitor ziehen (wie bei den Widgets) ------------------------
    // Liegt der Zeiger über dem Schreibtisch eines anderen Monitors, zeigt der dort einen Umriss
    // im Raster; beim Loslassen landet das Symbol (samt Auswahl) genau in dieser Zelle.
    // Der Platz wird wie gewohnt gespeichert (desktopIconCells).
    property var crossIcon: null          // { screen, col, row } oder null

    function iconCrossTarget(px, py) {
        const here = shell.screenGeometry(root.screenName)
        if (here.width === undefined)
            return null
        const gx = here.x + px, gy = here.y + py
        const name = shell.screenAt(gx, gy)
        if (!name || name === root.screenName)
            return null
        const g = shell.screenGeometry(name)
        const lx = gx - g.x, ly = gy - g.y
        if (tasks.windowAt(name, lx, ly))
            return null                   // über einem Fenster: an das Programm übergeben
        // gleiches Raster wie „icons“ auf jedem Monitor
        const left = icons.x, top = root.topSpace + 12
        const cols = Math.max(1, Math.floor((g.width - 24) / icons.cellWidth))
        const rows = Math.max(1, Math.floor((g.height - root.barSpace - root.topSpace - 24) / icons.cellHeight))
        const col = Math.max(0, Math.min(cols - 1, Math.floor((lx - left) / icons.cellWidth)))
        const row = Math.max(0, Math.min(rows - 1, Math.floor((ly - top) / icons.cellHeight)))
        return { screen: name, col: col, row: row,
                 x: left + col * icons.cellWidth, y: top + row * icons.cellHeight }
    }

    function crossIconMove(t) {
        crossIcon = t
        moveCell = null
        moveFolder = ""
        moveShelf = false
        shell.setWidgetGhost({ key: "icon", icon: true, screen: t.screen, x: t.x, y: t.y,
                               w: icons.cellWidth, h: icons.cellHeight })
    }

    function clearCrossIcon() {
        crossIcon = null
        if (shell.widgetGhost.key === "icon")
            shell.setWidgetGhost({})
    }

    function finishMove() {
        const path = movePath
        if (crossIcon) {
            desktop.placeDragged(path, crossIcon.screen, crossIcon.col, crossIcon.row)
        } else if (moveShelf) {
            const sel = desktop.selectedPaths()
            ;(sel.includes(path) ? sel : [path]).forEach(p => shelf.addPath(p))
        } else if (moveFolder !== "") {
            const sel = desktop.selectedPaths()
            desktop.dropUrls((sel.includes(path) ? sel : [path]).map(p => "file://" + p), moveFolder, "auto")
        } else if (moveCell) {
            desktop.pinCells(root.screenName, icons.slots)    // die anderen bleiben, wo sie sind
            desktop.placeDragged(path, root.screenName, moveCell[0], moveCell[1])
        }
        cancelMove()
    }
    function cancelMove() {
        clearCrossIcon()
        movePath = ""
        moveCell = null
        moveFolder = ""
        moveShelf = false
    }

    // Strg = kopieren, Umschalt = verschieben, sonst gleiches Laufwerk → verschieben
    function dropMode(drop) {
        if ((drop.modifiers & Qt.ControlModifier) || drop.proposedAction === Qt.CopyAction) return "copy"
        if (drop.modifiers & Qt.ShiftModifier) return "move"
        return "auto"
    }

    // Hintergrund (Farbe, Bild, bewegte Erde) als eine Ebene – Widgets im Fluid-Stil
    // zeigen diese Ebene weichgezeichnet hinter sich (Milchglas).
    Item {
        id: wallLayerItem
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            color: Theme.ground
        }

        Image {
            anchors.fill: parent
            source: wallpaperUrl
            // Beim bewegten Hintergrund liegt dieselbe Szene in Ebenen darüber
            visible: !(wallAnim.on && wallGround.status === Image.Ready)
            fillMode: Image.PreserveAspectCrop
            sourceSize.width: width
            sourceSize.height: height
            asynchronous: true
            smooth: true
            cache: true
        }

        // „Emerald Earth“ bewegt sich: Wolken ziehen, die Rakete schwebt, Sterne funkeln.
        // Sehr ruhig (eine Runde = 24 s) und nur, solange man den Schreibtisch auch sieht.
        Item {
            id: wallAnim
            objectName: "wallAnim"
            readonly property var d: (typeof wallpaperAnim !== "undefined" && wallpaperAnim) ? wallpaperAnim : ({})
            readonly property bool on: !!d.folder
            readonly property real s: Math.max(root.width / 3840, root.height / 2160)
            readonly property bool covered: {
                tasks.revision
                return tasks.largestWindowArea(root.screenName) > root.width * root.height * 0.85
            }
            readonly property bool running: on && root.visible && !covered
            property real phase: 0
            visible: on
            x: (root.width - width) / 2
            y: (root.height - height) / 2
            width: 3840 * s
            height: 2160 * s

            readonly property bool scene: !!d.layers
            NumberAnimation on phase {
                from: 0; to: 1
                duration: wallAnim.d.duration || 24000
                loops: Animation.Infinite
                running: wallAnim.running
            }

            Image {
                id: wallGround
                anchors.fill: parent
                source: wallAnim.on ? wallAnim.d.folder + "grund.svg" : ""
                z: -2
                sourceSize: Qt.size(width, height)
                asynchronous: true
            }
            // Wolken: zweite Lage mit verschobenen Schleiern, langsam überblendet
            Image {
                anchors.fill: parent
                visible: !wallAnim.scene
                source: wallAnim.on && !wallAnim.scene ? wallAnim.d.folder + "wolken.svg" : ""
                sourceSize: Qt.size(width, height)
                asynchronous: true
                opacity: 0.5 - 0.5 * Math.cos(2 * Math.PI * wallAnim.phase)
            }
            Repeater {
                model: wallAnim.on ? wallAnim.d.stars : []
                delegate: Rectangle {
                    required property var modelData
                    x: modelData.x * wallAnim.s - width / 2
                    y: modelData.y * wallAnim.s - height / 2
                    width: Math.max(1.5, modelData.r * 2 * wallAnim.s)
                    height: width
                    radius: width / 2
                    color: wallAnim.d.starColor || "#dce6ff"
                    opacity: modelData.o * (0.55 + 0.45 * Math.sin(2 * Math.PI * (wallAnim.phase * 6 * modelData.s + modelData.p)))
                }
            }
            // Rakete samt Spur schwebt in Flugrichtung vor und zurück
            Image {
                id: wallRocket
                anchors.fill: parent
                visible: !wallAnim.scene
                source: wallAnim.on && !wallAnim.scene ? wallAnim.d.folder + "rakete.svg" : ""
                sourceSize: Qt.size(width, height)
                asynchronous: true
                readonly property real heading: ((wallAnim.d.rocket ? wallAnim.d.rocket.angle : 90) - 90) * Math.PI / 180
                readonly property real bob: 18 * wallAnim.s * Math.sin(2 * Math.PI * wallAnim.phase * 2)
                transform: Translate { x: wallRocket.bob * Math.cos(wallRocket.heading); y: wallRocket.bob * Math.sin(wallRocket.heading) }
            }
            // Bewegte Szenen (Umlaufbahn, Nordlicht, Mondbasis): Ebenen aus ebenen.json, je nach Art bewegt.
            // grund liegt schon oben (wallGround); Sterne funkeln darüber, die Ebenen darüber.
            Repeater {
                model: wallAnim.scene ? wallAnim.d.layers : []
                delegate: Item {
                    id: lay
                    required property var modelData
                    required property int index
                    readonly property var L: modelData
                    readonly property real S: wallAnim.s
                    readonly property real t: 2 * Math.PI * (wallAnim.phase * (L.speed || 1) + (L.ph || 0))
                    readonly property bool sprite: L.kind === "orbit" || L.kind === "line"
                    // Umlaufbahn: Ort und Flugrichtung auf der gekippten Ellipse
                    readonly property real tilt: (L.tilt || 0) * Math.PI / 180
                    readonly property real ox: (L.rx || 0) * Math.cos(t)
                    readonly property real oy: (L.ry || 0) * Math.sin(t)
                    readonly property real behind: Math.sin(t) < 0 ? 1 : 0       // obere Hälfte = hinter der Erde
                    readonly property real px: L.kind === "orbit" ? (L.cx + ox * Math.cos(tilt) - oy * Math.sin(tilt))
                                             : L.kind === "line" ? (L.x0 + (L.x1 - L.x0) * ((wallAnim.phase * (L.speed || 1) + (L.ph || 0)) % 1)) : 0
                    readonly property real py: L.kind === "orbit" ? (L.cy + ox * Math.sin(tilt) + oy * Math.cos(tilt))
                                             : L.kind === "line" ? (L.y0 + (L.y1 - L.y0) * ((wallAnim.phase * (L.speed || 1) + (L.ph || 0)) % 1)) : 0
                    readonly property real heading: L.kind === "orbit"
                        ? Math.atan2(-(L.rx || 0) * Math.sin(t) * Math.sin(tilt) + (L.ry || 0) * Math.cos(t) * Math.cos(tilt),
                                     -(L.rx || 0) * Math.sin(t) * Math.cos(tilt) - (L.ry || 0) * Math.cos(t) * Math.sin(tilt)) * 180 / Math.PI
                        : (L.angle || 0)
                    z: L.kind === "occluder" ? 20 : (L.kind === "orbit" && behind > 0 ? 10 : 30 + index)
                    anchors.fill: parent
                    visible: L.kind !== "static" && (L.kind !== "occluder" || occ.behindNow)
                    QtObject {
                        id: occ
                        // Planet vor dem Raumschiff nur zeigen, wenn das Schiff gerade hinter der Erde ist
                        readonly property bool behindNow: Math.sin(lay.t) < 0
                    }
                    opacity: L.kind === "fade" ? 0.5 - 0.5 * Math.cos(t)
                           : L.kind === "sway" ? (L.min || 0.4) + ((L.max || 1) - (L.min || 0.4)) * (0.5 + 0.5 * Math.sin(t))
                           : L.kind === "blink" ? 0.35 + 0.65 * Math.max(0, Math.sin(t))
                           : L.kind === "orbit" ? (behind > 0 ? 0.85 : 1)
                           : 1
                    Image {
                        visible: !lay.sprite
                        anchors.fill: parent
                        source: wallAnim.scene && !lay.sprite && lay.L.kind !== "static" ? wallAnim.d.folder + lay.L.file : ""
                        sourceSize: Qt.size(width, height)
                        asynchronous: true
                        transform: Translate {
                            x: lay.L.kind === "sway" ? (lay.L.amp || 0) * lay.S * Math.sin(lay.t * 0.5)
                             : lay.L.kind === "bob" ? (lay.L.amp || 0) * lay.S * Math.sin(lay.t) * Math.cos(((lay.L.angle || 0) - 90) * Math.PI / 180) : 0
                            y: lay.L.kind === "bob" ? (lay.L.amp || 0) * lay.S * Math.sin(lay.t) * Math.sin(((lay.L.angle || 0) - 90) * Math.PI / 180) : 0
                        }
                    }
                    Image {
                        visible: lay.sprite
                        readonly property real k: (lay.L.scale || 1) * (lay.L.kind === "orbit" && lay.behind > 0 ? 0.82 : 1)
                        width: (lay.L.w || 100) * lay.S * k
                        height: (lay.L.h || 50) * lay.S * k
                        x: lay.px * lay.S - width / 2
                        y: lay.py * lay.S - height / 2
                        // nach links fliegend: spiegeln statt auf den Kopf drehen
                        readonly property bool left: Math.abs(lay.heading) > 90
                        mirror: left
                        rotation: left ? lay.heading - (lay.heading > 0 ? 180 : -180) : lay.heading
                        source: wallAnim.scene && lay.sprite ? wallAnim.d.folder + lay.L.file : ""
                        sourceSize: Qt.size((lay.L.w || 100) * 2, (lay.L.h || 50) * 2)
                        smooth: true
                        asynchronous: true
                    }
                }
            }
        }
    }

    // Klick auf den freien Desktop: Menüs schließen, Auswahl aufheben, Rechtsklick-Menü
    MouseArea {
        id: backgroundMouse
        property point origin
        property bool selecting: false
        anchors.fill: parent
        onPressed: (mouse) => {
            root.endFileDrag()
            if (mouse.button !== Qt.LeftButton) return
            marquee.width = 0
            marquee.height = 0
            origin = Qt.point(mouse.x, mouse.y)
        }
        onPositionChanged: (mouse) => {
            if (!(mouse.buttons & Qt.LeftButton)) return
            if (!selecting && Math.abs(mouse.x - origin.x) + Math.abs(mouse.y - origin.y) < 6) return
            if (!selecting) {
                root.takeKeyboard()
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
                    rows.push(icons.model.sourceRow(i))
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
            root.takeKeyboard()
            shell.closePopups()
            if (mouse.button === Qt.RightButton) {
                if (desktop.selectedCount > 0) itemMenu.openAt(mouse.x, mouse.y)
                else bgMenu.openAt(mouse.x, mouse.y)
            } else {
                desktop.clearSelection()
            }
        }
        // Doppelklick auf den freien Schreibtisch: alle Fenster minimieren (nochmal: zurückholen)
        onDoubleClicked: (mouse) => { if (mouse.button === Qt.LeftButton) tasks.showDesktop() }
    }

    // Ablegen auf dem Schreibtisch: eigene Symbole wandern auf diesen Monitor,
    // Dateien aus anderen Programmen (z. B. „Dateien“) landen im Ordner „Schreibtisch“.
    DropArea {
        id: desktopDrop
        anchors.fill: parent
        onEntered: (drag) => { drag.accepted = drag.formats.includes(root.iconDragFormat) || drag.hasUrls }
        onDropped: (drop) => {
            if (drop.formats.includes(root.iconDragFormat)) {
                const c = icons.cellAt(drop.x, drop.y)
                desktop.placeDragged(drop.getDataAsString(root.iconDragFormat), root.screenName, c[0], c[1])
                drop.accept(Qt.MoveAction)
                root.endFileDrag()
            } else if (drop.hasUrls) {
                desktop.dropUrls(drop.urls, "", root.dropMode(drop))
                drop.accept(Qt.CopyAction)   // wir erledigen das selbst – die Quelle löscht nichts
            }
        }
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
        id: feedRss
        source: rssWidget
        widgetKey: "rss"
        title: "RSS-Nachrichten"
        hint: "Eine Feed-Adresse pro Zeile"
        defaultY: 230
    }

    DesktopFeed {
        id: feedWeather
        source: weatherWidget
        widgetKey: "weather"
        title: "Wetter"
        hint: "Ort oder Postleitzahl"
        defaultY: 430
        isWeather: true
    }

    component DesktopFeed: Rectangle {
        id: widget
        required property var source
        required property string widgetKey
        required property string title
        required property string hint
        required property int defaultY
        property bool isWeather: false
        readonly property real maxX: Math.max(8, root.width - width - 8)
        readonly property real maxY: Math.max(root.minY, root.height - root.barSpace - height - 8)
        function homeX() {
            const pos = root.widgetPosition(widgetKey, source, "x")
            return pos < 0 ? maxX : 8 + pos * (maxX - 8)
        }
        function homeY() {
            const pos = root.widgetPosition(widgetKey, source, "y")
            return pos < 0 ? Math.max(root.minY, Math.min(defaultY, maxY)) : root.minY + pos * (maxY - root.minY)
        }
        function restorePosition() {
            x = Qt.binding(() => widget.homeX())
            y = Qt.binding(() => widget.homeY())
        }
        x: homeX()
        y: homeY()
        width: 320
        height: content.implicitHeight + 24
        visible: root.widgetOnScreen(widgetKey) && source.enabled
        radius: 22
        color: "transparent"
        GlassBackdrop { target: widget }

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
                drag.minimumY: root.minY
                drag.maximumX: widget.maxX
                drag.maximumY: widget.maxY
                onPositionChanged: (mouse) => { if (pressed) root.crossDragMove(widget.widgetKey, widget, handle, mouse) }
                onReleased: (mouse) => {
                    const moved = root.crossDragDrop(widget.widgetKey, widget, handle, mouse,
                                                     (x, y) => widget.source.setPos(x, y))
                    if (!moved && drag.active) root.saveWidgetPosition(widget.widgetKey, widget.source, widget)
                    widget.restorePosition()
                }
                onCanceled: { root.crossDragCancel(widget.widgetKey, widget); widget.restorePosition() }
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

    component ExtraWidget: Rectangle {
        id: extra
        required property string key
        required property real posX
        required property real posY
        required property real defaultX
        required property real defaultY
        required property Component body
        readonly property real maxX: Math.max(8, root.width - width - 8)
        readonly property real maxY: Math.max(root.minY, root.height - root.barSpace - height - 8)
        function homeX() {
            const pos = root.widgetPosition(key, extra, "x")
            return pos < 0 ? Math.min(defaultX, maxX) : 8 + pos * (maxX - 8)
        }
        function homeY() {
            const pos = root.widgetPosition(key, extra, "y")
            return pos < 0 ? Math.max(root.minY, Math.min(defaultY, maxY)) : root.minY + pos * (maxY - root.minY)
        }
        function setPos(x, y) {
            if (key === "ki") kiHelper.setPos(x, y)
            else if (key === "entwickler") devStats.setPos(x, y)
            else widgetExtras.setPosition(key, x, y)
        }
        function restorePosition() {
            x = Qt.binding(() => extra.homeX())
            y = Qt.binding(() => extra.homeY())
        }
        x: homeX()
        y: homeY()
        radius: 22
        color: "transparent"
        GlassBackdrop { target: extra }
        Loader {
            anchors.fill: parent
            anchors.leftMargin: 30
            anchors.rightMargin: 12
            anchors.topMargin: 10
            anchors.bottomMargin: 10
            active: extra.visible
            sourceComponent: extra.body
        }
        WidgetGrip {
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            highlighted: extraGrip.containsMouse || extraGrip.pressed
            MouseArea {
                id: extraGrip
                anchors.fill: parent
                anchors.margins: -7
                hoverEnabled: true
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                drag.target: extra
                drag.minimumX: 8
                drag.minimumY: root.minY
                drag.maximumX: extra.maxX
                drag.maximumY: extra.maxY
                onPositionChanged: (mouse) => { if (pressed) root.crossDragMove(extra.key, extra, extraGrip, mouse) }
                onReleased: (mouse) => {
                    const moved = root.crossDragDrop(extra.key, extra, extraGrip, mouse, (x, y) => extra.setPos(x, y))
                    if (!moved && drag.active)
                        root.saveWidgetPosition(extra.key, extra, extra)
                    extra.restorePosition()
                }
                onCanceled: { root.crossDragCancel(extra.key, extra); extra.restorePosition() }
            }
        }
    }

    ExtraWidget {
        id: extraClock
        key: "clock"
        visible: root.widgetOnScreen("clock") && widgetExtras.clockEnabled
        posX: widgetExtras.clockX
        posY: widgetExtras.clockY
        defaultX: Math.max(8, root.width - 570)
        defaultY: 24
        width: 190
        height: 168
        body: Canvas {
            id: face
            Accessible.name: "Analoge Uhr"
            Timer { interval: 1000; running: true; repeat: true; onTriggered: face.requestPaint() }
            onPaint: {
                const ctx = getContext("2d")
                const time = new Date()
                const r = Math.min(width, height) / 2 - 5
                ctx.reset()
                ctx.translate(width / 2, height / 2)
                ctx.beginPath()
                ctx.arc(0, 0, r, 0, Math.PI * 2)
                ctx.fillStyle = Theme.ground.toString()
                ctx.fill()
                ctx.strokeStyle = Theme.track.toString()
                ctx.lineWidth = 1
                ctx.stroke()
                function hand(turn, inner, outer, color, thickness) {
                    const angle = turn * Math.PI * 2 - Math.PI / 2
                    ctx.beginPath()
                    ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner)
                    ctx.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer)
                    ctx.strokeStyle = color
                    ctx.lineWidth = thickness
                    ctx.stroke()
                }
                for (let i = 0; i < 60; i++)
                    hand(i / 60, r - (i % 5 === 0 ? 9 : 5), r - 3,
                         i % 5 === 0 ? Theme.text.toString() : Theme.track.toString(), 1)
                hand((time.getHours() + time.getMinutes() / 60) / 12, 0, r * 0.48, Theme.text.toString(), 4)
                hand((time.getMinutes() + time.getSeconds() / 60) / 60, 0, r * 0.72, Theme.text.toString(), 3)
                hand(time.getSeconds() / 60, -8, r * 0.79, Theme.accent.toString(), 1.5)
                ctx.beginPath()
                ctx.arc(0, 0, 3, 0, 2 * Math.PI)
                ctx.fillStyle = Theme.accent.toString()
                ctx.fill()
            }
        }
    }

    ExtraWidget {
        id: extraTwitch
        key: "twitch"
        visible: root.widgetOnScreen("twitch") && widgetExtras.twitchEnabled
        posX: widgetExtras.twitchX
        posY: widgetExtras.twitchY
        defaultX: Math.max(8, root.width - 665)
        defaultY: 230
        width: 295
        height: 66 + 27 * widgetExtras.twitchRows.length
        body: Column {
            spacing: 4
            RowLayout {
                width: parent.width
                Text { Layout.fillWidth: true; text: "Twitch-Favoriten"; color: Theme.text; font.bold: true }
                IconButton {
                    icon: "refresh"; iconSize: 16; width: 28; height: 28
                    label: "Twitch-Status aktualisieren"
                    enabled: !widgetExtras.busy
                    onClicked: widgetExtras.refresh()
                }
            }
            Text {
                visible: widgetExtras.twitchRows.length === 0
                text: widgetExtras.busy ? "Status wird geprüft …" : "Kanäle in Widgets hinzufügen."
                color: Theme.textMuted
                width: parent.width
                elide: Text.ElideRight
            }
            Repeater {
                model: widgetExtras.twitchRows
                delegate: Item {
                    id: streamRow
                    required property var modelData
                    width: parent.width
                    height: 23
                    readonly property bool live: modelData.status === "live"
                    function openChannel() {
                        if (live) Qt.openUrlExternally("https://www.twitch.tv/" + modelData.name)
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.right: badge.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: streamRow.modelData.name
                        textFormat: Text.PlainText
                        color: streamRow.live ? Theme.accent : Theme.text
                        font.underline: streamRow.live
                        elide: Text.ElideRight
                    }
                    Text {
                        id: badge
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: streamRow.live ? "● LIVE" : streamRow.modelData.status === "offline" ? "Offline" : "Unbekannt"
                        color: streamRow.live ? Theme.ok : Theme.textMuted
                        font.pixelSize: 11
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: streamRow.live
                        cursorShape: Qt.PointingHandCursor
                        onClicked: streamRow.openChannel()
                    }
                    Accessible.role: Accessible.Link
                    Accessible.name: modelData.name + " – " + badge.text
                    Accessible.onPressAction: streamRow.openChannel()
                }
            }
        }
    }

    // Entwickler (nur für den Besitzer von Gibeon OS, „gibeon-entwickler an“): Besuche der GitHub-Seite,
    // wie oft das System und die AppImages geladen wurden, offene Fehlermeldungen von Nutzern
    ExtraWidget {
        id: extraDev
        key: "entwickler"
        visible: root.widgetOnScreen("entwickler") && devStats.enabled
        posX: devStats.posX
        posY: devStats.posY
        defaultX: Math.max(8, root.width - 1000)
        defaultY: 24
        width: 340
        height: 96 + 21 * devStats.rows.length + 22 * Math.max(1, Math.min(8, devStats.reports.length))
                + (devStats.regionsSetup ? 34 + 20 * Math.max(1, devStats.regions.length) : 0)
                + (devStats.message.length > 0 ? 34 : 0)
        body: Column {
            id: devBody
            spacing: 4
            RowLayout {
                width: parent.width
                Text { Layout.fillWidth: true; text: "Gibeon OS – Entwickler"; color: Theme.text; font.bold: true }
                IconButton {
                    icon: "refresh"; iconSize: 16; width: 28; height: 28
                    label: "Zahlen aktualisieren"
                    enabled: !devStats.busy
                    onClicked: devStats.refresh()
                }
            }
            Repeater {
                model: devStats.rows
                delegate: RowLayout {
                    required property var modelData
                    width: devBody.width
                    Text {
                        Layout.fillWidth: true
                        text: modelData.label
                        color: Theme.textMuted
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    Text { text: modelData.value; color: Theme.text; font.pixelSize: 13; font.bold: true }
                }
            }
            // Regionen: woher die Nutzer kommen (nur gemeldet mit Zustimmung, nur das Land)
            Item { width: 1; height: 6; visible: devStats.regionsSetup }
            RowLayout {
                visible: devStats.regionsSetup
                width: parent.width
                Text { Layout.fillWidth: true; text: "Regionen"; color: Theme.text; font.bold: true }
                Text { text: "Installiert · aktiv " + devStats.regionsMonth; color: Theme.textMuted; font.pixelSize: 11 }
            }
            Text {
                visible: devStats.regionsSetup && devStats.regions.length === 0
                text: devStats.busy ? "Wird geladen …" : "Noch keine Meldungen"
                color: Theme.textMuted
                font.pixelSize: 12
            }
            Repeater {
                model: devStats.regionsSetup ? devStats.regions : []
                delegate: RowLayout {
                    required property var modelData
                    width: devBody.width
                    Text {
                        Layout.fillWidth: true
                        text: modelData.land
                        color: Theme.textMuted
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    Text {
                        text: modelData.inst + " · " + modelData.aktiv
                        color: Theme.text
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
            }
            Item { width: 1; height: 6 }
            RowLayout {
                width: parent.width
                Text {
                    Layout.fillWidth: true
                    text: "Fehlermeldungen (" + devStats.reports.length + " offen)"
                    color: Theme.text
                    font.bold: true
                }
                Text {
                    text: "Alle ansehen"
                    color: Theme.accent
                    font.pixelSize: 12
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: devStats.openReports() }
                }
            }
            Text {
                visible: devStats.reports.length === 0
                text: devStats.busy ? "Wird geladen …" : "Keine offenen Meldungen"
                color: Theme.textMuted
                font.pixelSize: 12
            }
            Repeater {
                model: devStats.reports.slice(0, 8)
                delegate: Item {
                    required property var modelData
                    width: devBody.width
                    height: 22
                    Text {
                        anchors.left: parent.left
                        anchors.right: tag.left
                        anchors.rightMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        text: "#" + modelData.number + " " + modelData.title
                        textFormat: Text.PlainText
                        color: Theme.accent
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    Text {
                        id: tag
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.quelle
                        color: Theme.textMuted
                        font.pixelSize: 11
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Qt.openUrlExternally(parent.modelData.url)
                    }
                }
            }
            Text {
                visible: devStats.message.length > 0
                width: parent.width
                text: devStats.message
                textFormat: Text.PlainText
                color: Theme.textMuted
                font.pixelSize: 11
                wrapMode: Text.Wrap
            }
        }
    }

    // Akku (nur bei Laptops): großer Ring mit Prozent, Laden/Entladen und Restzeit
    ExtraWidget {
        id: extraAkku
        key: "akku"
        visible: root.widgetOnScreen("akku") && widgetExtras.akkuEnabled && akku.present
        posX: widgetExtras.akkuX
        posY: widgetExtras.akkuY
        defaultX: Math.max(8, root.width - 790)
        defaultY: 24
        width: 250
        height: 120
        body: RowLayout {
            spacing: 14
            Accessible.role: Accessible.StaticText
            Accessible.name: "Akku " + akku.percent + " Prozent, " + akku.statusText
            readonly property color levelColor: akku.low ? Theme.flame
                                                : (akku.charging || akku.full ? "#6fdcc0" : Theme.accent)
            Canvas {
                id: akkuRing
                Layout.preferredWidth: 92
                Layout.preferredHeight: 92
                property real level: akku.percent / 100
                property color fill: parent.levelColor
                onLevelChanged: requestPaint()
                onFillChanged: requestPaint()
                onPaint: {
                    const ctx = getContext("2d")
                    const r = Math.min(width, height) / 2 - 6
                    ctx.reset()
                    ctx.translate(width / 2, height / 2)
                    ctx.lineCap = "round"
                    ctx.lineWidth = 8
                    ctx.beginPath()
                    ctx.arc(0, 0, r, 0, Math.PI * 2)
                    ctx.strokeStyle = Theme.track.toString()
                    ctx.stroke()
                    if (level > 0) {
                        ctx.beginPath()
                        ctx.arc(0, 0, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * level)
                        ctx.strokeStyle = fill.toString()
                        ctx.stroke()
                    }
                }
                Text {
                    anchors.centerIn: parent
                    text: akku.percent + "%"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 22
                    font.bold: true
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                RowLayout {
                    spacing: 6
                    BatteryGlyph { level: akku.percent; charging: akku.charging; low: akku.low; Layout.preferredWidth: 26; Layout.preferredHeight: 13 }
                    Text {
                        text: "Akku"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                        font.bold: true
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: akku.statusText
                    color: akku.low ? Theme.flame : Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
            }
        }
    }

    // Notizen: direkt auf dem Schreibtisch tippen, wird von selbst gespeichert
    ExtraWidget {
        id: extraNotes
        key: "notes"
        visible: root.widgetOnScreen("notes") && widgetExtras.notesEnabled
        posX: widgetExtras.notesX
        posY: widgetExtras.notesY
        defaultX: Math.max(8, root.width - 990)
        defaultY: 24
        width: 300
        height: 280
        body: ColumnLayout {
            id: notesBody
            spacing: 6
            property string error: ""
            function store() {
                saveTimer.stop()
                notesBody.error = widgetExtras.saveNotes(notesArea.text)
            }
            Component.onDestruction: if (saveTimer.running) store()
            Timer { id: saveTimer; interval: 700; onTriggered: notesBody.store() }
            Connections {
                target: widgetExtras
                // anderswo geändert (zweiter Monitor, Neustart): nur übernehmen, wenn hier niemand tippt
                function onChanged() {
                    if (!notesArea.activeFocus && !saveTimer.running && notesArea.text !== widgetExtras.notesText)
                        notesArea.text = widgetExtras.notesText
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: "Notizen"; color: Theme.text; font.bold: true }
                Text {
                    text: notesBody.error ? notesBody.error
                        : saveTimer.running ? "Speichert …" : "Gespeichert"
                    color: notesBody.error ? Theme.flame : Theme.textMuted
                    font.pixelSize: 11
                    elide: Text.ElideLeft
                    Layout.maximumWidth: 170
                }
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea {
                    GibeonT.ContextMenu.menu: CTextMenu {}
                    id: notesArea
                    objectName: "notesArea"
                    text: widgetExtras.notesText
                    placeholderText: "Hier tippen – alles wird automatisch gespeichert."
                    placeholderTextColor: Theme.textMuted
                    color: Theme.text
                    selectionColor: Theme.accent
                    selectByMouse: true
                    persistentSelection: true
                    wrapMode: TextEdit.Wrap
                    font.pixelSize: 14
                    Accessible.name: "Notizen"
                    background: Rectangle {
                        color: Theme.ground
                        radius: 12
                        border.color: notesArea.activeFocus ? Theme.accent : Theme.hairline
                    }
                    onPressed: {
                        // Der Hintergrund bekommt die Tastatur nur auf Wunsch
                        if (root.Window.window && !root.Window.window.active) root.Window.window.requestActivate()
                        notesArea.forceActiveFocus()
                    }
                    onTextChanged: {
                        if (text.length > widgetExtras.notesMax) {
                            remove(widgetExtras.notesMax, text.length)
                            return
                        }
                        if (text !== widgetExtras.notesText) saveTimer.restart()
                    }
                    onActiveFocusChanged: if (!activeFocus && saveTimer.running) notesBody.store()
                    Keys.onEscapePressed: { notesBody.store(); root.takeKeyboard() }
                }
            }
        }
    }

    // KI-Helfer: lokales Open-Source-Sprachmodell – Fragen stellt man im eigenen Fenster
    KiChat { id: kiChat; ki: kiHelper }

    ExtraWidget {
        id: extraKi
        key: "ki"
        visible: root.widgetOnScreen("ki") && kiHelper.enabled
        posX: kiHelper.posX
        posY: kiHelper.posY
        defaultX: Math.max(8, root.width - 700)
        defaultY: 420
        width: 330
        height: 178
        body: KiCard { onOpen: kiChat.openChat() }
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
                    GibeonT.ContextMenu.menu: CTextMenu {}
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
        visible: root.widgetOnScreen("stats") && desktopStats.enabled && desktopStats.tiles.length > 0
        readonly property real maxX: Math.max(8, root.width - width - 8)
        readonly property real maxY: Math.max(root.minY, root.height - root.barSpace - height - 8)
        x: homeX()
        y: homeY()
        function homeX() {
            const pos = root.widgetPosition("stats", desktopStats, "x")
            return pos < 0 ? Math.max(8, maxX - 10) : 8 + pos * (maxX - 8)
        }
        function homeY() {
            const pos = root.widgetPosition("stats", desktopStats, "y")
            return pos < 0 ? Math.max(root.minY, Math.min(16, maxY)) : root.minY + pos * (maxY - root.minY)
        }
        function restoreBindings() {
            x = Qt.binding(() => statsBox.homeX())
            y = Qt.binding(() => statsBox.homeY())
        }
        width: stats.implicitWidth + 42
        height: stats.implicitHeight + 24
        radius: 22
        color: "transparent"
        GlassBackdrop { target: statsBox }

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
                drag.minimumY: root.minY
                drag.maximumY: statsBox.maxY
                onPositionChanged: (mouse) => { if (pressed) root.crossDragMove("stats", statsBox, statsMove, mouse) }
                onReleased: (mouse) => {
                    const moved = root.crossDragDrop("stats", statsBox, statsMove, mouse, (x, y) => desktopStats.setPos(x, y))
                    if (!moved && drag.active) root.saveWidgetPosition("stats", desktopStats, statsBox)
                    statsBox.restoreBindings()
                }
                onCanceled: { root.crossDragCancel("stats", statsBox); statsBox.restoreBindings() }
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
    // Feste Plätze im Raster (wie bei Windows): Ein Symbol liegt dort, wo man es hingezogen hat.
    // Neue Dateien (z. B. Downloads) suchen sich den ersten freien Platz – nie unter einem Widget.
    Item {
        id: icons
        x: 12
        y: root.topSpace + 12
        width: parent.width - 24
        height: parent.height - root.barSpace - root.topSpace - 24
        readonly property int cellWidth: 104
        readonly property int cellHeight: 108
        readonly property int cols: Math.max(1, Math.floor(width / cellWidth))
        readonly property int rows: Math.max(1, Math.floor(height / cellHeight))
        property var model: desktop.screenModel(root.screenName, shell.screenNames, shell.primaryScreen)
        readonly property int count: iconRepeater.count
        function itemAtIndex(i) { return iconRepeater.itemAt(i) }
        property var slots: ({})          // Pfad → [Spalte, Zeile]
        property var blocked: ({})        // "Spalte:Zeile" unter Widgets

        // Alle Widgets auf diesem Monitor – ändert sich eins (Lage, Größe, an/aus), neu anordnen
        readonly property var widgetItems: [feedRss, feedWeather, extraClock, extraNotes, extraTwitch, extraKi, statsBox, shelfBox]
        readonly property string widgetSig: widgetItems.map(w => w && w.visible
            ? [Math.round(w.x), Math.round(w.y), Math.round(w.width), Math.round(w.height)].join(",") : "-").join(";")
        onWidgetSigChanged: relayoutTimer.restart()
        onColsChanged: relayoutTimer.restart()
        onRowsChanged: relayoutTimer.restart()
        onCountChanged: relayoutTimer.restart()
        Connections {
            target: icons.model
            function onModelReset() { relayoutTimer.restart() }
            function onRowsInserted() { relayoutTimer.restart() }
            function onRowsRemoved() { relayoutTimer.restart() }
            function onLayoutChanged() { relayoutTimer.restart() }
        }
        Connections {
            target: desktop
            function onCellsChanged() { relayoutTimer.restart() }
        }
        Timer { id: relayoutTimer; interval: 60; onTriggered: icons.relayout() }
        Component.onCompleted: relayoutTimer.restart()

        // Zelle unter einem Punkt (Koordinaten von root)
        function cellAt(px, py) {
            return [Math.max(0, Math.min(cols - 1, Math.floor((px - x) / cellWidth))),
                    Math.max(0, Math.min(rows - 1, Math.floor((py - y) / cellHeight)))]
        }

        function relayout() {
            const taken = {}
            const key = (c, r) => c + ":" + r
            // Zellen unter Widgets sperren (mit etwas Abstand)
            for (const w of widgetItems) {
                if (!w || !w.visible) continue
                const left = w.x - x - 6, top = w.y - y - 6
                const right = left + w.width + 12, bottom = top + w.height + 12
                for (let c = 0; c < cols; ++c)
                    for (let r = 0; r < rows; ++r) {
                        const cx = c * cellWidth, cy = r * cellHeight
                        if (cx + cellWidth - 8 > left && cx + 8 < right && cy + cellHeight - 8 > top && cy + 8 < bottom)
                            taken[key(c, r)] = "widget"
                    }
            }
            const saved = (desktop.cells || {})[root.screenName] || {}
            const paths = []
            for (let i = 0; i < iconRepeater.count; ++i) {
                const it = iconRepeater.itemAt(i)
                if (it) paths.push(it.path)
            }
            const result = {}
            // 1. Symbole mit eigenem Platz (sofern frei)
            for (const p of paths) {
                const c = saved[p]
                if (c && c[0] < cols && c[1] < rows && !taken[key(c[0], c[1])]) {
                    result[p] = [c[0], c[1]]
                    taken[key(c[0], c[1])] = p
                }
            }
            // 2. Der Rest: erster freier Platz, von oben nach unten, dann nach rechts
            let col = 0, row = 0
            for (const p of paths) {
                if (result[p]) continue
                while (col < cols && taken[key(col, row)]) {
                    row += 1
                    if (row >= rows) { row = 0; col += 1 }
                }
                if (col >= cols) { result[p] = [cols - 1, rows - 1]; continue }   // Schreibtisch voll
                result[p] = [col, row]
                taken[key(col, row)] = p
            }
            slots = result
            const widgetCells = {}
            for (const k in taken) if (taken[k] === "widget") widgetCells[k] = true
            blocked = widgetCells
        }

        Repeater {
            id: iconRepeater
            model: icons.model
        delegate: Item {
            id: cell
            readonly property string path: model.path
            readonly property bool isDir: model.isDir
            readonly property var slot: icons.slots[model.path]
            property url dragImage: ""
            visible: !!slot
            x: slot ? slot[0] * icons.cellWidth : 0
            y: slot ? slot[1] * icons.cellHeight : 0
            Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            opacity: root.movePath === model.path ? 0.35 : 1
            width: icons.cellWidth
            height: icons.cellHeight

            Rectangle {
                anchors.fill: parent
                anchors.margins: 3
                radius: 10
                color: (folderDrop.containsDrag || (root.moveFolder !== "" && root.moveFolder === model.path)) ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.4)
                       : model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.28)
                                        : (m.containsMouse ? Theme.tint(0.1) : "transparent")
                border.color: (folderDrop.containsDrag || (root.moveFolder !== "" && root.moveFolder === model.path)) ? Theme.accent
                              : (model.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.7) : "transparent")
            }
            // Auf einen Ordner ziehen: hinein verschieben (Strg: kopieren)
            DropArea {
                id: folderDrop
                anchors.fill: parent
                enabled: model.isDir
                onEntered: (drag) => { drag.accepted = drag.hasUrls && root.dragPath !== model.path }
                onDropped: (drop) => {
                    desktop.dropUrls(drop.urls, model.path, root.dropMode(drop))
                    drop.accept(Qt.CopyAction)
                }
            }
            FileIcon {
                id: cellIcon
                y: 12
                anchors.horizontalCenter: parent.horizontalCenter
                size: 46
                isDir: model.isDir
                tint: model.tint
                ext: model.ext
                // Bild, das beim Ziehen am Mauszeiger hängt (das Betriebssystem zeichnet es)
                function prepareDragImage() {
                    if (cell.dragImage.toString() === "" && visible && width > 0)
                        grabToImage(r => cell.dragImage = r.url, Qt.size(46, 46))
                }
                Component.onCompleted: Qt.callLater(prepareDragImage)
            }
            Text {
                y: 64
                x: 6
                visible: root.renamePath !== model.path
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
                    if (!(mouse.buttons & Qt.LeftButton) || root.dragPath !== "")
                        return
                    const p = cell.mapToItem(root, mouse.x, mouse.y)
                    if (root.movePath === "") {
                        if (Math.abs(mouse.x - pressPos.x) + Math.abs(mouse.y - pressPos.y) <= 8)
                            return
                        // Verschieben auf dem Schreibtisch beginnt
                        root.pendingRow = -1
                        root.movePath = model.path
                        root.dragIsDir = model.isDir
                        root.dragTint = model.tint
                        root.dragExt = model.ext
                        tasks.refreshWindows()
                    }
                    if (root.movePath !== model.path)
                        return
                    const outside = p.x < 0 || p.y < 0 || p.x > root.width || p.y > root.height
                    // Über dem Schreibtisch eines anderen Monitors: dort im Raster ablegen
                    const cross = outside ? root.iconCrossTarget(p.x, p.y) : null
                    if (cross) {
                        root.crossIconMove(cross)
                        return
                    }
                    root.clearCrossIcon()
                    // Über einem Fenster: an das Programm übergeben
                    // (System-Ziehen, z. B. in Discord, Brave oder „Dateien“)
                    if (outside || tasks.windowAt(root.screenName, p.x, p.y)) {
                        root.cancelMove()
                        root.dragUris = desktop.dragUris(model.path)
                        root.dragPath = model.path
                        ghost.Drag.imageSource = cell.dragImage
                        ghost.Drag.startDrag()
                        root.endFileDrag()
                        return
                    }
                    root.updateMove(p.x, p.y)
                }
                onCanceled: root.cancelMove()
                onEntered: cellIcon.prepareDragImage()
                onPressed: (mouse) => {
                    pressPos = Qt.point(mouse.x, mouse.y)
                    root.endFileDrag()
                    root.takeKeyboard()
                    shell.closePopups()
                    if (mouse.button === Qt.RightButton) {
                        desktop.selectKeep(icons.model.sourceRow(index))
                        const p = cell.mapToItem(root, mouse.x, mouse.y)
                        itemMenu.openAt(p.x, p.y)
                    } else if (model.selected && !(mouse.modifiers & Qt.ControlModifier) && desktop.selectedCount > 1) {
                        root.pendingRow = icons.model.sourceRow(index)   // Auswahl zum Ziehen behalten
                    } else {
                        root.pendingRow = -1
                        desktop.select(icons.model.sourceRow(index), (mouse.modifiers & Qt.ControlModifier) !== 0)
                    }
                }
                onReleased: (mouse) => {
                    if (mouse.button === Qt.LeftButton && root.movePath === model.path) {
                        root.finishMove()
                        root.pendingRow = -1
                        return
                    }
                    if (mouse.button === Qt.LeftButton && root.pendingRow === icons.model.sourceRow(index) && root.dragPath === "")
                        desktop.select(root.pendingRow, false)
                    root.pendingRow = -1
                }
                onDoubleClicked: (mouse) => { if (mouse.button === Qt.LeftButton) desktop.open(icons.model.sourceRow(index)) }
            }
            // Namen bearbeiten – direkt unter dem Symbol
            TextField {
                GibeonT.ContextMenu.menu: CTextMenu {}
                id: renameField
                readonly property bool editing: root.renamePath === model.path
                visible: editing
                y: 60
                x: -8
                width: parent.width + 16
                height: 28
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 12
                horizontalAlignment: TextInput.AlignHCenter
                selectByMouse: true
                padding: 4
                background: Rectangle {
                    radius: 7
                    color: Theme.raised
                    border.width: 2
                    border.color: root.renameError ? "#e5707e" : Theme.accent
                }
                onEditingChanged: {
                    if (!editing) return
                    text = model.name
                    root.takeKeyboard()
                    forceActiveFocus()
                    // Wie bei Windows: Name ohne Dateiendung markieren
                    const dot = model.isDir ? -1 : text.lastIndexOf(".")
                    select(0, dot > 0 ? dot : text.length)
                }
                onTextEdited: root.renameError = ""
                Keys.onReturnPressed: root.commitRename(model.path, text)
                Keys.onEnterPressed: root.commitRename(model.path, text)
                Keys.onEscapePressed: root.cancelRename()
                onActiveFocusChanged: if (!activeFocus && editing) root.commitRename(model.path, text)
                Accessible.name: "Neuer Name"
            }
            Rectangle {
                visible: renameField.editing && root.renameError !== ""
                y: 92
                x: -20
                width: parent.width + 40
                height: errText.implicitHeight + 12
                radius: 8
                color: "#3a1f26"
                border.color: "#e5707e"
                z: 5
                Text {
                    id: errText
                    anchors.centerIn: parent
                    width: parent.width - 12
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.renameError
                    color: "#ffd9de"
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                }
            }
            Accessible.role: Accessible.ListItem
            Accessible.name: model.name
        }
        }
    }

    // Zielplatz beim Verschieben
    Rectangle {
        visible: root.movePath !== "" && root.moveCell !== null
        x: icons.x + (root.moveCell ? root.moveCell[0] : 0) * icons.cellWidth + 3
        y: icons.y + (root.moveCell ? root.moveCell[1] : 0) * icons.cellHeight + 3
        width: icons.cellWidth - 6
        height: icons.cellHeight - 6
        radius: 10
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
        border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.8)
        border.width: 2
        Behavior on x { NumberAnimation { duration: 90 } }
        Behavior on y { NumberAnimation { duration: 90 } }
    }

    // ---- Ablage oben mittig (wie das Dock bei macOS) ------------------------------------
    Rectangle {
        id: shelfBox
        visible: root.widgetOnScreen("shelf") && shelf.enabled
        readonly property bool dropHover: shelfDrop.containsDrag || root.moveShelf
        // frei verschiebbar (am Griff links oder an einer freien Stelle ziehen); Position bleibt gespeichert
        readonly property real maxX: Math.max(8, root.width - width - 8)
        readonly property real maxY: Math.max(root.minY, root.height - root.barSpace - height - 8)
        property bool moving: false
        function homeX() {
            const pos = root.widgetPosition("shelf", shelf, "x")
            return pos >= 0 ? 8 + pos * (maxX - 8) : Math.max(8, (root.width - width) / 2)
        }
        function homeY() {
            const pos = root.widgetPosition("shelf", shelf, "y")
            return pos >= 0 ? root.minY + pos * (maxY - root.minY) : root.topSpace + 12
        }
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
        color: "transparent"
        GlassBackdrop {
            target: shelfBox
            edge: shelfBox.dropHover ? Theme.accent : Theme.glassEdge
            edgeWidth: shelfBox.dropHover ? 2 : 1
        }
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
                shelfBox.y = Math.max(root.minY, Math.min(shelfBox.maxY, origin.y + p.y - start.y))
                root.crossDragMove("shelf", shelfBox, shelfMove, mouse)
            }
            onReleased: (mouse) => {
                if (!shelfBox.moving) return
                shelfBox.moving = false
                const moved = root.crossDragDrop("shelf", shelfBox, shelfMove, mouse, (x, y) => shelf.setPos(x, y))
                if (!moved && Math.abs(shelfBox.x - origin.x) + Math.abs(shelfBox.y - origin.y) > 3)
                    root.saveWidgetPosition("shelf", shelf, shelfBox)
                shelfBox.rebind()
            }
            onCanceled: {
                shelfBox.moving = false
                root.crossDragCancel("shelf", shelfBox)
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
                        color: sm.containsMouse ? Theme.tint(0.09) : "transparent"
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
                            source: slot.modelData.kind === "app" ? iconFiles.app(slot.modelData.icon) : ""
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
                if (drop.formats.includes(root.iconDragFormat)) {
                    shelf.addPath(drop.getDataAsString(root.iconDragFormat))
                    drop.acceptProposedAction()
                } else if (drop.hasUrls) {
                    shelf.addUrls(drop.urls)
                    drop.acceptProposedAction()
                }
            }
        }
    }

    // Was gerade gezogen wird
    Item {
        id: ghost
        Drag.mimeData: root.dragPath !== ""
            ? ({ [root.iconDragFormat]: root.dragPath, "text/uri-list": root.dragUris })
            : ({ [root.iconDragFormat]: root.dragPath })
        Drag.supportedActions: root.dragPath !== "" ? (Qt.MoveAction | Qt.CopyAction) : Qt.MoveAction
        Drag.proposedAction: Qt.MoveAction
        Drag.onDragFinished: root.endFileDrag()
        Drag.hotSpot.x: 23
        Drag.hotSpot.y: 23
        // Dateien zeigt das Betriebssystem am Mauszeiger – hier nur Einträge aus der Ablage
        visible: root.dragShelfKey !== "" || root.movePath !== ""
        z: 20
        width: 52; height: 52
        opacity: 0.85
        Image {
            visible: root.dragShelfItem !== null && root.dragShelfItem.kind === "app"
            anchors.centerIn: parent
            width: 38; height: 38
            sourceSize.width: 76; sourceSize.height: 76
            source: root.dragShelfItem && root.dragShelfItem.kind === "app" ? iconFiles.app(root.dragShelfItem.icon) : ""
        }
        FileIcon {
            visible: root.dragPath !== "" || root.movePath !== "" || (root.dragShelfItem !== null && root.dragShelfItem.kind !== "app")
            anchors.centerIn: parent
            size: 38
            isDir: (root.dragPath !== "" || root.movePath !== "") ? root.dragIsDir : (root.dragShelfItem ? root.dragShelfItem.kind === "dir" : false)
            tint: (root.dragPath !== "" || root.movePath !== "") ? root.dragTint : (root.dragShelfItem ? root.dragShelfItem.tint : "")
            ext: (root.dragPath !== "" || root.movePath !== "") ? root.dragExt : (root.dragShelfItem ? root.dragShelfItem.ext : "")
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
            if (act === "center") {
                if (root.onFallback("shelf")) root.setFallbackPosition("shelf", -1, -1)
                else shelf.resetPos()
            } else if (act === "hide") shelf.setEnabled(false)
        }
    }
    DesktopMenu {
        id: itemMenu
        entries: [
            { label: "Öffnen", icon: "open", act: "open" },
            { label: "In Dateien zeigen", icon: "files", act: "files" },
            { label: "Zur Ablage hinzufügen", icon: "plus", act: "shelf" },
            { sep: true },
            { label: "Kopieren", icon: "files", act: "copy" }
        ].concat(desktop.selectedCount === 1 ? [{ label: "Umbenennen  ·  F2", icon: "rename", act: "rename" }] : []).concat([
            { label: "Löschen (in den Papierkorb)  ·  Entf", icon: "trash", act: "trash" }
        ]).concat(desktop.canPaste ? [{ label: "Einfügen", icon: "plus", act: "paste" }] : [])
        onTriggered: (act) => {
            if (act === "shelf") desktop.selectedPaths().forEach(p => shelf.addPath(p))
            else if (act === "open") desktop.openSelected()
            else if (act === "files") desktop.openInFiles()
            else if (act === "trash") desktop.trashSelected()
            else if (act === "copy") desktop.copySelected()
            else if (act === "rename") root.startRename()
            else if (act === "paste") desktop.paste()
        }
    }
    DesktopMenu {
        id: bgMenu
        entries: (desktop.canPaste ? [{ label: "Einfügen", icon: "plus", act: "paste" }] : []).concat([
            { label: "Neuer Ordner", icon: "folder-plus", act: "new" },
            { label: "Schreibtisch in Dateien öffnen", icon: "files", act: "folder" },
            { sep: true },
            { label: "Taskmanager", icon: "taskmanager", act: "taskmanager" },
            { sep: true },
            { label: "Widgets öffnen", icon: "settings", act: "widgets" },
            { label: "Einstellungen", icon: "settings", act: "settings" }
        ])
        onTriggered: (act) => {
            if (act === "paste") desktop.paste()
            else if (act === "new") desktop.newFolder()
            else if (act === "folder") desktop.openFolder()
            else if (act === "settings") session.openSettings()
            else if (act === "widgets") shell.openWidgetManager()
            else if (act === "taskmanager") desktopStats.openTaskManager()
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
                        color: rm.containsMouse ? Theme.tint(0.08) : "transparent"
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
