import QtQuick
import QtQuick.Controls.Basic
import Creative

Item {
    id: root
    property string screenName
    focus: true
    Keys.onEscapePressed: shell.closePopups()
    function opened() { bluetooth.refresh(); root.forceActiveFocus() }
    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }
    Rectangle {
        anchors.right: parent.right; anchors.rightMargin: 24
        anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        width: 360; height: Math.min(parent.height - 10, content.implicitHeight + 36)
        radius: Theme.radiusMenu; color: Theme.surface; border.color: Theme.hairline
        MouseArea { anchors.fill: parent }
        Flickable {
            id: flick
            anchors.fill: parent; anchors.margins: 18
            contentHeight: content.implicitHeight; clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            Column {
                id: content
                width: flick.width; spacing: 12
                Item {
                    width: parent.width; height: 36
                    Row {
                        spacing: 10; anchors.verticalCenter: parent.verticalCenter
                        SvgIcon { name: "bluetooth"; size: 20 }
                        Text { text: "Bluetooth"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
                    }
                    CSwitch {
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        label: "Bluetooth einschalten"; checked: bluetooth.powered
                        enabled: bluetooth.available && !bluetooth.busy
                        onToggled: (v) => bluetooth.setPowered(v)
                    }
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: bluetooth.busy ? "Bluetooth wird aktualisiert …" : (!bluetooth.available ? "Kein Bluetooth-Adapter verfügbar. Bitte Adapter und Flugmodus prüfen." : (bluetooth.powered ? "Geräte verbinden oder neue Geräte koppeln." : "Bluetooth ist ausgeschaltet."))
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                }
                Text {
                    visible: bluetooth.error.length > 0
                    width: parent.width; wrapMode: Text.WrapAnywhere
                    text: bluetooth.error; color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 12
                }
                Row {
                    spacing: 8
                    CButton { text: "Suchen"; enabled: bluetooth.powered && !bluetooth.busy; onClicked: bluetooth.scan() }
                    CButton { text: "Koppeln …"; enabled: bluetooth.powered && !bluetooth.busy; onClicked: { bluetooth.pair(); shell.closePopups() } }
                }
                Divider { width: parent.width }
                Repeater {
                    model: bluetooth.devices
                    delegate: Rectangle {
                        required property var modelData
                        width: content.width; height: 76; radius: 12; color: Theme.subtle
                        Column {
                            x: 12; y: 8; width: parent.width - 24; spacing: 4
                            Text { width: parent.width; text: modelData.name; elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                            Row {
                                spacing: 8
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.connected ? "Verbunden" : (modelData.paired ? "Gekoppelt" : "Nicht gekoppelt")
                                    color: modelData.connected ? Theme.ok : Theme.textMuted
                                    font.family: Theme.fontFamily; font.pixelSize: 11
                                }
                                CButton {
                                    text: modelData.connected ? "Trennen" : (modelData.paired ? "Verbinden" : "Koppeln …")
                                    enabled: bluetooth.powered && !bluetooth.busy
                                    onClicked: {
                                        if (modelData.paired) bluetooth.setConnected(modelData.address, !modelData.connected)
                                        else { bluetooth.pair(); shell.closePopups() }
                                    }
                                }
                            }
                        }
                    }
                }
                Text {
                    visible: bluetooth.powered && bluetooth.devices.length === 0 && !bluetooth.busy
                    width: parent.width; wrapMode: Text.WordWrap
                    text: "Keine Geräte gefunden. Versetze das Gerät in den Kopplungsmodus und klicke auf Suchen."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                }
            }
        }
    }
}
