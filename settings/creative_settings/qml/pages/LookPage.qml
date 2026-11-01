import QtQuick
import Creative
import ".."

SettingsPage {
    PageHeader {
        title: "Darstellung"
        subtitle: "Hintergrundbild für alle Bildschirme"
        CButton { text: "Aktualisieren"; onClicked: look.refresh() }
    }

    Card {
        title: "Hintergrundbild"
        subtitle: "Eigene Bilder: einfach in den Ordner „Bilder“ legen – sie erscheinen hier."
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
}
