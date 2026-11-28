import QtQuick
import QtQuick.Controls.Basic
import Creative

// „Öffnen mit“: passende Apps oben, darunter alle anderen installierten Apps.
// Klick wählt aus, Doppelklick öffnet sofort. „Immer mit dieser App öffnen“
// macht die App zur Standard-App für diesen Dateityp.
//   chooser: OpenWithChooser aus Python, iconFiles: optional (runde App-Symbole)
Item {
    id: panel

    property var chooser
    property var info: ({})
    property string picked: ""
    property bool showAll: false
    signal finished()

    implicitWidth: 460
    implicitHeight: 560

    function load(paths) {
        info = chooser.prepare(paths)
        showAll = !info.ok || info.recommended.length === 0
        picked = info.ok && info.recommended.length ? info.recommended[0].id : ""
        always.checked = false
    }

    function rows() {
        if (!info.ok)
            return []
        let out = []
        if (info.recommended.length) {
            out.push({ header: "Empfohlene Apps" })
            out = out.concat(info.recommended)
        }
        if (showAll && info.others.length) {
            out.push({ header: info.recommended.length ? "Weitere Apps" : "Alle Apps" })
            out = out.concat(info.others)
        }
        return out
    }

    function open(id) {
        if (id && chooser.choose(id, always.checked))
            panel.finished()
    }

    function iconUrl(name) {
        return (typeof iconFiles !== "undefined" && iconFiles && name) ? iconFiles.app(name) : ""
    }

    Column {
        id: head
        width: parent.width
        spacing: 4
        Text {
            text: "Öffnen mit"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 17
            font.bold: true
        }
        Text {
            width: parent.width
            elide: Text.ElideMiddle
            text: panel.info.ok ? panel.info.title + "  ·  " + panel.info.typeName : "Keine Datei ausgewählt"
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 12
        }
    }

    ListView {
        id: list
        anchors.top: head.bottom
        anchors.topMargin: 14
        anchors.bottom: foot.top
        anchors.bottomMargin: 12
        width: parent.width
        clip: true
        spacing: 2
        model: panel.rows()
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Theme.tint(0.2) }
        }
        delegate: Item {
            id: rowItem
            required property var modelData
            readonly property bool isHeader: modelData.header !== undefined
            readonly property bool current: !isHeader && panel.picked === modelData.id
            width: ListView.view.width
            height: isHeader ? 30 : 44

            Text {
                visible: rowItem.isHeader
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                x: 6
                text: rowItem.isHeader ? rowItem.modelData.header : ""
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.bold: true
            }

            Rectangle {
                visible: !rowItem.isHeader
                anchors.fill: parent
                radius: Theme.radiusRow
                color: rowItem.current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                                       : (rowMouse.containsMouse ? Theme.hover : "transparent")
                border.color: rowItem.current ? Theme.accent : "transparent"

                Image {
                    id: appIcon
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: 28
                    height: 28
                    sourceSize: Qt.size(56, 56)
                    source: rowItem.isHeader ? "" : panel.iconUrl(rowItem.modelData.icon)
                    visible: status === Image.Ready
                }
                SvgIcon {
                    visible: !appIcon.visible
                    x: 16
                    anchors.verticalCenter: parent.verticalCenter
                    name: "open"
                    size: 16
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 50
                    anchors.right: tag.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: rowItem.isHeader ? "" : rowItem.modelData.name
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: rowItem.current
                }
                Text {
                    id: tag
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: !rowItem.isHeader && rowItem.modelData.isDefault ? "Standard" : ""
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: panel.picked = rowItem.modelData.id
                    onDoubleClicked: panel.open(rowItem.modelData.id)
                }
                Accessible.role: Accessible.ListItem
                Accessible.name: rowItem.isHeader ? "" : rowItem.modelData.name
                Accessible.onPressAction: panel.open(rowItem.modelData.id)
            }
        }
        footer: Item {
            width: list.width
            height: !panel.showAll && panel.info.ok && panel.info.others.length ? 48 : 0
            visible: height > 0
            CButton {
                anchors.centerIn: parent
                text: "Alle Apps anzeigen (" + (panel.info.ok ? panel.info.others.length : 0) + ")"
                onClicked: panel.showAll = true
            }
        }
    }

    Column {
        id: foot
        anchors.bottom: parent.bottom
        width: parent.width
        spacing: 14
        Row {
            spacing: 10
            visible: panel.info.ok === true
            CSwitch {
                id: always
                anchors.verticalCenter: parent.verticalCenter
                label: "Immer mit dieser App öffnen"
                onToggled: (v) => checked = v
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Immer mit dieser App öffnen" + (panel.info.ok ? " (" + panel.info.typeName + ")" : "")
                width: panel.width - 60
                elide: Text.ElideRight
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
        }
        Row {
            anchors.right: parent.right
            spacing: 8
            CButton { text: "Abbrechen"; onClicked: panel.finished() }
            CButton { text: "Öffnen"; primary: true; enabled: panel.picked !== ""; onClicked: panel.open(panel.picked) }
        }
    }
}
