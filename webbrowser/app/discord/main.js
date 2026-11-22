'use strict';
// Discord – das offizielle Discord Web im Gibeon-Look (Graphit/Porzellan, Akzentfarbe, Formen).
// Innen läuft discord.com/app (kein nachgebautes Protokoll); drumherum Gibeon OS: eigenes Fenster,
// Zähler an der Taskleiste, Benachrichtigungen mit Klick zum Fenster, Hintergrundbetrieb mit
// Tray-Symbol, Mikrofon/Kamera (auch Gibeon Mikrofon und Gibeon Kamera) und Bildschirm teilen über
// das System (PipeWire/Portal). Ersetzt den bisherigen Discord-Client – heißt weiter „Discord“.
// Start: discord [--hidden | --start-minimized]   (lädt über main.js mit --discord)

const path = require('path');
const fs = require('fs');
const { execFile, execFileSync, spawn } = require('child_process');
const {
  app, BrowserWindow, Menu, Tray, nativeImage, nativeTheme, ipcMain, shell, clipboard, desktopCapturer,
} = require('electron');

const DC_URL = process.env.GIBEON_DISCORD_URL || 'https://discord.com/app';
const DESKTOP_ID = 'discord';
const SELFTEST = (process.argv.find((a) => a.startsWith('--creative-selftest=')) || '').split('=').slice(1).join('=');
const HIDDEN = process.argv.includes('--hidden') || process.argv.includes('--start-minimized');

app.setName('Discord');
if (typeof app.setDesktopName === 'function') app.setDesktopName(`${DESKTOP_ID}.desktop`);
process.env.CHROME_DESKTOP = `${DESKTOP_ID}.desktop`;
app.setPath('userData', process.env.GIBEON_DISCORD_DATA
  || path.join(app.getPath('appData'), 'creative-browser', 'apps', 'discord'));
try { fs.mkdirSync(app.getPath('userData'), { recursive: true }); } catch (_) { /* meldet die Sperre */ }
app.commandLine.appendSwitch('ozone-platform-hint', 'auto');
app.commandLine.appendSwitch('enable-wayland-ime');
// Bildschirm teilen unter Wayland über PipeWire und das Freigabe-Fenster des Systems
app.commandLine.appendSwitch('enable-features', 'WebRTCPipeWireCapturer');
process.on('uncaughtException', (e) => console.error('Discord – Fehler:', e && e.stack || e));
process.on('unhandledRejection', (e) => console.error('Discord – Fehler:', e && e.stack || e));

// ---- Einstellungen (klein: der Rest steckt in Discord selbst) --------------------------------------
const DEFAULTS = { theme: true, background: true, bounds: null, hintShown: false };
const settingsFile = () => path.join(app.getPath('userData'), 'gibeon-discord.json');
function loadSettings() {
  try {
    const data = JSON.parse(fs.readFileSync(settingsFile(), 'utf8'));
    return { ...DEFAULTS, ...(data && typeof data === 'object' ? data : {}) };
  } catch (_) { return { ...DEFAULTS }; }
}
let settings = loadSettings();
function saveSettings() {
  try {
    const tmp = settingsFile() + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(settings, null, 2) + '\n', { mode: 0o600 });
    fs.renameSync(tmp, settingsFile());
  } catch (e) { console.error('Discord: Einstellungen nicht gespeichert:', e.message); }
}

// ---- Design von Gibeon OS ------------------------------------------------------------------------
const lookFile = () => path.join(process.env.XDG_CONFIG_HOME || path.join(app.getPath('home'), '.config'), 'creative-os', 'look.conf');
const ACCENTS = { blau: ['#8fb3ff', '#3d6fe0'], gruen: ['#6fdcc0', '#1f9e7f'], orange: ['#ffb07a', '#d9773a'], lila: ['#c3a6ff', '#7c4ddb'] };
function readLook() {
  let design = 'graphit';
  let accent = 'blau';
  try {
    const text = fs.readFileSync(lookFile(), 'utf8');
    const d = /^\s*design\s*=\s*(\w+)/m.exec(text);
    const a = /^\s*accent\s*=\s*(\w+)/m.exec(text);
    if (d && (d[1] === 'graphit' || d[1] === 'porzellan')) design = d[1];
    if (a && ACCENTS[a[1]]) accent = a[1];
  } catch (_) { /* Graphit/blau */ }
  const light = design === 'porzellan';
  return { design, light, accent: ACCENTS[accent][0], accentDark: ACCENTS[accent][1], ground: light ? '#e9eef6' : '#12151b' };
}
let look = readLook();

