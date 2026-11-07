import QtQuick
import QtQuick.Controls.Basic
import Creative

// Schnellzugriff aus dem Tray: WLAN, Helligkeit aller Monitore, Drucker, Kalender.
Item {
    id: root

    property string screenName

    function opened() {
        passwordBox.visible = false
        password.text = ""
        audioOutput.refresh()
        network.rescan()
        brightness.refresh()
        printers.refresh()
        calendar.reset()
        flick.contentY = 0
        // Klick auf Uhr/Datum: direkt zum Kalender
        if (shell.panelFocus === "calendar")
            Qt.callLater(() => flick.contentY = Math.max(0, flick.contentHeight - flick.height))
        root.forceActiveFocus()
    }

    focus: true
    Keys.onEscapePressed: shell.closePopups()

    component SectionTitle: Text {
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 14
        font.bold: true
    }
    component BodyText: Text {
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 12
        wrapMode: Text.WordWrap
    }

    // Klick in den freien Bereich über dem Schnellzugriff schließt ihn
    MouseArea {
        anchors.fill: parent
        onClicked: shell.closePopups()
    }

    Rectangle {
        id: panel
        anchors.right: parent.right
        anchors.rightMargin: 24
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        // So hoch wie der Inhalt – nur bei kleinen Bildschirmen scrollbar
        height: Math.min(parent.height - 10, content.implicitHeight + 36)
        width: 360
        radius: Theme.radiusMenu
        color: Theme.surface
        border.color: Theme.hairline
        border.width: 1

        MouseArea { anchors.fill: parent }   // Klicks auf das Panel nicht durchreichen

        Flickable {
            id: flick
            anchors.fill: parent
            anchors.margins: 18
            contentHeight: content.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.2) }
            }

            Column {
                id: content
                width: flick.width
                spacing: 12

                SectionTitle { text: "Systemlautstärke" }
                Item {
                    width: parent.width
                    height: 32
                    visible: audioOutput.available

                    IconButton {
                        id: muteOutput
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30; height: 30; iconSize: 17
                        icon: audioOutput.muted || audioOutput.value === 0 ? "volume-off" : "volume"
                        label: audioOutput.muted ? "Ton einschalten" : "Ton stummschalten"
                        onClicked: audioOutput.toggleMute()
                    }
                    CSlider {
                        anchors.left: muteOutput.right
                        anchors.right: volumeText.left
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        value: audioOutput.value
                        Accessible.name: "Systemlautstärke"
                        onMoved: audioOutput.setVolume(Math.round(value))
                    }
                    BodyText {
                        id: volumeText
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: audioOutput.value + " %"
                    }
                }
                BodyText {
                    visible: !audioOutput.available
                    text: "Kein Audioausgang verfügbar."
                }
                Divider { width: parent.width }

                // ---------- WLAN ----------
                Item {
                    width: parent.width
                    height: 24
                    SectionTitle { anchors.verticalCenter: parent.verticalCenter; text: "WLAN" }
                    CSwitch {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        label: "WLAN"
                        checked: network.wifiEnabled
                        onToggled: (value) => network.setWifiEnabled(value)
                    }
                }

                BodyText {
                    width: parent.width
                    text: !network.available ? "NetworkManager ist nicht verfügbar"
                        : network.connected ? "Verbunden mit " + network.ssid
                        : network.wired ? "Kabelverbindung aktiv"
                        : network.wifiEnabled ? "Nicht verbunden" : "WLAN ist ausgeschaltet"
                }

                Column {
                    width: parent.width
                    spacing: 2
                    visible: network.wifiEnabled

                    Repeater {
                        model: network.networks
                        delegate: Rectangle {
                            id: netRow
                            required property var modelData
                            width: parent.width
                            height: 40
                            radius: Theme.radiusRow
                            color: modelData.inUse ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.12)
                                   : (netMouse.containsMouse ? Theme.hover : "transparent")

                            SvgIcon {
                                id: netIcon
                                x: 10
                                anchors.verticalCenter: parent.verticalCenter
                                name: "wifi"
                                size: 16
                                opacity: netRow.modelData.strength > 60 ? 1 : (netRow.modelData.strength > 30 ? 0.75 : 0.5)
                            }
                            Text {
                                anchors.left: netIcon.right
                                anchors.leftMargin: 12
                                anchors.right: badges.left
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                text: netRow.modelData.ssid
                                elide: Text.ElideRight
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.bold: netRow.modelData.inUse
                            }
                            Row {
                                id: badges
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8
                                SvgIcon { name: "secure"; size: 14; visible: netRow.modelData.secured }
                                SvgIcon { name: "check"; size: 14; visible: netRow.modelData.inUse }
                            }
                            MouseArea {
                                id: netMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                enabled: !netRow.modelData.inUse && !network.busy
                                onClicked: {
                                    if (netRow.modelData.secured && !netRow.modelData.known) {
                                        passwordBox.ssid = netRow.modelData.ssid
                                        passwordBox.visible = true
                                        password.text = ""
                                        password.forceActiveFocus()
                                    } else {
                                        passwordBox.visible = false
                                        network.connectTo(netRow.modelData.ssid, "")
                                    }
                                }
                            }
                            Accessible.role: Accessible.Button
                            Accessible.name: "WLAN " + modelData.ssid + (modelData.inUse ? ", verbunden" : "")
                        }
                    }
                }

                Column {
                    id: passwordBox
                    property string ssid
                    visible: false
                    width: parent.width
                    spacing: 8

                    BodyText { width: parent.width; text: "Passwort für „" + passwordBox.ssid + "“" }
                    TextField {
                        id: password
                        width: parent.width
                        height: 38
                        echoMode: TextInput.Password
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        leftPadding: 12
                        background: Rectangle { radius: 10; color: Theme.ground; border.color: Theme.accent; border.width: 1 }
                        Keys.onReturnPressed: connectButton.clicked()
                        Keys.onEnterPressed: connectButton.clicked()
                        Accessible.name: "WLAN-Passwort"
                    }
                    Row {
                        spacing: 8
                        CButton {
                            id: connectButton
                            text: "Verbinden"
                            primary: true
                            enabled: password.text.length >= 8 && !network.busy
                            onClicked: {
                                if (!enabled)
                                    return
                                network.connectTo(passwordBox.ssid, password.text)
                                passwordBox.visible = false
                                password.text = ""
                            }
                        }
                        CButton {
                            text: "Abbrechen"
                            onClicked: { passwordBox.visible = false; password.text = "" }
                        }
                    }
                }

                BodyText {
                    width: parent.width
                    visible: network.message.length > 0
                    text: network.message
                }

                Divider { width: parent.width }

                // ---------- Helligkeit ----------
                SectionTitle { text: "Helligkeit" }

                Repeater {
                    model: brightness.displays
                    delegate: Column {
                        required property var modelData
                        width: content.width
                        spacing: 2
                        BodyText { width: parent.width; text: parent.modelData.name }
                        Row {
                            width: parent.width
                            spacing: 10
                            SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "brightness"; size: 14 }
                            CSlider {
                                width: parent.width - 24
                                value: modelData.value
                                onMoved: brightness.setValue(modelData.key, Math.round(value))
                                Accessible.name: "Helligkeit " + modelData.name
                            }
                        }
                    }
                }

                BodyText {
                    width: parent.width
                    visible: brightness.displays.length === 0
                    text: "Keine regelbaren Bildschirme gefunden. Bei externen Monitoren muss im Monitor-Menü DDC/CI eingeschaltet sein."
                }

                Divider { width: parent.width }

                // ---------- Drucker ----------
                SectionTitle { text: "Drucker" }

                Row {
                    spacing: 12
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 12
                        color: Qt.rgba(1, 1, 1, 0.07)
                        SvgIcon {
                            anchors.centerIn: parent
                            name: printers.attention ? "printer-alert" : "printer"
                            size: 20
                        }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3
                        Text {
                            text: printers.available ? printers.name : "Drucker"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }
                        BodyText { text: printers.statusText }
                    }
                }

                CButton {
                    text: printers.available ? "Druckereinstellungen" : "Drucker hinzufügen"
                    onClicked: {
                        shell.closePopups()
                        printers.openSettings()
                    }
                }

                Divider { width: parent.width }

                // ---------- Kalender ----------
                SectionTitle { text: "Kalender" }
                CalendarView {
                    id: calendar
                    width: parent.width
                }
            }
        }
    }
}
