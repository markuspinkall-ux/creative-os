import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import QtWebEngine
import Creative
import Studio

// Studio – Aufnehmen und Streamen im Gibeon-Look.
// Links Chat (Twitch/YouTube), Mitte Titel + Vorschau + Tonmischer, rechts Quellen und Knöpfe.
ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1100
    minimumHeight: 700
    visible: true
    title: "Studio"
    color: Theme.ground

    readonly property var st: studio.state
    readonly property var cfg: st.cfg || ({})
    readonly property var acc: st.accounts || ({})
    readonly property bool locked: !!st.locked
    property string chatTab: acc.twitch && acc.twitch.connected ? "twitch" : "youtube"
    property string loginService: ""
    property string loginCode: ""
    property string loginUrl: ""
    property string categoryId: ""
    property string categoryName: ""
    property var categoryHits: []
    property string selected: ""                 // ausgewählte Quelle (id) in der aktiven Szene
    property int renaming: -1                    // Szene, deren Namen gerade bearbeitet wird
    readonly property var items: st.items || []
    readonly property int selIndex: items.findIndex(i => i.id === win.selected)
    readonly property var selItem: selIndex >= 0 ? items[selIndex] : null
    readonly property string redLive: "#e5484d"

    onClosing: (close) => {
        if (studio.busyOutputs()) {
            close.accepted = false
            quitDialog.open = true
        } else {
            studio.shutdown()
        }
    }

    Connections {
        target: studio
        function onToast(text) { toast.show(text) }
        function onLoginCode(service, code, url) {
            win.loginService = code ? service : ""
            win.loginCode = code
            win.loginUrl = url
        }
        function onCategories(service, hits) { win.categoryHits = hits }
    }

    // Titel und Kategorie aus den Konten übernehmen, sobald sie geladen sind
    function syncTitle() {
        const t = acc.twitch && acc.twitch.connected ? acc.twitch : (acc.youtube && acc.youtube.connected ? acc.youtube : null)
        if (t && !titleField.activeFocus && !titleField.edited) {
            titleField.text = t.title
            categoryField.text = acc.twitch && acc.twitch.connected ? acc.twitch.category : ""
            win.categoryId = acc.twitch && acc.twitch.connected ? acc.twitch.categoryId : ""
            win.categoryName = categoryField.text
        }
    }
    onAccChanged: syncTitle()

    // Strg+1 … Strg+9: Szene wechseln
    Repeater {
        model: 9
        delegate: Item {
            required property int index
            Shortcut { sequence: "Ctrl+" + (index + 1); onActivated: studio.setScene(index) }
        }
    }
    Shortcut { sequence: "Delete"; enabled: win.selIndex >= 0 && !(win.activeFocusItem && win.activeFocusItem.cursorPosition !== undefined); onActivated: { studio.removeItem(win.selIndex); win.selected = "" } }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 14

        // ---------------- Links: Quellen und Chat ----------------
        ColumnLayout {
            id: leftCol
            Layout.fillHeight: true
            Layout.preferredWidth: 300
            spacing: 14

            Card {
                id: sourcesPane
                Layout.fillWidth: true
                Layout.fillHeight: !cfg.chat_open
                // mit Chat: so hoch wie nötig, höchstens gut die Hälfte – der Rest gehört dem Chat
                Layout.preferredHeight: cfg.chat_open ? Math.min(srcCol.implicitHeight + 32, leftCol.height * 0.58) : -1
                Flickable {
                    anchors.fill: parent
                    anchors.margins: 16
                    contentHeight: srcCol.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    ColumnLayout {
                        id: srcCol
                        width: parent.width
                        spacing: 10
                        Heading { text: "Quellen in „" + ((st.scenes || [])[st.scene] || {name: ""}).name + "“" }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: win.items.length ? "In der Vorschau anklicken und ziehen. An den Ecken größer oder kleiner ziehen, Doppelklick füllt das Bild."
                                                   : "Diese Szene ist noch leer – füge unten eine Quelle hinzu."
                            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                        }
                        // vorne liegende Quellen stehen oben
                        Repeater {
                            model: win.items.slice().reverse()
                            delegate: SourceRow {
                                required property var modelData
                                required property int index
                                item: modelData
                                pos: win.items.length - 1 - index
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 6
                            rowSpacing: 6
                            CButton { Layout.fillWidth: true; text: "+ Bildschirm"; onClicked: selectAt(studio.addSource("screen")) }
                            CButton { Layout.fillWidth: true; text: "+ Kamera"; onClicked: selectAt(studio.addSource("camera")) }
                            CButton { Layout.fillWidth: true; text: "+ Capture-Karte"; onClicked: selectAt(studio.addSource("capture")) }
                            CButton { Layout.fillWidth: true; text: "+ Bild"; onClicked: imagePicker.open() }
                        }
                        // Elgato-Karten ohne Treiber: lieber klar sagen als still nichts zeigen
                        Repeater {
                            model: st.unsupported || []
                            delegate: Rectangle {
                                required property string modelData
                                Layout.fillWidth: true
                                implicitHeight: unsupText.implicitHeight + 18
                                radius: Theme.radiusRow
                                color: Qt.rgba(0.95, 0.55, 0.2, 0.14)
                                border.color: Qt.rgba(0.95, 0.55, 0.2, 0.5)
                                Text {
                                    id: unsupText
                                    anchors.fill: parent
                                    anchors.margins: 9
                                    wrapMode: Text.WordWrap
                                    text: modelData
                                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 11
                                }
                            }
                        }

                        // Einstellungen der ausgewählten Quelle
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: !!win.selItem
                            spacing: 8
                            Divider { Layout.fillWidth: true; Layout.topMargin: 4 }
                            Heading { text: win.selItem ? win.selItem.label : "" }
                            Pick {
                                Layout.fillWidth: true
                                visible: !!win.selItem && (win.selItem.kind === "camera" || win.selItem.kind === "capture")
                                enabled: !win.locked
                                items: st.videoDevices || []
                                current: win.selItem ? win.selItem.device : ""
                                empty: "Keine Kamera gefunden"
                                onChosen: (id) => { if (win.selIndex >= 0 && id !== win.selItem.device) studio.setItem(win.selIndex, "device", id) }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                visible: !!win.selItem && (win.selItem.kind === "camera" || win.selItem.kind === "capture")
                                Text { text: "Abgerundete Ecken"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; Layout.fillWidth: true }
                                CSwitch { checked: !!(win.selItem && win.selItem.round); label: "Abgerundete Ecken"; onToggled: (v) => studio.setItem(win.selIndex, "round", v) }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                visible: !!win.selItem && (win.selItem.kind === "camera" || win.selItem.kind === "capture")
                                Column {
                                    Layout.fillWidth: true
                                    Text { text: "Grünen Hintergrund entfernen"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
                                    Text { text: "Für Greenscreen und die Gibeon Kamera"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                                }
                                CSwitch { checked: !!(win.selItem && win.selItem.green); label: "Grünen Hintergrund entfernen"; onToggled: (v) => studio.setItem(win.selIndex, "green", v) }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                CButton { Layout.fillWidth: true; text: "Bildfüllend"; onClicked: studio.fillItem(win.selIndex) }
                                CButton { Layout.fillWidth: true; danger: true; text: "Entfernen"; onClicked: { studio.removeItem(win.selIndex); win.selected = "" } }
                            }
                        }
                    }
                }
            }

            // ---------------- Chat ----------------
            Card {
                id: chatPane
                Layout.fillWidth: true
                Layout.fillHeight: !!cfg.chat_open
                Layout.preferredHeight: cfg.chat_open ? -1 : 52

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10
                    visible: cfg.chat_open

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: ["twitch", "youtube"].concat(acc.kick && acc.kick.connected ? ["kick"] : [])
                            delegate: Pill {
                                required property string modelData
                                Layout.fillWidth: true
                                text: modelData === "twitch" ? "Twitch" : modelData === "kick" ? "Kick" : "YouTube"
                                dot: modelData === "twitch" ? "#9f7aea" : modelData === "kick" ? "#53fc18" : "#ff4e45"
                                checked: win.chatTab === modelData
                                onClicked: win.chatTab = modelData
                            }
                        }
                        IconBtn { icon: "chevron-down"; tip: "Chat einklappen"; onClicked: studio.set("chat_open", false) }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        readonly property var a: acc[win.chatTab] || ({})

                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusRow
                            color: Theme.raised
                            clip: true
                            WebEngineView {
                                id: chatView
                                anchors.fill: parent
                                anchors.margins: 1
                                visible: !!parent.parent.a.chat
                                url: parent.parent.a.chat || "about:blank"
                                backgroundColor: Theme.raised
                                settings.javascriptCanOpenWindows: false
                                profile: WebEngineProfile {
                                    storageName: "gibeon-studio-chat"
                                    offTheRecord: false
                                    persistentCookiesPolicy: WebEngineProfile.ForcePersistentCookies
                                }
                                // Eigenes Eingabefeld unten – das der Seite ausblenden, Hintergrund angleichen
                                onLoadingChanged: (info) => {
                                    if (info.status !== WebEngineView.LoadSucceededStatus)
                                        return
                                    const css = ".chat-input, .chat-input-tray__open, yt-live-chat-message-input-renderer, #input-panel"
                                        + "{display:none!important} body{background:" + Theme.raised + "!important}"
                                    runJavaScript("(function(){var s=document.createElement('style');s.textContent="
                                                  + JSON.stringify(css) + ";document.head.appendChild(s);})()")
                                }
                            }
                            Column {
                                anchors.centerIn: parent
                                width: parent.width - 40
                                spacing: 12
                                visible: !chatView.visible
                                Text {
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.WordWrap
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 13
                                    text: win.chatTab === "kick" ? "Kick-Chat wird geladen …" : !parent.parent.parent.a.connected
                                          ? "Melde dich bei " + (win.chatTab === "twitch" ? "Twitch" : "YouTube") + " an – dann erscheint hier dein Chat."
                                          : (win.chatTab === "youtube" ? "Der YouTube-Chat erscheint, sobald deine Übertragung bereit ist." : "Chat wird geladen …")
                                }
                                CButton {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    visible: !parent.parent.parent.a.connected
                                    primary: true
                                    text: "Mit " + (win.chatTab === "twitch" ? "Twitch" : "YouTube") + " anmelden"
                                    onClicked: studio.login(win.chatTab)
                                }
                                CButton {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    visible: parent.parent.parent.a.connected && win.chatTab === "youtube"
                                    text: "Neu laden"
                                    onClicked: studio.reloadChannel("youtube")
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        visible: win.chatTab !== "kick"            // bei Kick schreibst du direkt im Chat oben
                    enabled: !!(acc[win.chatTab] && acc[win.chatTab].connected)
                        opacity: enabled ? 1 : 0.5
                        Field {
                            id: chatInput
                            Layout.fillWidth: true
                            placeholderText: "Nachricht an den Chat"
                            onAccepted: { studio.sendChat(win.chatTab, text); text = "" }
                        }
                        IconBtn { icon: "send"; tip: "Senden"; onClicked: { studio.sendChat(win.chatTab, chatInput.text); chatInput.text = "" } }
                    }
                }
                RowLayout {
                    visible: !cfg.chat_open
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 8
                    Text { text: "Chat"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true; Layout.fillWidth: true }
                    IconBtn { icon: "chevron-down"; turn: 180; tip: "Chat zeigen"; onClicked: studio.set("chat_open", true) }
                }
            }
        }

        // ---------------- Mitte ----------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            // Titel, Kategorie, Konten
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Field {
                    id: titleField
                    property bool edited: false
                    Layout.fillWidth: true
                    placeholderText: "Stream-Titel"
                    onTextEdited: edited = true
                    onAccepted: applyBtn.clicked()
                }
                Field {
                    id: categoryField
                    Layout.preferredWidth: 220
                    placeholderText: "Kategorie (Twitch)"
                    visible: !!(acc.twitch && acc.twitch.connected)
                    onTextEdited: { win.categoryId = ""; catTimer.restart(); titleField.edited = true }
                    Timer { id: catTimer; interval: 300; onTriggered: studio.searchCategory(categoryField.text) }
                    Popup {
                        y: parent.height + 4
                        width: parent.width
                        visible: categoryField.activeFocus && win.categoryHits.length > 0 && win.categoryId === ""
                        padding: 6
                        background: Rectangle { radius: Theme.radiusRow; color: Theme.surface; border.color: Theme.hairline }
                        contentItem: Column {
                            spacing: 2
                            Repeater {
                                model: win.categoryHits
                                delegate: Rectangle {
                                    required property var modelData
                                    width: parent ? parent.width : 0
                                    height: 32
                                    radius: 8
                                    color: hit.containsMouse ? Theme.hover : "transparent"
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: 10
                                        width: parent.width - 20
                                        elide: Text.ElideRight
                                        text: modelData.name
                                        color: Theme.text
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 13
                                    }
                                    MouseArea {
                                        id: hit
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: {
                                            win.categoryId = modelData.id
                                            win.categoryName = modelData.name
                                            categoryField.text = modelData.name
                                            win.categoryHits = []
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                CButton {
                    id: applyBtn
                    primary: true
                    text: "Übernehmen"
                    enabled: (acc.twitch && acc.twitch.connected) || (acc.youtube && acc.youtube.connected)
                    onClicked: {
                        studio.applyTitle(titleField.text, win.categoryId, win.categoryName)
                        titleField.edited = false
                    }
                }
                AccountChip { service: "twitch"; label: "Twitch"; dotColor: "#9f7aea" }
                AccountChip { service: "youtube"; label: "YouTube"; dotColor: "#ff4e45" }
            }

            // Vorschau
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: "#0b0d12"
                clip: true

                Preview {
                    id: preview
                    anchors.fill: parent
                    anchors.margins: 1
                }

                // Bearbeiten direkt im Bild: Quelle anklicken, ziehen zum Verschieben,
                // an den Ecken ziehen zum Vergrößern/Verkleinern (Seitenverhältnis bleibt)
                Item {
                    id: stage
                    readonly property real fitW: preview ? Math.min(preview.width, preview.height * 16 / 9) : 0
                    x: preview ? preview.x + (preview.width - fitW) / 2 : 0
                    y: preview ? preview.y + (preview.height - fitW * 9 / 16) / 2 : 0
                    width: fitW
                    height: fitW * 9 / 16
                    readonly property real snap: 0.012

                    function snapX(x, w) {
                        for (const t of [0, 1 - w, (1 - w) / 2])
                            if (Math.abs(x - t) < snap) return t
                        return x
                    }
                    function snapY(y, h) {
                        for (const t of [0, 1 - h, (1 - h) / 2])
                            if (Math.abs(y - t) < snap) return t
                        return y
                    }

                    MouseArea { anchors.fill: parent; onPressed: win.selected = "" }

                    Repeater {
                        model: win.items
                        delegate: Item {
                            id: box
                            required property var modelData
                            required property int index
                            readonly property bool sel: win.selected === modelData.id
                            readonly property real ratio: modelData.h / Math.max(0.0001, modelData.w)
                            visible: modelData.ok && !modelData.hidden
                            z: index + 1
                            x: modelData.x * stage.width
                            y: modelData.y * stage.height
                            width: modelData.w * stage.width
                            height: modelData.h * stage.height

                            Rectangle {
                                anchors.fill: parent
                                color: "transparent"
                                radius: box.modelData.round ? Math.min(width, height) * 0.14 : 0
                                border.width: box.sel ? 2 : (body.containsMouse ? 1 : 0)
                                border.color: box.sel ? Theme.accent : Qt.rgba(1, 1, 1, 0.55)
                            }
                            Rectangle {
                                visible: box.sel
                                x: 6; y: 6
                                width: selName.implicitWidth + 14; height: 22; radius: 6
                                color: Theme.accent
                                Text { id: selName; anchors.centerIn: parent; text: box.modelData.label; color: Theme.accentText; font.family: Theme.fontFamily; font.pixelSize: 11; font.bold: true }
                            }

                            MouseArea {
                                id: body
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                                property real sx; property real sy; property real ox; property real oy
                                onPressed: (m) => {
                                    win.selected = box.modelData.id
                                    const p = mapToItem(stage, m.x, m.y)
                                    sx = p.x; sy = p.y; ox = box.modelData.x; oy = box.modelData.y
                                }
                                onPositionChanged: (m) => {
                                    if (!pressed) return
                                    const p = mapToItem(stage, m.x, m.y)
                                    const w = box.modelData.w, h = box.modelData.h
                                    const nx = stage.snapX(ox + (p.x - sx) / stage.width, w)
                                    const ny = stage.snapY(oy + (p.y - sy) / stage.height, h)
                                    studio.moveItem(box.index, nx, ny, w)
                                }
                                onDoubleClicked: studio.fillItem(box.index)
                            }

                            // Ecken: proportional skalieren, die gegenüberliegende Ecke bleibt stehen
                            Repeater {
                                model: box.sel ? [[0, 0], [1, 0], [0, 1], [1, 1]] : []
                                delegate: Rectangle {
                                    required property var modelData
                                    readonly property int cx: modelData[0]
                                    readonly property int cy: modelData[1]
                                    width: 14; height: 14; radius: 4
                                    x: cx * box.width - width / 2
                                    y: cy * box.height - height / 2
                                    color: "white"
                                    border.color: Theme.accent
                                    border.width: 2
                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.margins: -6
                                        cursorShape: (parent.cx === parent.cy) ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                                        property real ax; property real ay
                                        onPressed: {
                                            const d = box.modelData
                                            ax = parent.cx ? d.x : d.x + d.w          // Gegenecke in Anteilen
                                            ay = parent.cy ? d.y : d.y + d.h
                                        }
                                        onPositionChanged: (m) => {
                                            if (!pressed) return
                                            const p = mapToItem(stage, m.x, m.y)
                                            const fx = p.x / stage.width, fy = p.y / stage.height
                                            // Breite aus der Maus – waagrecht oder senkrecht, was weiter reicht
                                            const w = Math.max(0.03, Math.max(Math.abs(fx - ax), Math.abs(fy - ay) / box.ratio))
                                            const h = w * box.ratio
                                            const nx = parent.cx ? ax : ax - w
                                            const ny = parent.cy ? ay : ay - h
                                            studio.moveItem(box.index, nx, ny, w)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Column {
                    anchors.centerIn: parent
                    spacing: 12
                    visible: win.items.some(i => i.kind === "screen") && !st.screenReady
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: st.screenAsking ? "Wähle im Fenster von KDE aus, was Studio zeigen soll." : "Noch kein Bildschirm gewählt."
                        color: "#dce6ff"
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                    }
                    CButton {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: !st.screenAsking
                        primary: true
                        text: "Bildschirm oder Fenster wählen"
                        onClicked: studio.chooseScreen()
                    }
                }
                Row {
                    x: 14; y: 14
                    spacing: 8
                    Badge { visible: !!st.live; text: "LIVE  " + st.liveTime; fill: win.redLive; pulse: true }
                    // Ampel je Ziel: kommt der Upload hinterher?
                    Repeater {
                        model: st.live ? (st.upload || []) : []
                        delegate: Rectangle {
                            id: upItem
                            required property var modelData
                            readonly property color dot: modelData.state === "gut" ? "#3ecf8e" : modelData.state === "wackelig" ? "#f5b544" : "#e5484d"
                            height: 26
                            width: upRow.implicitWidth + 18
                            radius: 8
                            color: Qt.rgba(0.07, 0.08, 0.1, 0.78)
                            border.color: modelData.state === "gut" ? "transparent" : dot
                            Row {
                                id: upRow
                                anchors.centerIn: parent
                                spacing: 6
                                Rectangle {
                                    width: 8; height: 8; radius: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: upItem.dot
                                    SequentialAnimation on opacity {
                                        running: upItem.modelData.state === "schlecht"
                                        loops: Animation.Infinite
                                        NumberAnimation { to: 0.3; duration: 400 }
                                        NumberAnimation { to: 1; duration: 400 }
                                    }
                                }
                                Text {
                                    text: upItem.modelData.label + (upItem.modelData.state === "gut" ? "  flüssig"
                                          : upItem.modelData.state === "wackelig" ? "  wackelig" : "  Upload zu langsam")
                                    color: "white"; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true
                                }
                            }
                            ToolTip.visible: upHover.containsMouse
                            ToolTip.text: modelData.state === "gut" ? "Der Upload kommt hinterher."
                                : "Rückstau " + modelData.backlog.toFixed(1) + " s – deine Leitung schafft die Bitrate gerade nicht. Bitrate senken hilft."
                            MouseArea { id: upHover; anchors.fill: parent; hoverEnabled: true }
                        }
                    }
                    Badge { visible: !!st.recording; text: "● Aufnahme  " + st.recTime; fill: Qt.rgba(0.07, 0.08, 0.1, 0.78) }
                }
                Text {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 12
                    text: (st.live ? (st.liveTargets || []).map(t => ({ twitch: "Twitch", youtube: "YouTube", kick: "Kick", tiktok: "TikTok" })[t] || "Eigener Server").join(" · ") + "  ·  " : "") + st.encoder
                    color: Qt.rgba(0.86, 0.9, 1, 0.55)
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                }
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 12
                    visible: !!st.error
                    height: errText.implicitHeight + 16
                    radius: 10
                    color: Qt.rgba(0.9, 0.28, 0.3, 0.92)
                    Text { id: errText; anchors.centerIn: parent; width: parent.width - 20; wrapMode: Text.WordWrap; text: st.error || ""; color: "white"; font.family: Theme.fontFamily; font.pixelSize: 12 }
                }
            }

            // Szenen
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text { text: "Szenen"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true; rightPadding: 4 }
                Repeater {
                    model: st.scenes || []
                    delegate: Rectangle {
                        id: chipScene
                        required property var modelData
                        required property int index
                        readonly property bool cur: index === st.scene
                        implicitHeight: 36
                        implicitWidth: (win.renaming === index ? 160 : sceneLabel.implicitWidth) + 30
                        radius: Theme.radiusRow
                        color: cur ? Theme.accent : (sca.containsMouse ? Theme.hover : Theme.surface)
                        border.color: cur ? "transparent" : Theme.hairline
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            id: sceneLabel
                            visible: win.renaming !== chipScene.index
                            anchors.centerIn: parent
                            text: chipScene.modelData.name
                            color: chipScene.cur ? Theme.accentText : Theme.text
                            font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: chipScene.cur
                        }
                        MouseArea {
                            id: sca
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            cursorShape: Qt.PointingHandCursor
                            onClicked: (m) => {
                                if (m.button === Qt.RightButton) { sceneMenu.popup(); return }
                                win.selected = ""
                                studio.setScene(chipScene.index)
                            }
                            onDoubleClicked: win.renaming = chipScene.index
                        }
                        TextField {
                            visible: win.renaming === chipScene.index
                            anchors.fill: parent
                            anchors.margins: 3
                            text: chipScene.modelData.name
                            color: Theme.accentText
                            font.family: Theme.fontFamily; font.pixelSize: 13
                            background: Item {}
                            onVisibleChanged: if (visible) { forceActiveFocus(); selectAll() }
                            onAccepted: { studio.renameScene(chipScene.index, text); win.renaming = -1 }
                            onActiveFocusChanged: if (!activeFocus && visible) { studio.renameScene(chipScene.index, text); win.renaming = -1 }
                            Keys.onEscapePressed: win.renaming = -1
                        }
                        Menu {
                            id: sceneMenu
                            MenuItem { text: "Umbenennen"; onTriggered: win.renaming = chipScene.index }
                            MenuItem { text: "Duplizieren"; onTriggered: studio.duplicateScene(chipScene.index) }
                            MenuItem { text: "Löschen"; enabled: (st.scenes || []).length > 1; onTriggered: studio.removeScene(chipScene.index) }
                        }
                    }
                }
                IconBtn { icon: "plus"; tip: "Neue Szene"; onClicked: { win.selected = ""; studio.addScene() } }
                Item { Layout.fillWidth: true }
                Text {
                    text: "Strg+1 … 9 wechselt die Szene"
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                }
            }

            // Tonmischer
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                AudioStrip { slot: "mic"; label: "Mikrofon" }
                AudioStrip { slot: "desktop"; label: "Desktop-Ton" }
                AudioStrip { slot: "extra"; label: "Weitere Tonquelle" }
            }
        }

        // ---------------- Quellen ----------------
        Card {
            Layout.fillHeight: true
            Layout.preferredWidth: 290

            Flickable {
                anchors.fill: parent
                anchors.margins: 16
                anchors.bottomMargin: buttons.height + 28
                contentHeight: side.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                ColumnLayout {
                    id: side
                    width: parent.width
                    spacing: 10

                    Heading { text: "Qualität" }
                    Seg {
                        Layout.fillWidth: true
                        enabled: !win.locked
                        options: [["720p30", "720p 30"], ["720p60", "720p 60"], ["1080p30", "1080p 30"], ["1080p60", "1080p 60"]]
                        value: cfg.canvas || "1080p30"
                        onPicked: (v) => studio.set("canvas", v)
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Bitrate"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                        CSlider {
                            Layout.fillWidth: true
                            from: 2500; to: 12000; stepSize: 500
                            enabled: !win.locked
                            value: cfg.kbps || 6000
                            onMoved: studio.set("kbps", value)
                        }
                        Text { text: ((cfg.kbps || 6000) / 1000).toFixed(1) + " Mbit/s"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12 }
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "Alle Ziele bekommen dasselbe Bild – einmal kodiert. Twitch und Kick empfehlen bis 6 Mbit/s."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                    }

                    Divider { Layout.fillWidth: true; Layout.topMargin: 6 }
                    Heading { text: "Ziele" }
                    TargetRow { key: "twitch"; label: "Twitch"; note: acc.twitch && acc.twitch.connected ? (acc.twitch.target ? acc.twitch.name : "kein Stream-Schlüssel") : (cfg.twitch_key ? "Stream-Schlüssel eingetragen" : "anmelden oder Schlüssel eintragen") }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.twitch && !(acc.twitch && acc.twitch.connected)
                        placeholderText: "Stream-Schlüssel (Twitch › Creator-Dashboard › Stream)"
                        echoMode: TextInput.Password
                        text: cfg.twitch_key || ""
                        onEditingFinished: studio.set("twitch_key", text.trim())
                    }
                    TargetRow { key: "youtube"; label: "YouTube"; note: acc.youtube && acc.youtube.connected ? (acc.youtube.target ? acc.youtube.name : "keine Übertragung") : (cfg.youtube_key ? "Stream-Schlüssel eingetragen" : "anmelden oder Schlüssel eintragen") }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.youtube && !(acc.youtube && acc.youtube.connected)
                        placeholderText: "Stream-Schlüssel (YouTube Studio › Livestream)"
                        echoMode: TextInput.Password
                        text: cfg.youtube_key || ""
                        onEditingFinished: studio.set("youtube_key", text.trim())
                    }
                    TargetRow { key: "kick"; label: "Kick"; note: cfg.kick_url ? "Stream-Schlüssel eingetragen" : "Server und Schlüssel eintragen" }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.kick
                        placeholderText: "Stream-URL (Kick › Einstellungen › Stream-Schlüssel)"
                        text: cfg.kick_url || ""
                        onEditingFinished: studio.set("kick_url", text)
                    }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.kick
                        placeholderText: "Stream-Schlüssel"
                        echoMode: TextInput.Password
                        text: cfg.kick_key || ""
                        onEditingFinished: studio.set("kick_key", text)
                    }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.kick
                        placeholderText: "Kanalname (für den Chat links)"
                        text: cfg.kick_channel || ""
                        onEditingFinished: studio.set("kick_channel", text)
                    }
                    TargetRow { key: "tiktok"; label: "TikTok"; note: cfg.tiktok_url ? "Stream-Schlüssel eingetragen" : "Server und Schlüssel eintragen" }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.tiktok
                        placeholderText: "Server-URL (TikTok LIVE Producer)"
                        text: cfg.tiktok_url || ""
                        onEditingFinished: studio.set("tiktok_url", text)
                    }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.tiktok
                        placeholderText: "Stream-Schlüssel"
                        echoMode: TextInput.Password
                        text: cfg.tiktok_key || ""
                        onEditingFinished: studio.set("tiktok_key", text)
                    }
                    TargetRow { key: "custom"; label: "Eigener Server"; note: "RTMP" }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.custom
                        placeholderText: "rtmp://server/app"
                        text: cfg.custom_url || ""
                        onEditingFinished: studio.set("custom_url", text)
                    }
                    Field {
                        Layout.fillWidth: true
                        visible: cfg.targets && cfg.targets.custom
                        placeholderText: "Stream-Schlüssel"
                        echoMode: TextInput.Password
                        text: cfg.custom_key || ""
                        onEditingFinished: studio.set("custom_key", text)
                    }

                    Divider { Layout.fillWidth: true; Layout.topMargin: 6 }
                    Heading { text: "Aufnahme" }
                    Seg {
                        Layout.fillWidth: true
                        enabled: !st.recording
                        options: [["mp4", "MP4"], ["mkv", "MKV"]]
                        value: cfg.format || "mp4"
                        onPicked: (v) => studio.set("format", v)
                    }
                    CButton { Layout.fillWidth: true; text: "Aufnahmen öffnen"; onClicked: studio.openRecordings() }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "Gespeichert unter Videos › Studio"
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                    }
                }
            }

            Column {
                id: buttons
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 16
                spacing: 8
                BigButton {
                    width: parent.width
                    text: st.live ? "Live beenden  ·  " + st.liveTime : "Live gehen"
                    fill: win.redLive
                    onClicked: studio.toggleLive()
                }
                BigButton {
                    width: parent.width
                    text: st.recording ? "Aufnahme stoppen  ·  " + st.recTime : "Aufnehmen"
                    fill: st.recording ? Theme.tint(0.16) : Theme.tint(0.08)
                    textColor: Theme.text
                    onClicked: studio.toggleRecord()
                }
            }
        }
    }

    function selectAt(pos) {
        if (pos >= 0 && pos < win.items.length)
            win.selected = win.items[pos].id
    }

    ImagePicker {
        id: imagePicker
        title: "Bild für die Szene wählen"
        acceptText: "Einfügen"
        onAccepted: (url) => win.selectAt(studio.addImage(url.toString()))
    }

    // ---------------- Anmeldung (Gerätecode) ----------------
    Rectangle {
        anchors.fill: parent
        visible: win.loginService !== ""
        color: Qt.rgba(0, 0, 0, 0.5)
        MouseArea { anchors.fill: parent }
        Rectangle {
            anchors.centerIn: parent
            width: 440
            height: loginCol.implicitHeight + 48
            radius: Theme.radiusMenu
            color: Theme.surface
            Column {
                id: loginCol
                anchors.centerIn: parent
                width: parent.width - 48
                spacing: 14
                Text { text: "Bei " + (win.loginService === "twitch" ? "Twitch" : "YouTube") + " anmelden"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Öffne die Seite unten (auch am Handy möglich), melde dich an und gib diesen Code ein:"
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                }
                Rectangle {
                    width: parent.width; height: 64; radius: 12; color: Theme.raised
                    Text { anchors.centerIn: parent; text: win.loginCode; color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: 30; font.bold: true; font.letterSpacing: 4 }
                }
                Text { text: win.loginUrl; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                Row {
                    spacing: 8
                    CButton { primary: true; text: "Seite öffnen"; onClicked: studio.openUrl(win.loginUrl) }
                    CButton { text: "Abbrechen"; onClicked: { studio.cancelLogin(win.loginService); win.loginService = "" } }
                }
                Text { width: parent.width; wrapMode: Text.WordWrap; text: "Studio wartet, bis du bestätigt hast. Dein Passwort sieht Studio nicht."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
            }
        }
    }

    // ---------------- Beenden, während etwas läuft ----------------
    Rectangle {
        id: quitDialog
        property bool open: false
        anchors.fill: parent
        visible: open
        color: Qt.rgba(0, 0, 0, 0.5)
        MouseArea { anchors.fill: parent }
        Rectangle {
            anchors.centerIn: parent
            width: 420; height: qcol.implicitHeight + 48
            radius: Theme.radiusMenu; color: Theme.surface
            Column {
                id: qcol
                anchors.centerIn: parent
                width: parent.width - 48
                spacing: 14
                Text { text: "Studio beenden?"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 18; font.bold: true }
                Text { width: parent.width; wrapMode: Text.WordWrap; text: "Stream und Aufnahme werden beendet, die Aufnahme wird sauber gespeichert."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13 }
                Row {
                    spacing: 8
                    CButton { danger: true; text: "Beenden"; onClicked: { studio.shutdown(); Qt.quit() } }
                    CButton { text: "Weiter"; onClicked: quitDialog.open = false }
                }
            }
        }
    }

    // ---------------- Hinweis unten ----------------
    Rectangle {
        id: toast
        property string text
        function show(t) { text = t; opacity = 1; hide.restart() }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        width: Math.min(parent.width - 80, toastText.implicitWidth + 36)
        height: toastText.implicitHeight + 20
        radius: 12
        color: Theme.raised
        border.color: Theme.hairline
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        Text { id: toastText; anchors.centerIn: parent; width: Math.min(implicitWidth, win.width - 116); wrapMode: Text.WordWrap; text: toast.text; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
        Timer { id: hide; interval: 4500; onTriggered: toast.opacity = 0 }
    }

    // =============== Bausteine ===============
    component Card: Rectangle { radius: 16; color: Theme.surface; border.color: Theme.hairline }

    component Heading: Text { color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }

    component Field: TextField {
        implicitHeight: 38
        color: Theme.text
        placeholderTextColor: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 13
        leftPadding: 12
        rightPadding: 12
        selectByMouse: true
        background: Rectangle { radius: Theme.radiusRow; color: Theme.raised; border.width: parent.activeFocus ? 1 : 0; border.color: Theme.accent }
    }

    component IconBtn: Rectangle {
        id: ib
        property string icon
        property real turn: 0
        property string tip
        signal clicked()
        width: 36; height: 36; radius: Theme.radiusRow
        color: ima.pressed ? Theme.pressed : (ima.containsMouse ? Theme.hover : "transparent")
        SvgIcon { anchors.centerIn: parent; name: ib.icon; size: 18; rotation: ib.turn }
        MouseArea { id: ima; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ib.clicked() }
        ToolTip.visible: ima.containsMouse && tip !== ""
        ToolTip.text: tip
        ToolTip.delay: 600
    }

    component Pill: Rectangle {
        id: pill
        property string text
        property color dot: Theme.accent
        property bool checked
        signal clicked()
        implicitHeight: 34
        implicitWidth: pl.implicitWidth + 36
        radius: Theme.radiusRow
        color: checked ? Theme.tint(0.12) : (pma.containsMouse ? Theme.hover : "transparent")
        Row {
            anchors.centerIn: parent
            spacing: 7
            Rectangle { width: 8; height: 8; radius: 4; color: pill.dot; anchors.verticalCenter: parent.verticalCenter }
            Text { id: pl; text: pill.text; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: pill.checked }
        }
        MouseArea { id: pma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pill.clicked() }
    }

    component Seg: Rectangle {
        id: seg
        property var options: []
        property string value
        signal picked(string v)
        implicitHeight: 36
        radius: Theme.radiusRow
        color: Theme.raised
        opacity: enabled ? 1 : 0.55
        Row {
            anchors.fill: parent
            anchors.margins: 3
            Repeater {
                model: seg.options
                delegate: Rectangle {
                    required property var modelData
                    width: (seg.width - 6) / seg.options.length
                    height: parent.height
                    radius: Theme.radiusRow - 3
                    color: seg.value === modelData[0] ? Theme.accent : (sma.containsMouse ? Theme.hover : "transparent")
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - 6
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: modelData[1]
                        color: seg.value === modelData[0] ? Theme.accentText : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: seg.value === modelData[0]
                    }
                    MouseArea { id: sma; anchors.fill: parent; hoverEnabled: true; enabled: seg.enabled; cursorShape: Qt.PointingHandCursor; onClicked: seg.picked(modelData[0]) }
                }
            }
        }
    }

    component Pick: ComboBox {
        id: pick
        property var items: []
        property string current
        property string empty: "–"
        signal chosen(string id)
        implicitHeight: 38
        model: items.length ? items.map(i => i.name) : [empty]
        currentIndex: Math.max(0, items.findIndex(i => i.id === current))
        onActivated: (i) => { if (items.length) chosen(items[i].id) }
        Component.onCompleted: if (items.length && !current) chosen(items[0].id)
        font.family: Theme.fontFamily
        font.pixelSize: 13
        contentItem: Text { leftPadding: 12; rightPadding: 30; text: pick.displayText; color: Theme.text; font: pick.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        indicator: Text { x: pick.width - width - 12; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: Theme.textMuted; font.pixelSize: 14 }
        background: Rectangle { radius: Theme.radiusRow; color: Theme.raised; opacity: pick.enabled ? 1 : 0.55 }
        delegate: ItemDelegate {
            required property int index
            required property var modelData
            width: pick.width - 8
            height: 34
            contentItem: Text { text: modelData; color: Theme.text; font: pick.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
            background: Rectangle { radius: 8; color: parent.hovered ? Theme.hover : "transparent" }
        }
        popup: Popup {
            y: pick.height + 4
            width: pick.width
            padding: 4
            implicitHeight: Math.min(contentItem.implicitHeight + 8, 300)
            background: Rectangle { radius: Theme.radiusRow; color: Theme.surface; border.color: Theme.hairline }
            contentItem: ListView { clip: true; implicitHeight: contentHeight; model: pick.popup.visible ? pick.delegateModel : null }
        }
    }

    component AccountChip: Rectangle {
        id: chip
        property string service
        property string label
        property color dotColor
        readonly property var a: acc[service] || ({})
        implicitWidth: chipRow.implicitWidth + 24
        implicitHeight: 38
        radius: Theme.radiusRow
        color: cma.containsMouse ? Theme.hover : Theme.raised
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 7
            Rectangle { width: 8; height: 8; radius: 4; anchors.verticalCenter: parent.verticalCenter; color: chip.a.connected ? chip.dotColor : Theme.tint(0.25) }
            Text {
                text: chip.a.busy ? chip.a.busy : (chip.a.connected ? (chip.a.name || chip.label) : chip.label + " anmelden")
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13
            }
        }
        MouseArea {
            id: cma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.a.connected ? menu.popup() : studio.login(chip.service)
        }
        Menu {
            id: menu
            MenuItem { text: "Neu laden"; onTriggered: studio.reloadChannel(chip.service) }
            MenuItem { text: "Abmelden"; onTriggered: studio.logout(chip.service) }
        }
    }

    component AudioStrip: Rectangle {
        id: strip
        property string slot
        property string label
        readonly property var a: (cfg.audio || {})[slot] || ({})
        readonly property real level: (studio.levelMap[slot] !== undefined) ? studio.levelMap[slot] : -90
        Layout.fillWidth: true
        implicitHeight: col.implicitHeight + 24
        radius: 14
        color: Theme.surface
        border.color: Theme.hairline
        opacity: a.on ? 1 : 0.6
        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                Text { text: strip.label; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                IconBtn {
                    width: 30; height: 30
                    icon: strip.a.muted ? "volume-off" : "volume"
                    tip: strip.a.muted ? "Ton an" : "Stumm"
                    onClicked: studio.set("audio." + strip.slot + ".muted", !strip.a.muted)
                }
                CSwitch { checked: !!strip.a.on; enabled: !win.locked; label: strip.label; onToggled: (v) => studio.set("audio." + strip.slot + ".on", v) }
            }
            // Pegel: grün bis -12 dB, orange bis -3 dB, darüber rot
            Rectangle {
                Layout.fillWidth: true
                height: 8
                radius: 4
                color: Theme.tint(0.1)
                Rectangle {
                    readonly property real frac: strip.a.on && !strip.a.muted ? Math.max(0, Math.min(1, (strip.level + 60) / 60)) : 0
                    width: parent.width * frac
                    height: parent.height
                    radius: 4
                    color: strip.level > -3 ? "#e5484d" : strip.level > -12 ? Theme.flame : Theme.ok
                    Behavior on width { NumberAnimation { duration: 90 } }
                }
            }
            CSlider {
                Layout.fillWidth: true
                from: 0; to: 150; stepSize: 1
                value: (strip.a.volume || 0) * 100
                onMoved: studio.set("audio." + strip.slot + ".volume", value / 100)
            }
            Pick {
                Layout.fillWidth: true
                enabled: !win.locked
                items: strip.slot === "desktop" ? (st.outputDevices || [])
                       : (strip.slot === "mic" ? [{ id: "", name: "Standard-Mikrofon" }] : []).concat(st.audioDevices || [])
                current: strip.a.device || ""
                empty: "Kein Gerät"
                onChosen: (id) => studio.set("audio." + strip.slot + ".device", id)
            }
            // Capture-Karte über Kopfhörer mithören (nicht fürs Mikrofon – da hörst du dich doppelt)
            RowLayout {
                Layout.fillWidth: true
                visible: strip.slot === "extra"
                Text { text: "Mithören"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; Layout.fillWidth: true }
                CSwitch { checked: !!strip.a.listen; enabled: !!strip.a.on; label: "Mithören"; onToggled: (v) => studio.set("audio.extra.listen", v) }
            }
            Pick {
                Layout.fillWidth: true
                visible: strip.slot === "extra" && !!strip.a.listen
                items: st.sinkDevices || []
                current: cfg.monitor_device || ""
                empty: "Standard-Ausgabe"
                onChosen: (id) => { if (id !== (cfg.monitor_device || "")) studio.set("monitor_device", id) }
            }
            Text {
                Layout.fillWidth: true
                visible: strip.slot === "extra" && !!st.monitorEcho
                wrapMode: Text.WordWrap
                text: "Achtung: Desktop-Ton nimmt dein Mithören mit auf – die Capture-Karte wäre doppelt im Stream. Wähle beim Desktop-Ton ein anderes Gerät oder hier eigene Kopfhörer."
                color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 11
            }
        }
    }

    component SourceRow: Rectangle {
        id: sr
        property var item
        property int pos
        readonly property bool sel: win.selected === item.id
        Layout.fillWidth: true
        implicitHeight: 42
        radius: Theme.radiusRow
        color: sel ? Theme.tint(0.12) : (srm.containsMouse ? Theme.hover : Theme.raised)
        MouseArea { id: srm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: win.selected = sr.item.id }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 4
            spacing: 4
            SvgIcon {
                name: sr.item.kind === "screen" ? "pc" : sr.item.kind === "image" ? "image" : sr.item.kind === "capture" ? "capture" : "video"
                size: 16
                opacity: sr.item.hidden ? 0.4 : 1
            }
            Text {
                Layout.fillWidth: true
                leftPadding: 6
                text: sr.item.label + (sr.item.ok ? "" : " – kein Gerät")
                elide: Text.ElideRight
                color: sr.item.hidden ? Theme.textMuted : Theme.text
                font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: sr.sel
            }
            IconBtn { width: 28; height: 28; icon: "up"; tip: "Nach vorne"; visible: sr.sel && sr.pos < win.items.length - 1; onClicked: studio.orderItem(sr.pos, 1) }
            IconBtn { width: 28; height: 28; icon: "up"; turn: 180; tip: "Nach hinten"; visible: sr.sel && sr.pos > 0; onClicked: studio.orderItem(sr.pos, -1) }
            CSwitch { checked: !sr.item.hidden; label: sr.item.hidden ? "Einblenden" : "Ausblenden"; onToggled: (v) => studio.setItem(sr.pos, "hidden", !v) }
        }
    }

    component TargetRow: RowLayout {
        id: tr
        property string key
        property string label
        property string note
        Layout.fillWidth: true
        Column {
            Layout.fillWidth: true
            Text { text: tr.label; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
            Text { text: tr.note; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
        }
        CSwitch { checked: !!(cfg.targets && cfg.targets[tr.key]); enabled: !st.live; label: tr.label; onToggled: (v) => studio.set("targets." + tr.key, v) }
    }

    component Badge: Rectangle {
        id: badge
        property string text
        property color fill
        property bool pulse: false
        width: bt.implicitWidth + 20
        height: 26
        radius: 8
        color: fill
        Text { id: bt; anchors.centerIn: parent; text: badge.text; color: "white"; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
        SequentialAnimation on opacity {
            running: badge.pulse && badge.visible
            loops: Animation.Infinite
            NumberAnimation { to: 0.75; duration: 900; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutSine }
        }
    }

    component BigButton: Rectangle {
        id: bb
        property string text
        property color fill
        property color textColor: "white"
        signal clicked()
        height: 48
        radius: 14
        color: bma.pressed ? Qt.darker(fill, 1.15) : (bma.containsMouse ? Qt.lighter(fill, 1.08) : fill)
        Text { anchors.centerIn: parent; text: bb.text; color: bb.textColor; font.family: Theme.fontFamily; font.pixelSize: 15; font.bold: true }
        MouseArea { id: bma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bb.clicked() }
    }
}
