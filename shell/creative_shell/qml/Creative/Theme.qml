pragma Singleton
import QtQuick

// Graphit-Design von Creative OS – alle Farben und Maße an einer Stelle.
QtObject {
    // Flächen
    readonly property color ground: "#12151b"
    readonly property color surface: "#1c2029"
    readonly property color footer: "#171a22"
    readonly property color raised: "#232836"
    readonly property color bar: Qt.rgba(26 / 255, 30 / 255, 38 / 255, 0.94)
    readonly property color track: "#3a4252"

    // Schrift: eine einheitliche Farbe, weiß-blau
    readonly property color text: "#dce6ff"
    readonly property color textMuted: Qt.rgba(220 / 255, 230 / 255, 255 / 255, 0.6)

    // Akzente
    readonly property color accent: "#8fb3ff"
    readonly property color accentText: "#12151b"
    readonly property color flame: "#ffb07a"
    readonly property color ok: "#6fdcc0"

    // Zustände
    readonly property color hairline: Qt.rgba(1, 1, 1, 0.08)
    readonly property color hover: Qt.rgba(1, 1, 1, 0.07)
    readonly property color pressed: Qt.rgba(1, 1, 1, 0.12)
    readonly property color subtle: Qt.rgba(1, 1, 1, 0.04)

    // Schrift (auf Fedora liefert "Liberation Sans" die Arial-Maße)
    readonly property string fontFamily: "Arial"

    // Rundungen
    readonly property int radiusBar: 18
    readonly property int radiusMenu: 18
    readonly property int radiusButton: 12
    readonly property int radiusRow: 10
}
