import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative OS installieren – läuft in der Live-Umgebung über dem Desktop.
ApplicationWindow {
    id: win
    width: 1060
    height: 680
    minimumWidth: 900
    minimumHeight: 600
    visible: true
    visibility: installer.demo ? Window.Windowed : Window.Maximized
    title: "Creative OS installieren"
    color: Theme.ground
    font.family: Theme.fontFamily

    property int step: Math.min(startStep, 4)
    readonly property var steps: [
        { title: "Willkommen", icon: "rocket" },
        { title: "Festplatte", icon: "drive" },
        { title: "Benutzer", icon: "lock" },
        { title: "Überblick", icon: "list" },
        { title: "Installieren", icon: "download" }
    ]

    // Auswahl
    property string disk: ""
    property string keyboard: "Deutsch"
    property string fullName: ""
    property string userName: ""
    property bool userEdited: false
    property string password: ""
    property string password2: ""
    property string hostName: "creative-os"
    property bool understood: false
    property string hint: ""
    property bool logOpen: autoMode

    // Testlauf in der VM (creative-installer --auto): Schritte nacheinander selbst ausfüllen
    Timer {
        running: autoMode && win.step < 4
        interval: 5000
        repeat: true
        onTriggered: {
            if (win.step === 1) {
                for (var i = 0; i < installer.disks.length; i++)
                    if (installer.disks[i].eligible) { win.disk = installer.disks[i].path; break }
            } else if (win.step === 2) {
                win.fullName = "Creative Test"; win.userName = "tester"
                win.password = "creative-test"; win.password2 = "creative-test"
            } else if (win.step === 3) {
                win.understood = true
            }
            if (win.canGoOn()) win.next()
        }
    }

    readonly property var chosenDisk: {
        for (var i = 0; i < installer.disks.length; i++)
            if (installer.disks[i].path === disk) return installer.disks[i]
        return null
    }

    function config() {
        return { disk: disk, keyboard: keyboard, fullName: fullName, userName: userName,
                 password: password, password2: password2, hostName: hostName }
    }

    function canGoOn() {
        if (step === 1) return chosenDisk !== null && chosenDisk.eligible
        if (step === 2) return fullName.trim().length > 0 && userName.length > 0
                               && password.length >= 6 && password === password2
        if (step === 3) return understood
        return true
    }

    function next() {
        hint = ""
        if (step === 2) {
            var err = installer.check(config())
            if (err.length > 0 && err.indexOf("Festplatte") < 0) { hint = err; return }
        }
        if (step === 3) {
            installer.start(config())
            step = 4
            return
        }
        if (step < 3) step++
    }
    function back() { hint = ""; if (step > 0 && step < 4) step-- }

    component Field: Column {
        id: fieldRoot
        property alias label: lbl.text
        property alias text: input.text
        property alias echo: input.echoMode
        property string placeholder: ""
        signal edited(string value)
        spacing: 5
        Text { id: lbl; color: Theme.text; font.pixelSize: 12; font.bold: true }
        Rectangle {
            width: fieldRoot.width; height: 40; radius: Theme.radiusRow
            color: Theme.ground
            border.color: input.activeFocus ? Theme.accent : Theme.hairline
            TextInput {
                id: input
                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.text; font.pixelSize: 14
                selectionColor: Theme.accent; selectedTextColor: Theme.accentText
                clip: true
                onTextEdited: fieldRoot.edited(text)
            }
            Text {
                visible: !input.text && !input.activeFocus
                x: 12; anchors.verticalCenter: parent.verticalCenter
                text: fieldRoot.placeholder
                color: Theme.textMuted; font.pixelSize: 14
            }
        }
    }

    // ---- Hintergrund: wie der Desktop ----------------------------------------------------
    Image {
        anchors.fill: parent
        source: wallpaperUrl
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: 1920
    }
    Rectangle { anchors.fill: parent; color: Qt.rgba(18 / 255, 21 / 255, 27 / 255, 0.35) }

    // ---- Fenster-Karte ----------------------------------------------------------------------
    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 980)
        height: Math.min(parent.height - 80, 600)
        radius: 22
        color: Qt.rgba(28 / 255, 32 / 255, 41 / 255, 0.97)
        border.color: Theme.hairline
        clip: true

        // Seitenleiste mit den Schritten
        Rectangle {
            id: side
            width: 230
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            radius: 22
            color: Theme.footer
            Rectangle { anchors.right: parent.right; width: 22; height: parent.height; color: Theme.footer }
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.hairline }

            Row {
                x: 22; y: 24
                spacing: 12
                Rectangle {
                    width: 40; height: 40; radius: 12
                    color: Theme.accent
                    SvgIcon { anchors.centerIn: parent; name: "rocket"; size: 24 }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { text: "Creative OS"; color: Theme.text; font.pixelSize: 16; font.bold: true }
                    Text { text: "Installation"; color: Theme.textMuted; font.pixelSize: 12 }
                }
            }

            Column {
                x: 14; y: 96
                width: parent.width - 28
                spacing: 4
                Repeater {
                    model: win.steps
                    delegate: Rectangle {
                        width: parent.width
                        height: 40
                        radius: Theme.radiusRow
                        color: index === win.step ? Theme.accent : "transparent"
                        Row {
                            x: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 10
                            Rectangle {
                                width: 22; height: 22; radius: 11
                                anchors.verticalCenter: parent.verticalCenter
                                color: index < win.step ? Theme.ok : (index === win.step ? Theme.accentText : Qt.rgba(1, 1, 1, 0.08))
                                Text {
                                    anchors.centerIn: parent
                                    text: index < win.step ? "✓" : (index + 1)
                                    color: index < win.step ? Theme.accentText : (index === win.step ? Theme.accent : Theme.textMuted)
                                    font.pixelSize: 11; font.bold: true
                                }
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.title
                                color: index === win.step ? Theme.accentText : (index < win.step ? Theme.text : Theme.textMuted)
                                font.pixelSize: 13; font.bold: index === win.step
                            }
                        }
                    }
                }
            }

            Text {
                anchors.left: parent.left; anchors.leftMargin: 22
                anchors.bottom: parent.bottom; anchors.bottomMargin: 20
                width: parent.width - 44
                wrapMode: Text.WordWrap
                text: installer.demo ? "Vorführung – es wird nichts installiert"
                                     : "Ausgabe: " + (installer.variant === "nvidia" ? "NVIDIA-Grafik" : "AMD/Intel-Grafik")
                color: Theme.textMuted; font.pixelSize: 11
            }
        }

        // Inhalt
        Item {
            id: content
            anchors.left: side.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.margins: 36

            // ---- 0) Willkommen ---------------------------------------------------------
            Column {
                visible: win.step === 0
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                spacing: 18
                Text { text: "Willkommen bei Creative OS"; color: Theme.text; font.pixelSize: 30; font.bold: true }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    lineHeight: 1.3
                    text: "Du kannst Creative OS jetzt fest auf deinem PC einrichten. Das dauert etwa 10 bis 20 Minuten " +
                          "und klappt ohne Internet. Bis du auf „Jetzt installieren“ klickst, wird nichts verändert."
                    color: Theme.text; font.pixelSize: 15
                }
                Rectangle {
                    width: parent.width; height: 70; radius: 14
                    color: Theme.raised; border.color: Theme.hairline
                    Row {
                        x: 18; anchors.verticalCenter: parent.verticalCenter; spacing: 14
                        Text { text: "⌨"; color: Theme.accent; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Text { text: "Sprache: Deutsch"; color: Theme.text; font.pixelSize: 14; font.bold: true }
                            Text { text: "Zeitzone: Europa/Berlin – beides lässt sich später ändern."; color: Theme.textMuted; font.pixelSize: 12 }
                        }
                    }
                    ComboBox {
                        id: kb
                        anchors.right: parent.right; anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        width: 190; height: 36
                        model: installer.keyboards
                        currentIndex: Math.max(0, installer.keyboards.indexOf(win.keyboard))
                        onActivated: win.keyboard = currentText
                        contentItem: Text {
                            leftPadding: 12
                            text: kb.displayText; color: Theme.text; font.pixelSize: 13
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle { radius: Theme.radiusRow; color: Theme.ground; border.color: Theme.hairline }
                        indicator: SvgIcon { x: kb.width - 26; anchors.verticalCenter: parent.verticalCenter; name: "chevron-down"; size: 14 }
                        popup.background: Rectangle { radius: Theme.radiusRow; color: Theme.raised; border.color: Theme.hairline }
                        delegate: ItemDelegate {
                            width: kb.width
                            contentItem: Text { text: modelData; color: Theme.text; font.pixelSize: 13 }
                            background: Rectangle { color: highlighted ? Theme.hover : "transparent"; radius: 8 }
                            highlighted: kb.highlightedIndex === index
                        }
                    }
                }
                Text {
                    text: "Etwas Besonderes vor, z. B. neben Windows installieren? → Fedora-Installer öffnen"
                    color: Theme.accent; font.pixelSize: 12
                    visible: !installer.demo
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: installer.openExpert() }
                }
            }

            // ---- 1) Festplatte -------------------------------------------------------------
            Column {
                visible: win.step === 1
                width: parent.width
                spacing: 8
                Text { text: "Wohin soll Creative OS?"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: "Die gewählte Festplatte wird komplett für Creative OS genutzt – alles, was bisher darauf ist, wird gelöscht."
                    color: Theme.textMuted; font.pixelSize: 13
                }
                Item { width: 1; height: 8 }
                Repeater {
                    model: installer.disks
                    delegate: Rectangle {
                        width: content.width
                        height: 68
                        radius: 14
                        readonly property bool chosen: win.disk === modelData.path
                        color: chosen ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                                      : (dm.containsMouse && modelData.eligible ? Theme.hover : Theme.raised)
                        border.width: chosen ? 2 : 1
                        border.color: chosen ? Theme.accent : Theme.hairline
                        opacity: modelData.eligible ? 1 : 0.5
                        Row {
                            x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 14
                            SvgIcon { anchors.verticalCenter: parent.verticalCenter; name: modelData.removable ? "usb" : "drive"; size: 26 }
                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 3
                                Text { text: modelData.model + " · " + modelData.sizeText; color: Theme.text; font.pixelSize: 14; font.bold: true }
                                Text {
                                    text: modelData.eligible ? (modelData.kind + " · bisher: " + modelData.previous) : modelData.reason
                                    color: modelData.eligible ? Theme.textMuted : Theme.flame; font.pixelSize: 12
                                }
                            }
                        }
                        Rectangle {
                            visible: parent.chosen
                            anchors.right: parent.right; anchors.rightMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            width: 24; height: 24; radius: 12; color: Theme.accent
                            Text { anchors.centerIn: parent; text: "✓"; color: Theme.accentText; font.bold: true; font.pixelSize: 13 }
                        }
                        MouseArea {
                            id: dm
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: modelData.eligible
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { win.disk = modelData.path; win.understood = false }
                        }
                    }
                }
                Text {
                    visible: installer.disks.length === 0
                    text: "Keine Festplatte gefunden."
                    color: Theme.flame; font.pixelSize: 13
                }
                Text {
                    text: "↻ Liste aktualisieren"
                    color: Theme.accent; font.pixelSize: 12
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: installer.refreshDisks() }
                }
            }

            // ---- 2) Benutzer ------------------------------------------------------------------
            Column {
                visible: win.step === 2
                width: parent.width
                spacing: 10
                Text { text: "Dein Benutzerkonto"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Text { text: "Damit meldest du dich später an. Das Konto bekommt Administratorrechte."; color: Theme.textMuted; font.pixelSize: 13 }
                Item { width: 1; height: 6 }

                Row {
                    width: parent.width; spacing: 16
                    Field {
                        width: (parent.width - 16) / 2
                        label: "Dein Name"; placeholder: "Markus Beispiel"
                        text: win.fullName
                        onEdited: function(v) { win.fullName = v; if (!win.userEdited) win.userName = installer.suggestUser(v) }
                    }
                    Field {
                        width: (parent.width - 16) / 2
                        label: "Benutzername"; placeholder: "markus"
                        text: win.userName
                        onEdited: function(v) { win.userName = v; win.userEdited = true }
                    }
                }
                Row {
                    width: parent.width; spacing: 16
                    Field {
                        width: (parent.width - 16) / 2
                        label: "Passwort"; echo: TextInput.Password
                        text: win.password
                        onEdited: function(v) { win.password = v }
                    }
                    Field {
                        width: (parent.width - 16) / 2
                        label: "Passwort wiederholen"; echo: TextInput.Password
                        text: win.password2
                        onEdited: function(v) { win.password2 = v }
                    }
                }
                Row {
                    spacing: 6
                    readonly property int s: installer.strength(win.password)
                    Repeater {
                        model: 3
                        delegate: Rectangle {
                            width: 60; height: 6; radius: 3
                            anchors.verticalCenter: parent.verticalCenter
                            color: index < parent.s ? (parent.s === 1 ? Theme.flame : (parent.s === 2 ? "#e6d27a" : Theme.ok)) : Theme.track
                        }
                    }
                    Text {
                        text: win.password.length === 0 ? "" : (win.password !== win.password2 && win.password2.length > 0
                              ? "Passwörter stimmen nicht überein" : ["", "schwach", "mittel", "gut"][parent.s])
                        color: win.password !== win.password2 && win.password2.length > 0 ? Theme.flame : Theme.textMuted
                        font.pixelSize: 12
                    }
                }
                Field {
                    width: (parent.width - 16) / 2
                    label: "Name des Computers"
                    text: win.hostName
                    onEdited: function(v) { win.hostName = v }
                }
            }

            // ---- 3) Überblick --------------------------------------------------------------
            Column {
                visible: win.step === 3
                width: parent.width
                spacing: 10
                Text { text: "Alles bereit"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Text { text: "Bitte prüfe deine Auswahl. Erst mit „Jetzt installieren“ geht es los."; color: Theme.textMuted; font.pixelSize: 13 }
                Item { width: 1; height: 4 }
                Rectangle {
                    width: parent.width; height: sumCol.implicitHeight + 24; radius: 14
                    color: Theme.raised; border.color: Theme.hairline
                    Column {
                        id: sumCol
                        x: 18; y: 12; width: parent.width - 36
                        spacing: 0
                        Repeater {
                            model: [
                                ["Festplatte", win.chosenDisk ? win.chosenDisk.model + " · " + win.chosenDisk.sizeText + " (" + win.chosenDisk.path + ")" : "–"],
                                ["Benutzer", win.fullName + " (" + win.userName + ")"],
                                ["Computer", win.hostName],
                                ["Tastatur", win.keyboard],
                                ["Zeitzone", "Europa/Berlin"],
                                ["Grafik", installer.variant === "nvidia" ? "NVIDIA-Treiber enthalten" : "AMD/Intel"]
                            ]
                            delegate: Item {
                                width: sumCol.width; height: 36
                                Text { anchors.verticalCenter: parent.verticalCenter; text: modelData[0]; color: Theme.textMuted; font.pixelSize: 13 }
                                Text { x: 130; anchors.verticalCenter: parent.verticalCenter; text: modelData[1]; color: Theme.text; font.pixelSize: 13; font.bold: true; elide: Text.ElideRight; width: parent.width - 130 }
                                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hairline; visible: index < 5 }
                            }
                        }
                    }
                }
                Rectangle {
                    width: parent.width; height: warnRow.implicitHeight + 24; radius: 14
                    color: Qt.rgba(229 / 255, 72 / 255, 77 / 255, 0.12)
                    border.color: Qt.rgba(229 / 255, 72 / 255, 77 / 255, 0.5)
                    Row {
                        id: warnRow
                        x: 16; y: 12; width: parent.width - 32; spacing: 14
                        CSwitch {
                            anchors.verticalCenter: parent.verticalCenter
                            checked: win.understood
                            label: "Daten werden gelöscht"
                            onToggled: function(v) { win.understood = v }
                        }
                        Text {
                            width: parent.width - 60
                            anchors.verticalCenter: parent.verticalCenter
                            wrapMode: Text.WordWrap
                            text: "Mir ist klar, dass alles auf " + (win.chosenDisk ? win.chosenDisk.model + " (" + win.chosenDisk.sizeText + ", bisher: " + win.chosenDisk.previous + ")" : "der Festplatte") + " gelöscht wird."
                            color: Theme.text; font.pixelSize: 13
                        }
                    }
                }
            }

            // ---- 4) Installieren / Fertig ---------------------------------------------------
            Column {
                visible: win.step === 4
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                spacing: 16
                Rectangle {
                    width: 72; height: 72; radius: 22
                    color: installer.error.length > 0 ? "#e5484d" : (installer.done ? Theme.ok : Theme.accent)
                    SvgIcon { anchors.centerIn: parent; name: "rocket"; size: 44; visible: !installer.done && installer.error.length === 0 }
                    Text { anchors.centerIn: parent; visible: installer.done || installer.error.length > 0; text: installer.done ? "✓" : "!"; color: Theme.accentText; font.pixelSize: 34; font.bold: true }
                }
                Text {
                    text: installer.error.length > 0 ? "Das hat leider nicht geklappt"
                          : (installer.done ? "Creative OS ist installiert!" : "Creative OS wird installiert …")
                    color: Theme.text; font.pixelSize: 26; font.bold: true
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: installer.error.length > 0 ? installer.error
                          : (installer.done ? "Zieh den USB-Stick ab und starte neu. Danach meldest du dich als „" + win.userName + "“ an."
                                            : installer.stage + " – du kannst nebenbei weiter ausprobieren.")
                    color: installer.error.length > 0 ? Theme.flame : Theme.textMuted; font.pixelSize: 14
                }
                Item {
                    visible: !installer.done && installer.error.length === 0
                    width: parent.width; height: 26
                    Rectangle {
                        width: parent.width; height: 10; radius: 5; color: Theme.track
                        anchors.verticalCenter: parent.verticalCenter
                        Rectangle {
                            width: Math.max(10, parent.width * installer.percent / 100)
                            height: parent.height; radius: 5; color: Theme.accent
                            Behavior on width { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
                        }
                    }
                }
                Text {
                    visible: !installer.done && installer.error.length === 0
                    text: installer.percent + " %"
                    color: Theme.text; font.pixelSize: 13; font.bold: true
                }
                Rectangle {
                    visible: win.logOpen
                    width: parent.width; height: 140; radius: 12
                    color: Theme.ground; border.color: Theme.hairline
                    Flickable {
                        id: logView
                        anchors.fill: parent; anchors.margins: 10
                        contentHeight: logText.implicitHeight
                        clip: true
                        onContentHeightChanged: contentY = Math.max(0, contentHeight - height)
                        Text { id: logText; width: parent.width; text: installer.log; color: Theme.textMuted; font.family: "monospace"; font.pixelSize: 11; wrapMode: Text.WrapAnywhere }
                    }
                }
                Row {
                    spacing: 10
                    CSwitch { checked: win.logOpen; label: "Details"; onToggled: function(v) { win.logOpen = v } }
                    Text { text: "Details anzeigen"; color: Theme.textMuted; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                }
            }
        }

        // ---- Fußleiste ---------------------------------------------------------------------
        Item {
            id: footer
            anchors.left: side.right
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 76
            Rectangle { width: parent.width; height: 1; color: Theme.hairline }
            Text {
                visible: win.hint.length > 0
                anchors.left: parent.left; anchors.leftMargin: 36
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 360; wrapMode: Text.WordWrap
                text: win.hint; color: Theme.flame; font.pixelSize: 12
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 36
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                CButton {
                    visible: win.step === 0
                    text: "Erst ausprobieren"
                    onClicked: installer.quit()
                }
                CButton {
                    visible: win.step > 0 && win.step < 4
                    text: "Zurück"
                    onClicked: win.back()
                }
                CButton {
                    visible: win.step < 4
                    primary: win.step !== 3
                    danger: win.step === 3
                    enabled: win.canGoOn()
                    text: win.step === 3 ? "Jetzt installieren" : "Weiter"
                    onClicked: win.next()
                }
                CButton {
                    visible: win.step === 4 && installer.error.length > 0 && !installer.busy
                    text: "Zurück zur Auswahl"
                    onClicked: win.step = 3
                }
                CButton {
                    visible: win.step === 4 && installer.done
                    primary: true
                    text: "Jetzt neu starten"
                    onClicked: installer.reboot()
                }
            }
        }
    }
}
