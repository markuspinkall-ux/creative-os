import QtQuick
import QtQuick.Window
import Creative

// Obere Leiste (Fluid-Design): links der Tray – WLAN, Ton, Bluetooth, Tastatur und die
// Symbole anderer Programme –, in der Mitte „Gibeon OS“. Uhrzeit, Datum und Akku sitzen
// unten in der Taskleiste hinter dem Papierkorb. Klick links öffnet den Schnellzugriff.
Item {
    id: root

    property string screenName

    // ---- Einfahren bei maximiertem Fenster ------------------------------------------------
    // Ist auf diesem Monitor ein Fenster maximiert, reserviert die Leiste keinen Platz und fährt
    // nach oben weg. Nur ein schmaler Streifen am oberen Rand über dem Tray (links) nimmt dann die
    // Maus an: geht sie dorthin, fährt die Leiste herein; verlässt sie die Leiste, fährt sie wieder
    // ein. Rechts bleibt der obere Rand frei – dort liegen Minimieren, Maximieren und Schließen des
    // Fensters, die die Leiste sonst verdecken würde. Auch ausgefahren nimmt sie dann nur am Tray
    // die Maus an.
    readonly property bool autoHide: !!(Window.window && Window.window.autoHide)
    readonly property bool hovered: !!(Window.window && Window.window.hovered)
    readonly property bool menuOpen: shell.trayMenuOpenOn === root.screenName
                                     || shell.quickPanelOpenOn === root.screenName
    property bool peek: false
    readonly property bool shown: !autoHide || peek || menuOpen
    readonly property int edge: 3            // Streifen, der die Maus fängt
    property real shift: shown ? 0 : -height
    Behavior on shift { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    transform: Translate { y: root.shift }
    // Eingefahren ganz unsichtbar (kein stehengebliebener Rest oben links): erst ausblenden,
    // dann ganz abschalten, Weichzeichner sofort aus und neu zeichnen lassen.
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }
    visible: shown || opacity > 0.01
    onVisibleChanged: if (Window.window) Window.window.update()
    readonly property int trayRight: left.x + left.width + 24

    onHoveredChanged: {
        if (hovered) {
            leaveTimer.stop()
            peek = true
        } else {
            leaveTimer.restart()
        }
    }
    Timer { id: leaveTimer; interval: 500; onTriggered: root.peek = root.hovered }
    onAutoHideChanged: { if (!autoHide) peek = false; updateInput() }
    onShownChanged: {
        updateInput()
        if (!shown) shell.setBlur(Window.window, [])      // Glas sofort weg, nicht erst nach dem Einfahren
        blurTimer.restart()
    }
    Timer { id: blurTimer; interval: 240; onTriggered: root.updateBlur() }

    function updateInput() {
        if (!Window.window) return
        if (!autoHide)
            shell.setInputRect(Window.window, 0, 0, 0, 0)               // ganze Fläche
        else if (shown)
            shell.setInputRect(Window.window, 0, 0, trayRight, height)  // nur am Tray
        else
            shell.setInputRect(Window.window, 0, 0, trayRight, edge)    // Streifen oben überm Tray
    }

    // Fluid-Glas: nur unter den beiden Feldern weichzeichnen
    function updateBlur() {
        if (!shown) {
            shell.setBlur(Window.window, [])
            return
        }
        shell.setBlur(Window.window, [
            { x: left.x, y: left.y, w: left.width, h: left.height, r: 17 }
        ])
    }
    Component.onCompleted: Qt.callLater(updateBlur)
    onWidthChanged: { Qt.callLater(updateBlur); updateInput() }

    // Glas-Feld: durchscheinend, feine Kante, Lichtkante oben
    component Pill: Rectangle {
        property bool lit: false
        height: 34
        radius: 17
        readonly property color base: shell.blurAvailable ? Theme.glass : Theme.glassSolid
        color: lit ? Qt.rgba(base.r, base.g, base.b, Math.min(1, base.a + 0.18)) : base
        border.color: Theme.glassEdge
        border.width: 1
        Rectangle {
            x: parent.radius
            y: 1
            width: parent.width - 2 * parent.radius
            height: 1
            color: Theme.glassShine
        }
        GlassSheen { radius: parent.radius; streak: false }
    }

    // Klick auf freie Fläche schließt offene Menüs
    MouseArea {
        anchors.fill: parent
        onClicked: shell.closePopups()
    }

    // ---- links: Tray ----
    Pill {
        id: left
        x: 14
        y: 10
        width: leftRow.implicitWidth + 28
        onWidthChanged: { Qt.callLater(root.updateBlur); Qt.callLater(root.updateInput) }
        lit: leftMouse.containsMouse || shell.quickPanelOpenOn === root.screenName

        MouseArea {
            id: leftMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: shell.toggleQuickPanel(root.screenName)
        }

        TrayIcons {
            id: leftRow
            anchors.centerIn: parent
            screenName: root.screenName
        }
        Accessible.role: Accessible.Button
        Accessible.name: "Schnellzugriff: WLAN, Lautstärke, Bluetooth, Helligkeit"
        Accessible.onPressAction: shell.toggleQuickPanel(root.screenName)
    }

    // ---- Mitte ----
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 10 + (34 - height) / 2
        text: "Gibeon OS"
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 14
        Accessible.ignored: true
    }
}
