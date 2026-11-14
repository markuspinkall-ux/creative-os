'use strict';
// Creative Browser – Hauptprozess.
// Jedes Fenster: unten die Tabs (je ein WebContentsView), darüber die Oberfläche (ui/), ein
// durchsichtiger WebContentsView. Öffnet die Oberfläche ein Menü, wird sie kurz fensterhoch.

const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');
const {
  app, BaseWindow, WebContentsView, ipcMain, session, protocol, net, clipboard, shell, nativeTheme,
} = require('electron');
const { Store, ENGINES } = require('./store');

const APP_DIR = __dirname;
const START_URL = 'creative://start/';
const arg = (name) => (process.argv.find((a) => a.startsWith(`--${name}=`)) || '').split('=').slice(1).join('=');
const SELFTEST = arg('creative-selftest');

// ---- Chromium-Schalter (vor „ready“) ----------------------------------------------------------
app.setPath('userData', path.join(app.getPath('appData'), 'creative-browser'));
// Den Ordner sofort anlegen: Die Sperre gegen einen zweiten Start liegt darin – fehlt er beim
// allerersten Start, schlägt sie fehl und der Browser würde sich still beenden.
try { fs.mkdirSync(app.getPath('userData'), { recursive: true }); } catch (_) { /* meldet die Sperre unten */ }
app.commandLine.appendSwitch('ozone-platform-hint', 'auto');
app.commandLine.appendSwitch('enable-wayland-ime');
app.commandLine.appendSwitch('enable-gpu-rasterization');
// Videos über die Grafikkarte entschlüsseln (VA-API: AMD und Intel). Mit dem NVIDIA-Treiber
// übernimmt der Prozessor – H.264 in 1080p60 schafft jeder aktuelle Prozessor flüssig.
const nvidia = fs.existsSync('/proc/driver/nvidia/version');
if (!nvidia && !SELFTEST) {
  app.commandLine.appendSwitch('enable-features',
    'VaapiVideoDecoder,VaapiVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL');
}
if (SELFTEST) app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
protocol.registerSchemesAsPrivileged([
  { scheme: 'creative', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
]);

process.on('uncaughtException', (e) => console.error('Creative Browser – Fehler:', e && e.stack || e));
process.on('unhandledRejection', (e) => console.error('Creative Browser – Fehler:', e && e.stack || e));

let store;
const windows = new Set();
const downloads = [];
let nextTabId = 1;
let nextPromptId = 1;
const closedTabs = [];

// Kein „Electron“ in der Browserkennung – manche Seiten sperren sonst eingebettete Browser aus
function cleanUserAgent(ua) {
  return ua.replace(/ Electron\/\S+/, '').replace(/ (creative-browser|Creative Browser)\/\S+/i, '');
}

function startpageDir() {
  for (const d of [path.join(APP_DIR, '..', '..', 'browser', 'startpage'), '/usr/share/creative-os/startpage']) {
    if (fs.existsSync(path.join(d, 'index.html'))) return d;
  }
  return null;
}

function errorPage(u) {
  const q = new URL(u).searchParams;
  const target = q.get('u') || '';
  const reason = q.get('r') || '';
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  return `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Seite nicht erreichbar</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#12151b;color:#dce6ff;font:15px Arial,sans-serif}
@media(prefers-color-scheme:light){body{background:#e9eef6;color:#1c2433}}
main{max-width:520px;padding:32px}h1{font-size:24px}p{opacity:.75;line-height:1.5}code{word-break:break-all}
a{display:inline-block;margin-top:16px;padding:10px 18px;border-radius:12px;background:#8fb3ff;color:#12151b;text-decoration:none;font-weight:700}</style>
</head><body><main><h1>Diese Seite ist gerade nicht erreichbar</h1>
<p><code>${esc(target)}</code></p><p>${esc(reason)}</p>
<p>Prüfe die Internetverbindung oder die Adresse und versuche es noch einmal.</p>
<a href="${esc(target)}">Erneut versuchen</a></main></body></html>`;
}

const ERRORS = {
  '-105': 'Die Adresse wurde nicht gefunden (DNS).',
  '-106': 'Keine Internetverbindung.',
  '-102': 'Die Verbindung wurde abgelehnt.',
  '-118': 'Die Verbindung hat zu lange gedauert.',
  '-137': 'Die Adresse wurde nicht gefunden.',
  '-200': 'Das Sicherheitszertifikat der Seite ist ungültig.',
  '-201': 'Das Sicherheitszertifikat der Seite ist abgelaufen oder noch nicht gültig.',
  '-202': 'Das Sicherheitszertifikat der Seite stammt von keiner vertrauenswürdigen Stelle.',
};

// ---- Sitzungen (normal / privat) ----------------------------------------------------------------
const preparedSessions = new WeakSet();

function prepareSession(ses, isPrivate) {
  if (preparedSessions.has(ses)) return;
  preparedSessions.add(ses);
  ses.setUserAgent(cleanUserAgent(ses.getUserAgent()));
  try { ses.setSpellCheckerLanguages(['de-DE']); } catch (_) { /* Wörterbuch nicht verfügbar */ }

  ses.protocol.handle('creative', (req) => {
    const u = new URL(req.url);
    if (u.host === 'fehler') {
      return new Response(errorPage(req.url), { headers: { 'content-type': 'text/html; charset=utf-8' } });
    }
    const dir = startpageDir();
    if (u.host !== 'start' || !dir) return new Response('Nicht gefunden', { status: 404 });
    const name = decodeURIComponent(u.pathname.replace(/^\/+/, '')) || 'index.html';
    const file = path.normalize(path.join(dir, name));
    if (!file.startsWith(dir)) return new Response('Nicht erlaubt', { status: 403 });
    if (name === 'index.html') {
      // Suchfeld der Startseite nutzt die eingestellte Suchmaschine
      const engine = store.engine().url.split('?')[0];
      const html = fs.readFileSync(file, 'utf8').replace(/action="[^"]*"/, `action="${engine}"`);
      return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } });
    }
    return net.fetch(pathToFileURL(file).toString());
  });

  // Berechtigungen: Vollbild u. Ä. sofort, Kamera/Mikrofon/Standort/Mitteilungen nach Rückfrage
  const AUTO = new Set(['fullscreen', 'clipboard-sanitized-write', 'pointerLock', 'keyboardLock', 'speaker-selection']);
  ses.setPermissionRequestHandler((wc, permission, callback, details) => {
    if (AUTO.has(permission)) return callback(true);
    const origin = originOf(details.requestingUrl || wc.getURL());
    const key = `${origin}|${permission}`;
    const remembered = isPrivate ? undefined : store.data.permissions[key];
    if (typeof remembered === 'boolean') return callback(remembered);
    const w = windowOf(wc);
    if (!w || !origin) return callback(false);
    w.askPermission(origin, permission, details, (allow, remember) => {
      if (remember && !isPrivate) { store.data.permissions[key] = allow; store.save(); }
      callback(allow);
    });
  });
  ses.setPermissionCheckHandler((wc, permission, requestingOrigin) => {
    if (AUTO.has(permission)) return true;
    return store.data.permissions[`${originOf(requestingOrigin)}|${permission}`] === true;
  });

  ses.on('will-download', (_e, item, wc) => {
    const dir = app.getPath('downloads');
    let name = item.getFilename() || 'download';
    let target = path.join(dir, name);
    for (let i = 1; fs.existsSync(target); i += 1) {
      const ext = path.extname(name);
      target = path.join(dir, `${path.basename(name, ext)} (${i})${ext}`);
    }
    item.setSavePath(target);
    const d = { id: downloads.length + 1, name: path.basename(target), path: target, received: 0,
      total: item.getTotalBytes(), state: 'progressing', paused: false, item, private: isPrivate };
    downloads.unshift(d);
    item.on('updated', (_ev, state) => {
      d.state = state; d.received = item.getReceivedBytes(); d.total = item.getTotalBytes(); d.paused = item.isPaused();
      broadcast();
    });
    item.once('done', (_ev, state) => {
      d.state = state; d.received = item.getReceivedBytes();
      broadcast();
    });
    const w = windowOf(wc);
    if (w) w.send('download-started', d.name);
    broadcast();
  });
}

