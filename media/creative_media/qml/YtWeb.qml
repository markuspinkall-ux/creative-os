import QtQuick
import QtWebEngine

// Die offizielle YouTube-Music-Webseite, eingebettet in den Creative Player.
// Anmeldung (z. B. YouTube Premium) bleibt gespeichert.
WebEngineView {
    id: web

    url: ytmusic.home
    backgroundColor: "#12151b"
    settings.playbackRequiresUserGesture: false
    settings.fullScreenSupportEnabled: true
    settings.localStorageEnabled: true
    settings.javascriptCanOpenWindows: false

    profile: WebEngineProfile {
        storageName: "creative-ytmusic"
        offTheRecord: false
        persistentCookiesPolicy: WebEngineProfile.ForcePersistentCookies
        httpCacheType: WebEngineProfile.DiskHttpCache
    }

    // Was läuft gerade? (Titel, Interpret, Bild – für Herz und Favoriten)
    readonly property string nowJs: "(function(){" +
        "var m=navigator.mediaSession&&navigator.mediaSession.metadata;" +
        "var v=document.querySelector('video');var id='';" +
        "try{id=new URL(location.href).searchParams.get('v')||'';}catch(e){}" +
        "if(!id){var a=document.querySelector('ytmusic-player-bar a.yt-simple-endpoint[href*=\"watch?v=\"]');" +
        "if(a){try{id=new URL(a.href).searchParams.get('v')||'';}catch(e){}}}" +
        "var art=(m&&m.artwork&&m.artwork.length)?m.artwork[m.artwork.length-1].src:'';" +
        "return {title:m?m.title:'',artist:m?m.artist:'',thumb:art,videoId:id,playing:!!(v&&!v.paused&&!v.ended)};})()"

    function command(c) {
        const js = {
            play: "document.querySelector('video')&&document.querySelector('video').play()",
            pause: "document.querySelector('video')&&document.querySelector('video').pause()",
            stop: "document.querySelector('video')&&document.querySelector('video').pause()",
            toggle: "(function(){var b=document.querySelector('#play-pause-button');if(b)b.click();})()",
            next: "(function(){var b=document.querySelector('.next-button');if(b)b.click();})()",
            prev: "(function(){var b=document.querySelector('.previous-button');if(b)b.click();})()"
        }[c]
        if (js)
            web.runJavaScript(js)
    }

    // Sprachassistent „spiel …“: erstes Suchergebnis im offiziellen Player starten
    property int autoTries: 0
    readonly property string firstResultJs: "(function(){" +
        "var a=document.querySelector('ytmusic-card-shelf-renderer a[href*=\"watch?v=\"]')||" +
        "document.querySelector('ytmusic-shelf-renderer a[href*=\"watch?v=\"]');" +
        "if(a){a.click();return true;}return false;})()"

    Timer {
        id: autoTimer
        interval: 1200
        repeat: true
        onTriggered: {
            web.autoTries += 1
            web.runJavaScript(web.firstResultJs, function (ok) { if (ok || web.autoTries > 8) autoTimer.stop() })
        }
    }

    onLoadingChanged: (info) => {
        if (info.status === WebEngineView.LoadSucceededStatus && ytmusic.takeAutoplay()) {
            web.autoTries = 0
            autoTimer.start()
        }
    }

    // Vollbild (z. B. Musikvideo) erlauben
    onFullScreenRequested: (request) => request.accept()

    Timer {
        interval: 2000
        repeat: true
        running: true
        onTriggered: web.runJavaScript(web.nowJs, function (r) { if (r) ytmusic.reportNow(r) })
    }

    Connections {
        target: ytmusic
        function onOpenUrl(u) { web.url = u }
        function onCommand(c) { web.command(c) }
    }
}
