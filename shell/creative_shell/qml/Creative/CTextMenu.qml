import QtQuick
import QtQuick.Controls.Basic as T
import Creative

// Rechtsklick in Textfeldern (Ausschneiden, Kopieren, Einfügen …) im Gibeon-Look.
// Verwendung: TextField { ContextMenu.menu: CTextMenu {} } – das Feld ist das Elternelement.
CMenu {
    id: menu
    property Item field: null
    readonly property Item f: field || parent
    readonly property bool editable: !!f && !f.readOnly
    readonly property bool hasSel: !!f && f.selectedText !== undefined && f.selectedText.length > 0
    CMenuItem { text: "Rückgängig"; visible: menu.editable; enabled: !!menu.f && menu.f.canUndo; onTriggered: menu.f.undo() }
    CMenuItem { text: "Wiederholen"; visible: menu.editable; enabled: !!menu.f && menu.f.canRedo; onTriggered: menu.f.redo() }
    CMenuSeparator { visible: menu.editable; height: visible ? implicitHeight : 0 }
    CMenuItem { text: "Ausschneiden"; visible: menu.editable; enabled: menu.hasSel && (!menu.f.echoMode || menu.f.echoMode === TextInput.Normal); onTriggered: menu.f.cut() }
    CMenuItem { text: "Kopieren"; enabled: menu.hasSel && (!menu.f.echoMode || menu.f.echoMode === TextInput.Normal); onTriggered: menu.f.copy() }
    CMenuItem { text: "Einfügen"; visible: menu.editable; enabled: !!menu.f && menu.f.canPaste; onTriggered: menu.f.paste() }
    CMenuItem { text: "Löschen"; visible: menu.editable; enabled: menu.hasSel; onTriggered: menu.f.remove(menu.f.selectionStart, menu.f.selectionEnd) }
    CMenuSeparator {}
    CMenuItem { text: "Alles markieren"; enabled: !!menu.f && menu.f.length > 0; onTriggered: menu.f.selectAll() }
}
