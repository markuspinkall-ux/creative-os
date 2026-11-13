import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtCore
import Creative

// Game Launcher – Steam-Spiele im Vollbild, mit Controller, Tastatur oder Maus.
// Farben kommen aus Theme: Graphit oder Porzellan, je nach Einstellung.
Window {
    id: win
    width: 1920
    height: 1080
    visible: false
    title: "Game Launcher"
    color: Theme.ground

    // Maßstab: alles ist für 1920 × 1080 entworfen
    readonly property real s: Math.max(0.5, Math.min(width / 1920, height / 1080))
    function px(v) { return Math.round(v * s) }

    // ---- Ansicht: große Kacheln oder Liste (bleibt gespeichert) ------------------------------------
    Settings {
        id: prefs
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/creative-os/gamelauncher-ansicht.conf"
        category: "Ansicht"
        property string view: "kacheln"
    }
    readonly property bool listMode: prefs.view === "liste"
    function toggleView() { prefs.view = listMode ? "kacheln" : "liste"; Qt.callLater(() => move(0)) }

    // ---- Daten -----------------------------------------------------------------------------
    readonly property var tabs: [
        { key: "recent", label: "Zuletzt gespielt" },
        { key: "all", label: "Bibliothek" },
        { key: "missing", label: "Nicht installiert" },
        { key: "shop", label: "Steam-Shop" }
    ]
    property int tab: 0
    readonly property string tabKey: tabs[tab].key
    readonly property var shown: {
        const all = launcher.games
        if (tabKey === "recent")
            return all.filter(g => g.installed)
        if (tabKey === "all")
            return all.slice().sort((a, b) => a.name.localeCompare(b.name, "de"))
        if (tabKey === "missing")
            return all.filter(g => !g.installed)
        return []
    }
    property int index: 0
    readonly property var game: shown.length ? shown[Math.min(index, shown.length - 1)] : null
    readonly property int installedCount: launcher.games.filter(g => g.installed).length

    onTabChanged: { index = 0; tiles.positionViewAtBeginning(); gameList.positionViewAtBeginning() }
    onShownChanged: if (index >= shown.length) index = Math.max(0, shown.length - 1)

    function primary() {
        if (tabKey === "shop") { launcher.openStore(); return }
        if (!game) return
        if (game.installed && game.ready) launcher.play(game.appid, game.name)
        else if (!game.installed) launcher.install(game.appid, game.name)
        else launcher.details(game.appid)
    }
    function move(d) {
        if (!shown.length) return
        index = Math.max(0, Math.min(shown.length - 1, index + d))
        tiles.positionViewAtIndex(index, ListView.Contain)
        gameList.positionViewAtIndex(index, ListView.Contain)
    }
    function handle(name) {
        if (!win.active) return              // Spiel läuft oder anderes Fenster vorne
        switch (name) {
        case "left": if (!listMode) move(-1); break
        case "right": if (!listMode) move(1); break
        case "up": if (listMode) move(-1); break
        case "down": if (listMode) move(1); break
        case "lb": tab = (tab + tabs.length - 1) % tabs.length; break
        case "rb": tab = (tab + 1) % tabs.length; break
        case "a": primary(); break
        case "x": if (game && !game.installed) launcher.install(game.appid, game.name); break
        case "y": if (game) launcher.details(game.appid); break
        case "menu": Qt.quit(); break
        case "view": toggleView(); break
        case "refresh": launcher.refresh(); break
        }
    }

    Connections {
        target: launcher
        function onAction(name) { win.handle(name) }
        function onToast(text) { toastText.text = text; toast.opacity = 1; toastTimer.restart() }
    }
    onActiveChanged: if (active) launcher.refresh()

    // Tastatur (gleiche Belegung)
    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: (event) => {
            const map = {}
            map[Qt.Key_Left] = "left"; map[Qt.Key_Right] = "right"; map[Qt.Key_Up] = "up"; map[Qt.Key_Down] = "down"
            map[Qt.Key_V] = "view"
            map[Qt.Key_Return] = "a"; map[Qt.Key_Enter] = "a"; map[Qt.Key_Space] = "a"
            map[Qt.Key_I] = "x"; map[Qt.Key_D] = "y"
            map[Qt.Key_PageUp] = "lb"; map[Qt.Key_PageDown] = "rb"
            map[Qt.Key_F5] = "refresh"
            if (event.key === Qt.Key_Tab) { win.handle(event.modifiers & Qt.ShiftModifier ? "lb" : "rb"); event.accepted = true; return }
            if (map[event.key] !== undefined) { win.handle(map[event.key]); event.accepted = true }
        }
    }

    // ---- Titelbild des gewählten Spiels -------------------------------------------------------
    Item {
        id: heroBox
        anchors.right: parent.right
        anchors.top: parent.top
        width: parent.width * 0.646
        height: parent.height * 0.648
        Rectangle { anchors.fill: parent; color: Theme.raised; visible: hero.status !== Image.Ready }
        Image {
            id: hero
            anchors.fill: parent
            source: win.game ? (win.game.hero || win.game.cover) : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 260 } }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Theme.ground }
                GradientStop { position: 0.35; color: Qt.rgba(Theme.ground.r, Theme.ground.g, Theme.ground.b, 0.6) }
                GradientStop { position: 0.7; color: Qt.rgba(Theme.ground.r, Theme.ground.g, Theme.ground.b, 0) }
            }
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: win.px(260)
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(Theme.ground.r, Theme.ground.g, Theme.ground.b, 0) }
                GradientStop { position: 1.0; color: Theme.ground }
            }
        }
    }

    // ---- Kopfleiste ------------------------------------------------------------------------
    Row {
        id: header
        x: win.px(64)
        y: win.px(40)
        spacing: win.px(40)
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: win.px(12)
            SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "games"; size: win.px(32) }
            Text { text: "Game Launcher"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(22); font.bold: true; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            spacing: win.px(8)
            Repeater {
                model: win.tabs
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool on: win.tab === index
                    width: tabLabel.implicitWidth + win.px(44)
                    height: win.px(44)
                    radius: height / 2
                    color: on ? Theme.text : (tabMouse.containsMouse ? Theme.pressed : (Theme.light ? Qt.rgba(1, 1, 1, 0.75) : Theme.subtle))
                    Text {
                        id: tabLabel
                        anchors.centerIn: parent
                        text: parent.modelData.label
                        color: parent.on ? Theme.ground : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: win.px(17)
                        font.bold: parent.on
                    }
                    MouseArea { id: tabMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: win.tab = parent.index }
                    Accessible.role: Accessible.PageTab
                    Accessible.name: modelData.label
                }
            }
        }
    }
    Rectangle {
        anchors.right: parent.right
        anchors.rightMargin: win.px(64)
        y: win.px(36)
        height: win.px(52)
        width: statusRow.implicitWidth + win.px(28)
        radius: height / 2
        color: Theme.light ? Qt.rgba(1, 1, 1, 0.86) : Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.7)
        Row {
            id: statusRow
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: win.px(6)
            spacing: win.px(20)
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: win.px(8)
                Rectangle { width: win.px(9); height: width; radius: width / 2; anchors.verticalCenter: parent.verticalCenter; color: launcher.pads > 0 ? Theme.ok : Theme.track }
                Text {
                    text: launcher.pads > 0 ? (launcher.pads > 1 ? launcher.pads + " Controller verbunden" : "Controller verbunden") : "Kein Controller"
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(16)
                }
            }
            // Ansicht: Kacheln | Liste
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                height: win.px(40)
                width: viewRow.implicitWidth + win.px(8)
                radius: height / 2
                color: Theme.light ? "#ffffff" : Theme.raised
                border.color: Theme.hairline
                Row {
                    id: viewRow
                    anchors.centerIn: parent
                    spacing: win.px(2)
                    Repeater {
                        model: [{ k: "kacheln", t: "Kacheln" }, { k: "liste", t: "Liste" }]
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool on: prefs.view === modelData.k
                            width: vText.implicitWidth + win.px(28)
                            height: win.px(32)
                            radius: height / 2
                            color: on ? Theme.text : (vMouse.containsMouse ? Theme.pressed : "transparent")
                            Text { id: vText; anchors.centerIn: parent; text: parent.modelData.t; color: parent.on ? Theme.ground : Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(15); font.bold: parent.on }
                            MouseArea { id: vMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (!parent.on) win.toggleView() }
                            Accessible.role: Accessible.Button
                            Accessible.name: "Ansicht: " + modelData.t
                        }
                    }
                }
            }
            Text { id: clock; anchors.verticalCenter: parent.verticalCenter; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(22); font.bold: true }
            Rectangle {
                id: deskBtn
                width: deskRow.implicitWidth + win.px(26)
                height: win.px(40)
                radius: height / 2
                color: deskMouse.containsMouse ? Theme.pressed : (Theme.light ? "#ffffff" : Theme.raised)
                border.color: Theme.hairline
                Row {
                    id: deskRow
                    anchors.centerIn: parent
                    spacing: win.px(8)
                    Hint { glyph: "☰"; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "Zum Desktop"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(16); font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea { id: deskMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Qt.quit() }
                Accessible.role: Accessible.Button
                Accessible.name: "Zum Desktop"
            }
        }
    }
    Timer {
        interval: 1000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: clock.text = Qt.formatTime(new Date(), "HH:mm")
    }

    // ---- Infos zum gewählten Spiel ------------------------------------------------------------
    Column {
        x: win.listMode ? win.width * 0.47 : win.px(64)
        y: win.listMode ? win.px(560) : win.px(150)
        width: win.listMode ? win.width * 0.53 - win.px(64) : win.px(900)
        spacing: win.px(win.listMode ? 18 : 16)
        visible: win.tabKey === "shop" || win.game !== null
        Text {
            text: {
                const g = win.game
                if (win.tabKey === "shop") return "STEAM-SHOP"
                if (!g) return ""
                if (g.installed && !g.ready) return "WIRD INSTALLIERT · " + Math.round(g.progress * 100) + " %"
                if (!g.installed) return "NICHT INSTALLIERT"
                return g.lastText ? "ZULETZT GESPIELT · " + g.lastText.toUpperCase() : "INSTALLIERT"
            }
            color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: win.px(16); font.bold: true; font.letterSpacing: win.px(2)
        }
        Text {
            width: parent.width
            text: win.tabKey === "shop" ? "Neue Spiele finden" : (win.game ? win.game.name : "")
            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(win.listMode ? 64 : 60); font.bold: true
            wrapMode: Text.Wrap; maximumLineCount: win.listMode ? 2 : 1; elide: Text.ElideRight
            lineHeight: 0.95
        }
        Row {
            spacing: win.px(28)
            Repeater {
                model: {
                    const g = win.game
                    if (win.tabKey === "shop") return ["Angebote, Neuheiten und deine Wunschliste – im Steam-Shop"]
                    if (!g) return []
                    return [g.playText, g.sizeText, g.installed ? "" : "Wird über Steam installiert"].filter(t => t && t.length)
                }
                delegate: Text { required property string modelData; text: modelData; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(18) }
            }
        }
        // Fortschritt beim Installieren
        Rectangle {
            visible: win.game !== null && win.game.installed && !win.game.ready && win.tabKey !== "shop"
            width: win.px(420); height: win.px(8); radius: height / 2
            color: Theme.track
            Rectangle { width: parent.width * (win.game ? win.game.progress : 0); height: parent.height; radius: parent.radius; color: Theme.accent }
        }
        Row {
            spacing: win.px(14)
            topPadding: win.px(10)
            BigButton {
                primary: true
                glyph: "A"
                label: {
                    const g = win.game
                    if (win.tabKey === "shop") return "Shop öffnen"
                    if (!g) return ""
                    return g.installed ? (g.ready ? "Spielen" : "In Steam ansehen") : "Installieren"
                }
                onActivated: win.primary()
            }
            BigButton {
                visible: win.tabKey !== "shop"
                glyph: "Y"
                label: "Details"
                onActivated: if (win.game) launcher.details(win.game.appid)
            }
        }
    }

    // ---- Kachel-Band ---------------------------------------------------------------------------
    Column {
        x: win.px(64)
        y: win.px(424)
        width: parent.width - x
        spacing: win.px(14)
        visible: win.tabKey !== "shop" && !win.listMode
        Row {
            spacing: win.px(16)
            Text { text: win.tabs[win.tab].label; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(24); font.bold: true }
            Text {
                anchors.baseline: parent.children[0].baseline
                text: win.installedCount + " installiert · " + launcher.games.length + " in der Bibliothek"
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(16)
            }
        }
        ListView {
            id: tiles
            width: parent.width
            height: win.px(516)
            orientation: ListView.Horizontal
            spacing: win.px(26)
            model: win.shown
            currentIndex: win.index
            highlightFollowsCurrentItem: false
            boundsBehavior: Flickable.StopAtBounds
            clip: false
            rightMargin: win.px(64)
            delegate: Item {
                id: tile
                required property var modelData
                required property int index
                readonly property bool on: index === win.index
                width: on ? win.px(340) : win.px(296)
                height: tiles.height
                Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                Rectangle {
                    id: card
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: win.px(6)
                    width: parent.width
                    height: tile.on ? win.px(506) : win.px(440)
                    Behavior on height { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    radius: win.px(16)
                    color: Theme.raised
                    clip: true
                    opacity: tile.on ? 1 : 0.9
                    Image {
                        anchors.fill: parent
                        source: tile.modelData.cover
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: win.px(692)
                        visible: status === Image.Ready
                    }
                    // Ohne Bild: Name groß
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - win.px(24)
                        visible: tile.modelData.cover === ""
                        text: tile.modelData.name
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        color: Theme.text
                        font.family: Theme.fontFamily; font.pixelSize: win.px(26); font.bold: true
                    }
                    Rectangle {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                        height: win.px(96)
                        visible: tile.modelData.cover !== ""
                        gradient: Gradient {
                            GradientStop { position: 0; color: "transparent" }
                            GradientStop { position: 1; color: Qt.rgba(0.04, 0.05, 0.06, 0.88) }
                        }
                        Text {
                            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                            anchors.margins: win.px(18)
                            text: tile.modelData.name
                            elide: Text.ElideRight
                            color: "#ffffff"
                            font.family: Theme.fontFamily; font.pixelSize: win.px(22); font.bold: true
                        }
                    }
                    // Nicht installiert / lädt
                    Rectangle {
                        visible: !tile.modelData.installed || !tile.modelData.ready
                        anchors.top: parent.top; anchors.right: parent.right; anchors.margins: win.px(10)
                        height: win.px(34)
                        width: badgeText.implicitWidth + win.px(24)
                        radius: height / 2
                        color: Theme.light ? "#ffffff" : Qt.rgba(0.06, 0.07, 0.09, 0.88)
                        Text {
                            id: badgeText
                            anchors.centerIn: parent
                            text: tile.modelData.installed ? Math.round(tile.modelData.progress * 100) + " %" : "↓ Installieren"
                            color: tile.modelData.installed ? Theme.accent : Theme.flame
                            font.family: Theme.fontFamily; font.pixelSize: win.px(16); font.bold: true
                        }
                    }
                    Rectangle {
                        visible: tile.modelData.installed && !tile.modelData.ready
                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                        height: win.px(5)
                        color: Qt.rgba(0, 0, 0, 0.4)
                        Rectangle { width: parent.width * tile.modelData.progress; height: parent.height; color: Theme.accent }
                    }
                }
                Rectangle {
                    anchors.fill: card
                    anchors.margins: -win.px(4)
                    radius: card.radius + win.px(4)
                    color: "transparent"
                    border.color: Theme.accent
                    border.width: win.px(4)
                    visible: tile.on
                }
                MouseArea {
                    anchors.fill: card
                    cursorShape: Qt.PointingHandCursor
                    onClicked: tile.on ? win.primary() : (win.index = tile.index)
                }
                Accessible.role: Accessible.ListItem
                Accessible.name: modelData.name + (modelData.installed ? "" : ", nicht installiert")
            }
            WheelHandler {
                onWheel: (event) => win.move(event.angleDelta.y > 0 || event.angleDelta.x > 0 ? -1 : 1)
            }
        }
    }

    // ---- Liste (optional) ---------------------------------------------------------------------------
    Column {
        x: win.px(64)
        y: win.px(130)
        width: win.width * 0.47 - win.px(110)
        height: win.height - y - win.px(96)
        spacing: win.px(14)
        visible: win.tabKey !== "shop" && win.listMode
        Row {
            spacing: win.px(16)
            Text { text: win.tabs[win.tab].label; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(24); font.bold: true }
            Text {
                anchors.baseline: parent.children[0].baseline
                text: win.shown.length + (win.shown.length === 1 ? " Spiel" : " Spiele")
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(16)
            }
        }
        ListView {
            id: gameList
            width: parent.width
            height: parent.height - win.px(50)
            clip: true
            spacing: win.px(6)
            model: win.shown
            currentIndex: win.index
            highlightFollowsCurrentItem: false
            boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool on: index === win.index
                width: gameList.width
                height: win.px(104)
                radius: win.px(16)
                color: on ? (Theme.light ? "#ffffff" : Theme.raised) : (rowMouse.containsMouse ? Theme.subtle : "transparent")
                border.color: on ? Theme.accent : "transparent"
                border.width: win.px(3)
                Rectangle {
                    id: thumb
                    x: win.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    width: win.px(56); height: win.px(84)
                    radius: win.px(8)
                    color: Theme.track
                    clip: true
                    Image {
                        anchors.fill: parent
                        source: row.modelData.cover
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: win.px(112)
                        visible: status === Image.Ready
                    }
                }
                Column {
                    anchors.left: thumb.right
                    anchors.leftMargin: win.px(18)
                    anchors.right: rowBadge.left
                    anchors.rightMargin: win.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: win.px(6)
                    Text {
                        width: parent.width
                        text: row.modelData.name
                        elide: Text.ElideRight
                        color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(24); font.bold: true
                    }
                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: {
                            const g = row.modelData
                            if (!g.installed) return [g.sizeText, "nicht installiert"].filter(t => t).join(" · ")
                            if (!g.ready) return "Wird installiert · " + Math.round(g.progress * 100) + " %"
                            return [g.lastText ? "Zuletzt " + g.lastText : "", g.playText, g.sizeText].filter(t => t).join(" · ")
                        }
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(16)
                    }
                }
                Rectangle {
                    id: rowBadge
                    anchors.right: parent.right
                    anchors.rightMargin: win.px(16)
                    anchors.verticalCenter: parent.verticalCenter
                    height: win.px(36)
                    width: rowBadgeText.implicitWidth + win.px(28)
                    radius: height / 2
                    color: row.on ? (row.modelData.installed ? Theme.accent : Theme.flame) : Theme.subtle
                    Text {
                        id: rowBadgeText
                        anchors.centerIn: parent
                        text: row.modelData.installed ? (row.modelData.ready ? "▶ Spielen" : Math.round(row.modelData.progress * 100) + " %") : "↓ Installieren"
                        color: row.on ? (Theme.light ? "#ffffff" : Theme.ground) : (row.modelData.installed ? Theme.text : Theme.flame)
                        font.family: Theme.fontFamily; font.pixelSize: win.px(15); font.bold: true
                    }
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: row.on ? win.primary() : (win.index = row.index)
                }
                Accessible.role: Accessible.ListItem
                Accessible.name: modelData.name + (modelData.installed ? "" : ", nicht installiert")
            }
            WheelHandler {
                onWheel: (event) => win.move(event.angleDelta.y > 0 ? -1 : 1)
            }
        }
    }

    // ---- Leere Zustände ------------------------------------------------------------------------
    Column {
        anchors.centerIn: parent
        spacing: win.px(16)
        visible: !launcher.loading && (win.tabKey !== "shop") && win.shown.length === 0
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: !launcher.steamInstalled ? "Steam ist nicht installiert"
                  : !launcher.steamFound ? "Steam wurde noch nicht eingerichtet"
                  : win.tabKey === "missing" ? "Alle Spiele sind installiert" : "Noch keine Spiele installiert"
            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: win.px(34); font.bold: true
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: !launcher.steamFound ? "Öffne Steam einmal und melde dich an – danach erscheinen hier deine Spiele."
                  : "Im Bereich „Nicht installiert“ und im Steam-Shop findest du Spiele zum Installieren."
            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(18)
        }
        BigButton {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: launcher.steamInstalled
            primary: true
            glyph: "A"
            label: launcher.steamFound ? "Steam-Shop öffnen" : "Steam öffnen"
            onActivated: launcher.steamFound ? launcher.openStore() : launcher.openSteam()
        }
    }

    // ---- Tasten-Hinweise --------------------------------------------------------------------------
    Row {
        anchors.right: parent.right
        anchors.rightMargin: win.px(64)
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.px(30)
        spacing: win.px(30)
        Repeater {
            model: [
                { g: "A", t: win.tabKey === "shop" ? "Öffnen" : (win.game && !win.game.installed ? "Installieren" : "Spielen") },
                { g: "Y", t: "Details" },
                { g: "LB / RB", t: "Bereich wechseln" },
                { g: "⧉", t: win.listMode ? "Kacheln" : "Liste" },
                { g: "☰", t: "Desktop" }
            ]
            delegate: Row {
                required property var modelData
                spacing: win.px(8)
                Hint { glyph: modelData.g; anchors.verticalCenter: parent.verticalCenter }
                Text { text: modelData.t; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: win.px(16); anchors.verticalCenter: parent.verticalCenter }
            }
        }
    }

    // ---- Meldung -------------------------------------------------------------------------------------
    Rectangle {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.px(90)
        width: toastText.implicitWidth + win.px(48)
        height: win.px(54)
        radius: height / 2
        color: Theme.text
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }
        Text { id: toastText; anchors.centerIn: parent; color: Theme.ground; font.family: Theme.fontFamily; font.pixelSize: win.px(18); font.bold: true }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ---- Bausteine ------------------------------------------------------------------------------------
    component Hint: Rectangle {
        property string glyph
        readonly property color glyphColor: glyph === "A" ? Theme.ok : glyph === "B" ? Theme.flame
                                            : glyph === "X" ? Theme.accent : glyph === "Y" ? (Theme.light ? "#a87a00" : "#ffd36f") : Theme.text
        width: Math.max(height, hintText.implicitWidth + win.px(16))
        height: win.px(28)
        radius: height / 2
        color: Theme.light ? "#ffffff" : Theme.pressed
        Text { id: hintText; anchors.centerIn: parent; text: parent.glyph; color: parent.glyphColor; font.family: Theme.fontFamily; font.pixelSize: win.px(14); font.bold: true }
    }

    component BigButton: Rectangle {
        id: bb
        property bool primary: false
        property string glyph
        property string label
        signal activated()
        width: bbRow.implicitWidth + win.px(46)
        height: win.px(64)
        radius: height / 2
        color: primary ? (bbMouse.pressed ? Qt.darker(Theme.accent, 1.12) : Theme.accent)
                       : (bbMouse.containsMouse ? Theme.pressed : (Theme.light ? "#ffffff" : Theme.raised))
        border.color: primary ? "transparent" : Theme.hairline
        Row {
            id: bbRow
            anchors.verticalCenter: parent.verticalCenter
            x: win.px(12)
            spacing: win.px(14)
            Rectangle {
                width: win.px(40); height: width; radius: width / 2
                color: bb.primary ? (Theme.light ? "#ffffff" : Theme.ground) : Theme.pressed
                Text {
                    anchors.centerIn: parent
                    text: bb.glyph
                    color: bb.glyph === "A" ? Theme.ok : (Theme.light ? "#a87a00" : "#ffd36f")
                    font.family: Theme.fontFamily; font.pixelSize: win.px(18); font.bold: true
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: bb.label
                color: bb.primary ? Theme.accentText : Theme.text
                font.family: Theme.fontFamily; font.pixelSize: win.px(21); font.bold: true
            }
        }
        MouseArea { id: bbMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bb.activated() }
        Accessible.role: Accessible.Button
        Accessible.name: label
        Accessible.onPressAction: activated()
    }
}
