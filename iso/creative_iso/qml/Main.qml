import QtCore
import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative Iso – Netzinstallations-ISOs und bootfähige USB-Sticks erstellen.
Window {
    id: win
    width: 1000
    height: 700
    minimumWidth: 860
    minimumHeight: 600
    visible: true
    title: "Creative Iso"
    color: Theme.surface

    property string mode: "net"     // net | usb
    property bool usbConfirm: false
    Component.onCompleted: if (Qt.application.arguments.indexOf("--usb") >= 0) mode = "usb"
    onModeChanged: { usbConfirm = false; if (mode === "usb") iso.refreshUsb() }
    // Sticks ein-/ausstecken wird laufend erkannt
    Timer { interval: 2500; repeat: true; running: win.mode === "usb" && !iso.running; onTriggered: iso.refreshUsb() }
    property bool showLog: false

    // ---- Kopf -------------------------------------------------------------------------
    Row {
        x: 26
        y: 20
        spacing: 12
        Rectangle {
            width: 38; height: 38; radius: 12
            color: Theme.accent
            SvgIcon { anchors.centerIn: parent; name: "disc"; size: 18 }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "Creative Iso"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true }
            Text { text: "Installations-ISOs von Creative OS erstellen und bootfähige USB-Sticks daraus machen"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
    }

    // ---- Auswahl: Art der ISO -----------------------------------------------------------
    Row {
        id: modes
        x: 20
        y: 84
        width: parent.width - 40
        spacing: 16
        enabled: !iso.running
        opacity: enabled ? 1 : 0.6

        ModeCard {
            width: (modes.width - 16) / 2
            key: "net"
            icon: "download"
            title: "Kleine Installations-ISO"
            text: "Unter 1 GB. Creative OS wird während der Installation frisch aus dem Internet geladen – immer die neueste Version."
        }
        ModeCard {
            width: (modes.width - 16) / 2
            key: "usb"
            icon: "usb"
            title: "Bootfähiger USB-Stick"
            text: "Schreibt eine ISO auf einen USB-Stick. Davon startet jeder PC die Installation. Alles auf dem Stick wird gelöscht."
        }
    }

    // ---- Optionen -----------------------------------------------------------------------
    Rectangle {
        id: opts
        x: 20
        y: modes.y + modes.height + 16
        width: parent.width - 40
        height: optCol.implicitHeight + 36
        radius: 18
        color: Theme.raised
        border.color: Theme.hairline
        enabled: !iso.running
        opacity: enabled ? 1 : 0.6

        Column {
            id: optCol
            x: 20; y: 18
            width: parent.width - 40
            spacing: 14

            OptRow {
                visible: win.mode === "net"
                label: "Grafik"
                Chips {
                    current: iso.variant
                    items: [{ k: "amd", t: "AMD / Intel / VM" }, { k: "nvidia", t: "NVIDIA" }]
                    onPicked: (k) => iso.setVariant(k)
                }
            }
            OptRow {
                visible: win.mode === "net"
                label: "Version"
                Chips {
                    current: iso.channel
                    items: [{ k: "stabil", t: "Stabil" }, { k: "test", t: "Test (Vorabversion)" }]
                    onPicked: (k) => iso.setChannel(k)
                }
            }
            OptRow {
                visible: win.mode === "net"
                label: "Grundlage"
                Row {
                    spacing: 8
                    Chips {
                        current: iso.source === "" ? "dl" : "file"
                        items: [{ k: "dl", t: "Automatisch herunterladen" }, { k: "file", t: iso.sourceName ? iso.sourceName : "Heruntergeladene ISO wählen …" }]
                        onPicked: (k) => { if (k === "dl") iso.setSource(""); else sourceDialog.open() }
                    }
                }
            }
            OptRow {
                visible: win.mode === "usb"
                label: "ISO-Datei"
                Row {
                    spacing: 10
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, 420)
                        elide: Text.ElideMiddle
                        text: iso.usbIsoName ? iso.usbIsoName + "  (" + iso.usbIsoSize + ")" : "Noch keine gewählt"
                        color: iso.usbIsoName ? Theme.text : Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                    }
                    CButton { text: "ISO wählen …"; onClicked: usbIsoDialog.open() }
                }
            }
            OptRow {
                visible: win.mode === "usb"
                label: "USB-Stick"
                Row {
                    spacing: 8
                    Chips {
                        visible: iso.sticks.length > 0
                        current: iso.usbDevice
                        items: iso.sticks.map(s => ({ k: s.device, t: s.label }))
                        onPicked: (k) => { iso.setUsbDevice(k); win.usbConfirm = false }
                    }
                    Text {
                        visible: iso.sticks.length === 0
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Kein USB-Stick gefunden – bitte einstecken (in einer VM unter „Geräte › USB“ durchreichen)."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                    }
                }
            }
            Row {
                visible: win.mode === "usb" && iso.usbDevice !== ""
                spacing: 10
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 20; height: 20; radius: 6
                    color: win.usbConfirm ? "#e5484d" : "transparent"
                    border.color: win.usbConfirm ? "#e5484d" : Theme.tint(0.35)
                    border.width: 1.5
                    Text { anchors.centerIn: parent; visible: win.usbConfirm; text: "✓"; color: "white"; font.pixelSize: 14; font.bold: true }
                    MouseArea { anchors.fill: parent; anchors.margins: -4; cursorShape: Qt.PointingHandCursor; onClicked: win.usbConfirm = !win.usbConfirm }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Ja, alles auf diesem Stick darf gelöscht werden"
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: win.usbConfirm = !win.usbConfirm }
                }
                Accessible.role: Accessible.CheckBox
                Accessible.name: "Löschen bestätigen"
                Accessible.checked: win.usbConfirm
            }
            OptRow {
                visible: win.mode !== "usb"
                label: "Speichern in"
                Row {
                    spacing: 10
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, 420)
                        elide: Text.ElideMiddle
                        text: iso.outdir
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
                    }
                    CButton { text: "Ändern …"; onClicked: folderDialog.open() }
                }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: win.mode === "usb"
                      ? (iso.usbIso && iso.usbDevice && !iso.usbFits ? "Der Stick ist zu klein für diese ISO."
                         : "Danach den Stick in den PC stecken, beim Einschalten das Startmenü öffnen (meist F12, F11 oder Esc) und den Stick wählen.")
                      : ("Benötigt etwa 6 GB freien Speicher (frei: " + iso.freeSpace.toFixed(0) + " GB). Ohne eigene ISO wird die Fedora-Netzinstallation (etwa 1 GB) geladen.")
                color: (win.mode === "usb" ? (iso.usbIso && iso.usbDevice && !iso.usbFits)
                        : iso.freeSpace < 6) ? Theme.flame : Theme.textMuted
                font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }
    }

    // ---- Start, Fortschritt, Ergebnis ----------------------------------------------------
    Rectangle {
        id: run
        x: 20
        y: opts.y + opts.height + 16
        width: parent.width - 40
        height: parent.height - y - 20
        radius: 18
        color: Theme.raised
        border.color: iso.error ? Qt.rgba(0.9, 0.28, 0.3, 0.6) : (iso.result ? Qt.rgba(0.43, 0.86, 0.75, 0.6) : Theme.hairline)

        Column {
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
                        width: parent.width
                        elide: Text.ElideRight
                        text: iso.result ? (iso.result.indexOf("/dev/") === 0 ? "USB-Stick ist fertig" : "ISO ist fertig")
                              : (iso.error ? "Hat nicht geklappt" : (iso.running ? iso.status : "Bereit"))
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: iso.result ? (iso.result.indexOf("/dev/") === 0 ? "Du kannst den Stick jetzt abziehen und davon starten." : iso.result)
                              : (iso.error ? iso.error
                              : (iso.running ? (win.mode === "usb" ? "Den Stick bitte nicht abziehen." : "Du kannst nebenbei normal weiterarbeiten.")
                                 : (win.mode === "usb" ? "Mit „Stick erstellen“ geht es los. Dein Passwort wird einmal abgefragt."
                                                       : "Mit „ISO erstellen“ geht es los. Dein Passwort wird einmal abgefragt.")))
                        color: iso.error ? Theme.flame : Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                    }
                }
                Row {
                    id: btnRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    CButton { visible: iso.result !== "" && iso.result.indexOf("/dev/") !== 0; text: "Ordner öffnen"; onClicked: iso.openFolder() }
                    CButton {
                        visible: iso.result !== "" && iso.result.indexOf("/dev/") !== 0
                        text: "Auf USB-Stick schreiben"
                        onClicked: { iso.useResultForUsb(); win.mode = "usb" }
                    }
                    CButton { visible: iso.running; text: "Abbrechen"; onClicked: iso.cancel() }
                    CButton {
                        visible: !iso.running
                        primary: true
                        text: win.mode === "usb" ? "Stick erstellen" : (iso.result || iso.error ? "Neue ISO erstellen" : "ISO erstellen")
                        enabled: win.mode !== "usb" || (iso.usbIso !== "" && iso.usbDevice !== "" && iso.usbFits && win.usbConfirm)
                        onClicked: {
                            if (win.mode === "usb") { win.usbConfirm = false; iso.makeUsb() }
                            else iso.makeNet()
                        }
                    }
                }
            }

            // Fortschrittsbalken
            Rectangle {
                visible: iso.running || iso.result !== ""
                width: parent.width
                height: 8
                radius: 4
                color: Theme.tint(0.08)
                Rectangle {
                    width: parent.width * Math.max(0.02, iso.percent / 100)
                    height: parent.height
                    radius: 4
                    color: iso.result ? Theme.ok : Theme.accent
                    Behavior on width { NumberAnimation { duration: 400 } }
                }
            }

            Text {
                text: (win.showLog ? "▾ " : "▸ ") + "Protokoll"
                color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: 12
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: win.showLog = !win.showLog }
            }
        }

        // Protokoll
        Rectangle {
            visible: win.showLog
            x: 20
            y: 150
            width: parent.width - 40
            height: parent.height - y - 18
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
                    text: iso.log || "Noch keine Ausgabe."
                    color: Theme.textMuted
                    font.family: "monospace"
                    font.pixelSize: 11
                }
            }
        }
    }

    FilePicker {
        id: sourceDialog
        title: "Fedora-Netzinstallation wählen"
        nameFilters: ["*.iso"]
        startFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        onAccepted: (url) => iso.setSource(url.toString())
    }
    FilePicker {
        id: usbIsoDialog
        title: "ISO für den USB-Stick wählen"
        nameFilters: ["*.iso"]
        startFolder: iso.outdirUrl
        onAccepted: (url) => iso.setUsbIso(url.toString())
    }
    FilePicker {
        id: folderDialog
        mode: "folder"
        title: "Speicherort für die ISO"
        startFolder: iso.outdirUrl
        onAccepted: (url) => iso.setOutdir(url.toString())
    }

    // ---- Bausteine -------------------------------------------------------------------------
    component ModeCard: Rectangle {
        id: mc
        property string key
        property string icon
        property string title
        property string text
        readonly property bool cur: win.mode === key
        height: 140
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
        MouseArea { id: mcMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: win.mode = mc.key }
        Accessible.role: Accessible.RadioButton
        Accessible.name: mc.title
    }

    component OptRow: Row {
        property string label
        spacing: 16
        Text {
            width: 120
            anchors.verticalCenter: parent.verticalCenter
            text: parent.label
            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true
        }
    }

    component Chips: Row {
        id: chips
        property var items: []
        property string current
        signal picked(string k)
        spacing: 6
        Repeater {
            model: chips.items
            delegate: Rectangle {
                required property var modelData
                readonly property bool cur: chips.current === modelData.k
                width: Math.min(chText.implicitWidth + 28, 320)
                height: 32
                radius: 16
                color: cur ? Theme.accent : (cm.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
                Text {
                    id: chText
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, 292)
                    elide: Text.ElideMiddle
                    text: modelData.t
                    color: parent.cur ? Theme.accentText : Theme.text
                    font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true
                }
                MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: chips.picked(modelData.k) }
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.t
            }
        }
    }
}
