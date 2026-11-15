'use strict';
// Creative WhatsApp – eigene App um das offizielle WhatsApp Web.
// Innen läuft web.whatsapp.com (kein nachgebautes Protokoll, also kein Sperr-Risiko für die Nummer),
// drumherum Creative OS: eigenes Fenster, Zähler an der Taskleiste, Benachrichtigungen mit Klick
// zum Chat, Hintergrundbetrieb mit Tray-Symbol, Start mit dem PC, Nicht-stören-Zeiten,
// Rechtschreibprüfung und Dateien per Ziehen.
// Start: creative-whatsapp [--hidden]   (wird über main.js mit --whatsapp geladen)

const path = require('path');
const fs = require('fs');
const { execFile, execFileSync, spawn } = require('child_process');
const {
  app, BrowserWindow, Menu, Tray, nativeImage, nativeTheme, ipcMain, session, shell, clipboard, Notification,
} = require('electron');

// CREATIVE_WHATSAPP_URL nur für Tests (z. B. ohne Netz eine leere Seite)
const WA_URL = process.env.CREATIVE_WHATSAPP_URL || 'https://web.whatsapp.com/';
const DESKTOP_ID = 'creative-whatsapp';
const SELFTEST = (process.argv.find((a) => a.startsWith('--creative-selftest=')) || '').split('=').slice(1).join('=');
const HIDDEN = process.argv.includes('--hidden');

app.setName('WhatsApp');
// Eigene App-Kennung (Wayland app_id) – sonst hält die Taskleiste WhatsApp für ein Browserfenster
// und stapelt beide unter einem Symbol. Electron nimmt sonst „desktopName“ aus package.json.
if (typeof app.setDesktopName === 'function') app.setDesktopName(`${DESKTOP_ID}.desktop`);
process.env.CHROME_DESKTOP = `${DESKTOP_ID}.desktop`;
// Gleicher Ordner wie die frühere WhatsApp-Verknüpfung – die Anmeldung (QR-Code) bleibt erhalten.
app.setPath('userData', process.env.CREATIVE_WHATSAPP_DATA
  || path.join(app.getPath('appData'), 'creative-browser', 'apps', 'whatsapp'));
try { fs.mkdirSync(app.getPath('userData'), { recursive: true }); } catch (_) { /* meldet die Sperre */ }
app.commandLine.appendSwitch('ozone-platform-hint', 'auto');
app.commandLine.appendSwitch('enable-wayland-ime');
process.on('uncaughtException', (e) => console.error('Creative WhatsApp – Fehler:', e && e.stack || e));
process.on('unhandledRejection', (e) => console.error('Creative WhatsApp – Fehler:', e && e.stack || e));

// ---- Einstellungen ----------------------------------------------------------------------------
const DEFAULTS = {
  notify: true, preview: true, sound: true,
  dnd: false, dndTimes: false, dndFrom: '22:00', dndTo: '07:00',
  background: true, autostart: false, spell: true, bounds: null, hintShown: false,
};
const settingsFile = () => path.join(app.getPath('userData'), 'creative-whatsapp.json');
function loadSettings() {
  try {
    const data = JSON.parse(fs.readFileSync(settingsFile(), 'utf8'));
    return { ...DEFAULTS, ...(data && typeof data === 'object' ? data : {}) };
  } catch (_) { return { ...DEFAULTS }; }
}
let settings = null;
function saveSettings() {
  try {
    const tmp = settingsFile() + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(settings, null, 2) + '\n', { mode: 0o600 });
    fs.renameSync(tmp, settingsFile());
  } catch (e) { console.error('Creative WhatsApp: Einstellungen nicht gespeichert:', e.message); }
}
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
function cleanSettings(next) {
  const out = { ...settings };
  for (const k of ['notify', 'preview', 'sound', 'dnd', 'dndTimes', 'background', 'autostart', 'spell']) {
    if (typeof next[k] === 'boolean') out[k] = next[k];
  }
  for (const k of ['dndFrom', 'dndTo']) if (typeof next[k] === 'string' && TIME.test(next[k])) out[k] = next[k];
  return out;
}

// Nicht stören: von Hand oder in den eingestellten Zeiten (auch über Mitternacht, 22:00–07:00)
function minutes(t) { const [h, m] = t.split(':').map(Number); return h * 60 + m; }
function inQuietTimes(s, now = new Date()) {
  if (!s.dndTimes) return false;
  const n = now.getHours() * 60 + now.getMinutes();
  const from = minutes(s.dndFrom);
  const to = minutes(s.dndTo);
  if (from === to) return false;
  return from < to ? n >= from && n < to : n >= from || n < to;
}
const isQuiet = () => settings.dnd || inQuietTimes(settings);

