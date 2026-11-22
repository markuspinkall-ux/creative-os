'use strict';
// Prüfung ohne Menschen (CI): H.264-Video abspielen, Oberfläche bedienen, Fotos speichern.
//   electron app --creative-selftest=<ordner> --creative-video=<file:///…/h264.html> [--creative-online]
const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// Nichts darf die Prüfung aufhalten: jede Abfrage hat eine Frist
const within = (promise, ms, fallback) => Promise.race([promise, sleep(ms).then(() => fallback)]);

function waitLoad(wc, timeout = 20000) {
  return new Promise((resolve) => {
    if (!wc.isLoading()) { resolve(); return; }
    const t = setTimeout(resolve, timeout);
    wc.once('did-stop-loading', () => { clearTimeout(t); resolve(); });
  });
}

async function shot(win, dir, name) {
  const ui = await within(win.ui.webContents.capturePage(), 8000, null);
  if (ui) fs.writeFileSync(path.join(dir, `${name}-ui.png`), ui.toPNG());
  if (win.active) {
    const page = await within(win.active.wc.capturePage(), 8000, null);
    if (page) fs.writeFileSync(path.join(dir, `${name}-seite.png`), page.toPNG());
  }
  return { chromeH: win.chromeH, overlay: win.overlay };
}

const VIDEO_JS = `(() => new Promise((resolve) => {
  const v = document.querySelector('video');
  const out = {
    mseH264: MediaSource.isTypeSupported('video/mp4; codecs="avc1.64002A"'),
    mseH264Base: MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"'),
    mseAac: MediaSource.isTypeSupported('audio/mp4; codecs="mp4a.40.2"'),
    mseVp9: MediaSource.isTypeSupported('video/webm; codecs="vp9"'),
    mseAv1: MediaSource.isTypeSupported('video/mp4; codecs="av01.0.05M.08"'),
    canPlayH264: document.createElement('video').canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"'),
  };
  if (!v) { resolve(out); return; }
  setTimeout(() => {
    const q = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : {};
    Object.assign(out, { time: v.currentTime, width: v.videoWidth, height: v.videoHeight,
      error: v.error ? v.error.code : 0, frames: q.totalVideoFrames || 0, dropped: q.droppedVideoFrames || 0,
      paused: v.paused });
    resolve(out);
  }, 5000);
}))()`;

