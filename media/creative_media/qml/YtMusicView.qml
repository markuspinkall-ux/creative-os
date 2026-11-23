import QtQuick
import QtQuick.Templates as GibeonT
import QtQuick.Controls.Basic
import QtWebEngine
import Creative

// YouTube Music mit eigener Oberfläche:
//   oben Suche und Reiter (Für dich, Charts, Favoriten), darunter Kacheln bzw. Treffer,
//   unten die Wiedergabe als reines Musikstück (Cover statt Video).
// Abgespielt wird im offiziellen YouTube-Music-Player, der unsichtbar im Hintergrund läuft –
// Werbung ist zu hören, aber nicht zu sehen; bietet YouTube „Überspringen“ an, gibt es dafür einen Knopf.
Item {
    id: root
    objectName: "ytView"
    property string tab: "home"          // home | charts | search | favs
    property bool showPage: false        // offizielle Seite zeigen (Anmeldung, Zustimmung)
    readonly property bool started: ytmusic.nowTitle.length > 0 || ytmusic.adPlaying

    // Erst laden, wenn YouTube Music zum ersten Mal geöffnet wird (oder der Sprachassistent etwas will)
    property bool activated: false
    onVisibleChanged: if (visible && !activated) activate()
    function activate() {
        if (activated || !webEngineAvailable)
            return
        activated = true
        ytmusic.loadHome()
    }
    Connections {
        target: ytmusic
        function onOpenUrl(u) { root.activate() }
    }

    function time(sec) {
        sec = Math.max(0, Math.floor(sec))
        return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0")
    }

    // ---- unsichtbare offizielle Seiten (gemeinsame Anmeldung) ---------------------------------------
    WebEngineProfile {
        id: ytProfile
        storageName: "creative-ytmusic"
        offTheRecord: false
        persistentCookiesPolicy: WebEngineProfile.ForcePersistentCookies
        httpCacheType: WebEngineProfile.DiskHttpCache
    }
    // Ein 1 px großer Ausschnitt hält die Seiten „sichtbar“ (sie laufen und laden weiter), ohne sie zu zeigen.
    // Mit „Webseite“ wird die Player-Seite groß gezeigt (z. B. zum Anmelden oder Zustimmen).
    Item {
        id: pageHost
        z: root.showPage ? 5 : -1
        x: 0
        y: root.showPage ? head.height : 0
        width: root.showPage ? root.width : 1
        height: root.showPage ? root.height - head.height - bar.height : 1
        clip: true
        Loader {
            id: playerLoader
            width: root.showPage ? pageHost.width : 1280
            height: root.showPage ? pageHost.height : 800
            active: webEngineAvailable && root.activated
            sourceComponent: Component { YtWeb { profile: ytProfile } }
        }
    }
    Item {
        width: 1; height: 1; clip: true; z: -1
        Loader {
            width: 1280; height: 1600
            active: webEngineAvailable && root.activated
            sourceComponent: Component { YtData { profile: ytProfile } }
        }
    }

    // ---- Kopf: Suche und Reiter -----------------------------------------------------------------------
    Rectangle {
        id: head
        anchors.left: parent.left
        anchors.right: parent.right
        height: 64
        color: Theme.footer
        z: 6

        Rectangle {
            id: searchBox
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(420, parent.width * 0.38)
            height: 40
            radius: 20
            color: Theme.raised
            border.color: searchField.activeFocus ? Theme.accent : "transparent"
            SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 15 }
            TextField {
                GibeonT.ContextMenu.menu: CTextMenu {}
                id: searchField
                anchors.fill: parent
                anchors.leftMargin: 36
                anchors.rightMargin: 12
                placeholderText: "Lieder, Künstler, Alben suchen"
                placeholderTextColor: Theme.textMuted
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                background: Item {}
                selectByMouse: true
                onAccepted: {
                    if (text.trim().length) {
                        root.tab = "search"
                        root.showPage = false
                        ytmusic.find(text)
                    }
                }
            }
        }

        Row {
            anchors.left: searchBox.right
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            Repeater {
                model: [["home", "Für dich"], ["charts", "Charts"], ["favs", "Favoriten"]]
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool cur: root.tab === modelData[0] && !root.showPage
                    width: tl.implicitWidth + 28
                    height: 34
                    radius: 17
                    color: cur ? Theme.accent : (tm.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
                    Text {
                        id: tl
                        anchors.centerIn: parent
                        text: modelData[1] + (modelData[0] === "favs" && ytmusic.favoriteCount > 0 ? "  " + ytmusic.favoriteCount : "")
                        color: parent.cur ? Theme.accentText : Theme.text
                        font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true
                    }
                    MouseArea {
                        id: tm
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.showPage = false
                            root.tab = modelData[0]
                            if (root.tab === "home") ytmusic.loadHome()
                            else if (root.tab === "charts") ytmusic.loadCharts()
                        }
                    }
                    Accessible.role: Accessible.PageTab
                    Accessible.name: modelData[1]
                }
            }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            width: wl.implicitWidth + 26
            height: 34
            radius: 17
            color: root.showPage ? Theme.accent : (wm.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
            Text { id: wl; anchors.centerIn: parent; text: root.showPage ? "Zurück zur Musik" : "Webseite (Anmelden)"; color: root.showPage ? Theme.accentText : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
            MouseArea { id: wm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.showPage = !root.showPage }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    // ---- Inhalt -----------------------------------------------------------------------------------------
    Flickable {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: head.bottom
        anchors.bottom: bar.top
        visible: !root.showPage
        contentHeight: content.implicitHeight + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 5; radius: 3; color: Theme.tint(0.2) } }

        Column {
            id: content
            x: 24
            y: 20
            width: body.width - 48
            spacing: 22

            // Zustimmung/Anmeldung nötig
            Rectangle {
                width: parent.width
                visible: ytmusic.needsConsent
                height: consentCol.implicitHeight + 32
                radius: 16
                color: Theme.raised
                Column {
                    id: consentCol
                    anchors.centerIn: parent
                    width: parent.width - 40
                    spacing: 10
                    Text { width: parent.width; wrapMode: Text.WordWrap; text: "YouTube Music möchte einmal deine Zustimmung (Cookies) bzw. Anmeldung."; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                    Text { width: parent.width; wrapMode: Text.WordWrap; text: "Öffne die Webseite, bestätige dort – danach erscheinen hier deine Vorschläge."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                    CButton { text: "Webseite öffnen"; primary: true; onClicked: root.showPage = true }
                }
            }

            Text {
                visible: ytmusic.loading && root.tab !== "favs"
                text: root.tab === "search" ? "Suche „" + ytmusic.query + "“ …" : "Vorschläge werden geladen …"
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
            }

            // Kachelreihen (Für dich, Charts)
            Repeater {
                model: (root.tab === "home" || root.tab === "charts") ? ytmusic.shelves : []
                delegate: Column {
                    required property var modelData
                    width: content.width
                    spacing: 10
                    Text { text: modelData.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true; visible: text.length > 0 }
                    ListView {
                        width: parent.width
                        height: 222
                        orientation: ListView.Horizontal
                        spacing: 14
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: modelData.items
                        ScrollBar.horizontal: ScrollBar { contentItem: Rectangle { implicitHeight: 4; radius: 2; color: Theme.tint(0.2) } }
                        delegate: Tile { required property var modelData; item: modelData }
                    }
                }
            }

            // Suchtreffer
            Column {
                width: parent.width
                visible: root.tab === "search"
                spacing: 4
                Text { text: "Treffer für „" + ytmusic.query + "“"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true; bottomPadding: 6 }
                Repeater {
                    model: root.tab === "search" ? ytmusic.results : []
                    delegate: ResultRow { required property var modelData; item: modelData }
                }
                Text {
                    visible: !ytmusic.loading && ytmusic.results.length === 0 && !ytmusic.needsConsent
                    text: "Nichts gefunden."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                }
            }

            // Favoriten als Kacheln
            Column {
                width: parent.width
                visible: root.tab === "favs"
                spacing: 12
                Text { text: "Favoriten"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true }
                Flow {
                    width: parent.width
                    spacing: 14
                    Repeater {
                        model: root.tab === "favs" ? ytmusic.favorites : []
                        delegate: Tile { required property var modelData; item: modelData }
                    }
                }
                Text {
                    visible: ytmusic.favoriteCount === 0
                    text: "Noch keine Favoriten – tippe bei einem Lied auf das Herz."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                }
            }
        }
    }

    // Ohne eingebauten Browser-Baustein: im eigenen Fenster öffnen
    Column {
        anchors.centerIn: body
        visible: !webEngineAvailable
        spacing: 14
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "YouTube Music öffnet sich in einem eigenen Fenster."; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14 }
        CButton { anchors.horizontalCenter: parent.horizontalCenter; text: "YouTube Music öffnen"; primary: true; onClicked: Qt.openUrlExternally(ytmusic.home) }
    }

    // ---- Wiedergabe: reines Musikstück ------------------------------------------------------------------
    Rectangle {
        id: bar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.started ? 92 : 0
        visible: root.started
        color: Theme.footer
        z: 6
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top }

        Rectangle {
            id: cover
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            width: 62; height: 62; radius: 10
            color: "#2b3550"
            clip: true
            Image { anchors.fill: parent; source: ytmusic.adPlaying ? "" : ytmusic.nowThumb; fillMode: Image.PreserveAspectCrop; asynchronous: true; visible: !ytmusic.adPlaying }
            SvgIcon { anchors.centerIn: parent; name: "music"; size: 22; visible: ytmusic.adPlaying || !ytmusic.nowThumb }
        }
        Column {
            anchors.left: cover.right
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(300, root.width * 0.25)
            spacing: 3
            Text { width: parent.width; elide: Text.ElideRight; text: ytmusic.adPlaying ? "Werbung" : ytmusic.nowTitle; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
            Text { width: parent.width; elide: Text.ElideRight; text: ytmusic.adPlaying ? "Gleich geht es mit deiner Musik weiter" : ytmusic.nowArtist; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }

        Column {
            anchors.centerIn: parent
            width: Math.min(460, root.width * 0.38)
            spacing: 6
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 8
                IconButton { width: 40; height: 40; icon: "prev"; iconSize: 18; label: "Zurück"; enabled: !ytmusic.adPlaying; onClicked: ytmusic.send("prev") }
                Rectangle {
                    width: 46; height: 46; radius: 23
                    color: Theme.accent
                    SvgIcon { anchors.centerIn: parent; name: ytmusic.playing ? "pause-dark" : "play-dark"; size: 18 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ytmusic.send("toggle") }
                    Accessible.role: Accessible.Button
                    Accessible.name: ytmusic.playing ? "Pause" : "Abspielen"
                }
                IconButton { width: 40; height: 40; icon: "next"; iconSize: 18; label: "Weiter"; enabled: !ytmusic.adPlaying; onClicked: ytmusic.send("next") }
            }
            Row {
                width: parent.width
                spacing: 8
                Text { text: root.time(ytmusic.position); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                Rectangle {
                    width: parent.width - 80
                    height: 4; radius: 2
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.tint(0.12)
                    Rectangle {
                        width: ytmusic.duration > 0 ? parent.width * Math.min(1, ytmusic.position / ytmusic.duration) : 0
                        height: 4; radius: 2
                        color: ytmusic.adPlaying ? Theme.flame : Theme.accent
                    }
                    MouseArea {
                        anchors.fill: parent
                        anchors.topMargin: -8; anchors.bottomMargin: -8
                        enabled: !ytmusic.adPlaying && ytmusic.duration > 0
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (m) => ytmusic.send("seek:" + (m.x / width * ytmusic.duration).toFixed(1))
                    }
                }
                Text { text: root.time(ytmusic.duration); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Rectangle {
                visible: ytmusic.adPlaying
                width: adl.implicitWidth + 20; height: 26; radius: 13
                anchors.verticalCenter: parent.verticalCenter
                color: Qt.rgba(Theme.flame.r, Theme.flame.g, Theme.flame.b, 0.2)
                Text { id: adl; anchors.centerIn: parent; text: "Werbung"; color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
            }
            CButton { visible: ytmusic.canSkip; text: "Überspringen"; onClicked: ytmusic.send("skip") }
            IconButton {
                width: 40; height: 40
                visible: !ytmusic.adPlaying
                icon: ytmusic.currentFavorite ? "heart-on" : "heart"
                iconSize: 18
                enabled: ytmusic.nowVideo.length > 0
                label: ytmusic.currentFavorite ? "Aus den Favoriten entfernen" : "Zu den Favoriten"
                onClicked: ytmusic.toggleCurrentFavorite()
            }
        }
    }

    // ---- Bausteine --------------------------------------------------------------------------------------
    component Tile: Rectangle {
        id: tile
        property var item: ({})
        readonly property bool current: !!item.videoId && item.videoId === ytmusic.nowVideo
        width: 160
        height: 216
        radius: 14
        color: tma.containsMouse ? Theme.hover : "transparent"
        Rectangle {
            id: art
            x: 6; y: 6
            width: 148; height: 148; radius: 12
            color: "#2b3550"
            clip: true
            Image { anchors.fill: parent; source: tile.item.thumb || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 300; sourceSize.height: 300 }
            SvgIcon { anchors.centerIn: parent; name: "music"; size: 28; visible: !tile.item.thumb }
            Rectangle {
                anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 8
                width: 40; height: 40; radius: 20
                color: Theme.accent
                visible: tma.containsMouse || tile.current
                SvgIcon { anchors.centerIn: parent; name: tile.current && ytmusic.playing ? "pause-dark" : "play-dark"; size: 15 }
            }
        }
        Column {
            x: 8
            anchors.top: art.bottom
            anchors.topMargin: 8
            width: parent.width - 16
            spacing: 2
            Text { width: parent.width; elide: Text.ElideRight; text: tile.item.title || ""; color: tile.current ? Theme.accent : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
            Text { width: parent.width; elide: Text.ElideRight; text: tile.item.subtitle || ""; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
        }
        MouseArea {
            id: tma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (tile.current) ytmusic.send("toggle")
                else ytmusic.playUrl(tile.item.url)
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: (item.title || "") + " abspielen"
    }

    component ResultRow: Rectangle {
        id: rr
        property var item: ({})
        readonly property bool current: !!item.videoId && item.videoId === ytmusic.nowVideo
        readonly property bool fav: ytmusic.favoriteCount >= 0 && !!item.videoId && ytmusic.isFavorite(item.videoId)
        width: content.width
        height: 64
        radius: 12
        color: current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14) : (rm.containsMouse ? Theme.hover : "transparent")
        Rectangle {
            id: rthumb
            x: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 48; height: 48; radius: 8
            color: "#2b3550"
            clip: true
            Image { anchors.fill: parent; source: rr.item.thumb || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 96; sourceSize.height: 96 }
        }
        Column {
            anchors.left: rthumb.right
            anchors.leftMargin: 12
            anchors.right: rheart.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            Text { width: parent.width; elide: Text.ElideRight; text: rr.item.title || ""; color: rr.current ? Theme.accent : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
            Text { width: parent.width; elide: Text.ElideRight; text: rr.item.subtitle || ""; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
        MouseArea { id: rm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ytmusic.playUrl(rr.item.url) }
        IconButton {
            id: rheart
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 38; height: 38
            visible: !!rr.item.videoId
            icon: rr.fav ? "heart-on" : "heart"
            iconSize: 16
            label: rr.fav ? "Aus den Favoriten entfernen" : "Zu den Favoriten"
            onClicked: ytmusic.toggleFavorite(rr.item)
        }
    }
}
