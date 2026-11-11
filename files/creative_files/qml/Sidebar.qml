import QtQuick
import QtQuick.Controls.Basic
import Creative

Rectangle {
    color: "#171b22"

    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.tint(0.05) }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: 10
        anchors.bottomMargin: 54
        contentHeight: col.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: col
            width: flick.width
            spacing: 1

            SectionLabel { text: "SCHNELLZUGRIFF" }
            NavRow {
                text: "Persönlicher Ordner"
                icon: "home"
                current: fm.page === "folder" && fm.currentPath === fm.homePath
                onClicked: fm.navigate(fm.homePath)
            }
            Repeater {
                model: fm.quickPlaces
                delegate: NavRow {
                    text: modelData.name
                    chip: modelData.color
                    current: fm.page === "folder" && fm.currentPath === modelData.path
                    onClicked: fm.navigate(modelData.path)
                }
            }

            SectionLabel { text: "GERÄTE"; topPadding: 14 }
            NavRow {
                text: "Dieser PC"
                icon: "pc"
                current: fm.page === "pc"
                onClicked: fm.openPage("pc")
            }
            Repeater {
                model: fm.drives
                delegate: NavRow {
                    indent: 10
                    text: modelData.name
                    icon: modelData.removable ? "usb" : "drive"
                    ejectable: modelData.removable && modelData.mounted
                    current: fm.page === "folder" && !modelData.system && modelData.mountPath.length > 0
                             && fm.currentPath.indexOf(modelData.mountPath) === 0
                    onClicked: fm.openDrive(index)
                    onEjectClicked: fm.ejectDrive(index)
                }
            }
        }
    }

    NavRow {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 10
        width: parent.width - 20
        text: "Papierkorb"
        icon: "trash"
        current: fm.page === "trash"
        onClicked: fm.openPage("trash")
    }

    component SectionLabel: Text {
        leftPadding: 12
        topPadding: 6
        bottomPadding: 6
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.bold: true
    }
}
