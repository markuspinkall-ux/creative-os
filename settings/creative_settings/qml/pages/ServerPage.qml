import QtQuick
import Creative
import ".."

SettingsPage {
    id: root

    PageHeader {
        title: "Mein Server"
        subtitle: "Deine eigene Webseite auf einer eigenen Festplatte – ein Schalter, fertig."
    }

    Message { text: server.installed ? server.message : "„Mein Server“ ist auf diesem System nicht installiert."; warning: !server.installed || server.message.indexOf("nicht") >= 0 }

    // ---- Schalter -------------------------------------------------------------------
    Rectangle {
        width: parent.width
        height: 96
        radius: 16
        color: server.active ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.1) : Qt.rgba(1, 1, 1, 0.03)
        border.color: server.active ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.35) : "transparent"

        Rectangle {
            x: 20
            anchors.verticalCenter: parent.verticalCenter
            width: 56; height: 56; radius: 16
            color: server.active ? Theme.accent : Qt.rgba(1, 1, 1, 0.08)
            SvgIcon { anchors.centerIn: parent; name: server.active ? "server-dark" : "server"; size: 26 }
        }
        Column {
            x: 94
            width: parent.width - 94 - right.width - 30
            anchors.verticalCenter: parent.verticalCenter
            spacing: 5
            Row {
                spacing: 8
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 9; height: 9; radius: 5
                    color: server.active ? Theme.ok : Theme.textMuted
                }
                Text {
                    text: server.busy ? "Einen Moment …" : (server.active ? "Server läuft" : "Server ist aus")
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 17
                    font.bold: true
                }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: server.active ? "Im Heimnetz erreichbar unter " + server.urls.join("  ·  ")
                                    : "Wähle unten eine Festplatte und schalte den Server ein."
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
        }
        Row {
            id: right
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16
            CButton { visible: server.active; text: "Webseite öffnen"; anchors.verticalCenter: parent.verticalCenter; onClicked: server.openWebsite() }
            CSwitch {
                anchors.verticalCenter: parent.verticalCenter
                checked: server.active
                enabled: !server.busy
                opacity: server.busy ? 0.5 : 1
                label: "Server eingeschaltet"
                onToggled: (v) => server.setEnabled(v)
            }
        }
    }

    Card {
        title: "Datenbanken"
        SettingRow {
            label: "MariaDB"
            hint: "Lokalen Datenbankserver starten und grafisch verwalten"
            last: true
            Row {
                spacing: 8
                CButton { text: "MariaDB starten"; enabled: !server.busy; onClicked: server.startDatabase() }
                CButton { text: "MariaDB öffnen"; onClicked: server.openDatabase() }
            }
        }
    }

    // ---- Speicherort ------------------------------------------------------------------
    Card {
        title: "Speicherort"
        subtitle: server.active ? "Zum Wechseln den Server zuerst ausschalten." : "Hier liegt deine Webseite. Es wird nichts formatiert oder gelöscht."
        Grid {
            id: grid
            width: parent.width
            columns: width > 760 ? 3 : (width > 480 ? 2 : 1)
            spacing: 12
            bottomPadding: 6
            Repeater {
                model: server.disks
                delegate: Rectangle {
                    width: (grid.width - (grid.columns - 1) * 12) / grid.columns
                    height: 108
                    radius: 14
                    color: modelData.selected ? Qt.rgba(1, 1, 1, 0.05) : (dm.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : Qt.rgba(1, 1, 1, 0.02))
                    border.color: modelData.selected ? Theme.accent : Qt.rgba(1, 1, 1, 0.08)
                    border.width: modelData.selected ? 2 : 1
                    Column {
                        x: 16; y: 14
                        width: parent.width - 32
                        spacing: 9
                        Item {
                            width: parent.width
                            height: 22
                            Text {
                                width: parent.width - tag.width - 8
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                                text: modelData.name
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.bold: true
                            }
                            Rectangle {
                                id: tag
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: tagText.implicitWidth + 14
                                height: 20
                                radius: 6
                                color: modelData.selected ? Theme.accent : Qt.rgba(1, 1, 1, 0.08)
                                Text {
                                    id: tagText
                                    anchors.centerIn: parent
                                    text: modelData.selected ? "Server" : (modelData.system ? "System" : "Verfügbar")
                                    color: modelData.selected ? Theme.accentText : Theme.text
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                            }
                        }
                        Rectangle {
                            width: parent.width; height: 6; radius: 3
                            color: Qt.rgba(1, 1, 1, 0.1)
                            Rectangle { width: parent.width * modelData.used; height: 6; radius: 3; color: modelData.selected ? Theme.accent : "#5a6478" }
                        }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            text: modelData.info
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                        }
                    }
                    MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true; cursorShape: server.active ? Qt.ArrowCursor : Qt.PointingHandCursor; onClicked: server.choose(modelData.device) }
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: modelData.name
                    Accessible.checked: modelData.selected
                }
            }
        }
        Text {
            visible: server.disks.length <= 1
            width: parent.width
            wrapMode: Text.WordWrap
            bottomPadding: 8
            text: "Tipp: Mit einer zweiten Festplatte bleibt die Webseite getrennt vom System. Ohne Zusatzplatte nutzt der Server einen geschützten Ordner auf dem System-Laufwerk."
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 12
        }
    }

    // ---- Webseite ---------------------------------------------------------------------
    Card {
        title: "Webseite"
        SettingRow {
            label: "Ordner „Webseite“"
            hint: server.site.length ? server.site : "Wird beim Einschalten angelegt"
            CButton { text: "Ordner öffnen"; enabled: server.site.length > 0; onClicked: server.openFolder() }
        }
        SettingRow {
            label: "PHP"
            hint: server.php ? "Eingeschaltet – index.php funktioniert" : "Nur normale Webseiten (HTML)"
            Text { text: server.php ? "Aktiv" : "–"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
        }
        SettingRow {
            label: "Erreichbar"
            hint: server.domain ? "Im Heimnetz und im Internet: https://" + server.domain
                                : "Nur im eigenen Heimnetz – von außen ist der Server nicht sichtbar."
            last: true
            SvgIcon { name: "secure"; size: 18 }
        }
    }

    // ---- Internet ---------------------------------------------------------------------
    Card {
        title: "Im Internet erreichbar"
        subtitle: "Mit kostenloser Adresse von DuckDNS und automatischem HTTPS-Zertifikat"
        visible: server.installed

        SettingRow {
            visible: server.domain !== ""
            label: "https://" + server.domain
            hint: "Deine Webseite ist aus dem Internet erreichbar."
            CButton { text: "Nur noch Heimnetz"; enabled: !server.busy; onClicked: server.disableInternet() }
        }

        Column {
            visible: server.domain === ""
            width: parent.width
            spacing: 12
            bottomPadding: 6

            Repeater {
                model: [
                    "Auf duckdns.org kostenlos anmelden und einen Namen anlegen, z. B. „markus“ → markus.duckdns.org.",
                    "Im Router die Ports 80 und 443 an diesen PC weiterleiten" + (server.localIp ? " (IP-Adresse: " + server.localIp + ")." : "."),
                    "Hier Namen und Token von duckdns.org eintragen und einschalten."
                ]
                delegate: Row {
                    spacing: 12
                    Rectangle {
                        width: 24; height: 24; radius: 12
                        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                        Text { anchors.centerIn: parent; text: index + 1; color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
                    }
                    Text {
                        width: col.width - 40
                        anchors.verticalCenter: parent.verticalCenter
                        wrapMode: Text.WordWrap
                        text: modelData
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                }
            }
            Item { id: col; width: parent.width; height: 1 }

            Row {
                spacing: 8
                Rectangle {
                    width: 280; height: 36; radius: 10
                    color: Theme.ground
                    border.color: duckName.activeFocus ? Theme.accent : Theme.hairline
                    TextInput {
                        id: duckName
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 118
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        clip: true
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: ".duckdns.org"
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                    Text {
                        visible: duckName.text.length === 0
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Dein Name"
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                }
                Rectangle {
                    width: 300; height: 36; radius: 10
                    color: Theme.ground
                    border.color: duckToken.activeFocus ? Theme.accent : Theme.hairline
                    TextInput {
                        id: duckToken
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        echoMode: TextInput.Password
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        clip: true
                    }
                    Text {
                        visible: duckToken.text.length === 0
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Token (von duckdns.org)"
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                }
            }
            Row {
                spacing: 8
                CButton { text: "duckdns.org öffnen"; onClicked: server.openDuckDns() }
                CButton {
                    text: "Im Internet freigeben"
                    primary: true
                    enabled: server.active && !server.busy && duckName.text.length > 0 && duckToken.text.length > 0
                    onClicked: server.enableInternet(duckName.text, duckToken.text)
                }
            }
            Rectangle {
                width: parent.width
                height: warn.implicitHeight + 20
                radius: 10
                color: Qt.rgba(1, 0.69, 0.48, 0.1)
                Text {
                    id: warn
                    x: 12
                    width: parent.width - 24
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: "Dann kann jeder deine Webseite sehen. Lege nur hinein, was öffentlich sein darf. Mit „Nur noch Heimnetz“ ist der Server sofort wieder privat."
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                }
            }
        }
    }
}
