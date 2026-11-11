import QtQuick
import QtQuick.Controls.Basic
import Creative

// Schieberegler (z. B. Helligkeit).
Slider {
    id: control

    from: 0
    to: 100
    stepSize: 1
    implicitHeight: 28

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 6
        radius: 3
        color: Theme.tint(0.12)

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: 3
            color: Theme.accent
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: 18
        height: 18
        radius: 9
        color: control.pressed ? Theme.text : "white"
    }
}
