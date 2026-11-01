import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtMultimedia
import Creative

// Creative Player – Musik, Videos und IPTV im Graphit-Look.
Window {
    id: win

    width: 1240
    height: 780
    minimumWidth: 900
    minimumHeight: 600
    visible: true
    title: nowTitle.length > 0 ? nowTitle + " – Creative Player" : "Creative Player"
    color: Theme.surface

    property string section: "music"          // music | videos | iptv
    property var queueModel: null              // music, videos oder iptv
    property int queueIndex: -1
    property string nowTitle: ""
    property string nowSubtitle: ""
    property bool shuffle: false
    property bool repeat: false
    property bool fullscreen: false
    readonly property bool playing: player.playbackState === MediaPlayer.PlayingState
    readonly property bool showVideoPage: section === "videos" && player.hasVideo && queueModel !== iptv

    // ---- Wiedergabe ---------------------------------------------------------------
    function playFrom(model, row) {
        const item = model.get(row)
        if (!item || !item.url)
            return
        errorBox.text = ""
        queueModel = model
        queueIndex = row
        nowTitle = item.title
        nowSubtitle = item.subtitle
        player.source = item.url
        player.play()
        if (model === iptv)
            settings.lastChannel = item.url
    }

    function step(delta) {
        if (!queueModel || queueModel.count === 0)
            return
        let row
        if (shuffle && queueModel !== iptv)
            row = Math.floor(Math.random() * queueModel.count)
        else
            row = (queueIndex + delta + queueModel.count) % queueModel.count
        playFrom(queueModel, row)
    }

    function togglePlay() {
        if (playing)
            player.pause()
        else if (player.source.toString().length > 0)
            player.play()
    }

    // Wiedergabe ganz beenden (z. B. IPTV-Sender ausschalten)
    function stopPlayback() {
        if (fullscreen)
            setFullscreen(false)
        player.stop()
        player.source = ""
        queueModel = null
        queueIndex = -1
        nowTitle = ""
        nowSubtitle = ""
    }

    function setFullscreen(on) {
        if (on && !player.hasVideo)
            return
        fullscreen = on
        if (on)
            win.showFullScreen()
        else
            win.showNormal()
    }

    function playStartFile(url) {
        const name = decodeURIComponent(url.toString().split("/").pop())
        const isVideo = /\.(mp4|mkv|webm|avi|mov|m4v|wmv|ts|mpe?g)$/i.test(name)
        section = isVideo ? "videos" : "music"
        queueModel = null
        queueIndex = -1
        nowTitle = name.replace(/\.[^.]+$/, "")
        nowSubtitle = ""
        player.source = url
        player.play()
    }

    MediaPlayer {
        id: player
        audioOutput: AudioOutput {
            volume: settings.volume
        }
        videoOutput: win.fullscreen ? fullVideo
                   : (win.queueModel === iptv ? iptvPage.videoOutput : videoPage.videoOutput)
        onMediaStatusChanged: {
            if (mediaStatus !== MediaPlayer.EndOfMedia || win.queueModel === iptv)
                return
            if (win.repeat) {
                player.position = 0
                player.play()
            } else if (win.queueModel) {
                win.step(1)
            }
        }
        onErrorOccurred: (error, message) => {
            errorBox.text = win.queueModel === iptv
                ? "Dieser Sender ist gerade nicht erreichbar. Probiere einen anderen."
                : "Diese Datei kann nicht abgespielt werden."
        }
    }

    // ---- Normale Ansicht ------------------------------------------------------------
    Item {
        anchors.fill: parent
        visible: !win.fullscreen

        Rectangle {
            id: sidebar
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: playerBar.visible ? playerBar.top : parent.bottom
            width: 230
            color: Theme.footer

            Column {
                anchors.fill: parent
                anchors.margins: 12
                anchors.topMargin: 18
                spacing: 2

                Row {
                    leftPadding: 10
                    bottomPadding: 18
                    spacing: 10
                    Rectangle {
                        width: 32
                        height: 32
                        radius: 10
                        color: Theme.accent
                        SvgIcon { anchors.centerIn: parent; name: "player"; size: 14 }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Creative Player"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                        font.bold: true
                    }
                }

                Repeater {
                    model: [
                        { key: "music", label: "Musik", icon: "music" },
                        { key: "videos", label: "Videos", icon: "video" },
                        { key: "iptv", label: "IPTV", icon: "tv" }
                    ]
                    delegate: Rectangle {
                        id: navItem
                        required property var modelData
                        readonly property bool current: win.section === modelData.key
                        width: parent.width
                        height: 40
                        radius: Theme.radiusRow
                        color: current ? Theme.hover : (navMouse.containsMouse ? Theme.subtle : "transparent")

                        Rectangle {
                            x: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: 3
                            height: 14
                            radius: 2
                            color: Theme.accent
                            visible: navItem.current
                        }
                        SvgIcon {
                            id: navIcon
                            x: 16
                            anchors.verticalCenter: parent.verticalCenter
                            name: navItem.modelData.icon
                            size: 17
                        }
                        Text {
                            anchors.left: navIcon.right
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: navItem.modelData.label
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: navItem.current
                        }
                        MouseArea {
                            id: navMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.section = navItem.modelData.key
                        }
                        Accessible.role: Accessible.PageTab
                        Accessible.name: modelData.label
                    }
                }
            }
        }

        Item {
            id: content
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: playerBar.visible ? playerBar.top : parent.bottom

            LibraryView {
                anchors.fill: parent
                visible: win.section === "music"
                model: music
                heading: "Musik"
                emptyText: "Noch keine Musik gefunden. Lege deine Musikdateien in den Ordner „Musik“."
                playingUrl: win.queueModel === music ? player.source.toString() : ""
                onPlay: (row) => win.playFrom(music, row)
            }

            LibraryView {
                anchors.fill: parent
                visible: win.section === "videos" && !win.showVideoPage
                model: videos
                heading: "Videos"
                showAlbum: false
                emptyText: "Noch keine Videos gefunden. Lege deine Videos in den Ordner „Videos“."
                playingUrl: win.queueModel === videos ? player.source.toString() : ""
                onPlay: (row) => win.playFrom(videos, row)
            }

            VideoView {
                id: videoPage
                anchors.fill: parent
                visible: win.showVideoPage
                title: win.nowTitle
                onBack: {
                    player.stop()
                    win.queueModel = null
                    win.nowTitle = ""
                }
                onFullscreenRequested: win.setFullscreen(true)
            }

            IptvView {
                id: iptvPage
                anchors.fill: parent
                visible: win.section === "iptv"
                host: win
                mediaPlayer: player
            }
        }

        PlayerBar {
            id: playerBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: win.section !== "iptv"
            host: win
            mediaPlayer: player
        }

        // Fehlerhinweis
        Rectangle {
            anchors.horizontalCenter: content.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 16
            visible: errorBox.text.length > 0
            width: errorBox.implicitWidth + 32
            height: 40
            radius: 10
            color: Theme.raised
            border.color: Theme.flame
            border.width: 1
            Text {
                id: errorBox
                anchors.centerIn: parent
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            Timer {
                running: errorBox.text.length > 0
                interval: 6000
                onTriggered: errorBox.text = ""
            }
        }
    }

    // ---- Vollbild ---------------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        visible: win.fullscreen
        color: "black"

        VideoOutput {
            id: fullVideo
            anchors.fill: parent
            fillMode: VideoOutput.PreserveAspectFit
        }

        Rectangle {
            id: fullInfo
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 80
            color: Qt.rgba(11 / 255, 13 / 255, 17 / 255, 0.75)
            opacity: fullMouse.containsMouse && infoTimer.running ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200 } }
            Text {
                x: 24
                anchors.verticalCenter: parent.verticalCenter
                text: win.nowTitle + "   ·   Esc beendet das Vollbild"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.bold: true
            }
        }

        Timer { id: infoTimer; interval: 2500 }

        MouseArea {
            id: fullMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: infoTimer.running ? Qt.ArrowCursor : Qt.BlankCursor
            onPositionChanged: infoTimer.restart()
            onDoubleClicked: win.setFullscreen(false)
        }
    }

    // ---- Tastatur -------------------------------------------------------------------------
    Shortcut { sequence: "Esc"; enabled: win.fullscreen; onActivated: win.setFullscreen(false) }
    Shortcut { sequence: "F11"; onActivated: win.setFullscreen(!win.fullscreen) }
    Shortcut { sequence: "Space"; onActivated: win.togglePlay() }
    Shortcut { sequences: ["MediaStop"]; onActivated: win.stopPlayback() }
    Shortcut { sequences: [StandardKey.MoveToPreviousPage]; onActivated: win.step(-1) }   // Bild auf
    Shortcut { sequences: [StandardKey.MoveToNextPage]; onActivated: win.step(1) }        // Bild ab
    Shortcut { sequence: "Ctrl+Left"; onActivated: win.step(-1) }
    Shortcut { sequence: "Ctrl+Right"; onActivated: win.step(1) }

    Component.onCompleted: {
        if (startFiles.length > 0)
            playStartFile(startFiles[0])
    }
}
