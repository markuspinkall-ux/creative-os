import QtQuick
import QtQuick.Controls.Basic
import Creative

Popup {
    id: dlg
    property string title
    property string message
    property string okText: "OK"
    property var action: null

    function ask(t, m, ok, fn) {
        title = t; message = m; okText = ok; action = fn
        open()
    }

    anchors.centerIn: Overlay.overlay
    width: 440
    modal: true
    focus: true
    padding: 22
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }
    background: Rectangle { radius: 16; color: Theme.raised; border.color: Theme.hairline }

    contentItem: Column {
        spacing: 14
        Text { text: dlg.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 17; font.bold: true }
        Text {
            text: dlg.message
            width: parent.width
            wrapMode: Text.Wrap
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            lineHeight: 1.3
        }
        Row {
            anchors.right: parent.right
            spacing: 8
            CButton { text: "Abbrechen"; onClicked: dlg.close() }
            CButton { text: dlg.okText; primary: true; onClicked: { dlg.close(); if (dlg.action) dlg.action() } }
        }
    }
}
