import QtCore
import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative Shots – wie das Snipping Tool von Windows 11, im Graphit-Look.
Window {
    id: win

    width: shots.hasImage ? Math.max(820, Math.min(1280, shots.imageWidth + 80)) : 680
    height: shots.hasImage ? Math.max(560, Math.min(860, shots.imageHeight + 180)) : 230
    minimumWidth: 640
    minimumHeight: 200
    visible: false
    title: shots.hasImage && shots.savedName ? shots.savedName + " – Creative Shots" : "Creative Shots"
    color: Theme.surface

    // ---- Zeichnen ----------------------------------------------------------------------------
    property string tool: ""              // "" | pen | marker | arrow | rect | eraser | crop
    property var strokes: []
    property var redoStack: []
    property var current: null
    property color penColor: "#ff5a5a"
    property real penWidth: 4
    property var cropRect: null
    readonly property string imgUrl: shots.imageUrl
    onImgUrlChanged: resetEditor()
    readonly property var penColors: ["#ff5a5a", "#ffb07a", "#f2d58a", "#6fdcc0", "#8fb3ff", "#d7a8ff", "#ffffff", "#12151b"]

    function resetEditor() {
        strokes = []
        redoStack = []
        current = null
        cropRect = null
        tool = ""
        paint.requestPaint()
    }
    function undo() {
        if (!strokes.length) return
        const s = strokes.slice(); const r = redoStack.slice()
        r.push(s.pop()); strokes = s; redoStack = r
        paint.requestPaint()
    }
    function redo() {
        if (!redoStack.length) return
        const s = strokes.slice(); const r = redoStack.slice()
        s.push(r.pop()); strokes = s; redoStack = r
        paint.requestPaint()
    }
    function eraseAt(x, y) {
        const rad = 12 / view.k
        const keep = strokes.filter(st => {
            const p = st.pts
            if (st.tool === "rect" || st.tool === "arrow") {
                const x1 = Math.min(p[0], p[p.length - 2]) - rad, x2 = Math.max(p[0], p[p.length - 2]) + rad
                const y1 = Math.min(p[1], p[p.length - 1]) - rad, y2 = Math.max(p[1], p[p.length - 1]) + rad
                return !(x >= x1 && x <= x2 && y >= y1 && y <= y2)
            }
            for (let i = 0; i < p.length; i += 2)
                if (Math.abs(p[i] - x) < rad + st.width && Math.abs(p[i + 1] - y) < rad + st.width)
                    return false
            return true
        })
        if (keep.length !== strokes.length) {
            redoStack = []
            strokes = keep
            paint.requestPaint()
        }
    }

    Connections {
        target: shots
        function onShowEditor() { win.show(); win.raise(); win.requestActivate() }
        function onHideEditor() { win.hide() }
    }

    // ---- Werkzeugleiste --------------------------------------------------------------------------
    Rectangle {
        id: toolbar
        anchors.left: parent.left
        anchors.right: parent.right
        height: 60
        color: Theme.footer

        Row {
            id: leftTools
            x: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            Rectangle {
                id: newBtn
                width: newRow.implicitWidth + 26
                height: 38
                radius: 12
                color: nm.pressed ? Qt.darker(Theme.accent, 1.15) : (nm.containsMouse ? Qt.lighter(Theme.accent, 1.06) : Theme.accent)
                Row {
                    id: newRow
                    anchors.centerIn: parent
                    spacing: 7
                    SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "plus-dark"; size: 15 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Neu"; color: Theme.accentText; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                }
                MouseArea { id: nm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: shots.newCapture() }
                Accessible.role: Accessible.Button
                Accessible.name: "Neues Bildschirmfoto"
            }

            // Modus
            Rectangle {
                width: modeRow.implicitWidth + 8
                height: 38
                radius: 12
                color: Theme.tint(0.05)
                Row {
                    id: modeRow
                    anchors.centerIn: parent
                    spacing: 2
                    Repeater {
                        model: [
                            { m: "rect", icon: "rect-tool", tip: "Rechteck" },
                            { m: "window", icon: "window-tool", tip: "Fenster" },
                            { m: "screen", icon: "screen-tool", tip: "Vollbild" },
                            { m: "free", icon: "freeform", tip: "Freihand" }
                        ]
                        delegate: IconButton {
                            required property var modelData
                            width: 32; height: 32
                            icon: modelData.icon
                            iconSize: 16
                            label: "Modus: " + modelData.tip
                            active: shots.mode === modelData.m
                            onClicked: shots.mode = modelData.m
                        }
                    }
                }
            }

            // Verzögerung
            Rectangle {
                id: delayBtn
                width: delayRow.implicitWidth + 22
                height: 38
                radius: 12
                color: dm.containsMouse ? Theme.hover : Theme.tint(0.05)
                Row {
                    id: delayRow
                    anchors.centerIn: parent
                    spacing: 6
                    SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "timer"; size: 15 }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: shots.delay ? shots.delay + " s" : "Sofort"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                    }
                    SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "chevron-down"; size: 10 }
                }
                MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: delayMenu.open() }
                Popup {
                    id: delayMenu
                    y: parent.height + 6
                    width: 190
                    padding: 6
                    background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
                    contentItem: Column {
                        spacing: 1
                        Repeater {
                            model: [{ d: 0, t: "Keine Verzögerung" }, { d: 3, t: "3 Sekunden" }, { d: 5, t: "5 Sekunden" }, { d: 10, t: "10 Sekunden" }]
                            delegate: Rectangle {
                                required property var modelData
                                width: 178; height: 34; radius: 8
                                color: om.containsMouse ? Theme.hover : "transparent"
                                Text { x: 12; anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: shots.delay === modelData.d }
                                MouseArea { id: om; anchors.fill: parent; hoverEnabled: true; onClicked: { shots.delay = modelData.d; delayMenu.close() } }
                            }
                        }
                    }
                }
            }
        }

        // Editor-Werkzeuge (nur mit Bild)
        Row {
            id: editTools
            visible: shots.hasImage
            anchors.left: leftTools.right
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            Rectangle { width: 1; height: 26; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }
            Item { width: 8; height: 1 }
            Repeater {
                model: [
                    { t: "pen", icon: "pen", tip: "Kugelschreiber" },
                    { t: "marker", icon: "highlighter", tip: "Textmarker" },
                    { t: "arrow", icon: "arrow-tool", tip: "Pfeil" },
                    { t: "rect", icon: "rect-tool", tip: "Rechteck" },
                    { t: "eraser", icon: "eraser", tip: "Radierer" },
                    { t: "crop", icon: "crop", tip: "Zuschneiden" }
                ]
                delegate: IconButton {
                    required property var modelData
                    width: 38; height: 38
                    icon: modelData.icon
                    iconSize: 18
                    label: modelData.tip
                    active: win.tool === modelData.t
                    onClicked: { win.tool = win.tool === modelData.t ? "" : modelData.t; win.cropRect = null }
                }
            }
            Item { width: 6; height: 1 }
            IconButton { width: 38; height: 38; icon: "undo"; iconSize: 17; label: "Rückgängig (Strg+Z)"; opacity: win.strokes.length ? 1 : 0.4; onClicked: win.undo() }
            IconButton { width: 38; height: 38; icon: "redo"; iconSize: 17; label: "Wiederholen (Strg+Y)"; opacity: win.redoStack.length ? 1 : 0.4; onClicked: win.redo() }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            visible: shots.hasImage
            IconButton { width: 38; height: 38; icon: "copy"; iconSize: 17; label: "Kopieren (Strg+C)"; onClicked: shots.copy(win.strokes) }
            IconButton { width: 38; height: 38; icon: "save"; iconSize: 17; label: "Speichern (Strg+S)"; onClicked: shots.save(win.strokes) }
            IconButton {
                id: moreBtn
                width: 38; height: 38; icon: "more"; iconSize: 17; label: "Mehr"
                onClicked: moreMenu.open()
                Popup {
                    id: moreMenu
                    y: parent.height + 6
                    x: parent.width - width
                    width: 250
                    padding: 6
                    background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
                    contentItem: Column {
                        spacing: 1
                        Repeater {
                            model: [
                                { t: "Speichern unter …", a: "saveas" },
                                { t: "Ordner öffnen", a: "folder" },
                                { t: "In Creative Pictures öffnen", a: "pictures" }
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                width: 238; height: 34; radius: 8
                                color: mm.containsMouse ? Theme.hover : "transparent"
                                Text { x: 12; anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                                MouseArea {
                                    id: mm
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        moreMenu.close()
                                        if (modelData.a === "saveas") saveDialog.open()
                                        else if (modelData.a === "folder") shots.openFolder()
                                        else { shots.save(win.strokes); shots.openInPictures() }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    // Farben und Strichstärke für Stift, Textmarker, Pfeil, Rechteck
    Rectangle {
        id: penBar
        anchors.top: toolbar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: visible ? 46 : 0
        visible: ["pen", "marker", "arrow", "rect"].indexOf(win.tool) >= 0
        color: Theme.footer
        Row {
            anchors.centerIn: parent
            spacing: 8
            Repeater {
                model: win.penColors
                delegate: Rectangle {
                    required property var modelData
                    width: 26; height: 26; radius: 13
                    anchors.verticalCenter: parent.verticalCenter
                    color: modelData
                    border.color: Qt.colorEqual(win.penColor, modelData) ? Theme.accent : Theme.tint(0.25)
                    border.width: Qt.colorEqual(win.penColor, modelData) ? 3 : 1
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: win.penColor = modelData }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Farbe " + modelData
                }
            }
            Item { width: 14; height: 1 }
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Stärke"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
            CSlider {
                anchors.verticalCenter: parent.verticalCenter
                width: 140
                from: 1; to: 16; stepSize: 1
                value: win.penWidth
                onMoved: win.penWidth = value
                Accessible.name: "Strichstärke"
            }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    // ---- Bildfläche --------------------------------------------------------------------------------
    Item {
        id: view
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: penBar.bottom
        anchors.bottom: parent.bottom
        readonly property real k: shots.hasImage ? Math.min(1, (width - 48) / shots.imageWidth, (height - 48) / shots.imageHeight) : 1

        // Leerer Zustand
        Column {
            anchors.centerIn: parent
            visible: !shots.hasImage
            spacing: 8
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Wähle oben einen Modus und klicke auf „Neu“."
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Oder jederzeit: Druck-Taste bzw. Win + Umschalt + S"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }

        Item {
            id: paper
            visible: shots.hasImage
            width: shots.imageWidth * view.k
            height: shots.imageHeight * view.k
            anchors.centerIn: parent

            // Schachbrett für durchsichtige Stellen (Freihand)
            Rectangle { anchors.fill: parent; color: "#2a2f3b" }
            Image {
                id: shot
                anchors.fill: parent
                source: shots.imageUrl
                smooth: true
                mipmap: true
                cache: false
            }
            Rectangle { anchors.fill: parent; color: "transparent"; border.color: Theme.hairline }

            Canvas {
                id: paint
                anchors.fill: parent
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    const k = view.k
                    const all = win.current ? win.strokes.concat([win.current]) : win.strokes
                    for (const s of all) {
                        const p = s.pts
                        if (p.length < 4) continue
                        ctx.save()
                        ctx.lineCap = s.tool === "marker" ? "butt" : "round"
                        ctx.lineJoin = "round"
                        ctx.strokeStyle = s.color
                        ctx.globalAlpha = s.tool === "marker" ? 0.38 : 1
                        ctx.lineWidth = (s.tool === "marker" ? s.width * 3.2 : s.width) * k
                        ctx.beginPath()
                        if (s.tool === "pen" || s.tool === "marker") {
                            ctx.moveTo(p[0] * k, p[1] * k)
                            for (let i = 2; i < p.length; i += 2) ctx.lineTo(p[i] * k, p[i + 1] * k)
                            ctx.stroke()
                        } else if (s.tool === "rect") {
                            const x1 = p[0] * k, y1 = p[1] * k, x2 = p[p.length - 2] * k, y2 = p[p.length - 1] * k
                            ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1))
                        } else if (s.tool === "arrow") {
                            const ax = p[0] * k, ay = p[1] * k, bx = p[p.length - 2] * k, by = p[p.length - 1] * k
                            ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke()
                            const ang = Math.atan2(by - ay, bx - ax)
                            const head = Math.max(12, s.width * 4) * k
                            ctx.beginPath()
                            ctx.moveTo(bx, by)
                            ctx.lineTo(bx - head * Math.cos(ang - 0.45), by - head * Math.sin(ang - 0.45))
                            ctx.lineTo(bx - head * Math.cos(ang + 0.45), by - head * Math.sin(ang + 0.45))
                            ctx.closePath()
                            ctx.fillStyle = s.color
                            ctx.fill()
                        }
                        ctx.restore()
                    }
                }
            }

            // Zuschneide-Rahmen
            Rectangle {
                visible: win.tool === "crop" && win.cropRect !== null
                x: win.cropRect ? win.cropRect.x * view.k : 0
                y: win.cropRect ? win.cropRect.y * view.k : 0
                width: win.cropRect ? win.cropRect.width * view.k : 0
                height: win.cropRect ? win.cropRect.height * view.k : 0
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.08)
                border.color: Theme.accent
                border.width: 2
            }

            MouseArea {
                anchors.fill: parent
                enabled: win.tool !== ""
                cursorShape: win.tool === "eraser" ? Qt.PointingHandCursor : Qt.CrossCursor
                property real ox: 0
                property real oy: 0
                onPressed: (m) => {
                    const x = m.x / view.k, y = m.y / view.k
                    if (win.tool === "eraser") { win.eraseAt(x, y); return }
                    if (win.tool === "crop") { ox = x; oy = y; win.cropRect = Qt.rect(x, y, 0, 0); return }
                    win.current = { tool: win.tool, color: win.penColor.toString(), width: win.penWidth, pts: [x, y] }
                }
                onPositionChanged: (m) => {
                    const x = Math.max(0, Math.min(shots.imageWidth, m.x / view.k))
                    const y = Math.max(0, Math.min(shots.imageHeight, m.y / view.k))
                    if (win.tool === "eraser") { win.eraseAt(x, y); return }
                    if (win.tool === "crop") { win.cropRect = Qt.rect(Math.min(ox, x), Math.min(oy, y), Math.abs(x - ox), Math.abs(y - oy)); return }
                    if (!win.current) return
                    const c = win.current
                    if (c.tool === "pen" || c.tool === "marker") c.pts.push(x, y)
                    else c.pts = [c.pts[0], c.pts[1], x, y]
                    win.current = c
                    paint.requestPaint()
                }
                onReleased: {
                    if (win.current && win.current.pts.length >= 4) {
                        const s = win.strokes.slice()
                        s.push(win.current)
                        win.strokes = s
                        win.redoStack = []
                    }
                    win.current = null
                    paint.requestPaint()
                }
            }
        }

        // Zuschneiden übernehmen
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 16
            spacing: 8
            visible: win.tool === "crop"
            Rectangle {
                width: hint.implicitWidth + 24; height: 36; radius: 12
                color: Theme.raised
                visible: !win.cropRect || win.cropRect.width < 3
                Text { id: hint; anchors.centerIn: parent; text: "Ziehe den Bereich auf, der übrig bleiben soll"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12 }
            }
            CButton {
                visible: win.cropRect !== null && win.cropRect.width >= 3
                text: "Abbrechen"
                onClicked: { win.cropRect = null; win.tool = "" }
            }
            CButton {
                visible: win.cropRect !== null && win.cropRect.width >= 3
                text: "Zuschneiden"
                primary: true
                onClicked: {
                    const r = win.cropRect
                    shots.crop(win.strokes, r.x, r.y, r.width, r.height)
                }
            }
        }
    }

    // ---- Hinweis -----------------------------------------------------------------------------------------
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.tool === "crop" ? 64 : 16
        visible: shots.message.length > 0
        width: Math.min(parent.width - 40, msg.implicitWidth + 32)
        height: 36
        radius: 18
        color: Theme.raised
        border.color: Theme.hairline
        Text { id: msg; anchors.centerIn: parent; width: parent.width - 24; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: shots.message; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12 }
    }

    FilePicker {
        id: saveDialog
        mode: "save"
        title: "Bildschirmfoto speichern unter"
        nameFilters: ["*.png", "*.jpg", "*.jpeg"]
        defaultSuffix: "png"
        fileName: shots.savedName || ("Bildschirmfoto " + Qt.formatDateTime(new Date(), "yyyy-MM-dd HH.mm") + ".png")
        startFolder: StandardPaths.writableLocation(StandardPaths.PicturesLocation)
        onAccepted: (url) => shots.saveAs(win.strokes, url.toString())
    }

    Shortcut { sequence: "Ctrl+N"; onActivated: shots.newCapture() }
    Shortcut { sequence: StandardKey.Undo; onActivated: win.undo() }
    Shortcut { sequence: "Ctrl+Y"; onActivated: win.redo() }
    Shortcut { sequence: StandardKey.Copy; enabled: shots.hasImage; onActivated: shots.copy(win.strokes) }
    Shortcut { sequence: StandardKey.Save; enabled: shots.hasImage; onActivated: shots.save(win.strokes) }
    Shortcut { sequence: "Ctrl+Shift+S"; enabled: shots.hasImage; onActivated: saveDialog.open() }
    Shortcut { sequence: "Esc"; onActivated: { win.tool = ""; win.cropRect = null } }

    // Eine Auswahl-Ebene je Monitor
    Instantiator {
        model: shots.overlay ? Qt.application.screens : []
        delegate: SnipOverlay { info: modelData }
    }
}
