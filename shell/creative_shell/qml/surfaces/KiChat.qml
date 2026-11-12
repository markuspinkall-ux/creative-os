import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import Creative

// Chat-Fenster des KI-Helfers (lokales Open-Source-Modell).
// Ein normales Fenster – der Schreibtisch selbst bekommt unter Wayland keine Tastatur.
Window {
    id: win
    property var ki
    title: "KI-Helfer"
    width: 500
    height: 680
    minimumWidth: 380
    minimumHeight: 460
    color: Theme.surface
    flags: Qt.Dialog

    function openChat(prefill) {
        show()
        raise()
        requestActivate()
        if (prefill !== undefined && prefill.length) input.text = prefill
        Qt.callLater(() => { input.forceActiveFocus(); list.positionViewAtEnd() })
    }
    function send() {
        const t = input.text.trim()
        if (!t.length || ki.busy) return
        ki.ask(t)
        input.text = ""
    }

    Shortcut { sequence: "Escape"; onActivated: win.close() }

    Connections {
        target: win.ki
        function onMessagesChanged() { Qt.callLater(() => list.positionViewAtEnd()) }
    }

    readonly property bool setupMode: ki.state !== "bereit"

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- Kopf ------------------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 14
            Layout.bottomMargin: 10
            spacing: 10
            Rectangle {
                width: 38; height: 38; radius: 12
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                SvgIcon { anchors.centerIn: parent; name: "sparkle"; size: 20 }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Text { text: "KI-Helfer"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
                Text {
                    Layout.fillWidth: true
                    text: (ki.modelName ? ki.modelName + " · " : "") + "läuft auf deinem PC · Open Source"
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                    elide: Text.ElideRight
                }
            }
            IconButton {
                visible: !win.setupMode
                icon: "plus"; iconSize: 18; width: 34; height: 34
                label: "Neues Gespräch"
                onClicked: { ki.clear(); input.forceActiveFocus() }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

        // ---- Einrichten ---------------------------------------------------------------
        Flickable {
            visible: win.setupMode
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: setupCol.implicitHeight + 32
            clip: true
            ColumnLayout {
                id: setupCol
                x: 20; y: 18
                width: parent.width - 40
                spacing: 12
                Text {
                    Layout.fillWidth: true
                    text: "Einmal einrichten"
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                    text: "Der KI-Helfer beantwortet Wissensfragen und formuliert E-Mails – ohne Konto und ohne Cloud. "
                        + "Dafür wird einmalig ein Sprachmodell (Gemma 4 von Google, Apache-2.0-Lizenz) geladen. "
                        + "Es gilt danach für alle Benutzerkonten auf diesem PC."
                }
                Repeater {
                    model: ki.models
                    delegate: Rectangle {
                        id: option
                        required property var modelData
                        readonly property bool chosen: ki.choice === modelData.key
                        Layout.fillWidth: true
                        implicitHeight: optCol.implicitHeight + 22
                        radius: 14
                        color: chosen ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.13)
                                      : (optMouse.containsMouse ? Theme.hover : Theme.subtle)
                        border.color: chosen ? Theme.accent : Theme.hairline
                        border.width: chosen ? 1.5 : 1
                        opacity: ki.state === "laedt" && !chosen ? 0.5 : 1
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12
                            Rectangle {
                                width: 18; height: 18; radius: 9
                                color: "transparent"
                                border.color: option.chosen ? Theme.accent : Theme.track
                                border.width: 2
                                Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; color: Theme.accent; visible: option.chosen }
                            }
                            ColumnLayout {
                                id: optCol
                                Layout.fillWidth: true
                                spacing: 2
                                RowLayout {
                                    spacing: 8
                                    Text { text: option.modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                                    Rectangle {
                                        visible: option.modelData.empfohlen
                                        implicitWidth: rec.implicitWidth + 14; implicitHeight: 20; radius: 10
                                        color: Qt.rgba(Theme.ok.r, Theme.ok.g, Theme.ok.b, 0.18)
                                        Text { id: rec; anchors.centerIn: parent; text: "Empfohlen für deinen PC"; color: Theme.ok; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: option.modelData.beschreibung + " · " + String(option.modelData.gb).replace(".", ",") + " GB"
                                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                        MouseArea {
                            id: optMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: ki.state !== "laedt"
                            cursorShape: Qt.PointingHandCursor
                            onClicked: ki.chooseModel(option.modelData.key)
                        }
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: modelData.name
                        Accessible.checked: chosen
                    }
                }
                // Fortschritt
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: ki.state === "laedt"
                    spacing: 6
                    Rectangle {
                        Layout.fillWidth: true
                        height: 8; radius: 4
                        color: Theme.tint(0.08)
                        Rectangle {
                            width: parent.width * Math.max(0.02, ki.progress / 100)
                            height: parent.height; radius: 4
                            color: Theme.accent
                            Behavior on width { NumberAnimation { duration: 300 } }
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: ki.progress + " % · " + ki.status
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Du kannst das Fenster schließen – der Download läuft weiter."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                }
                Text {
                    Layout.fillWidth: true
                    visible: ki.state === "einrichten" && ki.status.length > 0
                    text: ki.status
                    color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 13
                    wrapMode: Text.Wrap
                }
                CButton {
                    Layout.alignment: Qt.AlignRight
                    visible: ki.state === "einrichten"
                    primary: true
                    text: "Jetzt einrichten"
                    onClicked: ki.install()
                }
            }
        }

        // ---- Verlauf --------------------------------------------------------------------
        ListView {
            id: list
            visible: !win.setupMode
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            topMargin: 14
            bottomMargin: 14
            model: ki.messages
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            // Leerer Verlauf: Begrüßung + Beispiele
            Column {
                visible: list.count === 0
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, 380)
                spacing: 12
                SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "sparkle"; size: 34 }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: "Was möchtest du wissen?"
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: "Frag nach Allgemeinwissen, lass dir etwas erklären oder eine E-Mail formulieren."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                }
                Repeater {
                    model: [
                        "Wer war der erste Bundeskanzler?",
                        "Erklär mir einfach, wie ein Regenbogen entsteht.",
                        "Schreib eine kurze E-Mail an meinen Vermieter: Die Heizung im Bad ist kaputt.",
                        "Wie viele Einwohner hat Deutschland?"
                    ]
                    delegate: Rectangle {
                        required property string modelData
                        width: parent.width
                        height: exText.implicitHeight + 18
                        radius: 12
                        color: exMouse.containsMouse ? Theme.hover : Theme.subtle
                        border.color: Theme.hairline
                        Text {
                            id: exText
                            anchors.fill: parent
                            anchors.margins: 9
                            anchors.leftMargin: 14
                            text: parent.modelData
                            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
                            wrapMode: Text.Wrap
                            verticalAlignment: Text.AlignVCenter
                        }
                        MouseArea { id: exMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ki.ask(parent.modelData) }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData
                    }
                }
            }

            delegate: Item {
                id: msg
                required property var modelData
                required property int index
                readonly property bool mine: modelData.role === "user"
                readonly property bool last: index === list.count - 1
                width: list.width
                height: bubble.height + (tools.visible ? tools.height + 4 : 0)

                Rectangle {
                    id: bubble
                    x: msg.mine ? parent.width - width - 14 : 14
                    width: Math.min(list.width * (msg.mine ? 0.8 : 0.9), body.implicitWidth + 28)
                    height: Math.max(40, body.implicitHeight + 20)
                    radius: 16
                    color: msg.mine ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, Theme.light ? 0.16 : 0.22)
                                    : Theme.raised
                    border.color: msg.modelData.fehler ? Theme.flame : "transparent"
                    TextEdit {
                        id: body
                        x: 14; y: 10
                        width: Math.min(implicitWidth, list.width * (msg.mine ? 0.8 : 0.9) - 28)
                        text: msg.modelData.text.length ? msg.modelData.text
                              : (win.ki.status.length ? win.ki.status : "Denkt nach …")
                        textFormat: msg.mine ? TextEdit.PlainText : TextEdit.MarkdownText
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: msg.modelData.text.length ? Theme.text : Theme.textMuted
                        selectionColor: Theme.accent
                        selectedTextColor: Theme.accentText
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        onLinkActivated: (link) => Qt.openUrlExternally(link)
                        Accessible.name: msg.mine ? "Du: " + text : "KI-Helfer: " + text
                    }
                }
                Row {
                    id: tools
                    visible: !msg.mine && msg.modelData.text.length > 0 && !(msg.last && win.ki.busy)
                    x: 18
                    anchors.top: bubble.bottom
                    anchors.topMargin: 4
                    spacing: 6
                    Rectangle {
                        width: copyRow.implicitWidth + 16; height: 24; radius: 12
                        color: copyMouse.containsMouse ? Theme.hover : "transparent"
                        Row {
                            id: copyRow
                            anchors.centerIn: parent
                            spacing: 5
                            SvgIcon { name: "copy"; size: 13; anchors.verticalCenter: parent.verticalCenter }
                            Text { id: copyLabel; text: "Kopieren"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea {
                            id: copyMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { win.ki.copy(msg.index); copyLabel.text = "Kopiert ✓"; copyReset.restart() }
                        }
                        Timer { id: copyReset; interval: 1600; onTriggered: copyLabel.text = "Kopieren" }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Antwort kopieren"
                    }
                    Repeater {
                        model: msg.modelData.quellen || []
                        delegate: Rectangle {
                            required property var modelData
                            width: srcText.implicitWidth + 16; height: 24; radius: 12
                            color: srcMouse.containsMouse ? Theme.hover : "transparent"
                            border.color: Theme.hairline
                            Text {
                                id: srcText
                                anchors.centerIn: parent
                                text: "W  " + parent.modelData.titel
                                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                                width: Math.min(implicitWidth, 160)
                                elide: Text.ElideRight
                            }
                            MouseArea { id: srcMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(parent.modelData.url) }
                            Accessible.role: Accessible.Link
                            Accessible.name: "Wikipedia: " + modelData.titel
                        }
                    }
                }
            }
        }

        // ---- Eingabe ------------------------------------------------------------------------
        Rectangle { visible: !win.setupMode; Layout.fillWidth: true; height: 1; color: Theme.hairline }
        Item {
            visible: !win.setupMode
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(160, Math.max(52, input.implicitHeight + 8)) + 24
            Rectangle {
                anchors.fill: parent
                anchors.margins: 12
                radius: 22
                color: Theme.ground
                border.color: input.activeFocus ? Theme.accent : Theme.hairline
                border.width: input.activeFocus ? 1.5 : 1
                ScrollView {
                    anchors.left: parent.left
                    anchors.right: sendBtn.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: 8
                    TextArea {
                        id: input
                        placeholderText: "Frag mich etwas …"
                        placeholderTextColor: Theme.textMuted
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        background: null
                        topPadding: 13
                        bottomPadding: 13
                        Accessible.name: "Frage an den KI-Helfer"
                        Keys.onReturnPressed: (event) => {
                            if (event.modifiers & Qt.ShiftModifier) event.accepted = false
                            else win.send()
                        }
                        Keys.onEnterPressed: win.send()
                    }
                }
                Rectangle {
                    id: sendBtn
                    anchors.right: parent.right
                    anchors.rightMargin: 7
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 7
                    width: 38; height: 38; radius: 19
                    color: win.ki.busy ? Theme.tint(0.12) : (input.text.trim().length ? Theme.accent : Theme.tint(0.08))
                    SvgIcon {
                        anchors.centerIn: parent
                        name: win.ki.busy ? "stop" : "send"
                        size: 18
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.ki.busy ? win.ki.stop() : win.send()
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: win.ki.busy ? "Antwort anhalten" : "Senden"
                }
            }
        }
    }
}
