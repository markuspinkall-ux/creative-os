'use strict';
// Prüfung ohne Menschen (CI): H.264-Video abspielen, Oberfläche bedienen, Fotos speichern.
//   electron app --creative-selftest=<ordner> --creative-video=<file:///…/h264.html> [--creative-online]
const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function waitLoad(wc, timeout = 20000) {
  return new Promise((resolve) => {
    if (!wc.isLoading()) { resolve(); return; }
    const t = setTimeout(resolve, timeout);
    wc.once('did-stop-loading', () => { clearTimeout(t); resolve(); });
  });
}

async function shot(win, dir, name) {
  const ui = await win.ui.webContents.capturePage();
  fs.writeFileSync(path.join(dir, `${name}-ui.png`), ui.toPNG());
  if (win.active) {
    const page = await win.active.wc.capturePage();
    fs.writeFileSync(path.join(dir, `${name}-seite.png`), page.toPNG());
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

async function run({ Win, store, START_URL, arg }) {
  const dir = arg('creative-selftest');
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
    const v = await win.active.wc.executeJavaScript(VIDEO_JS);
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
    await win.ui.webContents.executeJavaScript("document.getElementById('menu-btn').click()");
    await sleep(500);
    check('Menü öffnet sich', win.overlay === true);
    await shot(win, dir, '3-menue');
    await win.ui.webContents.executeJavaScript("document.getElementById('backdrop').dispatchEvent(new MouseEvent('mousedown'))");
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
    const audioIcons = await win.ui.webContents.executeJavaScript("[...document.querySelectorAll('.tab .audio')].filter((b) => b.offsetWidth > 0).length");
    check('Lautsprecher nur bei Ton', audioIcons <= 1);

    // Adressleiste: Suche vs. Adresse
    store.visit('https://www.twitch.tv/creativeos', 'Creative OS – Twitch');
    const sug = store.suggest('twi');
    check('Vorschläge aus dem Verlauf', sug.length > 0 && sug[0].url.includes('twitch'));

    // Seite durchsuchen
    win.activate(win.tabs.find((t) => t.url.includes('h264')) || win.tabs[1]);
    await sleep(300);

    if (process.argv.includes('--creative-online')) {
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
          result.online[name] = await t.wc.executeJavaScript(`(() => { const vs = [...document.querySelectorAll('video')];
            const v = vs.find((x) => x.currentTime > 0) || vs[0];
            return v ? { time: v.currentTime, width: v.videoWidth, height: v.videoHeight, paused: v.paused,
              frames: (v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().totalVideoFrames : 0),
              dropped: (v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().droppedVideoFrames : 0) } : { video: false }; })()`);
        } catch (e) { result.online[name] = { error: e.message }; }
        await shot(win, dir, `4-${name}`);
      }
    }
    result.ok = Object.values(result.checks).every(Boolean);
  } catch (e) {
    result.error = String(e && e.stack || e);
  }
  fs.writeFileSync(path.join(dir, 'ergebnis.json'), JSON.stringify(result, null, 2));
  for (const [k, v] of Object.entries(result.checks)) console.log(`${v ? 'ok  ' : 'FEHLER'} ${k}`);
  console.log(JSON.stringify({ video: result.video, online: result.online, error: result.error }, null, 1));
  console.log(result.ok ? 'Creative Browser: alle Prüfungen bestanden' : 'Creative Browser: Prüfung FEHLGESCHLAGEN');
  app.exit(result.ok ? 0 : 1);
}

module.exports = { run };
