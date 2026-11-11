import QtQuick
import Creative

// Eigene Creative-Symbole aus dem Ordner icons/ (einheitlich weiß-blau).
Image {
    property string name
    property int size: 22

    width: size
    height: size
    source: name ? Qt.resolvedUrl((name.endsWith("-dark") ? "icons/" : Theme.iconDir) + name + ".svg") : ""
    sourceSize.width: size * 2
    sourceSize.height: size * 2
    fillMode: Image.PreserveAspectFit
    smooth: true
    Accessible.ignored: true
}
