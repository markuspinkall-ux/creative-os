import QtQuick
import QtQuick.Templates as GibeonT
import QtQuick.Controls.Basic
import Creative

// Podcasts im Player: oben Suche (Texteingabe) und Reiter, darunter Kacheln mit Cover.
// Klick auf eine Kachel öffnet den Podcast mit seinen Folgen; abgespielt wird über die
// Wiedergabeleiste des Players.
Item {
    id: root
    objectName: "podcastView"
    property var host: null
    property string tab: "discover"          // discover | following | offline
    readonly property bool detail: !!podcasts.selected.url

    // Beim ersten Öffnen: beliebte Podcasts als Kacheln
    onVisibleChanged: if (visible && podcasts.catalogue.length === 0) podcasts.loadTop()

    // Suche per Texteingabe (auch für den Selbsttest)
    function runSearch(text) {
        const value = (text || "").trim()
        if (!value.length)
            return
        searchField.text = value
        tab = "discover"
        if (/^https?:\/\//i.test(value))
            podcasts.openFeed(value)
        else {
            podcasts.back()
            podcasts.search(value)
        }
    }

    // ---- Kopf: Suche und Reiter -----------------------------------------------------------------
    Rectangle {
        id: head
        anchors.left: parent.left
        anchors.right: parent.right
        height: 64
        color: Theme.footer
        z: 2

        Rectangle {
            id: searchBox
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(440, parent.width * 0.42)
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
                placeholderText: "Podcasts suchen – Name, Thema oder RSS-Adresse"
                placeholderTextColor: Theme.textMuted
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                background: Item {}
                selectByMouse: true
                onAccepted: root.runSearch(text)
                Keys.onEscapePressed: text = ""
            }
        }

        Row {
            anchors.left: searchBox.right
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            Repeater {
                model: [["discover", "Entdecken"], ["following", "Abos"], ["offline", "Downloads"]]
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool cur: root.tab === modelData[0] && !root.detail
                    width: tl.implicitWidth + 28
                    height: 34
                    radius: 17
                    color: cur ? Theme.accent : (tm.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
                    Text {
                        id: tl
                        anchors.centerIn: parent
                        text: modelData[1]
                        color: parent.cur ? Theme.accentText : Theme.text
                        font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true
                    }
                    MouseArea {
                        id: tm
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            podcasts.back()
                            root.tab = modelData[0]
                            if (root.tab === "discover" && podcasts.catalogue.length === 0)
                                podcasts.loadTop()
                        }
                    }
                }
            }
        }
    }

    // ---- Kacheln (Entdecken, Abos) ------------------------------------------------------------------
    Flickable {
        id: grid
        anchors.top: head.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: !root.detail && root.tab !== "offline"
        clip: true
        contentHeight: gridCol.height + 40
        ScrollBar.vertical: ScrollBar {}

        Column {
            id: gridCol
            x: 24
            y: 20
            width: grid.width - 48
            spacing: 14

            Text {
                text: root.tab === "following" ? "Deine Abos" : (podcasts.heading || "Podcasts")
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 20
                font.bold: true
            }
            // Themen zum schnellen Stöbern
            Flow {
                width: parent.width
                spacing: 6
                visible: root.tab === "discover"
                Repeater {
                    model: ["Beliebt", "Nachrichten", "Wissen", "Comedy", "True Crime", "Gaming", "Sport", "Geschichte", "Technik", "Musik"]
                    delegate: Rectangle {
                        required property string modelData
                        width: ct.implicitWidth + 24
                        height: 30
                        radius: 15
                        color: cm.containsMouse ? Theme.tint(0.1) : Theme.tint(0.05)
                        Text { id: ct; anchors.centerIn: parent; text: modelData; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12 }
                        MouseArea {
                            id: cm
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (modelData === "Beliebt") {
                                    searchField.text = ""
                                    podcasts.loadTop()
                                } else {
                                    root.runSearch(modelData)
                                }
                            }
                        }
                    }
                }
            }
            Text {
                visible: text.length > 0
                width: parent.width
                text: podcasts.status
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }
            BusyIndicator {
                visible: podcasts.loading && tiles.count === 0
                running: visible
                width: 36; height: 36
            }
            Text {
                visible: root.tab === "following" && podcasts.following.length === 0
                text: "Du folgst noch keinem Podcast. Öffne einen Podcast und tippe auf „Folgen“."
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            Flow {
                width: parent.width
                spacing: 8
                Repeater {
                    id: tiles
                    model: root.tab === "following" ? podcasts.following : podcasts.catalogue
                    delegate: ShowTile { required property var modelData; show: modelData }
                }
            }
        }
    }

    // ---- Ein Podcast: Kopf mit Cover und die Folgen ------------------------------------------------
    Item {
        id: page
        anchors.top: head.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.detail || root.tab === "offline"

        Item {
            id: pageHead
            x: 24
            y: 20
            width: parent.width - 48
            height: root.detail ? 150 : 40

            // Zurück zu den Kacheln
            Rectangle {
                id: backBtn
                visible: root.detail
                width: 34; height: 34; radius: 17
                color: bm.containsMouse ? Theme.tint(0.12) : Theme.tint(0.06)
                SvgIcon { anchors.centerIn: parent; name: "chevron-left"; size: 14 }
                MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: podcasts.back() }
                Accessible.role: Accessible.Button
                Accessible.name: "Zurück"
            }
            Rectangle {
                id: cover
                visible: root.detail
                anchors.left: backBtn.right
                anchors.leftMargin: 16
                width: 150; height: 150; radius: 14
                color: "#2b3550"
                clip: true
                Image { anchors.fill: parent; source: podcasts.selected.image || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 300; sourceSize.height: 300 }
                SvgIcon { anchors.centerIn: parent; name: "speaker"; size: 30; visible: !podcasts.selected.image }
            }
            Column {
                anchors.left: root.detail ? cover.right : parent.left
                anchors.leftMargin: root.detail ? 20 : 0
                anchors.right: parent.right
                anchors.verticalCenter: root.detail ? cover.verticalCenter : undefined
                spacing: 6
                Text {
                    width: parent.width
                    text: root.detail ? (podcasts.selected.title || "Podcast") : "Heruntergeladene Folgen"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 22
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: root.detail && text.length > 0
                    text: podcasts.selected.author || ""
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    elide: Text.ElideRight
                }
                Row {
                    visible: root.detail
                    spacing: 8
                    topPadding: 6
                    CButton {
                        text: "Neueste abspielen"
                        primary: true
                        enabled: episodes.count > 0
                        onClicked: root.host.playPodcast(podcasts.playlist, 0)
                    }
                    CButton {
                        text: podcasts.followed ? "Entfolgen" : "Folgen"
                        onClicked: podcasts.toggleFollow()
                    }
                }
            }
        }

        Text {
            id: pageStatus
            anchors.top: pageHead.bottom
            anchors.topMargin: 14
            x: 24
            visible: text.length > 0
            text: root.detail && podcasts.loading ? "Folgen werden geladen …"
                  : root.detail ? podcasts.status
                  : (podcasts.offline.length === 0 ? "Noch keine Folgen heruntergeladen." : "")
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }

        ListView {
            id: episodes
            anchors.top: pageStatus.visible ? pageStatus.bottom : pageHead.bottom
            anchors.topMargin: 14
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            clip: true
            spacing: 4
            model: root.tab === "offline" && !root.detail ? podcasts.offline : podcasts.playlist
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool downloaded: podcasts.downloadedKeys.includes(modelData.key)
                readonly property bool downloading: podcasts.pendingKeys.includes(modelData.key)
                readonly property bool current: root.host && root.host.nowKey === modelData.key
                width: ListView.view.width - 10
                height: 64
                radius: Theme.radiusRow
                color: current ? Theme.raised : (rm.containsMouse ? Theme.hover : "transparent")
                MouseArea {
                    id: rm
                    anchors.fill: parent
                    hoverEnabled: true
                    onDoubleClicked: root.host.playPodcast(episodes.model, row.index)
                }
                Rectangle {
                    id: thumb
                    x: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 48; height: 48; radius: 8
                    color: "#2b3550"
                    clip: true
                    Image { anchors.fill: parent; source: row.modelData.image || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 96; sourceSize.height: 96 }
                }
                Column {
                    anchors.left: thumb.right
                    anchors.leftMargin: 12
                    anchors.right: actions.left
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 3
                    Text { width: parent.width; elide: Text.ElideRight; text: row.modelData.title || ""; color: row.current ? Theme.accent : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                    Text { width: parent.width; elide: Text.ElideRight; text: (root.detail ? row.modelData.date : row.modelData.show) || ""; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
                Row {
                    id: actions
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Rectangle {
                        width: 36; height: 36; radius: 18
                        color: Theme.accent
                        SvgIcon { anchors.centerIn: parent; name: "play-dark"; size: 13 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.host.playPodcast(episodes.model, row.index) }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Abspielen"
                    }
                    CButton {
                        text: row.downloading ? "Lädt …" : (row.downloaded ? "Löschen" : "Download")
                        enabled: !row.downloading
                        onClicked: row.downloaded ? podcasts.removeDownload(row.modelData.key) : podcasts.download(row.modelData)
                    }
                }
            }
        }
    }

    // ---- Kachel eines Podcasts ------------------------------------------------------------------------
    component ShowTile: Rectangle {
        id: tile
        property var show: ({})
        width: 170
        height: 226
        radius: 14
        color: sm.containsMouse ? Theme.hover : "transparent"
        Rectangle {
            id: art
            x: 6; y: 6
            width: 158; height: 158; radius: 12
            color: "#2b3550"
            clip: true
            Image { anchors.fill: parent; source: tile.show.image || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 320; sourceSize.height: 320 }
            SvgIcon { anchors.centerIn: parent; name: "speaker"; size: 28; visible: !tile.show.image }
        }
        Column {
            x: 8
            anchors.top: art.bottom
            anchors.topMargin: 8
            width: parent.width - 16
            spacing: 2
            Text { width: parent.width; elide: Text.ElideRight; text: tile.show.title || ""; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
            Text { width: parent.width; elide: Text.ElideRight; text: tile.show.author || ""; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
        }
        MouseArea {
            id: sm
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: podcasts.openShow(tile.show)
        }
        Accessible.role: Accessible.Button
        Accessible.name: (show.title || "Podcast") + " öffnen"
    }
}
