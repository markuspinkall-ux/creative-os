import QtQuick
import QtQuick.Controls.Basic
import Creative

// Kontextmenü im Graphit-Look.
// items: [{label, icon, key, enabled, act}] oder {sep: true}
// Beim Anklicken wird triggered(act) ausgelöst.
Popup {
    id: menu
    property var items: []
    signal triggered(string act)

    padding: 6
    width: 260
    modal: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function openAt(item, px, py) {
        const p = item.mapToItem(parent, px, py)
        x = Math.min(p.x, parent.width - width - 8)
        y = Math.min(p.y, parent.height - implicitHeight - 8)
        open()
    }

    background: Rectangle {
        radius: 14
        color: Theme.raised
        border.color: Theme.hairline
    }

    contentItem: Column {
        spacing: 1
        Repeater {
            model: menu.items
            delegate: Item {
                width: menu.width - 12
                height: modelData.sep ? 9 : 36
                Rectangle {
                    visible: !!modelData.sep
                    anchors.centerIn: parent
                    width: parent.width - 16
                    height: 1
                    color: Theme.hairline
                }
                Rectangle {
                    id: row
                    visible: !modelData.sep
                    readonly property bool on: modelData.enabled === undefined || modelData.enabled
                    anchors.fill: parent
                    radius: 9
                    opacity: on ? 1 : 0.4
                    color: rowMouse.containsMouse && on ? Theme.tint(0.08) : "transparent"
                    SvgIcon {
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        name: modelData.icon || ""
                        size: 15
                    }
                    Text {
                        x: 39
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label || ""
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.key || ""
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: row.on
                        onClicked: {
                            menu.close()
                            menu.triggered(modelData.act)
                        }
                    }
                }
            }
        }
    }
}
