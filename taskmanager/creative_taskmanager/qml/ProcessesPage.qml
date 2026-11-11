import QtQuick
import QtQuick.Controls.Basic
import Creative

// Prozesse: Apps, Hintergrundprozesse, Systemprozesse – mit CPU, Speicher, Datenträger.
Item {
    id: root
    property var host

    readonly property int colStatus: 130
    readonly property int colCpu: 92
    readonly property int colMem: 124
    readonly property int colDisk: 104

    // ---- Spaltenkopf mit Gesamtwerten (wie bei Windows) -------------------------------------
    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 18
        anchors.rightMargin: 22
        height: 58

        Row {
            anchors.fill: parent
            Col { key: "name"; label: "Name"; alignRight: false; total: ""; width: parent.width - root.colStatus - root.colCpu - root.colMem - root.colDisk }
            Col { key: "status"; label: "Status"; alignRight: false; total: ""; width: root.colStatus; enabled: false }
            Col { key: "cpu"; label: "CPU"; total: tm.summary.cpu || ""; width: root.colCpu }
            Col { key: "mem"; label: "Arbeitsspeicher"; total: tm.summary.mem || ""; width: root.colMem }
            Col { key: "disk"; label: "Datenträger"; total: tm.summary.disk || ""; width: root.colDisk }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    component Col: Item {
        id: col
        property string key
        property string total
        property string label
        property bool alignRight: true
        height: 58
        readonly property bool sorted: tm.sortColumn === key
        Rectangle { anchors.fill: parent; anchors.margins: 3; radius: 8; color: cm.containsMouse ? Theme.hover : "transparent" }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: col.alignRight ? parent.right : undefined
            anchors.left: col.alignRight ? undefined : parent.left
            anchors.rightMargin: 12
            anchors.leftMargin: 12
            spacing: 2
            Text {
                anchors.right: col.alignRight ? parent.right : undefined
                text: col.total
                visible: text.length > 0
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.bold: true
            }
            Text {
                anchors.right: col.alignRight ? parent.right : undefined
                text: col.label + (col.sorted ? (tm.sortDesc ? "  ↓" : "  ↑") : "")
                color: col.sorted ? Theme.accent : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.bold: col.sorted
            }
        }
        MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tm.sortBy(col.key) }
        Accessible.role: Accessible.ColumnHeader
        Accessible.name: "Sortieren nach " + label
    }

    // ---- Liste ------------------------------------------------------------------------------------
    ListView {
        id: list
        anchors.left: header.left
        anchors.right: header.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.topMargin: 4
        clip: true
        model: tm.processes
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 5; radius: 3; color: Theme.tint(0.2) } }

        delegate: Item {
            id: row
            required property int index
            required property string key
            required property string type
            required property string kind
            required property string name
            required property string icon
            required property string label
            required property int count
            required property bool expanded
            required property bool canExpand
            required property int depth
            required property string cpuText
            required property string memText
            required property string diskText
            required property real cpuHeat
            required property real memHeat
            required property real diskHeat
            required property var pids
            required property string status
            readonly property bool isHeader: type === "header"
            readonly property bool isSel: root.host.selected !== null && root.host.selected.key === key

            width: ListView.view.width
            height: isHeader ? 44 : 36

            function selectMe() {
                if (!isHeader)
                    root.host.selected = { key: key, name: name, pids: pids, kind: kind }
            }

            // Abschnitts-Überschrift
            Text {
                visible: row.isHeader
                x: 12
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                text: row.label
                color: Theme.accent
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.bold: true
            }

            Rectangle {
                visible: !row.isHeader
                anchors.fill: parent
                anchors.topMargin: 1
                radius: 8
                color: row.isSel ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                 : (rm.containsMouse ? Theme.hover : "transparent")
            }

            Row {
                visible: !row.isHeader
                anchors.fill: parent

                // Name
                Item {
                    width: parent.width - root.colStatus - root.colCpu - root.colMem - root.colDisk
                    height: parent.height
                    Item {
                        id: chevron
                        x: 4 + row.depth * 26
                        width: 22
                        height: parent.height
                        SvgIcon {
                            anchors.centerIn: parent
                            visible: row.canExpand && row.depth === 0
                            name: "chevron-down"
                            size: 12
                            rotation: row.expanded ? 0 : -90
                            Behavior on rotation { NumberAnimation { duration: 100 } }
                        }
                        MouseArea { anchors.fill: parent; enabled: row.canExpand; cursorShape: Qt.PointingHandCursor; onClicked: tm.toggleExpand(row.key) }
                    }
                    Item {
                        id: ico
                        anchors.left: chevron.right
                        anchors.leftMargin: 4
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20; height: 20
                        Image {
                            id: appIcon
                            anchors.fill: parent
                            visible: row.icon.length > 0 && status === Image.Ready
                            source: row.icon.length > 0 ? "image://icon/" + row.icon : ""
                            sourceSize.width: 40
                            sourceSize.height: 40
                            asynchronous: true
                        }
                        Rectangle {
                            anchors.fill: parent
                            visible: !appIcon.visible
                            radius: 6
                            color: row.kind === "sys" ? Theme.tint(0.07) : Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                            Text {
                                anchors.centerIn: parent
                                text: row.name.length ? row.name.charAt(0).toUpperCase() : "?"
                                color: row.kind === "sys" ? Theme.textMuted : Theme.accent
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                    }
                    Text {
                        anchors.left: ico.right
                        anchors.leftMargin: 10
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        text: row.name + (row.count > 1 && row.depth === 0 ? "  (" + row.count + ")" : "")
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: row.kind === "app" && row.depth === 0
                    }
                }
                Text {
                    width: root.colStatus
                    leftPadding: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.status
                    color: Theme.flame
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
                Cell { width: root.colCpu; text: row.cpuText; heat: row.cpuHeat }
                Cell { width: root.colMem; text: row.memText; heat: row.memHeat }
                Cell { width: root.colDisk; text: row.diskText; heat: row.diskHeat }
            }

            MouseArea {
                id: rm
                anchors.fill: parent
                anchors.leftMargin: 30 + row.depth * 26
                enabled: !row.isHeader
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (mouse) => {
                    row.selectMe()
                    if (mouse.button === Qt.RightButton)
                        menu.popupFor(row, mouse.x + rm.x, mouse.y)
                }
                onDoubleClicked: if (row.canExpand) tm.toggleExpand(row.key)
            }
            Accessible.role: Accessible.Row
            Accessible.name: name + ", CPU " + cpuText + ", Arbeitsspeicher " + memText
        }
    }

    // Zahl mit Wärme-Hintergrund (je mehr Last, desto kräftiger – wie bei Windows)
    component Cell: Item {
        property alias text: t.text
        property real heat: 0
        height: 36
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 2
            anchors.bottomMargin: 2
            anchors.leftMargin: 2
            radius: 6
            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.04 + parent.heat * 0.42)
        }
        Text {
            id: t
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
    }

    // ---- Rechtsklick-Menü ------------------------------------------------------------------------------
    Popup {
        id: menu
        property var target: null
        function popupFor(item, mx, my) {
            target = { key: item.key, name: item.name, pids: item.pids, kind: item.kind, canExpand: item.canExpand, expanded: item.expanded }
            const p = item.mapToItem(root, mx, my)
            x = Math.min(p.x, root.width - width - 8)
            y = Math.min(p.y, root.height - implicitHeight - 8)
            open()
        }
        width: 250
        padding: 6
        background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Column {
            spacing: 1
            MenuRow { text: "Task beenden"; onClicked: { menu.close(); root.host.askEnd(menu.target, false) } }
            MenuRow { text: "Sofort beenden (erzwingen)"; onClicked: { menu.close(); root.host.askEnd(menu.target, true) } }
            Rectangle { width: parent.width; height: 1; color: Theme.hairline }
            MenuRow {
                visible: menu.target && menu.target.canExpand
                text: menu.target && menu.target.expanded ? "Reduzieren" : "Erweitern"
                onClicked: { menu.close(); tm.toggleExpand(menu.target.key) }
            }
            MenuRow { text: "Dateispeicherort öffnen"; onClicked: { menu.close(); tm.openLocation(menu.target.pids) } }
            MenuRow {
                text: "Im Internet suchen"
                onClicked: { menu.close(); Qt.openUrlExternally("https://search.brave.com/search?q=" + encodeURIComponent(menu.target.name + " Linux Prozess")) }
            }
            MenuRow { text: "Zu den Details wechseln"; onClicked: { menu.close(); root.host.page = "details" } }
        }
    }

    component MenuRow: Rectangle {
        id: mr
        property string text
        signal clicked()
        width: 238
        height: visible ? 34 : 0
        radius: 8
        color: mrm.containsMouse ? Theme.hover : "transparent"
        Text { x: 12; anchors.verticalCenter: parent.verticalCenter; text: mr.text; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
        MouseArea { id: mrm; anchors.fill: parent; hoverEnabled: true; onClicked: mr.clicked() }
    }
}
