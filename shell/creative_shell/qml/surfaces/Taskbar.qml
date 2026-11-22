import QtQuick
import QtQuick.Window
import Creative

// Die Taskleiste: links Startmenü und Apps, Mitte „Gerade läuft“, rechts Papierkorb und Uhr.
// Der Tray (WLAN, Ton, Bluetooth, Programme) sitzt in der oberen Leiste (Topbar.qml).
Item {
    id: root

    property string screenName

    // Fluid-Glas: KWin zeichnet den Hintergrund hinter der Leiste weich
    function updateBlur() {
        shell.setBlur(Window.window, [{ x: bar.x, y: bar.y, w: bar.width, h: bar.height, r: 0 }])
    }
    Component.onCompleted: Qt.callLater(updateBlur)
    onWidthChanged: { Qt.callLater(updateBlur); pointTimer.restart() }

    // Fenster wachsen aus ihrem Symbol: Lage der Symbole an den KWin-Effekt melden
    Timer { id: pointTimer; interval: 300; onTriggered: root.reportPoints() }
    Connections { target: tasks; function onRevisionChanged() { pointTimer.restart() } }
    function reportPoints() {
        const win = Window.window
        const geo = shell.screenGeometry(root.screenName)
        if (!win || geo.width === undefined) return
        const top = geo.y + geo.height - win.height
        const pts = []
        for (let i = 0; i < taskRepeater.count; i++) {
            const it = taskRepeater.itemAt(i)
            if (!it || !it.modelData) continue
            const p = it.mapToItem(null, it.width / 2, it.height / 2)
            pts.push({ key: it.modelData.key, desktopId: it.modelData.desktopId || "",
                       x: geo.x + p.x, y: top + p.y })
        }
        windowAnim.setTaskPoints(root.screenName, pts)
    }
    onHeightChanged: Qt.callLater(updateBlur)

    // Fluid-Design: Glasleiste über die ganze Breite, bündig am unteren Rand,
    // oben eine feine Kante und darunter eine Lichtkante wie bei Glas.
    Rectangle {
        id: bar
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        height: 52
        radius: 0
        color: shell.blurAvailable ? Theme.glass : Theme.glassSolid

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1
            color: Theme.glassEdge
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 1 }
            height: 1
            color: Theme.glassShine
        }

        // Klick auf freie Fläche schließt offene Menüs
        MouseArea {
            anchors.fill: parent
            onClicked: shell.closePopups()
        }

        // Musik-Visualizer: dunkelblaue Balken über die ganze Breite, hinter allen Knöpfen.
        // Nimmt keine Klicks an – die Taskleiste bleibt voll bedienbar.
        Item {
            id: viz
            anchors.fill: parent
            anchors.leftMargin: 4
            anchors.rightMargin: 4
            anchors.topMargin: 6
            anchors.bottomMargin: 3
            enabled: false
            opacity: visualizer.active && visualizer.enabled ? visualizer.strength : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
            readonly property int count: visualizer.bars
            readonly property real step: width / count
            Repeater {
                model: viz.count
                delegate: Rectangle {
                    required property int index
                    readonly property real level: visualizer.levels[index] || 0
                    x: index * viz.step + 1
                    width: Math.max(2, viz.step - 3)
                    height: Math.max(2, viz.height * level)
                    anchors.bottom: parent.bottom
                    radius: Math.min(3, width / 2)
                    // dunkles Orbit-Blau, nach oben heller
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0.40, 0.55, 0.92, 0.62) }
                        GradientStop { position: 1.0; color: Qt.rgba(0.16, 0.27, 0.55, 0.45) }
                    }
                    Behavior on height { NumberAnimation { duration: 60 } }
                }
            }
        }

        Row {
            id: appsRow
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            StartButton {
                open: shell.startMenuOpenOn === root.screenName
                onClicked: shell.toggleStartMenu(root.screenName)
            }

            Item {
                width: 13
                height: 44
                Rectangle {
                    anchors.centerIn: parent
                    width: 1
                    height: 28
                    color: Theme.tint(0.1)
                }
            }

            Repeater {
                id: taskRepeater
                // Angeheftete Apps + laufende Programme auf diesem Monitor
                onItemAdded: pointTimer.restart()
                onItemRemoved: pointTimer.restart()
                model: {
                    tasks.revision
                    return tasks.taskbarItems(root.screenName)
                }
                delegate: TaskButton {
                    required property var modelData
                    icon: modelData.icon
                    themeIcon: modelData.themeIcon
                    label: modelData.title
                    running: modelData.running
                    active: modelData.active
                    count: modelData.count
                    badge: modelData.badge || 0
                    onClicked: {
                        shell.closePopups()
                        tasks.activate(root.screenName, modelData.key, modelData.desktopId)
                    }
                    onMiddleClicked: tasks.launchNew(modelData.desktopId)
                    // Programmname beim Drüberfahren (eigene, durchlässige Fläche über der Leiste)
                    onHoveredChanged: {
                        if (hovered)
                            shell.showTaskTip(root.screenName, modelData.name || modelData.title || "",
                                              mapToItem(null, width / 2, 0).x, modelData.count || 0)
                        else
                            shell.hideTaskTip(root.screenName)
                    }
                    onRightClicked: shell.toggleTaskMenu(root.screenName, {
                        key: modelData.key, desktopId: modelData.desktopId, name: modelData.name,
                        running: modelData.running, count: modelData.count,
                        pinned: !!modelData.pinned   // ohne das zeigte das Menü nie „Von der Taskleiste lösen“
                    }, mapToItem(null, width / 2, 0).x)
                }
            }
        }

        // Gerade läuft: Interpret – Titel, mittig im freien Platz der Taskleiste
        Item {
            id: nowPlaying
            readonly property real freeL: appsRow.x + appsRow.width + 18
            readonly property real freeR: trashBtn.x - 26
            // Breite aus dem Text selbst (nicht aus der Zeile – sonst bleibt sie bei 0 hängen)
            width: Math.max(0, Math.min(15 + 9 + npText.implicitWidth + 24, freeR - freeL, 460))
            x: Math.max(freeL, Math.min(bar.width / 2 - width / 2, freeR - width))
            height: 40
            anchors.verticalCenter: parent.verticalCenter
            opacity: nowplaying.active && width > 90 ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 250 } }

            Rectangle {
                anchors.fill: parent
                radius: 20
                color: npMouse.containsMouse ? Theme.hover : "transparent"
            }
            Row {
                id: npRow
                anchors.centerIn: parent
                width: Math.min(implicitWidth, nowPlaying.width - 24)
                spacing: 9
                SvgIcon { id: npIcon; anchors.verticalCenter: parent.verticalCenter; name: "music"; size: 15 }
                Text {
                    id: npText
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, Math.max(0, nowPlaying.width - 24 - npIcon.width - 9))
                    elide: Text.ElideRight
                    text: nowplaying.artist.length ? nowplaying.artist + "  –  " + nowplaying.title : nowplaying.title
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
            MouseArea {
                id: npMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: nowplaying.raiseSource()
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Gerade läuft: " + nowplaying.artist + " – " + nowplaying.title
        }

        // Ganz rechts: Uhrzeit, Datum und Akku im Glasfeld – Klick öffnet den Kalender
        Rectangle {
            id: clockPill
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            width: clockRow.implicitWidth + 28
            height: 34
            radius: 17
            // Nur ein Hauch Grau (10 %) – eine leichte Abgrenzung zur Taskleiste
            readonly property color base: Theme.glassSolid
            color: Qt.rgba(base.r, base.g, base.b, clockMouse.containsMouse ? 0.22 : 0.10)
            // Rand nur angedeutet, keine Lichtkante – bloß eine leichte Nuance
            border.color: Theme.tint(0.05)
            border.width: 1
            MouseArea {
                id: clockMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: shell.toggleCalendar(root.screenName)
            }
            Row {
                id: clockRow
                anchors.centerIn: parent
                spacing: 12
                Text {
                    id: clock
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                }
                Text {
                    id: date
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                // Akku (nur bei Laptops)
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: akku.present && widgetExtras.akkuInstalled
                    spacing: 6
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: akku.percent + " %"
                        color: akku.low ? Theme.flame : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                    }
                    BatteryGlyph {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 24; height: 12
                        level: akku.percent
                        charging: akku.charging
                        low: akku.low
                    }
                    Accessible.role: Accessible.StaticText
                    Accessible.name: "Akku " + akku.percent + " Prozent, " + akku.statusText
                }
            }
            Timer {
                interval: 1000
                running: true
                repeat: true
                triggeredOnStart: true
                onTriggered: {
                    const now = new Date()
                    clock.text = Qt.formatTime(now, "HH:mm")
                    // z. B. „Sa., 21. Nov.“
                    date.text = now.toLocaleDateString(Qt.locale("de_DE"), "ddd, d. MMM")
                }
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Kalender – " + clock.text + ", " + date.text
            Accessible.onPressAction: shell.toggleCalendar(root.screenName)
        }

        // Systemtray vor der Uhr – wenn in Systemsteuerung › Darstellung so eingestellt.
        // Gleiche Darstellung wie die Uhr; Klick auf freie Stelle öffnet den Schnellzugriff.
        Rectangle {
            id: trayPill
            visible: shell.trayInTaskbar
            anchors.right: clockPill.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: visible ? trayIcons.implicitWidth + 28 : 0
            height: 34
            radius: 17
            readonly property color base: Theme.glassSolid
            readonly property bool lit: trayMouse.containsMouse || shell.quickPanelOpenOn === root.screenName
            color: Qt.rgba(base.r, base.g, base.b, lit ? 0.22 : 0.10)
            border.color: Theme.tint(0.05)
            border.width: 1
            MouseArea {
                id: trayMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: shell.toggleQuickPanel(root.screenName)
            }
            TrayIcons {
                id: trayIcons
                anchors.centerIn: parent
                screenName: root.screenName
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Schnellzugriff: WLAN, Lautstärke, Bluetooth, Helligkeit"
            Accessible.onPressAction: shell.toggleQuickPanel(root.screenName)
        }

        // Papierkorb vor dem Tray bzw. der Uhr
        Rectangle {
            id: trashBtn
            anchors.right: trayPill.visible ? trayPill.left : clockPill.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 40
            height: 40
            radius: 12
            color: (trashMouse.containsMouse || shell.trashMenuOpenOn === root.screenName)
                   ? Theme.hover : "transparent"
            SvgIcon {
                anchors.centerIn: parent
                name: trash.full ? "trash-full" : "trash"
                size: 20
            }
            MouseArea {
                id: trashMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                cursorShape: Qt.PointingHandCursor
                onClicked: (mouse) => {
                    if (mouse.button === Qt.RightButton) {
                        shell.toggleTrashMenu(root.screenName)
                    } else {
                        shell.closePopups()
                        trash.open()
                    }
                }
            }
            Accessible.role: Accessible.Button
            Accessible.name: trash.full ? "Papierkorb (" + trash.count + " Elemente)" : "Papierkorb (leer)"
            Accessible.onPressAction: trash.open()
        }
        Rectangle {
            anchors.right: trashBtn.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: 24
            color: Theme.tint(0.1)
        }
    }

}