function originOf(u) {
  try { return new URL(u).origin; } catch (_) { return ''; }
}

function windowOf(wc) {
  if (!wc) return null;
  for (const w of windows) {
    if (w.ui.webContents === wc || w.tabs.some((t) => t.wc === wc)) return w;
  }
  const host = wc.hostWebContents;
  return host ? windowOf(host) : [...windows][0] || null;
}

function broadcast() {
  for (const w of windows) w.pushState();
}

function toUrl(text) {
  const t = text.trim();
  if (!t) return START_URL;
  if (/^[a-z][a-z0-9+.-]*:/i.test(t) && !/^[^\s:]+:\d+/.test(t)) return t;
  if (/^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?(\/|$)/i.test(t)) return `http://${t}`;
  if (!/\s/.test(t) && /^[^\s/]+\.[a-z]{2,}(:\d+)?(\/.*)?$/i.test(t)) return `https://${t}`;
  return store.engine().url + encodeURIComponent(t);
}

function displayUrl(u) {
  if (!u || u.startsWith(START_URL) || u.startsWith('creative://fehler')) return '';
  return u;
}

const PERMISSION_NAMES = {
  media: 'Kamera und Mikrofon', notifications: 'Mitteilungen anzeigen', geolocation: 'Deinen Standort',
  midi: 'MIDI-Geräte', midiSysex: 'MIDI-Geräte', 'display-capture': 'Deinen Bildschirm', openExternal: 'Ein anderes Programm öffnen',
  'idle-detection': 'Erkennen, ob du am PC bist', 'clipboard-read': 'Die Zwischenablage lesen', hid: 'Ein USB-Gerät', serial: 'Ein serielles Gerät', usb: 'Ein USB-Gerät',
};