async function run({ Win, windows, store, START_URL, arg, setLook, lookFor, adblock, downloads = [], getPasswords = () => null }) {
  const dir = arg('creative-selftest');
  setTimeout(() => { console.log('Browser: Prüfung hängt – Abbruch'); app.exit(2); }, 240000).unref?.();
  fs.mkdirSync(dir, { recursive: true });
  const result = { ok: false, checks: {} };
  const check = (name, cond) => { result.checks[name] = !!cond; };
  try {
    const video = arg('creative-video');
    const win = new Win({ urls: [START_URL, video], active: 1 });
    win.win.setSize(1360, 860);
    await waitLoad(win.ui.webContents);
    await sleep(800);
    check('zwei Tabs', win.tabs.length === 2);
    check('Video-Tab aktiv', win.active === win.tabs[1]);
    await waitLoad(win.active.wc);
    const v = await within(win.active.wc.executeJavaScript(VIDEO_JS), 15000, {});
    result.video = v;
    check('H.264 per MSE (Twitch/YouTube)', v.mseH264 && v.mseH264Base);
    check('AAC per MSE', v.mseAac);
    check('H.264 abspielbar', v.canPlayH264 === 'probably');
    check('Testvideo läuft', v.time > 2 && v.width === 1280 && !v.error);
    check('Bilder werden flüssig dargestellt', v.frames > 60 && v.dropped / Math.max(1, v.frames) < 0.2);
    result.layout = await shot(win, dir, '1-video');

    // Startseite + Oberfläche
    win.activate(win.tabs[0]);
    await sleep(600);
    result.layout = await shot(win, dir, '2-startseite');
    check('Leiste hat Höhe', win.chromeH > 60 && win.chromeH < 160);

    // Menü öffnen (Schicht wird fensterhoch)
    await within(win.ui.webContents.executeJavaScript("document.getElementById('menu-btn').click()"), 5000);
    await sleep(500);
    check('Menü öffnet sich', win.overlay === true);
    await shot(win, dir, '3-menue');
    await within(win.ui.webContents.executeJavaScript("document.getElementById('backdrop').dispatchEvent(new MouseEvent('mousedown'))"), 5000);
    await sleep(300);
    check('Menü schließt sich', win.overlay === false);

    // Tabs: neu, schließen, wieder öffnen
    win.command('new-tab');
    await sleep(300);
    check('Neuer Tab', win.tabs.length === 3 && win.active.url.startsWith(START_URL) && win.active !== win.tabs[0]);
    win.closeTab(win.tabs.find((t) => t.url.includes('h264')));
    await sleep(200);
    check('Tab schließen', win.tabs.length === 2);
    win.reopen();
    await sleep(1500);
    check('Geschlossenen Tab wiederherstellen', win.tabs.length === 3 && win.tabs.some((t) => t.url.includes('h264')));
    const audioIcons = await within(win.ui.webContents.executeJavaScript("[...document.querySelectorAll('.tab .audio')].filter((b) => b.offsetWidth > 0).length"), 5000, 99);
    check('Lautsprecher nur bei Ton', audioIcons <= 1);

    // Adressleiste: Suche vs. Adresse
    store.visit('https://www.twitch.tv/creativeos', 'Gibeon OS – Twitch');
    const sug = store.suggest('twi');
    check('Vorschläge aus dem Verlauf', sug.length > 0 && sug[0].url.includes('twitch'));

    // Lautstärke-Verstärker am H.264-Testvideo (hat Ton)
    const vt = win.tabs.find((t) => t.url.includes('h264'));
    if (vt) {
      win.activate(vt);
      await sleep(400);
      const hooked = await within(win.setBoost(vt, 3), 5000, 0);
      await sleep(1200);
      const still = await within(vt.wc.executeJavaScript('(() => { const v = document.querySelector("video"); return { t: v.currentTime, p: v.paused }; })()'), 3000, {});
      check('Verstärker hängt sich ans Video', hooked >= 1 && vt.boost === 3);
      check('Video läuft mit Verstärker weiter', still.t > 0 && !still.p);
      await within(win.ui.webContents.executeJavaScript("document.getElementById('boost-btn').click()"), 3000);
      await sleep(500);
      await shot(win, dir, '10-verstaerker');
      await within(win.ui.webContents.executeJavaScript("document.getElementById('backdrop').dispatchEvent(new MouseEvent('mousedown'))"), 3000);

      // Tab in eigenes Fenster ziehen
      const before = windows.size;
      const nw = win.tearOff(vt);
      await sleep(800);
      check('Tab wandert in neues Fenster', windows.size === before + 1 && nw && nw.tabs[0] === vt && !win.tabs.includes(vt));
      const inNew = await within(vt.wc.executeJavaScript('document.querySelector("video") ? document.querySelector("video").currentTime : 0'), 3000, 0);
      check('Video läuft im neuen Fenster weiter', inNew > 0 && vt.win === nw);
      nw.win.close();
      await sleep(500);
    }

    // Beide Designs wie in Gibeon OS (Graphit ist Standard)
    win.activate(win.tabs[0]);
    win.command('navigate', 'creative://start/');
    await sleep(1200);
    const design = () => within(win.ui.webContents.executeJavaScript('document.body.dataset.design'), 3000, '');
    check('Graphit als Standard', (await design()) === 'graphit');
    await shot(win, dir, '5-graphit');
    setLook(lookFor('porzellan', 'blau'));
    await sleep(900);
    check('Porzellan wird übernommen', (await design()) === 'porzellan');
    await shot(win, dir, '6-porzellan');
    await within(win.ui.webContents.executeJavaScript("document.getElementById('menu-btn').click()"), 5000);
    await sleep(500);
    await shot(win, dir, '7-porzellan-menue');
    await within(win.ui.webContents.executeJavaScript("document.getElementById('backdrop').dispatchEvent(new MouseEvent('mousedown'))"), 5000);
    setLook(lookFor('graphit', 'orange'));
    await sleep(900);
    const acc = await within(win.ui.webContents.executeJavaScript("getComputedStyle(document.body).getPropertyValue('--accent').trim()"), 3000, '');
    check('Akzentfarbe wird übernommen', acc === '#ffb07a');
    await shot(win, dir, '8-graphit-orange');
    setLook(lookFor('graphit', 'blau'));
    await sleep(300);

    // Werbeblocker mit einer Testseite auf einem eigenen kleinen Webserver
    if (process.argv.includes('--creative-online')) {
      const ok = await within(adblock.ready, 60000, false);
      check('Werbeblocker geladen', ok === true);
      const http = require('http');
      const page = `<!doctype html><title>Werbetest</title><body>
        <p id="inhalt">Inhalt</p>
        <ins class="adsbygoogle" data-ad-client="ca-pub-1234" data-ad-slot="5678" style="display:block;width:300px;height:250px;background:red">Werbung</ins>
        <div id="ad-banner" data-ad-cls="banner" style="width:300px;height:90px;background:red">Werbung</div>
        <script src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" onerror="window.__blocked=1" onload="window.__loaded=1"></script>
        <video id="clip" src="/clip.webm" preload="auto" muted></video>
        </body>`;
      const server = http.createServer((q, r) => {
        if (q.url.startsWith('/clip')) { r.writeHead(200, { 'content-type': 'video/webm' }); r.end(Buffer.alloc(2048)); return; }
        r.writeHead(200, { 'content-type': 'text/html' }); r.end(page);
      });
      await new Promise((r) => server.listen(0, '127.0.0.1', r));
      // Echter Hostname (über /etc/hosts): Ghostery wendet Ausblend-Regeln nicht auf IP-Adressen an
      const host = process.env.CREATIVE_WERBETEST_HOST || '127.0.0.1';
      const url = `http://${host}:${server.address().port}/`;
      const t = win.addTab(url);
      await waitLoad(t.wc, 20000);
      await sleep(2500);
      const res = await within(t.wc.executeJavaScript(`({ blocked: window.__blocked || 0, loaded: window.__loaded || 0,
        ins: document.querySelector('ins.adsbygoogle').offsetHeight, banner: document.getElementById('ad-banner').offsetHeight,
        inhalt: document.getElementById('inhalt').offsetHeight })`), 5000, {});
      result.adblock = { ...res, count: adblock.count(t.wc.id) };
      check('Werbeskript blockiert', res.blocked === 1 && !res.loaded);
      check('Werbeflächen ausgeblendet', res.ins === 0 && res.banner === 0 && res.inhalt > 0);
      check('Zähler zählt', adblock.count(t.wc.id) >= 1);
      // Videodaten gehen ohne Filterprüfung durch (schnellerer Start bei YouTube & Co.)
      const { isMediaFast } = require('./adblock');
      check('Videodaten ungeprüft durchgelassen', adblock.fastPassed >= 1
        && isMediaFast('https://rr1---sn-abc.googlevideo.com/videoplayback?id=1')
        && !isMediaFast('https://www.youtube.com/pagead/adview?ai=1'));
      result.adblockSchnell = adblock.fastPassed;
      await shot(win, dir, '9-werbeblocker');
      await within(win.ui.webContents.executeJavaScript("document.getElementById('shield').click()"), 5000);
      await sleep(500);
      await shot(win, dir, '9-werbeblocker-panel');
      await within(win.ui.webContents.executeJavaScript("document.getElementById('backdrop').dispatchEvent(new MouseEvent('mousedown'))"), 5000);
      win.command('adblock-site', true);                  // auf dieser Seite erlauben
      await sleep(400);
      await waitLoad(t.wc, 20000);
      await sleep(2500);
      const res2 = await within(t.wc.executeJavaScript('({ blocked: window.__blocked || 0, loaded: window.__loaded || 0 })'), 5000, {});
      result.adblockErlaubt = res2;
      check('Seite erlauben lässt Werbung durch', res2.loaded === 1 && !res2.blocked);
      win.command('adblock-site', false);
      // Videoportale (YouTube, Twitch): Blocker von Haus aus aus, im Schild wieder einschaltbar
      const { isVideoPortal } = require('./adblock');
      check('Videoportale erkannt', isVideoPortal('youtube.com') && isVideoPortal('m.youtube.com') && isVideoPortal('youtu.be')
        && isVideoPortal('twitch.tv') && isVideoPortal('player.twitch.tv') && !isVideoPortal('example.org') && !isVideoPortal('notyoutube.com'));
      check('Blocker auf YouTube und Twitch aus', adblock.isAllowedHost('www.youtube.com'.replace(/^www\./, '')) && adblock.isAllowedHost('twitch.tv'));
      check('Allgemeine Seiten weiter geblockt', !adblock.isAllowedHost('example.org') && !adblock.isAllowedHost(host));
      adblock.setAllowed('youtube.com', false);         // im Schild auf YouTube wieder einschalten
      check('Auf YouTube wieder einschaltbar', !adblock.isAllowedHost('youtube.com') && adblock.isAllowedHost('twitch.tv'));
      adblock.setAllowed('youtube.com', true);
      check('und wieder aus', adblock.isAllowedHost('youtube.com'));
      // Ausblenden/Seiten-Skripte werden auf Videoportalen nicht eingespielt
      let injected = 0;
      const fakeEvent = (u) => ({ sender: { getURL: () => u, insertCSS: () => { injected += 1; }, executeJavaScript: () => { injected += 1; } }, frameId: 1, processId: 1 });
      await adblock.blocker.onInjectCosmeticFilters(fakeEvent('https://www.youtube.com/watch?v=x'), 'https://www.youtube.com/watch?v=x');
      await adblock.blocker.onInjectCosmeticFilters(fakeEvent('https://example.org/'), 'https://www.youtube-nocookie.com/embed/x');
      check('Keine Seiten-Skripte auf YouTube (auch eingebettet)', injected === 0);
      // Videowerbung (Versuch): nur auf YouTube/Twitch, abschaltbar, folgt dem Hauptschalter
      check('Videowerbung-Skript nur auf Videoportalen', adblock.videoAdFor('www.youtube.com') && adblock.videoAdFor('twitch.tv')
        && !adblock.videoAdFor('example.org'));
      adblock.setVideoAd(false);
      check('Videowerbung-Skript abschaltbar', !adblock.videoAdFor('youtube.com'));
      adblock.setVideoAd(true);
      server.close();
      win.closeTab(t);

      // Echte Seiten – nur zur Info, nicht entscheidend (CI-Netz, Cookie-Banner …)
      result.online = {};
      for (const [name, url, wait] of [
        ['youtube', 'https://www.youtube.com/watch?v=aqz-KE-bpKQ', 15000],
        ['twitch', 'https://www.twitch.tv/', 20000],
      ]) {
        const t = win.addTab(url);
        await waitLoad(t.wc, 30000);
        await sleep(wait);
        try {
          result.online[name] = await within(t.wc.executeJavaScript(`(() => { const vs = [...document.querySelectorAll('video')];
            const v = vs.find((x) => x.currentTime > 0) || vs[0];
            return v ? { time: v.currentTime, width: v.videoWidth, height: v.videoHeight, paused: v.paused,
              frames: (v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().totalVideoFrames : 0),
              dropped: (v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().droppedVideoFrames : 0),
              host: location.hostname,
              hooked: !!(Object.getOwnPropertyDescriptor(window, 'ytInitialPlayerResponse') || {}).get,
              adData: !!(window.ytInitialPlayerResponse && (ytInitialPlayerResponse.adPlacements || ytInitialPlayerResponse.playerAds)),
              adShowing: !!document.querySelector('.ad-showing') } : { video: false, host: location.hostname,
              hooked: !!(Object.getOwnPropertyDescriptor(window, 'ytInitialPlayerResponse') || {}).get }; })()`), 10000, { timeout: true });
          if (name === 'youtube' && /youtube\.com$/.test(result.online[name].host || '')) {
            check('Videowerbung-Skript läuft früh auf YouTube', result.online[name].hooked === true);
            check('Keine Werbedaten im YouTube-Player', !result.online[name].adData);
          }
        } catch (e) { result.online[name] = { error: e.message }; }
        await shot(win, dir, `4-${name}`);
      }
    }
    // Downloads: so wie Webseiten Dateien anbieten (Link mit download, neues Fenster, Blob)
    {
      const html = `<!doctype html><body>
        <a id="d1" download="probe-link.txt" href="data:text/plain,eins">Link</a>
        <a id="d2" download="probe-fenster.txt" target="_blank" href="data:text/plain,zwei">Fenster</a>
        <button id="d3">Blob</button>
        <script>document.getElementById('d3').onclick = () => { const a = document.createElement('a');
          a.href = URL.createObjectURL(new Blob(['drei'], { type: 'text/plain' })); a.download = 'probe-blob.txt';
          a.target = '_blank'; document.body.appendChild(a); a.click(); };</script>`;
      const t = win.addTab('data:text/html;charset=utf-8,' + encodeURIComponent(html));
      await waitLoad(t.wc);
      await sleep(500);
      for (const id of ['d1', 'd2', 'd3']) {
        await within(t.wc.executeJavaScript(`document.getElementById('${id}').click()`, true), 3000, null);
        await sleep(1500);
      }
      await sleep(2000);
      const names = downloads.map((d) => d.name);
      result.downloads = names;
      check('Download per Link', names.some((n) => n.startsWith('probe-link')));
      check('Download per Link in neuem Fenster', names.some((n) => n.startsWith('probe-fenster')));
      check('Download per Blob', names.some((n) => n.startsWith('probe-blob')));
    }
    // Web-App (wie Claude): Datei per window.open(blob:) muss in der App heruntergeladen werden
    {
      const page = path.join(dir, 'webapp-download.html');
      fs.writeFileSync(page, `<!doctype html><body><button id="d4">Datei</button>
        <script>document.getElementById('d4').onclick = () => {
          window.open(URL.createObjectURL(new Blob(['vier'], { type: 'application/gzip' })), '_blank'); };</script>`);
      const vorher = downloads.length;
      const appWin = new Win({ urls: [require('url').pathToFileURL(page).href], appMode: true });
      await waitLoad(appWin.ui.webContents);
      await sleep(800);
      if (appWin.active) await waitLoad(appWin.active.wc);
      await sleep(500);
      if (appWin.active) await within(appWin.active.wc.executeJavaScript(`document.getElementById('d4').click()`, true), 3000, null);
      await sleep(3000);
      result.appDownloads = downloads.slice(0, downloads.length - vorher).map((d) => d.name);
      check('Download aus einer Web-App (blob, neues Fenster)', downloads.length > vorher);
      try { appWin.win.close(); } catch (_) { /* egal */ }
    }
    await neueFunktionen({ Win, store, check, result, dir, getPasswords });
    result.ok = Object.values(result.checks).every(Boolean);
  } catch (e) {
    result.error = String(e && e.stack || e);
  }
  fs.writeFileSync(path.join(dir, 'ergebnis.json'), JSON.stringify(result, null, 2));
  for (const [k, v] of Object.entries(result.checks)) console.log(`${v ? 'ok  ' : 'FEHLER'} ${k}`);
  console.log(JSON.stringify({ video: result.video, online: result.online, downloads: result.downloads, appDownloads: result.appDownloads, error: result.error }, null, 1));
  console.log(result.ok ? 'Browser: alle Prüfungen bestanden' : 'Browser: Prüfung FEHLGESCHLAGEN');
  app.exit(result.ok ? 0 : 1);
}

