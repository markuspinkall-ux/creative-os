import QtQuick
import Creative
import ".."

SettingsPage {
    id: root

    PageHeader {
        title: "Ton"
        subtitle: sound.outputs.length ? "Wiedergabe über „" + sound.outputs[0].label + "“" : "Kein Ausgabegerät gefunden"
        CButton { text: "Ton testen"; enabled: sound.outputs.length > 0; onClicked: sound.testSound() }
    }

    Message { text: sound.available ? "" : "Die Tonsteuerung (PipeWire/pactl) ist nicht verfügbar."; warning: true }

    DeviceCard {
        title: "Ausgabe"
        subtitle: "Lautsprecher, Kopfhörer, Bildschirm (HDMI)"
        icon: "speaker"
        devices: sound.outputs
        onChoose: (n) => sound.setOutput(n)
        onVolume: (n, v) => sound.setOutputVolume(n, v)
        onMute: (n, m) => sound.setOutputMuted(n, m)
    }
    DeviceCard {
        title: "Eingabe"
        subtitle: "Mikrofon, Headset"
        icon: "mic"
        devices: sound.inputs
        onChoose: (n) => sound.setInput(n)
        onVolume: (n, v) => sound.setInputVolume(n, v)
        onMute: (n, m) => sound.setInputMuted(n, m)
    }

    component DeviceCard: Card {
        id: card
        property string icon
        property var devices: []
        signal choose(string name)
        signal volume(string name, int value)
        signal mute(string name, bool muted)

        // Lautstärke des aktiven Geräts
        Item {
            visible: card.devices.length > 0
            width: parent.width
            height: 56
            SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: card.icon; size: 20 }
            CSlider {
                id: vol
                x: 36
                width: parent.width - 36 - muteRow.width - 20
                anchors.verticalCenter: parent.verticalCenter
                from: 0; to: 100
                value: card.devices.length ? card.devices[0].volume : 0
                onMoved: card.volume(card.devices[0].name, Math.round(value))
            }
            Row {
                id: muteRow
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: card.devices.length ? (card.devices[0].muted ? "Stumm" : Math.round(vol.value) + " %") : ""
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    width: 52
                    horizontalAlignment: Text.AlignRight
                }
                CSwitch {
                    anchors.verticalCenter: parent.verticalCenter
                    label: "Ton an"
                    checked: card.devices.length ? !card.devices[0].muted : false
                    onToggled: (v) => card.mute(card.devices[0].name, !v)
                }
            }
        }
        Text {
            visible: card.devices.length === 0
            text: "Kein Gerät gefunden."
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 13
            bottomPadding: 6
        }
        // Geräteauswahl
        Repeater {
            model: card.devices.length > 1 ? card.devices : []
            delegate: Rectangle {
                width: parent.width
                height: 42
                radius: 10
                color: modelData.isDefault ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12)
                                           : (dm.containsMouse ? Theme.subtle : "transparent")
                Rectangle {
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 16; height: 16; radius: 8
                    color: "transparent"
                    border.color: modelData.isDefault ? Theme.accent : Theme.textMuted
                    border.width: 2
                    Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; color: Theme.accent; visible: modelData.isDefault }
                }
                Text {
                    x: 40
                    width: parent.width - 52
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: modelData.isDefault
                }
                MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: card.choose(modelData.name) }
            }
        }
    }
}
