import QtQuick
import Creative

// Rechtsklick auf ein Programm in der Taskleiste: Neues Fenster, Schließen.
// Die Fläche ist so breit wie der Bildschirm; die Karte sitzt über dem angeklickten Symbol.
Item {
    id: root
    property string screenName
    readonly property var item: shell.taskMenu
    readonly property bool running: !!item.running
    readonly property int count: item.count || 0

    function opened() { root.forceActiveFocus() }
    focus: true
    Keys.onEscapePressed: shell.closePopups()

    readonly property var entries: {
        const list = []
        if (!root.running && root.item.desktopId)
            list.push({ act: "open", label: "Öffnen", icon: "open" })
        if (root.running && root.item.desktopId)
            list.push({ act: "new", label: "Neues Fenster", icon: "plus" })
        if (root.running)
            list.push({ act: "close", label: root.count > 1 ? "Alle " + root.count + " Fenster schließen" : "Fenster schließen",
                        icon: "close", danger: true })
        return list
    }

    function run(act) {
        shell.closePopups()
        if (act === "open" || act === "new") tasks.launchNew(root.item.desktopId)
        else if (act === "close") tasks.closeApp(root.screenName, root.item.key)
    }

    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }

    Rectangle {
        id: card
        width: 250
        height: col.implicitHeight + 16
        x: Math.max(8, Math.min(root.width - width - 8, (root.item.x || 0) - width / 2))
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        radius: 14
        color: Theme.raised
        border.color: Theme.hairline
        MouseArea { anchors.fill: parent }

        Column {
            id: col
            x: 8; y: 8
            width: parent.width - 16
            spacing: 1
            Text {
                leftPadding: 10
                topPadding: 6
                bottomPadding: 6
                width: parent.width
                elide: Text.ElideRight
                text: root.item.name || ""
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.bold: true
            }
            Repeater {
                model: root.entries
                delegate: Rectangle {
                    required property var modelData
                    width: col.width
                    height: 36
                    radius: 9
                    color: em.containsMouse ? (modelData.danger ? Qt.rgba(0.9, 0.28, 0.3, 0.16) : Theme.hover) : "transparent"
                    SvgIcon {
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        name: modelData.icon
                        size: 15
                    }
                    Text {
                        x: 38
                        width: parent.width - 48
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        text: modelData.label
                        color: modelData.danger && em.containsMouse ? "#ff8a8e" : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                    MouseArea {
                        id: em
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.run(modelData.act)
                    }
                    Accessible.role: Accessible.MenuItem
                    Accessible.name: modelData.label
                }
            }
        }
    }
}
