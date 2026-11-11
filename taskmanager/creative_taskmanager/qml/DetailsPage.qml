import QtQuick
import QtQuick.Controls.Basic
import Creative

// Details: alle Prozesse einzeln mit PID, Status, Benutzer, CPU, Speicher, Befehlszeile.
Item {
    id: root
    property var host

    readonly property var cols: [
        { key: "name", label: "Name", w: 190, right: false },
        { key: "pid", label: "PID", w: 74, right: true },
        { key: "status", label: "Status", w: 150, right: false },
        { key: "user", label: "Benutzer", w: 110, right: false },
        { key: "cpu", label: "CPU", w: 80, right: true },
        { key: "mem", label: "Arbeitsspeicher", w: 124, right: true },
        { key: "command", label: "Befehlszeile", w: -1, right: false }
    ]
    function colWidth(c, total) {
        if (c.w >= 0)
            return c.w
        let used = 0
        for (const x of cols) if (x.w >= 0) used += x.w
        return Math.max(120, total - used)
    }

    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 18
        anchors.rightMargin: 22
        height: 40
        Row {
            anchors.fill: parent
            Repeater {
                model: root.cols
                delegate: Item {
                    required property var modelData
                    readonly property bool sorted: tm.detailSort === modelData.key
                    width: root.colWidth(modelData, header.width)
                    height: header.height
                    Rectangle { anchors.fill: parent; anchors.margins: 3; radius: 8; color: hm.containsMouse && modelData.key !== "command" ? Theme.hover : "transparent" }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: modelData.right ? parent.right : undefined
                        anchors.left: modelData.right ? undefined : parent.left
                        anchors.rightMargin: 12
                        anchors.leftMargin: 12
                        text: modelData.label + (parent.sorted ? (tm.detailDesc ? "  ↓" : "  ↑") : "")
                        color: parent.sorted ? Theme.accent : Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                    }
                    MouseArea { id: hm; anchors.fill: parent; hoverEnabled: true; enabled: modelData.key !== "command"; onClicked: tm.sortDetails(modelData.key) }
                }
            }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    ListView {
        id: list
        anchors.left: header.left
        anchors.right: header.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        clip: true
        model: tm.details
        reuseItems: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 5; radius: 3; color: Theme.tint(0.2) } }
        delegate: Rectangle {
            id: row
            required property string key
            required property string name
            required property int pid
            required property string status
            required property string user
            required property string cpuText
            required property string memText
            required property string command
            readonly property bool isSel: root.host.selected !== null && root.host.selected.key === "pid:" + pid
            readonly property var values: ({ name: name, pid: String(pid), status: status, user: user, cpu: cpuText, mem: memText, command: command })
            width: ListView.view.width
            height: 32
            radius: 7
            color: isSel ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18) : (dm.containsMouse ? Theme.hover : "transparent")
            Row {
                anchors.fill: parent
                Repeater {
                    model: root.cols
                    delegate: Text {
                        required property var modelData
                        width: root.colWidth(modelData, header.width)
                        height: row.height
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: modelData.right ? Text.AlignRight : Text.AlignLeft
                        leftPadding: 12
                        rightPadding: 12
                        elide: Text.ElideRight
                        text: row.values[modelData.key]
                        color: modelData.key === "command" ? Theme.textMuted : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                    }
                }
            }
            MouseArea {
                id: dm
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (mouse) => {
                    root.host.selected = { key: "pid:" + row.pid, name: row.name, pids: [row.pid], kind: row.user === "root" ? "sys" : "bg" }
                    if (mouse.button === Qt.RightButton) {
                        const p = row.mapToItem(root, mouse.x, mouse.y)
                        menu.x = Math.min(p.x, root.width - menu.width - 8)
                        menu.y = Math.min(p.y, root.height - menu.implicitHeight - 8)
                        menu.open()
                    }
                }
            }
            ToolTip.visible: dm.containsMouse && command.length > 60
            ToolTip.delay: 800
            ToolTip.text: command
        }
    }

    Popup {
        id: menu
        width: 250
        padding: 6
        background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Column {
            spacing: 1
            Repeater {
                model: [
                    { t: "Task beenden", a: "end" },
                    { t: "Sofort beenden (erzwingen)", a: "kill" },
                    { t: "Dateispeicherort öffnen", a: "open" }
                ]
                delegate: Rectangle {
                    required property var modelData
                    width: 238
                    height: 34
                    radius: 8
                    color: mm.containsMouse ? Theme.hover : "transparent"
                    Text { x: 12; anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                    MouseArea {
                        id: mm
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            menu.close()
                            const s = root.host.selected
                            if (modelData.a === "end") root.host.askEnd(s, false)
                            else if (modelData.a === "kill") root.host.askEnd(s, true)
                            else tm.openLocation(s.pids)
                        }
                    }
                }
            }
        }
    }
}
