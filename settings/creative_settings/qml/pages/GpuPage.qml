import QtQuick
import Creative
import ".."

// Grafikkarte – Daten der eingebauten Karte (live, solange die Seite offen ist) und ihre Beleuchtung.
SettingsPage {
    id: root
    readonly property var g: gpu.info
    function val(v, unit, digits) {
        if (v === undefined || v === null) return "–"
        return Number(v).toFixed(digits || 0).replace(".", ",") + (unit ? " " + unit : "")
    }
    readonly property string vendorName: g.vendor === "nvidia" ? "NVIDIA" : g.vendor === "amd" ? "AMD" : g.vendor === "intel" ? "Intel" : ""
    // Farbe des Abzeichens: dezent nach Hersteller (keine Markenlogos)
    readonly property color badgeColor: g.vendor === "nvidia" ? "#5fae3a" : g.vendor === "amd" ? "#e2453c" : g.vendor === "intel" ? "#3d8bfd" : Theme.accent

    PageHeader {
        title: "Grafikkarte"
        subtitle: "Daten deiner Grafikkarte und ihre Beleuchtung"
    }

    // Abzeichen mit Baureihe und Modell
    Card {
        Item {
            width: parent.width
            height: 150
            Rectangle {
                id: badge
                width: 250; height: 130; radius: 18
                anchors.verticalCenter: parent.verticalCenter
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.darker(root.badgeColor, Theme.light ? 1.0 : 1.6) }
                    GradientStop { position: 1; color: Theme.light ? Qt.lighter(root.badgeColor, 1.35) : "#12151b" }
                }
                border.color: Qt.rgba(root.badgeColor.r, root.badgeColor.g, root.badgeColor.b, 0.6)
                border.width: 2
                Rectangle { x: 12; y: 22; width: 6; height: parent.height - 44; radius: 3; color: root.badgeColor }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 26
                    spacing: 0
                    Text {
                        text: (gpu.badge[0] || root.vendorName || "Grafik").toUpperCase()
                        color: Theme.light ? "#12151b" : "#ffffff"
                        opacity: 0.8
                        font.family: Theme.fontFamily; font.pixelSize: 15; font.bold: true; font.letterSpacing: 2
                    }
                    Text {
                        text: gpu.badge[1] || "–"
                        color: Theme.light ? "#12151b" : "#ffffff"
                        font.family: Theme.fontFamily; font.pixelSize: 44; font.bold: true
                    }
                }
            }
            Column {
                x: badge.width + 24
                width: parent.width - x
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Text {
                    width: parent.width
                    text: root.g.name || "Grafikkarte wird gelesen …"
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: [root.g.vramMb ? Math.round(root.g.vramMb / 1024) + " GB Grafikspeicher" : "",
                           root.g.driver ? "Treiber " + root.g.driver : "", root.g.pcie || ""].filter(x => x).join("  ·  ")
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }
            }
        }
    }

    // Live-Werte als Kacheln
    Card {
        title: "Gerade jetzt"
        subtitle: "Wird alle 2 Sekunden aktualisiert, solange diese Seite offen ist"
        Flow {
            width: parent.width
            spacing: 10
            bottomPadding: 8
            Repeater {
                model: [
                    { t: "Auslastung", v: root.val(root.g.load, "%"), p: root.g.load },
                    { t: "Temperatur", v: root.val(root.g.temp, "°C"), p: root.g.temp },
                    { t: "Grafikspeicher belegt", v: root.g.vramUsedMb !== undefined && root.g.vramUsedMb !== null && root.g.vramMb
                          ? root.val(root.g.vramUsedMb / 1024, "GB", 1) + " von " + root.val(root.g.vramMb / 1024, "GB", 0) : "–",
                      p: root.g.vramMb ? 100 * (root.g.vramUsedMb || 0) / root.g.vramMb : undefined },
                    { t: "Leistung", v: root.g.power !== undefined && root.g.power !== null
                          ? root.val(root.g.power, "W") + (root.g.powerLimit ? " von " + root.val(root.g.powerLimit, "W") : "") : "–",
                      p: root.g.powerLimit ? 100 * (root.g.power || 0) / root.g.powerLimit : undefined },
                    { t: "Takt", v: root.val(root.g.clock, "MHz") + (root.g.clockMax ? " (max. " + root.val(root.g.clockMax, "MHz") + ")" : ""),
                      p: root.g.clockMax ? 100 * (root.g.clock || 0) / root.g.clockMax : undefined },
                    { t: "Lüfter", v: root.val(root.g.fan, "%"), p: root.g.fan }
                ]
                delegate: Rectangle {
                    required property var modelData
                    width: (parent.width - 20) / 3
                    height: 84
                    radius: 12
                    color: Theme.tint(0.04)
                    border.color: Theme.hairline
                    Column {
                        x: 14; y: 12
                        width: parent.width - 28
                        spacing: 4
                        Text { text: modelData.t; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                        Text { text: modelData.v; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true; elide: Text.ElideRight; width: parent.width }
                        Rectangle {
                            visible: modelData.p !== undefined && modelData.p !== null
                            width: parent.width; height: 5; radius: 3
                            color: Theme.tint(0.08)
                            Rectangle {
                                width: parent.width * Math.max(0, Math.min(1, (modelData.p || 0) / 100))
                                height: parent.height; radius: 3
                                color: modelData.t === "Temperatur" && (modelData.p || 0) > 80 ? "#e5484d" : Theme.accent
                                Behavior on width { NumberAnimation { duration: 300 } }
                            }
                        }
                    }
                }
            }
        }
    }

    Card {
        title: "Beleuchtung"
        subtitle: gpu.lightAvailable ? gpu.lightName : "Farbe und Effekt der Grafikkarte"
        Text {
            visible: gpu.lightNote !== ""
            width: parent.width
            text: gpu.lightNote
            wrapMode: Text.WordWrap
            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
            bottomPadding: 8
        }
        SettingRow {
            visible: gpu.lightAvailable
            label: "Effekt"
            Row {
                spacing: 6
                Repeater {
                    model: gpu.modes
                    delegate: CButton {
                        required property var modelData
                        text: modelData.label
                        primary: gpu.mode === modelData.key
                        enabled: !gpu.busy
                        onClicked: gpu.setMode(modelData.key)
                    }
                }
            }
        }
        SettingRow {
            visible: gpu.lightAvailable
            last: true
            label: "Farbe"
            hint: "Wird gespeichert und beim Anmelden wieder gesetzt"
            Row {
                spacing: 8
                Repeater {
                    model: gpu.colors
                    delegate: Rectangle {
                        required property var modelData
                        width: 30; height: 30; radius: 15
                        color: modelData
                        border.color: gpu.color === modelData ? Theme.text : Theme.hairline
                        border.width: gpu.color === modelData ? 3 : 1
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !gpu.busy; onClicked: gpu.setColor(modelData) }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Farbe " + modelData
                    }
                }
            }
        }
        CButton {
            visible: gpu.lightReady && !gpu.lightAvailable
            text: "Erneut suchen"
            onClicked: gpu.scanLight()
        }
    }

    Card {
        title: "Details"
        SettingRow { label: "Hersteller"; Text { text: root.vendorName || "–"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 } }
        SettingRow { label: "Treiber"; Text { text: root.g.driver || "–"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 } }
        SettingRow { label: "Speichertakt"; Text { text: root.val(root.g.memClock, "MHz"); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 } }
        SettingRow { label: "Anbindung"; Text { text: root.g.pcie || "–"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 } }
        SettingRow { label: "Grafik-BIOS"; last: true; Text { text: root.g.bios || "–"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 } }
    }

    onVisibleChanged: gpu.setActive(visible)
    Component.onCompleted: gpu.setActive(visible)
    Component.onDestruction: gpu.setActive(false)
}
