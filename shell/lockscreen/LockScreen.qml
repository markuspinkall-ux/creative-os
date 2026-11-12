// Creative OS – Sperrbildschirm im Graphit-Look.
//
// Ersetzt die LockScreen.qml im Plasma-Shell-Paket, die KWins
// Bildschirmsperre (kscreenlocker_greet) lädt. Die
// Passwortprüfung übernimmt das System (PAM) über das Objekt
// "authenticator" – dieser Code zeigt nur die Oberfläche an.
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root

    readonly property color textColor: "#dce6ff"
    readonly property color accent: "#8fb3ff"
    readonly property string fontFamily: "Arial"
    readonly property string userName: typeof kscreenlocker_userName !== "undefined" ? kscreenlocker_userName : ""
    readonly property string userImage: typeof kscreenlocker_userImage !== "undefined" ? String(kscreenlocker_userImage) : ""
    property bool busy: false
    property string message: ""

    function startAuth() {
        if (typeof authenticator.startAuthenticating === "function")
            authenticator.startAuthenticating()
    }

    function unlock() {
        // leeres Feld erlaubt: Konten ohne Passwort entsperren mit Enter
        if (busy)
            return
        busy = true
        message = ""
        if (typeof authenticator.respond === "function") {
            authenticator.respond(password.text)
        } else if (typeof authenticator.tryUnlock === "function") {
            authenticator.tryUnlock()
        }
    }

    Connections {
        target: authenticator
        function onSucceeded() {
            Qt.quit()
        }
        function onFailed(kind) {
            if (kind !== undefined && kind !== 0)
                return   // Fehler ohne Eingabe (z. B. Fingerabdruck) ignorieren
            root.busy = false
            root.message = "Falsches Passwort. Bitte noch einmal versuchen."
            password.text = ""
            password.forceActiveFocus()
            shake.restart()
            root.startAuth()
        }
    }

    // ---- Hintergrund --------------------------------------------------------------
    Rectangle { anchors.fill: parent; color: "#12151b" }
    Image {
        anchors.fill: parent
        source: Qt.resolvedUrl("graphit.svg")
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: width
        sourceSize.height: height
        asynchronous: true
    }
    Rectangle { anchors.fill: parent; color: Qt.rgba(13 / 255, 16 / 255, 21 / 255, 0.45) }

    // ---- Uhr ----------------------------------------------------------------------
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.16
        spacing: 6

        Text {
            id: clock
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: Math.max(72, root.height * 0.11)
            font.bold: true
        }
        Text {
            id: date
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: Math.max(18, root.height * 0.022)
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
            date.text = now.toLocaleDateString(Qt.locale("de_DE"), "dddd, d. MMMM")
        }
    }

    // ---- Anmeldung ----------------------------------------------------------------
    Column {
        id: login
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.52
        spacing: 16

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 84
            height: 84
            radius: 42
            color: face.status === Image.Ready ? "transparent" : root.accent
            Text {
                anchors.centerIn: parent
                visible: face.status !== Image.Ready
                text: (root.userName.length > 0 ? root.userName[0] : "?").toUpperCase()
                color: "#12151b"
                font.family: root.fontFamily
                font.pixelSize: 36
                font.bold: true
            }
            Image {
                id: face
                anchors.fill: parent
                source: root.userImage
                visible: status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 168
                sourceSize.height: 168
                smooth: true
                cache: false
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.userName
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 20
            font.bold: true
        }

        Item {
            id: fieldBox
            anchors.horizontalCenter: parent.horizontalCenter
            width: 340
            height: 46

            TextField {
                id: password
                anchors.fill: parent
                echoMode: TextInput.Password
                placeholderText: "Passwort"
                placeholderTextColor: Qt.rgba(220 / 255, 230 / 255, 255 / 255, 0.6)
                color: root.textColor
                font.family: root.fontFamily
                font.pixelSize: 15
                leftPadding: 20
                rightPadding: 52
                enabled: !root.busy
                focus: true
                background: Rectangle {
                    radius: 23
                    color: Qt.rgba(18 / 255, 21 / 255, 27 / 255, 0.85)
                    border.color: root.accent
                    border.width: 1.5
                }
                Keys.onReturnPressed: root.unlock()
                Keys.onEnterPressed: root.unlock()
                Accessible.name: "Passwort"
            }

            Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 36
                height: 36
                radius: 18
                color: root.accent
                opacity: !root.busy ? (password.text.length > 0 ? 1 : 0.75) : 0.5
                Text {
                    anchors.centerIn: parent
                    text: root.busy ? "…" : "→"
                    color: "#12151b"
                    font.family: root.fontFamily
                    font.pixelSize: 18
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.unlock()
                }
                Accessible.role: Accessible.Button
                Accessible.name: "Entsperren"
            }

            SequentialAnimation {
                id: shake
                NumberAnimation { target: fieldBox; property: "anchors.horizontalCenterOffset"; to: -12; duration: 50 }
                NumberAnimation { target: fieldBox; property: "anchors.horizontalCenterOffset"; to: 12; duration: 80 }
                NumberAnimation { target: fieldBox; property: "anchors.horizontalCenterOffset"; to: -8; duration: 70 }
                NumberAnimation { target: fieldBox; property: "anchors.horizontalCenterOffset"; to: 0; duration: 60 }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.message.length > 0
            text: root.message
            color: "#ffb07a"
            font.family: root.fontFamily
            font.pixelSize: 14
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        text: "Creative OS · gesperrt"
        color: Qt.rgba(220 / 255, 230 / 255, 255 / 255, 0.6)
        font.family: root.fontFamily
        font.pixelSize: 13
    }

    // Jede Taste oder jeder Klick setzt den Cursor ins Passwortfeld
    MouseArea {
        anchors.fill: parent
        z: -1
        onClicked: password.forceActiveFocus()
    }

    Component.onCompleted: {
        startAuth()
        password.forceActiveFocus()
    }
}