// ---- Fenster ---------------------------------------------------------------------------------
class Win {
  constructor({ isPrivate = false, urls = null, active = 0 } = {}) {
    this.isPrivate = isPrivate;
    this.ses = isPrivate ? session.fromPartition(`creative-privat-${Date.now()}`) : session.defaultSession;
    prepareSession(this.ses, isPrivate);
    const b = store.settings.bounds || {};
    this.win = new BaseWindow({
      width: b.width || 1360, height: b.height || 880, minWidth: 560, minHeight: 400,
      title: isPrivate ? 'Privates Fenster – Creative Browser' : 'Creative Browser',
      backgroundColor: nativeTheme.shouldUseDarkColors ? '#12151b' : '#e9eef6',
      icon: fs.existsSync(path.join(APP_DIR, 'icon.png')) ? path.join(APP_DIR, 'icon.png') : undefined,
      show: true,
    });
    if (b.maximized && !SELFTEST) this.win.maximize();
    this.ui = new WebContentsView({
      webPreferences: { preload: path.join(APP_DIR, 'preload-ui.js'), contextIsolation: true, sandbox: true },
    });
    this.ui.setBackgroundColor('#00000000');
    this.win.contentView.addChildView(this.ui);
    this.ui.webContents.loadFile(path.join(APP_DIR, 'ui', 'index.html'), { query: { privat: isPrivate ? '1' : '0' } });
    this.ui.webContents.on('before-input-event', (e, input) => { if (this.shortcut(input, null)) e.preventDefault(); });
    this.tabs = [];
    this.active = null;
    this.chromeH = 84;
    this.overlay = false;
    this.fullscreen = false;
    this.prompts = new Map();
    this.pushTimer = null;
    windows.add(this);

    this.win.on('resize', () => this.layout());
    this.win.on('close', () => { if (!isPrivate) this.remember(); });
    this.win.on('closed', () => {
      for (const t of this.tabs) this.destroyTab(t);
      this.ui.webContents.close?.();
      windows.delete(this);
      if (!isPrivate) saveSession();
    });

    const list = urls && urls.length ? urls : [START_URL];
    list.forEach((u, i) => this.addTab(u, { background: i !== Math.min(active, list.length - 1) }));
    this.layout();
  }

  remember() {
    const [width, height] = this.win.getSize();
    store.settings.bounds = { width, height, maximized: this.win.isMaximized() };
    store.save();
  }

  send(channel, payload) {
    if (!this.ui.webContents.isDestroyed()) this.ui.webContents.send(channel, payload);
  }

  // ---- Anordnung ----
  layout() {
    const [w, h] = this.win.getContentSize();
    const top = this.fullscreen ? 0 : this.chromeH;
    for (const t of this.tabs) t.view.setVisible(t === this.active);
    if (this.active) this.active.view.setBounds({ x: 0, y: top, width: w, height: Math.max(0, h - top) });
    this.ui.setBounds({ x: 0, y: 0, width: w, height: this.fullscreen ? 0 : (this.overlay ? h : this.chromeH) });
  }

  // ---- Tabs ----
  addTab(url = START_URL, { background = false, webContents = null, index = null } = {}) {
    const view = webContents
      ? new WebContentsView({ webContents })
      : new WebContentsView({ webPreferences: { session: this.ses, sandbox: true, contextIsolation: true, nodeIntegration: false, spellcheck: true } });
    const tab = { id: nextTabId++, view, wc: view.webContents, title: 'Neuer Tab', url, favicon: '',
      loading: false, audible: false, muted: false, crashed: false, find: null };
    view.setBackgroundColor(nativeTheme.shouldUseDarkColors ? '#12151b' : '#ffffff');
    const at = index == null ? (this.active ? this.tabs.indexOf(this.active) + 1 : this.tabs.length) : index;
    this.tabs.splice(at, 0, tab);
    this.win.contentView.addChildView(view, 0);   // unter der Oberfläche
    this.wire(tab);
    if (!webContents) tab.wc.loadURL(url).catch(() => {});
    else tab.url = tab.wc.getURL() || url;
    if (!background || !this.active) this.activate(tab);
    else { view.setVisible(false); this.pushState(); }
    return tab;
  }

