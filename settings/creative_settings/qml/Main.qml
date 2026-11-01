import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Systemsteuerung von Creative OS
ApplicationWindow {
    id: win
    width: 1240
    height: 800
    minimumWidth: 900
    minimumHeight: 560
    visible: true
    color: Theme.surface
    title: current.name + " – Systemsteuerung"
    font.family: Theme.fontFamily

    readonly property var pages: [
        { key: "network", name: "Netzwerk", icon: "wifi", file: "NetworkPage.qml", words: "wlan internet lan kabel verbindung passwort" },
        { key: "displays", name: "Bildschirme", icon: "pc", file: "DisplaysPage.qml", words: "monitor auflösung skalierung hz anordnen hauptbildschirm" },
        { key: "sound", name: "Ton", icon: "speaker", file: "SoundPage.qml", words: "lautstärke lautsprecher kopfhörer mikrofon audio sound" },
        { key: "drives", name: "Laufwerke", icon: "drive", file: "DrivesPage.qml", words: "festplatte ssd m2 nvme formatieren einrichten partition laufwerk zustand smart" },
        { key: "printers", name: "Drucker", icon: "printer", file: "PrintersPage.qml", words: "drucken testseite scanner" },
        { key: "server", name: "Mein Server", icon: "server", file: "ServerPage.qml", words: "webserver webseite homepage php caddy festplatte" },
        { key: "look", name: "Darstellung", icon: "palette", file: "LookPage.qml", words: "hintergrund hintergrundbild wallpaper bild" },
        { key: "updates", name: "Software & Updates", icon: "refresh", file: "UpdatesPage.qml", words: "update aktualisieren version neustart" },
        { key: "system", name: "System", icon: "info", file: "SystemPage.qml", words: "info gerätename prozessor ram grafik speicher" }
    ]
    property var current: pages.find(p => p.key === startPage) || pages[0]

    readonly property var shown: {
        const t = search.text.trim().toLowerCase()
        if (!t) return pages
        return pages.filter(p => (p.name + " " + p.words).toLowerCase().indexOf(t) >= 0)
    }

    Shortcut { sequences: ["Ctrl+F"]; onActivated: search.forceActiveFocus() }
    Shortcut { sequences: ["Ctrl+W", "Ctrl+Q"]; onActivated: win.close() }

    // ---- Navigation -------------------------------------------------------------------
    Rectangle {
        id: nav
        width: 250
        height: parent.height
        color: "#171b22"
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Qt.rgba(1, 1, 1, 0.05) }

        Column {
            x: 12
            y: 16
            width: parent.width - 24
            spacing: 2

            Row {
                leftPadding: 8
                bottomPadding: 14
                spacing: 10
                Rectangle {
                    width: 34; height: 34; radius: 17
                    color: Theme.accent
                    Text { anchors.centerIn: parent; text: session.initial; color: Theme.accentText; font.pixelSize: 15; font.bold: true }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { text: session.userName; color: Theme.text; font.pixelSize: 14; font.bold: true }
                    Text { text: "Dein Konto"; color: Theme.textMuted; font.pixelSize: 11 }
                }
            }

            Rectangle {
                width: parent.width
                height: 36
                radius: 10
                color: Theme.ground
                border.color: search.activeFocus ? Theme.accent : "transparent"
                SvgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 14 }
                TextField {
                    id: search
                    anchors.fill: parent
                    leftPadding: 34
                    color: Theme.text
                    placeholderText: "Einstellung suchen"
                    placeholderTextColor: Theme.textMuted
                    font.pixelSize: 13
                    background: null
                    onAccepted: if (win.shown.length) win.current = win.shown[0]
                }
            }
            Item { width: 1; height: 10 }

            Repeater {
                model: win.shown
                delegate: Rectangle {
                    readonly property bool on: modelData.key === win.current.key
                    width: parent.width
                    height: 38
                    radius: 10
                    color: on ? Qt.rgba(1, 1, 1, 0.07) : (nm.containsMouse ? Theme.subtle : "transparent")
                    Rectangle { x: 0; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 14; radius: 2; color: Theme.accent; visible: parent.on }
                    SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: modelData.icon; size: 17 }
                    Text {
                        x: 44
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.name
                        color: Theme.text
                        font.pixelSize: 13
                        font.bold: parent.on
                    }
                    MouseArea { id: nm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: win.current = modelData }
                    Accessible.role: Accessible.PageTab
                    Accessible.name: modelData.name
                }
            }
            Text {
                visible: win.shown.length === 0
                leftPadding: 12
                topPadding: 8
                text: "Nichts gefunden"
                color: Theme.textMuted
                font.pixelSize: 13
            }
        }
    }

    // ---- Seite ---------------------------------------------------------------------------
    Loader {
        anchors.left: nav.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        source: Qt.resolvedUrl("pages/" + win.current.file)
    }
}
