import QtQuick
import QtWebEngine

// Die offizielle YouTube-Music-Webseite, eingebettet in den Creative Player.
// Anmeldung (z. B. YouTube Premium) bleibt gespeichert.
WebEngineView {
    id: web

    url: ytmusic.home
    backgroundColor: "#141a26"
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

    // Graphit-Blau für die offizielle Seite – nur Farben, Inhalte, Logo und Werbung bleiben unangetastet.
    // Wird beim Laden und danach alle 3 s geprüft (YouTube Music lädt Seiten ohne Neuladen nach).
    readonly property string themeCss:
        ":root,html,body,ytmusic-app{" +
        "--ytmusic-background:#141a26!important;" +
        "--ytmusic-general-background-A:#141a26!important;--ytmusic-general-background-B:#182031!important;" +
        "--ytmusic-general-background-C:#1b2334!important;--ytmusic-general-background-D:#222b3f!important;" +
        "--ytmusic-brand-background-solid:#171d2a!important;--ytmusic-brand-background-translucent:rgba(23,29,42,.94)!important;" +
        "--ytmusic-nav-bar:#171d2a!important;--ytmusic-player-bar-background:#171d2a!important;" +
        "--ytmusic-search-background:#222b3f!important;--ytmusic-color-black4:#222b3f!important;" +
        "--ytmusic-text-primary:#dce6ff!important;--ytmusic-text-secondary:rgba(220,230,255,.62)!important;" +
        "--yt-spec-base-background:#141a26!important;--yt-spec-raised-background:#1b2334!important;" +
        "--yt-spec-menu-background:#222b3f!important;--yt-spec-inverted-background:#dce6ff!important;" +
        "--yt-spec-general-background-a:#141a26!important;--yt-spec-general-background-b:#182031!important;" +
        "--yt-spec-general-background-c:#1b2334!important;--yt-spec-brand-background-solid:#171d2a!important;" +
        "--yt-spec-brand-background-primary:#171d2a!important;--yt-spec-brand-background-secondary:#1b2334!important;" +
        "--yt-spec-text-primary:#dce6ff!important;--yt-spec-text-secondary:rgba(220,230,255,.62)!important;" +
        "--yt-spec-10-percent-layer:rgba(143,179,255,.12)!important;--yt-spec-badge-chip-background:rgba(143,179,255,.14)!important;" +
        "--yt-spec-call-to-action:#8fb3ff!important;--yt-spec-themed-blue:#8fb3ff!important;" +
        "--paper-slider-active-color:#8fb3ff!important;--paper-slider-knob-color:#8fb3ff!important;}" +
        "html,body,ytmusic-app,ytmusic-app-layout,#layout,#content,ytmusic-browse-response,ytmusic-search-page," +
        "ytmusic-section-list-renderer,ytmusic-tabbed-search-results-renderer,ytmusic-tabbed-browse-renderer," +
        "ytmusic-player-page,#player-page,#main-panel,#side-panel,ytmusic-tab-renderer,#tab-renderer," +
        "ytmusic-two-column-browse-results-renderer{background-color:#141a26!important;}" +
        "ytmusic-nav-bar,#nav-bar-background,#nav-bar-divider,ytmusic-player-bar,#player-bar-background," +
        "ytmusic-guide-renderer,#guide-wrapper,#mini-guide-background,#guide-content,tp-yt-app-drawer #contentContainer," +
        "ytmusic-app-layout[player-page-open] #nav-bar-background{background:#171d2a!important;}" +
        "ytmusic-search-box #input-box,ytmusic-search-box .search-box{background:#222b3f!important;border-radius:10px!important;}" +
        "tp-yt-paper-listbox,ytmusic-menu-popup-renderer,ytd-multi-page-menu-renderer,tp-yt-iron-dropdown #contentWrapper>*{background:#222b3f!important;}" +
        "ytmusic-chip-cloud-chip-renderer:not([is-selected]) a,ytmusic-chip-cloud-chip-renderer:not([is-selected]) .gradient-box{background:rgba(143,179,255,.12)!important;}" +
        "ytmusic-player-bar #progress-bar #primaryProgress,ytmusic-player-bar #sliderKnobInner,#progress-bar #sliderKnob .slider-knob-inner{background:#8fb3ff!important;}" +
        "::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:rgba(143,179,255,.25);border-radius:5px}" +
        "::-webkit-scrollbar-track{background:transparent}"

    readonly property string themeJs: "(function(css){var s=document.getElementById('creative-theme');" +
        "if(!s){s=document.createElement('style');s.id='creative-theme';}" +
        "if(s.textContent!==css)s.textContent=css;" +
        "if(s.parentNode!==document.documentElement||document.documentElement.lastElementChild!==s)" +
        "document.documentElement.appendChild(s);})"

    function applyTheme() {
        web.runJavaScript(themeJs + "(" + JSON.stringify(themeCss) + ")")
    }

    Timer {
        interval: 3000
        repeat: true
        running: true
        onTriggered: web.applyTheme()
    }

    onLoadingChanged: (info) => {
        if (info.status === WebEngineView.LoadSucceededStatus)
            web.applyTheme()
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
