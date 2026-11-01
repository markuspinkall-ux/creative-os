import QtQuick
import QtQuick.Controls.Basic
import Creative

Popup {
    id: dlg
    property var info: ({})

    anchors.centerIn: Overlay.overlay
    width: 420
    modal: true
    focus: true
    padding: 22
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }
    background: Rectangle { radius: 16; color: Theme.raised; border.color: Theme.hairline }

    contentItem: Column {
        spacing: 18
        Row {
            spacing: 14
            FileGlyph {
                size: 44
                isDir: !!dlg.info.isDir
                tint: dlg.info.tint || Theme.accent
                ext: dlg.info.ext || ""
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                width: 300
                anchors.verticalCenter: parent.verticalCenter
                text: dlg.info.name || ""
                elide: Text.ElideMiddle
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 17
                font.bold: true
            }
        }
        Column {
            spacing: 10
            width: parent.width
            Repeater {
                model: [
                    ["Art", dlg.info.type], ["Ort", dlg.info.location],
                    ["Größe", dlg.info.size], ["Geändert", dlg.info.changed]
                ].filter(r => r[1])
                delegate: Row {
                    spacing: 14
                    Text { width: 80; text: modelData[0]; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 }
                    Text {
                        width: 290
                        text: modelData[1]
                        wrapMode: Text.WrapAnywhere
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                }
            }
        }
        CButton { anchors.right: parent.right; text: "Schließen"; primary: true; onClicked: dlg.close() }
    }
}
