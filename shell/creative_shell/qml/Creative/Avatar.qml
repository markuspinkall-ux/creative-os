import QtQuick
import Creative

// Runder Avatar: eigenes Profilbild, sonst das Kürzel aus Vor- und Nachname.
// Das Bild ist schon rund gespeichert (siehe creative_shell/avatar.py),
// deshalb braucht es hier keine Maske.
Rectangle {
    id: avatar

    property string source: ""         // file://…  ("" = Kürzel zeigen)
    property string initials: "?"
    property int size: 34

    width: size
    height: size
    radius: size / 2
    color: picture.status === Image.Ready ? "transparent" : Theme.accent

    Text {
        anchors.centerIn: parent
        visible: picture.status !== Image.Ready
        text: avatar.initials
        color: Theme.accentText
        font.family: Theme.fontFamily
        font.pixelSize: Math.round(avatar.size * (avatar.initials.length > 1 ? 0.38 : 0.44))
        font.bold: true
    }
    Image {
        id: picture
        anchors.fill: parent
        source: avatar.source
        visible: status === Image.Ready
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: avatar.size * 2
        sourceSize.height: avatar.size * 2
        smooth: true
        mipmap: true
        cache: false
        asynchronous: true
    }

    Accessible.role: Accessible.Graphic
    Accessible.name: picture.status === Image.Ready ? "Profilbild" : "Kürzel " + initials
}
