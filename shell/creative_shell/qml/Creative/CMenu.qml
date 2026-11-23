import QtQuick
import QtQuick.Controls.Basic as T
import Creative

// Rechtsklick-Menü im Gibeon-Look (statt des schwarzen Standardmenüs von Qt).
// Einträge: CMenuItem, Trennlinie: CMenuSeparator. Untermenüs: CMenu im CMenu.
T.Menu {
    id: menu
    padding: 6
    margins: 8
    overlap: 4
    implicitWidth: Math.max(220, contentItem.implicitWidth + leftPadding + rightPadding)
    delegate: CMenuItem {}
    background: Rectangle {
        implicitWidth: 220
        radius: 12
        color: Theme.raised
        border.color: Theme.hairline
    }
    contentItem: ListView {
        implicitHeight: contentHeight
        implicitWidth: {
            let w = 0
            for (let i = 0; i < count; i++) {
                const it = menu.itemAt(i)
                if (it && it.visible) w = Math.max(w, it.implicitWidth)
            }
            return w
        }
        model: menu.contentModel
        interactive: Window.window ? contentHeight + menu.topPadding + menu.bottomPadding > menu.height : false
        clip: true
        currentIndex: menu.currentIndex
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110 } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 80 } }
}
