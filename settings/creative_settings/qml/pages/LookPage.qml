import QtQuick
import Creative
import ".."

SettingsPage {
    PageHeader {
        title: "Darstellung"
        subtitle: "Design, Akzentfarbe, Hintergrundbild, Musik-Visualizer, Leistungsanzeige, Widgets"
        CButton { text: "Aktualisieren"; onClicked: look.refresh() }
    }

    Card {
        title: "Design"
        subtitle: "Gilt für Taskleiste, Startmenü, Einstellungen und alle Creative-Programme"
        Row {
            spacing: 14
            bottomPadding: 6
            Repeater {
                model: [
                    { id: "graphit", name: "Graphit", hint: "dunkel", ground: "#12151b", win: "#1c2029", bar: "#232836", line: "#2a303d" },
                    { id: "porzellan", name: "Porzellan", hint: "hell", ground: "#e9eef6", win: "#ffffff", bar: "#ffffff", line: "#d9dfe9" }
                ]
                delegate: Rectangle {
                    readonly property bool current: look.design === modelData.id
                    width: 220; height: 156; radius: 14
                    color: Theme.raised
                    border.color: current ? Theme.accent : (dm.containsMouse ? Theme.tint(0.25) : Theme.hairline)
                    border.width: current ? 3 : 1
                    Rectangle {
                        x: 10; y: 10; width: parent.width - 20; height: 100; radius: 10
                        color: modelData.ground
                        Rectangle { x: 14; y: 12; width: 110; height: 58; radius: 8; color: modelData.win; border.color: modelData.line }
                        Rectangle { x: 18; y: 18; width: 34; height: 8; radius: 4; color: Theme.accent }
                        Rectangle { x: 10; width: parent.width - 20; height: 14; radius: 7; anchors.bottom: parent.bottom; anchors.bottomMargin: 8; color: modelData.bar; border.color: modelData.line }
                    }
                    Text {
                        x: 14; anchors.bottom: parent.bottom; anchors.bottomMargin: 12
                        text: (parent.current ? "✓ " : "") + modelData.name + "  ·  " + modelData.hint
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: parent.current
                    }
                    MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: look.setDesign(modelData.id) }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Design " + modelData.name
                }
            }
        }
        SettingRow {
            label: "Akzentfarbe"
            hint: "Knöpfe, Auswahl, Schalter und Markierungen"
            last: true
            Row {
                spacing: 10
                Repeater {
                    model: [
                        { id: "blau", name: "Blau", dark: "#8fb3ff", light: "#3d6fe0" },
                        { id: "gruen", name: "Grün", dark: "#6fdcc0", light: "#1f9e7f" },
                        { id: "orange", name: "Orange", dark: "#ffb07a", light: "#d9773a" },
                        { id: "lila", name: "Lila", dark: "#c3a6ff", light: "#7c4ddb" }
                    ]
                    delegate: Rectangle {
                        readonly property bool current: look.accent === modelData.id
                        width: 30; height: 30; radius: 15
                        color: Theme.light ? modelData.light : modelData.dark
                        border.width: current ? 3 : 0
                        border.color: Theme.text
                        MouseArea { anchors.fill: parent; anchors.margins: -4; cursorShape: Qt.PointingHandCursor; onClicked: look.setAccent(modelData.id) }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Akzentfarbe " + modelData.name
                    }
                }
            }
        }
        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            topPadding: 6
            text: "Beim Umschalten lädt die Taskleiste kurz neu. Offene Programme übernehmen das Design beim nächsten Start."
            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
        }
    }

    Card {
        title: "Hintergrundbild"
        subtitle: "Eigene Bilder: direkt in den Ordner „Bilder“ legen – nur die erscheinen hier, Unterordner nicht."
        Flow {
            id: flow
            width: parent.width
            spacing: 12
            bottomPadding: 6
            Repeater {
                model: look.images
                delegate: Rectangle {
                    readonly property bool current: modelData.path === look.current
                    width: 200
                    height: 140
                    radius: 12
                    color: Theme.ground
                    border.color: current ? Theme.accent : (tm.containsMouse ? Theme.tint(0.25) : Theme.tint(0.08))
                    border.width: current ? 3 : 1
                    Image {
                        anchors.fill: parent
                        anchors.margins: 4
                        anchors.bottomMargin: 28
                        source: modelData.url
                        sourceSize.width: 400
                        sourceSize.height: 240
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        clip: true
                    }
                    Text {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 7
                        x: 10
                        width: parent.width - 20
                        elide: Text.ElideRight
                        text: (parent.current ? "✓ " : "") + modelData.label
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: parent.current
                    }
                    MouseArea { id: tm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: look.setWallpaper(modelData.path) }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Hintergrundbild " + modelData.label
                }
            }
        }
    }

    Card {
        title: "Musik-Visualizer"
        subtitle: "Balken hinter der Taskleiste, wenn Musik läuft"
        SettingRow {
            label: "Visualizer anzeigen"
            hint: "Aus = keine Balken und keine Messung im Hintergrund"
            CSwitch {
                checked: look.visualizer
                label: "Musik-Visualizer anzeigen"
                onToggled: (v) => look.setVisualizer(v)
            }
        }
        SettingRow {
            label: "Deckkraft"
            hint: "Wie kräftig die Balken zu sehen sind"
            last: true
            enabled: look.visualizer
            opacity: enabled ? 1 : 0.45
            Row {
                spacing: 12
                CSlider {
                    id: vizOpacity
                    anchors.verticalCenter: parent.verticalCenter
                    width: 220
                    from: 10; to: 100; stepSize: 5
                    value: Math.round(look.visualizerOpacity * 100)
                    onMoved: look.setVisualizerOpacity(value / 100)
                    Accessible.name: "Deckkraft des Visualizers"
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 44
                    text: Math.round(vizOpacity.value) + " %"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
        }
    }

    Card {
        title: "Gerade läuft"
        subtitle: "Interpret und Titel des laufenden Liedes mittig in der Taskleiste"
        SettingRow {
            label: "In der Taskleiste anzeigen"
            hint: "Gilt für den Creative Player, YouTube Music und andere Musikprogramme"
            last: true
            CSwitch {
                checked: look.nowPlaying
                label: "Interpret und Titel in der Taskleiste anzeigen"
                onToggled: (v) => look.setNowPlaying(v)
            }
        }
    }

    Card {
        title: "Leistungsanzeige"
        subtitle: "CPU, Arbeitsspeicher, Datenträger und Netzwerk oben rechts auf dem Schreibtisch"
        SettingRow {
            label: "Auf dem Schreibtisch anzeigen"
            last: true
            CSwitch {
                checked: look.desktopStats
                label: "Leistungsanzeige anzeigen"
                onToggled: (v) => look.setDesktopStats(v)
            }
        }
    }

    Card {
        title: "Widgets"
        subtitle: "Auf dem Schreibtisch – wie in Creative Widgets. Ort, Feeds und Kanäle stellst du am Widget selbst ein"
        Repeater {
            model: [
                { k: "shelf", t: "Ablage", h: "Dateien kurz zwischenlagern" },
                { k: "weather", t: "Wetter", h: "Wetter für deinen Ort (Daten: Open-Meteo)" },
                { k: "rss", t: "RSS-Nachrichten", h: "Schlagzeilen aus bis zu fünf Feeds" },
                { k: "ki", t: "KI-Helfer", h: "Lokale KI zum Fragen und Formulieren (Open Source)" },
                { k: "twitch", t: "Twitch-Favoriten", h: "Wer von deinen Kanälen gerade live ist" },
                { k: "clock", t: "Analoge Uhr", h: look.widgets.clockInstalled ? "Uhr mit Sekundenzeiger" : "Erst in Creative Widgets herunterladen" }
            ]
            delegate: SettingRow {
                required property var modelData
                label: modelData.t
                hint: modelData.h
                enabled: look.widgets.shell && (modelData.k !== "clock" || look.widgets.clockInstalled)
                opacity: enabled ? 1 : 0.45
                CSwitch {
                    checked: !!look.widgets[modelData.k]
                    label: modelData.t + " anzeigen"
                    onToggled: (v) => look.setGadget(modelData.k, v)
                }
            }
        }
        SettingRow {
            label: "Bildschirm und mehr"
            hint: look.widgets.shell ? "Auf welchem Monitor ein Widget erscheint, neue Widgets herunterladen"
                                     : "Der Schreibtisch ist gerade nicht erreichbar – Widgets lassen sich nach der Anmeldung schalten"
            last: true
            CButton { text: "Creative Widgets öffnen"; onClicked: look.openWidgets() }
        }
    }
}
