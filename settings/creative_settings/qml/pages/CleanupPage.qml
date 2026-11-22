import QtQuick
import Creative
import ".."

// Bereinigung – Platz schaffen wie mit CCleaner: erst analysieren, dann angehakte Bereiche leeren.
// Gelöscht wird nur, was sich von selbst neu bildet oder schon im Papierkorb liegt.
SettingsPage {
    id: root

    PageHeader {
        title: "Bereinigung"
        subtitle: "Platz schaffen: Papierkorb, Zwischenspeicher und Reste aufräumen – deine Dateien bleiben unberührt"
    }

    Card {
        Item {
            width: parent.width
            height: 76
            Rectangle {
                width: 52; height: 52; radius: 14
                anchors.verticalCenter: parent.verticalCenter
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15)
                SvgIcon { anchors.centerIn: parent; name: "sparkle"; size: 24 }
            }
            Column {
                x: 70
                width: parent.width - 70 - btns.width - 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Text {
                    width: parent.width
                    text: cleanup.busy ? cleanup.phase : (cleanup.summary || "Erst analysieren – dann siehst du, wie viel Platz frei wird")
                    color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Tipp: Browser und Spiele vorher schließen."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                }
            }
            Row {
                id: btns
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                CButton { objectName: "analyzeBtn"; text: "Analysieren"; enabled: !cleanup.busy; onClicked: cleanup.analyze() }
                CButton { objectName: "cleanBtn"; text: "Bereinigen"; primary: true; enabled: !cleanup.busy; onClicked: cleanup.clean() }
            }
        }
    }

    Card {
        title: "Was aufgeräumt wird"
        Repeater {
            id: rows
            model: cleanup.rows
            delegate: SettingRow {
                required property var modelData
                required property int index
                label: modelData.name
                hint: modelData.hint
                last: index === rows.count - 1
                Row {
                    spacing: 14
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.done ? "✓ " + (modelData.note || "bereinigt")
                                             : (modelData.sizeText || modelData.note || "")
                        color: modelData.done ? Theme.ok : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: !modelData.done && modelData.sizeText !== ""
                    }
                    CSwitch {
                        anchors.verticalCenter: parent.verticalCenter
                        checked: modelData.checked
                        enabled: !cleanup.busy
                        label: modelData.name + " bereinigen"
                        onToggled: (v) => cleanup.setChecked(modelData.key, v)
                    }
                }
            }
        }
    }
}
