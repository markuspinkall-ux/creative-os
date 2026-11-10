import QtQuick
import QtQuick.Controls.Basic
import Creative

// Rückfrage im Creative-OS-Stil (statt Dialog mit Standardknöpfen).
//   ConfirmDialog { id: ask; title: "Löschen?"; text: "…"; confirmText: "Löschen"; danger: true
//                   onConfirmed: … }
//   ask.open()
Popup {
    id: dialog

    property string title: ""
    property string text: ""
    property string confirmText: "OK"
    property string cancelText: "Abbrechen"
    property bool danger: false
    signal confirmed()

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(440, parent ? parent.width - 40 : 440)
    modal: true
    focus: true
    padding: 24
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
    background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }

    contentItem: Column {
        spacing: 14
        Row {
            spacing: 12
            width: parent.width
            Rectangle {
                visible: dialog.danger
                width: 36; height: 36; radius: 18
                anchors.verticalCenter: parent.verticalCenter
                color: Qt.rgba(0.9, 0.28, 0.3, 0.16)
                Text {
                    anchors.centerIn: parent
                    text: "!"
                    color: "#ff6b70"
                    font.family: Theme.fontFamily
                    font.pixelSize: 20
                    font.bold: true
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - (dialog.danger ? 48 : 0)
                wrapMode: Text.WordWrap
                text: dialog.title
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.bold: true
            }
        }
        Text {
            visible: dialog.text.length > 0
            width: parent.width
            wrapMode: Text.WordWrap
            text: dialog.text
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 13
            lineHeight: 1.3
        }
        Item { width: 1; height: 4 }
        Row {
            anchors.right: parent.right
            spacing: 8
            CButton { text: dialog.cancelText; onClicked: dialog.close() }
            CButton {
                text: dialog.confirmText
                primary: !dialog.danger
                danger: dialog.danger
                onClicked: { dialog.close(); dialog.confirmed() }
            }
        }
    }
}