  wire(tab) {
    const wc = tab.wc;
    const upd = () => this.pushState();
    wc.setUserAgent(cleanUserAgent(wc.getUserAgent()));
    wc.on('page-title-updated', (_e, title) => {
      tab.title = title; if (!this.isPrivate) store.title(wc.getURL(), title); upd();
      if (tab === this.active) this.setTitle();
    });
    wc.on('page-favicon-updated', (_e, icons) => { tab.favicon = icons[0] || ''; upd(); });
    wc.on('did-start-loading', () => { tab.loading = true; tab.crashed = false; upd(); });
    wc.on('did-stop-loading', () => { tab.loading = false; upd(); });
    wc.on('did-navigate', (_e, url) => {
      tab.url = url; tab.favicon = url.startsWith('creative:') ? '' : tab.favicon;
      if (!this.isPrivate) store.visit(url, wc.getTitle());
      upd();
    });
    wc.on('did-navigate-in-page', (_e, url, isMain) => { if (isMain) { tab.url = url; upd(); } });
    wc.on('audio-state-changed', (e) => { tab.audible = e.audible; upd(); });
    wc.on('did-fail-load', (_e, code, desc, url, isMain) => {
      if (!isMain || code === -3 || url.startsWith('creative:')) return;
      const r = ERRORS[String(code)] || `${desc} (${code})`;
      wc.loadURL(`creative://fehler/?u=${encodeURIComponent(url)}&r=${encodeURIComponent(r)}`).catch(() => {});
    });
    wc.on('render-process-gone', () => { tab.crashed = true; tab.loading = false; upd(); });
    wc.on('enter-html-full-screen', () => this.setFullscreen(true));
    wc.on('leave-html-full-screen', () => this.setFullscreen(false));
    wc.on('found-in-page', (_e, r) => { this.send('find-result', { active: r.activeMatchOrdinal, total: r.matches }); });
    wc.on('zoom-changed', (_e, dir) => this.zoom(dir === 'in' ? 1 : -1, tab));
    wc.on('before-input-event', (e, input) => { if (this.shortcut(input, tab)) e.preventDefault(); });
    wc.on('context-menu', (_e, params) => this.contextMenu(tab, params));
    wc.on('focus', () => { if (this.overlay) this.send('close-overlays'); });
    wc.setWindowOpenHandler((details) => {
      // Anmelde-Fenster (window.open mit Größe) bleiben echte Fenster, damit window.opener funktioniert
      if (details.disposition === 'new-window') {
        return { action: 'allow', overrideBrowserWindowOptions: { autoHideMenuBar: true, width: 520, height: 680 } };
      }
      if (details.disposition === 'other' || details.disposition === 'save-to-disk') return { action: 'deny' };
      const background = details.disposition === 'background-tab';
      return {
        action: 'allow',
        createWindow: (options) => {
          const t = this.addTab(details.url, { background, webContents: options.webContents });
          return t.wc;
        },
      };
    });
  }

  destroyTab(tab) {
    try { this.win.contentView.removeChildView(tab.view); } catch (_) { /* Fenster schon zu */ }
    if (!tab.wc.isDestroyed()) (tab.wc.close ? tab.wc.close() : tab.wc.destroy());
  }

  activate(tab) {
    if (!tab) return;
    if (this.active && this.active !== tab && this.active.find) this.active.wc.stopFindInPage('clearSelection');
    this.active = tab;
    this.layout();
    this.setTitle();
    this.pushState();
    if (tab.url.startsWith(START_URL)) this.send('focus-address');
    else tab.wc.focus();
  }

  setTitle() {
    const t = this.active ? (this.active.title || 'Neuer Tab') : '';
    this.win.setTitle(`${t} – ${this.isPrivate ? 'Privates Fenster' : 'Creative Browser'}`);
  }

  closeTab(tab) {
    const i = this.tabs.indexOf(tab);
    if (i < 0) return;
    if (!this.isPrivate && tab.url && !tab.url.startsWith(START_URL)) {
      closedTabs.push(tab.url);
      if (closedTabs.length > 25) closedTabs.shift();
    }
    this.tabs.splice(i, 1);
    this.destroyTab(tab);
    if (!this.tabs.length) { this.win.close(); return; }
    if (this.active === tab) this.activate(this.tabs[Math.min(i, this.tabs.length - 1)]);
    else this.pushState();
    if (!this.isPrivate) saveSession();
  }

