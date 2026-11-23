import QtQuick
import QtWebEngine
import Creative

// Rechtsklick in Webansichten (Chat, YouTube Music …) im Gibeon-Look statt des schwarzen Standardmenüs.
// WebEngineView { onContextMenuRequested: (r) => webMenu.show(r) }   CWebMenu { id: webMenu; view: … }
CMenu {
    id: menu
    property var view: null
    property string link: ""
    property string sel: ""
    property bool editable: false

    function show(request) {
        request.accepted = true
        link = request.linkUrl ? request.linkUrl.toString() : ""
        sel = request.selectedText || ""
        editable = !!request.isContentEditable
        popup()
    }
    function act(a) { if (view) view.triggerWebAction(a) }

    CMenuItem { text: "Zurück"; visible: !menu.editable && !menu.sel; enabled: !!menu.view && menu.view.canGoBack; onTriggered: menu.act(WebEngineView.Back) }
    CMenuItem { text: "Neu laden"; visible: !menu.editable && !menu.sel; onTriggered: menu.act(WebEngineView.Reload) }
    CMenuItem { text: "Link kopieren"; visible: menu.link !== ""; onTriggered: menu.act(WebEngineView.CopyLinkToClipboard) }
    CMenuItem { text: "Ausschneiden"; visible: menu.editable; enabled: menu.sel !== ""; onTriggered: menu.act(WebEngineView.Cut) }
    CMenuItem { text: "Kopieren"; visible: menu.sel !== "" || menu.editable; enabled: menu.sel !== ""; onTriggered: menu.act(WebEngineView.Copy) }
    CMenuItem { text: "Einfügen"; visible: menu.editable; onTriggered: menu.act(WebEngineView.Paste) }
    CMenuSeparator {}
    CMenuItem { text: "Alles markieren"; onTriggered: menu.act(WebEngineView.SelectAll) }
}
