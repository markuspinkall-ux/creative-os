import QtQuick
import Creative

// Knopf für eine App in der Taskleiste – angeheftet oder gerade geöffnet.
// Darunter zeigt ein Strich, ob die App läuft (kurz) oder vorne ist (lang, Akzent).
Item {
    id: root

    property string icon        // eigenes Creative-Symbol (files, browser, terminal)
    property string themeIcon   // sonst Symbol aus dem Icon-Theme
    property string label
    property bool running: false
    property bool active: false
    property int count: 0

    signal clicked()
    signal middleClicked()
    signal rightClicked()
    readonly property bool hovered: mouse.containsMouse

    implicitWidth: 44
    implicitHeight: 44

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusButton
        color: mouse.pressed ? Theme.pressed : ((mouse.containsMouse || root.active) ? Theme.hover : "transparent")
    }

    SvgIcon {
        anchors.centerIn: parent
        visible: root.icon.length > 0
        name: root.icon
        size: 22
    }

    // Graphit-Kachel aus dem Creative-Symbolthema (wie im Startmenü)
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
    Accessible.onPressAction: root.clicked()
}