  moveTab(tab, index) {
    const i = this.tabs.indexOf(tab);
    if (i < 0) return;
    this.tabs.splice(i, 1);
    this.tabs.splice(Math.max(0, Math.min(index, this.tabs.length)), 0, tab);
    this.pushState();
  }

  tabById(id) { return this.tabs.find((t) => t.id === id); }

  setFullscreen(on) {
    this.fullscreen = on;
    this.win.setFullScreen(on);
    this.layout();
    this.pushState();
  }

  zoom(step, tab = this.active) {
    if (!tab) return;
    const level = step === 0 ? 0 : Math.max(-7, Math.min(9, tab.wc.getZoomLevel() + step));
    tab.wc.setZoomLevel(level);
    this.pushState();
  }

  // ---- Zustand an die Oberfläche ----
  pushState() {
    if (this.pushTimer) return;
    this.pushTimer = setTimeout(() => {
      this.pushTimer = null;
      const a = this.active;
      const wc = a && !a.wc.isDestroyed() ? a.wc : null;
      this.send('state', {
        private: this.isPrivate,
        fullscreen: this.fullscreen,
        tabs: this.tabs.map((t) => ({ id: t.id, title: t.title || displayUrl(t.url) || 'Neuer Tab',
          favicon: t.favicon, loading: t.loading, audible: t.audible, muted: t.wc.isDestroyed() ? false : t.wc.isAudioMuted(),
          crashed: t.crashed, start: t.url.startsWith(START_URL) })),
        active: a ? {
          id: a.id, url: displayUrl(a.url), start: a.url.startsWith(START_URL),
          canBack: wc ? wc.navigationHistory.canGoBack() : false,
          canForward: wc ? wc.navigationHistory.canGoForward() : false,
          loading: a.loading, secure: a.url.startsWith('https://'),
          zoom: wc ? Math.round(100 * 1.2 ** wc.getZoomLevel()) : 100,
          bookmarked: store.isBookmarked(a.url),
        } : null,
        bookmarks: store.data.bookmarks,
        settings: { engine: store.settings.engine, bookmarksBar: store.settings.bookmarksBar,
          restoreSession: store.settings.restoreSession },
        engines: Object.entries(ENGINES).map(([id, e]) => ({ id, name: e.name })),
        downloads: downloads.filter((d) => this.isPrivate || !d.private).slice(0, 30).map((d) => ({
          id: d.id, name: d.name, received: d.received, total: d.total, state: d.state, paused: d.paused })),
      });
    }, 16);
  }

