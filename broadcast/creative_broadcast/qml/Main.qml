import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Creative

// Creative Broadcast – rauschfreies Mikrofon und virtueller Greenscreen.
Window {
    id: win
    width: 980
    height: 660
    minimumWidth: 820
    minimumHeight: 560
    visible: true
    title: "Creative Broadcast"
    color: Theme.surface

    onActiveChanged: bc.setPreview(active && bc.camera)
    Connections { target: bc; function onChanged() { bc.setPreview(win.active && bc.camera) } }

    // ---- Kopf --------------------------------------------------------------------------
    Row {
        x: 26
        y: 20
        spacing: 12
        Rectangle {
            width: 38; height: 38; radius: 12
            color: Theme.accent
            SvgIcon { anchors.centerIn: parent; name: "broadcast"; size: 18 }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "Creative Broadcast"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true }
            Text { text: "Rauschfreies Mikrofon und virtueller Hintergrund für Discord, Teams, OBS und Co."; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        }
    }

    Row {
        id: cards
        x: 20
        y: 84
        width: parent.width - 40
        height: parent.height - 104
        spacing: 16

        // ---- Mikrofon ------------------------------------------------------------------------
        Panel {
            width: (cards.width - 16) * 0.42
            height: cards.height
            icon: "mic"
            title: "Mikrofon"
            on: bc.voice
            onToggled: (v) => bc.setVoice(v)

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Rauschentfernung filtert Tastatur, Lüfter, Hintergrundgeräusche und Hall – deine Stimme bleibt natürlich."
                color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12
            }
            Item { width: 1; height: 6 }
            Text { text: "Stärke"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
            Row {
                width: parent.width
                spacing: 10
                CSlider {
                    id: strength
                    width: parent.width - 54
                    anchors.verticalCenter: parent.verticalCenter
                    from: 0; to: 100; stepSize: 5
                    value: bc.strength
                    enabled: bc.voice
                    onMoved: bc.setStrength(Math.round(value))
                    Accessible.name: "Stärke der Rauschentfernung"
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: Math.round(strength.value) + " %"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12 }
            }
            Item { width: 1; height: 8 }
            Row {
                width: parent.width
                spacing: 6
                ComboBox {
                    width: parent.width - refreshMics.width - parent.spacing
                    model: [{ id: "", label: "Echtes Mikrofon wählen" }].concat(bc.microphones)
                    textRole: "label"
                    valueRole: "id"
                    currentIndex: Math.max(0, indexOfValue(bc.voiceInput))
                    Accessible.name: "Echtes Mikrofon"
                    onActivated: bc.setVoiceInput(currentValue)
                }
                CButton { id: refreshMics; text: "Aktualisieren"; onClicked: bc.refreshMicrophones() }
            }
            InfoRow { label: "Neue Eingabe"; value: "Creative Mikrofon (rauschfrei)" }
            InfoRow { label: "Technik"; value: bc.deepFilter ? "DeepFilterNet (KI)" : "WebRTC (Ersatz)" }
            InfoRow { label: "Zustand"; value: bc.voice ? bc.voiceStatus : "Aus" }
            Item { width: 1; height: 8 }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: bc.voice
                text: "In Discord, Teams oder Zoom „Creative Mikrofon (rauschfrei)“ als Mikrofon wählen."
                color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }

        // ---- Kamera --------------------------------------------------------------------------
        Panel {
            width: (cards.width - 16) * 0.58
            height: cards.height
            icon: "screen-tool"
            title: "Kamera"
            on: bc.camera
            onToggled: (v) => bc.setCamera(v)

            // Vorschau
            Rectangle {
                width: parent.width
                height: width * 9 / 16
                radius: 12
                color: Theme.ground
                clip: true
                Image {
                    anchors.fill: parent
                    visible: bc.camera && bc.previewUrl.length > 0
                    source: bc.camera ? bc.previewUrl : ""
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    asynchronous: true
                    retainWhileLoading: true
                }
                Text {
                    anchors.centerIn: parent
                    visible: !bc.camera || bc.previewUrl.length === 0
                    width: parent.width - 40
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: bc.camera ? (bc.cameraStatus.indexOf("fehlt") === 0 || bc.cameraStatus.indexOf("keine") === 0 ? bc.cameraStatus : "Vorschau wird geladen …")
                                    : "Kamera-Effekt einschalten, um die Vorschau zu sehen."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
                }
                Rectangle {
                    visible: bc.camera && bc.fps > 0
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 10
                    width: fpsText.implicitWidth + 16
                    height: 24
                    radius: 8
                    color: Qt.rgba(0, 0, 0, 0.55)
                    Text { id: fpsText; anchors.centerIn: parent; text: bc.fps + " Bilder/s · " + bc.engine; color: "white"; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
            }

            Text { text: "Hintergrund"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; font.bold: true }
            Row {
                spacing: 6
                Repeater {
                    model: [
                        { k: "blur", t: "Unscharf" },
                        { k: "replace", t: "Eigenes Bild" },
                        { k: "green", t: "Greenscreen" },
                        { k: "none", t: "Aus" }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool cur: bc.effect === modelData.k
                        width: chipText.implicitWidth + 26
                        height: 32
                        radius: 16
                        color: cur ? Theme.accent : (chipMouse.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
                        Text { id: chipText; anchors.centerIn: parent; text: modelData.t; color: parent.cur ? Theme.accentText : Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modelData.k === "replace" && !bc.background ? imageDialog.open() : bc.setEffect(modelData.k)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Hintergrund: " + modelData.t
                    }
                }
            }
            Row {
                visible: bc.effect === "replace"
                spacing: 10
                Rectangle {
                    width: 64; height: 36; radius: 6
                    color: Theme.ground
                    clip: true
                    Image { anchors.fill: parent; source: bc.backgroundUrl; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 128 }
                }
                CButton { anchors.verticalCenter: parent.verticalCenter; text: "Bild wählen …"; onClicked: imageDialog.open() }
            }

            Row {
                spacing: 18
                Column {
                    spacing: 4
                    Text { text: "Kamera"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                    ComboBox {
                        id: camBox
                        width: 240
                        model: [{ device: "", name: "Automatisch" }].concat(bc.cameras)
                        textRole: "name"
                        currentIndex: Math.max(0, model.findIndex(c => c.device === bc.cameraDevice))
                        onActivated: (i) => bc.setCameraDevice(model[i].device)
                        background: Rectangle { radius: 8; color: Theme.tint(0.06) }
                        contentItem: Text { leftPadding: 12; text: camBox.displayText; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                    }
                }
                Column {
                    spacing: 4
                    Text { text: "Qualität"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                    Row {
                        spacing: 6
                        Repeater {
                            model: [{ k: "sparsam", t: "Sparsam" }, { k: "hoch", t: "Beste Qualität" }]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool cur: bc.quality === modelData.k
                                width: qText.implicitWidth + 24
                                height: 32
                                radius: 16
                                color: cur ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.25) : (qm.containsMouse ? Theme.tint(0.1) : Theme.tint(0.06))
                                Text { id: qText; anchors.centerIn: parent; text: modelData.t; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: parent.cur }
                                MouseArea { id: qm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bc.setQuality(modelData.k) }
                            }
                        }
                    }
                }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: bc.camera
                text: "In Discord, Teams, Zoom oder OBS die Kamera „Creative Kamera“ wählen. Gerechnet wird nur, solange ein Programm sie benutzt."
                color: Theme.accent; font.family: Theme.fontFamily; font.pixelSize: 12
            }
        }
    }

    ImagePicker {
        id: imageDialog
        title: "Hintergrundbild wählen"
        acceptText: "Als Hintergrund nehmen"
        onAccepted: (url) => bc.setBackground(url.toString())
    }

    // ---- Bausteine ----------------------------------------------------------------------------------
    component Panel: Rectangle {
        id: panel
        property string icon
        property string title
        property bool on: false
        signal toggled(bool v)
        default property alias content: body.data
        radius: 18
        color: Theme.raised
        border.color: panel.on ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45) : Theme.hairline
        Row {
            x: 20; y: 18
            spacing: 10
            Rectangle {
                width: 32; height: 32; radius: 10
                color: panel.on ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22) : Theme.tint(0.06)
                SvgIcon { anchors.centerIn: parent; name: panel.icon; size: 16 }
            }
            Text { anchors.verticalCenter: parent.verticalCenter; text: panel.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 16; font.bold: true }
        }
        CSwitch {
            anchors.right: parent.right
            anchors.rightMargin: 20
            y: 24
            checked: panel.on
            label: panel.title + " an"
            onToggled: (v) => panel.toggled(v)
        }
        Column {
            id: body
            x: 20
            y: 66
            width: parent.width - 40
            spacing: 10
        }
    }
    component InfoRow: Item {
        property string label
        property string value
        width: parent ? parent.width : 300
        height: 22
        Text { text: parent.label; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
        Text {
            anchors.right: parent.right
            width: parent.width * 0.62
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideLeft
            text: parent.value
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 12
        }
    }

    Component.onDestruction: bc.setPreview(false)
}
