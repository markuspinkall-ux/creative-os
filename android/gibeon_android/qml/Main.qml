import QtCore
import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Android-Apps – Android (Waydroid) mit einem Klick einrichten, Play Store öffnen,
// APKs installieren und das Gerät bei Google anmelden.
Window {
    id: win
    width: 1000
    height: 720
    minimumWidth: 860
    minimumHeight: 600
    visible: true
    title: "Android-Apps"
    color: Theme.surface

    property bool showLog: false
    readonly property bool working: android.busy !== ""

    // ---- Kopf -------------------------------------------------------------------------
    Row {
        id: head
        x: 26
        y: 20
        spacing: 12
        Rectangle {
            width: 38; height: 38; radius: 12
            color: Theme.accent
            SvgIcon { anchors.centerIn: parent; name: "android"; size: 18 }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "Android-Apps"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true }
            Text {
                text: "Android-Apps und den Google Play Store auf Gibeon OS nutzen – mit Waydroid"
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }
    }

    Flickable {
        id: page
        x: 20
        y: 84
        width: parent.width - 40
        height: parent.height - y - 16
        clip: true
        contentHeight: body.implicitHeight + 8
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: body
            width: page.width
            spacing: 16

            // ---- Waydroid fehlt (sollte im System immer dabei sein) ------------------------
            Card {
                visible: !android.installed
                Column {
                    width: parent.width
                    spacing: 6
                    Text { text: "Waydroid fehlt"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap
                        text: "Diese Version von Gibeon OS enthält Waydroid noch nicht. Bitte in der Systemsteuerung unter „Updates“ aktualisieren."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                    }
                }
            }

            // ---- Noch nicht eingerichtet: Auswahl -------------------------------------------
            Row {
                id: modes
                visible: android.installed && !android.isSetUp
                width: parent.width
                spacing: 16
                enabled: !win.working
                opacity: enabled ? 1 : 0.6
                ModeCard {
                    width: (modes.width - 16) / 2
                    key: "google"
                    icon: "store"
                    title: "Mit Google Play Store"
                    text: "Android mit Play Store und Google-Diensten. Danach meldest du den PC einmal bei Google an (Anleitung folgt hier). Banking-Apps und Netflix in HD laufen oft trotzdem nicht."
                }
                ModeCard {
                    width: (modes.width - 16) / 2
                    key: "frei"
                    icon: "shield"
                    title: "Ohne Google"
                    text: "Schlankes Android ohne Google-Konto. Apps installierst du als APK-Datei oder über freie App-Stores wie F-Droid."
                }
            }

            Card {
                visible: android.installed && !android.isSetUp
                Column {
                    width: parent.width
                    spacing: 10
                    InfoRow { label: "Grafik"; value: android.graphicsText; warn: android.graphics !== "hw" }
                    InfoRow { label: "Download"; value: "Etwa 1 GB, insgesamt rund 4 GB Speicher. Dein Passwort wird einmal abgefragt." }
                    InfoRow {
                        visible: android.choice === "google"
                        label: "Hinweis"
                        value: "Die Google-Apps kommen direkt von Waydroid und Google, nicht von Gibeon OS. Mit der Einrichtung gelten die Bedingungen von Google."
                    }
                    InfoRow {
                        visible: android.graphics === "sw"
                        label: "Tipp"
                        value: "Hat dein Prozessor eine eingebaute Grafik, schalte sie im BIOS ein (oft „iGPU Multi-Monitor“). Dann nutzt Android sie automatisch – mit Beschleunigung."
                    }
                }
            }

            // ---- Eingerichtet: Bedienung -------------------------------------------------------
            Card {
                visible: android.installed && android.isSetUp
                Column {
                    width: parent.width
                    spacing: 14
                    Row {
                        width: parent.width
                        spacing: 12
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 12; height: 12; radius: 6
                            color: android.session === "RUNNING" ? Theme.ok : (android.session === "STARTING" ? Theme.accent : Theme.tint(0.3))
                            SequentialAnimation on opacity {
                                running: android.session === "STARTING"; loops: Animation.Infinite
                                NumberAnimation { to: 0.3; duration: 500 }
                                NumberAnimation { to: 1; duration: 500 }
                            }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 24 - startStop.width
                            spacing: 2
                            Text {
                                text: android.session === "RUNNING" ? "Android läuft"
                                      : (android.session === "STARTING" ? "Android startet …" : "Android ist aus")
                                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true
                            }
                            Text {
                                width: parent.width; wrapMode: Text.WordWrap
                                text: (android.google ? "Mit Google Play Store" : "Ohne Google") + " · "
                                      + (android.appCount === 1 ? "1 App im Startmenü" : android.appCount + " Apps im Startmenü")
                                      + (android.session === "STOPPED" ? " · startet von selbst, sobald du eine Android-App öffnest" : "")
                                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                            }
                        }
                        CButton {
                            id: startStop
                            anchors.verticalCenter: parent.verticalCenter
                            enabled: !win.working && android.session !== "STARTING"
                            text: android.session === "STOPPED" ? "Starten" : "Beenden"
                            onClicked: android.session === "STOPPED" ? android.startAndroid() : android.stopAndroid()
                        }
                    }
                    Row {
                        spacing: 8
                        enabled: !win.working
                        CButton { visible: android.google; primary: true; text: "Play Store öffnen"; onClicked: android.openStore() }
                        CButton { text: "APK installieren …"; onClicked: apkDialog.open() }
                        CButton { text: "Android-Oberfläche"; onClicked: android.showFull() }
                    }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap
                        text: "Installierte Android-Apps findest du ganz normal im Startmenü. Sie öffnen sich als eigene Fenster."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                    }
                }
            }

            // ---- Bei Google anmelden ------------------------------------------------------------
            Card {
                visible: android.installed && android.isSetUp && android.google
                Column {
                    width: parent.width
                    spacing: 12
                    Text { text: "PC bei Google anmelden"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap
                        text: "Meldet der Play Store „Gerät ist nicht zertifiziert“, trägst du den PC einmal bei Google ein. Das ist der offizielle Weg von Google für selbst eingerichtete Android-Systeme."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                    }
                    Step {
                        num: 1
                        text: "Play Store einmal öffnen und eine Minute warten"
                        CButton { visible: android.session !== "RUNNING"; text: "Play Store öffnen"; onClicked: android.openStore() }
                    }
                    Step {
                        num: 2
                        text: android.gsfId ? "Geräte-ID: " + android.gsfId : "Geräte-ID auslesen"
                        CButton { visible: !android.gsfId; enabled: !win.working; text: "ID anzeigen"; onClicked: android.fetchGsf() }
                        CButton { visible: android.gsfId !== ""; text: "Kopieren"; onClicked: android.copyGsf() }
                    }
                    Step {
                        num: 3
                        text: "Auf der Google-Seite eintragen, „Registrieren“ klicken"
                        CButton { text: "Google-Seite öffnen"; onClicked: android.openRegister() }
                    }
                    Step {
                        num: 4
                        text: "Etwa 15 Minuten warten, Android beenden und neu starten"
                    }
                }
            }

            // ---- Meldung, Fortschritt, Protokoll --------------------------------------------------
            Rectangle {
                width: parent.width
                height: runCol.implicitHeight + 36
                radius: 18
                visible: android.installed && (!android.isSetUp || win.working || android.error !== "" || android.message !== "")
                color: Theme.raised
                border.color: android.error ? Qt.rgba(0.9, 0.28, 0.3, 0.6) : (android.message ? Qt.rgba(0.43, 0.86, 0.75, 0.6) : Theme.hairline)

                Column {
                    id: runCol
                    x: 20; y: 18
                    width: parent.width - 40
                    spacing: 12
                    Row {
                        width: parent.width
                        spacing: 12
                        Column {
                            width: parent.width - btnRow.width - 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3
                            Text {
                                width: parent.width; elide: Text.ElideRight
                                text: win.working ? android.status
                                      : (android.error ? "Hat nicht geklappt" : (android.message ? "Erledigt" : "Bereit"))
                                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true
                            }
                            Text {
                                width: parent.width; wrapMode: Text.WordWrap
                                text: android.error ? android.error
                                      : (android.message ? android.message
                                      : (win.working ? "Du kannst nebenbei normal weiterarbeiten."
                                         : "Mit „Android-Apps aktivieren“ geht es los."))
                                color: android.error ? Theme.flame : Theme.textMuted
                                font.family: Theme.fontFamily; font.pixelSize: 12
                            }
                        }
                        Row {
                            id: btnRow
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8
                            CButton { visible: android.busy === "einrichten"; text: "Abbrechen"; onClicked: android.cancel() }
                            CButton {
                                visible: !win.working && (android.error !== "" || android.message !== "") && android.isSetUp
                                text: "OK"; onClicked: android.clearMessage()
                            }
                            CButton {
                                visible: !win.working && !android.isSetUp
                                primary: true
                                text: "Android-Apps aktivieren"
                                onClicked: android.setUp()
                            }
                        }
                    }
                    Rectangle {
                        visible: android.busy === "einrichten" || android.busy === "entfernen"
                        width: parent.width
                        height: 8
                        radius: 4
                        color: Theme.tint(0.08)
                        Rectangle {
                            width: parent.width * Math.max(0.02, android.percent / 100)
                            height: parent.height
                            radius: 4
                            color: Theme.accent
                            Behavior on width { NumberAnimation { duration: 400 } }
                        }
                    }
                    Text {
                        visible: android.log !== ""
                        text: (win.showLog ? "▾ " : "▸ ") + "Protokoll"
                        color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: 12
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: win.showLog = !win.showLog }
                    }
                    Rectangle {
                        visible: win.showLog && android.log !== ""
                        width: parent.width
                        height: 200
                        radius: 10
                        color: Theme.ground
                        Flickable {
                            id: logView
                            anchors.fill: parent
                            anchors.margins: 10
                            clip: true
                            contentHeight: logText.implicitHeight
                            boundsBehavior: Flickable.StopAtBounds
                            onContentHeightChanged: contentY = Math.max(0, contentHeight - height)
                            Text {
                                id: logText
                                width: logView.width
                                wrapMode: Text.WrapAnywhere
                                text: android.log
                                color: Theme.textMuted
                                font.family: "monospace"
                                font.pixelSize: 11
                            }
                        }
                    }
                }
            }

            // ---- Einstellungen -------------------------------------------------------------------
            Card {
                visible: android.installed && android.isSetUp
                Column {
                    width: parent.width
                    spacing: 12
                    Text { text: "Fenster"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
                    OptionRow {
                        title: "Fensterrahmen wie bei allen Fenstern"
                        text: "Android-Apps bekommen dieselbe Titelleiste wie alle anderen Fenster – mit Minimieren, Maximieren und Schließen. Die kleine Android-Leiste im Fenster bleibt zusätzlich. Gilt ab dem nächsten Start von Android."
                        checked: android.frame
                        onToggled: (v) => android.setFrame(v)
                    }
                    OptionRow {
                        title: "Im Tablet-Format öffnen"
                        text: "Neue Android-Fenster öffnen sich groß im Querformat wie auf einem Tablet statt schmal wie auf einem Handy. Apps, die nur hochkant gedacht sind, wirken dabei manchmal gestreckt."
                        checked: android.tablet
                        onToggled: (v) => android.setTablet(v)
                    }
                    Divider { width: parent.width }
                    InfoRow { label: "Grafik"; value: android.graphicsText; warn: android.graphics !== "hw" }
                    Row {
                        spacing: 8
                        enabled: !win.working
                        CButton { text: "Grafik neu einstellen"; onClicked: android.fixGraphics() }
                        CButton { danger: true; text: "Android entfernen …"; onClicked: removeAsk.open() }
                    }
                }
            }
        }
    }

    FilePicker {
        id: apkDialog
        title: "Android-App (APK) wählen"
        nameFilters: ["*.apk"]
        startFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        onAccepted: (url) => android.installApk(url.toString())
    }

    ConfirmDialog {
        id: removeAsk
        title: "Android entfernen?"
        text: "Android, alle Android-Apps und ihre Daten werden gelöscht. Du kannst es später jederzeit wieder einrichten."
        confirmText: "Entfernen"
        danger: true
        onConfirmed: android.remove()
    }

    // ---- Bausteine -------------------------------------------------------------------------
    component Card: Rectangle {
        default property alias content: inner.data
        width: parent ? parent.width : 0
        height: inner.childrenRect.height + 36
        radius: 18
        color: Theme.raised
        border.color: Theme.hairline
        Item {
            id: inner
            x: 20; y: 18
            width: parent.width - 40
        }
    }

    component ModeCard: Rectangle {
        id: mc
        property string key
        property string icon
        property string title
        property string text
        readonly property bool cur: android.choice === key
        height: 150
        radius: 18
        color: cur ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12) : (mcMouse.containsMouse ? Theme.tint(0.05) : Theme.raised)
        border.color: cur ? Theme.accent : Theme.hairline
        border.width: cur ? 2 : 1
        Row {
            x: 18; y: 18
            spacing: 10
            Rectangle {
                width: 32; height: 32; radius: 10
                color: mc.cur ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.25) : Theme.tint(0.06)
                SvgIcon { anchors.centerIn: parent; name: mc.icon; size: 16 }
            }
            Text { anchors.verticalCenter: parent.verticalCenter; text: mc.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
        }
        Text {
            x: 18; y: 62
            width: parent.width - 36
            wrapMode: Text.WordWrap
            text: mc.text
            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
        }
        MouseArea { id: mcMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: android.setChoice(mc.key) }
        Accessible.role: Accessible.RadioButton
        Accessible.name: mc.title
    }

    component InfoRow: Row {
        property string label
        property string value
        property bool warn: false
        width: parent ? parent.width : 0
        spacing: 16
        Text {
            width: 100
            text: parent.label
            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true
        }
        Text {
            width: parent.width - 116
            wrapMode: Text.WordWrap
            text: parent.value
            color: parent.warn ? Theme.flame : Theme.textMuted
            font.family: Theme.fontFamily; font.pixelSize: 12
        }
    }

    component OptionRow: Row {
        id: opt
        property string title
        property string text
        property bool checked
        signal toggled(bool value)
        width: parent ? parent.width : 0
        spacing: 16
        Column {
            width: parent.width - 16 - optSwitch.width
            spacing: 3
            Text { width: parent.width; text: opt.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true; wrapMode: Text.WordWrap }
            Text { width: parent.width; text: opt.text; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12; wrapMode: Text.WordWrap }
        }
        CSwitch {
            id: optSwitch
            anchors.verticalCenter: parent.verticalCenter
            checked: opt.checked
            label: opt.title
            onToggled: (v) => opt.toggled(v)
        }
    }

    component Step: Row {
        id: st
        property int num
        property string text
        default property alias buttons: btns.data
        width: parent ? parent.width : 0
        spacing: 12
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 26; height: 26; radius: 13
            color: Theme.tint(0.08)
            Text { anchors.centerIn: parent; text: st.num; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 38 - btns.width - 12
            wrapMode: Text.WordWrap
            text: st.text
            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
        }
        Row { id: btns; anchors.verticalCenter: parent.verticalCenter; spacing: 8 }
    }
}
