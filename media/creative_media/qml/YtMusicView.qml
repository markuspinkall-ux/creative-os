import QtQuick
import QtQuick.Controls.Basic
import Creative

// YouTube Music: oben die Top 10 aus Deutschland, Suche nach Liedern,
// ein Klick spielt direkt im Player ab.
Item {
    id: root

    property var model          // ytmusic
    signal play(int row)

    readonly property bool isTop: model.mode === "top"
    readonly property bool isFav: model.mode === "favorites"

    // ---- Kopf --------------------------------------------------------------------------
    Text {
        id: title
        x: 28
        y: 24
        text: root.isTop ? "YouTube Music" : (root.isFav ? "Favoriten" : "Suche")
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 24
        font.bold: true
    }
    Text {
        anchors.left: title.left
        anchors.top: title.bottom
        anchors.topMargin: 4
        text: root.model.loading ? (root.isTop ? "Die Top 10 werden geladen …" : "Wird gesucht …")
            : (root.isTop ? "Die Top 10 in Deutschland"
               : (root.isFav ? (root.model.count === 1 ? "1 Lied" : root.model.count + " Lieder")
                             : root.model.count + " Treffer für „" + root.model.query + "“"))
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 13
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 28
        y: 26
        spacing: 8

        TextField {
            id: search
            width: 320
            height: 38
            leftPadding: 38
            rightPadding: 34
            placeholderText: "Lied oder Künstler suchen – Enter"
            placeholderTextColor: Theme.textMuted
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            selectByMouse: true
            background: Rectangle { radius: 19; color: Theme.ground; border.color: search.activeFocus ? Theme.accent : Theme.hairline; border.width: 1 }
            SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 15 }
            onAccepted: root.model.search(text)
            Accessible.name: "Lied suchen"

            // Suche leeren → zurück zu den Top 10
            Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                visible: search.text.length > 0 || !root.isTop
                width: 26; height: 26; radius: 13
                color: clearMouse.containsMouse ? Theme.hover : "transparent"
                SvgIcon { anchors.centerIn: parent; name: "close"; size: 12 }
                MouseArea {
                    id: clearMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { search.text = ""; root.model.loadTop() }
                }
                Accessible.role: Accessible.Button
                Accessible.name: "Zurück zu den Top 10"
            }
        }
        IconButton {
            width: 38
            height: 38
            icon: "refresh"
            iconSize: 17
            visible: !root.isFav
            label: root.isTop ? "Top 10 neu laden" : "Neu suchen"
            onClicked: root.isTop ? root.model.reloadTop() : root.model.search(root.model.query)
        }
    }

    // ---- Reiter: Top 10 | Favoriten ------------------------------------------------------
    Row {
        id: tabs
        anchors.left: title.left
        anchors.top: title.bottom
        anchors.topMargin: 30
        spacing: 6
        Repeater {
            model: [
                { key: "top", label: "Top 10", icon: "ytmusic" },
                { key: "favorites", label: "Favoriten", icon: "heart" }
            ]
            delegate: Rectangle {
                id: tab
                required property var modelData
                readonly property bool current: root.model.mode === modelData.key
                width: tabRow.implicitWidth + 26
                height: 32
                radius: 16
                color: current ? Theme.accent : (tabMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06))
                Row {
                    id: tabRow
                    anchors.centerIn: parent
                    spacing: 7
                    SvgIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !tab.current
                        name: tab.modelData.icon
                        size: 14
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: tab.modelData.label + (tab.modelData.key === "favorites" && root.model.favoriteCount > 0 ? "  " + root.model.favoriteCount : "")
                        color: tab.current ? Theme.accentText : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
                MouseArea {
                    id: tabMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        search.text = ""
                        if (tab.modelData.key === "favorites") root.model.loadFavorites()
                        else root.model.loadTop()
                    }
                }
                Accessible.role: Accessible.PageTab
                Accessible.name: modelData.label
            }
        }
    }

    // ---- Liste ---------------------------------------------------------------------------
    ListView {
        id: list
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: tabs.bottom
        anchors.topMargin: 14
        anchors.bottom: parent.bottom
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.bottomMargin: 8
        clip: true
        model: root.model
        spacing: 4
        boundsBehavior: Flickable.StopAtBounds
        opacity: root.model.loading ? 0.4 : 1
        Behavior on opacity { NumberAnimation { duration: 150 } }
        ScrollBar.vertical: ScrollBar {
            contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.2) }
        }

        delegate: Rectangle {
            id: row
            required property int index
            required property string title
            required property string artist
            required property string duration
            required property string thumb
            required property string videoId
            required property int rank
            required property bool favorite
            readonly property bool current: videoId === root.model.currentId
            readonly property bool big: root.isTop

            width: ListView.view.width
            height: big ? 72 : 60
            radius: 12
            color: current ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.12)
                           : (rowMouse.containsMouse ? Theme.hover : "transparent")

            // Platz (nur bei den Top 10)
            Text {
                id: rankText
                visible: row.big
                x: 10
                width: 40
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignHCenter
                text: row.rank
                color: row.rank <= 3 ? Theme.accent : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: row.rank <= 3 ? 22 : 18
                font.bold: true
            }

            // Cover
            Rectangle {
                id: cover
                x: row.big ? 58 : 10
                anchors.verticalCenter: parent.verticalCenter
                width: row.big ? 54 : 44
                height: width
                radius: 9
                color: "#2b3550"
                clip: true
                Image {
                    anchors.fill: parent
                    source: row.thumb
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    sourceSize.width: 120
                    sourceSize.height: 120
                }
                // Abspielen-Hinweis beim Darüberfahren / läuft gerade
                Rectangle {
                    anchors.fill: parent
                    color: Qt.rgba(0, 0, 0, 0.45)
                    visible: rowMouse.containsMouse || row.current
                    SvgIcon {
                        anchors.centerIn: parent
                        visible: !(row.current && root.model.resolving)
                        name: row.current ? "volume" : "play"
                        size: 18
                    }
                    // Lädt gerade
                    Rectangle {
                        anchors.centerIn: parent
                        visible: row.current && root.model.resolving
                        width: 18; height: 18; radius: 9
                        color: "transparent"
                        border.color: Theme.accent
                        border.width: 2
                        Rectangle { x: 6; y: -2; width: 6; height: 6; radius: 3; color: Theme.accent }
                        RotationAnimation on rotation { running: parent.visible; from: 0; to: 360; duration: 900; loops: Animation.Infinite }
                    }
                }
            }

            Column {
                anchors.left: cover.right
                anchors.leftMargin: 14
                anchors.right: dur.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: row.title
                    color: row.current ? Theme.accent : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    font.bold: true
                }
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: row.artist
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                }
            }
            Text {
                id: dur
                anchors.right: heart.left
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: row.duration
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }

            MouseArea {
                id: rowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.play(row.index)
            }

            // Herz: zu den Favoriten / aus den Favoriten
            Rectangle {
                id: heart
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 36; height: 36; radius: 18
                visible: row.favorite || rowMouse.containsMouse || heartMouse.containsMouse
                color: heartMouse.containsMouse ? Theme.hover : "transparent"
                SvgIcon {
                    anchors.centerIn: parent
                    name: row.favorite ? "heart-on" : "heart"
                    size: 17
                    scale: heartMouse.pressed ? 0.85 : 1
                    Behavior on scale { NumberAnimation { duration: 80 } }
                }
                MouseArea {
                    id: heartMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.model.toggleFavorite(row.index)
                }
                Accessible.role: Accessible.Button
                Accessible.name: row.favorite ? "Aus den Favoriten entfernen" : "Zu den Favoriten"
            }
            Accessible.role: Accessible.ListItem
            Accessible.name: row.title + ", " + row.artist
            Accessible.onPressAction: root.play(row.index)
        }
    }

    // ---- Laden / leer / Fehler ---------------------------------------------------------------
    Column {
        anchors.centerIn: list
        width: Math.min(440, list.width - 40)
        spacing: 14
        visible: list.count === 0 || (root.model.status.length > 0 && !root.model.loading)

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 40; height: 40
            visible: root.model.loading
            Rectangle {
                anchors.fill: parent
                radius: 20
                color: "transparent"
                border.color: Qt.rgba(1, 1, 1, 0.12)
                border.width: 3
            }
            Rectangle { x: 16; y: -1; width: 8; height: 8; radius: 4; color: Theme.accent }
            RotationAnimation on rotation { running: root.model.loading; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            visible: !root.model.loading
            text: root.model.status
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }
        CButton {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.model.loading && root.model.status.length > 0 && !root.isFav
            text: "Nochmal versuchen"
            onClicked: root.isTop ? root.model.reloadTop() : root.model.search(root.model.query)
        }
    }

    // Beim ersten Öffnen die Top 10 holen
    onVisibleChanged: if (visible && list.count === 0 && !model.loading && !root.isFav) model.loadTop()
}
