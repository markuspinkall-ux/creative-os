import QtQuick
import Creative
import ".."

SettingsPage {
    PageHeader {
        title: "Darstellung"
        subtitle: "Hintergrundbild, Musik-Visualizer, Leistungsanzeige"
        CButton { text: "Aktualisieren"; onClicked: look.refresh() }
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
                    border.color: current ? Theme.accent : (tm.containsMouse ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(1, 1, 1, 0.08))
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
}
