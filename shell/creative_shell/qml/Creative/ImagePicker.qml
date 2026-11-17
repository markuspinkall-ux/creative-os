import QtCore
import QtQuick
import Creative

// Bildauswahl im Orbit-OS-Stil: FilePicker mit Bildfiltern, startet im Ordner „Bilder“.
FilePicker {
    title: "Bild wählen"
    acceptText: "Auswählen"
    mode: "open"
    nameFilters: ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif"]
    startFolder: StandardPaths.writableLocation(StandardPaths.PicturesLocation)
}
