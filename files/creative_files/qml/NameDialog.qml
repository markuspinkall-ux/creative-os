import QtQuick
import QtQuick.Controls.Basic
import Creative

// Fragt nach einem Namen (Neuer Ordner, Umbenennen …).
// accept(name) muss "" (ok) oder eine Fehlermeldung zurückgeben.
Popup {
    id: dlg
    property string title
    property string okText: "OK"
    property var accept: function (name) { return "" }

    function ask(t, ok, initial, fn) {
        title = t
        okText = ok
        accept = fn
        error.text = ""
        field.text = initial
        open()
        field.forceActiveFocus()
        const dot = initial.lastIndexOf(".")
        field.select(0, dot > 0 ? dot : initial.length)
    }

    function submit() {
        const err = accept(field.text)
        if (err && err.length)
            error.text = err
        else
            close()
    }

    anchors.centerIn: Overlay.overlay
    width: 420
    modal: true
    focus: true
    padding: 22
    closePolicy: Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }

    background: Rectangle { radius: 16; color: Theme.raised; border.color: Theme.hairline }

    contentItem: Column {
        spacing: 14
        Text {
            text: dlg.title
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 17
            font.bold: true
        }
        TextField {
            id: field
            width: parent.width
            height: 40
            leftPadding: 12
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.accentText
            font.family: Theme.fontFamily
            font.pixelSize: 14
            background: Rectangle {
                radius: 10
                color: Theme.ground
                border.color: field.activeFocus ? Theme.accent : Theme.hairline
            }
            onAccepted: dlg.submit()
        }
        Text {
            id: error
            visible: text.length > 0
            width: parent.width
            wrapMode: Text.Wrap
            color: Theme.flame
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
        Row {
            anchors.right: parent.right
            spacing: 8
            CButton { text: "Abbrechen"; onClicked: dlg.close() }
            CButton { text: dlg.okText; primary: true; onClicked: dlg.submit() }
        }
    }
}
