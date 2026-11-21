import QtQuick
import Creative

// Knopf für eine App in der Taskleiste – angeheftet oder gerade geöffnet.
// Darunter zeigt ein Strich, ob die App läuft (kurz) oder vorne ist (lang, Akzent).
Item {
    id: root

    property string icon        // eigenes Gibeon-Symbol (files, browser, terminal)
    property string themeIcon   // sonst Symbol aus dem Icon-Theme
    property string label
    property bool running: false
    property bool active: false
    property int count: 0
    property int badge: 0       // ungelesene Nachrichten (z. B. WhatsApp)

    signal clicked()
    signal middleClicked()
    signal rightClicked()
    readonly property bool hovered: mouse.containsMouse

    implicitWidth: 40
    implicitHeight: 40

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusButton
        color: mouse.pressed ? Theme.pressed : ((mouse.containsMouse || root.active) ? Theme.hover : "transparent")
    }

    // eigene Gibeon-Symbole: runde Fläche wie die App-Symbole (schlicht, wie Android-Apps)
    Rectangle {
        anchors.centerIn: parent
        visible: root.icon.length > 0
        width: 30
        height: 30
        radius: 15
        color: Theme.light ? "#edf0f5" : "#232836"
    }
    SvgIcon {
        anchors.centerIn: parent
        visible: root.icon.length > 0
        name: root.icon
        size: 17
    }

    // Graphit-Kachel aus dem Gibeon-Symbolthema (wie im Startmenü)
    Image {
        anchors.centerIn: parent
        visible: root.icon.length === 0
        width: 32
        height: 32
        sourceSize.width: 64
        sourceSize.height: 64
        source: root.icon.length === 0 ? iconFiles.url(root.themeIcon) : ""
        asynchronous: true
        smooth: true
    }

    // Ungelesen: kleine Zahl oben rechts
    Rectangle {
        visible: root.badge > 0
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 1
        anchors.topMargin: 2
        height: 17
        width: Math.max(17, badgeText.implicitWidth + 9)
        radius: 9
        color: Theme.accent
        border.color: Theme.ground
        border.width: 2
        Text {
            id: badgeText
            anchors.centerIn: parent
            text: root.badge > 99 ? "99+" : root.badge
            color: Theme.ground
            font.pixelSize: 10
            font.bold: true
        }
    }

    // Laufend / aktiv
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.bottom
        anchors.topMargin: 3
        height: 3
        radius: 2
        width: root.active ? 18 : 6
        visible: root.running
        color: root.active ? Theme.accent : Theme.text
        Behavior on width { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }

    // Mehrere Fenster: kleiner zweiter Punkt
    Rectangle {
        anchors.left: parent.horizontalCenter
        anchors.leftMargin: root.active ? 12 : 6
        anchors.top: parent.bottom
        anchors.topMargin: 3
        width: 3
        height: 3
        radius: 2
        visible: root.count > 1
        color: Theme.text
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: (mouse) => {
            if (mouse.button === Qt.MiddleButton)
                root.middleClicked()
            else if (mouse.button === Qt.RightButton)
                root.rightClicked()
            else
                root.clicked()
        }
    }

    Accessible.role: Accessible.Button
    Accessible.name: label + (running ? (active ? ", aktiv" : ", geöffnet") : "")
                     + (badge > 0 ? ", " + badge + " ungelesen" : "")
    Accessible.onPressAction: root.clicked()
}
