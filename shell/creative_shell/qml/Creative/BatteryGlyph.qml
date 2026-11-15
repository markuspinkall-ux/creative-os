import QtQuick
import Creative

// Akku-Symbol im Creative-Stil: Rahmen mit Füllstand, Blitz beim Laden, rot wenn fast leer.
Item {
    id: glyph
    property int level: 0
    property bool charging: false
    property bool low: false
    implicitWidth: 24
    implicitHeight: 12
    Accessible.ignored: true

    Rectangle {
        id: body
        x: 0
        y: 0
        width: parent.width - 3
        height: parent.height
        radius: 3
        color: "transparent"
        border.width: 1.5
        border.color: glyph.low ? Theme.flame : Theme.text
        Rectangle {
            x: 2.5
            y: 2.5
            height: parent.height - 5
            width: Math.max(1.5, (parent.width - 5) * Math.max(0, Math.min(100, glyph.level)) / 100)
            radius: 1.5
            color: glyph.low ? Theme.flame : (glyph.charging ? "#6fdcc0" : Theme.text)
        }
    }
    Rectangle {
        x: body.width + 0.5
        width: 2.5
        height: parent.height * 0.45
        anchors.verticalCenter: parent.verticalCenter
        radius: 1
        color: glyph.low ? Theme.flame : Theme.text
    }
    // Blitz beim Laden
    Canvas {
        visible: glyph.charging
        anchors.centerIn: body
        width: body.height * 1.1
        height: body.height * 1.25
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.beginPath()
            ctx.moveTo(width * 0.6, 0)
            ctx.lineTo(width * 0.15, height * 0.58)
            ctx.lineTo(width * 0.48, height * 0.58)
            ctx.lineTo(width * 0.38, height)
            ctx.lineTo(width * 0.88, height * 0.4)
            ctx.lineTo(width * 0.54, height * 0.4)
            ctx.closePath()
            ctx.fillStyle = Theme.ground.toString()
            ctx.strokeStyle = Theme.text.toString()
            ctx.lineWidth = 1
            ctx.fill()
            ctx.stroke()
        }
    }
}
