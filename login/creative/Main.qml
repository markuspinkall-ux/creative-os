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

    function userName() {
        const i = userModel.index(root.userIndex, 0)
        return userModel.data(i, Qt.UserRole + 1) || ""          // name
    }
    function realName() {
        const i = userModel.index(root.userIndex, 0)
        return userModel.data(i, Qt.UserRole + 2) || userName()   // realName
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
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.48
        spacing: 16

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 96; height: 96; radius: 48
            color: root.accent
            Text {
                anchors.centerIn: parent
                text: (root.realName() || "?").charAt(0).toUpperCase()
                color: root.dark
                font.family: root.fontFamily
                font.pixelSize: 40
                font.bold: true
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

    // ---- Andere Benutzer ---------------------------------------------------------------
    Row {
        visible: userModel.count > 1
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

    Component.onCompleted: password.forceActiveFocus()
}
