import QtQuick
import QtQuick.Window
import Creative

// Auswahl-Ebene auf einem Monitor: der Bildschirm ist „eingefroren“ und abgedunkelt,
// oben in der Mitte die Leiste mit Rechteck / Fenster / Vollbild / Freihand.
Window {
    id: ov

    property var info                       // Eintrag aus Qt.application.screens
    readonly property real k: shots.scale
    readonly property real gx: info ? info.virtualX : 0
    readonly property real gy: info ? info.virtualY : 0
    property int hoverWindow: -1
    property var freePts: []
    property bool dragging: false
    property real sx: 0
    property real sy: 0
    property real ex: 0
    property real ey: 0
    readonly property real selX: Math.min(sx, ex)
    readonly property real selY: Math.min(sy, ey)
    readonly property real selW: Math.abs(ex - sx)
    readonly property real selH: Math.abs(ey - sy)

    screen: info
    x: gx
    y: gy
    width: info ? info.width : 800
    height: info ? info.height : 600
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    visibility: Window.FullScreen
    color: "black"
    title: "Creative Shots – Auswahl"

    function windowAt(lx, ly) {
        const px = lx + gx, py = ly + gy
        const ws = shots.windows
        for (let i = 0; i < ws.length; i++) {
            const w = ws[i]
            if (px >= w.x && px < w.x + w.w && py >= w.y && py < w.y + w.h)
                return i
        }
        return -1
    }

    // Eingefrorenes Bild dieses Monitors
    Image {
        id: frozen
        anchors.fill: parent
        source: shots.fullUrl
        sourceClipRect: Qt.rect((ov.gx - shots.unionX) * ov.k, (ov.gy - shots.unionY) * ov.k, ov.width * ov.k, ov.height * ov.k)
        smooth: true
        cache: false
    }

    // Abdunkeln
    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.42) }

    // Ausgewählter Bereich hell (Rechteck oder Fenster)
    Item {
        id: lit
        readonly property var r: {
            if (shots.mode === "rect" && ov.dragging)
                return Qt.rect(ov.selX, ov.selY, ov.selW, ov.selH)
            if (shots.mode === "window" && ov.hoverWindow >= 0) {
                const w = shots.windows[ov.hoverWindow]
                return Qt.rect(w.x - ov.gx, w.y - ov.gy, w.w, w.h)
            }
            return Qt.rect(0, 0, 0, 0)
        }
        x: r.x; y: r.y; width: r.width; height: r.height
        visible: width > 0 && height > 0
        clip: true
        Image {
            x: -lit.x
            y: -lit.y
            width: ov.width
            height: ov.height
            source: shots.fullUrl
            sourceClipRect: frozen.sourceClipRect
            smooth: true
            cache: false
        }
        Rectangle { anchors.fill: parent; color: "transparent"; border.color: Theme.accent; border.width: 2 }
    }

    // Größe anzeigen
    Rectangle {
        visible: shots.mode === "rect" && ov.dragging && ov.selW > 0
        x: Math.min(ov.selX, ov.width - width - 6)
        y: ov.selY + ov.selH + 8 > ov.height - 30 ? ov.selY - 30 : ov.selY + ov.selH + 8
        width: sizeText.implicitWidth + 16
        height: 24
        radius: 8
        color: Theme.raised
        Text {
            id: sizeText
            anchors.centerIn: parent
            text: Math.round(ov.selW * ov.k) + " × " + Math.round(ov.selH * ov.k)
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 11
        }
    }

    // Freihand-Linie
    Canvas {
        id: freeCanvas
        anchors.fill: parent
        visible: shots.mode === "free"
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const p = ov.freePts
            if (p.length < 4)
                return
            ctx.beginPath()
            ctx.moveTo(p[0] - ov.gx, p[1] - ov.gy)
            for (let i = 2; i < p.length; i += 2)
                ctx.lineTo(p[i] - ov.gx, p[i + 1] - ov.gy)
            ctx.strokeStyle = "white"
            ctx.lineWidth = 2
            ctx.stroke()
        }
    }

    // Vollbild: ganzer Monitor leicht hervorgehoben
    Rectangle {
        anchors.fill: parent
        visible: shots.mode === "screen" && screenHover.hovered
        color: "transparent"
        border.color: Theme.accent
        border.width: 3
    }
    HoverHandler { id: screenHover }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: shots.mode === "window" || shots.mode === "screen" ? Qt.PointingHandCursor : Qt.CrossCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: (m) => {
            if (m.button === Qt.RightButton) { shots.cancel(); return }
            if (shots.mode === "rect") {
                ov.sx = ov.ex = m.x
                ov.sy = ov.ey = m.y
                ov.dragging = true
            } else if (shots.mode === "free") {
                ov.freePts = [m.x + ov.gx, m.y + ov.gy]
                ov.dragging = true
            }
        }
        onPositionChanged: (m) => {
            if (shots.mode === "rect" && ov.dragging) {
                ov.ex = Math.max(0, Math.min(ov.width, m.x))
                ov.ey = Math.max(0, Math.min(ov.height, m.y))
            } else if (shots.mode === "free" && ov.dragging) {
                const p = ov.freePts
                p.push(m.x + ov.gx, m.y + ov.gy)
                ov.freePts = p
                freeCanvas.requestPaint()
            } else if (shots.mode === "window") {
                ov.hoverWindow = ov.windowAt(m.x, m.y)
            }
        }
        onReleased: (m) => {
            if (m.button !== Qt.LeftButton)
                return
            if (shots.mode === "rect" && ov.dragging) {
                ov.dragging = false
                if (ov.selW > 4 && ov.selH > 4)
                    shots.selectRect(ov.selX + ov.gx, ov.selY + ov.gy, ov.selW, ov.selH)
            } else if (shots.mode === "free" && ov.dragging) {
                ov.dragging = false
                shots.selectFree(ov.freePts)
                ov.freePts = []
                freeCanvas.requestPaint()
            }
        }
        onClicked: (m) => {
            if (m.button !== Qt.LeftButton)
                return
            if (shots.mode === "window") {
                const i = ov.windowAt(m.x, m.y)
                if (i >= 0) shots.selectWindow(i)
                else shots.selectScreen(ov.gx, ov.gy, ov.width, ov.height)
            } else if (shots.mode === "screen") {
                shots.selectScreen(ov.gx, ov.gy, ov.width, ov.height)
            }
        }
    }

    // ---- Leiste oben in der Mitte ------------------------------------------------------------
    Rectangle {
        id: bar
        anchors.horizontalCenter: parent.horizontalCenter
        y: 22
        width: barRow.implicitWidth + 16
        height: 52
        radius: 16
        color: Theme.raised
        border.color: Theme.hairline
        MouseArea { anchors.fill: parent }       // Klicks nicht an die Auswahl weitergeben
        Row {
            id: barRow
            anchors.centerIn: parent
            spacing: 4
            Repeater {
                model: [
                    { m: "rect", icon: "rect-tool", tip: "Rechteck" },
                    { m: "window", icon: "window-tool", tip: "Fenster" },
                    { m: "screen", icon: "screen-tool", tip: "Vollbild" },
                    { m: "free", icon: "freeform", tip: "Freihand" }
                ]
                delegate: IconButton {
                    required property var modelData
                    width: 40; height: 40
                    icon: modelData.icon
                    iconSize: 19
                    label: modelData.tip
                    active: shots.mode === modelData.m
                    onClicked: shots.mode = modelData.m
                }
            }
            Rectangle { width: 1; height: 26; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }
            IconButton { width: 40; height: 40; icon: "close"; iconSize: 15; label: "Abbrechen (Esc)"; onClicked: shots.cancel() }
        }
    }
    // Kurzer Hinweis unter der Leiste
    Text {
        anchors.horizontalCenter: bar.horizontalCenter
        anchors.top: bar.bottom
        anchors.topMargin: 10
        visible: !ov.dragging
        text: ({ rect: "Ziehe einen Bereich auf", window: "Klicke auf ein Fenster", screen: "Klicke, um den ganzen Bildschirm aufzunehmen", free: "Zeichne die Form mit gedrückter Maustaste" })[shots.mode]
        color: "white"
        style: Text.Outline
        styleColor: Qt.rgba(0, 0, 0, 0.6)
        font.family: Theme.fontFamily
        font.pixelSize: 13
    }

    Shortcut { sequence: "Esc"; onActivated: shots.cancel() }
    Shortcut { sequence: "1"; onActivated: shots.mode = "rect" }
    Shortcut { sequence: "2"; onActivated: shots.mode = "window" }
    Shortcut { sequence: "3"; onActivated: shots.mode = "screen" }
    Shortcut { sequence: "4"; onActivated: shots.mode = "free" }

    Component.onCompleted: { showFullScreen(); requestActivate() }
}
