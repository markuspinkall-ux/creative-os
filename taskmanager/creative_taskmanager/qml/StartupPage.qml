import QtQuick
import QtQuick.Controls.Basic
import Creative

// Autostart-Apps: welche Programme beim Anmelden mitstarten (ein/aus).
Item {
    id: root

    Text {
        id: hint
        x: 26
        y: 16
        width: parent.width - 52
        wrapMode: Text.WordWrap
        text: "Diese Programme starten automatisch, wenn du dich anmeldest. Weniger Autostart-Apps = schnellerer Start."
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 13
    }

    ListView {
        id: list
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: hint.bottom
        anchors.bottom: parent.bottom
        anchors.margins: 18
        anchors.topMargin: 16
        clip: true
        spacing: 4
        model: tm.autostart
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { contentItem: Rectangle { implicitWidth: 5; radius: 3; color: Theme.tint(0.2) } }
        delegate: Rectangle {
            required property var modelData
            width: ListView.view.width
            height: 58
            radius: 12
            color: am.containsMouse ? Theme.hover : Theme.tint(0.025)
            MouseArea { id: am; anchors.fill: parent; hoverEnabled: true }
            Image {
                id: ai
                x: 16
                anchors.verticalCenter: parent.verticalCenter
                width: 28; height: 28
                source: modelData.icon ? "image://icon/" + modelData.icon : "image://icon/application-x-executable"
                sourceSize.width: 56
                sourceSize.height: 56
                asynchronous: true
            }
            Column {
                anchors.left: ai.right
                anchors.leftMargin: 14
                anchors.right: stateText.left
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                Text { width: parent.width; elide: Text.ElideRight; text: modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.bold: true }
                Text { width: parent.width; elide: Text.ElideRight; text: modelData.command; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
            }
            Text {
                id: stateText
                anchors.right: sw.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.enabled ? "Aktiviert" : "Deaktiviert"
                color: modelData.enabled ? Theme.text : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            CSwitch {
                id: sw
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                checked: modelData.enabled
                label: "Beim Anmelden starten: " + modelData.name
                onToggled: (v) => tm.setAutostart(modelData.file, v)
            }
        }
    }

    Column {
        anchors.centerIn: list
        visible: list.count === 0
        spacing: 8
        SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "rocket"; size: 34 }
        Text {
            text: "Keine Autostart-Apps – Creative OS startet so schnell wie möglich."
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: 14
        }
    }
}
