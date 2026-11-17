import QtCore
import QtQuick
import QtQuick.Controls.Basic
import Creative
import ".."

SettingsPage {
    id: root

    PageHeader {
        title: "VPN"
        subtitle: vpn.connected ? "Geschützt über Proton VPN – " + vpn.activeCountry
                                : vpn.servers.length ? "Proton VPN ist aus" : "Proton VPN einrichten"
        CButton {
            visible: vpn.connected
            text: "Trennen"
            enabled: !vpn.busy
            onClicked: vpn.disconnect()
        }
    }

    Message {
        text: !vpn.available ? "Die Netzwerkverwaltung (NetworkManager) läuft nicht." : vpn.message
        warning: !vpn.available || /nicht|fehl|ungültig|abgelehnt|keine/i.test(vpn.message)
    }

    Card {
        title: "Server"
        subtitle: vpn.servers.length ? "Immer nur ein Server gleichzeitig. Auch im Schnellzugriff (Tray) ein- und ausschaltbar."
                                     : "Noch kein Server – so geht's unten in drei Schritten."
        Repeater {
            model: vpn.servers
            delegate: SettingRow {
                required property var modelData
                required property int index
                label: modelData.country
                hint: (modelData.active ? "Verbunden · " : modelData.uuid === vpn.lastUuid ? "Zuletzt benutzt · " : "")
                      + (modelData.server || "Proton VPN")
                last: index === vpn.servers.length - 1
                Row {
                    spacing: 8
                    CButton {
                        text: modelData.active ? "Trennen" : "Verbinden"
                        primary: !modelData.active
                        enabled: !vpn.busy
                        onClicked: modelData.active ? vpn.disconnect() : vpn.connectTo(modelData.uuid)
                    }
                    IconButton {
                        icon: "trash"
                        iconSize: 16
                        width: 34
                        height: 34
                        label: "„" + modelData.country + "“ entfernen"
                        enabled: !vpn.busy
                        onClicked: { removeDialog.server = modelData; removeDialog.open() }
                    }
                }
            }
        }
        SettingRow {
            label: "Konfiguration hinzufügen"
            hint: "Eine WireGuard-Datei (.conf) von Proton VPN auswählen"
            last: true
            CButton {
                text: "Datei wählen …"
                primary: vpn.servers.length === 0
                enabled: vpn.available
                onClicked: picker.open()
            }
        }
    }

    Card {
        title: "So richtest du Proton VPN ein"
        subtitle: "Proton VPN ist kostenlos nutzbar (ohne Datenlimit, Server in mehreren Ländern) – aus der Schweiz, Open Source"
        Repeater {
            model: [
                { t: "1. Bei Proton anmelden", h: "Ein kostenloses Proton-Konto genügt. Der Knopf öffnet die Download-Seite im Browser." },
                { t: "2. WireGuard-Konfiguration erstellen", h: "Unter „WireGuard-Konfiguration“: einen Namen eingeben (z. B. „Orbit OS“), als Plattform „GNU/Linux“ wählen, dann bei einem Server auf „Erstellen“ und die .conf-Datei herunterladen." },
                { t: "3. Hier hinzufügen", h: "Oben „Datei wählen …“ – die Datei liegt meist in Downloads. Für weitere Länder einfach weitere Dateien hinzufügen." }
            ]
            delegate: SettingRow {
                required property var modelData
                required property int index
                label: modelData.t
                hint: modelData.h
                last: index === 2
                CButton {
                    visible: index === 0
                    text: "Proton öffnen"
                    onClicked: vpn.openProton()
                }
            }
        }
    }

    Card {
        title: "Gut zu wissen"
        SettingRow {
            label: "Nur für dein Konto"
            hint: "Die VPN-Verbindungen und Schlüssel gehören nur dir – andere Benutzerkonten auf diesem PC sehen sie nicht. Nach dem Hinzufügen kannst du die .conf-Datei löschen."
        }
        SettingRow {
            label: "Startet nicht von selbst"
            hint: "Nach dem Neustart ist das VPN aus. Einschalten hier oder im Schnellzugriff."
        }
        SettingRow {
            label: "Ganzer PC"
            hint: "Solange das VPN an ist, laufen alle Programme darüber – Browser, Spiele, Updates. Für Online-Spiele kann das die Latenz erhöhen."
            last: true
        }
    }

    FilePicker {
        id: picker
        title: "WireGuard-Konfiguration wählen"
        nameFilters: ["*.conf"]
        startFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        onAccepted: (url) => vpn.importFile(url.toString())
    }

    ConfirmDialog {
        id: removeDialog
        property var server
        danger: true
        title: server ? "„" + server.country + "“ entfernen?" : "Server entfernen?"
        text: "Die VPN-Verbindung wird von diesem PC gelöscht. Du kannst sie jederzeit mit der .conf-Datei wieder hinzufügen."
        confirmText: "Entfernen"
        onConfirmed: if (server) vpn.remove(server.uuid)
    }

    Component.onCompleted: vpn.refresh()
}
