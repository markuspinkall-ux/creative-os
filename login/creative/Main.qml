// Creative OS – Anmeldebildschirm (SDDM) im Graphit-Look.
// Sieht aus wie der Sperrbildschirm: Uhr, Benutzer, rundes Passwortfeld.
// Die Anmeldung selbst übernimmt SDDM (Objekt "sddm").
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    width: 1920
    height: 1080

    readonly property color textColor: "#dce6ff"
    readonly property color muted: Qt.rgba(220 / 255, 230 / 255, 255 / 255, 0.6)
    readonly property color accent: "#8fb3ff"
    readonly property color dark: "#12151b"
    readonly property string fontFamily: "Arial"

    property int userIndex: Math.max(0, userModel.lastIndex)
    property string message: ""
    property bool busy: false

    // ---- Server-Modus ---------------------------------------------------------------
    // /usr/libexec/creative-servermode schreibt alle 30 s seinen Status hierher.
    // Lesen per XHR braucht QML_XHR_ALLOW_FILE_READ=1 (sddm-creative.conf).
    property var server: ({ active: false })
    property bool loginRequested: false        // „Zurück zum normalen Modus“ gedrückt
    property bool dimmed: false                 // Bildschirm abgedunkelt (spart Strom/Display)
    readonly property bool serverView: server.active === true && !loginRequested
    readonly property bool serverHealthy: server.server === true
                                          && (Date.now() / 1000 - (server.updated || 0)) < 120

    function readServer() {
        const xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            try {
                root.server = xhr.responseText ? JSON.parse(xhr.responseText) : { active: false }
            } catch (e) {
                root.server = { active: false }
            }
        }
        xhr.open("GET", "file:///var/lib/creative-servermode/state.json")
        xhr.send()
    }
    function wake() {
        root.dimmed = false
        idle.restart()
        if (root.loginRequested)
            backToMask.restart()
    }
    function sinceText() {
        if (!server.since)
            return ""
        const d = new Date(server.since * 1000)
        const today = new Date()
        const sameDay = d.toDateString() === today.toDateString()
        return "seit " + (sameDay ? "" : Qt.formatDate(d, "dd.MM. ")) + Qt.formatTime(d, "HH:mm") + " Uhr"
    }

    Timer { interval: 5000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.readServer() }
    // Nach 2 Minuten ohne Eingabe im Server-Modus abdunkeln
    Timer { id: idle; interval: 120000; running: root.server.active === true; onTriggered: root.dimmed = true }
    // Anmeldung angefangen, aber liegen gelassen → nach 1 Minute zurück zur Maske
    Timer {
        id: backToMask
        interval: 60000
        onTriggered: { root.loginRequested = false; password.text = ""; root.message = "" }
    }

    function userName() {
        const i = userModel.index(root.userIndex, 0)
        return userModel.data(i, Qt.UserRole + 1) || ""          // name
    }
    function realName() {
        const i = userModel.index(root.userIndex, 0)
        return userModel.data(i, Qt.UserRole + 2) || userName()   // realName
    }
    function userIcon() {
        // Profilbild vom Kontodienst (AccountsService); SDDMs Standard-Gesicht zählt nicht
        const i = userModel.index(root.userIndex, 0)
        const icon = String(userModel.data(i, Qt.UserRole + 4) || "")   // icon
        if (!icon.length || icon.indexOf("/sddm/faces/") >= 0 || icon.indexOf("default") >= 0)
            return ""
        return icon.indexOf("file:") === 0 ? icon : "file://" + icon
    }
    function initials() {
        const words = String(realName()).replace(/-/g, " ").split(/\s+/).filter(w => w.length > 0)
        if (words.length >= 2)
            return (words[0].charAt(0) + words[words.length - 1].charAt(0)).toUpperCase()
        return words.length ? words[0].charAt(0).toUpperCase() : "?"
    }
    function sessionIndex() {
        // Nur die Creative-Sitzung anbieten, sonst die zuletzt benutzte
        for (let n = 0; n < sessionModel.rowCount(); n++) {
            const name = sessionModel.data(sessionModel.index(n, 0), Qt.UserRole + 4) || ""   // name
            const file = sessionModel.data(sessionModel.index(n, 0), Qt.UserRole + 2) || ""   // file
            if (String(file).indexOf("creative") >= 0 || String(name).indexOf("Creative") >= 0)
                return n
        }
        return sessionModel.lastIndex
    }
    function login() {
        if (busy || password.text.length === 0)
            return
        busy = true
        message = ""
        sddm.login(userName(), password.text, sessionIndex())
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false
            root.message = "Falsches Passwort. Bitte noch einmal versuchen."
            password.text = ""
            password.forceActiveFocus()
            shake.restart()
        }
        function onLoginSucceeded() {
            root.message = ""
        }
    }

    // ---- Hintergrund ----------------------------------------------------------------
    Rectangle { anchors.fill: parent; color: root.dark }
    Image {
        anchors.fill: parent
        source: Qt.resolvedUrl(config.background || "background.svg")
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: width
        sourceSize.height: height
        asynchronous: true
    }
    Rectangle { anchors.fill: parent; color: Qt.rgba(0.05, 0.06, 0.08, 0.55) }

    // ---- Uhr ------------------------------------------------------------------------
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.14
        spacing: 6
        Text {
            id: clock
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 96
            font.bold: true
        }
        Text {
            id: date
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 20
        }
    }
    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const now = new Date()
            clock.text = Qt.formatTime(now, "HH:mm")
            const days = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]
            const months = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                            "September", "Oktober", "November", "Dezember"]
            date.text = days[now.getDay()] + ", " + now.getDate() + ". " + months[now.getMonth()]
        }
    }

    // ---- Benutzer + Passwort --------------------------------------------------------
    Column {
        id: loginBox
        visible: !root.serverView
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.48
        spacing: 16

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 96; height: 96; radius: 48
            color: face.status === Image.Ready ? "transparent" : root.accent
            Text {
                anchors.centerIn: parent
                visible: face.status !== Image.Ready
                text: root.initials()
                color: root.dark
                font.family: root.fontFamily
                font.pixelSize: text.length > 1 ? 36 : 40
                font.bold: true
            }
            // Profilbild (schon rund gespeichert); fehlt es, bleibt das Kürzel
            Image {
                id: face
                anchors.fill: parent
                source: root.userIcon()
                visible: status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 192
                sourceSize.height: 192
                smooth: true
                cache: false
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.realName()
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 22
            font.bold: true
        }

        Item {
            id: field
            anchors.horizontalCenter: parent.horizontalCenter
            width: 340
            height: 50
            Rectangle {
                anchors.fill: parent
                radius: 25
                color: Qt.rgba(28 / 255, 32 / 255, 41 / 255, 0.92)
                border.color: password.activeFocus ? root.accent : Qt.rgba(1, 1, 1, 0.12)
                border.width: password.activeFocus ? 2 : 1
            }
            TextField {
                id: password
                anchors.fill: parent
                anchors.rightMargin: 50
                leftPadding: 22
                echoMode: TextInput.Password
                placeholderText: "Passwort"
                placeholderTextColor: root.muted
                color: root.textColor
                font.family: root.fontFamily
                font.pixelSize: 16
                background: null
                focus: true
                enabled: !root.busy
                onAccepted: root.login()
                onTextChanged: root.wake()
                Keys.onEscapePressed: text = ""
            }
            Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 38; height: 38; radius: 19
                color: goMouse.pressed ? Qt.darker(root.accent, 1.15) : root.accent
                opacity: password.text.length ? 1 : 0.5
                Text {
                    anchors.centerIn: parent
                    text: root.busy ? "…" : "→"
                    color: root.dark
                    font.pixelSize: 20
                    font.bold: true
                }
                MouseArea { id: goMouse; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.login() }
            }
            SequentialAnimation {
                id: shake
                NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: -12; duration: 50 }
                NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: 12; duration: 70 }
                NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: -8; duration: 60 }
                NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: 0; duration: 50 }
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.message || (keyboard && keyboard.capsLock ? "Feststelltaste ist aktiv" : " ")
            color: "#ffb07a"
            font.family: root.fontFamily
            font.pixelSize: 14
        }
    }

    // ---- Server-Modus: Maske statt Anmeldung -------------------------------------------
    Rectangle {
        id: serverCard
        visible: root.serverView
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.44
        width: 520
        height: serverColumn.implicitHeight + 64
        radius: 20
        color: Qt.rgba(28 / 255, 32 / 255, 41 / 255, 0.92)
        border.color: Qt.rgba(1, 1, 1, 0.08)

        Column {
            id: serverColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 32
            spacing: 14

            Row {
                spacing: 12
                Rectangle {
                    id: statusDot
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12; height: 12; radius: 6
                    color: root.serverHealthy ? "#6fdcc0" : "#ffb07a"
                    SequentialAnimation on opacity {
                        running: root.serverView && root.serverHealthy
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.35; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1; duration: 1400; easing.type: Easing.InOutSine }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Server-Modus"
                    color: root.textColor
                    font.family: root.fontFamily
                    font.pixelSize: 26
                    font.bold: true
                }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: root.serverHealthy
                      ? "„Mein Server“ ist online. Alles andere ruht, der PC geht nicht in Bereitschaft."
                      : "„Mein Server“ antwortet gerade nicht. Melde dich an und prüfe ihn in der Systemsteuerung."
                color: root.serverHealthy ? root.muted : "#ffb07a"
                font.family: root.fontFamily
                font.pixelSize: 15
                lineHeight: 1.3
            }

            Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.08) }

            // Adressen
            Repeater {
                model: [
                    root.server.host ? { k: "Heimnetz", v: "http://" + root.server.host + ".local" } : null,
                    (root.server.ips || []).length ? { k: "IP-Adresse", v: root.server.ips.join(", ") } : null,
                    root.server.domain ? { k: "Internet", v: "https://" + root.server.domain } : null,
                    root.server.since ? { k: "Läuft", v: root.sinceText() } : null
                ].filter(x => x !== null)
                delegate: Row {
                    required property var modelData
                    spacing: 12
                    Text {
                        width: 110
                        text: parent.modelData.k
                        color: root.muted
                        font.family: root.fontFamily
                        font.pixelSize: 14
                    }
                    Text {
                        text: parent.modelData.v
                        color: root.textColor
                        font.family: root.fontFamily
                        font.pixelSize: 14
                        font.bold: true
                    }
                }
            }

            Item { width: 1; height: 6 }

            // Zurück zum normalen Modus → Passwortfeld
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: backLabel.implicitWidth + 48
                height: 46
                radius: 23
                color: backMouse.pressed ? Qt.darker(root.accent, 1.15) : root.accent
                Text {
                    id: backLabel
                    anchors.centerIn: parent
                    text: "Zurück zum normalen Modus"
                    color: root.dark
                    font.family: root.fontFamily
                    font.pixelSize: 15
                    font.bold: true
                }
                MouseArea {
                    id: backMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.loginRequested = true
                        root.message = ""
                        backToMask.restart()
                        password.forceActiveFocus()
                    }
                }
                Accessible.role: Accessible.Button
                Accessible.name: backLabel.text
            }
        }
    }

    // Hinweis über dem Passwortfeld, wenn man aus der Maske kommt
    Column {
        visible: root.server.active === true && root.loginRequested
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: loginBox.top
        anchors.bottomMargin: 18
        spacing: 6
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Anmelden beendet den Server-Modus"
            color: root.muted
            font.family: root.fontFamily
            font.pixelSize: 14
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "‹ Zurück zur Server-Ansicht"
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: 14
            MouseArea {
                anchors.fill: parent
                anchors.margins: -6
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.loginRequested = false; password.text = ""; root.message = "" }
            }
        }
    }

    // ---- Andere Benutzer ---------------------------------------------------------------
    Row {
        visible: userModel.count > 1 && !root.serverView
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40
        spacing: 14
        Repeater {
            model: userModel
            delegate: Rectangle {
                width: 150; height: 44; radius: 22
                color: index === root.userIndex ? Qt.rgba(143 / 255, 179 / 255, 255 / 255, 0.22)
                                                : (um.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(28 / 255, 32 / 255, 41 / 255, 0.8))
                border.color: index === root.userIndex ? root.accent : Qt.rgba(1, 1, 1, 0.1)
                Text {
                    anchors.centerIn: parent
                    text: model.realName || model.name
                    color: root.textColor
                    font.family: root.fontFamily
                    font.pixelSize: 14
                    font.bold: index === root.userIndex
                }
                MouseArea {
                    id: um
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { root.userIndex = index; password.text = ""; password.forceActiveFocus() }
                }
            }
        }
    }

    // ---- Neustart / Ausschalten --------------------------------------------------------
    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 28
        spacing: 10
        PowerButton { visible: sddm.canReboot; label: "Neu starten"; glyph: "↻"; onActivated: sddm.reboot() }
        PowerButton { visible: sddm.canPowerOff; label: "Ausschalten"; glyph: "⏻"; onActivated: sddm.powerOff() }
    }

    component PowerButton: Rectangle {
        id: pb
        property string label
        property string glyph
        signal activated()
        width: row.implicitWidth + 28
        height: 44
        radius: 22
        color: pm.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(28 / 255, 32 / 255, 41 / 255, 0.8)
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Text { text: pb.glyph; color: root.textColor; font.pixelSize: 17; anchors.verticalCenter: parent.verticalCenter }
            Text { text: pb.label; color: root.textColor; font.family: root.fontFamily; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pb.activated() }
    }

    // ---- Abdunkeln im Server-Modus; jede Maus-/Tastatureingabe weckt auf -------------
    HoverHandler { onPointChanged: if (root.server.active === true) root.wake() }
    Rectangle {
        anchors.fill: parent
        z: 60
        color: "black"
        opacity: root.dimmed ? 0.92 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 800 } }
        MouseArea { anchors.fill: parent; onClicked: root.wake() }
    }
    Keys.onPressed: root.wake()
    onLoginRequestedChanged: if (!loginRequested) backToMask.stop()
    onServerViewChanged: serverView ? root.forceActiveFocus() : password.forceActiveFocus()

    Component.onCompleted: password.forceActiveFocus()
}
