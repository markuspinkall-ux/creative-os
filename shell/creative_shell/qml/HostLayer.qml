// Fenster-Hülle für Wayland: Die Taskleiste und die Menüs werden als
// "Layer-Shell"-Flächen angelegt. Damit sitzen sie fest am Bildschirmrand,
// liegen über normalen Fenstern und reservieren Platz, sodass maximierte
// Fenster die Taskleiste nicht verdecken.
import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

Window {
    id: host

    property url contentSource
    property string screenName
    property string placement: "bar"   // bar | left | right | background
    property string popupKey: ""        // start | panel | trash
    property int surfaceWidth: 400
    property int surfaceHeight: 74
    property bool wantsKeyboard: false

    width: surfaceWidth
    height: surfaceHeight
    visible: false
    color: "transparent"
    title: placement === "bar" ? "Creative Taskleiste" : (placement === "background" ? "Creative Hintergrund" : "Creative Menü")

    readonly property bool isBar: placement === "bar"
    readonly property bool isBackground: placement === "background"

    LayerShell.Window.scope: isBar ? "creative-taskbar" : (isBackground ? "creative-wallpaper" : "creative-popup")
    LayerShell.Window.layer: isBackground ? LayerShell.Window.LayerBackground
                           : (isBar ? LayerShell.Window.LayerTop : LayerShell.Window.LayerOverlay)
    LayerShell.Window.anchors: isBackground
        ? (LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight)
        : isBar
            ? (LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight | LayerShell.Window.AnchorBottom)
            : (placement === "left"
                ? (LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorBottom)
                : (LayerShell.Window.AnchorRight | LayerShell.Window.AnchorBottom))
    // Leiste reserviert ihre Höhe; Menüs (0) setzen sich darüber;
    // das Hintergrundbild (-1) füllt den ganzen Bildschirm.
    LayerShell.Window.exclusionZone: isBar ? surfaceHeight : (isBackground ? -1 : 0)
    LayerShell.Window.keyboardInteractivity: wantsKeyboard
        ? LayerShell.Window.KeyboardInteractivityOnDemand
        : LayerShell.Window.KeyboardInteractivityNone

    Loader {
        id: loader
        anchors.fill: parent
        focus: true
    }

    Component.onCompleted: loader.setSource(contentSource, { screenName: screenName })

    onVisibleChanged: {
        if (visible && placement !== "bar" && placement !== "background") {
            requestActivate()
            if (loader.item && loader.item.opened)
                loader.item.opened()
        }
    }
    onActiveChanged: {
        if (!active && visible && placement !== "bar" && placement !== "background")
            shell.popupLostFocus(screenName, popupKey || placement)
    }
}