// ---- Neue Browser-Funktionen (Nov. 2026) --------------------------------------------------------
async function neueFunktionen({ Win, store, check, result, dir, getPasswords }) {
  const http = require('http');
  const { pathToFileURL } = require('url');
  const pages = {
    '/artikel': `<!doctype html><html><head><title>Ein langer Artikel</title></head><body style="background:#fff;color:#111">
      <nav>Menü · Start · Kontakt</nav><article><h1>Ein langer Artikel</h1>${'<p>Gibeon OS ist ein Betriebssystem für Kreative. Dieser Absatz ist lang genug, damit die Leseansicht ihn als Inhalt erkennt und nicht als Navigation. </p>'.repeat(12)}</article>
      <footer>Impressum</footer></body></html>`,
    '/lang': `<!doctype html><html><head><title>Lange Seite</title></head><body style="margin:0;background:#fff">
      <div style="height:3200px;background:linear-gradient(#fff,#f2c)">oben</div><div>unten</div></body></html>`,
    '/anmelden': `<!doctype html><html><head><title>Anmelden</title></head><body style="background:#fff">
      <form id="f" onsubmit="event.preventDefault(); document.title='abgeschickt'">
      <input id="u" type="text" autocomplete="username"><input id="p" type="password"><button>Anmelden</button></form></body></html>`,
  };
  const server = http.createServer((req, res) => {
    const html = pages[req.url.split('?')[0]];
    res.writeHead(html ? 200 : 404, { 'content-type': 'text/html; charset=utf-8' });
    res.end(html || 'nicht da');
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const w = new Win({ urls: [`${base}/artikel`] });
  w.win.setSize(1360, 860);
  try {
    await waitLoad(w.ui.webContents);
    await sleep(600);
    await waitLoad(w.active.wc);
    await sleep(800);

    // Leseansicht
    const vorher = w.tabs.length;
    await w.reader(w.active);
    await sleep(300);
    if (w.active) await waitLoad(w.active.wc);
    await sleep(500);
    const lesen = w.active && w.active.url.startsWith('creative://lesen/');
    const lesenText = lesen ? await within(w.active.wc.executeJavaScript('document.body.innerText'), 3000, '') : '';
    check('Leseansicht öffnet sich', lesen && w.tabs.length === vorher + 1);
    check('Leseansicht ohne Menü/Fußzeile', /Gibeon OS ist ein Betriebssystem/.test(lesenText) && !/Impressum/.test(lesenText));
    await shot(w, dir, '11-leseansicht');

    // Dunkelmodus für helle Seiten
    store.settings.darkPages = true;
    w.addTab(`${base}/artikel?dunkel`);
    await waitLoad(w.active.wc);
    await sleep(900);
    const filter = await within(w.active.wc.executeJavaScript('getComputedStyle(document.documentElement).filter'), 3000, '');
    result.darkFilter = filter;
    check('Dunkelmodus auf heller Seite', /invert/.test(filter));
    await shot(w, dir, '12-dunkelmodus');
    store.settings.darkPages = false;
    await w.applyDark(w.active);
    await sleep(200);
    const filterAus = await within(w.active.wc.executeJavaScript('getComputedStyle(document.documentElement).filter'), 3000, '');
    check('Dunkelmodus wieder aus', !/invert/.test(filterAus));

    // Ganze Seite als Bild
    w.addTab(`${base}/lang`);
    await waitLoad(w.active.wc);
    await sleep(600);
    const file = await w.fullShot(w.active);
    let hoehe = 0;
    try {
      const buf = fs.readFileSync(file);
      hoehe = buf.readUInt32BE(20);
      fs.copyFileSync(file, path.join(dir, '13-ganze-seite.png'));
    } catch (_) { /* nicht gespeichert */ }
    result.fullShotHeight = hoehe;
    check('Ganze Seite als Bild (länger als das Fenster)', hoehe >= 3000);

    // Tabs schlafen legen und wecken
    const hinten = w.addTab(`${base}/artikel?schlaf`, { background: true });
    await waitLoad(hinten.wc);
    await sleep(300);
    const alt = hinten.wc;
    const schlaeft = w.sleepTab(hinten);
    await sleep(300);
    check('Tab schläft (Speicher frei)', schlaeft && hinten.sleeping && alt.isDestroyed());
    w.activate(hinten);
    await waitLoad(hinten.wc);
    await sleep(400);
    check('Schlafender Tab wacht auf', !hinten.sleeping && !hinten.wc.isDestroyed() && /Ein langer Artikel/.test(hinten.wc.getTitle()));

    // Video erkannt → Bild-im-Bild-Knopf
    const video = arg2('creative-video');
    if (video) {
      w.addTab(video);
      await waitLoad(w.active.wc);
      await sleep(1500);
      check('Video erkannt (Bild im Bild)', w.active.hasVideo);
      result.pip = await within(w.pip(w.active), 4000, 'zeit');
    }

    // Lesezeichen-Ordner
    store.toggleBookmark(`${base}/artikel`, 'Artikel');
    store.setBookmarkFolder(`${base}/artikel`, 'Test-Ordner');
    w.pushState();
    await sleep(400);
    const ordner = await within(w.ui.webContents.executeJavaScript(
      `[...document.querySelectorAll('.bm.folder')].map((e) => e.textContent.trim())`), 3000, []);
    check('Lesezeichen-Ordner in der Leiste', ordner.includes('Test-Ordner'));
    await w.ui.webContents.executeJavaScript(`document.querySelector('.bm.folder').click()`);
    await sleep(400);
    await shot(w, dir, '14-ordner');
    w.ui.webContents.send('close-overlays');
    await sleep(200);

    // Passwort speichern und wieder ausfüllen
    const pw = getPasswords();
    result.passwordsAvailable = pw ? pw.available() : null;
    if (pw && pw.available()) {
      w.addTab(`${base}/anmelden`);
      await waitLoad(w.active.wc);
      await sleep(700);
      await w.active.wc.executeJavaScript(`(() => {
        const set = (el, v) => { el.focus(); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
        set(document.getElementById('u'), 'markus'); set(document.getElementById('p'), 'geheim123');
        document.querySelector('button').click(); })()`, true);
      await sleep(800);
      const frage = w.pwPrompts && [...w.pwPrompts.entries()].find(([, v]) => v.user === 'markus');
      check('Passwort: Browser fragt nach dem Anmelden', !!frage);
      await shot(w, dir, '15-passwort-frage');
      if (frage) w.answerPassword(frage[0], 'save');
      w.addTab(`${base}/anmelden?neu`);
      await waitLoad(w.active.wc);
      await sleep(1500);
      const felder = await within(w.active.wc.executeJavaScript(
        `[document.getElementById('u').value, document.getElementById('p').value]`), 3000, []);
      check('Passwort wird ausgefüllt', felder[0] === 'markus' && felder[1] === 'geheim123');
      pw.remove(`${base}`, 'markus');
    } else {
      console.log('Browser: kein Schlüsselbund im Test – Passwortprüfung übersprungen');
    }

    // SponsorBlock-Skript lässt sich übersetzen
    const tools = require('./page-tools');
    try { new Function(tools.sponsorScript('abc', [{ segment: [1, 2], category: 'sponsor' }])); check('SponsorBlock-Skript', true); }
    catch (_) { check('SponsorBlock-Skript', false); }
    check('Übersetzen-Adresse', /translate/.test(tools.translatePageUrl('https://example.org/x')));
  } catch (e) {
    result.neuFehler = String(e && e.stack || e);
    check('neue Funktionen ohne Fehler', false);
  } finally {
    try { w.win.close(); } catch (_) { /* egal */ }
    server.close();
  }
}
const arg2 = (name) => { const a = process.argv.find((x) => x.startsWith(`--${name}=`)); return a ? a.slice(name.length + 3) : null; };

module.exports = { run };
