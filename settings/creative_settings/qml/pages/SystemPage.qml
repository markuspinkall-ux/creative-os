import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root
    property bool renaming: false

    PageHeader {
        title: "System"
        subtitle: system.info.os
    }

    Message { text: system.message }

    Card {
        title: "Gerätename"
        SettingRow {
            label: system.hostName
            hint: "So heißt der PC im Netzwerk"
            last: !root.renaming
            CButton { text: "Umbenennen"; visible: !root.renaming; onClicked: { root.renaming = true; nameField.text = system.hostName; nameField.forceActiveFocus(); nameField.selectAll() } }
        }
        Column {
            visible: root.renaming
            width: parent.width
            spacing: 8
            bottomPadding: 6
            Row {
                spacing: 8
                TextField {
                    id: nameField
                    width: 260
                    height: 36
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    leftPadding: 12
                    background: Rectangle { radius: 10; color: Theme.ground; border.color: nameField.activeFocus ? Theme.accent : Theme.hairline }
                    onAccepted: saveBtn.clicked()
                }
                CButton {
                    id: saveBtn
                    text: "Speichern"
                    primary: true
                    onClicked: {
                        const err = system.rename(nameField.text)
                        nameError.text = err
                        if (!err) root.renaming = false
                    }
                }
                CButton { text: "Abbrechen"; onClicked: { root.renaming = false; nameError.text = "" } }
            }
            Text { id: nameError; visible: text.length > 0; color: Theme.flame; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
    }

    Card {
        title: "Gerät"
        SettingRow { label: "Prozessor"; Text { text: system.info.cpu; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow { label: "Arbeitsspeicher"; Text { text: system.info.ram; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow {
            label: "Grafik"
            Text { text: system.info.gpu; width: Math.min(implicitWidth, 520); elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
        }
        SettingRow { label: "Systemlaufwerk"; Text { text: system.info.disk; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow { label: "System"; Text { text: system.info.os; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true } }
        SettingRow { label: "Kernel"; last: true; Text { text: system.info.kernel; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 } }
    }

    Card {
        title: "Benutzerkonten"
        Repeater {
            model: system.accounts
            delegate: SettingRow {
                required property var modelData
                label: modelData.name
                hint: modelData.current ? "Aktuell angemeldet" : "Lokales Konto"
                CButton {
                    text: "Konto löschen"
                    visible: !modelData.current
                    enabled: !system.accountBusy
                    onClicked: {
                        deleteAccountDialog.account = modelData
                        deleteAccountDialog.open()
                    }
                }
            }
        }
    }

    Dialog {
        id: deleteAccountDialog
        property var account
        anchors.centerIn: Overlay.overlay
        title: account ? "Konto „" + account.name + "“ löschen?" : "Konto löschen?"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label {
            text: "Der persönliche Ordner bleibt erhalten."
            color: Theme.text
        }
        onAccepted: if (account) system.deleteAccount(account.uid, account.name)
    }

    // ---- Danke: worauf Creative OS aufbaut --------------------------------------------------
    Card {
        title: "Über Creative OS"
        subtitle: "Creative OS steht auf den Schultern großartiger Open-Source-Projekte. Danke an alle, die daran mitarbeiten!"
        Repeater {
            id: credits
            model: [
                { app: "Unterbau", base: "Fedora Kinoite (Fedora-Projekt)" },
                { app: "Fenster, Anmeldung, Sitzung", base: "KDE Plasma: KWin, SDDM, KDE Frameworks" },
                { app: "Oberflächen der Creative-Apps", base: "Qt und PySide (The Qt Company / Qt Project)" },
                { app: "Creative Software", base: "Flatpak und Flathub" },
                { app: "Terminal", base: "Konsole (KDE)" },
                { app: "Entpacken", base: "Ark (KDE)" },
                { app: "Laufwerke", base: "UDisks, exfatprogs, ntfsprogs" },
                { app: "OBS Studio", base: "OBS Studio (OBS Project, GPL v2) – unverändert, nur im Graphit-Look" },
                { app: "Creative Broadcast", base: "DeepFilterNet (Rauschfilter), Robust Video Matting (Freistellung), v4l2loopback" },
                { app: "Creative Iso", base: "bootc-image-builder, Lorax/mkksiso, Anaconda (Fedora-Installer)" },
                { app: "Automatisches Zurückrollen", base: "greenboot" },
                { app: "Bildschirmfoto-Dienst für Creative Shots", base: "Spectacle (KDE)" },
                { app: "Ton und Bild", base: "PipeWire, FFmpeg, Qt Multimedia" },
                { app: "YouTube Music im Creative Player", base: "Offizielle Webseite von YouTube Music, Qt WebEngine (Chromium)" },
                { app: "Sprachassistent", base: "Vosk, faster-whisper, Piper; Wetter von Open-Meteo" },
                { app: "Mein Server", base: "Caddy und PHP" },
                { app: "Browser, Spiele, Chat", base: "Brave, Steam, Discord (unverändert, Eigentum der jeweiligen Firmen)" }
            ]
            delegate: SettingRow {
                required property var modelData
                required property int index
                label: modelData.app
                hint: modelData.base
                last: index === credits.count - 1
            }
        }
    }

    // ---- Quellcode und Lizenzen -------------------------------------------------------------
    Card {
        title: "Quellcode und Lizenzen"
        SettingRow {
            label: "Eigene Programme von Creative OS"
            hint: "© 2026 Markus Pinkall – alle Rechte vorbehalten. Der Quellcode ist auf GitHub einsehbar, darf aber ohne Erlaubnis nicht übernommen werden."
            CButton { text: "Öffnen"; onClicked: system.openUrl("https://github.com/markuspinkall-ux/creative-os") }
        }
        SettingRow {
            label: "Enthaltene Open-Source-Programme"
            hint: "Behalten ihre eigenen Lizenzen (z. B. GPL, LGPL, MIT). Die Lizenztexte liegen unter /usr/share/licenses, die Quellen stellt das Fedora-Projekt bereit."
            last: true
            CButton { text: "Lizenzen ansehen"; onClicked: system.openUrl("file:///usr/share/licenses") }
        }
    }
}
