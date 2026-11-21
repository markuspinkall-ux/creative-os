import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Creative

// Podcasts im Player (früher eigene App): Entdecken, Abos, Downloads.
// Abgespielt wird über die Wiedergabeleiste des Players.
Item {
    id: root
    property var host: null
    property string section: "discover"

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
        anchors.margins: 24
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Heading { text: "Podcasts"; Layout.fillWidth: true }
            CButton {
                text: "Entdecken"
                primary: root.section === "discover"
                onClicked: root.section = "discover"
            }
            CButton {
                text: "Abos"
                primary: root.section === "following"
                onClicked: root.section = "following"
            }
            CButton {
                text: "Downloads"
                primary: root.section === "offline"
                onClicked: root.section = "offline"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.section === "discover"
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
            visible: root.section === "discover"
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
                visible: root.section !== "offline"
                color: Theme.surface
                radius: Theme.radiusMenu

                ListView {
                    id: shows
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true
                    spacing: 4
                    model: root.section === "following" ? podcasts.following : podcasts.catalogue
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
                        text: root.section === "following" ? "Du folgst noch keinem Podcast." : "Wähle ein Thema oder suche."
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
                            text: root.section === "offline" ? "Offline hören" : (podcasts.selected.title || "Folgen")
                        }
                        CButton {
                            visible: root.section !== "offline" && !!podcasts.selected.url
                            enabled: !podcasts.loading
                            text: podcasts.followed ? "Entfolgen" : "Folgen"
                            onClicked: podcasts.toggleFollow()
                        }
                        CButton {
                            visible: root.section !== "offline" && !!podcasts.selected.url
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
                        model: root.section === "offline" ? podcasts.offline : podcasts.playlist
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
                            color: root.host && root.host.nowKey === modelData.key
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
                                        text: root.section === "offline" ? episodeRow.modelData.show : episodeRow.modelData.date
                                    }
                                }
                                CButton {
                                    text: "Abspielen"
                                    onClicked: root.host.playPodcast(episodes.model, episodeRow.index)
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
                            text: root.section === "offline" ? "Keine Folgen heruntergeladen."
                                  : podcasts.selected.url ? "Keine Folgen verfügbar." : "Öffne einen Podcast für seine Playlist."
                        }
                    }
                }
            }
        }

    }
}
