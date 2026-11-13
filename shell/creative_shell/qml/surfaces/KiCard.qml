import QtQuick
import QtQuick.Layouts
import Creative

// Desktop-Karte des KI-Helfers: letzte Antwort, Einrichtungs-Fortschritt,
// ein Klick öffnet das Chat-Fenster (KiChat.qml).
ColumnLayout {
    id: card
    property var ki: kiHelper
    signal open()
    spacing: 8
    readonly property var lastAnswer: {
        const m = card.ki.messages
        for (let i = m.length - 1; i >= 0; i--)
            if (m[i].role === "assistant" && m[i].text.length) return m[i].text
        return ""
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        SvgIcon { name: "sparkle"; size: 18 }
        Text { Layout.fillWidth: true; text: "KI-Helfer"; color: Theme.text; font.bold: true; font.family: Theme.fontFamily }
        Rectangle {
            visible: card.ki.state === "bereit"
            implicitWidth: badge.implicitWidth + 14; implicitHeight: 20; radius: 10
            color: Theme.tint(0.06)
            Text {
                id: badge
                anchors.centerIn: parent
                text: card.ki.busy ? "denkt …" : card.ki.loaded ? "● bereit" : "lokal"
                color: card.ki.loaded || card.ki.busy ? Theme.ok : Theme.textMuted
                font.family: Theme.fontFamily; font.pixelSize: 11
            }
        }
    }
    Text {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: card.ki.state !== "laedt"
        text: card.ki.state !== "bereit"
              ? "Frag mich alles – Allgemeinwissen, Erklärungen oder eine E-Mail. Läuft komplett auf deinem PC."
              : parent.lastAnswer.length ? parent.lastAnswer.replace(/[*#_`>]/g, "")
              : "Was möchtest du wissen? Zum Beispiel: „Wer war der erste Bundeskanzler?“"
        color: parent.lastAnswer.length && card.ki.state === "bereit" ? Theme.text : Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 13
        wrapMode: Text.Wrap
        elide: Text.ElideRight
        maximumLineCount: 3
        textFormat: Text.PlainText
    }
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: card.ki.state === "laedt"
        spacing: 6
        Text { text: "Wird eingerichtet …"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
        Rectangle {
            Layout.fillWidth: true
            height: 6; radius: 3; color: Theme.tint(0.08)
            Rectangle { width: parent.width * Math.max(0.02, card.ki.progress / 100); height: 6; radius: 3; color: Theme.accent }
        }
        Text {
            Layout.fillWidth: true
            text: card.ki.status; color: Theme.textMuted
            font.family: Theme.fontFamily; font.pixelSize: 11; elide: Text.ElideRight
        }
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 38
        radius: 19
        color: askMouse.containsMouse ? Theme.hover : Theme.tint(0.05)
        border.color: Theme.hairline
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: card.ki.state === "einrichten" ? "Einrichten …" : "Frag mich etwas …"
            color: card.ki.state === "einrichten" ? Theme.accent : Theme.textMuted
            font.family: Theme.fontFamily; font.pixelSize: 13
            font.bold: card.ki.state === "einrichten"
        }
        SvgIcon { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; name: "send"; size: 16 }
        MouseArea { id: askMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: card.open() }
        Accessible.role: Accessible.Button
        Accessible.name: "KI-Helfer öffnen"
        Accessible.onPressAction: card.open()
    }
}
