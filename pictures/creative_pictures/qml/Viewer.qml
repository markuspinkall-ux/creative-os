import QtQuick
import QtQuick.Controls.Basic
import Creative

// Bildansicht: oben Leiste mit Aktionen, Bild mit Zoom und Verschieben,
// Pfeile links/rechts, unten Filmstreifen und Zoom-Regler, rechts Infos.
Item {
    id: root
    property var host
    property bool showInfo: false
    property bool showStrip: true
    property bool slideshow: false
    property real zoom: 1               // 1 = 100 %
    property bool fit: true
    readonly property real fitZoom: img.implicitWidth > 0
        ? Math.min(1, area.width / img.implicitWidth, area.height / img.implicitHeight) : 1
    readonly property real shownZoom: fit ? fitZoom : zoom
    readonly property bool isFav: pics.favorites.indexOf(pics.currentPath) >= 0

    function setZoom(z, cx, cy) {
        const old = shownZoom
        z = Math.max(0.05, Math.min(8, z))
        const fx = cx === undefined ? flick.width / 2 : cx
        const fy = cy === undefined ? flick.height / 2 : cy
        const px = (flick.contentX + fx) / old
        const py = (flick.contentY + fy) / old
        fit = false
        zoom = z
        Qt.callLater(() => {
            flick.contentX = Math.max(0, px * z - fx)
            flick.contentY = Math.max(0, py * z - fy)
        })
    }
    function resetZoom() { fit = true; zoom = 1 }

    Connections {
        target: pics
        function onViewChanged() { root.resetZoom() }
    }

    Rectangle { anchors.fill: parent; color: "#0e1015" }

    // ---- Leiste oben -------------------------------------------------------------------------
    Rectangle {
        id: topBar
        anchors.left: parent.left
        anchors.right: parent.right
        height: root.host.fullscreen ? 0 : 56
        visible: !root.host.fullscreen
        color: Theme.footer

        Row {
            x: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            IconButton { width: 38; height: 38; icon: "back"; iconSize: 16; label: "Zurück zur Sammlung (Esc)"; onClicked: { root.slideshow = false; pics.closeView() } }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    width: Math.min(420, root.width * 0.35)
                    elide: Text.ElideMiddle
                    text: pics.currentName
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                }
                Text {
                    text: (pics.index + 1) + " von " + pics.total + "   ·   " + Math.round(root.shownZoom * 100) + " %"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                }
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            IconButton { width: 40; height: 40; icon: "zoom-out"; iconSize: 17; label: "Verkleinern (−)"; onClicked: root.setZoom(root.shownZoom / 1.25) }
            IconButton { width: 40; height: 40; icon: "zoom-in"; iconSize: 17; label: "Vergrößern (+)"; onClicked: root.setZoom(root.shownZoom * 1.25) }
            IconButton { width: 40; height: 40; icon: "fit"; iconSize: 17; label: "Einpassen (0)"; active: root.fit; onClicked: root.resetZoom() }
            Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }
            IconButton { width: 40; height: 40; icon: "rotate"; iconSize: 17; label: "Drehen (Strg+R)"; onClicked: pics.rotate(90) }
            IconButton { width: 40; height: 40; icon: root.isFav ? "heart-on" : "heart"; iconSize: 17; label: root.isFav ? "Aus den Favoriten entfernen" : "Zu den Favoriten (F)"; onClicked: pics.toggleFavorite(pics.currentPath) }
            IconButton { width: 40; height: 40; icon: "trash"; iconSize: 17; label: "Löschen (Entf)"; onClicked: deleteAsk.open() }
            Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }
            IconButton { width: 40; height: 40; icon: "slideshow"; iconSize: 17; label: "Diashow (F5)"; active: root.slideshow; onClicked: root.slideshow = !root.slideshow }
            IconButton { width: 40; height: 40; icon: "info"; iconSize: 17; label: "Infos (I)"; active: root.showInfo; onClicked: root.showInfo = !root.showInfo }
            IconButton {
                width: 40; height: 40; icon: "more"; iconSize: 17; label: "Mehr"
                onClicked: more.open()
                Popup {
                    id: more
                    y: parent.height + 6
                    x: parent.width - width
                    width: 260
                    padding: 6
                    background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
                    contentItem: Column {
                        spacing: 1
                        Repeater {
                            model: [
                                { t: "Kopieren", a: "copy" },
                                { t: "Als Hintergrundbild festlegen", a: "wall" },
                                { t: "Umbenennen …", a: "rename" },
                                { t: "Im Ordner zeigen", a: "folder" },
                                { t: "Gegen den Uhrzeigersinn drehen", a: "rotl" },
                                { t: "Vollbild", a: "full" }
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                width: 248; height: 34; radius: 8
                                color: mm.containsMouse ? Theme.hover : "transparent"
                                Text { x: 12; anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                                MouseArea {
                                    id: mm
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        more.close()
                                        const a = modelData.a
                                        if (a === "copy") pics.copyImage()
                                        else if (a === "wall") pics.setWallpaper()
                                        else if (a === "rename") renameDialog.open()
                                        else if (a === "folder") pics.showInFolder()
                                        else if (a === "rotl") pics.rotate(-90)
                                        else root.host.setFullscreen(true)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    // ---- Bild ----------------------------------------------------------------------------------------
    Item {
        id: area
        anchors.left: parent.left
        anchors.right: infoPane.visible ? infoPane.left : parent.right
        anchors.top: topBar.bottom
        anchors.bottom: bottomBar.top

        Flickable {
            id: flick
            anchors.fill: parent
            clip: true
            contentWidth: Math.max(width, img.implicitWidth * root.shownZoom)
            contentHeight: Math.max(height, img.implicitHeight * root.shownZoom)
            interactive: !root.fit
            boundsBehavior: Flickable.StopAtBounds

            Item {
                width: flick.contentWidth
                height: flick.contentHeight
                Image {
                    id: img
                    visible: !pics.currentAnimated
                    anchors.centerIn: parent
                    width: implicitWidth * root.shownZoom
                    height: implicitHeight * root.shownZoom
                    source: pics.currentAnimated ? "" : pics.currentUrl
                    asynchronous: true
                    autoTransform: true
                    smooth: true
                    mipmap: root.shownZoom < 1
                    cache: false
                }
                AnimatedImage {
                    id: anim
                    visible: pics.currentAnimated
                    anchors.centerIn: parent
                    width: implicitWidth * root.shownZoom
                    height: implicitHeight * root.shownZoom
                    source: pics.currentAnimated ? pics.currentUrl : ""
                    playing: visible
                    cache: false
                }
            }

            WheelHandler {
                acceptedModifiers: Qt.NoModifier | Qt.ControlModifier
                onWheel: (ev) => {
                    const f = ev.angleDelta.y > 0 ? 1.15 : 1 / 1.15
                    root.setZoom(root.shownZoom * f, ev.x, ev.y)
                }
            }
            TapHandler {
                onDoubleTapped: (ev) => { if (root.fit) root.setZoom(1, ev.position.x, ev.position.y); else root.resetZoom() }
            }
        }

        // Laden
        Text {
            anchors.centerIn: parent
            visible: (img.status === Image.Loading) || (img.status === Image.Error && !pics.currentAnimated)
            text: img.status === Image.Error ? "Dieses Bild lässt sich nicht anzeigen." : "Wird geladen …"
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }

        // Pfeile
        Repeater {
            model: [{ d: -1, icon: "back" }, { d: 1, icon: "forward" }]
            delegate: Rectangle {
                required property var modelData
                anchors.verticalCenter: parent.verticalCenter
                x: modelData.d < 0 ? 14 : area.width - width - 14
                width: 46; height: 46; radius: 23
                visible: pics.total > 1 && (areaHover.hovered || am.containsMouse)
                color: am.containsMouse ? Qt.rgba(35 / 255, 40 / 255, 54 / 255, 0.95) : Qt.rgba(35 / 255, 40 / 255, 54 / 255, 0.75)
                border.color: Theme.hairline
                SvgIcon { anchors.centerIn: parent; name: modelData.icon; size: 18 }
                MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pics.step(modelData.d) }
                Accessible.role: Accessible.Button
                Accessible.name: modelData.d < 0 ? "Vorheriges Bild" : "Nächstes Bild"
            }
        }
        HoverHandler { id: areaHover }
    }

    // ---- Infos rechts --------------------------------------------------------------------------------
    Rectangle {
        id: infoPane
        anchors.right: parent.right
        anchors.top: topBar.bottom
        anchors.bottom: bottomBar.top
        width: 300
        visible: root.showInfo && !root.host.fullscreen
        color: Theme.footer
        Rectangle { width: 1; height: parent.height; color: Theme.hairline }
        Column {
            x: 22
            y: 20
            width: parent.width - 44
            spacing: 14
            Text { text: "Infos"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
            Repeater {
                model: pics.info
                delegate: Column {
                    required property var modelData
                    width: parent.width
                    spacing: 3
                    Text { text: modelData.label; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                    Text { width: parent.width; wrapMode: Text.WrapAnywhere; text: modelData.value; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                }
            }
        }
    }

    // ---- Unten: Filmstreifen + Zoom ---------------------------------------------------------------------
    Rectangle {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.host.fullscreen ? 0 : (root.showStrip ? 96 : 44)
        visible: !root.host.fullscreen
        color: Theme.footer
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top }

        ListView {
            id: strip
            visible: root.showStrip
            anchors.left: parent.left
            anchors.right: zoomRow.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 10
            anchors.rightMargin: 20
            orientation: ListView.Horizontal
            spacing: 6
            clip: true
            model: pics.strip
            currentIndex: pics.index
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: width / 2 - 40
            preferredHighlightEnd: width / 2 + 40
            highlightMoveDuration: 200
            boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: 76; height: 76
                radius: 8
                color: Theme.raised
                clip: true
                border.color: index === pics.index ? Theme.accent : "transparent"
                border.width: 2
                Image {
                    anchors.fill: parent
                    anchors.margins: 2
                    source: modelData
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    autoTransform: true
                    sourceSize.width: 160
                    sourceSize.height: 160
                    opacity: index === pics.index ? 1 : 0.7
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: pics.goTo(index) }
            }
        }

        Row {
            id: zoomRow
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            IconButton { width: 34; height: 34; icon: "list"; iconSize: 15; label: root.showStrip ? "Filmstreifen ausblenden" : "Filmstreifen einblenden"; active: root.showStrip; onClicked: root.showStrip = !root.showStrip }
            CSlider {
                anchors.verticalCenter: parent.verticalCenter
                width: 150
                from: 5; to: 400; stepSize: 1
                value: Math.round(root.shownZoom * 100)
                onMoved: root.setZoom(value / 100)
                Accessible.name: "Zoom"
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: 44
                text: Math.round(root.shownZoom * 100) + " %"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }
    }

    // ---- Diashow ---------------------------------------------------------------------------------------
    Timer {
        running: root.slideshow && root.visible
        interval: 4000
        repeat: true
        onTriggered: pics.step(1)
    }

    // ---- Rückfragen ------------------------------------------------------------------------------------
    Popup {
        id: deleteAsk
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 420
        modal: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Column {
            spacing: 14
            Text { text: "Bild löschen?"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 17; font.bold: true }
            Text { width: parent.width; wrapMode: Text.WordWrap; text: "„" + pics.currentName + "“ kommt in den Papierkorb. Von dort kannst du es wiederherstellen."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: deleteAsk.close() }
                CButton { text: "Löschen"; primary: true; onClicked: { deleteAsk.close(); pics.deleteCurrent() } }
            }
        }
    }
    Popup {
        id: renameDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 420
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        onOpened: { nameField.text = pics.currentName.replace(/\.[^.]+$/, ""); nameField.selectAll(); nameField.forceActiveFocus() }
        contentItem: Column {
            spacing: 14
            Text { text: "Umbenennen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 17; font.bold: true }
            TextField {
                id: nameField
                width: parent.width
                height: 40
                leftPadding: 12
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                background: Rectangle { radius: 10; color: Theme.ground; border.color: nameField.activeFocus ? Theme.accent : Theme.hairline }
                onAccepted: if (pics.rename(text)) renameDialog.close()
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: renameDialog.close() }
                CButton { text: "Umbenennen"; primary: true; onClicked: if (pics.rename(nameField.text)) renameDialog.close() }
            }
        }
    }

    // ---- Tastatur --------------------------------------------------------------------------------------------
    Shortcut { enabled: root.visible && !renameDialog.opened; sequences: ["Right", "Space", "PgDown"]; onActivated: pics.step(1) }
    Shortcut { enabled: root.visible && !renameDialog.opened; sequences: ["Left", "Backspace", "PgUp"]; onActivated: pics.step(-1) }
    Shortcut { enabled: root.visible && !renameDialog.opened; sequence: "Delete"; onActivated: deleteAsk.open() }
    Shortcut { enabled: root.visible; sequences: ["+", "Ctrl++", "Ctrl+="]; onActivated: root.setZoom(root.shownZoom * 1.25) }
    Shortcut { enabled: root.visible; sequences: ["-", "Ctrl+-"]; onActivated: root.setZoom(root.shownZoom / 1.25) }
    Shortcut { enabled: root.visible; sequences: ["0", "Ctrl+0"]; onActivated: root.resetZoom() }
    Shortcut { enabled: root.visible; sequence: "1"; onActivated: root.setZoom(1) }
    Shortcut { enabled: root.visible; sequence: "Ctrl+R"; onActivated: pics.rotate(90) }
    Shortcut { enabled: root.visible; sequence: "Ctrl+C"; onActivated: pics.copyImage() }
    Shortcut { enabled: root.visible && !renameDialog.opened; sequence: "F"; onActivated: pics.toggleFavorite(pics.currentPath) }
    Shortcut { enabled: root.visible && !renameDialog.opened; sequence: "I"; onActivated: root.showInfo = !root.showInfo }
    Shortcut { enabled: root.visible; sequence: "F2"; onActivated: renameDialog.open() }
    Shortcut { enabled: root.visible; sequence: "F5"; onActivated: { root.slideshow = !root.slideshow; if (root.slideshow) root.host.setFullscreen(true) } }
    Shortcut { enabled: root.visible; sequence: "F11"; onActivated: root.host.setFullscreen(!root.host.fullscreen) }
    Shortcut {
        enabled: root.visible
        sequence: "Esc"
        onActivated: {
            if (root.host.fullscreen) { root.host.setFullscreen(false); root.slideshow = false }
            else pics.closeView()
        }
    }
}
