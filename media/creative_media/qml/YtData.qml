import QtQuick
import QtWebEngine

// Unsichtbare zweite Ansicht der offiziellen YouTube-Music-Seite (ohne Ton): Startseite, Charts und
// Suche werden hier geöffnet und die angezeigten Kacheln/Treffer ausgelesen, damit der Player sie als
// eigene Kacheln und Liste zeigen kann. Abgespielt wird nur in der Player-Ansicht.
WebEngineView {
    id: data

    audioMuted: true
    Component.onCompleted: url = ytmusic.lastBrowse || ytmusic.home
    backgroundColor: "#141a26"
    settings.playbackRequiresUserGesture: true
    settings.javascriptCanOpenWindows: false
    settings.localStorageEnabled: true

    property int tries: 0
    property string lastJson: ""

    readonly property string readJs: "(function(){" +
        "if(location.host.indexOf('consent.')===0||location.host.indexOf('accounts.')===0)return {consent:true};" +
        "function T(e,s){var x=s?e.querySelector(s):e;return x?(x.getAttribute('title')||x.textContent||'').replace(/\\s+/g,' ').trim():'';}" +
        "function V(u){try{return new URL(u).searchParams.get('v')||'';}catch(e){return '';}}" +
        "function I(e,v){var i=e.querySelector('img');var s=i?(i.currentSrc||i.src||''):'';" +
        "if((!s||s.indexOf('data:')===0)&&v)s='https://i.ytimg.com/vi/'+v+'/hqdefault.jpg';return s.indexOf('data:')===0?'':s;}" +
        "function row(it){var a=it.querySelector('a[href*=\"watch?v=\"]')||it.querySelector('a.yt-simple-endpoint[href]');" +
        "var u=a?a.href:'';var v=V(u);return {title:T(it,'.title-column .title')||T(it,'.title'),subtitle:T(it,'.secondary-flex-columns')," +
        "thumb:I(it,v),url:u,videoId:v};}" +
        "function tile(it){var a=it.querySelector('a.yt-simple-endpoint[href]');var u=a?a.href:'';var v=V(u);" +
        "return {title:T(it,'.title'),subtitle:T(it,'.subtitle'),thumb:I(it,v),url:u,videoId:v};}" +
        "var shelves=[];document.querySelectorAll('ytmusic-carousel-shelf-renderer,ytmusic-grid-renderer').forEach(function(s){" +
        "var t=T(s,'ytmusic-carousel-shelf-basic-header-renderer .title')||T(s,'#header .title')||T(s,'.title');var items=[];" +
        "s.querySelectorAll('ytmusic-two-row-item-renderer').forEach(function(it){items.push(tile(it));});" +
        "s.querySelectorAll('ytmusic-responsive-list-item-renderer').forEach(function(it){items.push(row(it));});" +
        "if(items.length)shelves.push({title:t,items:items});});" +
        "var results=[];var top=document.querySelector('ytmusic-card-shelf-renderer');" +
        "if(top){var a=top.querySelector('a[href*=\"watch?v=\"]')||top.querySelector('a.yt-simple-endpoint[href]');var u=a?a.href:'';" +
        "results.push({title:T(top,'.title'),subtitle:T(top,'.subtitle'),thumb:I(top,V(u)),url:u,videoId:V(u)});}" +
        "if(location.pathname.indexOf('/search')===0)document.querySelectorAll('ytmusic-responsive-list-item-renderer').forEach(function(it){var r=row(it);if(r.url)results.push(r);});" +
        // nach unten blättern, damit die Seite weitere Reihen und Bilder nachlädt
        "window.scrollBy(0,900);" +
        // Kachelreihen seitlich weiterblättern, damit auch die Bilder rechts nachgeladen werden
        "document.querySelectorAll('ytmusic-carousel-shelf-renderer #items').forEach(function(c){c.scrollLeft+=700;});" +
        "return {consent:false,shelves:shelves,results:results,search:location.pathname.indexOf('/search')===0};})()"

    function read() {
        data.runJavaScript(data.readJs, function (r) {
            if (!r)
                return
            ytmusic.setConsent(!!r.consent)
            if (r.consent) {
                reader.stop()
                return
            }
            const json = JSON.stringify(r.search ? r.results : r.shelves)
            if (r.search)
                ytmusic.receiveResults(r.results)
            else
                ytmusic.receiveShelves(r.shelves)
            // fertig, sobald sich nichts mehr ändert (oder nach ein paar Versuchen)
            const enough = r.search ? r.results.length > 3 || data.tries > 6 : true
            if ((json === data.lastJson && json.length > 2 && enough) || data.tries > 14)
                reader.stop()
            data.lastJson = json
        })
    }

    Timer {
        id: reader
        interval: 1200
        repeat: true
        onTriggered: { data.tries += 1; data.read() }
    }

    onLoadingChanged: (info) => {
        if (info.status === WebEngineView.LoadSucceededStatus) {
            data.tries = 0
            data.lastJson = ""
            reader.restart()
        }
    }

    Connections {
        target: ytmusic
        function onBrowse(u) {
            data.tries = 0
            data.lastJson = ""
            data.url = u
            reader.restart()
        }
    }
}
