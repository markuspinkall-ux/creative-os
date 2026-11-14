import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Creative

// Creative Deck: links das Stream Deck mit seinen Tasten, rechts die gewählte Taste.
ApplicationWindow {
    id: win
    width: 1240
    height: 800
    minimumWidth: 1000
    minimumHeight: 640
    visible: true
    title: "Creative Deck"
    color: Theme.ground

    readonly property var sel: deck.sel
    readonly property var act: sel.aktion || ({ typ: "keine" })
    property bool recording: false

    component Caption: Text {
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 12
        font.bold: true
    }
    component Body: Text {
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        wrapMode: Text.WordWrap
    }
    component Field: TextField {
        id: f
        height: 36
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        leftPadding: 12
        placeholderTextColor: Theme.textMuted
        selectByMouse: true
        background: Rectangle { radius: 10; color: Theme.ground; border.color: f.activeFocus ? Theme.accent : Theme.hairline }
    }
    // Auswahl-Chip (Aktion, Farbe, Seite …)
    component Chip: Rectangle {
        id: chip
        property string text
        property bool active: false
        signal clicked()
        height: 32
        width: chipText.implicitWidth + 26
        radius: 10
        color: active ? Theme.accent : (chipMouse.containsMouse ? Theme.hover : Theme.raised)
        border.color: active ? Theme.accent : Theme.hairline
        Text {
            id: chipText
            anchors.centerIn: parent
            text: chip.text
            color: chip.active ? Theme.accentText : Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 12
            font.bold: chip.active
        }
        MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: chip.clicked() }
        Accessible.role: Accessible.Button
        Accessible.name: text
    }

    // ---- Kopfzeile ----------------------------------------------------------------
    header: Rectangle {
        height: 60
        color: Theme.surface
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hairline }
        Row {
            x: 20
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12
            Image {
                source: Qt.resolvedUrl("../../creative-deck.svg")
                width: 30; height: 30
                sourceSize.width: 60; sourceSize.height: 60
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: "Creative Deck"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        // Gerätestatus
        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            height: 34
            width: statusRow.implicitWidth + 28
            radius: 17
            color: Theme.raised
            border.color: Theme.hairline
            Row {
                id: statusRow
                anchors.centerIn: parent
                spacing: 8
                Rectangle {
                    width: 9; height: 9; radius: 4.5
                    anchors.verticalCenter: parent.verticalCenter
                    color: deck.connected ? Theme.ok : (deck.statusError ? Theme.flame : Theme.textMuted)
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: deck.connected ? deck.deviceName + " verbunden"
                        : deck.statusError ? "Problem mit dem Stream Deck"
                        : !deck.daemonRunning ? "Dienst startet mit der nächsten Anmeldung"
                        : "Kein Stream Deck angesteckt"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 20

        // ---- Links: Seiten und Tasten -----------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            // Seiten
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: deck.pageNames
                    delegate: Chip {
                        required property int index
                        required property string modelData
                        text: modelData
                        active: index === deck.page
                        onClicked: deck.setPage(index)
                    }
                }
                Chip {
                    text: "+ Seite"
                    onClicked: deck.setPage(deck.addPage(""))
                }
            }

            // Das Gerät
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Rectangle {
                    id: device
                    readonly property real tile: Math.min(104, (parent.width - 56 - (deck.cols - 1) * 14) / deck.cols,
                                                          (parent.height - 56 - (deck.rows - 1) * 14) / deck.rows)
                    anchors.centerIn: parent
                    width: deck.cols * tile + (deck.cols - 1) * 14 + 56
                    height: deck.rows * tile + (deck.rows - 1) * 14 + 56
                    radius: 26
                    color: "#0d0f13"
                    border.color: Qt.rgba(1, 1, 1, 0.06)
                    border.width: 2

                    Grid {
                        id: grid
                        anchors.centerIn: parent
                        columns: deck.cols
                        spacing: 14
                        Repeater {
                            model: deck.keys
                            delegate: Item {
                                id: slot
                                required property int index
                                required property var modelData
                                width: device.tile
                                height: device.tile
                                z: keyMouse.drag.active ? 10 : 0

                                DropArea {
                                    anchors.fill: parent
                                    keys: ["deck-key"]
                                    onDropped: (drop) => deck.swap(drop.source.from, slot.index)
                                }
                                Rectangle {
                                    id: face
                                    property int from: slot.index
                                    width: slot.width
                                    height: slot.height
                                    radius: width * 0.16
                                    color: slot.modelData.leer ? "#171a21" : (slot.modelData.farbe || "#232836")
                                    border.width: deck.selected === slot.index ? 3 : (keyMouse.containsMouse ? 1 : 0)
                                    border.color: deck.selected === slot.index ? Theme.accent : Qt.rgba(1, 1, 1, 0.2)
                                    opacity: keyMouse.drag.active ? 0.85 : 1
                                    Drag.active: keyMouse.drag.active
                                    Drag.keys: ["deck-key"]
                                    Drag.hotSpot.x: width / 2
                                    Drag.hotSpot.y: height / 2

                                    Image {
                                        id: sym
                                        visible: source != ""
                                        source: slot.modelData.symbolUrl
                                        readonly property real edge: parent.width * (label.text ? 0.46 : 0.62)
                                        width: edge; height: edge
                                        sourceSize.width: edge * 2; sourceSize.height: edge * 2
                                        fillMode: Image.PreserveAspectFit
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        y: parent.height * (label.text ? 0.12 : 0.19)
                                    }
                                    Text {
                                        id: label
                                        text: slot.modelData.text
                                        width: parent.width * 0.88
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        y: sym.visible ? parent.height * 0.6 : (parent.height - height) / 2
                                        horizontalAlignment: Text.AlignHCenter
                                        wrapMode: Text.WordWrap
                                        maximumLineCount: sym.visible ? 2 : 3
                                        elide: Text.ElideRight
                                        color: "#dce6ff"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Math.max(9, parent.width * (sym.visible ? 0.15 : 0.2))
                                        font.bold: true
                                    }
                                    Text {
                                        visible: slot.modelData.leer
                                        anchors.centerIn: parent
                                        text: "+"
                                        color: Qt.rgba(1, 1, 1, 0.18)
                                        font.pixelSize: parent.width * 0.32
                                    }
                                    Text {
                                        visible: slot.modelData.seite
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        anchors.margins: parent.width * 0.06
                                        text: "›"
                                        color: "#8fb3ff"
                                        font.pixelSize: parent.width * 0.18
                                        font.bold: true
                                    }
                                    MouseArea {
                                        id: keyMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        drag.target: face
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        onPressed: deck.select(slot.index)
                                        onReleased: { face.Drag.drop(); face.x = 0; face.y = 0 }
                                        onDoubleClicked: deck.testKey()
                                        onClicked: (mouse) => { if (mouse.button === Qt.RightButton) keyMenu.popup() }
                                    }
                                    Accessible.role: Accessible.Button
                                    Accessible.name: "Taste " + (slot.index + 1) + (slot.modelData.text ? ": " + slot.modelData.text : "")
                                }
                            }
                        }
                    }
                }
            }

            Body {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                color: Theme.textMuted
                font.pixelSize: 12
                text: "Taste anklicken zum Einrichten · ziehen zum Tauschen · Doppelklick zum Ausprobieren · Rechtsklick für Kopieren/Einfügen"
            }

            // Geräte-Einstellungen
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: settingsCol.implicitHeight + 32
                radius: 16
                color: Theme.surface
                border.color: Theme.hairline
                Column {
                    id: settingsCol
                    x: 16; y: 16
                    width: parent.width - 32
                    spacing: 10
                    Body {
                        width: parent.width
                        visible: deck.statusError.length > 0
                        color: Theme.flame
                        text: deck.statusError
                    }
                    RowLayout {
                        width: parent.width
                        spacing: 14
                        Caption { text: "Helligkeit" }
                        CSlider {
                            Layout.fillWidth: true
                            from: 5; to: 100
                            value: deck.brightness
                            onMoved: deck.setBrightness(Math.round(value))
                            Accessible.name: "Helligkeit"
                        }
                        Body { text: deck.brightness + " %"; Layout.preferredWidth: 44 }
                    }
                    Flow {
                        width: parent.width
                        spacing: 8
                        Caption { text: "Tasten ausschalten nach"; height: 32; verticalAlignment: Text.AlignVCenter; rightPadding: 6 }
                        Repeater {
                            model: [{ t: "Nie", m: 0 }, { t: "5 Min.", m: 5 }, { t: "15 Min.", m: 15 }, { t: "30 Min.", m: 30 }, { t: "1 Std.", m: 60 }]
                            delegate: Chip { required property var modelData; text: modelData.t; active: deck.offMinutes === modelData.m; onClicked: deck.setOffMinutes(modelData.m) }
                        }
                    }
                    Flow {
                        width: parent.width
                        spacing: 8
                        visible: !deck.connected
                        Caption { text: "Vorschau für"; height: 32; verticalAlignment: Text.AlignVCenter; rightPadding: 6 }
                        Repeater {
                            model: deck.models
                            delegate: Chip { required property string modelData; text: modelData; active: deck.deviceName === modelData; onClicked: deck.setPreviewModel(modelData) }
                        }
                    }
                }
            }
        }

        // ---- Rechts: gewählte Taste ---------------------------------------------------
        Rectangle {
            Layout.preferredWidth: 400
            Layout.fillHeight: true
            radius: 18
            color: Theme.surface
            border.color: Theme.hairline

            Flickable {
                id: side
                anchors.fill: parent
                anchors.margins: 20
                contentHeight: form.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                Column {
                    id: form
                    width: side.width
                    spacing: 12

                    Item {
                        width: parent.width
                        height: 36
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Taste " + (deck.selected + 1) + " · " + (deck.pageNames[deck.page] || "")
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 17
                            font.bold: true
                        }
                        Row {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6
                            CButton { text: "Testen"; onClicked: deck.testKey() }
                            CButton { text: "Leeren"; onClicked: deck.clearKey() }
                        }
                    }

                    Caption { text: "BESCHRIFTUNG" }
                    Field {
                        id: textField
                        width: parent.width
                        placeholderText: "z. B. Aufnahme"
                        text: win.sel.text || ""
                        onTextEdited: deck.setText(text)
                    }

                    Caption { text: "SYMBOL" }
                    Row {
                        spacing: 10
                        Rectangle {
                            width: 56; height: 56; radius: 12
                            color: win.sel.farbe || "#232836"
                            Image {
                                anchors.centerIn: parent
                                width: 34; height: 34
                                source: win.sel.symbolUrl || ""
                                sourceSize.width: 68; sourceSize.height: 68
                                fillMode: Image.PreserveAspectFit
                            }
                        }
                        Column {
                            spacing: 6
                            anchors.verticalCenter: parent.verticalCenter
                            Row {
                                spacing: 6
                                CButton { text: "Symbol wählen"; onClicked: glyphPopup.open() }
                                CButton { text: "Bild …"; onClicked: imagePicker.open() }
                            }
                            Row {
                                spacing: 6
                                CButton {
                                    visible: win.act.typ === "app" && (win.act.app || "") !== ""
                                    text: "App-Symbol"
                                    onClicked: deck.setSymbol("app:" + win.act.app)
                                }
                                CButton { text: "Ohne"; onClicked: deck.setSymbol("") }
                            }
                        }
                    }

                    Caption { text: "FARBE" }
                    Row {
                        spacing: 8
                        Repeater {
                            model: deck.colors
                            delegate: Rectangle {
                                required property string modelData
                                width: 32; height: 32; radius: 9
                                color: modelData || "#232836"
                                border.width: (win.sel.farbe || "") === modelData ? 3 : 1
                                border.color: (win.sel.farbe || "") === modelData ? Theme.accent : Qt.rgba(1, 1, 1, 0.15)
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: deck.setColor(parent.modelData) }
                                Accessible.role: Accessible.Button
                                Accessible.name: "Farbe " + (modelData || "Standard")
                            }
                        }
                    }

                    Divider { width: parent.width }

                    Caption { text: "AKTION" }
                    Flow {
                        width: parent.width
                        spacing: 6
                        Repeater {
                            model: deck.actionTypes
                            delegate: Chip {
                                required property var modelData
                                text: modelData.name
                                active: win.act.typ === modelData.id
                                onClicked: deck.setActionType(modelData.id)
                            }
                        }
                    }
                    Body {
                        width: parent.width
                        color: Theme.textMuted
                        text: win.sel.beschreibung || ""
                    }

                    // --- Programm starten ---
                    Column {
                        visible: win.act.typ === "app"
                        width: parent.width
                        spacing: 8
                        Field { id: appSearch; width: parent.width; placeholderText: "Programm suchen …" }
                        Rectangle {
                            width: parent.width
                            height: 240
                            radius: 12
                            color: Theme.ground
                            border.color: Theme.hairline
                            ListView {
                                id: appList
                                anchors.fill: parent
                                anchors.margins: 4
                                clip: true
                                model: win.act.typ === "app" ? deck.appList.filter(a => a.name.toLowerCase().indexOf(appSearch.text.toLowerCase()) >= 0) : []
                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                                delegate: Rectangle {
                                    required property var modelData
                                    width: appList.width
                                    height: 38
                                    radius: 8
                                    color: (win.act.app || "") === modelData.id ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.16)
                                         : appMouse.containsMouse ? Theme.hover : "transparent"
                                    Row {
                                        x: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 10
                                        Image { source: modelData.iconUrl; width: 22; height: 22; sourceSize.width: 44; sourceSize.height: 44; anchors.verticalCenter: parent.verticalCenter }
                                        Text { text: modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                                    }
                                    MouseArea { id: appMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: deck.setActionField("app", parent.modelData.id) }
                                }
                            }
                        }
                    }

                    // --- Befehl / Webseite ---
                    Field {
                        visible: win.act.typ === "befehl"
                        width: parent.width
                        placeholderText: "z. B. notify-send Hallo"
                        text: win.act.befehl || ""
                        onTextEdited: deck.setActionField("befehl", text)
                    }
                    Field {
                        visible: win.act.typ === "webseite"
                        width: parent.width
                        placeholderText: "z. B. twitch.tv"
                        text: win.act.url || ""
                        onTextEdited: deck.setActionField("url", text)
                    }

                    // --- Tastenkürzel aufnehmen ---
                    Rectangle {
                        id: recorder
                        visible: win.act.typ === "tasten"
                        width: parent.width
                        height: 48
                        radius: 12
                        color: win.recording ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.14) : Theme.ground
                        border.color: win.recording || recorder.activeFocus ? Theme.accent : Theme.hairline
                        activeFocusOnTab: true
                        Text {
                            anchors.centerIn: parent
                            text: win.recording ? "Jetzt die Tasten drücken …"
                                : (win.sel.tastenText || "Hier klicken und Tastenkürzel drücken")
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: !win.recording && (win.sel.tastenText || "") !== ""
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { win.recording = true; recorder.forceActiveFocus() } }
                        Keys.onPressed: (event) => {
                            if (!win.recording) return
                            const combo = deck.shortcutFromKey(event.key, event.modifiers)
                            if (combo) {
                                deck.setActionField("tasten", combo)
                                win.recording = false
                            }
                            event.accepted = true
                        }
                        onActiveFocusChanged: if (!activeFocus) win.recording = false
                    }

                    // --- Text einfügen ---
                    Rectangle {
                        visible: win.act.typ === "text"
                        width: parent.width
                        height: 110
                        radius: 10
                        color: Theme.ground
                        border.color: textArea.activeFocus ? Theme.accent : Theme.hairline
                        TextArea {
                            id: textArea
                            anchors.fill: parent
                            anchors.margins: 4
                            wrapMode: TextEdit.Wrap
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            placeholderText: "Dieser Text wird eingefügt, wo der Cursor steht"
                            placeholderTextColor: Theme.textMuted
                            background: null
                            text: win.act.text || ""
                            onTextChanged: if (activeFocus) deck.setActionField("text", text)
                        }
                    }

                    // --- Auswahl je Aktion ---
                    Flow {
                        width: parent.width
                        spacing: 6
                        visible: ["medien", "lautstaerke", "obs", "helligkeit"].indexOf(win.act.typ) >= 0
                        Repeater {
                            model: win.act.typ === "medien" ? [["play-pause", "Abspielen/Pause"], ["weiter", "Nächster Titel"], ["zurueck", "Voriger Titel"], ["stopp", "Stopp"]]
                                 : win.act.typ === "lautstaerke" ? [["lauter", "Lauter"], ["leiser", "Leiser"], ["stumm", "Ton aus/an"]]
                                 : win.act.typ === "obs" ? [["aufnahme", "Aufnahme"], ["stream", "Stream"], ["pause", "Aufnahme pausieren"], ["replay", "Replay speichern"], ["replay-an", "Replay-Puffer"], ["szene", "Szene wechseln"], ["stumm", "Quelle stumm"]]
                                 : win.act.typ === "helligkeit" ? [["hoch", "Heller"], ["runter", "Dunkler"]] : []
                            delegate: Chip {
                                required property var modelData
                                text: modelData[1]
                                active: win.act.was === modelData[0]
                                onClicked: deck.setActionField("was", modelData[0])
                            }
                        }
                    }
                    Field {
                        visible: win.act.typ === "obs" && (win.act.was === "szene" || win.act.was === "stumm")
                        width: parent.width
                        placeholderText: win.act.was === "szene" ? "Name der Szene wie in OBS" : "Name der Quelle wie in OBS (z. B. Mikrofon/AUX)"
                        text: win.act.name || ""
                        onTextEdited: deck.setActionField("name", text)
                    }

                    // --- Seite öffnen ---
                    Flow {
                        visible: win.act.typ === "seite"
                        width: parent.width
                        spacing: 6
                        Repeater {
                            model: deck.pageNames
                            delegate: Chip {
                                required property int index
                                required property string modelData
                                text: modelData
                                active: win.act.seite === index
                                onClicked: deck.setTargetPage(index)
                            }
                        }
                        Chip { text: "+ Neue Seite"; onClicked: deck.setTargetPage(deck.addPage(textField.text)) }
                    }

                    // --- Ton abspielen ---
                    Row {
                        visible: win.act.typ === "sound"
                        spacing: 8
                        CButton { text: "Ton wählen …"; onClicked: soundPicker.open() }
                    }

                    // --- OBS-Verbindung ---
                    Rectangle {
                        visible: win.act.typ === "obs"
                        width: parent.width
                        implicitHeight: obsCol.implicitHeight + 24
                        radius: 12
                        color: Theme.raised
                        Column {
                            id: obsCol
                            x: 12; y: 12
                            width: parent.width - 24
                            spacing: 8
                            Caption { text: "VERBINDUNG ZU OBS" }
                            Body {
                                width: parent.width
                                color: Theme.textMuted
                                font.pixelSize: 12
                                text: "In OBS: Werkzeuge › WebSocket-Servereinstellungen › „WebSocket-Server aktivieren“. Port und Passwort von dort hier eintragen."
                            }
                            Row {
                                spacing: 8
                                Field { id: obsHost; width: 170; text: deck.obsHost; placeholderText: "localhost" }
                                Field { id: obsPort; width: 80; text: String(deck.obsPort); inputMethodHints: Qt.ImhDigitsOnly }
                            }
                            Field { id: obsPw; width: parent.width; text: deck.obsPassword; echoMode: TextInput.Password; placeholderText: "Passwort" }
                            Row {
                                spacing: 8
                                CButton { text: "Speichern"; primary: true; onClicked: deck.setObs(obsHost.text, parseInt(obsPort.text) || 4455, obsPw.text) }
                                CButton { text: "Verbindung testen"; onClicked: { deck.setObs(obsHost.text, parseInt(obsPort.text) || 4455, obsPw.text); deck.testObs() } }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- Rechtsklick auf eine Taste -----------------------------------------------------
    Menu {
        id: keyMenu
        MenuItem { text: "Ausprobieren"; onTriggered: deck.testKey() }
        MenuItem { text: "Kopieren"; onTriggered: deck.copyKey() }
        MenuItem { text: "Einfügen"; onTriggered: deck.pasteKey() }
        MenuItem { text: "Leeren"; onTriggered: deck.clearKey() }
        MenuSeparator {}
        MenuItem {
            text: "Seite umbenennen"
            onTriggered: { renameField.text = deck.pageNames[deck.page]; renamePopup.open() }
        }
        MenuItem { text: "Seite löschen"; enabled: deck.pageNames.length > 1; onTriggered: removeDialog.open() }
    }

    Popup {
        id: renamePopup
        anchors.centerIn: Overlay.overlay
        width: 380
        modal: true
        padding: 22
        background: Rectangle { radius: 16; color: Theme.raised; border.color: Theme.hairline }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }
        contentItem: Column {
            spacing: 12
            Text { text: "Seite umbenennen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
            Field { id: renameField; width: parent.width; onAccepted: { deck.renamePage(deck.page, text); renamePopup.close() } }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: renamePopup.close() }
                CButton { text: "Umbenennen"; primary: true; onClicked: { deck.renamePage(deck.page, renameField.text); renamePopup.close() } }
            }
        }
    }

    ConfirmDialog {
        id: removeDialog
        title: "Seite löschen?"
        text: "Die Seite „" + (deck.pageNames[deck.page] || "") + "“ und alle ihre Tasten werden gelöscht."
        confirmText: "Löschen"
        danger: true
        onConfirmed: deck.removePage(deck.page)
    }

    // ---- Symbol wählen ------------------------------------------------------------------
    Popup {
        id: glyphPopup
        anchors.centerIn: Overlay.overlay
        width: 520
        height: 460
        modal: true
        padding: 20
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }
        contentItem: Column {
            spacing: 12
            Text { text: "Symbol wählen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
            GridView {
                width: parent.width
                height: parent.height - 40
                clip: true
                cellWidth: 60
                cellHeight: 60
                model: deck.glyphs
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    required property var modelData
                    width: 52; height: 52; radius: 12
                    color: glyphMouse.containsMouse ? Theme.hover : "#232836"
                    Image { anchors.centerIn: parent; width: 28; height: 28; source: modelData.url; sourceSize.width: 56; sourceSize.height: 56 }
                    MouseArea { id: glyphMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { deck.setGlyph(parent.modelData.name); glyphPopup.close() } }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.name
                }
            }
        }
    }

    ImagePicker { id: imagePicker; onAccepted: (url) => deck.setImage(url.toString()) }
    FilePicker {
        id: soundPicker
        title: "Ton wählen"
        nameFilters: ["*.ogg", "*.oga", "*.wav", "*.mp3", "*.flac", "*.opus"]
        onAccepted: (url) => deck.setActionField("datei", decodeURIComponent(url.toString().replace("file://", "")))
    }

    // ---- Meldung unten ----------------------------------------------------------------------
    Rectangle {
        visible: deck.message.length > 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        width: Math.min(560, toastText.implicitWidth + 40)
        height: toastText.implicitHeight + 22
        radius: 14
        color: Theme.raised
        border.color: Theme.hairline
        Text {
            id: toastText
            anchors.centerIn: parent
            width: Math.min(520, implicitWidth)
            text: deck.message
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
        }
        Timer { running: parent.visible; interval: 3500; onTriggered: deck.clearMessage() }
    }
}
