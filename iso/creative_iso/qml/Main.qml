import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import Creative

// Creative Iso – Installations-ISOs erstellen: aus diesem System oder als kleine
// Netzinstallation (aus einer heruntergeladenen Fedora-ISO).
Window {
    id: win
    width: 1000
    height: 700
    minimumWidth: 860
    minimumHeight: 600
    visible: true
    title: "Creative Iso"
    color: Theme.surface

    property string mode: "full"     // full | net
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
            Text { text: "Installations-ISOs von Creative OS erstellen – zum Installieren auf anderen PCs oder in einer VM"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
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
            key: "full"
            icon: "screen-tool"
            title: "Dieses System als ISO"
            text: "Vollständige ISO mit allem, was auf diesem PC an Creative OS installiert ist. Installiert ohne Internet. Etwa 5 GB, dauert 15–40 Minuten."
        }
        ModeCard {
            width: (modes.width - 16) / 2
            key: "net"
            icon: "download"
            title: "Kleine Installations-ISO"
            text: "Unter 1 GB. Creative OS wird während der Installation frisch aus dem Internet geladen – immer die neueste Version. Grundlage ist eine Fedora-Netzinstallation."
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
                text: win.mode === "full"
                      ? ("Benötigt etwa 25 GB freien Speicher (frei: " + iso.systemFree.toFixed(0) + " GB) und eine Internetverbindung für das ISO-Werkzeug. Das installierte System bekommt danach ganz normal Updates.")
                      : ("Benötigt etwa 6 GB freien Speicher (frei: " + iso.freeSpace.toFixed(0) + " GB). Ohne eigene ISO wird die Fedora-Netzinstallation (etwa 1 GB) geladen.")
                color: (win.mode === "full" ? iso.systemFree < 25 : iso.freeSpace < 6) ? Theme.flame : Theme.textMuted
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
                        text: iso.result ? "ISO ist fertig" : (iso.error ? "Hat nicht geklappt" : (iso.running ? iso.status : "Bereit"))
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: iso.result ? iso.result : (iso.error ? iso.error
                              : (iso.running ? "Du kannst nebenbei normal weiterarbeiten." : "Mit „ISO erstellen“ geht es los. Dein Passwort wird einmal abgefragt."))
                        color: iso.error ? Theme.flame : Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                    }
                }
                Row {
                    id: btnRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    CButton { visible: iso.result !== ""; text: "Ordner öffnen"; onClicked: iso.openFolder() }
                    CButton { visible: iso.running; text: "Abbrechen"; onClicked: iso.cancel() }
                    CButton {
                        visible: !iso.running
                        primary: true
                        text: iso.result || iso.error ? "Neue ISO erstellen" : "ISO erstellen"
                        onClicked: win.mode === "full" ? iso.makeFull() : iso.makeNet()
                    }
                }
            }

            // Fortschrittsbalken
            Rectangle {
                visible: iso.running || iso.result !== ""
                width: parent.width
                height: 8
                radius: 4
                color: Qt.rgba(1, 1, 1, 0.08)
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

    FileDialog {
        id: sourceDialog
        title: "Fedora-Netzinstallation wählen"
        nameFilters: ["ISO-Dateien (*.iso)"]
        onAccepted: iso.setSource(selectedFile.toString())
    }
    FolderDialog {
        id: folderDialog
        title: "Speicherort für die ISO"
        currentFolder: iso.outdirUrl
        onAccepted: iso.setOutdir(selectedFolder.toString())
    }

    // ---- Bausteine -------------------------------------------------------------------------
    component ModeCard: Rectangle {
        id: mc
        property string key
        property string icon
        property string title
        property string text
        readonly property bool cur: win.mode === key
        height: 132
        radius: 18
        color: cur ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12) : (mcMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.05) : Theme.raised)
        border.color: cur ? Theme.accent : Theme.hairline
        border.width: cur ? 2 : 1
        Row {
            x: 18; y: 18
            spacing: 10
            Rectangle {
                width: 32; height: 32; radius: 10
                color: mc.cur ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.25) : Qt.rgba(1, 1, 1, 0.06)
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
                color: cur ? Theme.accent : (cm.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06))
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
