import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtMultimedia
import Creative

// Creative Capture – zeigt Bild und Ton einer Capture-Karte (Konsole, Kamera, zweiter PC)
// möglichst verzögerungsarm an. Dazu: Vollbild, Bildschirmfoto und Aufnahme.
Window {
    id: win
    width: 1280
    height: 760
    minimumWidth: 720
    minimumHeight: 440
    visible: true
    title: cam.cameraDevice && hasVideo ? "Creative Capture – " + cam.cameraDevice.description : "Creative Capture"
    color: "black"

    readonly property bool hasVideo: devices.videoInputs.length > 0
    readonly property bool fullscreen: visibility === Window.FullScreen
    property bool barVisible: true
    property string lastFile: ""
    property string toastText: ""
    property var formats: []              // [{ text, fmt }]

    // ---- Geräte ------------------------------------------------------------------------
    MediaDevices { id: devices }

    function pickVideo() {
        const list = devices.videoInputs
        if (!list.length) return null
        const saved = capture.get("video")
        for (let i = 0; i < list.length; i++)
            if (list[i].id == saved) return list[i]
        // echte Capture-Karten vor den virtuellen Kameras
        for (let i = 0; i < list.length; i++) {
            const d = list[i].description
            if (d.indexOf("Creative Kamera") < 0 && d.indexOf("OBS") < 0 && d.indexOf("Virtuelle") < 0) return list[i]
        }
        return list[0]
    }

    function buildFormats(dev) {
        const seen = {}
        const out = []
        if (!dev) return out
        const fs = dev.videoFormats
        for (let i = 0; i < fs.length; i++) {
            const f = fs[i]
            const fps = Math.round(f.maxFrameRate)
            const key = f.resolution.width + "x" + f.resolution.height + "@" + fps
            if (seen[key]) continue
            seen[key] = true
            out.push({ text: f.resolution.width + " × " + f.resolution.height + "  ·  " + fps + " Bilder/s", key: key,
                       w: f.resolution.width, h: f.resolution.height, fps: fps, fmt: f })
        }
        out.sort((a, b) => (b.w * b.h - a.w * a.h) || (b.fps - a.fps))
        return out
    }

    function bestFormat(list) {
        const saved = capture.get("format")
        for (let i = 0; i < list.length; i++)
            if (list[i].key === saved) return i
        // am liebsten 1080p mit 60, sonst die größte Auflösung mit mindestens 30 Bildern/s
        for (let i = 0; i < list.length; i++)
            if (list[i].w === 1920 && list[i].h === 1080 && list[i].fps >= 50) return i
        for (let i = 0; i < list.length; i++)
            if (list[i].fps >= 30) return i
        return list.length ? 0 : -1
    }

    function pickAudio(videoName) {
        const list = devices.audioInputs
        const saved = capture.get("audio")
        if (saved === "none") return null
        for (let i = 0; i < list.length; i++)
            if (list[i].id == saved) return list[i]
        // Tonquelle der Capture-Karte am Namen erkennen – nie einfach das Mikrofon (Rückkopplung!)
        let best = null, score = 0
        for (let i = 0; i < list.length; i++) {
            const s = capture.matchScore(videoName, list[i].description)
            if (s > score) { score = s; best = list[i] }
        }
        return best
    }

    function applyDevice(dev) {
        if (!dev) return
        cam.cameraDevice = dev
        formats = buildFormats(dev)
        const fi = bestFormat(formats)
        formatBox.currentIndex = fi
        if (fi >= 0) cam.cameraFormat = formats[fi].fmt
        const a = pickAudio(dev.description)
        if (a) audioIn.device = a
        audioOn = a !== null
        cam.active = true
    }

    property bool audioOn: false

    Component.onCompleted: { if (!selftest) applyDevice(pickVideo()) }
    Connections {
        target: devices
        function onVideoInputsChanged() {
            // neu eingesteckt oder abgezogen
            if (win.indexOfDev(devices.videoInputs, cam.cameraDevice) < 0) applyDevice(pickVideo())
        }
    }

    CaptureSession {
        id: session
        camera: Camera {
            id: cam
            active: false
        }
        audioInput: win.audioOn ? audioIn : null
        audioOutput: win.audioOn ? audioOut : null
        videoOutput: video
        imageCapture: ImageCapture {
            id: shot
            onImageSaved: (id, path) => { win.lastFile = path; win.toast("Bildschirmfoto gespeichert") }
        }
        recorder: MediaRecorder {
            id: rec
            quality: MediaRecorder.HighQuality
            onRecorderStateChanged: if (recorderState === MediaRecorder.StoppedState && win.lastFile !== "") win.toast("Aufnahme gespeichert")
            onErrorOccurred: (err, text) => win.toast("Aufnahme nicht möglich: " + text)
        }
    }
    AudioInput { id: audioIn; volume: 1.0 }
    AudioOutput {
        id: audioOut
        volume: capture.get("volume") === undefined ? 1.0 : capture.get("volume")
        muted: capture.get("muted") === true
    }

    function indexOfDev(list, dev) {
        if (!dev) return -1
        for (let i = 0; i < list.length; i++)
            if (list[i].id == dev.id) return i
        return -1
    }

    function toast(t) { toastText = t; toastTimer.restart() }
    function showBar() { barVisible = true; hideTimer.restart() }
    function toggleFullscreen() { win.visibility = fullscreen ? Window.Windowed : Window.FullScreen }

    // ---- Bild ------------------------------------------------------------------------------
    VideoOutput {
        id: video
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectFit
    }

    // Kein Signal / keine Karte
    Column {
        visible: !win.hasVideo || cam.error !== Camera.NoError
        anchors.centerIn: parent
        spacing: 12
        width: Math.min(parent.width - 80, 520)
        SvgIcon { anchors.horizontalCenter: parent.horizontalCenter; name: "tv"; size: 48 }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: !win.hasVideo ? "Keine Capture-Karte gefunden" : "Die Capture-Karte meldet sich nicht"
            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.bold: true
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: !win.hasVideo
                  ? "Steck die Capture-Karte (z. B. HDMI-Grabber per USB) ein – sie erscheint hier automatisch. In einer VM muss sie unter „Geräte › USB“ durchgereicht werden."
                  : (cam.errorString || "Vielleicht benutzt gerade ein anderes Programm (OBS, Discord …) die Karte.")
            color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 13
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: win.barVisible ? Qt.ArrowCursor : Qt.BlankCursor
        onPositionChanged: win.showBar()
        onClicked: win.showBar()
        onDoubleClicked: win.toggleFullscreen()
    }

    Timer { id: hideTimer; interval: 2800; running: true; onTriggered: if (!barMouse.containsMouse && !formatBox.popup.visible && !videoBox.popup.visible && !audioBox.popup.visible) win.barVisible = false }
    Timer { id: toastTimer; interval: 2600; onTriggered: win.toastText = "" }

    Shortcut { sequences: ["F11", "F"]; onActivated: win.toggleFullscreen() }
    Shortcut { sequence: "Escape"; enabled: win.fullscreen; onActivated: win.visibility = Window.Windowed }
    Shortcut { sequence: "M"; onActivated: { audioOut.muted = !audioOut.muted; capture.set("muted", audioOut.muted) } }
    Shortcut { sequence: "Print"; onActivated: shot.captureToFile(capture.newFile("photo")) }

    // Aufnahme läuft: roter Punkt oben links
    Rectangle {
        visible: rec.recorderState === MediaRecorder.RecordingState
        x: 18; y: 18
        width: recLabel.implicitWidth + 36
        height: 30
        radius: 15
        color: Qt.rgba(0, 0, 0, 0.6)
        Rectangle { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 5; color: "#e5484d" }
        Text {
            id: recLabel
            x: 28
            anchors.verticalCenter: parent.verticalCenter
            text: "REC  " + Math.floor(rec.duration / 60000) + ":" + ("0" + Math.floor(rec.duration / 1000) % 60).slice(-2)
            color: "white"; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true
        }
    }

    // Kurze Meldung
    Rectangle {
        visible: win.toastText !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        y: 24
        width: toastLabel.implicitWidth + 40
        height: 38
        radius: 19
        color: Theme.raised
        border.color: Theme.hairline
        Text { id: toastLabel; anchors.centerIn: parent; text: win.toastText; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 13 }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: capture.showInFiles(win.lastFile) }
    }

    // ---- Bedienleiste (blendet sich aus) ----------------------------------------------------
    Rectangle {
        id: bar
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 18
        width: Math.min(parent.width - 36, barRow.implicitWidth + 28)
        height: 60
        radius: 20
        color: Theme.bar
        border.color: Theme.hairline
        opacity: win.barVisible ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }

        MouseArea { id: barMouse; anchors.fill: parent; hoverEnabled: true; onEntered: win.showBar() }

        Row {
            id: barRow
            anchors.centerIn: parent
            spacing: 8

            Dropdown {
                id: videoBox
                width: 230
                enabled: win.hasVideo
                model: devices.videoInputs.map(d => d.description)
                currentIndex: Math.max(0, win.indexOfDev(devices.videoInputs, cam.cameraDevice))
                onActivated: (i) => { const d = devices.videoInputs[i]; capture.set("video", d.id); capture.set("format", ""); win.applyDevice(d) }
                Accessible.name: "Capture-Karte"
            }
            Dropdown {
                id: formatBox
                width: 210
                enabled: win.formats.length > 0
                model: win.formats.map(f => f.text)
                onActivated: (i) => { cam.cameraFormat = win.formats[i].fmt; capture.set("format", win.formats[i].key) }
                Accessible.name: "Auflösung und Bildrate"
            }

            Rectangle { width: 1; height: 30; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }

            Dropdown {
                id: audioBox
                width: 200
                model: ["Ton aus"].concat(devices.audioInputs.map(d => d.description))
                currentIndex: win.audioOn ? Math.max(0, win.indexOfDev(devices.audioInputs, audioIn.device) + 1) : 0
                onActivated: (i) => {
                    if (i === 0) { win.audioOn = false; capture.set("audio", "none") }
                    else { audioIn.device = devices.audioInputs[i - 1]; win.audioOn = true; capture.set("audio", devices.audioInputs[i - 1].id) }
                }
                Accessible.name: "Tonquelle"
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 40; height: 40; iconSize: 18
                icon: audioOut.muted || !win.audioOn ? "volume-off" : "volume"
                label: audioOut.muted ? "Ton einschalten" : "Stumm"
                onClicked: { audioOut.muted = !audioOut.muted; capture.set("muted", audioOut.muted) }
            }
            CSlider {
                anchors.verticalCenter: parent.verticalCenter
                width: 110
                from: 0; to: 1; stepSize: 0.05
                value: audioOut.volume
                enabled: win.audioOn
                onMoved: { audioOut.volume = value; capture.set("volume", value) }
                Accessible.name: "Lautstärke"
            }

            Rectangle { width: 1; height: 30; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 40; height: 40; iconSize: 18
                icon: "screenshot"
                label: "Bildschirmfoto (Druck)"
                enabled: cam.active
                onClicked: shot.captureToFile(capture.newFile("photo"))
            }
            // Aufnahme
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 40; height: 40
                radius: Theme.radiusButton
                color: recMouse.containsMouse ? Theme.hover : "transparent"
                readonly property bool recording: rec.recorderState === MediaRecorder.RecordingState
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.recording ? 14 : 16
                    height: width
                    radius: parent.recording ? 3 : 8
                    color: "#e5484d"
                }
                MouseArea {
                    id: recMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (rec.recorderState === MediaRecorder.RecordingState) {
                            rec.stop()
                        } else {
                            const f = capture.newFile("video")
                            win.lastFile = f
                            rec.outputLocation = capture.fileUrl(f)
                            rec.record()
                        }
                    }
                }
                Accessible.role: Accessible.Button
                Accessible.name: parent.recording ? "Aufnahme beenden" : "Aufnahme starten"
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 40; height: 40; iconSize: 18
                icon: win.fullscreen ? "restore" : "fullscreen"
                label: win.fullscreen ? "Vollbild beenden" : "Vollbild (F11)"
                onClicked: win.toggleFullscreen()
            }
        }
    }

    // ---- Baustein: Auswahlliste im Creative-Look -------------------------------------------------
    component Dropdown: ComboBox {
        id: dd
        height: 40
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        font.family: Theme.fontFamily
        font.pixelSize: 13
        background: Rectangle { radius: 12; color: dd.hovered ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06) }
        contentItem: Text {
            leftPadding: 12
            rightPadding: 28
            text: dd.displayText
            color: dd.enabled ? Theme.text : Theme.textMuted
            font: dd.font
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        indicator: SvgIcon { x: dd.width - 24; anchors.verticalCenter: parent.verticalCenter; name: "chevron-down"; size: 12 }
        delegate: ItemDelegate {
            required property int index
            required property var modelData
            width: dd.popup.width
            height: 36
            highlighted: dd.highlightedIndex === index
            background: Rectangle { radius: 8; color: parent.highlighted ? Qt.rgba(1, 1, 1, 0.08) : "transparent" }
            contentItem: Text {
                text: modelData
                color: index === dd.currentIndex ? Theme.accent : Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
        }
        popup: Popup {
            y: -implicitHeight - 6
            width: Math.max(dd.width, 280)
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 360)
            padding: 6
            background: Rectangle { radius: 14; color: Theme.raised; border.color: Theme.hairline }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: dd.popup.visible ? dd.delegateModel : null
                currentIndex: dd.highlightedIndex
            }
        }
    }
}
