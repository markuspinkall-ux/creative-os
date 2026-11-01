import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative Pictures – Sammlung und Bildansicht wie „Fotos“ bei Windows 11.
Window {
    id: win

    width: 1240
    height: 800
    minimumWidth: 760
    minimumHeight: 520
    visible: true
    title: pics.viewing ? pics.currentName + " – Creative Pictures" : "Creative Pictures"
    color: Theme.surface

    property bool fullscreen: false
    function setFullscreen(on) {
        fullscreen = on
        if (on) win.showFullScreen()
        else win.showNormal()
    }

    // ---- Sammlung ---------------------------------------------------------------------------
    Item {
        anchors.fill: parent
        visible: !pics.viewing

        Rectangle {
            id: nav
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 230
            color: Theme.footer

            Row {
                x: 18
                y: 18
                spacing: 10
                Rectangle {
                    width: 32; height: 32; radius: 10
                    color: Theme.accent
                    SvgIcon { anchors.centerIn: parent; name: "pictures"; size: 16 }
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Creative Pictures"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 15; font.bold: true }
            }

            Column {
                x: 10
                y: 76
                width: parent.width - 20
                spacing: 2
                Repeater {
                    model: [{ key: "all", label: "Alle Fotos", icon: "pictures" }, { key: "favorites", label: "Favoriten", icon: "heart" }]
                    delegate: NavRow {
                        required property var modelData
                        label: modelData.label
                        icon: modelData.icon
                        current: pics.collection === modelData.key
                        onClicked: pics.loadCollection(modelData.key)
                    }
                }
                Text {
                    topPadding: 18
                    bottomPadding: 6
                    leftPadding: 14
                    text: "Ordner"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                }
                Repeater {
                    model: pics.folders()
                    delegate: NavRow {
                        required property var modelData
                        label: modelData.label
                        icon: "folder-plus"
                        current: pics.collection === modelData.key
                        onClicked: pics.loadCollection(modelData.key)
                    }
                }
            }
        }

        Item {
            id: galleryHead
            anchors.left: nav.right
            anchors.right: parent.right
            height: 74
            Text {
                id: gTitle
                x: 28
                y: 18
                text: pics.collection === "all" ? "Alle Fotos" : (pics.collection === "favorites" ? "Favoriten" : pics.collection.split("/").pop())
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 24
                font.bold: true
            }
            Text {
                anchors.left: gTitle.left
                anchors.top: gTitle.bottom
                anchors.topMargin: 2
                text: pics.scanning ? "Bilder werden gesucht …" : (pics.count === 1 ? "1 Bild" : pics.count + " Bilder")
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
            Row {
                anchors.right: parent.right
                anchors.rightMargin: 22
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Größe"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                CSlider {
                    id: thumbSize
                    anchors.verticalCenter: parent.verticalCenter
                    width: 120
                    from: 110; to: 280; stepSize: 10
                    value: 170
                    Accessible.name: "Vorschaugröße"
                }
                IconButton { width: 38; height: 38; icon: "refresh"; iconSize: 16; label: "Neu einlesen"; onClicked: pics.reload() }
                IconButton { width: 38; height: 38; icon: "files"; iconSize: 16; label: "Ordner öffnen"; onClicked: pics.showInFolder() }
            }
        }

        ListView {
            id: months
            anchors.left: nav.right
            anchors.right: parent.right
            anchors.top: galleryHead.bottom
            anchors.bottom: parent.bottom
            anchors.leftMargin: 24
            anchors.rightMargin: 16
            clip: true
            spacing: 18
            model: pics.groups
            boundsBehavior: Flickable.StopAtBounds
            cacheBuffer: 1200
            ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 5; radius: 3; color: Qt.rgba(1, 1, 1, 0.2) } }
            delegate: Column {
                required property var modelData
                width: months.width - 12
                spacing: 10
                Text {
                    text: modelData.label
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 15
                    font.bold: true
                }
                Flow {
                    width: parent.width
                    spacing: 6
                    Repeater {
                        model: modelData.items
                        delegate: Rectangle {
                            required property var modelData
                            width: thumbSize.value
                            height: thumbSize.value
                            radius: 10
                            color: Theme.raised
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: modelData.url
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                autoTransform: true
                                cache: true
                                sourceSize.width: 320
                                sourceSize.height: 320
                                opacity: status === Image.Ready ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: 150 } }
                            }
                            Rectangle {
                                anchors.fill: parent
                                radius: 10
                                color: tm.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                                border.color: tm.containsMouse ? Theme.accent : "transparent"
                                border.width: 2
                            }
                            SvgIcon {
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 8
                                visible: pics.favorites.indexOf(modelData.path) >= 0
                                name: "heart-on"
                                size: 16
                            }
                            MouseArea {
                                id: tm
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: pics.openFromLibrary(modelData.path)
                            }
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData.name
                        }
                    }
                }
            }
        }

        Column {
            anchors.centerIn: months
            visible: !pics.scanning && pics.count === 0
            spacing: 10
            SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: pics.collection === "favorites" ? "heart" : "pictures"; size: 40 }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: pics.collection === "favorites" ? "Noch keine Favoriten – tippe beim Ansehen auf das Herz." : "Hier sind noch keine Bilder."
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 14
            }
        }
    }

    // ---- Bildansicht ---------------------------------------------------------------------------------
    Viewer {
        id: viewer
        anchors.fill: parent
        visible: pics.viewing
        host: win
    }

    // ---- Hinweis --------------------------------------------------------------------------------------
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: pics.viewing ? 120 : 20
        visible: pics.message.length > 0
        width: msg.implicitWidth + 32
        height: 38
        radius: 19
        color: Theme.raised
        border.color: Theme.hairline
        Text { id: msg; anchors.centerIn: parent; text: pics.message; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
        Timer { running: parent.visible; interval: 3500; onTriggered: pics.clearMessage() }
    }

    component NavRow: Rectangle {
        id: nr
        property string label
        property string icon
        property bool current: false
        signal clicked()
        width: parent ? parent.width : 200
        height: 40
        radius: Theme.radiusRow
        color: current ? Theme.hover : (nrm.containsMouse ? Theme.subtle : "transparent")
        Rectangle { x: 4; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 14; radius: 2; color: Theme.accent; visible: nr.current }
        SvgIcon { id: nri; x: 16; anchors.verticalCenter: parent.verticalCenter; name: nr.icon; size: 16 }
        Text {
            anchors.left: nri.right
            anchors.leftMargin: 12
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: nr.label
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.bold: nr.current
        }
        MouseArea { id: nrm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: nr.clicked() }
        Accessible.role: Accessible.PageTab
        Accessible.name: label
    }

    Component.onCompleted: if (!pics.viewing) pics.loadCollection("all")
}
