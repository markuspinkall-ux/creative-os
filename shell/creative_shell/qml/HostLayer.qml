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
    property string placement: "bar"   // bar | top | left | right | topleft | topright | background
    property string popupKey: ""        // start | panel | trash
    property int surfaceWidth: 400
    property int surfaceHeight: 52
    property bool wantsKeyboard: false

    width: surfaceWidth
    height: surfaceHeight
    visible: false
    color: "transparent"
    // Der Name über einem Taskleisten-Symbol darf keine Klicks abfangen
    flags: popupKey === "tasktip" ? (Qt.Window | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus) : Qt.Window
    title: placement === "bar" ? "Taskleiste" : (placement === "top" ? "Obere Leiste" : (placement === "background" ? "Hintergrund" : "Menü"))

    readonly property bool isBar: placement === "bar" || placement === "top"
    readonly property bool isTop: placement === "top" || placement === "topleft" || placement === "topright"
    readonly property bool isBackground: placement === "background"

    LayerShell.Window.scope: placement === "top" ? "creative-topbar" : isBar ? "creative-taskbar" : (isBackground ? "creative-wallpaper" : "creative-popup")
    LayerShell.Window.layer: isBackground ? LayerShell.Window.LayerBackground
                           : (isBar ? LayerShell.Window.LayerTop : LayerShell.Window.LayerOverlay)
    LayerShell.Window.anchors: isBackground
        ? (LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight)
        : isBar
            ? (LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
               | (isTop ? LayerShell.Window.AnchorTop : LayerShell.Window.AnchorBottom))
            : (placement === "left" || placement === "topleft"
                ? (LayerShell.Window.AnchorLeft | (isTop ? LayerShell.Window.AnchorTop : LayerShell.Window.AnchorBottom))
                : (LayerShell.Window.AnchorRight | (isTop ? LayerShell.Window.AnchorTop : LayerShell.Window.AnchorBottom)))
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
        if (visible && !isBar && placement !== "background" && popupKey !== "bubble" && popupKey !== "tasktip") {
            requestActivate()
            if (loader.item && loader.item.opened)
                loader.item.opened()
        }
    }
    onActiveChanged: {
        if (!active && visible && !isBar && placement !== "background" && popupKey !== "bubble" && popupKey !== "tasktip")
            shell.popupLostFocus(screenName, popupKey || placement)
    }
}
