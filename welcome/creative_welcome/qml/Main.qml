import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Willkommen bei Creative OS – einmal nach der ersten Anmeldung.
ApplicationWindow {
    id: win
    width: 980
    height: 640
    minimumWidth: 820
    minimumHeight: 560
    visible: true
    title: "Willkommen bei Creative OS"
    color: Theme.ground
    font.family: Theme.fontFamily

    property int step: 0
    readonly property var steps: ["Willkommen", "Internet", "Hintergrund", "So geht's", "Fertig"]

    function next() { if (step < steps.length - 1) step++ }
    function back() { if (step > 0) step-- }

    Shortcut { sequences: ["Return", "Enter"]; enabled: win.step !== 1; onActivated: win.step === win.steps.length - 1 ? welcome.finish() : win.next() }

    // Hintergrund: Graphit, abgedunkelt
    Image {
        anchors.fill: parent
        source: wallpaperUrl
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: 1600
        opacity: 0.55
    }

    // ---- Karte ---------------------------------------------------------------------------
    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 760)
        height: Math.min(parent.height - 60, 520)
        radius: 22
        color: Qt.rgba(28 / 255, 32 / 255, 41 / 255, 0.96)
        border.color: Theme.hairline

        // Fortschritt
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 22
            spacing: 8
            Repeater {
                model: win.steps.length
                delegate: Rectangle {
                    width: index === win.step ? 26 : 8
                    height: 8
                    radius: 4
                    color: index <= win.step ? Theme.accent : Qt.rgba(1, 1, 1, 0.15)
                    Behavior on width { NumberAnimation { duration: 160 } }
                }
            }
        }

        Item {
            id: pageArea
            anchors.fill: parent
            anchors.topMargin: 54
            anchors.bottomMargin: 76
            anchors.leftMargin: 40
            anchors.rightMargin: 40

            // 1) Willkommen
            Column {
                visible: win.step === 0
                anchors.centerIn: parent
                width: parent.width
                spacing: 16
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 96; height: 96; radius: 28
                    color: Theme.accent
                    SvgIcon { anchors.centerIn: parent; name: "rocket"; size: 60 }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Willkommen, " + session.userName + "!"
                    color: Theme.text; font.pixelSize: 32; font.bold: true
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: "Schön, dass du Creative OS benutzt. In einer Minute ist alles eingerichtet – " +
                          "du kannst jeden Schritt auch überspringen."
                    color: Theme.text; font.pixelSize: 15; lineHeight: 1.3
                }
            }

            // 2) Internet
            Column {
                visible: win.step === 1
                width: parent.width
                spacing: 12
                Text { text: "Mit dem Internet verbinden"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: network.wired ? "Du bist schon per Kabel verbunden – hier ist nichts zu tun."
                          : (network.connected ? "Verbunden mit „" + network.ssid + "“." : "Wähle dein WLAN aus.")
                    color: Theme.text; font.pixelSize: 14
                }
                Text {
                    visible: network.message.length > 0
                    text: network.message
                    color: Theme.flame; font.pixelSize: 13
                }
                Flickable {
                    visible: !network.wired
                    width: parent.width
                    height: pageArea.height - 110
                    contentHeight: wifiCol.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: wifiCol
                        width: parent.width
                        spacing: 4
                        property string asking: ""
                        Repeater {
                            model: network.networks
                            delegate: Column {
                                width: wifiCol.width
                                Rectangle {
                                    width: parent.width
                                    height: 48
                                    radius: 12
                                    color: modelData.inUse ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                                                           : (wm.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.03))
                                    SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "wifi"; size: 18; opacity: 0.35 + 0.65 * modelData.strength / 100 }
                                    Text {
                                        x: 46
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.ssid + (modelData.inUse ? "  ·  Verbunden" : "")
                                        color: Theme.text; font.pixelSize: 14; font.bold: modelData.inUse
                                    }
                                    SvgIcon {
                                        visible: modelData.secured
                                        anchors.right: parent.right; anchors.rightMargin: 16
                                        anchors.verticalCenter: parent.verticalCenter
                                        name: "lock"; size: 14; opacity: 0.6
                                    }
                                    MouseArea {
                                        id: wm
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: !modelData.inUse && !network.busy
                                        onClicked: {
                                            if (modelData.secured && !modelData.known) {
                                                wifiCol.asking = modelData.ssid
                                                pw.text = ""
                                                pw.forceActiveFocus()
                                            } else {
                                                network.connectTo(modelData.ssid, "")
                                            }
                                        }
                                    }
                                }
                                Row {
                                    visible: wifiCol.asking === modelData.ssid
                                    spacing: 8
                                    topPadding: 8
                                    bottomPadding: 8
                                    leftPadding: 46
                                    TextField {
                                        id: pw
                                        width: 280; height: 38
                                        echoMode: TextInput.Password
                                        placeholderText: "WLAN-Passwort"
                                        placeholderTextColor: Theme.textMuted
                                        color: Theme.text
                                        font.pixelSize: 14
                                        leftPadding: 12
                                        background: Rectangle { radius: 10; color: Theme.ground; border.color: pw.activeFocus ? Theme.accent : Theme.hairline }
                                        onAccepted: { network.connectTo(modelData.ssid, text); wifiCol.asking = "" }
                                    }
                                    CButton { text: "Verbinden"; primary: true; onClicked: { network.connectTo(modelData.ssid, pw.text); wifiCol.asking = "" } }
                                }
                            }
                        }
                        Text {
                            visible: network.networks.length === 0
                            text: network.wifiEnabled ? "Suche nach WLAN-Netzen …" : "WLAN ist ausgeschaltet."
                            color: Theme.textMuted; font.pixelSize: 14
                        }
                    }
                }
            }

            // 3) Hintergrund
            Column {
                visible: win.step === 2
                width: parent.width
                spacing: 12
                Text { text: "Such dir ein Hintergrundbild aus"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Eigene Bilder legst du später einfach in den Ordner „Bilder“ – sie erscheinen dann in der Systemsteuerung."
                    color: Theme.text; font.pixelSize: 14
                }
                Flow {
                    width: parent.width
                    spacing: 12
                    Repeater {
                        model: look.images.slice(0, 6)
                        delegate: Rectangle {
                            readonly property bool current: modelData.path === look.current
                            width: 210; height: 132; radius: 14
                            color: Theme.ground
                            border.color: current ? Theme.accent : (im.containsMouse ? Qt.rgba(1, 1, 1, 0.3) : Theme.hairline)
                            border.width: current ? 3 : 1
                            Image {
                                anchors.fill: parent
                                anchors.margins: 4
                                source: modelData.url
                                sourceSize.width: 420
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                            }
                            Rectangle {
                                visible: parent.current
                                anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                                width: 26; height: 26; radius: 13
                                color: Theme.accent
                                SvgIcon { anchors.centerIn: parent; name: "check-dark"; size: 14 }
                            }
                            MouseArea { id: im; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: look.setWallpaper(modelData.path) }
                        }
                    }
                }
            }

            // 4) So geht's
            Column {
                visible: win.step === 3
                width: parent.width
                spacing: 14
                Text { text: "So geht's"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Repeater {
                    model: [
                        { icon: "rocket", title: "Startmenü", text: "Windows-Taste oder die Rakete unten links – dort findest du alle Apps und die Suche." },
                        { icon: "files", title: "Dateien", text: "Windows-Taste + E. Gelöschtes landet im Papierkorb unten rechts und lässt sich zurückholen." },
                        { icon: "settings", title: "Systemsteuerung", text: "Windows-Taste + I: WLAN, Bildschirme, Ton, Drucker, Updates und „Mein Server“." },
                        { icon: "games", title: "Spielen", text: "Steam ist schon dabei – einfach anmelden und loslegen." },
                        { icon: "mic", title: "Sprachassistent", text: "Sag „Computer“ oder klick aufs Mikrofon unten rechts – für Wetter, Timer und Musik." }
                    ]
                    delegate: Row {
                        spacing: 14
                        Rectangle {
                            width: 42; height: 42; radius: 12
                            color: modelData.icon === "rocket" ? Theme.accent : Qt.rgba(1, 1, 1, 0.07)
                            SvgIcon { anchors.centerIn: parent; name: modelData.icon; size: modelData.icon === "rocket" ? 26 : 20 }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2
                            Text { text: modelData.title; color: Theme.text; font.pixelSize: 14; font.bold: true }
                            Text { width: pageArea.width - 60; wrapMode: Text.WordWrap; text: modelData.text; color: Theme.text; font.pixelSize: 13; opacity: 0.85 }
                        }
                    }
                }
            }

            // 5) Fertig
            Column {
                visible: win.step === 4
                anchors.centerIn: parent
                width: parent.width
                spacing: 16
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 84; height: 84; radius: 42
                    color: Qt.rgba(0.43, 0.86, 0.75, 0.18)
                    SvgIcon { anchors.centerIn: parent; name: "check"; size: 38 }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Alles bereit!"
                    color: Theme.text; font.pixelSize: 30; font.bold: true
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: "Updates kommen automatisch im Hintergrund. Viel Spaß mit Creative OS!"
                    color: Theme.text; font.pixelSize: 15
                }
            }
        }

        // ---- Knöpfe -------------------------------------------------------------------
        Item {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 24
            height: 40
            CButton {
                visible: win.step > 0 && win.step < win.steps.length - 1
                anchors.left: parent.left
                text: "Zurück"
                onClicked: win.back()
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton {
                    visible: win.step === 1 || win.step === 2
                    text: "Überspringen"
                    onClicked: win.next()
                }
                CButton {
                    text: win.step === 0 ? "Los geht's" : (win.step === win.steps.length - 1 ? "Fertig" : "Weiter")
                    primary: true
                    onClicked: win.step === win.steps.length - 1 ? welcome.finish() : win.next()
                }
            }
        }
    }

    onStepChanged: if (step === 1) network.rescan()
    onClosing: welcome.finish()
}
