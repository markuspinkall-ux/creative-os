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

    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 14

        // ---------------- Chat ----------------
        Card {
            id: chatPane
            Layout.fillHeight: true
            Layout.preferredWidth: cfg.chat_open ? 340 : 56
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10
                visible: cfg.chat_open

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: ["twitch", "youtube"]
                        delegate: Pill {
                            required property string modelData
                            Layout.fillWidth: true
                            text: modelData === "twitch" ? "Twitch" : "YouTube"
                            dot: modelData === "twitch" ? "#9f7aea" : "#ff4e45"
                            checked: win.chatTab === modelData
                            onClicked: win.chatTab = modelData
                        }
                    }
                    IconBtn { icon: "chevron-left"; tip: "Chat einklappen"; onClicked: studio.set("chat_open", false) }
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
                                text: !parent.parent.parent.a.connected
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
            IconBtn {
                visible: !cfg.chat_open
                anchors.horizontalCenter: parent.horizontalCenter
                y: 12
                icon: "chevron-left"
                turn: 180
                tip: "Chat zeigen"
                onClicked: studio.set("chat_open", true)
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
                Column {
                    anchors.centerIn: parent
                    spacing: 12
                    visible: cfg.main && cfg.main.type === "screen" && !st.screenReady
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
                    Badge { visible: !!st.recording; text: "● Aufnahme  " + st.recTime; fill: Qt.rgba(0.07, 0.08, 0.1, 0.78) }
                }
                Text {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 12
                    text: (st.live ? (st.liveTargets || []).map(t => t === "twitch" ? "Twitch" : t === "youtube" ? "YouTube" : "Eigener Server").join(" · ") + "  ·  " : "") + st.encoder
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
            Layout.preferredWidth: 320

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

                    Heading { text: "Hauptbild" }
                    Seg {
                        Layout.fillWidth: true
                        enabled: !win.locked
                        options: [["screen", "Bildschirm"], ["video", "Kamera / Capture"], ["none", "Keins"]]
                        value: cfg.main ? cfg.main.type : "screen"
                        onPicked: (v) => studio.set("main.type", v)
                    }
                    CButton {
                        Layout.fillWidth: true
                        visible: cfg.main && cfg.main.type === "screen"
                        enabled: !win.locked
                        text: st.screenReady ? "Anderen Bildschirm wählen" : "Bildschirm wählen"
                        onClicked: studio.chooseScreen()
                    }
                    Pick {
                        Layout.fillWidth: true
                        visible: cfg.main && cfg.main.type === "video"
                        enabled: !win.locked
                        items: st.videoDevices || []
                        current: cfg.main ? cfg.main.device : ""
                        empty: "Keine Kamera gefunden"
                        onChosen: (id) => studio.set("main.device", id)
                    }

                    Divider { Layout.fillWidth: true; Layout.topMargin: 6 }
                    RowLayout {
                        Layout.fillWidth: true
                        Heading { text: "Kamera einblenden"; Layout.fillWidth: true }
                        CSwitch { checked: !!(cfg.cam && cfg.cam.on); enabled: !win.locked; label: "Kamera einblenden"; onToggled: (v) => studio.set("cam.on", v) }
                    }
                    Pick {
                        Layout.fillWidth: true
                        visible: cfg.cam && cfg.cam.on
                        enabled: !win.locked
                        items: st.videoDevices || []
                        current: cfg.cam ? cfg.cam.device : ""
                        empty: "Keine Kamera gefunden"
                        onChosen: (id) => studio.set("cam.device", id)
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: cfg.cam && cfg.cam.on
                        spacing: 12
                        // Ecke wählen: kleines Bild mit vier Punkten
                        Rectangle {
                            width: 96; height: 54; radius: 8
                            color: Theme.raised
                            Repeater {
                                model: ["oben-links", "oben-rechts", "unten-links", "unten-rechts"]
                                delegate: Rectangle {
                                    required property string modelData
                                    readonly property bool sel: cfg.cam && cfg.cam.corner === modelData
                                    width: 26; height: 15; radius: 4
                                    x: modelData.indexOf("links") >= 0 ? 6 : parent.width - width - 6
                                    y: modelData.indexOf("oben") >= 0 ? 6 : parent.height - height - 6
                                    color: sel ? Theme.accent : (cm.containsMouse ? Theme.tint(0.2) : Theme.tint(0.1))
                                    MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; enabled: !win.locked; cursorShape: Qt.PointingHandCursor; onClicked: studio.set("cam.corner", modelData) }
                                }
                            }
                        }
                        Seg {
                            Layout.fillWidth: true
                            enabled: !win.locked
                            options: [["klein", "S"], ["mittel", "M"], ["gross", "L"]]
                            value: cfg.cam ? cfg.cam.size : "mittel"
                            onPicked: (v) => studio.set("cam.size", v)
                        }
                    }

                    Divider { Layout.fillWidth: true; Layout.topMargin: 6 }
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
                        text: "Twitch empfiehlt bis 6 Mbit/s, YouTube verträgt mehr."
                        color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11
                    }

                    Divider { Layout.fillWidth: true; Layout.topMargin: 6 }
                    Heading { text: "Ziele" }
                    TargetRow { key: "twitch"; label: "Twitch"; note: !acc.twitch || !acc.twitch.connected ? "nicht angemeldet" : (acc.twitch.target ? acc.twitch.name : "kein Stream-Schlüssel") }
                    TargetRow { key: "youtube"; label: "YouTube"; note: !acc.youtube || !acc.youtube.connected ? "nicht angemeldet" : (acc.youtube.target ? acc.youtube.name : "keine Übertragung") }
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
                visible: strip.slot !== "desktop"
                enabled: !win.locked
                items: (strip.slot === "mic" ? [{ id: "", name: "Standard-Mikrofon" }] : []).concat(st.audioDevices || [])
                current: strip.a.device || ""
                empty: "Kein Gerät"
                onChosen: (id) => studio.set("audio." + strip.slot + ".device", id)
            }
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
