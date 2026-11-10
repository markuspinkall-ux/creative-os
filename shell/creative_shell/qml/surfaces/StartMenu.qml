import QtQuick
import QtQuick.Controls.Basic
import Creative

// Schlankes Startmenü: Suche oben, alle Apps alphabetisch darunter,
// unten Benutzer, Sperren und Ein/Aus.
Item {
    id: root

    property string screenName

    // Wird beim Öffnen aufgerufen
    function opened() {
        search.text = ""
        powerMenu.visible = false
        powerMenu.confirmServer = false
        session.refreshServer()
        session.refreshAvatar()
        appMenu.visible = false
        list.currentIndex = -1
        list.positionViewAtBeginning()
        search.forceActiveFocus()
    }

    Keys.onEscapePressed: shell.closePopups()

    Rectangle {
        id: menu
        x: 24
        width: 380
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        radius: Theme.radiusMenu
        color: Theme.surface
        border.color: Theme.hairline
        border.width: 1
        // leicht durchsichtig wie die Taskleiste (als Ganzes, damit Fußleiste und Fläche gleich wirken)
        layer.enabled: true
        layer.smooth: true
        opacity: Theme.bar.a

        TextField {
            id: search
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 18
                leftMargin: 18
                rightMargin: 18
            }
            height: 42
            leftPadding: 42
            rightPadding: 14
            placeholderText: "Suchen"
            placeholderTextColor: Theme.textMuted
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.accentText
            font.family: Theme.fontFamily
            font.pixelSize: 14
            selectByMouse: true
            background: Rectangle {
                radius: 21
                color: Theme.ground
                border.color: Theme.accent
                border.width: 1.5
            }

            SvgIcon {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                name: "search"
                size: 16
            }

            onTextChanged: {
                apps.filterText = text
                list.currentIndex = (text.length > 0 && list.count > 0) ? 0 : -1
            }
            Keys.onDownPressed: {
                list.forceActiveFocus()
                if (list.currentIndex < 0 && list.count > 0)
                    list.currentIndex = 0
            }
            Keys.onReturnPressed: list.launchCurrent()
            Keys.onEnterPressed: list.launchCurrent()
            Keys.onEscapePressed: shell.closePopups()

            Accessible.name: "Apps suchen"
        }

        Text {
            id: heading
            anchors.top: search.bottom
            anchors.topMargin: 16
            anchors.left: parent.left
            anchors.leftMargin: 22
            text: search.text.length > 0 ? "Ergebnisse" : "Alle Apps"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.bold: true
        }

        ListView {
            id: list

            function launchCurrent() {
                if (count === 0)
                    return
                apps.launchAt(currentIndex >= 0 ? currentIndex : 0)
                shell.closePopups()
            }

            anchors {
                top: heading.bottom
                topMargin: 4
                left: parent.left
                right: parent.right
                bottom: footer.top
                leftMargin: 10
                rightMargin: 10
                bottomMargin: 6
            }
            clip: true
            model: apps
            spacing: 4
            keyNavigationEnabled: true
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0

            section.property: "letter"
            section.criteria: ViewSection.FullString
            section.delegate: Item {
                required property string section
                width: ListView.view.width
                height: section.length > 0 ? 34 : 0
                visible: section.length > 0
                Text {
                    x: 12
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 6
                    text: parent.section
                    color: Theme.accent
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.bold: true
                }
            }

            delegate: Rectangle {
                id: row
                required property int index
                required property string name
                required property string icon
                required property string comment
                required property string desktopId

                width: ListView.view.width
                height: 44
                radius: Theme.radiusRow
                color: rowMouse.pressed ? Theme.pressed
                       : ((rowMouse.containsMouse || ListView.isCurrentItem) ? Theme.hover : "transparent")

                Image {
                    id: appIcon
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 26
                    height: 26
                    sourceSize.width: 52
                    sourceSize.height: 52
                    source: "image://icon/" + row.icon
                    asynchronous: true
                    smooth: true
                }

                Text {
                    anchors.left: appIcon.right
                    anchors.leftMargin: 14
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.name
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                }

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (mouse) => {
                        if (mouse.button === Qt.RightButton) {
                            appMenu.desktopId = row.desktopId
                            const p = row.mapToItem(menu, mouse.x, mouse.y)
                            appMenu.x = Math.min(p.x, menu.width - appMenu.width - 8)
                            appMenu.y = Math.min(p.y, menu.height - appMenu.height - 8)
                            appMenu.visible = true
                            return
                        }
                        apps.launchAt(row.index)
                        shell.closePopups()
                    }
                }

                Accessible.role: Accessible.ListItem
                Accessible.name: row.name
                Accessible.description: row.comment
            }

            Keys.onReturnPressed: launchCurrent()
            Keys.onEnterPressed: launchCurrent()
            Keys.onUpPressed: {
                if (currentIndex <= 0)
                    search.forceActiveFocus()
                else
                    decrementCurrentIndex()
            }
            Keys.onPressed: (event) => {
                // Einfach lostippen springt zurück in die Suche
                if (event.text.length > 0 && event.text.trim().length > 0 && !(event.modifiers & Qt.ControlModifier)) {
                    search.forceActiveFocus()
                    search.text += event.text
                    event.accepted = true
                }
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 4
                    radius: 2
                    color: Qt.rgba(1, 1, 1, 0.2)
                }
            }

            Text {
                anchors.centerIn: parent
                visible: list.count === 0
                text: "Keine App gefunden"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
            }
        }

        // Ein/Aus-Menü
        Rectangle {
            id: powerMenu
            // Server-Modus fragt erst nach, weil dabei alle Programme schließen
            property bool confirmServer: false
            visible: false
            onVisibleChanged: if (!visible) confirmServer = false
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.bottom: footer.top
            anchors.bottomMargin: 8
            width: confirmServer ? 300 : 200
            height: confirmServer ? serverConfirm.implicitHeight + 28 : powerColumn.implicitHeight + 12
            radius: 14
            color: Theme.raised
            border.color: Theme.hairline
            border.width: 1
            z: 2

            Column {
                id: powerColumn
                visible: !powerMenu.confirmServer
                anchors.fill: parent
                anchors.margins: 6
                spacing: 2

                Repeater {
                    model: [
                        { label: "Bereitschaft", action: "suspend" },
                        { label: "Neu starten", action: "reboot" },
                        { label: "Ausschalten", action: "poweroff" },
                        { label: "Abmelden", action: "logout" }
                    ].concat(session.serverModeAvailable
                             ? [{ label: "Server-Modus", action: "serverMode", icon: "server" }] : [])
                    delegate: Rectangle {
                        required property var modelData
                        width: powerColumn.width
                        height: 40
                        radius: 10
                        color: pm.containsMouse ? Theme.hover : "transparent"
                        SvgIcon {
                            visible: !!parent.modelData.icon
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            name: parent.modelData.icon || "server"
                            size: 15
                        }
                        Text {
                            x: 14
                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.modelData.label
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: pm
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (parent.modelData.action === "serverMode") {
                                    powerMenu.confirmServer = true
                                    return
                                }
                                shell.closePopups()
                                session[parent.modelData.action]()
                            }
                        }
                        Accessible.role: Accessible.MenuItem
                        Accessible.name: modelData.label
                    }
                }
            }

            // Rückfrage für den Server-Modus
            Column {
                id: serverConfirm
                visible: powerMenu.confirmServer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                Row {
                    spacing: 10
                    SvgIcon { name: "server"; size: 18; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Server-Modus starten?"
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                        font.bold: true
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Alle Programme werden geschlossen – speichere vorher deine Arbeit. "
                          + "Nur „Mein Server“ bleibt online, der PC geht nicht in Bereitschaft. "
                          + "Zurück geht es über den Anmeldebildschirm."
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    lineHeight: 1.25
                }
                Row {
                    anchors.right: parent.right
                    spacing: 8
                    bottomPadding: 2
                    CButton { text: "Abbrechen"; onClicked: powerMenu.confirmServer = false }
                    CButton {
                        text: "Starten"
                        primary: true
                        onClicked: {
                            shell.closePopups()
                            session.serverMode()
                        }
                    }
                }
            }
        }

        // Rechtsklick auf eine App
        Rectangle {
            id: appMenu
            property string desktopId: ""
            visible: false
            z: 3
            width: 230
            height: 84
            radius: 12
            color: Theme.raised
            border.color: Theme.hairline
            Rectangle {
                x: 4; y: 4
                width: parent.width - 8; height: 36
                radius: 9
                color: amMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                SvgIcon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: "plus"; size: 15 }
                Text {
                    x: 36
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Zur Ablage hinzufügen"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                MouseArea {
                    id: amMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { shelf.addApp(appMenu.desktopId); appMenu.visible = false }
                }
            }
            Rectangle {
                x: 4; y: 44
                width: parent.width - 8; height: 36
                radius: 9
                color: hideMouse.containsMouse ? Theme.hover : "transparent"
                Text {
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Aus Startmenü entfernen"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                MouseArea {
                    id: hideMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        appMenu.visible = false
                        apps.hideFromStartMenu(appMenu.desktopId)
                    }
                }
                Accessible.role: Accessible.MenuItem
                Accessible.name: "Aus Startmenü entfernen"
                Accessible.onPressAction: {
                    appMenu.visible = false
                    apps.hideFromStartMenu(appMenu.desktopId)
                }
            }
        }

        Rectangle {
            id: footer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 1
            height: 56
            radius: Theme.radiusMenu - 1
            color: Theme.footer

            // eckige Oberkante, runde Unterkante
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: parent.radius
                color: Theme.footer
            }
            Divider {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Avatar {
                    size: 30
                    source: session.avatar
                    initials: session.initials
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: session.userName
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                IconButton {
                    width: 40
                    height: 40
                    icon: "lock"
                    iconSize: 16
                    label: "Sperren"
                    onClicked: {
                        shell.closePopups()
                        session.lock()
                    }
                }
                IconButton {
                    width: 40
                    height: 40
                    icon: "power"
                    iconSize: 16
                    label: "Ein/Aus"
                    active: powerMenu.visible
                    onClicked: powerMenu.visible = !powerMenu.visible
                }
            }
        }
    }
}
