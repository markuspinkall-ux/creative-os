import QtQuick
import QtQuick.Controls.Basic as T
import Creative

// Eintrag für CMenu. danger: true färbt rot (Löschen u. Ä.).
T.MenuItem {
    id: item
    property bool danger: false
    implicitWidth: label.implicitWidth + leftPadding + rightPadding + (subMenu ? 18 : 0)
    implicitHeight: visible ? 34 : 0
    height: visible ? implicitHeight : 0
    leftPadding: checkable ? 34 : 12
    rightPadding: 14
    font.family: Theme.fontFamily
    font.pixelSize: 13
    contentItem: Text {
        id: label
        text: item.text
        font: item.font
        color: !item.enabled ? Theme.textMuted : (item.danger ? "#e5484d" : Theme.text)
        opacity: item.enabled ? 1 : 0.7
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }
    indicator: Rectangle {
        visible: item.checkable
        x: 11
        anchors.verticalCenter: parent.verticalCenter
        width: 15; height: 15; radius: 4
        color: item.checked ? Theme.accent : "transparent"
        border.color: item.checked ? Theme.accent : Theme.textMuted
        Text {
            anchors.centerIn: parent
            visible: item.checked
            text: "✓"
            color: Theme.light ? "#ffffff" : "#12151b"
            font.pixelSize: 11
            font.bold: true
        }
    }
    arrow: Text {
        visible: !!item.subMenu
        x: item.width - width - 10
        anchors.verticalCenter: parent.verticalCenter
        text: "›"
        color: Theme.textMuted
        font.pixelSize: 16
    }
    background: Rectangle {
        implicitWidth: 200
        radius: 8
        color: item.down ? Theme.tint(0.12) : (item.highlighted ? Theme.tint(0.08) : "transparent")
    }
}
