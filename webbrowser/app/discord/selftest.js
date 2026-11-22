'use strict';
// Selbsttest für Discord im Gibeon-Look (CI): electron --discord --creative-selftest=<ordner für Bilder>
const fs = require('fs');
const path = require('path');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, ms, what) {
  const end = Date.now() + ms;
  for (;;) {
    try { if (await fn()) return; } catch (_) { /* weiter versuchen */ }
    if (Date.now() > end) throw new Error(`Zeitüberschreitung: ${what}`);
    await sleep(400);
  }
}

async function run(ctx) {
  const { app, createWindow, setTheme, themeCss, unreadFromTitle, isDiscord } = ctx;
  const out = (process.argv.find((a) => a.startsWith('--creative-selftest=')) || '').split('=').slice(1).join('=') || '/tmp';
  const check = (cond, what) => { if (!cond) throw new Error(`FEHLER: ${what}`); console.log('✓', what); };
  setTimeout(() => { console.error('Selbsttest hängt – Abbruch'); app.exit(3); }, 150000).unref();
  try {
    check(process.env.CHROME_DESKTOP === 'discord.desktop', `App-Kennung discord (${process.env.CHROME_DESKTOP})`);
    check(unreadFromTitle('(3) Discord | #allgemein') === 3 && unreadFromTitle('• Discord | #x') === 0, 'Zähler aus dem Fenstertitel');
    check(isDiscord('https://discord.com/app') && isDiscord('https://cdn.discordapp.com/x') && !isDiscord('https://evil.com/discord.com'),
      'nur Discord-Adressen bleiben im Fenster');
    check(!/ACCENT/.test(themeCss()) && /#8fb3ff/.test(themeCss()), 'Gibeon-Farben eingesetzt');

    const win = createWindow({ hidden: false });
    const wc = win.webContents;
    await until(async () => isDiscord(wc.getURL()) && await wc.executeJavaScript('document.readyState') === 'complete', 60000, 'Discord lädt');
    await until(async () => wc.executeJavaScript("/login|anmelden|willkommen|welcome|QR/i.test(document.body.innerText)"), 45000, 'Anmeldeseite');
    const ua = await wc.executeJavaScript('navigator.userAgent');
    check(!/Electron|creative/i.test(ua), 'Browserkennung wie Chrome');
    await sleep(2500);
    const bg = await wc.executeJavaScript(
      "getComputedStyle(document.querySelector('.theme-dark, .theme-light') || document.documentElement).getPropertyValue('--background-primary').trim()");
    console.log('--background-primary =', bg);
    check(/#1a1e27|#f4f7fb/i.test(bg), `Gibeon-Farben in Discord aktiv (${bg})`);
    fs.writeFileSync(path.join(out, 'discord-gibeon.png'), (await wc.capturePage()).toPNG());
    setTheme(false);
    await sleep(1500);
    fs.writeFileSync(path.join(out, 'discord-original.png'), (await wc.capturePage()).toPNG());
    setTheme(true);
    await sleep(800);
    check(await wc.executeJavaScript('window.Notification.__gibeon === true'), 'Benachrichtigungen holen das Fenster nach vorn');
    console.log('Discord-Selbsttest: alles in Ordnung');
    app.exit(0);
  } catch (e) {
    console.error(e.message);
    try { fs.writeFileSync(path.join(out, 'discord-fehler.png'), (await ctx.getWin().webContents.capturePage()).toPNG()); } catch (_) { /* */ }
    app.exit(1);
  }
}
module.exports = { run };
