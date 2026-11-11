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
                    text: u.state === "classic" ? "Software öffnen" : (u.busy ? ((u.progressText || "").length ? "Bitte warten …" : "Suche …") : "Nach Updates suchen")
                    enabled: !u.busy
                    primary: u.state === "classic"
                    onClicked: system.checkUpdates()
                }
            }
        }
        // Fortschritt beim Herunterladen oder Kanalwechsel
        Column {
            visible: u.busy && (u.progressText || "").length > 0
            width: parent.width
            spacing: 6
            topPadding: 6
            bottomPadding: 12
            Rectangle {
                id: track
                width: parent.width
                height: 8
                radius: 4
                color: Qt.rgba(1, 1, 1, 0.08)
                clip: true
                // bekannter Fortschritt
                Rectangle {
                    visible: u.progress >= 0
                    width: track.width * Math.max(0.03, u.progress / 100)
                    height: parent.height
                    radius: 4
                    color: Theme.accent
                    Behavior on width { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
                }
                // noch unbekannt: laufender Streifen
                Rectangle {
                    id: runner
                    visible: u.progress < 0
                    width: track.width * 0.25
                    height: parent.height
                    radius: 4
                    color: Theme.accent
                    SequentialAnimation on x {
                        running: runner.visible
                        loops: Animation.Infinite
                        NumberAnimation { from: -track.width * 0.25; to: track.width; duration: 1400; easing.type: Easing.InOutQuad }
                    }
                }
            }
            Text {
                width: parent.width
                text: u.progressText + (u.progress >= 0 && u.progress < 100 ? "  ·  " + u.progress + " %" : "")
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }
    }

    // Secure Boot: Treiber (Grafik, virtuelle Kamera) freischalten
    Card {
        visible: system.secureBoot.secureboot === true && system.secureBoot.enrolled !== true
        title: "Treiber für Secure Boot freischalten"
        subtitle: "Ohne Freischaltung laden NVIDIA-Treiber und die virtuelle Kamera nicht"
        SettingRow {
            label: system.secureBoot.pending ? "Vorgemerkt – jetzt neu starten" : "Einmalig bestätigen"
            hint: system.secureBootMessage || (system.secureBoot.pending
                  ? "Beim Neustart: „Enroll MOK“ › „Continue“ › „Yes“, Passwort creative, dann „Reboot“."
                  : "Nach einem Klick fragt der PC beim nächsten Start einmal auf einem blauen Bildschirm nach (Passwort: creative).")
            last: true
            Row {
                spacing: 8
                CButton { visible: !system.secureBoot.pending; text: "Freischalten"; primary: true; onClicked: system.enrollSecureBoot() }
                CButton { visible: system.secureBoot.pending === true; text: "Jetzt neu starten"; primary: true; onClicked: system.reboot() }
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
            readonly property string shown: u.wantChannel || u.pendingChannel || u.channel
            label: (shown === "test" ? "Test – neue Versionen sofort" : "Stabil – nur geprüfte Versionen")
            hint: u.wantChannel ? "Wechsel läuft – die passende Version wird geladen (Fortschritt oben)."
                  : (u.pendingChannel ? "Gewechselt – aktiv nach dem nächsten Neustart. Ein Klick auf den anderen Kanal macht es rückgängig."
                  : (shown === "test" ? "Du bekommst jede neue Version gleich nach dem Bauen und hilfst beim Testen."
                                      : "Empfohlen. Neue Versionen kommen erst, wenn sie getestet und freigegeben sind."))
            last: true
            Row {
                spacing: 6
                Repeater {
                    model: [{ k: "stabil", t: "Stabil" }, { k: "test", t: "Test" }]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool cur: (u.wantChannel || u.pendingChannel || u.channel) === modelData.k
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
            label: "Was ist neu?"
            hint: "Alle Neuerungen jeder freigegebenen Version"
            CButton { text: "Neuerungen ansehen"; onClicked: news.open() }
        }
        SettingRow {
            label: "Apps aktualisieren"
            hint: "Apps aus „Software“ (Flathub) werden dort aktualisiert."
            last: true
            CButton { text: "Software öffnen"; onClicked: system.openSoftware() }
        }
    }

    NeuerungenDialog {
        id: news
        entries: system.changelog
        version: u.version || ""
        Component.onCompleted: if (showNews) Qt.callLater(open)
    }
}
