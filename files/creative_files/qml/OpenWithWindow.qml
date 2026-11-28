import QtQuick
import QtQuick.Controls.Basic
import Creative

// Eigenes Fenster für „Öffnen mit“ vom Schreibtisch: creative-files --open-with Datei …
ApplicationWindow {
    id: win
    width: 500
    height: 640
    minimumWidth: 420
    minimumHeight: 420
    visible: true
    title: "Öffnen mit"
    color: Theme.raised

    OpenWithPanel {
        id: panel
        anchors.fill: parent
        anchors.margins: 22
        chooser: openWith
        onFinished: Qt.quit()
        Component.onCompleted: load(openWithPaths)
    }

    Text {
        visible: !panel.info.ok
        anchors.centerIn: parent
        text: "Die Datei wurde nicht gefunden."
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 14
    }

    Shortcut { sequence: "Escape"; onActivated: Qt.quit() }
}
