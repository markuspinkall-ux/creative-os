import QtQuick
import QtMultimedia
import Creative

// Wiedergabeleiste unten: Titel, Steuerung, Fortschritt, Lautstärke.
Rectangle {
    id: bar

    property var host
    property var mediaPlayer

    function fmt(ms) {
        if (!ms || ms < 0)
            return "0:00"
        const s = Math.floor(ms / 1000)
        const h = Math.floor(s / 3600)
        const m = Math.floor((s % 3600) / 60)
        const sec = (s % 60).toString().padStart(2, "0")
        return h > 0 ? h + ":" + m.toString().padStart(2, "0") + ":" + sec : m + ":" + sec
    }

    height: 92
    color: Theme.footer

    Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top }

    // Links: Titel
    Row {
        anchors.left: parent.left
        anchors.leftMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width * 0.3
        spacing: 14

        Rectangle {
            width: 56
            height: 56
            radius: 12
            color: "#2b3550"
            clip: true
            Rectangle { x: 30; y: 26; width: 54; height: 54; radius: 27; color: Theme.accent }
            Rectangle { x: 8; y: 8; width: 18; height: 18; radius: 9; color: Theme.flame }
            Image {
                anchors.fill: parent
                visible: bar.host.nowCover.length > 0
                source: bar.host.nowCover
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 120
                sourceSize.height: 120
            }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 70
            spacing: 5
            Text {
                width: parent.width
                elide: Text.ElideRight
                text: bar.host.nowTitle.length > 0 ? bar.host.nowTitle : "Nichts ausgewählt"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.bold: true
            }
            Text {
                width: parent.width
                elide: Text.ElideRight
                text: bar.host.nowSubtitle
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }
    }

    // Mitte: Steuerung + Fortschritt
    Column {
        anchors.centerIn: parent
        width: parent.width * 0.38
        spacing: 6

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 12

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 34; height: 34
                icon: bar.host.shuffle ? "shuffle-on" : "shuffle"
                iconSize: 17
                label: "Zufällige Wiedergabe"
                active: bar.host.shuffle
                onClicked: bar.host.shuffle = !bar.host.shuffle
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 38; height: 38
                icon: "prev"
                iconSize: 20
                label: "Vorheriger Titel"
                onClicked: bar.host.step(-1)
            }
            Rectangle {
                width: 48
                height: 48
                radius: 24
                color: playMouse.pressed ? Qt.darker(Theme.accent, 1.15) : Theme.accent
                SvgIcon {
                    anchors.centerIn: parent
                    name: bar.host.playing ? "pause-dark" : "play-dark"
                    size: 18
                }
                MouseArea {
                    id: playMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bar.host.togglePlay()
                }
                Accessible.role: Accessible.Button
                Accessible.name: bar.host.playing ? "Pause" : "Abspielen"
                Accessible.onPressAction: bar.host.togglePlay()
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 38; height: 38
                icon: "next"
                iconSize: 20
                label: "Nächster Titel"
                onClicked: bar.host.step(1)
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 34; height: 34
                icon: bar.host.repeat ? "repeat-on" : "repeat"
                iconSize: 17
                label: "Wiederholen"
                active: bar.host.repeat
                onClicked: bar.host.repeat = !bar.host.repeat
            }
        }

        Row {
            width: parent.width
            spacing: 10
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: 44
                horizontalAlignment: Text.AlignRight
                text: bar.fmt(bar.mediaPlayer.position)
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 11
            }
            CSlider {
                id: seek
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 108
                from: 0
                to: Math.max(1, bar.mediaPlayer.duration)
                stepSize: 0
                enabled: bar.mediaPlayer.seekable
                onMoved: bar.mediaPlayer.position = value
                Binding on value {
                    when: !seek.pressed
                    value: bar.mediaPlayer.position
                }
                Accessible.name: "Position"
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: 44
                text: bar.fmt(bar.mediaPlayer.duration)
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 11
            }
        }
    }

    // Rechts: Lautstärke
    Row {
        anchors.right: parent.right
        anchors.rightMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        spacing: 10
        SvgIcon {
            anchors.verticalCenter: parent.verticalCenter
            name: settings.volume > 0 ? "volume" : "volume-off"
            size: 17
        }
        CSlider {
            anchors.verticalCenter: parent.verticalCenter
            width: 120
            from: 0
            to: 1
            stepSize: 0.01
            value: settings.volume
            onMoved: settings.volume = value
            Accessible.name: "Lautstärke"
        }
    }
}
