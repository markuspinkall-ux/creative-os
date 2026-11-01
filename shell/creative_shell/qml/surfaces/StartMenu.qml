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
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
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
            visible: false
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.bottom: footer.top
            anchors.bottomMargin: 8
            width: 200
            height: powerColumn.implicitHeight + 12
            radius: 14
            color: Theme.raised
            border.color: Theme.hairline
            border.width: 1
            z: 2

            Column {
                id: powerColumn
                anchors.fill: parent
                anchors.margins: 6
                spacing: 2

                Repeater {
                    model: [
                        { label: "Bereitschaft", action: "suspend" },
                        { label: "Neu starten", action: "reboot" },
                        { label: "Ausschalten", action: "poweroff" },
                        { label: "Abmelden", action: "logout" }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        width: powerColumn.width
                        height: 40
                        radius: 10
                        color: pm.containsMouse ? Theme.hover : "transparent"
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
                                shell.closePopups()
                                session[parent.modelData.action]()
                            }
                        }
                        Accessible.role: Accessible.MenuItem
                        Accessible.name: modelData.label
                    }
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

                Rectangle {
                    width: 30
                    height: 30
                    radius: 15
                    color: Theme.accent
                    Text {
                        anchors.centerIn: parent
                        text: session.initial
                        color: Theme.accentText
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
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