// ---- Design von Creative OS --------------------------------------------------------------------
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
  return { design, light, accent: ACCENTS[accent][light ? 1 : 0], ground: light ? '#e9eef6' : '#12151b' };
}
let look = readLook();

// ---- Zustand -------------------------------------------------------------------------------------
let win = null;
let settingsWin = null;
let tray = null;
let unread = 0;
let quitting = false;

const iconPath = () => {
  for (const p of [path.join(__dirname, 'icon.png'), '/usr/share/icons/hicolor/256x256/apps/creative-whatsapp.png']) {
    if (fs.existsSync(p)) return p;
  }
  return '';
};

function userAgent() {
  const major = process.versions.chrome.split('.')[0];
  return `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;
}

// Zähler an der Taskleiste: die Creative-Shell nimmt ihn über D-Bus entgegen
let badgeSent = -1;
function sendBadge(n) {
  if (n === badgeSent || SELFTEST) return;
  badgeSent = n;
  execFile('gdbus', ['call', '--session', '--dest', 'org.creativeos.Shell', '--object-path', '/Shell',
    '--method', 'org.creativeos.Shell.setBadge', DESKTOP_ID, String(n)], { timeout: 4000 }, () => {});
}

function setUnread(n) {
  n = Math.max(0, Math.min(9999, n | 0));
  if (n === unread) return;
  unread = n;
  sendBadge(n);
  if (win) win.setTitle(n ? `WhatsApp (${n})` : 'WhatsApp');
  updateTray();
}

function pushState() {
  if (win && !win.isDestroyed()) {
    win.webContents.send('wa:state', { notify: settings.notify, preview: settings.preview, sound: settings.sound, quiet: isQuiet() });
  }
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
    const exe = fs.existsSync('/usr/bin/creative-browser') ? '/usr/bin/creative-browser' : null;
    if (exe) spawn(exe, [url], { detached: true, stdio: 'ignore' }).unref();
    else shell.openExternal(url);
  } catch (_) { shell.openExternal(url); }
}

const isWhatsApp = (url) => {
  try { const h = new URL(url).hostname; return h === 'web.whatsapp.com' || h.endsWith('.whatsapp.com') || h.endsWith('.whatsapp.net'); } catch (_) { return false; }
};

function uniquePath(dir, name) {
  const safe = (name || 'Datei').replace(/[/\\\0]/g, '_').slice(0, 200) || 'Datei';
  const ext = path.extname(safe);
  const base = safe.slice(0, safe.length - ext.length);
  let p = path.join(dir, safe);
  for (let i = 2; fs.existsSync(p); i++) p = path.join(dir, `${base} (${i})${ext}`);
  return p;
}

function prepareSession(ses) {
  ses.setUserAgent(userAgent());
  const allowed = new Set(['notifications', 'media', 'clipboard-read', 'clipboard-sanitized-write', 'fullscreen']);
  ses.setPermissionRequestHandler((wc, permission, cb, details) => {
    const ok = allowed.has(permission) && isWhatsApp(details.requestingUrl || wc.getURL());
    cb(ok);
  });
  ses.setPermissionCheckHandler((_wc, permission, origin) => allowed.has(permission) && isWhatsApp(origin));
  applySpell(ses);
  // Heruntergeladene Bilder, Videos und Dokumente landen ohne Nachfrage in „Downloads“
  ses.on('will-download', (_e, item) => {
    const dir = app.getPath('downloads');
    try { fs.mkdirSync(dir, { recursive: true }); } catch (_) { /* nimmt dann den Dialog */ }
    const target = uniquePath(dir, item.getFilename());
    item.setSavePath(target);
    item.once('done', (_ev, state) => {
      if (state === 'completed' && Notification.isSupported() && !SELFTEST) {
        const n = new Notification({ title: 'Gespeichert in Downloads', body: path.basename(target), silent: true, icon: iconPath() || undefined });
        n.on('click', () => shell.showItemInFolder(target));
        n.show();
      }
    });
  });
}

function applySpell(ses) {
  try {
    ses.setSpellCheckerEnabled(!!settings.spell);
    if (settings.spell) ses.setSpellCheckerLanguages(['de-DE']);
  } catch (e) { console.error('Rechtschreibprüfung:', e.message); }
}

// ---- Rechtsklick: Rechtschreibung, Kopieren/Einfügen, Einstellungen ------------------------------
function contextMenu(wc, p) {
  const items = [];
  if (p.misspelledWord) {
    for (const s of p.dictionarySuggestions.slice(0, 5)) items.push({ label: s, click: () => wc.replaceMisspelling(s) });
    if (!p.dictionarySuggestions.length) items.push({ label: 'Keine Vorschläge', enabled: false });
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
    items.push({ label: 'Alles auswählen', role: 'selectAll' });
    items.push({ type: 'separator' });
  } else if (p.selectionText) {
    items.push({ label: 'Kopieren', role: 'copy' });
    items.push({ type: 'separator' });
  }
  items.push({ label: 'Nicht stören', type: 'checkbox', checked: settings.dnd, click: (m) => setSettings({ dnd: m.checked }) });
  items.push({ label: 'Einstellungen …', click: openSettings });
  Menu.buildFromTemplate(items).popup({ window: win });
}

// ---- Tray ------------------------------------------------------------------------------------------
function trayMenu() {
  return Menu.buildFromTemplate([
    { label: 'WhatsApp öffnen', click: showWindow },
    { label: 'Nicht stören', type: 'checkbox', checked: settings.dnd, click: (m) => setSettings({ dnd: m.checked }) },
    { label: 'Einstellungen …', click: openSettings },
    { type: 'separator' },
    { label: 'Beenden', click: () => { quitting = true; app.quit(); } },
  ]);
}
function updateTray() {
  if (!tray) return;
  const quiet = isQuiet() ? ' · Nicht stören' : '';
  tray.setToolTip(unread ? `WhatsApp – ${unread} ungelesen${quiet}` : `WhatsApp${quiet}`);
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

// ---- Start mit dem PC (XDG-Autostart) -------------------------------------------------------------
function autostartFile() {
  return path.join(process.env.XDG_CONFIG_HOME || path.join(app.getPath('home'), '.config'), 'autostart', 'creative-whatsapp.desktop');
}
function applyAutostart() {
  const file = autostartFile();
  try {
    if (settings.autostart) {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, ['[Desktop Entry]', 'Type=Application', 'Name=WhatsApp',
        'Comment=Startet unsichtbar im Hintergrund, damit Nachrichten ankommen', 'Exec=creative-whatsapp --hidden',
        'Icon=creative-whatsapp', 'Terminal=false', 'X-GNOME-Autostart-enabled=true', ''].join('\n'));
    } else if (fs.existsSync(file)) {
      fs.unlinkSync(file);
    }
  } catch (e) { console.error('Autostart:', e.message); }
}

function setSettings(next) {
  const before = settings;
  settings = cleanSettings(next);
  saveSettings();
  if (before.spell !== settings.spell && win) applySpell(win.webContents.session);
  if (before.autostart !== settings.autostart) applyAutostart();
  if (!settings.background && tray) { tray.destroy(); tray = null; }
  if (settings.background) createTray();
  pushState();
  if (settingsWin && !settingsWin.isDestroyed()) settingsWin.webContents.send('settings', publicSettings());
}
const publicSettings = () => { const { bounds, hintShown, ...rest } = settings; return { ...rest, quietNow: isQuiet() }; };

// ---- Einstellungsfenster (Creative-Optik) -----------------------------------------------------------
function openSettings() {
  if (settingsWin && !settingsWin.isDestroyed()) { settingsWin.show(); settingsWin.focus(); return; }
  settingsWin = new BrowserWindow({
    width: 520, height: 680, minWidth: 440, minHeight: 480, title: 'WhatsApp – Einstellungen',
    parent: win && win.isVisible() ? win : undefined, backgroundColor: look.ground, autoHideMenuBar: true,
    icon: iconPath() || undefined, show: false,
    webPreferences: { preload: path.join(__dirname, 'settings-preload.js'), contextIsolation: true, sandbox: true },
  });
  settingsWin.setMenu(null);
  settingsWin.loadFile(path.join(__dirname, 'settings.html'), { query: { design: look.design, accent: look.accent } });
  settingsWin.once('ready-to-show', () => settingsWin.show());
  settingsWin.on('closed', () => { settingsWin = null; });
}

ipcMain.handle('settings:get', () => publicSettings());
ipcMain.handle('settings:set', (_e, next) => { setSettings(next || {}); return publicSettings(); });
ipcMain.handle('settings:logout', async () => {
  // Abmelden: alle Daten von WhatsApp Web löschen (danach erscheint wieder der QR-Code)
  if (!win) return false;
  await win.webContents.session.clearStorageData();
  await win.webContents.session.clearCache();
  setUnread(0);
  win.loadURL(WA_URL, { userAgent: userAgent() });
  return true;
});
ipcMain.on('wa:focus', showWindow);

// ---- Hauptfenster -------------------------------------------------------------------------------------
function createWindow({ hidden }) {
  const b = settings.bounds;
  win = new BrowserWindow({
    width: b && b.width || 1180, height: b && b.height || 800, x: b ? b.x : undefined, y: b ? b.y : undefined,
    minWidth: 640, minHeight: 480, title: 'WhatsApp', backgroundColor: look.ground,
    icon: iconPath() || undefined, autoHideMenuBar: true, show: false,
    webPreferences: {
      preload: path.join(__dirname, 'wa-preload.js'), contextIsolation: true, sandbox: true, spellcheck: true,
      backgroundThrottling: false,      // Nachrichten kommen auch an, wenn das Fenster versteckt ist
    },
  });
  win.setMenu(null);
  if (b && b.maximized) win.maximize();
  prepareSession(win.webContents.session);
  const wc = win.webContents;

  wc.on('page-title-updated', (e, title) => {
    e.preventDefault();
    const m = /^\((\d+)\)/.exec(title || '');
    setUnread(m ? Number(m[1]) : 0);
  });
  wc.on('did-finish-load', pushState);
  wc.on('context-menu', (_e, p) => contextMenu(wc, p));
  // Fremde Links öffnen im Creative Browser, nie in diesem Fenster
  wc.setWindowOpenHandler(({ url }) => {
    openExternal(url);
    return { action: 'deny' };
  });
  wc.on('will-navigate', (e, url) => {
    if (isWhatsApp(url)) return;
    e.preventDefault();          // auch eine aufs Fenster gezogene Datei öffnet sich nicht anstelle von WhatsApp
    openExternal(url);
  });
  wc.on('render-process-gone', (_e, d) => {
    console.error('WhatsApp-Seite beendet:', d.reason);
    if (!quitting && d.reason !== 'clean-exit') setTimeout(() => !quitting && win && win.reload(), 1500);
  });
  wc.on('before-input-event', (e, input) => {
    if (input.type !== 'keyDown') return;
    const ctrl = input.control || input.meta;
    if (ctrl && input.key === ',') { e.preventDefault(); openSettings(); }
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
      if (!settings.hintShown && Notification.isSupported() && !SELFTEST) {
        settings.hintShown = true;
        saveSettings();
        new Notification({ title: 'WhatsApp läuft im Hintergrund weiter',
          body: 'Neue Nachrichten kommen weiter an. Beenden über das Tray-Symbol oder Strg+Q.', icon: iconPath() || undefined, silent: true }).show();
      }
    }
  });
  win.on('closed', () => { win = null; });
  win.once('ready-to-show', () => { if (!hidden) showWindow(); });
  wc.setUserAgent(userAgent());
  wc.loadURL(WA_URL, { userAgent: userAgent() });
  return win;
}

// ---- Start ---------------------------------------------------------------------------------------------
settings = loadSettings();
const single = SELFTEST ? true : app.requestSingleInstanceLock();
if (!single) {
  app.quit();
} else {
  app.on('second-instance', (_e, argv) => {
    if (argv.includes('--einstellungen')) openSettings();
    else if (!argv.includes('--hidden')) showWindow();
  });
  app.whenReady().then(() => {
    app.userAgentFallback = userAgent();   // ohne „Electron“: sonst meldet WhatsApp „Browser nicht unterstützt“
    nativeTheme.themeSource = look.light ? 'light' : 'dark';
    fs.watchFile(lookFile(), { interval: 2000 }, () => {
      look = readLook();
      nativeTheme.themeSource = look.light ? 'light' : 'dark';
      if (win) win.setBackgroundColor(look.ground);
    });
    if (SELFTEST) {
      require('./selftest').run({ app, createWindow, getWin: () => win, openSettings, getSettingsWin: () => settingsWin,
        setSettings, getSettings: () => settings, inQuietTimes, getUnread: () => unread, autostartFile, WA_URL });
      return;
    }
    const onlySettings = process.argv.includes('--einstellungen');
    createWindow({ hidden: HIDDEN || onlySettings });
    if (onlySettings) openSettings();
    if (settings.background) createTray();
    applyAutostart();
    // Nicht-stören-Zeiten: jede Minute prüfen
    let lastQuiet = isQuiet();
    setInterval(() => { const q = isQuiet(); if (q !== lastQuiet) { lastQuiet = q; pushState(); } }, 30000);
  });
  app.on('before-quit', () => {
    quitting = true;
    if (settings) saveSettings();
    if (badgeSent > 0) {     // Zähler an der Taskleiste weg, bevor der Prozess endet
      try {
        execFileSync('gdbus', ['call', '--session', '--dest', 'org.creativeos.Shell', '--object-path', '/Shell',
          '--method', 'org.creativeos.Shell.setBadge', DESKTOP_ID, '0'], { timeout: 1500, stdio: 'ignore' });
      } catch (_) { /* Shell nicht da */ }
    }
  });
  app.on('window-all-closed', () => { if (!settings.background || quitting) app.quit(); });
}

module.exports = { inQuietTimes, cleanSettings, uniquePath };
