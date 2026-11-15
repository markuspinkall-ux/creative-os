'use strict';
// Selbsttest für Creative WhatsApp (CI): creative-whatsapp --creative-selftest=<ordner für Bilder>
const fs = require('fs');
const path = require('path');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function within(ms, promise, what) {
  return Promise.race([promise, sleep(ms).then(() => { throw new Error(`Zeitüberschreitung: ${what}`); })]);
}
async function until(fn, ms, what) {
  const end = Date.now() + ms;
  for (;;) {
    try { if (await fn()) return; } catch (_) { /* weiter versuchen */ }
    if (Date.now() > end) throw new Error(`Zeitüberschreitung: ${what}`);
    await sleep(300);
  }
}

async function run(ctx) {
  const { app, createWindow, getWin, openSettings, getSettingsWin, setSettings, getSettings, inQuietTimes, getUnread, autostartFile } = ctx;
  const out = (process.argv.find((a) => a.startsWith('--creative-selftest=')) || '').split('=').slice(1).join('=') || '/tmp';
  const ok = [];
  const check = (cond, what) => { if (!cond) throw new Error(`FEHLER: ${what}`); ok.push(what); console.log('✓', what); };
  setTimeout(() => { console.error('Selbsttest hängt – Abbruch'); app.exit(3); }, 150000).unref();
  try {
    // eigene App-Kennung (Wayland app_id), damit die Taskleiste WhatsApp nicht zum Browser stapelt
    check(process.env.CHROME_DESKTOP === 'creative-whatsapp.desktop', `eigene App-Kennung (${process.env.CHROME_DESKTOP})`);
    // Nicht-stören-Zeiten
    const at = (h, m) => { const d = new Date(2026, 10, 15, h, m); return d; };
    const night = { dndTimes: true, dndFrom: '22:00', dndTo: '07:00' };
    check(inQuietTimes(night, at(23, 30)) && inQuietTimes(night, at(6, 59)) && !inQuietTimes(night, at(7, 0)) && !inQuietTimes(night, at(12, 0)),
      'Nicht stören über Mitternacht');
    check(inQuietTimes({ dndTimes: true, dndFrom: '12:00', dndTo: '13:30' }, at(12, 45)) && !inQuietTimes({ dndTimes: false, dndFrom: '12:00', dndTo: '13:30' }, at(12, 45)),
      'Nicht stören tagsüber, nur wenn eingeschaltet');
    setSettings({ dndFrom: '25:99', dnd: 'ja' });
    check(getSettings().dndFrom === '22:00' && getSettings().dnd === false, 'ungültige Einstellungen werden ignoriert');

    const win = createWindow({ hidden: false });
    const wc = win.webContents;
    await within(60000, new Promise((r) => wc.once('did-finish-load', r)), 'WhatsApp Web lädt');
    check(new URL(wc.getURL()).hostname === 'web.whatsapp.com', 'WhatsApp Web geladen');
    const ua = await wc.executeJavaScript('navigator.userAgent');
    check(!/Electron|creative/i.test(ua) && /Chrome\/\d+/.test(ua), `Browserkennung wie Chrome (${ua})`);
    // WhatsApp lässt uns rein: QR-Code statt „Browser wird nicht unterstützt“
    await until(async () => wc.executeJavaScript(
      "!!document.querySelector('canvas, [data-ref], [data-testid=\"qrcode\"]') || /QR|verknüpfen|Link with phone|Mit Telefonnummer/i.test(document.body.innerText)"), 45000, 'Anmeldeseite mit QR-Code');
    const text = await wc.executeJavaScript('document.body.innerText');
    check(!/Google Chrome (36|85|60)\+|nicht unterstützt|not supported|update your browser|aktualisiere/i.test(text), 'kein „Browser nicht unterstützt“');
    check(true, 'Anmeldeseite erscheint');
    await sleep(2500);
    fs.writeFileSync(path.join(out, 'whatsapp-fenster.png'), (await wc.capturePage()).toPNG());

    // Benachrichtigungen: unsere Hülle sitzt in der Seite
    check(await wc.executeJavaScript('window.Notification.__creative === true'), 'Benachrichtigungen laufen über Creative WhatsApp');
    check(await wc.executeJavaScript('Notification.permission') === 'granted', 'Benachrichtigungen erlaubt');
    setSettings({ dnd: true });
    await sleep(300);
    check(await wc.executeJavaScript("(() => { const n = new Notification('Test', { body: 'x' }); n.close(); return n.constructor.name; })()") === 'Silent',
      'Nicht stören: keine Benachrichtigung');
    setSettings({ dnd: false });

    // Zähler aus dem Seitentitel
    await wc.executeJavaScript("document.title = '(3) WhatsApp'");
    await until(() => getUnread() === 3, 3000, 'Zähler 3');
    check(win.getTitle() === 'WhatsApp (3)', 'ungelesen: Zähler und Fenstertitel');
    await wc.executeJavaScript("document.title = 'WhatsApp'");
    await until(() => getUnread() === 0, 3000, 'Zähler 0');
    check(true, 'gelesen: Zähler weg');

    // Fremde Links öffnen nicht im WhatsApp-Fenster
    await wc.executeJavaScript("location.href = 'https://example.com/'").catch(() => {});
    await sleep(1500);
    check(new URL(wc.getURL()).hostname === 'web.whatsapp.com', 'fremde Seiten öffnen nicht im WhatsApp-Fenster');

    // Mit dem PC starten
    setSettings({ autostart: true });
    const auto = fs.readFileSync(autostartFile(), 'utf8');
    check(/Exec=creative-whatsapp --hidden/.test(auto), 'Autostart-Eintrag angelegt');
    setSettings({ autostart: false });
    check(!fs.existsSync(autostartFile()), 'Autostart-Eintrag entfernt');

    // Einstellungsfenster
    openSettings();
    const sw = getSettingsWin();
    await within(15000, new Promise((r) => sw.webContents.once('did-finish-load', r)), 'Einstellungen laden');
    await sleep(800);
    fs.writeFileSync(path.join(out, 'whatsapp-einstellungen.png'), (await sw.webContents.capturePage()).toPNG());
    await sw.webContents.executeJavaScript("document.querySelector('[data-key=dndTimes]').click()");
    await until(() => getSettings().dndTimes === true, 3000, 'Schalter Nicht-stören-Zeiten');
    check(true, 'Schalter im Einstellungsfenster wirkt');
    const saved = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'creative-whatsapp.json'), 'utf8'));
    check(saved.dndTimes === true, 'Einstellungen gespeichert');
    await sleep(500);
    fs.writeFileSync(path.join(out, 'whatsapp-einstellungen-2.png'), (await sw.webContents.capturePage()).toPNG());
    sw.close();

    // Schließen: läuft im Hintergrund weiter
    win.close();
    await sleep(800);
    check(getWin() && !getWin().isDestroyed() && !getWin().isVisible(), 'Schließen versteckt nur (läuft im Hintergrund)');

    console.log(`SELBSTTEST OK (${ok.length} Prüfungen)`);
    app.exit(0);
  } catch (e) {
    console.error(e && e.stack || e);
    try {
      const w = getWin();
      if (w && !w.isDestroyed()) {
        fs.writeFileSync(path.join(out, 'whatsapp-fehler.png'), (await w.webContents.capturePage()).toPNG());
        console.error('Seitentext:', (await w.webContents.executeJavaScript('document.body.innerText')).slice(0, 600));
      }
    } catch (_) { /* egal */ }
    app.exit(1);
  }
}

module.exports = { run };
