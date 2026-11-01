import QtQuick
import Creative

// Abschnitt einer Einstellungsseite mit Überschrift.
Rectangle {
    id: card
    property string title
    property string subtitle
    default property alias content: inner.data

    width: parent ? parent.width : 600
    implicitHeight: inner.implicitHeight + (title.length ? 58 : 36)
    radius: 16
    color: Qt.rgba(1, 1, 1, 0.03)

    Column {
        x: 18
        y: 16
        spacing: 2
        visible: card.title.length > 0
        Text { text: card.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
        Text {
            visible: card.subtitle.length > 0
            text: card.subtitle
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 12
        }
    }
    Column {
        id: inner
        x: 18
        y: card.title.length ? (card.subtitle.length ? 58 : 44) : 18
        width: card.width - 36
        spacing: 0
    }
}
