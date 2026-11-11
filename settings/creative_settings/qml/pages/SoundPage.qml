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
        meter: true
    }

    Card {
        title: "Anmelde-Ton"
        subtitle: "Ein kurzer Klang, sobald nach der Anmeldung der Desktop erscheint – wie beim Abmelden"
        SettingRow {
            label: "Ton beim Anmelden"
            hint: "Spielt einmal pro Anmeldung"
            last: true
            Row {
                spacing: 12
                CButton {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Anhören"
                    onClicked: look.testLoginSound()
                }
                CSwitch {
                    anchors.verticalCenter: parent.verticalCenter
                    checked: look.loginSound
                    label: "Ton beim Anmelden abspielen"
                    onToggled: (v) => look.setLoginSound(v)
                }
            }
        }
    }

    Card {
        title: "Rauschfreies Mikrofon und virtueller Hintergrund"
        subtitle: "KI-Rauschentfernung fürs Mikrofon und Greenscreen für die Kamera – in Creative Broadcast"
        SettingRow {
            label: "Creative Broadcast"
            hint: "Für Discord, Teams, Zoom und OBS"
            last: true
            CButton { text: "Öffnen"; onClicked: sound.openBroadcast() }
        }
    }

    // ---- Einzelne Apps (wie der Lautstärkemixer bei Windows) -----------------------------
    Card {
        title: "Apps"
        subtitle: sound.apps.length ? "Lautstärke und Ausgabegerät für jedes Programm, das gerade Ton abspielt"
                                    : "Gerade spielt kein Programm Ton ab."
        Repeater {
            model: sound.apps
            delegate: Item {
                id: appRow
                required property var modelData
                readonly property var labels: sound.outputs.map(o => o.label)
                readonly property string current: {
                    const o = sound.outputs.find(o => o.index === modelData.device)
                    return o ? o.label : ""
                }
                width: parent.width
                height: 64
                Rectangle {
                    id: appIcon
                    anchors.verticalCenter: parent.verticalCenter
                    width: 34; height: 34; radius: 10
                    color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                    Text {
                        anchors.centerIn: parent
                        text: appRow.modelData.app.charAt(0).toUpperCase()
                        color: Theme.accent
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                        font.bold: true
                    }
                }
                Column {
                    anchors.left: appIcon.right
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(220, parent.width * 0.28)
                    spacing: 2
                    Text { width: parent.width; elide: Text.ElideRight; text: appRow.modelData.app; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                    Text { width: parent.width; elide: Text.ElideRight; visible: text.length > 0; text: appRow.modelData.media; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
                CSlider {
                    id: appVol
                    anchors.verticalCenter: parent.verticalCenter
                    x: appIcon.width + 24 + Math.min(220, parent.width * 0.28)
                    width: parent.width - x - deviceBox.width - appMute.width - 90
                    from: 0; to: 100
                    value: appRow.modelData.volume
                    onMoved: sound.setAppVolume(appRow.modelData.index, Math.round(value))
                    Accessible.name: "Lautstärke " + appRow.modelData.app
                }
                Text {
                    anchors.left: appVol.right
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: 44
                    text: appRow.modelData.muted ? "Stumm" : Math.round(appVol.value) + " %"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                }
                CSwitch {
                    id: appMute
                    anchors.right: deviceBox.left
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    label: "Ton an: " + appRow.modelData.app
                    checked: !appRow.modelData.muted
                    onToggled: (v) => sound.setAppMuted(appRow.modelData.index, !v)
                }
                CCombo {
                    id: deviceBox
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 200
                    label: "Ausgabegerät für " + appRow.modelData.app
                    model: appRow.labels
                    value: appRow.current
                    enabled: sound.outputs.length > 1
                    onActivated: (t) => {
                        const o = sound.outputs.find(o => o.label === t)
                        if (o) sound.moveApp(appRow.modelData.index, o.name)
                    }
                }
            }
        }
    }

    // ---- Geräteprofile (z. B. HDMI statt Lautsprecher, Headset-Modus) -------------------------
    Card {
        visible: sound.cards.length > 0
        title: "Geräteprofile"
        subtitle: "Fehlt ein Ausgang (z. B. der Bildschirm über HDMI), hier das passende Profil wählen"
        Repeater {
            model: sound.cards
            delegate: SettingRow {
                required property var modelData
                required property int index
                label: modelData.label
                last: index === sound.cards.length - 1
                CCombo {
                    width: 280
                    label: "Profil für " + modelData.label
                    model: modelData.profiles.map(p => p.label)
                    value: modelData.activeLabel
                    onActivated: (t) => {
                        const p = modelData.profiles.find(p => p.label === t)
                        if (p) sound.setProfile(modelData.name, p.name)
                    }
                }
            }
        }
    }

    onVisibleChanged: sound.setMeter(visible)
    Component.onCompleted: sound.setMeter(visible)
    Component.onDestruction: sound.setMeter(false)

    component DeviceCard: Card {
        id: card
        property string icon
        property var devices: []
        property bool meter: false
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
        // Pegelanzeige (Mikrofon): zeigt, ob es etwas hört
        Item {
            visible: card.meter && card.devices.length > 0
            width: parent.width
            height: 26
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Pegel"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
            Rectangle {
                x: 36
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 36
                height: 8
                radius: 4
                color: Theme.track
                Rectangle {
                    width: parent.width * Math.min(1, sound.level * 1.6)
                    height: parent.height
                    radius: 4
                    color: sound.level > 0.55 ? Theme.flame : Theme.ok
                    Behavior on width { NumberAnimation { duration: 70 } }
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
            model: card.devices
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
