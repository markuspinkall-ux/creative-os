import QtQuick
import QtQuick.Window
import Creative

// Kleine Leiste während der Video-Aufnahme: roter Punkt, Laufzeit, Ton an/aus und „Stopp“.
// Lässt sich an der freien Fläche verschieben.
Window {
    id: bar

    width: row.implicitWidth + 24
    height: 52
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    title: "Shots – Aufnahme"
    visible: shots.recording

    function clock(s) {
        const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, sec = s % 60
        const two = n => (n < 10 ? "0" : "") + n
        return (h > 0 ? h + ":" : "") + two(m) + ":" + two(sec)
    }

    Rectangle {
        anchors.fill: parent
        radius: 16
        color: Theme.raised
        border.color: Theme.hairline

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.SizeAllCursor
            onPressed: bar.startSystemMove()
        }

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 10

            // pulsierender Punkt
            Rectangle {
                id: dot
                anchors.verticalCenter: parent.verticalCenter
                width: 12; height: 12; radius: 6
                color: shots.recordState === "recording" ? "#ff4d5e" : Theme.textMuted
                SequentialAnimation on opacity {
                    running: shots.recordState === "recording"
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 700 }
                    NumberAnimation { to: 1; duration: 700 }
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(implicitWidth, 64)
                text: shots.recordState === "starting" ? "Bildschirm wählen …"
                      : shots.recordState === "stopping" ? "Wird gespeichert …"
                      : bar.clock(shots.recordSeconds)
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.bold: true
            }
            Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }
            // Stopp
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: stopRow.implicitWidth + 24
                height: 36
                radius: 12
                enabled: shots.recordState !== "stopping"
                opacity: enabled ? 1 : 0.5
                color: sm.pressed ? "#c23646" : (sm.containsMouse ? "#f05565" : "#e04656")
                Row {
                    id: stopRow
                    anchors.centerIn: parent
                    spacing: 8
                    Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 11; height: 11; radius: 2; color: "white" }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: shots.recordState === "starting" ? "Abbrechen" : "Stopp"
                        color: "white"
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                }
                MouseArea { id: sm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: shots.stopRecording() }
                Accessible.role: Accessible.Button
                Accessible.name: "Aufnahme beenden"
                Accessible.onPressAction: shots.stopRecording()
            }
        }
    }
}
