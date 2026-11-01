import QtQuick

// Eigene Creative-Symbole aus dem Ordner icons/ (einheitlich weiß-blau).
Image {
    property string name
    property int size: 22

    width: size
    height: size
    source: name ? Qt.resolvedUrl("icons/" + name + ".svg") : ""
    sourceSize.width: size * 2
    sourceSize.height: size * 2
    fillMode: Image.PreserveAspectFit
    smooth: true
    Accessible.ignored: true
}
