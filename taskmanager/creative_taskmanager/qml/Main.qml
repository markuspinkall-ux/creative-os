import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Taskmanager – wie bei Windows: Prozesse, Leistung, Autostart-Apps, Details.
Window {
    id: win

    width: 1120
    height: 720
    minimumWidth: 820
    minimumHeight: 520
    visible: true
    title: "Taskmanager"
    color: Theme.surface

    property string page: startPage            // processes | performance | startup | details
    property var selected: null                // { key, name, pids, kind }

    function askEnd(sel, force) {
        if (!sel || !sel.pids || sel.pids.length === 0)
            return
        if (sel.kind === "sys") {
            confirm.target = sel
            confirm.force = force
            confirm.open()
        } else {
            tm.endTask(sel.pids, sel.name, force)
            win.selected = null
        }
    }

    // ---- Seitenleiste ----------------------------------------------------------------------
    Rectangle {
        id: nav
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 220
        color: Theme.footer

        Row {
            x: 18
            y: 18
            spacing: 10
            Rectangle {
                width: 32; height: 32; radius: 10
                color: Theme.accent
                SvgIcon { anchors.centerIn: parent; name: "taskmanager"; size: 16 }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Taskmanager"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.bold: true
            }
        }

        Column {
            x: 10
            y: 76
            width: parent.width - 20
            spacing: 2
            Repeater {
                model: [
                    { key: "processes", label: "Prozesse", icon: "grid" },
                    { key: "performance", label: "Leistung", icon: "taskmanager" },
                    { key: "startup", label: "Autostart-Apps", icon: "rocket" },
                    { key: "details", label: "Details", icon: "list" }
                ]
                delegate: Rectangle {
                    id: navItem
                    required property var modelData
                    readonly property bool current: win.page === modelData.key
                    width: parent.width
                    height: 40
                    radius: Theme.radiusRow
                    color: current ? Theme.hover : (nm.containsMouse ? Theme.subtle : "transparent")
                    Rectangle {
                        x: 4; anchors.verticalCenter: parent.verticalCenter
                        width: 3; height: 14; radius: 2
                        color: Theme.accent
                        visible: navItem.current
                    }
                    SvgIcon { id: ni; x: 16; anchors.verticalCenter: parent.verticalCenter; name: navItem.modelData.icon; size: 17 }
                    Text {
                        anchors.left: ni.right
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: navItem.modelData.label
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: navItem.current
                    }
                    MouseArea {
                        id: nm
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { win.page = navItem.modelData.key; if (win.page === "startup") tm.refreshAutostart() }
                    }
                    Accessible.role: Accessible.PageTab
                    Accessible.name: modelData.label
                }
            }
        }

        // Aktualisierung
        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 16
            spacing: 8
            Text {
                text: "Aktualisierung"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 11
            }
            Row {
                spacing: 4
                Repeater {
                    model: [{ ms: 750, t: "Schnell" }, { ms: 1500, t: "Normal" }, { ms: 4000, t: "Langsam" }, { ms: 0, t: "Pause" }]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool on: modelData.ms === 0 ? tm.paused : (!tm.paused && tm.interval === modelData.ms)
                        width: lab.implicitWidth + 14
                        height: 26
                        radius: 8
                        color: on ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22) : (um.containsMouse ? Theme.hover : "transparent")
                        Text { id: lab; anchors.centerIn: parent; text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: parent.on }
                        MouseArea {
                            id: um
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (modelData.ms === 0) tm.setPaused(!tm.paused)
                                else { tm.setPaused(false); tm.setInterval(modelData.ms) }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- Kopfzeile ---------------------------------------------------------------------------
    Item {
        id: head
        anchors.left: nav.right
        anchors.right: parent.right
        anchors.top: parent.top
        height: 68

        Text {
            id: pageTitle
            x: 26
            anchors.verticalCenter: parent.verticalCenter
            text: ({ processes: "Prozesse", performance: "Leistung", startup: "Autostart-Apps", details: "Details" })[win.page]
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 22
            font.bold: true
        }

        TextField {
            id: search
            visible: win.page === "processes" || win.page === "details"
            anchors.left: pageTitle.right
            anchors.leftMargin: 26
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(340, head.width - pageTitle.width - actions.width - 90)
            height: 38
            leftPadding: 38
            placeholderText: "Name oder PID suchen"
            placeholderTextColor: Theme.textMuted
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            selectByMouse: true
            background: Rectangle { radius: 19; color: Theme.ground; border.color: search.activeFocus ? Theme.accent : Theme.hairline }
            SvgIcon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 15 }
            onTextChanged: tm.setFilter(text)
            Accessible.name: "Prozess suchen"
        }

        Row {
            id: actions
            anchors.right: parent.right
            anchors.rightMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            CButton {
                text: "Neuen Task ausführen"
                onClicked: runDialog.open()
            }
            CButton {
                visible: win.page === "processes" || win.page === "details"
                text: "Task beenden"
                primary: true
                enabled: win.selected !== null
                onClicked: win.askEnd(win.selected, false)
            }
        }
        Divider { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
    }

    // ---- Seiten ------------------------------------------------------------------------------------
    Item {
        id: content
        anchors.left: nav.right
        anchors.right: parent.right
        anchors.top: head.bottom
        anchors.bottom: parent.bottom

        ProcessesPage {
            anchors.fill: parent
            visible: win.page === "processes"
            host: win
        }
        PerformancePage {
            anchors.fill: parent
            visible: win.page === "performance"
        }
        StartupPage {
            anchors.fill: parent
            visible: win.page === "startup"
        }
        DetailsPage {
            anchors.fill: parent
            visible: win.page === "details"
            host: win
        }
    }

    // ---- Hinweis unten -----------------------------------------------------------------------------
    Rectangle {
        anchors.horizontalCenter: content.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 18
        visible: tm.message.length > 0
        width: msg.implicitWidth + 32
        height: 38
        radius: 19
        color: Theme.raised
        border.color: Theme.hairline
        Text { id: msg; anchors.centerIn: parent; text: tm.message; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
    }

    // ---- Rückfrage bei Systemprozessen -----------------------------------------------------------------
    Popup {
        id: confirm
        property var target: null
        property bool force: false
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 440
        modal: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        contentItem: Column {
            spacing: 14
            Text {
                text: confirm.target ? "„" + confirm.target.name + "“ beenden?" : ""
                width: parent.width
                elide: Text.ElideRight
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 17; font.bold: true
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Das ist ein Systemprozess. Wenn du ihn beendest, kann Creative OS instabil werden oder Dinge funktionieren nicht mehr bis zum Neustart. Ungespeicherte Daten können verloren gehen."
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: confirm.close() }
                CButton {
                    text: "Trotzdem beenden"
                    primary: true
                    onClicked: {
                        confirm.close()
                        tm.endTask(confirm.target.pids, confirm.target.name, confirm.force)
                        win.selected = null
                    }
                }
            }
        }
    }

    // ---- Neuen Task ausführen -----------------------------------------------------------------------------
    Popup {
        id: runDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 460
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        onOpened: { runField.text = ""; runField.forceActiveFocus() }
        contentItem: Column {
            spacing: 14
            Text { text: "Neuen Task ausführen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 17; font.bold: true }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Gib den Namen eines Programms, Ordners oder einer Internetadresse ein."
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
            }
            TextField {
                id: runField
                width: parent.width
                height: 40
                leftPadding: 12
                placeholderText: "z. B. creative-notes, steam, https://…"
                placeholderTextColor: Theme.textMuted
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                background: Rectangle { radius: 10; color: Theme.ground; border.color: runField.activeFocus ? Theme.accent : Theme.hairline }
                onAccepted: if (tm.runTask(text)) runDialog.close()
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: runDialog.close() }
                CButton { text: "Ausführen"; primary: true; enabled: runField.text.trim().length > 0; onClicked: if (tm.runTask(runField.text)) runDialog.close() }
            }
        }
    }

    Shortcut { sequence: "Delete"; enabled: win.selected !== null && !runDialog.opened; onActivated: win.askEnd(win.selected, false) }
    Shortcut { sequence: "Ctrl+F"; onActivated: search.forceActiveFocus() }
    Shortcut { sequence: "Esc"; onActivated: { if (search.activeFocus) search.text = ""; win.selected = null } }
}
