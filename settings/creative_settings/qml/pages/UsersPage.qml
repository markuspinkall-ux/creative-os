import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root

    // Eingabefeld im Creative-Stil
    component Field: Rectangle {
        id: field
        property alias text: input.text
        property alias input: input
        property string placeholder
        property bool password: false
        property bool bad: false
        width: 320; height: 38; radius: 10
        color: Theme.ground
        border.color: bad ? "#ff8a8e" : (input.activeFocus ? Theme.accent : Theme.hairline)
        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: TextInput.AlignVCenter
            echoMode: field.password ? TextInput.Password : TextInput.Normal
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.accentText
            font.family: Theme.fontFamily
            font.pixelSize: 14
            clip: true
        }
        Text {
            visible: input.text.length === 0
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            text: field.placeholder
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }
    }

    component FieldLabel: Text {
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }

    component Badge: Rectangle {
        property string text
        property color tint: Theme.accent
        height: 22; radius: 11
        width: badgeText.implicitWidth + 18
        color: Qt.rgba(tint.r, tint.g, tint.b, 0.16)
        Text {
            id: badgeText
            anchors.centerIn: parent
            text: parent.text
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 11
            font.bold: true
        }
    }

    Connections {
        target: users
        function onDone(ok, text) {
            if (ok) { addPopup.close(); passwordPopup.close(); deletePopup.close() }
            status.warning = !ok
            status.text = text
        }
    }

    PageHeader {
        title: "Benutzerkonten"
        subtitle: "Wer diesen PC benutzt – jedes Konto hat eigene Dateien, Einstellungen und ein eigenes Passwort"
        CButton { text: "Konto hinzufügen"; primary: true; enabled: !users.busy; onClicked: addPopup.openFresh() }
    }

    Message { id: status; text: "" }

    Card {
        title: "Konten auf diesem PC"
        subtitle: "Änderungen brauchen das Passwort eines Administrators"
        Repeater {
            model: users.accounts
            delegate: Item {
                required property var modelData
                required property int index
                width: parent ? parent.width : 600
                height: 74
                Rectangle {
                    visible: index > 0
                    width: parent.width; height: 1
                    color: Theme.hairline
                }
                Avatar {
                    id: face
                    size: 46
                    anchors.verticalCenter: parent.verticalCenter
                    source: modelData.picture
                    initials: modelData.initials
                }
                Column {
                    x: 62
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 62 - actions.width - 16
                    spacing: 5
                    Row {
                        spacing: 8
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.name
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: 15
                            font.bold: true
                        }
                        Badge { visible: modelData.me; text: "Du"; anchors.verticalCenter: parent.verticalCenter }
                        Badge { visible: modelData.admin; text: "Administrator"; tint: "#ffb07a"; anchors.verticalCenter: parent.verticalCenter }
                        Badge { visible: modelData.active && !modelData.me; text: "angemeldet"; tint: "#6fdcc0"; anchors.verticalCenter: parent.verticalCenter }
                        Badge { visible: modelData.nopassword; text: "ohne Passwort"; tint: "#c3a6ff"; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Text {
                        text: modelData.login + "  ·  " + modelData.home
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                    }
                }
                Row {
                    id: actions
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    CButton {
                        text: modelData.nopassword ? "Passwort vergeben" : "Passwort ändern"
                        enabled: !users.busy
                        onClicked: passwordPopup.openFor(modelData)
                    }
                    CButton {
                        text: modelData.admin ? "Zum Standardkonto" : "Zum Administrator"
                        enabled: !users.busy && !(modelData.admin && (modelData.me || users.adminCount <= 1)) && !(modelData.nopassword && !modelData.admin)
                        onClicked: users.setAdmin(modelData.login, !modelData.admin)
                    }
                    CButton {
                        text: "Löschen"
                        danger: true
                        enabled: !users.busy && !modelData.me
                        onClicked: deletePopup.openFor(modelData)
                    }
                }
            }
        }
    }

    Message {
        text: "Administratoren dürfen Programme installieren, Updates einspielen und Konten verwalten. "
              + "Standardkonten können alles andere – gut für Kinder oder Gäste."
    }

    // ---- Konto hinzufügen ---------------------------------------------------------------
    Popup {
        id: addPopup
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 460
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        property bool loginTouched: false
        property string loginHint: loginField.text.length ? users.check(loginField.text) : ""
        property bool ready: nameField.text.trim().length > 0 && loginHint === "" && loginField.text.length > 0
                             && (noPw.checked || (pw1.text.length >= 4 && pw1.text === pw2.text))

        function openFresh() {
            nameField.text = ""; loginField.text = ""; pw1.text = ""; pw2.text = ""
            loginTouched = false; adminSwitch.checked = false; noPw.checked = false
            open()
            nameField.input.forceActiveFocus()
        }

        contentItem: Column {
            spacing: 10
            Text {
                text: "Neues Konto"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 19
                font.bold: true
            }
            Item { width: 1; height: 2 }
            FieldLabel { text: "Name" }
            Field {
                id: nameField
                width: parent.width
                placeholder: "z. B. Anna Müller"
                input.onTextEdited: if (!addPopup.loginTouched) loginField.text = users.suggest(nameField.text)
            }
            FieldLabel { text: "Benutzername (zum Anmelden, klein geschrieben)" }
            Field {
                id: loginField
                width: parent.width
                placeholder: "anna"
                bad: addPopup.loginHint !== ""
                input.onTextEdited: addPopup.loginTouched = true
            }
            FieldLabel { visible: addPopup.loginHint !== ""; text: addPopup.loginHint; color: "#ff8a8e" }
            CSwitch {
                id: noPw
                label: "Ohne Passwort – Anmelden mit einem Klick (gut für Kinder oder einen Familien-PC)"
                onToggled: value => { noPw.checked = value; if (value) adminSwitch.checked = false }
            }
            FieldLabel { visible: !noPw.checked; text: "Passwort" }
            Field { id: pw1; visible: !noPw.checked; width: parent.width; password: true; placeholder: "mindestens 4 Zeichen" }
            Field {
                id: pw2
                visible: !noPw.checked
                width: parent.width
                password: true
                placeholder: "Passwort wiederholen"
                bad: pw2.text.length > 0 && pw2.text !== pw1.text
            }
            FieldLabel { visible: !noPw.checked && pw2.text.length > 0 && pw2.text !== pw1.text; text: "Die Passwörter sind verschieden."; color: "#ff8a8e" }
            Item { width: 1; height: 2 }
            CSwitch {
                id: adminSwitch
                visible: !noPw.checked
                label: "Administrator (darf Programme installieren und Konten verwalten)"
                onToggled: value => adminSwitch.checked = value
            }
            Item { width: 1; height: 6 }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: addPopup.close() }
                CButton {
                    text: users.busy ? "Wird angelegt …" : "Konto anlegen"
                    primary: true
                    enabled: addPopup.ready && !users.busy
                    onClicked: users.add(nameField.text, loginField.text, noPw.checked ? "" : pw1.text,
                                         adminSwitch.checked && !noPw.checked)
                }
            }
        }
    }

    // ---- Passwort ändern ------------------------------------------------------------------
    Popup {
        id: passwordPopup
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 420
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        property var account: ({})
        function openFor(a) { account = a; np1.text = ""; np2.text = ""; open(); np1.input.forceActiveFocus() }
        contentItem: Column {
            spacing: 10
            Text {
                text: "Neues Passwort für " + (passwordPopup.account.name || "")
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.bold: true
            }
            Field { id: np1; width: parent.width; password: true; placeholder: "Neues Passwort (mindestens 4 Zeichen)" }
            Field { id: np2; width: parent.width; password: true; placeholder: "Wiederholen"; bad: np2.text.length > 0 && np2.text !== np1.text }
            Item { width: 1; height: 6 }
            Text {
                visible: passwordPopup.account.admin === true
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Administratoren brauchen immer ein Passwort."
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton {
                    visible: !passwordPopup.account.admin && !passwordPopup.account.nopassword
                    text: "Ohne Passwort"
                    enabled: !users.busy
                    onClicked: users.setPassword(passwordPopup.account.login, "")
                }
                CButton { text: "Abbrechen"; onClicked: passwordPopup.close() }
                CButton {
                    text: "Passwort ändern"
                    primary: true
                    enabled: np1.text.length >= 4 && np1.text === np2.text && !users.busy
                    onClicked: users.setPassword(passwordPopup.account.login, np1.text)
                }
            }
        }
    }

    // ---- Löschen ----------------------------------------------------------------------------
    Popup {
        id: deletePopup
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 460
        modal: true
        focus: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }
        background: Rectangle { radius: 18; color: Theme.raised; border.color: Theme.hairline }
        property var account: ({})
        function openFor(a) { account = a; keepSwitch.checked = true; open() }
        contentItem: Column {
            spacing: 12
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Konto „" + (deletePopup.account.name || "") + "“ löschen?"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.bold: true
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: deletePopup.account.active
                      ? "Das Konto ist gerade angemeldet. Bitte dort zuerst abmelden."
                      : "Das Konto kann sich danach nicht mehr anmelden."
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            CSwitch {
                id: keepSwitch
                label: "Persönliche Dateien behalten (kommen in /var/home/geloeschte-konten)"
                onToggled: value => keepSwitch.checked = value
            }
            Text {
                visible: !keepSwitch.checked
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Alle Dateien von " + (deletePopup.account.login || "") + " werden endgültig gelöscht."
                color: "#ff8a8e"
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            Item { width: 1; height: 4 }
            Row {
                anchors.right: parent.right
                spacing: 8
                CButton { text: "Abbrechen"; onClicked: deletePopup.close() }
                CButton {
                    text: "Konto löschen"
                    danger: true
                    enabled: !users.busy && !deletePopup.account.active
                    onClicked: users.remove(deletePopup.account.login, keepSwitch.checked)
                }
            }
        }
    }
}
