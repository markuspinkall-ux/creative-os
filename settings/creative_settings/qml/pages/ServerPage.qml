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
            hint: "Nur im eigenen Heimnetz – von außen ist der Server nicht sichtbar."
            last: true
            SvgIcon { name: "secure"; size: 18 }
        }
    }
}
