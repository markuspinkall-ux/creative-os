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
    color: hasVideo && cam.active && cam.error === Camera.NoError ? "black" : Theme.surface

    // Nur echte Capture-Karten – virtuelle Kameras (Creative Kamera, OBS) gehören nicht hierher
    readonly property var cards: devices.videoInputs.filter(d => d.description.indexOf("Creative Kamera") < 0
                                     && d.description.indexOf("OBS") < 0 && d.description.indexOf("Virtuelle") < 0
                                     && d.description.indexOf("Dummy") < 0 && d.description.indexOf("v4l2loopback") < 0)
    readonly property bool hasVideo: cards.length > 0
    readonly property bool fullscreen: visibility === Window.FullScreen
    property bool barVisible: true
    property string lastFile: ""
    property string toastText: ""
    property var formats: []              // [{ text, fmt }]

    // ---- Geräte ------------------------------------------------------------------------
    MediaDevices { id: devices }

    function pickVideo() {
        const list = win.cards
        if (!list.length) return null
        const saved = capture.get("video")
        for (let i = 0; i < list.length; i++)
            if (capture.deviceKey(list[i].id) === saved) return list[i]
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

    function pickAudio(dev) {
        const list = devices.audioInputs
        const videoId = capture.deviceKey(dev.id)
        const saved = capture.savedAudio(videoId)
        if (saved === "none") return null
        if (saved) {
            for (let i = 0; i < list.length; i++)
                if (capture.deviceKey(list[i].id) === saved) return list[i]
            return null // selected source disconnected: never substitute a camera microphone
        }
        const match = capture.matchedAudio(videoId, list.map(d => ({id: capture.deviceKey(d.id)})))
        for (let i = 0; i < list.length; i++)
            if (match && capture.deviceKey(list[i].id) === match) return list[i]
        return null
    }

    function applyAudio(dev) {
        const a = dev ? pickAudio(dev) : null
        audioOn = false
        if (a) { audioIn.device = a; audioOn = true }
        updateChannelSource()
    }

    function applyDevice(dev) {
        if (!dev) return
        cam.cameraDevice = dev
        formats = buildFormats(dev)
        const fi = bestFormat(formats)
        formatBox.currentIndex = fi
        if (fi >= 0) cam.cameraFormat = formats[fi].fmt
        applyAudio(dev)
        if (!audioOn && capture.savedAudio(capture.deviceKey(dev.id)) !== "none")
            toast("Bitte die HDMI-Tonquelle unter Tonquelle auswählen")
        cam.active = true
    }

    property bool audioOn: false
    property string monitorSource: ""
    property int channelCount: 0
    property int monitorChannel: 0

    function updateChannelSource() {
        monitorSource = audioOn ? capture.deviceKey(audioIn.device.id) : ""
        channelCount = monitorSource ? capture.channelCount(monitorSource) : 0
        const saved = capture.savedChannel(monitorSource)
        monitorChannel = saved <= channelCount ? saved : 0
        syncMonitor()
    }

    function syncMonitor() {
        if (!selftest && audioOn && monitorChannel > 0 && !audioOut.muted)
            capture.playChannel(monitorSource, channelCount, monitorChannel, audioOut.volume)
        else
            capture.stopMonitor()
    }

    Timer { id: monitorVolume; interval: 180; onTriggered: win.syncMonitor() }
    Connections {
        target: capture
        function onToast(message) { win.toast(message) }
    }

    Component.onCompleted: { if (!selftest) applyDevice(pickVideo()) }
    Connections {
        target: devices
        function onAudioInputsChanged() { win.applyAudio(win.hasVideo ? cam.cameraDevice : null) }
        function onVideoInputsChanged() {
            // neu eingesteckt oder abgezogen
            if (win.indexOfDev(win.cards, cam.cameraDevice) < 0) {
                cam.active = false
                const d = pickVideo()
                if (d) applyDevice(d)
                else applyAudio(null)
            }
        }
    }

    CaptureSession {
        id: session
        camera: Camera {
            id: cam
            active: false
        }
        audioInput: win.audioOn ? audioIn : null
        audioOutput: win.audioOn && win.monitorChannel === 0 ? audioOut : null
        videoOutput: video
        imageCapture: ImageCapture {
            id: shot
            onImageSaved: (id, path) => { win.lastFile = path; win.toast("Bildschirmfoto gespeichert") }
        }
        recorder: MediaRecorder {
            id: rec
            quality: MediaRecorder.NormalQuality
            videoFrameRate: cam.cameraFormat.maxFrameRate
            mediaFormat {
                fileFormat: MediaFormat.MPEG4
                videoCodec: MediaFormat.VideoCodec.H264
            }
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

    Timer { id: hideTimer; interval: 2800; running: true; onTriggered: if (win.hasVideo && !barMouse.containsMouse && !formatBox.popup.visible && !videoBox.popup.visible && !audioBox.popup.visible && !channelBox.popup.visible) win.barVisible = false }
    Timer { id: toastTimer; interval: 2600; onTriggered: win.toastText = "" }

    Shortcut { sequences: ["F11", "F"]; onActivated: win.toggleFullscreen() }
    Shortcut { sequence: "Escape"; enabled: win.fullscreen; onActivated: win.visibility = Window.Windowed }
    Shortcut { sequence: "M"; onActivated: { audioOut.muted = !audioOut.muted; capture.set("muted", audioOut.muted); win.syncMonitor() } }
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
            readonly property real selectorWidth: Math.max(56, (win.width - (channelBox.visible ? 550 : 430)) / 3)
            anchors.centerIn: parent
            spacing: 8

            Dropdown {
                id: videoBox
                width: Math.min(230, barRow.selectorWidth)
                placeholder: "Keine Capture-Karte"
                enabled: win.hasVideo
                model: win.cards.map(d => d.description)
                currentIndex: Math.max(0, win.indexOfDev(win.cards, cam.cameraDevice))
                onActivated: (i) => { const d = win.cards[i]; capture.set("video", capture.deviceKey(d.id)); capture.set("format", ""); win.applyDevice(d) }
                Accessible.name: "Capture-Karte"
            }
            Dropdown {
                id: formatBox
                width: Math.min(210, barRow.selectorWidth)
                placeholder: "Auflösung"
                enabled: win.formats.length > 0
                model: win.formats.map(f => f.text)
                onActivated: (i) => { cam.cameraFormat = win.formats[i].fmt; capture.set("format", win.formats[i].key) }
                Accessible.name: "Auflösung und Bildrate"
            }

            Rectangle { width: 1; height: 30; anchors.verticalCenter: parent.verticalCenter; color: Theme.hairline }

            Dropdown {
                id: audioBox
                width: Math.min(200, barRow.selectorWidth)
                model: ["Ton aus / Quelle wählen"].concat(devices.audioInputs.map(d => d.description))
                currentIndex: win.audioOn ? Math.max(0, win.indexOfDev(devices.audioInputs, audioIn.device) + 1) : 0
                onActivated: (i) => {
                    if (i === 0) { win.audioOn = false; capture.saveAudio(capture.deviceKey(cam.cameraDevice.id), "none") }
                    else { audioIn.device = devices.audioInputs[i - 1]; win.audioOn = true; capture.saveAudio(capture.deviceKey(cam.cameraDevice.id), capture.deviceKey(devices.audioInputs[i - 1].id)) }
                    win.updateChannelSource()
                }
                Accessible.name: "Tonquelle"
            }
            Dropdown {
                id: channelBox
                width: 112
                visible: win.audioOn && win.channelCount > 1
                model: ["Alle Kanäle"].concat(Array.from({ length: win.channelCount }, (_, i) => "Kanal " + (i + 1)))
                currentIndex: win.monitorChannel
                onActivated: (i) => {
                    win.monitorChannel = i
                    capture.saveChannel(win.monitorSource, i)
                    win.syncMonitor()
                }
                Accessible.name: "Wiedergabekanal"
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                width: 40; height: 40; iconSize: 18
                icon: audioOut.muted || !win.audioOn ? "volume-off" : "volume"
                label: audioOut.muted ? "Ton einschalten" : "Stumm"
                onClicked: { audioOut.muted = !audioOut.muted; capture.set("muted", audioOut.muted); win.syncMonitor() }
            }
            CSlider {
                anchors.verticalCenter: parent.verticalCenter
                width: 110
                from: 0; to: 1; stepSize: 0.05
                value: audioOut.volume
                enabled: win.audioOn
                onMoved: { audioOut.volume = value; capture.set("volume", value); if (win.monitorChannel > 0) monitorVolume.restart() }
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
        property string placeholder: ""
        height: 40
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        font.family: Theme.fontFamily
        font.pixelSize: 13
        background: Rectangle { radius: 12; color: dd.hovered ? Theme.tint(0.1) : Theme.tint(0.06) }
        contentItem: Text {
            leftPadding: 12
            rightPadding: 28
            text: dd.count > 0 ? dd.displayText : dd.placeholder
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
            background: Rectangle { radius: 8; color: parent.highlighted ? Theme.tint(0.08) : "transparent" }
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
