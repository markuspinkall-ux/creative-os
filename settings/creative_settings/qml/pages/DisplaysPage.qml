import QtQuick
import Creative
import ".."

SettingsPage {
    id: root
    readonly property var d: displays.details

    PageHeader {
        title: "Bildschirme"
        subtitle: displays.screens.length === 1 ? "1 Bildschirm verbunden"
                  : displays.screens.length + " Bildschirme verbunden · Ziehen zum Anordnen"
        CButton { text: "Bildschirme erkennen"; onClicked: displays.refresh() }
        CButton { text: "Übernehmen"; primary: true; enabled: displays.dirty && displays.confirmSeconds === 0; onClicked: displays.apply() }
    }

    Message { text: displays.message; warning: true }

    // Rückfrage nach dem Übernehmen (wie bei Windows)
    Rectangle {
        visible: displays.confirmSeconds > 0
        width: parent.width
        height: 74
        radius: 14
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
        border.color: Theme.accent
        Column {
            x: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            Text { text: "Diese Einstellung behalten?"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 15; font.bold: true }
            Text {
                text: "Ohne Antwort wird in " + displays.confirmSeconds + " Sekunden automatisch zurückgestellt."
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            CButton { text: "Zurücksetzen"; onClicked: displays.revert() }
            CButton { text: "Behalten"; primary: true; onClicked: displays.keep() }
        }
    }

    // ---- Vorschau zum Anordnen ---------------------------------------------------------
    Rectangle {
        id: stage
        width: parent.width
        height: 230
        radius: 16
        color: Theme.ground
        border.color: Qt.rgba(1, 1, 1, 0.05)

        readonly property var list: displays.screens
        readonly property real totalW: {
            let r = 1
            for (const s of list) r = Math.max(r, s.x + s.w)
            return r
        }
        readonly property real totalH: {
            let r = 1
            for (const s of list) r = Math.max(r, s.y + s.h)
            return r
        }
        readonly property real k: Math.min((width - 80) / totalW, (height - 60) / totalH)
        readonly property real ox: (width - totalW * k) / 2
        readonly property real oy: (height - totalH * k) / 2

        Repeater {
            model: stage.list
            delegate: Rectangle {
                id: mon
                readonly property bool sel: modelData.index === displays.selected
                x: stage.ox + modelData.x * stage.k
                y: stage.oy + modelData.y * stage.k
                width: Math.max(40, modelData.w * stage.k - 6)
                height: Math.max(30, modelData.h * stage.k - 6)
                radius: 10
                opacity: modelData.enabled ? 1 : 0.4
                color: sel ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15) : Theme.raised
                border.color: sel ? Theme.accent : Qt.rgba(1, 1, 1, 0.1)
                border.width: sel ? 2 : 1
                z: dragArea.drag.active ? 10 : 1

                Column {
                    anchors.centerIn: parent
                    spacing: 2
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: modelData.number
                        color: mon.sel ? Theme.accent : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 28
                        font.bold: true
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: modelData.name + " · " + (modelData.primary ? "Hauptbildschirm" : (modelData.enabled ? modelData.resolution : "Aus"))
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        font.bold: modelData.primary
                    }
                }

                MouseArea {
                    id: dragArea
                    anchors.fill: parent
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    drag.target: displays.screens.length > 1 ? mon : null
                    drag.threshold: 6
                    onPressed: displays.select(modelData.index)
                    onReleased: {
                        if (Math.abs(mon.x - (stage.ox + modelData.x * stage.k)) > 2
                                || Math.abs(mon.y - (stage.oy + modelData.y * stage.k)) > 2) {
                            displays.moveTo(modelData.index,
                                            Math.round((mon.x - stage.ox) / stage.k),
                                            Math.round((mon.y - stage.oy) / stage.k))
                        }
                    }
                }
            }
        }
    }

    // ---- Einstellungen des gewählten Bildschirms -----------------------------------------
    Card {
        title: root.d.number ? "Bildschirm " + root.d.number + " · " + root.d.name : ""
        visible: !!root.d.number
        SettingRow {
            label: "Eingeschaltet"
            hint: "Ein ausgeschalteter Bildschirm bleibt dunkel"
            CSwitch { checked: !!root.d.enabled; label: "Eingeschaltet"; onToggled: (v) => displays.setEnabled(v) }
        }
        SettingRow {
            label: "Hauptbildschirm"
            hint: "Hier erscheinen neue Fenster und die Schreibtisch-Symbole"
            CButton {
                text: root.d.primary ? "Ist Hauptbildschirm" : "Zum Hauptbildschirm machen"
                enabled: !root.d.primary && !!root.d.enabled
                onClicked: displays.makePrimary()
            }
        }
        SettingRow {
            label: "Auflösung"
            CCombo { label: "Auflösung"; enabled: !!root.d.enabled; model: root.d.resolutions || []; value: root.d.resolution || ""; onActivated: (t) => displays.setResolution(t) }
        }
        SettingRow {
            label: "Bildwiederholrate"
            hint: "Höher = flüssiger, z. B. beim Spielen"
            CCombo { label: "Bildwiederholrate"; enabled: !!root.d.enabled; model: root.d.rates || []; value: root.d.rate || ""; onActivated: (t) => displays.setRate(t) }
        }
        SettingRow {
            label: "Skalierung"
            hint: "Macht Schrift und Fenster größer – sinnvoll bei 4K"
            CCombo { label: "Skalierung"; enabled: !!root.d.enabled; model: root.d.scales || []; value: root.d.scale || ""; onActivated: (t) => displays.setScale(t) }
        }
        SettingRow {
            label: "Ausrichtung"
            last: true
            CCombo { label: "Ausrichtung"; enabled: !!root.d.enabled; model: root.d.rotations || []; value: root.d.rotation || ""; onActivated: (t) => displays.setRotation(t) }
        }
    }

    Card {
        title: "Tipps für mehrere Bildschirme"
        SettingRow { label: "Fenster auf einen anderen Bildschirm schieben"; hint: "Windows-Taste + Umschalt + Pfeil links/rechts"; Text { text: "⊞ ⇧ ← →"; color: Theme.textMuted; font.pixelSize: 13 } }
        SettingRow { label: "Fenster an den Rand einrasten (halbe Breite)"; hint: "Windows-Taste + Pfeil links/rechts – oder Fenster an den Rand ziehen"; Text { text: "⊞ ← →"; color: Theme.textMuted; font.pixelSize: 13 } }
        SettingRow { label: "Jeder Bildschirm hat seine eigene Taskleiste"; hint: "Sie zeigt nur die Fenster, die auf diesem Bildschirm liegen"; last: true; Item { width: 1; height: 1 } }
    }
}
