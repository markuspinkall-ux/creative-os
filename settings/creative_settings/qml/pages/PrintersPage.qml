import QtQuick
import Creative
import ".."

SettingsPage {
    PageHeader {
        title: "Drucker"
        subtitle: printerList.printers.length === 0 ? "Kein Drucker eingerichtet"
                  : (printerList.printers.length === 1 ? "1 Drucker" : printerList.printers.length + " Drucker")
        CButton { text: "Aktualisieren"; onClicked: printerList.refresh() }
        CButton { text: "Drucker hinzufügen"; primary: true; onClicked: printerList.addPrinter() }
    }

    Message {
        text: printerList.available ? "" : "Der Druckdienst (CUPS) ist nicht installiert."
        warning: true
    }

    Card {
        visible: printerList.printers.length === 0
        title: "So kommt dein Drucker dazu"
        SettingRow {
            label: "Die meisten Drucker werden automatisch erkannt"
            hint: "Drucker einschalten und per USB-Kabel oder im selben WLAN verbinden. Er erscheint dann nach kurzer Zeit hier."
            last: true
            Item { width: 1; height: 1 }
        }
    }

    Repeater {
        model: printerList.printers
        delegate: Card {
            title: modelData.label
            subtitle: modelData.isDefault ? "Standarddrucker · " + modelData.state : modelData.state
            SettingRow {
                label: "Testseite drucken"
                hint: "Zeigt, ob der Drucker richtig arbeitet"
                CButton { text: "Testseite"; onClicked: printerList.testPage(modelData.name) }
            }
            SettingRow {
                label: "Standarddrucker"
                hint: "Wird beim Drucken automatisch vorgeschlagen"
                last: true
                CButton {
                    text: modelData.isDefault ? "Ist Standard" : "Als Standard festlegen"
                    enabled: !modelData.isDefault
                    onClicked: printerList.setDefault(modelData.name)
                }
            }
        }
    }
}
