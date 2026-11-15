// Vorschau „Creative Abstand“: Hintergrund und Taskleiste als Layer-Shell-Flächen (wie die echte Shell),
// dazu ein App-Fenster, das maximiert wird.
import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

Item {
    property url wallpaper
    property url iconDir

    Window {
        id: bg
        visible: true
        color: "#12151b"
        LayerShell.Window.scope: "vorschau-hintergrund"
        LayerShell.Window.layer: LayerShell.Window.LayerBackground
        LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
        LayerShell.Window.exclusionZone: -1
        Image { anchors.fill: parent; source: wallpaper; fillMode: Image.PreserveAspectCrop }
    }

    Window {
        id: bar
        visible: true
        height: 56
        color: "transparent"
        LayerShell.Window.scope: "vorschau-taskleiste"
        LayerShell.Window.layer: LayerShell.Window.LayerTop
        LayerShell.Window.anchors: LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight | LayerShell.Window.AnchorBottom
        LayerShell.Window.exclusionZone: 56
        Rectangle {
            anchors.fill: parent
            color: "#1c2029"
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: "#14ffffff" }
            Row {
                anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Repeater {
                    model: ["rocket", "files", "browser", "whatsapp", "discord", "games", "terminal", "settings"]
                    delegate: Rectangle {
                        required property string modelData
                        required property int index
                        width: 44; height: 44; radius: 10
                        color: index === 1 ? "#12ffffff" : "transparent"
                        Image { anchors.centerIn: parent; width: 22; height: 22; sourceSize: Qt.size(44, 44); source: iconDir + "/" + modelData + ".svg" }
                        Rectangle { visible: index === 1 || index === 3; anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.bottom; anchors.topMargin: -3
                                    width: index === 1 ? 18 : 6; height: 3; radius: 2; color: index === 1 ? "#8fb3ff" : "#dce6ff" }
                        Rectangle { visible: index === 3; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 1
                                    width: 17; height: 17; radius: 9; color: "#8fb3ff"; border.color: "#12151b"; border.width: 2
                                    Text { anchors.centerIn: parent; text: "3"; color: "#12151b"; font.pixelSize: 10; font.bold: true } }
                    }
                }
            }
            Text { anchors.right: parent.right; anchors.rightMargin: 18; anchors.verticalCenter: parent.verticalCenter
                   text: "06:30\n15.11.2026"; color: "#dce6ff"; font.pixelSize: 12; horizontalAlignment: Text.AlignRight; font.family: "Liberation Sans" }
        }
    }
}
