import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtMultimedia
import Creative

ApplicationWindow {
    id: window
    width: 1020
    height: 670
    minimumWidth: 740
    minimumHeight: 460
    visible: true
    color: Theme.ground
    title: "Creative Podcast"

    required property QtObject podcasts
    property string section: "discover"
    property var queue: []
    property int current: -1
    readonly property string nowPlaying: current >= 0 ? queue[current].title : ""
    readonly property bool playing: player.playbackState === MediaPlayer.PlayingState

    function start(episodes, index) {
        if (index < 0 || index >= episodes.length)
            return
        queue = episodes
        current = index
        playbackError.text = ""
        player.stop()
        player.source = podcasts.playbackUrl(queue[current])
        player.play()
    }

    function time(ms) {
        const seconds = Math.floor(ms / 1000)
        const minutes = Math.floor(seconds / 60)
        return minutes + ":" + String(seconds % 60).padStart(2, "0")
    }

    MediaPlayer {
        id: player
        audioOutput: AudioOutput {}
        onMediaStatusChanged: {
            if (mediaStatus === MediaPlayer.EndOfMedia)
                window.start(window.queue, window.current + 1)
        }
        onErrorOccurred: (error, errorString) => {
            if (error !== MediaPlayer.NoError)
                playbackError.text = "Wiedergabe fehlgeschlagen: " + errorString
        }
    }

    component Heading: Label {
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 22
        font.bold: true
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    component Hint: Label {
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 13
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Heading { text: "Creative Podcast"; Layout.fillWidth: true }
            CButton {
                text: "Entdecken"
                primary: window.section === "discover"
                onClicked: window.section = "discover"
            }
            CButton {
                text: "Abos"
                primary: window.section === "following"
                onClicked: window.section = "following"
            }
            CButton {
                text: "Downloads"
                primary: window.section === "offline"
                onClicked: window.section = "offline"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: window.section === "discover"
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Podcast, Thema oder RSS-Adresse"
                color: Theme.text
                placeholderTextColor: Theme.textMuted
                background: Rectangle { color: Theme.surface; radius: Theme.radiusRow }
                selectByMouse: true
                onAccepted: searchButton.clicked()
            }
            CButton {
                id: searchButton
                text: "Suchen / öffnen"
                enabled: !podcasts.loading && searchField.text.trim().length > 0
                onClicked: {
                    if (!enabled)
                        return
                    const value = searchField.text.trim()
                    if (/^https?:\/\//i.test(value))
                        podcasts.openFeed(value)
                    else
                        podcasts.search(value)
                }
            }
        }

        RowLayout {
            visible: window.section === "discover"
            Repeater {
                model: ["Nachrichten", "Wissen", "Comedy", "Gaming", "Sport"]
                CButton {
                    required property string modelData
                    text: modelData
                    enabled: !podcasts.loading
                    onClicked: {
                        searchField.text = modelData
                        podcasts.search(modelData)
                    }
                }
            }
        }

        Hint {
            Layout.fillWidth: true
            visible: text.length > 0
            text: podcasts.status
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Rectangle {
                Layout.preferredWidth: 270
                Layout.minimumWidth: 205
                Layout.fillHeight: true
                visible: window.section !== "offline"
                color: Theme.surface
                radius: Theme.radiusMenu

                ListView {
                    id: shows
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true
                    spacing: 4
                    model: window.section === "following" ? podcasts.following : podcasts.catalogue
                    ScrollBar.vertical: ScrollBar {}
                    delegate: ItemDelegate {
                        id: showRow
                        required property var modelData
                        width: ListView.view.width - 8
                        enabled: !podcasts.loading
                        highlighted: podcasts.selected.url === modelData.url
                        contentItem: Column {
                            Hint {
                                width: parent.width
                                text: showRow.modelData.title
                                color: Theme.text
                                font.bold: true
                            }
                            Hint { width: parent.width; text: showRow.modelData.author }
                        }
                        background: Rectangle {
                            radius: Theme.radiusRow
                            color: showRow.highlighted ? Theme.raised : (showRow.hovered ? Theme.hover : "transparent")
                        }
                        onClicked: podcasts.openShow(modelData)
                    }
                    Hint {
                        anchors.centerIn: parent
                        visible: shows.count === 0
                        text: window.section === "following" ? "Du folgst noch keinem Podcast." : "Wähle ein Thema oder suche."
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.surface
                radius: Theme.radiusMenu

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Heading {
                            Layout.fillWidth: true
                            text: window.section === "offline" ? "Offline hören" : (podcasts.selected.title || "Folgen")
                        }
                        CButton {
                            visible: window.section !== "offline" && !!podcasts.selected.url
                            enabled: !podcasts.loading
                            text: podcasts.followed ? "Entfolgen" : "Folgen"
                            onClicked: podcasts.toggleFollow()
                        }
                        CButton {
                            visible: window.section !== "offline" && !!podcasts.selected.url
                            enabled: !podcasts.loading
                            text: "Aktualisieren"
                            onClicked: podcasts.openShow(podcasts.selected)
                        }
                    }

                    ListView {
                        id: episodes
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 4
                        model: window.section === "offline" ? podcasts.offline : podcasts.playlist
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            id: episodeRow
                            required property var modelData
                            required property int index
                            readonly property bool downloaded: podcasts.downloadedKeys.includes(modelData.key)
                            readonly property bool downloading: podcasts.pendingKeys.includes(modelData.key)
                            width: ListView.view.width - 8
                            height: 56
                            radius: Theme.radiusRow
                            color: window.current >= 0 && window.queue[window.current].key === modelData.key
                                   ? Theme.raised : Theme.subtle
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Hint {
                                        Layout.fillWidth: true
                                        text: episodeRow.modelData.title
                                        color: Theme.text
                                        font.bold: true
                                    }
                                    Hint {
                                        Layout.fillWidth: true
                                        text: window.section === "offline" ? episodeRow.modelData.show : episodeRow.modelData.date
                                    }
                                }
                                CButton {
                                    text: "Abspielen"
                                    onClicked: window.start(episodes.model, episodeRow.index)
                                }
                                CButton {
                                    text: episodeRow.downloading ? "Lädt …" : (episodeRow.downloaded ? "Löschen" : "Download")
                                    enabled: !episodeRow.downloading
                                    onClicked: {
                                        if (episodeRow.downloaded)
                                            podcasts.removeDownload(episodeRow.modelData.key)
                                        else
                                            podcasts.download(episodeRow.modelData)
                                    }
                                }
                            }
                        }

                        Hint {
                            anchors.centerIn: parent
                            visible: episodes.count === 0
                            text: window.section === "offline" ? "Keine Folgen heruntergeladen."
                                  : podcasts.selected.url ? "Keine Folgen verfügbar." : "Öffne einen Podcast für seine Playlist."
                        }
                    }
                }
            }
        }

        Hint {
            id: playbackError
            Layout.fillWidth: true
            visible: text.length > 0
            color: Theme.flame
        }

        Hint {
            Layout.fillWidth: true
            text: window.nowPlaying || "Keine Wiedergabe"
            color: Theme.text
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            CButton {
                text: "Zurück"
                enabled: window.current > 0
                onClicked: window.start(window.queue, window.current - 1)
            }
            CButton {
                text: window.playing ? "Pause" : "Play"
                primary: true
                enabled: window.current >= 0
                onClicked: window.playing ? player.pause() : player.play()
            }
            CButton {
                text: "Weiter"
                enabled: window.current >= 0 && window.current + 1 < window.queue.length
                onClicked: window.start(window.queue, window.current + 1)
            }
            Hint { text: window.time(player.position) }
            Slider {
                Layout.fillWidth: true
                to: Math.max(1, player.duration)
                value: player.position
                enabled: player.seekable
                onMoved: player.position = value
            }
            Hint { text: window.time(player.duration) }
        }
    }
}
