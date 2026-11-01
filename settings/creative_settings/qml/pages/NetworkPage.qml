import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root
    property string asking: ""   // WLAN, für das gerade das Passwort abgefragt wird

    PageHeader {
        title: "Netzwerk"
        subtitle: network.wired ? "Mit Kabel verbunden" : (network.connected ? "Verbunden mit „" + network.ssid + "“" : "Nicht verbunden")
        CButton { text: "Netzwerke suchen"; enabled: network.wifiEnabled; onClicked: network.rescan() }
    }

    Message { text: network.available ? network.message : "Die Netzwerkverwaltung (NetworkManager) läuft nicht."; warning: !network.available || network.message.indexOf("nicht") >= 0 }

    Card {
        title: "WLAN"
        SettingRow {
            label: "WLAN verwenden"
            hint: network.wifiEnabled ? "Eingeschaltet" : "Ausgeschaltet – z. B. im Flugzeug"
            last: !network.wifiEnabled || network.networks.length === 0
            CSwitch { checked: network.wifiEnabled; label: "WLAN"; onToggled: (v) => network.setWifiEnabled(v) }
        }
        Repeater {
            model: network.wifiEnabled ? network.networks : []
            delegate: Column {
                width: parent.width
                Item {
                    width: parent.width
                    height: 52
                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: 4
                        anchors.bottomMargin: 4
                        radius: 10
                        color: wm.containsMouse ? Theme.subtle : "transparent"
                    }
                    SvgIcon {
                        x: 10
                        anchors.verticalCenter: parent.verticalCenter
                        name: "wifi"
                        size: 18
                        opacity: 0.35 + 0.65 * modelData.strength / 100
                    }
                    Column {
                        x: 42
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text { text: modelData.ssid; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: modelData.inUse }
                        Text {
                            text: modelData.inUse ? "Verbunden" : (modelData.known ? "Gespeichert" : (modelData.secured ? "Geschützt" : "Offen"))
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                        }
                    }
                    SvgIcon {
                        visible: modelData.secured
                        anchors.right: connectBtn.left
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        name: "lock"
                        size: 14
                        opacity: 0.6
                    }
                    CButton {
                        id: connectBtn
                        anchors.right: parent.right
                        anchors.rightMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !modelData.inUse
                        text: "Verbinden"
                        enabled: !network.busy
                        onClicked: {
                            if (modelData.secured && !modelData.known) {
                                root.asking = modelData.ssid
                                pw.text = ""
                                pw.forceActiveFocus()
                            } else {
                                network.connectTo(modelData.ssid, "")
                            }
                        }
                    }
                    MouseArea { id: wm; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                }
                // Passwort direkt unter dem gewählten Netz
                Row {
                    visible: root.asking === modelData.ssid
                    spacing: 8
                    leftPadding: 42
                    bottomPadding: 10
                    TextField {
                        id: pw
                        width: 260
                        height: 36
                        echoMode: TextInput.Password
                        placeholderText: "WLAN-Passwort"
                        placeholderTextColor: Theme.textMuted
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        leftPadding: 12
                        background: Rectangle { radius: 10; color: Theme.ground; border.color: pw.activeFocus ? Theme.accent : Theme.hairline }
                        onAccepted: { network.connectTo(modelData.ssid, text); root.asking = "" }
                    }
                    CButton { text: "Verbinden"; primary: true; onClicked: { network.connectTo(modelData.ssid, pw.text); root.asking = "" } }
                    CButton { text: "Abbrechen"; onClicked: root.asking = "" }
                }
            }
        }
    }

    Card {
        title: "Kabel (LAN)"
        SettingRow {
            label: network.wired ? "Verbunden" : "Kein Kabel eingesteckt"
            hint: "Mit Kabel verbindet sich der PC automatisch – hier ist nichts einzustellen."
            last: true
            SvgIcon { name: "wired"; size: 20; opacity: network.wired ? 1 : 0.35 }
        }
    }

    Component.onCompleted: network.rescan()
}
