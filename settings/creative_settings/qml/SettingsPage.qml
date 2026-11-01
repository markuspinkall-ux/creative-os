import QtQuick
import QtQuick.Controls.Basic
import Creative

// Rahmen jeder Seite: Inhalt (beginnend mit PageHeader) scrollbar.
Flickable {
    id: page
    default property alias content: body.data

    contentHeight: body.implicitHeight + 60
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}

    Column {
        id: body
        x: 32
        y: 26
        width: page.width - 64
        spacing: 18
    }
}
