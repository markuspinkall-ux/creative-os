import QtQuick
import QtQuick.Controls.Basic
import Creative

// Rechtsklick auf den Assistenten im Tray: Mikrofon, Stimme, Aktivierungswort,
// Wohnort fürs Wetter – dazu laufende Musik und Timer.
Item {
    id: root
    property string screenName

    function opened() {
        cityField.text = assistant.city
        flick.contentY = 0
        root.forceActiveFocus()
    }
    focus: true
    Keys.onEscapePressed: shell.closePopups()

    function clock(sec) {
        const m = Math.floor(sec / 60), s = sec % 60
        const h = Math.floor(m / 60)
        return (h ? h + ":" + String(m % 60).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0")
    }

    MouseArea { anchors.fill: parent; onClicked: shell.closePopups() }

    Rectangle {
        id: card
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        width: 320
        height: Math.min(parent.height - 10, col.implicitHeight + 32)
        radius: 16
        color: Theme.surface
        border.color: Theme.hairline
        MouseArea { anchors.fill: parent }

        Flickable {
            id: flick
            anchors.fill: parent
            anchors.margins: 16
            contentHeight: col.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}

            Column {
                id: col
                width: flick.width
                spacing: 10

                // Kopf
                Row {
                    spacing: 10
                    Rectangle {
                        width: 36; height: 36; radius: 11
                        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                        SvgIcon { anchors.centerIn: parent; name: "mic"; size: 18 }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Text { text: "Sprachassistent"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                        Text {
                            text: assistant.wake && assistant.wakeAvailable ? "Sag „Computer“ oder klick aufs Mikrofon" : "Klick aufs Mikrofon zum Sprechen"
                            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                        }
                    }
                }

                // Läuft gerade etwas?
                Rectangle {
                    visible: assistant.music !== ""
                    width: parent.width
                    height: 52
                    radius: 12
                    color: Qt.rgba(1, 1, 1, 0.05)
                    SvgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "music"; size: 18 }
                    Text {
                        x: 40
                        width: parent.width - 40 - mBtns.width - 16
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        text: assistant.music
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12
                    }
                    Row {
                        id: mBtns
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        IconButton { width: 30; height: 30; icon: assistant.paused ? "media-play" : "media-pause"; iconSize: 14; label: assistant.paused ? "Weiter" : "Pause"; onClicked: assistant.toggleMusic()
                                     visible: true }
                        IconButton { width: 30; height: 30; icon: "close"; iconSize: 14; label: "Musik stoppen"; onClicked: assistant.stopMusic() }
                    }
                }
                Rectangle {
                    visible: assistant.timer > 0 || assistant.state === "alarm"
                    width: parent.width
                    height: 52
                    radius: 12
                    color: assistant.state === "alarm" ? Qt.rgba(1, 0.69, 0.48, 0.15) : Qt.rgba(1, 1, 1, 0.05)
                    SvgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "clock"; size: 18 }
                    Text {
                        x: 40
                        anchors.verticalCenter: parent.verticalCenter
                        text: assistant.state === "alarm" ? "Timer abgelaufen" : "Timer: noch " + root.clock(assistant.timer)
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true
                    }
                    CButton {
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Stopp"
                        onClicked: assistant.stopTimer()
                    }
                }

                Divider { width: parent.width }

                // Aktivierungswort
                Item {
                    width: parent.width
                    height: 40
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 60
                        Text { text: "Auf „Computer“ hören"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: assistant.wakeAvailable ? "Alles wird auf diesem PC erkannt – nichts geht ins Internet." : "Nicht verfügbar – nur per Klick"
                            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                        }
                    }
                    CSwitch {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        enabled: assistant.wakeAvailable
                        opacity: enabled ? 1 : 0.4
                        checked: assistant.wake && assistant.wakeAvailable
                        label: "Aktivierungswort"
                        onToggled: (v) => assistant.setWake(v)
                    }
                }

                Divider { width: parent.width }

                // Mikrofon
                Text { text: "Mikrofon"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                Repeater {
                    model: [{ name: "", label: "Standard (wie in der Systemsteuerung)" }].concat(assistant.devices)
                    delegate: Choice {
                        text: modelData.label
                        selected: modelData.name === assistant.device
                        onPicked: assistant.setDevice(modelData.name)
                    }
                }

                Divider { width: parent.width }

                // Stimme
                Text { text: "Stimme"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                Repeater {
                    model: assistant.voices
                    delegate: Choice {
                        text: modelData.name
                        selected: modelData.id === assistant.voice
                        onPicked: assistant.setVoice(modelData.id)
                    }
                }
                Text {
                    visible: assistant.voices.length === 0
                    text: "Keine Stimme installiert."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                }

                Divider { width: parent.width }

                // Wohnort
                Text { text: "Wohnort fürs Wetter"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                Row {
                    spacing: 8
                    TextField {
                        id: cityField
                        width: col.width - saveCity.width - 8
                        height: 34
                        leftPadding: 10
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        placeholderText: "z. B. Hamburg"
                        placeholderTextColor: Theme.textMuted
                        background: Rectangle { radius: 9; color: Theme.ground; border.color: cityField.activeFocus ? Theme.accent : Theme.hairline }
                        onAccepted: assistant.setCity(text)
                    }
                    CButton { id: saveCity; text: "Speichern"; enabled: cityField.text.trim() !== assistant.city; onClicked: assistant.setCity(cityField.text) }
                }
            }
        }
    }

    component Choice: Rectangle {
        id: ch
        property string text
        property bool selected: false
        signal picked()
        width: col.width
        height: 34
        radius: 9
        color: selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.13) : (cm.containsMouse ? Theme.hover : "transparent")
        Rectangle {
            x: 10
            anchors.verticalCenter: parent.verticalCenter
            width: 14; height: 14; radius: 7
            color: "transparent"
            border.color: ch.selected ? Theme.accent : Theme.textMuted
            border.width: 2
            Rectangle { anchors.centerIn: parent; width: 6; height: 6; radius: 3; color: Theme.accent; visible: ch.selected }
        }
        Text {
            x: 34
            width: parent.width - 44
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: ch.text
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 12
            font.bold: ch.selected
        }
        MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ch.picked() }
        Accessible.role: Accessible.RadioButton
        Accessible.name: ch.text
        Accessible.checked: ch.selected
    }
}
