import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative Calculator – Rechner im Graphit-Look.
Window {
    id: win

    property bool showHistory: false
    readonly property int padWidth: 360

    width: showHistory ? padWidth + 280 : padWidth
    height: 600
    minimumWidth: 320
    minimumHeight: 520
    visible: true
    title: "Creative Calculator"
    color: Theme.ground

    Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

    // ---- Rechner -----------------------------------------------------------------------
    Item {
        id: pad
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: win.showHistory ? Math.max(320, win.width - 280) : win.width

        // Kopfzeile
        Item {
            id: head
            x: 16
            y: 12
            width: parent.width - 32
            height: 36
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 9
                Rectangle {
                    width: 26; height: 26; radius: 8
                    color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                    SvgIcon { anchors.centerIn: parent; name: "calculator"; size: 15 }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Creative Calculator"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                }
            }
            IconButton {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 34; height: 34
                icon: "clock"
                iconSize: 16
                active: win.showHistory
                label: win.showHistory ? "Verlauf ausblenden" : "Verlauf zeigen"
                onClicked: win.showHistory = !win.showHistory
            }
        }

        // Anzeige
        Rectangle {
            id: screen
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: head.bottom
            anchors.margins: 14
            anchors.topMargin: 8
            height: Math.max(140, parent.height * 0.27)
            radius: 18
            color: Theme.surface
            border.color: Theme.hairline

            // Rechnung (nach „=“) oder Vorschau
            Text {
                id: topLine
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.left: parent.left
                anchors.leftMargin: 20
                y: 18
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideLeft
                text: calc.topLine
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 15
            }

            Text {
                id: main
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.bottom: previewText.top
                anchors.bottomMargin: 2
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideLeft
                text: calc.display
                color: calc.error ? Theme.flame : Theme.text
                font.family: Theme.fontFamily
                font.bold: calc.done
                // Schrift schrumpft, damit lange Zahlen hineinpassen
                font.pixelSize: {
                    const n = text.length
                    const room = width / 0.58
                    return calc.error ? 22 : Math.max(22, Math.min(52, room / Math.max(1, n)))
                }
                Behavior on font.pixelSize { NumberAnimation { duration: 90 } }
            }

            Text {
                id: previewText
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 14
                height: 22
                text: calc.preview.length > 0 ? "= " + calc.preview : ""
                color: Theme.accent
                font.family: Theme.fontFamily
                font.pixelSize: 17
            }

            // Kopieren per Klick
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.RightButton
                onClicked: copyMenu.popup()
            }
            Menu {
                id: copyMenu
                MenuItem { text: "Kopieren"; onTriggered: { calc.copy(); toast.show("Ergebnis kopiert") } }
                MenuItem { text: "Einfügen"; onTriggered: calc.paste() }
                background: Rectangle { implicitWidth: 160; radius: 10; color: Theme.raised; border.color: Theme.hairline }
                delegate: MenuItem {
                    id: mi
                    contentItem: Text { text: mi.text; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; leftPadding: 6 }
                    background: Rectangle { radius: 8; color: mi.highlighted ? Theme.hover : "transparent" }
                }
            }
        }

        // Tasten
        Grid {
            id: keys
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: screen.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 14
            anchors.topMargin: 12
            columns: 4
            spacing: 8
            readonly property real kw: (width - 3 * spacing) / 4
            readonly property real kh: (height - 5 * spacing) / 6

            Repeater {
                model: [
                    { k: "√", t: "√", kind: "fn" },    { k: "x²", t: "x²", kind: "fn" },  { k: "1/x", t: "¹⁄ₓ", kind: "fn" }, { k: "back", t: "", kind: "fn", icon: "backspace" },
                    { k: "C", t: "C", kind: "clear" }, { k: "()", t: "( )", kind: "fn" }, { k: "%", t: "%", kind: "fn" },    { k: "÷", t: "÷", kind: "op" },
                    { k: "7", t: "7", kind: "num" },   { k: "8", t: "8", kind: "num" },   { k: "9", t: "9", kind: "num" },    { k: "×", t: "×", kind: "op" },
                    { k: "4", t: "4", kind: "num" },   { k: "5", t: "5", kind: "num" },   { k: "6", t: "6", kind: "num" },    { k: "−", t: "−", kind: "op" },
                    { k: "1", t: "1", kind: "num" },   { k: "2", t: "2", kind: "num" },   { k: "3", t: "3", kind: "num" },    { k: "+", t: "+", kind: "op" },
                    { k: "±", t: "±", kind: "num" },   { k: "0", t: "0", kind: "num" },   { k: ",", t: ",", kind: "num" },    { k: "=", t: "=", kind: "eq" }
                ]
                delegate: Rectangle {
                    id: key
                    required property var modelData
                    readonly property bool eq: modelData.kind === "eq"
                    readonly property bool op: modelData.kind === "op"
                    readonly property bool flash: flashTimer.running
                    width: keys.kw
                    height: keys.kh
                    radius: Math.min(16, height / 3)
                    color: eq ? (km.pressed || flash ? Qt.darker(Theme.accent, 1.15) : (km.containsMouse ? Qt.lighter(Theme.accent, 1.06) : Theme.accent))
                         : (km.pressed || flash ? Theme.pressed
                            : (km.containsMouse ? Theme.tint(modelData.kind === "num" ? 0.11 : 0.09)
                               : (modelData.kind === "num" ? Theme.tint(0.07) : Theme.tint(0.035))))
                    border.color: op ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22) : "transparent"
                    scale: km.pressed || flash ? 0.96 : 1
                    Behavior on scale { NumberAnimation { duration: 70 } }

                    Text {
                        anchors.centerIn: parent
                        visible: !key.modelData.icon
                        text: key.modelData.t
                        color: key.eq ? Theme.accentText
                             : (key.op ? Theme.accent : (key.modelData.kind === "clear" ? Theme.flame : Theme.text))
                        font.family: Theme.fontFamily
                        font.pixelSize: key.modelData.kind === "num" || key.eq || key.op ? 22 : 18
                        font.bold: key.modelData.kind !== "num" || key.modelData.k === "±"
                    }
                    SvgIcon {
                        anchors.centerIn: parent
                        visible: !!key.modelData.icon
                        name: key.modelData.icon || "backspace"
                        size: 18
                    }
                    Timer { id: flashTimer; interval: 110 }
                    Connections {
                        target: win
                        function onKeyFlash(k) { if (k === key.modelData.k) flashTimer.restart() }
                    }
                    MouseArea {
                        id: km
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.hit(key.modelData.k)
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: ({ "back": "Löschen", "C": "Alles löschen", "÷": "geteilt", "×": "mal", "−": "minus", "+": "plus", "=": "gleich", "±": "Vorzeichen", "()": "Klammer", "1/x": "Kehrwert", "x²": "Quadrat", "√": "Wurzel" })[key.modelData.k] || key.modelData.t
                    Accessible.onPressAction: win.hit(key.modelData.k)
                }
            }
        }
    }

    // ---- Verlauf ------------------------------------------------------------------------------
    Rectangle {
        id: historyPane
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 280
        visible: win.showHistory
        color: Theme.footer

        Rectangle { width: 1; height: parent.height; color: Theme.hairline }

        Text {
            id: hTitle
            x: 20
            y: 20
            text: "Verlauf"
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.bold: true
        }
        IconButton {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: hTitle.verticalCenter
            width: 32; height: 32
            icon: "trash"
            iconSize: 15
            visible: calc.history.length > 0
            label: "Verlauf löschen"
            onClicked: calc.clearHistory()
        }

        ListView {
            id: hList
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: hTitle.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 10
            anchors.topMargin: 14
            clip: true
            spacing: 4
            model: calc.history
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Theme.tint(0.2) } }
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: hList.width
                height: col.implicitHeight + 18
                radius: 12
                color: hm.containsMouse ? Theme.hover : "transparent"
                Column {
                    id: col
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 3
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideLeft
                        text: modelData.expr + " ="
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                    }
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideLeft
                        text: modelData.result
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 19
                        font.bold: true
                    }
                }
                MouseArea {
                    id: hm
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: calc.useHistory(index)
                }
                Accessible.role: Accessible.ListItem
                Accessible.name: modelData.expr + " gleich " + modelData.result
            }
        }
        Text {
            anchors.centerIn: hList
            visible: calc.history.length === 0
            width: hList.width - 40
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Noch keine Rechnungen."
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
    }

    // ---- Kurzer Hinweis -------------------------------------------------------------------------
    Rectangle {
        id: toast
        function show(t) { toastText.text = t; toastTimer.restart() }
        anchors.horizontalCenter: pad.horizontalCenter
        y: 18
        width: toastText.implicitWidth + 28
        height: 34
        radius: 17
        color: Theme.raised
        border.color: Theme.hairline
        opacity: toastTimer.running ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 150 } }
        Text { id: toastText; anchors.centerIn: parent; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12 }
        Timer { id: toastTimer; interval: 1400 }
    }

    // ---- Tastatur ---------------------------------------------------------------------------------
    signal keyFlash(string k)

    function hit(k) {
        keyFlash(k)
        if (k === "=") calc.equals()
        else if (k === "C") calc.clear()
        else if (k === "back") calc.backspace()
        else calc.press(k)
    }

    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: (e) => {
            const ctrl = e.modifiers & Qt.ControlModifier
            if (ctrl && e.key === Qt.Key_C) { calc.copy(); toast.show("Ergebnis kopiert"); e.accepted = true; return }
            if (ctrl && e.key === Qt.Key_V) { calc.paste(); e.accepted = true; return }
            if (ctrl && e.key === Qt.Key_H) { win.showHistory = !win.showHistory; e.accepted = true; return }
            const map = { "+": "+", "-": "−", "*": "×", "/": "÷", ":": "÷", "x": "×", "%": "%", ",": ",", ".": ",",
                          "(": "(", ")": ")", "^": "x²" }
            if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.text === "=") { win.hit("="); e.accepted = true }
            else if (e.key === Qt.Key_Backspace) { win.hit("back"); e.accepted = true }
            else if (e.key === Qt.Key_Escape || e.key === Qt.Key_Delete) { win.hit("C"); e.accepted = true }
            else if (e.text >= "0" && e.text <= "9" && e.text.length === 1) { win.hit(e.text); e.accepted = true }
            else if (map[e.text] !== undefined) {
                const k = map[e.text]
                keyFlash(k === "(" || k === ")" ? "()" : k)
                calc.press(k)
                e.accepted = true
            }
        }
    }
}
