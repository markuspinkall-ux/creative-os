// Beispiel-App (wie „Dateien“) – wird maximiert
import QtQuick
import QtQuick.Window

Window {
    id: w
    title: "Dateien – Bilder"
    width: 900; height: 560
    visible: true
    color: "#12151b"
    Rectangle {
        id: side
        width: 220; height: parent.height; color: "#171a22"
        Column {
            x: 14; y: 16; spacing: 4
            Repeater {
                model: ["Schreibtisch", "Dokumente", "Bilder", "Musik", "Videos", "Downloads", "Papierkorb"]
                delegate: Rectangle {
                    required property string modelData
                    width: 192; height: 36; radius: 9
                    color: modelData === "Bilder" ? "#2e8fb3ff" : "transparent"
                    Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: modelData; color: "#dce6ff"; font.pixelSize: 14; font.family: "Liberation Sans" }
                }
            }
        }
    }
    Text { x: side.width + 28; y: 22; text: "Bilder"; color: "#dce6ff"; font.pixelSize: 22; font.bold: true; font.family: "Liberation Sans" }
    Grid {
        x: side.width + 28; y: 70; columns: Math.max(1, Math.floor((w.width - side.width - 40) / 176)); spacing: 16
        Repeater {
            model: 18
            delegate: Rectangle {
                required property int index
                width: 160; height: 120; radius: 12
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.hsla((index * 0.13) % 1, 0.45, 0.42, 1) }
                    GradientStop { position: 1; color: Qt.hsla((index * 0.13 + 0.08) % 1, 0.5, 0.25, 1) }
                }
                Text { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.margins: 8; text: "Foto " + (index + 1) + ".jpg"; color: "white"; font.pixelSize: 12; font.family: "Liberation Sans" }
            }
        }
    }
}
