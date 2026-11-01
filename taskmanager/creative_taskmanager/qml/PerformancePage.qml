import QtQuick
import QtQuick.Controls.Basic
import Creative

// Leistung: links die Kacheln (wie auf dem Schreibtisch), rechts die große Kurve mit Details.
Item {
    id: root
    readonly property var d: tm.perfDetail

    // ---- Kacheln ------------------------------------------------------------------------------
    ListView {
        id: tiles
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 14
        width: 250
        clip: true
        spacing: 4
        model: tm.tiles
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.2) } }
        delegate: PerfTile {
            required property var modelData
            width: ListView.view.width
            height: 66
            title: modelData.title
            value: modelData.value
            sub: modelData.sub
            history: modelData.history
            color: modelData.color
            selected: tm.selectedPerf === modelData.key
            onClicked: tm.selectPerf(modelData.key)
        }
    }

    Rectangle { anchors.left: tiles.right; anchors.leftMargin: 8; width: 1; height: parent.height; color: Theme.hairline }

    // ---- Detail ---------------------------------------------------------------------------------
    Flickable {
        id: detail
        anchors.left: tiles.right
        anchors.leftMargin: 26
        anchors.right: parent.right
        anchors.rightMargin: 26
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        contentHeight: col.implicitHeight + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: col
            width: detail.width
            y: 18
            spacing: 14

            Item {
                width: parent.width
                height: 36
                Text {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    text: root.d.title || ""
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 26
                    font.bold: true
                }
                Text {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 4
                    width: parent.width * 0.55
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideLeft
                    text: root.d.subtitle || ""
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                }
            }

            Item {
                width: parent.width
                height: 16
                Text { text: root.d.unit || ""; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                Text { anchors.right: parent.right; text: "100 %"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
            }

            // Große Kurve mit Raster
            Rectangle {
                id: graphBox
                width: parent.width
                height: Math.max(200, Math.min(340, root.height * 0.42))
                color: Qt.rgba(1, 1, 1, 0.015)
                property color c: root.d.color || Theme.accent
                border.color: Qt.rgba(c.r, c.g, c.b, 0.65)
                border.width: 1
                Canvas {
                    id: big
                    anchors.fill: parent
                    anchors.margins: 1
                    property var hist: root.d.history || []
                    property color c: root.d.color || Theme.accent
                    onHistChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.reset()
                        const w = width, h = height
                        ctx.strokeStyle = Qt.rgba(c.r, c.g, c.b, 0.12)
                        ctx.lineWidth = 1
                        for (let i = 1; i < 10; i++) {
                            const y = Math.round(h * i / 10) + 0.5
                            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
                        }
                        for (let i = 1; i < 20; i++) {
                            const x = Math.round(w * i / 20) + 0.5
                            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
                        }
                        const n = 60, step = w / (n - 1)
                        const start = n - hist.length
                        if (hist.length < 2)
                            return
                        ctx.beginPath()
                        ctx.moveTo(start * step, h)
                        for (let i = 0; i < hist.length; i++) {
                            const v = Math.max(0, Math.min(100, hist[i]))
                            ctx.lineTo((start + i) * step, h - v / 100 * (h - 2) - 1)
                        }
                        ctx.lineTo(w, h)
                        ctx.closePath()
                        ctx.fillStyle = Qt.rgba(c.r, c.g, c.b, 0.18)
                        ctx.fill()
                        ctx.beginPath()
                        for (let i = 0; i < hist.length; i++) {
                            const v = Math.max(0, Math.min(100, hist[i]))
                            const x = (start + i) * step, y = h - v / 100 * (h - 2) - 1
                            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                        }
                        ctx.strokeStyle = c
                        ctx.lineWidth = 1.6
                        ctx.stroke()
                    }
                }
            }
            Item {
                width: parent.width
                height: 14
                Text { text: "60 Sekunden"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                Text { anchors.right: parent.right; text: "0"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
            }

            // Einzelne Prozessorkerne
            Flow {
                width: parent.width
                spacing: 4
                visible: (root.d.cores || []).length > 1
                Repeater {
                    model: root.d.cores || []
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: 46
                        height: 34
                        radius: 6
                        color: Qt.rgba(1, 1, 1, 0.03)
                        border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.3)
                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 1
                            radius: 5
                            height: Math.max(0, (parent.height - 2) * Math.min(100, modelData) / 100)
                            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.35)
                            Behavior on height { NumberAnimation { duration: 200 } }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(modelData) + " %"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 10
                        }
                    }
                }
            }

            // Werte: links groß, rechts als Liste
            Item {
                width: parent.width
                height: Math.max(bigStats.height, extraList.height)
                Flow {
                    id: bigStats
                    width: parent.width * 0.58
                    spacing: 22
                    Repeater {
                        model: root.d.stats || []
                        delegate: Column {
                            required property var modelData
                            spacing: 2
                            Text { text: modelData.label; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                            Text { text: modelData.value; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20 }
                        }
                    }
                }
                Column {
                    id: extraList
                    anchors.right: parent.right
                    width: parent.width * 0.38
                    spacing: 6
                    Repeater {
                        model: root.d.extra || []
                        delegate: Item {
                            required property var modelData
                            width: extraList.width
                            height: 18
                            Text { text: modelData.label + ":"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                            Text {
                                anchors.right: parent.right
                                width: parent.width * 0.55
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideLeft
                                text: modelData.value
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }
        }
    }
}