function themeCss() {
  const css = fs.readFileSync(path.join(__dirname, 'gibeon.css'), 'utf8');
  return css.replace(/ACCENT_TEXT/g, '#10131a').replace(/ACCENT_DARK/g, look.accentDark).replace(/ACCENT/g, look.accent);
}

let win = null;
let tray = null;
let unread = 0;
let quitting = false;
let cssKey = null;

const iconPath = () => {
  for (const p of [path.join(__dirname, 'icon.png'), '/usr/share/icons/hicolor/256x256/apps/discord.png']) {
    if (fs.existsSync(p)) return p;
  }
  return '';
};

function userAgent() {
  const major = process.versions.chrome.split('.')[0];
  return `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;
}

async function applyTheme() {
  if (!win || win.isDestroyed()) return;
  const wc = win.webContents;
  if (cssKey) { try { await wc.removeInsertedCSS(cssKey); } catch (_) { /* Seite neu geladen */ } cssKey = null; }
  if (settings.theme) {
    try { cssKey = await wc.insertCSS(themeCss()); } catch (e) { console.error('Design:', e.message); }
  }
}

// Zähler an der Taskleiste (Gibeon-Shell über D-Bus)
let badgeSent = -1;
function sendBadge(n) {
  if (n === badgeSent || SELFTEST) return;
  badgeSent = n;
  execFile('gdbus', ['call', '--session', '--dest', 'org.creativeos.Shell', '--object-path', '/Shell',
    '--method', 'org.creativeos.Shell.setBadge', DESKTOP_ID, String(n)], { timeout: 4000 }, () => {});
}
// Discord-Titel: „(3) Discord | …“ = 3 Erwähnungen/Direktnachrichten
function unreadFromTitle(title) {
  const m = /^\((\d+)\)/.exec(title || '');
  return m ? Number(m[1]) : 0;
}
function setUnread(n) {
  n = Math.max(0, Math.min(9999, n | 0));
  if (n === unread) return;
  unread = n;
  sendBadge(n);
  updateTray();
}

function showWindow() {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function openExternal(url) {
  if (!/^https?:/i.test(url)) return;
  if (SELFTEST) { console.log('würde im Browser öffnen:', url); return; }
  try {
    if (fs.existsSync('/usr/bin/creative-browser')) spawn('/usr/bin/creative-browser', [url], { detached: true, stdio: 'ignore' }).unref();
    else shell.openExternal(url);
  } catch (_) { shell.openExternal(url); }
}

const DISCORD_HOSTS = ['discord.com', 'discordapp.com', 'discord.gg', 'discord.media', 'discordapp.net', 'discord.new', 'discord.gift'];
const isDiscord = (url) => {
  try {
    const h = new URL(url).hostname;
    return DISCORD_HOSTS.some((d) => h === d || h.endsWith('.' + d));
  } catch (_) { return false; }
};

function prepareSession(ses) {
  ses.setUserAgent(userAgent());
  const allowed = new Set(['notifications', 'media', 'clipboard-read', 'clipboard-sanitized-write', 'fullscreen', 'display-capture']);
  ses.setPermissionRequestHandler((wc, permission, cb, details) => cb(allowed.has(permission) && isDiscord(details.requestingUrl || wc.getURL())));
  ses.setPermissionCheckHandler((_wc, permission, origin) => allowed.has(permission) && isDiscord(origin));
  // Bildschirm teilen: unter Wayland fragt das System (Portal) selbst, was geteilt wird
  if (typeof ses.setDisplayMediaRequestHandler === 'function') {
    ses.setDisplayMediaRequestHandler((_req, cb) => {
      desktopCapturer.getSources({ types: ['screen', 'window'] }).then((sources) => {
        if (sources && sources.length) cb({ video: sources[0] });
        else cb({});
      }).catch(() => cb({}));
    });
  }
  try { ses.setSpellCheckerLanguages(['de-DE']); } catch (_) { /* ohne Wörterbuch */ }
}

function contextMenu(wc, p) {
  const items = [];
  if (p.misspelledWord) {
    for (const s of p.dictionarySuggestions.slice(0, 5)) items.push({ label: s, click: () => wc.replaceMisspelling(s) });
    items.push({ label: `„${p.misspelledWord}“ ins Wörterbuch`, click: () => wc.session.addWordToSpellCheckerDictionary(p.misspelledWord) });
    items.push({ type: 'separator' });
  }
  if (p.linkURL && /^https?:/i.test(p.linkURL)) {
    items.push({ label: 'Link im Browser öffnen', click: () => openExternal(p.linkURL) });
    items.push({ label: 'Link kopieren', click: () => clipboard.writeText(p.linkURL) });
    items.push({ type: 'separator' });
  }
  if (p.mediaType === 'image' && p.srcURL) {
    items.push({ label: 'Bild kopieren', click: () => wc.copyImageAt(p.x, p.y) });
    items.push({ type: 'separator' });
  }
  const f = p.editFlags;
  if (p.isEditable) {
    items.push({ label: 'Ausschneiden', role: 'cut', enabled: f.canCut });
    items.push({ label: 'Kopieren', role: 'copy', enabled: f.canCopy });
    items.push({ label: 'Einfügen', role: 'paste', enabled: f.canPaste });
    items.push({ type: 'separator' });
  } else if (p.selectionText) {
    items.push({ label: 'Kopieren', role: 'copy' });
    items.push({ type: 'separator' });
  }
  items.push({ label: 'Gibeon-Design', type: 'checkbox', checked: settings.theme, click: (m) => setTheme(m.checked) });
  Menu.buildFromTemplate(items).popup({ window: win });
}

function setTheme(on) {
  settings.theme = !!on;
  saveSettings();
  applyTheme();
  updateTray();
}

function trayMenu() {
  return Menu.buildFromTemplate([
    { label: 'Discord öffnen', click: showWindow },
    { label: 'Gibeon-Design', type: 'checkbox', checked: settings.theme, click: (m) => setTheme(m.checked) },
    { label: 'Im Hintergrund weiterlaufen', type: 'checkbox', checked: settings.background,
      click: (m) => { settings.background = m.checked; saveSettings(); } },
    { type: 'separator' },
    { label: 'Beenden', click: () => { quitting = true; app.quit(); } },
  ]);
}
function updateTray() {
  if (!tray) return;
  tray.setToolTip(unread ? `Discord – ${unread} neu` : 'Discord');
  tray.setContextMenu(trayMenu());
}
function createTray() {
  if (tray || SELFTEST) return;
  try {
    const icon = iconPath() ? nativeImage.createFromPath(iconPath()).resize({ width: 32, height: 32 }) : nativeImage.createEmpty();
    tray = new Tray(icon);
    tray.on('click', () => (win && win.isVisible() && win.isFocused() ? win.hide() : showWindow()));
    updateTray();
  } catch (e) { console.error('Tray nicht möglich:', e.message); }
}

ipcMain.on('dc:focus', showWindow);

function createWindow({ hidden }) {
  const b = settings.bounds;
  win = new BrowserWindow({
    width: b && b.width || 1280, height: b && b.height || 820, x: b ? b.x : undefined, y: b ? b.y : undefined,
    minWidth: 760, minHeight: 500, title: 'Discord', backgroundColor: look.ground,
    icon: iconPath() || undefined, autoHideMenuBar: true, show: false,
    webPreferences: {
      preload: path.join(__dirname, 'dc-preload.js'), contextIsolation: true, sandbox: true, spellcheck: true,
      backgroundThrottling: false,      // Sprachkanal und Nachrichten laufen auch versteckt weiter
    },
  });
  win.setMenu(null);
  if (b && b.maximized) win.maximize();
  prepareSession(win.webContents.session);
  const wc = win.webContents;
  wc.on('page-title-updated', (e, title) => {
    e.preventDefault();
    setUnread(unreadFromTitle(title));
  });
  wc.on('dom-ready', () => { cssKey = null; applyTheme(); });
  wc.on('context-menu', (_e, p) => contextMenu(wc, p));
  wc.setWindowOpenHandler(({ url }) => {
    if (isDiscord(url)) return { action: 'allow' };        // z. B. Anmelden per QR-Code, Pop-out
    openExternal(url);
    return { action: 'deny' };
  });
  wc.on('will-navigate', (e, url) => {
    if (isDiscord(url)) return;
    e.preventDefault();
    openExternal(url);
  });
  wc.on('render-process-gone', (_e, d) => {
    console.error('Discord-Seite beendet:', d.reason);
    if (!quitting && d.reason !== 'clean-exit') setTimeout(() => !quitting && win && win.reload(), 1500);
  });
  wc.on('before-input-event', (e, input) => {
    if (input.type !== 'keyDown') return;
    const ctrl = input.control || input.meta;
    if ((ctrl && input.key.toLowerCase() === 'r') || input.key === 'F5') { e.preventDefault(); wc.reload(); }
    if (ctrl && input.key === '0') { e.preventDefault(); wc.setZoomLevel(0); }
    if (ctrl && (input.key === '+' || input.key === '=')) { e.preventDefault(); wc.setZoomLevel(Math.min(4, wc.getZoomLevel() + 0.5)); }
    if (ctrl && input.key === '-') { e.preventDefault(); wc.setZoomLevel(Math.max(-3, wc.getZoomLevel() - 0.5)); }
    if (ctrl && input.key.toLowerCase() === 'q') { e.preventDefault(); quitting = true; app.quit(); }
  });
  const remember = () => {
    if (!win || win.isDestroyed() || win.isMinimized()) return;
    settings.bounds = { ...(win.isMaximized() ? (settings.bounds || {}) : win.getBounds()), maximized: win.isMaximized() };
  };
  win.on('resize', remember);
  win.on('move', remember);
  win.on('close', (e) => {
    remember();
    saveSettings();
    if (settings.background && !quitting) {
      e.preventDefault();
      win.hide();
    }
  });
  win.on('closed', () => { win = null; });
  win.once('ready-to-show', () => { if (!hidden) showWindow(); });
  if (!hidden) setTimeout(() => { if (win && !win.isDestroyed() && !win.isVisible()) showWindow(); }, 3000);
  wc.loadURL(DC_URL, { userAgent: userAgent() });
  return win;
}

const single = SELFTEST ? true : app.requestSingleInstanceLock();
if (!single) {
  app.quit();
} else {
  app.on('second-instance', (_e, argv) => { if (!argv.includes('--hidden') && !argv.includes('--start-minimized')) showWindow(); });
  app.whenReady().then(() => {
    app.userAgentFallback = userAgent();
    nativeTheme.themeSource = look.light ? 'light' : 'dark';
    fs.watchFile(lookFile(), { interval: 2000 }, () => {
      look = readLook();
      nativeTheme.themeSource = look.light ? 'light' : 'dark';
      if (win) { win.setBackgroundColor(look.ground); applyTheme(); }
    });
    if (SELFTEST) {
      require('./selftest').run({ app, createWindow, getWin: () => win, setTheme, themeCss, unreadFromTitle, isDiscord, DC_URL });
      return;
    }
    createWindow({ hidden: HIDDEN });
    if (settings.background) createTray();
  });
  app.on('before-quit', () => {
    quitting = true;
    saveSettings();
    if (badgeSent > 0) {
      try {
        execFileSync('gdbus', ['call', '--session', '--dest', 'org.creativeos.Shell', '--object-path', '/Shell',
          '--method', 'org.creativeos.Shell.setBadge', DESKTOP_ID, '0'], { timeout: 1500, stdio: 'ignore' });
      } catch (_) { /* Shell nicht da */ }
    }
  });
  app.on('window-all-closed', () => { if (!settings.background || quitting) app.quit(); });
}

module.exports = { unreadFromTitle, isDiscord };
