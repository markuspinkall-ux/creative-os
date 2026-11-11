import QtQuick
import QtQuick.Controls.Basic
import QtMultimedia
import Creative

// IPTV: links Senderliste mit Suche und Kategorien, rechts das Bild.
// Zurück/Weiter oder Bild auf/ab wechselt den Sender, Doppelklick = Vollbild.
Item {
    id: root

    property var host
    property var mediaPlayer
    property alias videoOutput: video
    readonly property bool active: host.queueModel === iptv

    // ---- Senderliste ------------------------------------------------------------------
    Item {
        id: listPane
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 24
        width: 340

        Text {
            id: heading
            text: "IPTV"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 24
            font.bold: true
        }
        Text {
            anchors.right: parent.right
            anchors.baseline: heading.baseline
            text: iptv.total + " Sender"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 12
        }

        TextField {
            id: search
            anchors.top: heading.bottom
            anchors.topMargin: 14
            width: parent.width
            height: 38
            leftPadding: 38
            placeholderText: "Sender suchen"
            placeholderTextColor: Theme.textMuted
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            selectByMouse: true
            background: Rectangle { radius: 19; color: Theme.ground; border.color: search.activeFocus ? Theme.accent : Theme.hairline; border.width: 1 }
            SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 15 }
            onTextChanged: iptv.filterText = text
            Accessible.name: "Sender suchen"
        }

        Flow {
            id: cats
            anchors.top: search.bottom
            anchors.topMargin: 12
            width: parent.width
            spacing: 6
            Repeater {
                model: iptv.categories
                delegate: Rectangle {
                    id: chip
                    required property string modelData
                    readonly property bool current: iptv.category === modelData
                    width: chipText.implicitWidth + 24
                    height: 30
                    radius: 15
                    color: current ? Theme.accent : (chipMouse.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
                    Text {
                        id: chipText
                        anchors.centerIn: parent
                        text: chip.modelData
                        color: chip.current ? Theme.accentText : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                    }
                    MouseArea {
                        id: chipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: iptv.category = chip.modelData
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Kategorie " + modelData
                }
            }
        }

        ListView {
            id: channels
            anchors.top: cats.bottom
            anchors.topMargin: 12
            anchors.bottom: parent.bottom
            width: parent.width
            clip: true
            model: iptv
            spacing: 2
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {
                contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Theme.tint(0.2) }
            }
            delegate: Rectangle {
                id: ch
                required property int index
                required property string name
                required property string group
                required property string url
                required property int number
                readonly property bool current: root.active && root.mediaPlayer.source.toString() === url

                width: ListView.view.width
                height: 42
                radius: Theme.radiusRow
                color: current ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.12)
                               : (chMouse.containsMouse ? Theme.hover : "transparent")
                Text {
                    id: num
                    x: 12
                    width: 34
                    anchors.verticalCenter: parent.verticalCenter
                    text: ch.number
                    color: ch.current ? Theme.accent : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.bold: true
                }
                Text {
                    anchors.left: num.right
                    anchors.right: grp.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: ch.name
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: ch.current
                }
                Text {
                    id: grp
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, 110)
                    elide: Text.ElideRight
                    text: ch.group
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                }
                MouseArea {
                    id: chMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.host.playFrom(iptv, ch.index)
                }
                Accessible.role: Accessible.ListItem
                Accessible.name: "Sender " + ch.number + " " + ch.name
                Accessible.onPressAction: root.host.playFrom(iptv, ch.index)
            }
        }

        Text {
            anchors.centerIn: channels
            width: channels.width - 20
            visible: channels.count === 0
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: iptv.loading ? "Senderliste wird geladen …" : (iptv.total === 0 ? iptv.status : "Kein Sender gefunden.")
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
    }

    // ---- Bild und Steuerung -----------------------------------------------------------
    Column {
        anchors.left: listPane.right
        anchors.leftMargin: 24
        anchors.right: parent.right
        anchors.rightMargin: 24
        anchors.top: parent.top
        anchors.topMargin: 24
        spacing: 14

        Rectangle {
            id: screen
            width: parent.width
            height: width * 9 / 16
            radius: 14
            color: "#0b0d11"
            clip: true
            border.color: Theme.hairline
            border.width: 1

            VideoOutput {
                id: video
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
            }

            Column {
                anchors.centerIn: parent
                spacing: 12
                visible: !root.active
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 74
                    height: 74
                    radius: 37
                    color: Theme.tint(0.08)
                    SvgIcon { anchors.centerIn: parent; name: "play"; size: 28 }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Wähle links einen Sender aus"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                }
            }

            Rectangle {
                x: 16
                y: 16
                visible: root.active
                width: liveText.implicitWidth + 20
                height: 24
                radius: 6
                color: "#e5484d"
                Text {
                    id: liveText
                    anchors.centerIn: parent
                    text: "LIVE"
                    color: "white"
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 66
                visible: root.active
                color: Qt.rgba(11 / 255, 13 / 255, 17 / 255, 0.75)
                Column {
                    x: 18
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4
                    Text {
                        text: root.host.nowTitle
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 16
                        font.bold: true
                    }
                    Text {
                        text: root.mediaPlayer.mediaStatus === MediaPlayer.LoadingMedia
                              || root.mediaPlayer.mediaStatus === MediaPlayer.BufferingMedia
                              ? "Wird geladen …" : "Vollbild per Doppelklick · Esc beendet"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                onDoubleClicked: root.host.setFullscreen(true)
            }
        }

        Item {
            width: parent.width
            height: 38

            Row {
                spacing: 8
                CButton { text: "■  Stopp"; primary: root.active; enabled: root.active; onClicked: root.host.stopPlayback() }
                CButton { text: "‹  Zurück"; enabled: root.active; onClicked: root.host.step(-1) }
                CButton { text: "Weiter  ›"; enabled: root.active; onClicked: root.host.step(1) }
                CButton { text: "Vollbild"; enabled: root.active; onClicked: root.host.setFullscreen(true) }
            }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: settings.volume > 0 ? "volume" : "volume-off"; size: 17 }
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

        // Quelle der Senderliste
        Rectangle {
            width: parent.width
            height: sourceCol.implicitHeight + 28
            radius: 14
            color: Theme.subtle

            Column {
                id: sourceCol
                x: 16
                y: 14
                width: parent.width - 32
                spacing: 10

                Item {
                    width: parent.width
                    height: 40
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        Text {
                            text: "Senderliste (M3U)"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            text: iptv.sourceName + " · " + iptv.status
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                        }
                    }
                    Row {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8
                        CButton { text: "Aktualisieren"; enabled: !iptv.loading; onClicked: iptv.reload() }
                        CButton {
                            text: "Quelle ändern"
                            primary: true
                            onClicked: {
                                sourceEdit.visible = !sourceEdit.visible
                                sourceField.text = settings.iptvSource
                                if (sourceEdit.visible)
                                    sourceField.forceActiveFocus()
                            }
                        }
                    }
                }

                Row {
                    id: sourceEdit
                    visible: false
                    width: parent.width
                    spacing: 8
                    TextField {
                        id: sourceField
                        width: parent.width - 220
                        height: 36
                        leftPadding: 12
                        placeholderText: "https://…/senderliste.m3u"
                        placeholderTextColor: Theme.textMuted
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        selectByMouse: true
                        background: Rectangle { radius: 10; color: Theme.ground; border.color: Theme.accent; border.width: 1 }
                        Keys.onReturnPressed: applySource.clicked()
                        Accessible.name: "Adresse der Senderliste"
                    }
                    CButton {
                        id: applySource
                        text: "Übernehmen"
                        primary: true
                        onClicked: {
                            iptv.setSource(sourceField.text)
                            sourceEdit.visible = false
                        }
                    }
                    CButton { text: "Abbrechen"; onClicked: sourceEdit.visible = false }
                }
            }
        }
    }
}
