// Fenster-Hülle für den Testmodus (--dev) oder X11: normale rahmenlose
// Fenster, die Python an die richtige Stelle setzt.
import QtQuick
import QtQuick.Window

Window {
    id: host

    property url contentSource
    property string screenName
    property string placement: "bar"
    property string popupKey: ""        // start | panel | trash
    property int surfaceWidth: 400
    property int surfaceHeight: 74
    property bool wantsKeyboard: false

    width: surfaceWidth
    height: surfaceHeight
    visible: false
    color: "transparent"
    title: placement === "bar" ? "Creative Taskleiste" : "Creative Menü"
    flags: placement === "bar"
        ? (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        : (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

    Loader {
        id: loader
        anchors.fill: parent
        focus: true
    }

    Component.onCompleted: loader.setSource(contentSource, { screenName: screenName })

    onVisibleChanged: {
        if (visible && placement !== "bar" && popupKey !== "bubble") {
            requestActivate()
            if (loader.item && loader.item.opened)
                loader.item.opened()
        }
    }
    onActiveChanged: {
        if (!active && visible && placement !== "bar" && popupKey !== "bubble")
            shell.popupLostFocus(screenName, popupKey || placement)
    }
}
