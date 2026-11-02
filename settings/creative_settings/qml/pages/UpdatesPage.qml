import QtQuick
import Creative
import ".."

SettingsPage {
    readonly property var u: system.updates

    PageHeader {
        title: "Software & Updates"
        subtitle: u.version ? "Creative OS " + u.version : ""
    }

    Card {
        Item {
            width: parent.width
            height: 76
            Rectangle {
                width: 52; height: 52; radius: 14
                anchors.verticalCenter: parent.verticalCenter
                color: u.state === "reboot" || u.state === "available" ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                       : (u.state === "error" ? Qt.rgba(1, 0.69, 0.48, 0.15) : Qt.rgba(0.43, 0.86, 0.75, 0.15))
                SvgIcon { anchors.centerIn: parent; name: u.state === "available" ? "download" : (u.state === "reboot" ? "power" : "refresh"); size: 24 }
            }
            Column {
                x: 70
                width: parent.width - 70 - buttons.width - 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: u.state === "reboot" ? "Neustart erforderlich" : (u.state === "available" ? "Update verfügbar"
                          : (u.state === "current" ? "Alles aktuell" : (u.state === "classic" ? "Updates" : "Updates")))
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 16
                    font.bold: true
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: u.text
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
            Row {
                id: buttons
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                CButton { visible: u.state === "reboot"; text: "Jetzt neu starten"; primary: true; onClicked: system.reboot() }
                CButton { visible: u.state === "available"; text: "Herunterladen"; primary: true; enabled: !u.busy; onClicked: system.downloadUpdate() }
                CButton {
                    visible: u.state !== "reboot" && u.state !== "available"
                    text: u.state === "classic" ? "Software öffnen" : (u.busy ? "Suche …" : "Nach Updates suchen")
                    enabled: !u.busy
                    primary: u.state === "classic"
                    onClicked: system.checkUpdates()
                }
            }
        }
    }

    // Automatisch zurückgerollt?
    Card {
        visible: (u.rolledBack || "").length > 0
        SettingRow {
            label: "Ein Update wurde automatisch zurückgenommen"
            hint: "Am " + u.rolledBack + " ist eine neue Version nicht richtig gestartet. Creative OS ist von selbst zur letzten funktionierenden Version zurückgekehrt – deine Daten sind unberührt."
            last: true
            Item { width: 1; height: 1 }
        }
    }

    Card {
        visible: u.channel === "stabil" || u.channel === "test"
        title: "Update-Kanal"
        subtitle: "Welche Versionen dieser PC bekommt"
        SettingRow {
            label: u.channel === "test" ? "Test – neue Versionen sofort" : "Stabil – nur geprüfte Versionen"
            hint: u.channel === "test" ? "Du bekommst jede neue Version gleich nach dem Bauen und hilfst beim Testen."
                                       : "Empfohlen. Neue Versionen kommen erst, wenn sie getestet und freigegeben sind."
            last: true
            Row {
                spacing: 6
                Repeater {
                    model: [{ k: "stabil", t: "Stabil" }, { k: "test", t: "Test" }]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool cur: u.channel === modelData.k
                        width: chText.implicitWidth + 28
                        height: 34
                        radius: 17
                        opacity: u.busy && !cur ? 0.5 : 1
                        color: cur ? Theme.accent : (chMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06))
                        Text {
                            id: chText
                            anchors.centerIn: parent
                            text: modelData.t
                            color: parent.cur ? Theme.accentText : Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }
                        MouseArea {
                            id: chMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: !u.busy
                            cursorShape: Qt.PointingHandCursor
                            onClicked: system.setChannel(modelData.k)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Update-Kanal " + modelData.t
                    }
                }
            }
        }
    }

    Card {
        title: "So funktionieren Updates"
        SettingRow { label: "Automatisch im Hintergrund"; hint: "Creative OS lädt Updates selbst herunter, während du arbeitest."; Item { width: 1; height: 1 } }
        SettingRow { label: "Aktiv nach dem nächsten Neustart"; hint: "Nichts ändert sich mitten in der Arbeit."; Item { width: 1; height: 1 } }
        SettingRow { label: "Immer ein Weg zurück"; hint: "Startet eine neue Version nicht richtig, kehrt Creative OS von selbst zur letzten funktionierenden zurück."; Item { width: 1; height: 1 } }
        SettingRow {
            label: "Apps aktualisieren"
            hint: "Apps aus „Software“ (Flathub) werden dort aktualisiert."
            last: true
            CButton { text: "Software öffnen"; onClicked: system.openSoftware() }
        }
    }
}
