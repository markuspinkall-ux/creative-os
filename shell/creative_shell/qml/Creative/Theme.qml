pragma Singleton
import QtQuick
import QtCore

// Design von Creative OS – alle Farben und Maße an einer Stelle.
// „Graphit“ (dunkel) oder „Porzellan“ (hell), dazu eine Akzentfarbe.
// Gewählt wird in den Einstellungen → Darstellung (Datei ~/.config/creative-os/look.conf).
QtObject {
    id: theme

    property Settings look: Settings {
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/creative-os/look.conf"
        category: "Look"
        property string design: "graphit"
        property string accent: "blau"
    }
    readonly property bool light: look.design === "porzellan"
    readonly property string accentName: ["blau", "gruen", "orange", "lila"].indexOf(look.accent) >= 0 ? look.accent : "blau"

    // Flächen
    readonly property color ground: light ? "#e9eef6" : "#12151b"
    readonly property color surface: light ? "#ffffff" : "#1c2029"
    readonly property color footer: light ? "#f4f6fa" : "#171a22"
    readonly property color raised: light ? "#eef1f6" : "#232836"
    readonly property color bar: light ? Qt.rgba(1, 1, 1, 0.86) : Qt.rgba(26 / 255, 30 / 255, 38 / 255, 0.94)
    readonly property color track: light ? "#cdd5e2" : "#3a4252"

    // Schrift: eine einheitliche Farbe (Graphit: weiß-blau, Porzellan: dunkles Blaugrau)
    readonly property color text: light ? "#1c2433" : "#dce6ff"
    readonly property color textMuted: light ? Qt.rgba(28 / 255, 36 / 255, 51 / 255, 0.62)
                                             : Qt.rgba(220 / 255, 230 / 255, 255 / 255, 0.6)

    // Akzente
    readonly property var accents: ({
        "blau":   { dark: "#8fb3ff", light: "#3d6fe0" },
        "gruen":  { dark: "#6fdcc0", light: "#1f9e7f" },
        "orange": { dark: "#ffb07a", light: "#d9773a" },
        "lila":   { dark: "#c3a6ff", light: "#7c4ddb" }
    })
    readonly property color accent: light ? accents[accentName].light : accents[accentName].dark
    readonly property color accentText: light ? "#ffffff" : "#12151b"
    readonly property color flame: light ? "#d9773a" : "#ffb07a"
    readonly property color ok: light ? "#1f9e7f" : "#6fdcc0"

    // Zustände: auf Graphit helle, auf Porzellan dunkle Schleier
    function tint(alpha) { return light ? Qt.rgba(20 / 255, 30 / 255, 50 / 255, alpha * 0.9) : Qt.rgba(1, 1, 1, alpha) }
    readonly property color hairline: tint(0.08)
    readonly property color hover: tint(0.07)
    readonly property color pressed: tint(0.12)
    readonly property color subtle: tint(0.04)

    // Symbole: hell auf Graphit, dunkel auf Porzellan
    readonly property string iconDir: light ? "icons-light/" : "icons/"

    // Schrift (unter Linux liefert "Liberation Sans" die Arial-Maße)
    readonly property string fontFamily: "Arial"

    // Rundungen
    readonly property int radiusBar: 18
    readonly property int radiusMenu: 18
    readonly property int radiusButton: 12
    readonly property int radiusRow: 10
}
