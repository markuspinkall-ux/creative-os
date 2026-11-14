import QtQuick
import Creative

// Name des Programms über dem Taskleisten-Symbol, auf dem die Maus liegt.
// Die Fläche ist so breit wie der Bildschirm und lässt alle Klicks durch.
Item {
    id: root
    property string screenName
    readonly property var tip: shell.taskTip
    readonly property bool mine: tip.screen === root.screenName

    Rectangle {
        id: card
        visible: root.mine && !!root.tip.text
        width: Math.min(360, row.implicitWidth + 28)
        height: 34
        radius: 11
        x: Math.max(8, Math.min(root.width - width - 8, (root.tip.x || 0) - width / 2))
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        color: Theme.raised
        border.color: Theme.hairline
        Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

        // kleiner Zeiger zum Symbol
        Rectangle {
            width: 10; height: 10
            rotation: 45
            color: Theme.raised
            border.color: Theme.hairline
            x: Math.max(10, Math.min(card.width - 20, (root.tip.x || 0) - card.x - 5))
            y: card.height - 6
            z: -1
        }
        Rectangle {   // deckt die obere Hälfte des Zeigers ab, damit die Kante sauber ist
            x: 1; y: card.height - 12
            width: card.width - 2; height: 11
            radius: 10
            color: Theme.raised
        }

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.tip.text || ""
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.bold: true
                elide: Text.ElideRight
                width: Math.min(implicitWidth, 300)
            }
            Rectangle {
                visible: (root.tip.count || 0) > 1
                anchors.verticalCenter: parent.verticalCenter
                width: countText.implicitWidth + 12; height: 20; radius: 10
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                Text {
                    id: countText
                    anchors.centerIn: parent
                    text: (root.tip.count || 0) + " Fenster"
                    color: Theme.accent
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }
}
