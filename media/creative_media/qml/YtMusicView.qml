import QtQuick
import QtQuick.Controls.Basic
import Creative

// YouTube Music: die offizielle Webseite im Creative Player.
// Oben unsere Leiste (Zurück, Startseite, Charts, Neu laden, gerade läuft, Herz),
// rechts aufklappbar die Favoriten (Lesezeichen – ein Klick spielt im offiziellen Player).
Item {
    id: root
    property bool showFavs: false

    // ---- Leiste --------------------------------------------------------------------------
    Rectangle {
        id: head
        anchors.left: parent.left
        anchors.right: parent.right
        height: 58
        color: Theme.footer

        Row {
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            IconButton { width: 38; height: 38; icon: "back"; iconSize: 16; label: "Zurück"; enabled: webLoader.item !== null; onClicked: webLoader.item.goBack() }
            IconButton { width: 38; height: 38; icon: "forward"; iconSize: 16; label: "Vor"; enabled: webLoader.item !== null; onClicked: webLoader.item.goForward() }
            IconButton { width: 38; height: 38; icon: "home"; iconSize: 16; label: "Startseite"; onClicked: ytmusic.openUrl(ytmusic.home) }
            Rectangle {
                width: chartsRow.implicitWidth + 22
                height: 34
                anchors.verticalCenter: parent.verticalCenter
                radius: 17
                color: cm.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06)
                Row {
                    id: chartsRow
                    anchors.centerIn: parent
                    spacing: 6
                    SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: "ytmusic"; size: 14 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Charts"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
                }
                MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ytmusic.openUrl(ytmusic.charts) }
                Accessible.role: Accessible.Button
                Accessible.name: "Charts"
            }
            IconButton { width: 38; height: 38; icon: "refresh"; iconSize: 16; label: "Neu laden"; enabled: webLoader.item !== null; onClicked: webLoader.item.reload() }
        }

        // Gerade läuft
        Row {
            anchors.centerIn: parent
            spacing: 10
            visible: ytmusic.nowTitle.length > 0
            Rectangle {
                width: 38; height: 38; radius: 8
                anchors.verticalCenter: parent.verticalCenter
                color: "#2b3550"
                clip: true
                Image { anchors.fill: parent; source: ytmusic.nowThumb; fillMode: Image.PreserveAspectCrop; asynchronous: true }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(300, root.width * 0.28)
                Text { width: parent.width; elide: Text.ElideRight; text: ytmusic.nowTitle; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                Text { width: parent.width; elide: Text.ElideRight; text: ytmusic.nowArtist; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 38; height: 38
                icon: ytmusic.currentFavorite ? "heart-on" : "heart"
                iconSize: 17
                enabled: ytmusic.nowVideo.length > 0
                label: ytmusic.currentFavorite ? "Aus den Favoriten entfernen" : "Zu den Favoriten"
                onClicked: ytmusic.toggleCurrentFavorite()
            }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            width: favRow.implicitWidth + 24
            height: 34
            radius: 17
            color: root.showFavs ? Theme.accent : (fm.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06))
            Row {
                id: favRow
                anchors.centerIn: parent
                spacing: 7
                SvgIcon { anchors.verticalCenter: parent.verticalCenter; visible: !root.showFavs; name: "heart"; size: 14 }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Favoriten" + (ytmusic.favoriteCount > 0 ? "  " + ytmusic.favoriteCount : "")
                    color: root.showFavs ? Theme.accentText : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.bold: true
                }
            }
            MouseArea { id: fm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.showFavs = !root.showFavs }
            Accessible.role: Accessible.Button
            Accessible.name: "Favoriten"
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    // ---- Offizielle Webseite --------------------------------------------------------------------
    Loader {
        id: webLoader
        anchors.left: parent.left
        anchors.right: favPane.visible ? favPane.left : parent.right
        anchors.top: head.bottom
        anchors.bottom: parent.bottom
        active: webEngineAvailable
        source: "YtWeb.qml"
    }

    // Ohne eingebauten Browser-Baustein: im eigenen Fenster öffnen
    Column {
        anchors.centerIn: webLoader
        visible: !webEngineAvailable
        spacing: 14
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "YouTube Music öffnet sich in einem eigenen Fenster."
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }
        CButton {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "YouTube Music öffnen"
            primary: true
            onClicked: Qt.openUrlExternally(ytmusic.home)
        }
    }

    // ---- Favoriten ---------------------------------------------------------------------------------
    Rectangle {
        id: favPane
        anchors.right: parent.right
        anchors.top: head.bottom
        anchors.bottom: parent.bottom
        width: 320
        visible: root.showFavs
        color: Theme.footer
        Rectangle { width: 1; height: parent.height; color: Theme.hairline }

        Text {
            id: favTitle
            x: 20
            y: 16
            text: "Favoriten"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.bold: true
        }
        Text {
            anchors.left: favTitle.left
            anchors.top: favTitle.bottom
            anchors.topMargin: 2
            width: parent.width - 40
            wrapMode: Text.WordWrap
            text: "Tippe oben auf das Herz, um ein Lied zu merken. Abgespielt wird im offiziellen YouTube-Music-Player."
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 11
        }

        ListView {
            id: favList
            anchors.fill: parent
            anchors.topMargin: 86
            anchors.margins: 10
            clip: true
            spacing: 4
            model: ytmusic
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.2) } }
            delegate: Rectangle {
                id: fr
                required property string title
                required property string artist
                required property string thumb
                required property string videoId
                readonly property bool current: videoId === ytmusic.nowVideo
                width: ListView.view.width
                height: 58
                radius: 10
                color: current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14) : (frm.containsMouse ? Theme.hover : "transparent")
                Rectangle {
                    id: fthumb
                    x: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 42; height: 42; radius: 8
                    color: "#2b3550"
                    clip: true
                    Image { anchors.fill: parent; source: fr.thumb; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 96; sourceSize.height: 96 }
                }
                Column {
                    anchors.left: fthumb.right
                    anchors.leftMargin: 10
                    anchors.right: fdel.left
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Text { width: parent.width; elide: Text.ElideRight; text: fr.title; color: fr.current ? Theme.accent : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
                    Text { width: parent.width; elide: Text.ElideRight; text: fr.artist; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
                MouseArea { id: frm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ytmusic.playFavorite(fr.videoId) }
                Rectangle {
                    id: fdel
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    width: 32; height: 32; radius: 16
                    color: fdm.containsMouse ? Theme.hover : "transparent"
                    SvgIcon { anchors.centerIn: parent; name: "heart-on"; size: 15 }
                    MouseArea { id: fdm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ytmusic.removeFavorite(fr.videoId) }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Aus den Favoriten entfernen"
                }
            }
        }
        Text {
            anchors.centerIn: favList
            visible: favList.count === 0
            width: favList.width - 30
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Noch keine Favoriten."
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
    }
}
