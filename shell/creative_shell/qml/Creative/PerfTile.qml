import QtQuick
import Creative

// Leistungs-Kachel wie im Windows-Taskmanager: kleine Kurve links, Werte rechts.
// Wird im Taskmanager (Seitenleiste „Leistung“) und auf dem Schreibtisch benutzt.
Item {
    id: tile

    property string title
    property string value
    property string sub
    property var history: []
    property color color: Theme.accent
    property bool selected: false
    property bool plain: false          // Schreibtisch: ohne Hintergrund
    property int graphWidth: 78

    signal clicked()

    implicitWidth: 230
    implicitHeight: 64

    Rectangle {
        anchors.fill: parent
        visible: !tile.plain
        radius: 12
        color: tile.selected ? Theme.tint(0.08) : (hover.containsMouse ? Theme.tint(0.05) : "transparent")
        border.color: tile.selected ? Qt.rgba(tile.color.r, tile.color.g, tile.color.b, 0.45) : "transparent"
    }

    // Kurve
    Rectangle {
        id: box
        x: tile.plain ? 0 : 10
        anchors.verticalCenter: parent.verticalCenter
        width: tile.graphWidth
        height: tile.height - 16
        radius: 5
        color: tile.plain ? "transparent" : Qt.rgba(tile.color.r, tile.color.g, tile.color.b, 0.05)
        border.color: Qt.rgba(tile.color.r, tile.color.g, tile.color.b, tile.plain ? 0.55 : 0.7)
        border.width: 1

        Canvas {
            id: graph
            anchors.fill: parent
            anchors.margins: 1
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                const h = tile.history || []
                if (h.length < 2)
                    return
                const n = 60
                const w = width, ht = height
                const step = w / (n - 1)
                const start = n - h.length
                ctx.beginPath()
                ctx.moveTo(start * step, ht)
                for (let i = 0; i < h.length; i++) {
                    const v = Math.max(0, Math.min(100, h[i]))
                    ctx.lineTo((start + i) * step, ht - (v / 100) * (ht - 2) - 1)
                }
                ctx.lineTo(w, ht)
                ctx.closePath()
                ctx.fillStyle = Qt.rgba(tile.color.r, tile.color.g, tile.color.b, 0.22)
                ctx.fill()
                ctx.beginPath()
                for (let i = 0; i < h.length; i++) {
                    const v = Math.max(0, Math.min(100, h[i]))
                    const x = (start + i) * step, y = ht - (v / 100) * (ht - 2) - 1
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                }
                ctx.strokeStyle = tile.color
                ctx.lineWidth = 1.4
                ctx.stroke()
            }
        }
    }
    onHistoryChanged: graph.requestPaint()

    Column {
        anchors.left: box.right
        anchors.leftMargin: 12
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text {
            width: parent.width
            elide: Text.ElideRight
            text: tile.title
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.bold: true
            style: tile.plain ? Text.Raised : Text.Normal
            styleColor: Qt.rgba(0, 0, 0, 0.5)
        }
        Text {
            width: parent.width
            elide: Text.ElideRight
            text: tile.value
            color: tile.plain ? Theme.text : Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 12
            style: tile.plain ? Text.Raised : Text.Normal
            styleColor: Qt.rgba(0, 0, 0, 0.5)
        }
        Text {
            width: parent.width
            elide: Text.ElideRight
            visible: text.length > 0
            text: tile.sub
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 11
            style: tile.plain ? Text.Raised : Text.Normal
            styleColor: Qt.rgba(0, 0, 0, 0.5)
        }
    }

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tile.clicked()
    }
    Accessible.role: Accessible.Button
    Accessible.name: tile.title + " " + tile.value
}