  // ---- Rückfragen (Berechtigungen) ----
  askPermission(origin, permission, details, done) {
    const id = nextPromptId++;
    this.prompts.set(id, done);
    let label = PERMISSION_NAMES[permission] || permission;
    if (permission === 'media' && details.mediaTypes) {
      const t = details.mediaTypes;
      if (t.includes('video') && !t.includes('audio')) label = 'Deine Kamera';
      else if (t.includes('audio') && !t.includes('video')) label = 'Dein Mikrofon';
    }
    this.send('permission', { id, origin: origin.replace(/^https?:\/\//, ''), label });
  }

  answerPermission(id, allow, remember) {
    const done = this.prompts.get(id);
    if (done) { this.prompts.delete(id); done(allow, remember); }
  }

  // ---- Rechtsklick-Menü (in der Oberfläche gezeichnet) ----
  contextMenu(tab, p) {
    const items = [];
    const add = (id, label, enabled = true) => items.push({ id, label, enabled });
    const sep = () => { if (items.length && items[items.length - 1].id !== '-') items.push({ id: '-' }); };
    if (p.misspelledWord && p.dictionarySuggestions.length) {
      p.dictionarySuggestions.slice(0, 4).forEach((s) => add(`spell:${s}`, s));
      add('learn', 'Zum Wörterbuch hinzufügen');
      sep();
    }
    if (p.linkURL) {
      add('link-tab', 'Link in neuem Tab öffnen');
      add('link-window', 'Link in neuem Fenster öffnen');
      if (!this.isPrivate) add('link-private', 'Link in privatem Fenster öffnen');
      add('link-copy', 'Link-Adresse kopieren');
      sep();
    }
    if (p.mediaType === 'image' && p.srcURL) {
      add('img-tab', 'Bild in neuem Tab öffnen');
      add('img-save', 'Bild speichern');
      add('img-copy', 'Bild kopieren');
      add('img-copy-url', 'Bildadresse kopieren');
      sep();
    }
    if (p.mediaType === 'video' && p.srcURL && !p.srcURL.startsWith('blob:')) {
      add('video-save', 'Video speichern');
      sep();
    }
    if (p.isEditable) {
      add('cut', 'Ausschneiden', p.editFlags.canCut);
      add('copy', 'Kopieren', p.editFlags.canCopy);
      add('paste', 'Einfügen', p.editFlags.canPaste);
      add('select-all', 'Alles markieren');
      sep();
    } else if (p.selectionText) {
      add('copy', 'Kopieren');
      const s = p.selectionText.trim().replace(/\s+/g, ' ');
      add('search', `Mit ${store.engine().name} suchen: „${s.length > 24 ? `${s.slice(0, 24)}…` : s}“`);
      sep();
    }
    if (!p.linkURL && p.mediaType === 'none' && !p.isEditable && !p.selectionText) {
      add('back', 'Zurück', tab.wc.navigationHistory.canGoBack());
      add('forward', 'Vorwärts', tab.wc.navigationHistory.canGoForward());
      add('reload', 'Neu laden');
      sep();
      add('save-page', 'Seite speichern');
      add('print', 'Drucken …');
      sep();
    }
    add('inspect', 'Untersuchen');
    this.menuParams = { tab, p };
    this.send('context-menu', { x: p.x, y: p.y + (this.fullscreen ? 0 : this.chromeH), items });
  }

  contextAction(id) {
    const m = this.menuParams;
    if (!m || m.tab.wc.isDestroyed()) return;
    const { tab, p } = m;
    const wc = tab.wc;
    if (id.startsWith('spell:')) return wc.replaceMisspelling(id.slice(6));
    switch (id) {
      case 'learn': return this.ses.addWordToSpellCheckerDictionary(p.misspelledWord);
      case 'link-tab': return this.addTab(p.linkURL, { background: true });
      case 'link-window': return new Win({ isPrivate: this.isPrivate, urls: [p.linkURL] });
      case 'link-private': return new Win({ isPrivate: true, urls: [p.linkURL] });
      case 'link-copy': return clipboard.writeText(p.linkURL);
      case 'img-tab': return this.addTab(p.srcURL, { background: true });
      case 'img-save': case 'video-save': return wc.downloadURL(p.srcURL);
      case 'img-copy': return wc.copyImageAt(p.x, p.y);
      case 'img-copy-url': return clipboard.writeText(p.srcURL);
      case 'cut': return wc.cut();
      case 'copy': return wc.copy();
      case 'paste': return wc.paste();
      case 'select-all': return wc.selectAll();
      case 'search': return this.addTab(toUrl(p.selectionText), {});
      case 'back': return wc.navigationHistory.goBack();
      case 'forward': return wc.navigationHistory.goForward();
      case 'reload': return wc.reload();
      case 'save-page': return wc.downloadURL(wc.getURL());
      case 'print': return wc.print();
      case 'inspect': return wc.inspectElement(p.x, p.y);
      default: return undefined;
    }
  }

  // ---- Tastenkürzel (in Seite und Oberfläche) ----
  shortcut(input, tab) {
    if (input.type !== 'keyDown') return false;
    const k = input.key.length === 1 ? input.key.toLowerCase() : input.key;
    const c = input.control || input.meta;
    const run = (fn) => { fn(); return true; };
    const a = this.active;
    if (c && input.shift) {
      if (k === 't') return run(() => this.reopen());
      if (k === 'n') return run(() => new Win({ isPrivate: true }));
      if (k === 'b') return run(() => this.command('toggle-bookmarks-bar'));
      if (k === 'i') return run(() => a && a.wc.toggleDevTools());
      if (k === 'r') return run(() => a && a.wc.reloadIgnoringCache());
      if (k === 'Tab') return run(() => this.cycle(-1));
      return false;
    }
    if (c && !input.alt) {
      if (k === 't') return run(() => this.addTab());
      if (k === 'n') return run(() => new Win({}));
      if (k === 'w') return run(() => a && this.closeTab(a));
      if (k === 'l') return run(() => this.send('focus-address'));
      if (k === 'r') return run(() => a && a.wc.reload());
      if (k === 'f') return run(() => this.send('find-open'));
      if (k === 'p') return run(() => a && a.wc.print());
      if (k === 'd') return run(() => this.command('toggle-bookmark'));
      if (k === 'j') return run(() => this.send('open-downloads'));
      if (k === 'Tab' || k === 'PageDown') return run(() => this.cycle(1));
      if (k === 'PageUp') return run(() => this.cycle(-1));
      if (k === '+' || k === '=') return run(() => this.zoom(1));
      if (k === '-') return run(() => this.zoom(-1));
      if (k === '0') return run(() => this.zoom(0));
      if (/^[1-8]$/.test(k)) return run(() => this.activate(this.tabs[Number(k) - 1]));
      if (k === '9') return run(() => this.activate(this.tabs[this.tabs.length - 1]));
      return false;
    }
    if (input.alt && !c) {
      if (k === 'ArrowLeft') return run(() => a && a.wc.navigationHistory.goBack());
      if (k === 'ArrowRight') return run(() => a && a.wc.navigationHistory.goForward());
      if (k === 'Home') return run(() => a && a.wc.loadURL(START_URL));
      if (k === 'd') return run(() => this.send('focus-address'));
      return false;
    }
    if (k === 'F5') return run(() => a && (input.shift ? a.wc.reloadIgnoringCache() : a.wc.reload()));
    if (k === 'F6') return run(() => this.send('focus-address'));
    if (k === 'F11') return run(() => this.setFullscreen(!this.fullscreen));
    if (k === 'F12') return run(() => a && a.wc.toggleDevTools());
    if (k === 'Escape' && tab && tab.loading) { tab.wc.stop(); return false; }
    return false;
  }

  cycle(dir) {
    if (!this.tabs.length) return;
    const i = this.tabs.indexOf(this.active);
    this.activate(this.tabs[(i + dir + this.tabs.length) % this.tabs.length]);
  }

  reopen() {
    const u = closedTabs.pop();
    if (u) this.addTab(u);
  }

  // ---- Befehle aus der Oberfläche ----
  command(cmd, arg1, arg2) {
    const a = this.active;
    const wc = a && !a.wc.isDestroyed() ? a.wc : null;
    switch (cmd) {
      case 'chrome-height': this.chromeH = Math.max(0, Math.round(arg1)); this.layout(); break;
      case 'overlay': this.overlay = !!arg1; this.layout(); if (!arg1 && wc && !wc.getURL().startsWith(START_URL)) wc.focus(); break;
      case 'new-tab': this.addTab(arg1 ? toUrl(arg1) : START_URL); break;
      case 'close-tab': this.closeTab(this.tabById(arg1)); break;
      case 'activate': this.activate(this.tabById(arg1)); break;
      case 'move-tab': this.moveTab(this.tabById(arg1), arg2); break;
      case 'mute-tab': { const t = this.tabById(arg1); if (t) { t.wc.setAudioMuted(!t.wc.isAudioMuted()); this.pushState(); } break; }
      case 'duplicate-tab': { const t = this.tabById(arg1); if (t) this.addTab(t.wc.getURL(), { background: true }); break; }
      case 'reload-tab': { const t = this.tabById(arg1); if (t) t.wc.reload(); break; }
      case 'close-others': this.tabs.filter((t) => t.id !== arg1).forEach((t) => this.closeTab(t)); break;
      case 'navigate': if (wc) { wc.loadURL(toUrl(arg1)).catch(() => {}); wc.focus(); } break;
      case 'open-url': if (wc) wc.loadURL(arg1).catch(() => {}); break;
      case 'open-url-tab': this.addTab(arg1, { background: !!arg2 }); break;
      case 'back': if (wc) wc.navigationHistory.goBack(); break;
      case 'forward': if (wc) wc.navigationHistory.goForward(); break;
      case 'reload': if (wc) wc.reload(); break;
      case 'stop': if (wc) wc.stop(); break;
      case 'home': if (wc) wc.loadURL(START_URL); break;
      case 'toggle-bookmark': if (wc && /^https?:/.test(wc.getURL())) { store.toggleBookmark(wc.getURL(), a.title); broadcast(); } break;
      case 'remove-bookmark': store.removeBookmark(arg1); broadcast(); break;
      case 'rename-bookmark': store.renameBookmark(arg1, arg2); broadcast(); break;
      case 'move-bookmark': store.moveBookmark(arg1, arg2); broadcast(); break;
      case 'toggle-bookmarks-bar': store.settings.bookmarksBar = !store.settings.bookmarksBar; store.save(); broadcast(); break;
      case 'engine': if (ENGINES[arg1]) { store.settings.engine = arg1; store.save(); broadcast(); } break;
      case 'restore-session': store.settings.restoreSession = !!arg1; store.save(); broadcast(); break;
      case 'clear-history': store.clearHistory(); this.ses.clearCache(); break;
      case 'clear-all': store.clearHistory(); this.ses.clearCache(); this.ses.clearStorageData(); break;
      case 'find': if (wc) {
        const again = a.find === arg1;   // gleicher Text: weitersuchen, neuer Text: neue Suche
        a.find = arg1 || null;
        if (arg1) wc.findInPage(arg1, { findNext: !again, forward: arg2 !== false });
        else wc.stopFindInPage('clearSelection');
      } break;
      case 'find-next': if (wc && a.find) wc.findInPage(a.find, { findNext: false, forward: arg1 !== false }); break;
      case 'find-stop': if (wc) { a.find = null; wc.stopFindInPage('clearSelection'); wc.focus(); } break;
      case 'zoom': this.zoom(arg1); break;
      case 'new-window': new Win({}); break;
      case 'new-private': new Win({ isPrivate: true }); break;
      case 'devtools': if (wc) wc.toggleDevTools(); break;
      case 'print': if (wc) wc.print(); break;
      case 'fullscreen': this.setFullscreen(!this.fullscreen); break;
      case 'context-action': this.contextAction(arg1); break;
      case 'permission': this.answerPermission(arg1, arg2.allow, arg2.remember); break;
      case 'download-open': { const d = downloads.find((x) => x.id === arg1); if (d) shell.openPath(d.path); break; }
      case 'download-show': { const d = downloads.find((x) => x.id === arg1); if (d) shell.showItemInFolder(d.path); break; }
      case 'download-cancel': { const d = downloads.find((x) => x.id === arg1); if (d && d.state === 'progressing') d.item.cancel(); break; }
      case 'download-pause': { const d = downloads.find((x) => x.id === arg1); if (d && d.state === 'progressing') { if (d.item.isPaused()) d.item.resume(); else d.item.pause(); } break; }
      case 'downloads-clear': for (let i = downloads.length - 1; i >= 0; i -= 1) if (downloads[i].state !== 'progressing') downloads.splice(i, 1); broadcast(); break;
      case 'downloads-folder': shell.openPath(app.getPath('downloads')); break;
      case 'quit': app.quit(); break;
      default: break;
    }
  }
}

function saveSession() {
  if (!store) return;
  store.data.session = [...windows].filter((w) => !w.isPrivate && w.tabs.length).map((w) => ({
    urls: w.tabs.map((t) => (t.wc.isDestroyed() ? t.url : t.wc.getURL() || t.url)).filter((u) => u && !u.startsWith('creative://fehler')),
    active: Math.max(0, w.tabs.indexOf(w.active)),
  }));
  store.save();
}

// ---- IPC ----------------------------------------------------------------------------------------
ipcMain.on('cmd', (e, cmd, a1, a2) => {
  const w = windowOf(e.sender);
  if (w) w.command(cmd, a1, a2);
});
ipcMain.handle('suggest', (_e, text) => store.suggest(text));

// ---- Start ----------------------------------------------------------------------------------------
const single = SELFTEST ? true : app.requestSingleInstanceLock();
if (!single) {
  console.log('Creative Browser läuft schon – der Auftrag geht an das offene Fenster.');
  app.quit();
} else {
  app.on('second-instance', (_e, argv) => {
    const urls = argv.slice(1).filter((x) => /^(https?|file|creative):/i.test(x));
    const w = [...windows].find((x) => !x.isPrivate);
    if (argv.includes('--privat')) new Win({ isPrivate: true, urls });
    else if (w && urls.length) { urls.forEach((u) => w.addTab(u)); w.win.focus(); }
    else if (w && !argv.includes('--neues-fenster')) { w.addTab(); w.win.focus(); }
    else new Win({ urls });
  });

  app.whenReady().then(() => {
    store = new Store(app.getPath('userData'));
    app.userAgentFallback = cleanUserAgent(app.userAgentFallback);
    if (SELFTEST) { require('./selftest').run({ Win, windows, store, START_URL, arg }); return; }
    const urls = process.argv.slice(1).filter((x) => /^(https?|file|creative):/i.test(x));
    if (process.argv.includes('--privat')) { new Win({ isPrivate: true, urls }); return; }
    const saved = store.settings.restoreSession ? store.data.session.filter((s) => s.urls && s.urls.length) : [];
    if (saved.length) {
      saved.forEach((s, i) => new Win({ urls: i === 0 ? [...s.urls, ...urls] : s.urls, active: i === 0 && urls.length ? s.urls.length : s.active }));
    } else {
      new Win({ urls });
    }
  });

  app.on('before-quit', () => { saveSession(); store && store.save(true); });
  app.on('window-all-closed', () => { if (store) store.save(true); app.quit(); });
  app.on('web-contents-created', (_e, wc) => {
    // Anmelde-Popups (eigene Fenster): saubere Kennung, Links daraus als Tab
    wc.setUserAgent(cleanUserAgent(wc.getUserAgent()));
  });
}
