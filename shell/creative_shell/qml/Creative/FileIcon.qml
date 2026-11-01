import QtQuick
import Creative

// Einheitliches Symbol für Ordner und Dateien (Farbe je Dateiart) – für Schreibtisch und Apps.
Item {
    id: g
    property bool isDir: false
    property color tint: Theme.accent
    property string ext: ""
    property int size: 20

    width: size
    height: size

    // Ordner: Reiter + Mappe
    Rectangle {
        visible: g.isDir
        x: 0; y: g.size * 0.12
        width: g.size * 0.46; height: g.size * 0.3
        radius: Math.max(2, g.size * 0.08)
        color: Qt.darker(g.tint, 1.3)
    }
    Rectangle {
        visible: g.isDir
        y: g.size * 0.22
        width: g.size; height: g.size * 0.66
        radius: Math.max(3, g.size * 0.14)
        color: g.tint
    }

    // Datei: Blatt mit Endung
    Rectangle {
        visible: !g.isDir
        anchors.horizontalCenter: parent.horizontalCenter
        y: g.size >= 32 ? 0 : g.size * 0.1
        width: g.size >= 32 ? g.size * 0.78 : g.size
        height: g.size >= 32 ? g.size : g.size * 0.8
        radius: Math.max(3, g.size * 0.14)
        color: g.tint

        Text {
            visible: g.size >= 32 && g.ext.length > 0
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: g.size * 0.12
            text: g.ext
            color: Theme.accentText
            font.family: Theme.fontFamily
            font.pixelSize: Math.round(g.size * 0.2)
            font.bold: true
        }
    }
}
