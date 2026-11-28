'use strict';
// Gespeicherte Daten: Lesezeichen, Verlauf, Einstellungen, Berechtigungen, letzte Sitzung.
// ~/.config/creative-browser/creative.json – wird gebündelt und verzögert geschrieben.

const fs = require('fs');
const path = require('path');

const ENGINES = {
  brave: { name: 'Brave Search', url: 'https://search.brave.com/search?q=' },
  google: { name: 'Google', url: 'https://www.google.com/search?q=' },
  duckduckgo: { name: 'DuckDuckGo', url: 'https://duckduckgo.com/?q=' },
  startpage: { name: 'Startpage', url: 'https://www.startpage.com/do/search?q=' },
  ecosia: { name: 'Ecosia', url: 'https://www.ecosia.org/search?q=' },
};

const DEFAULTS = () => ({
  version: 1,
  settings: { engine: 'google', engineChosen: false, restoreSession: true, bookmarksBar: true, adblock: true, adblockAllow: [],
    sleepTabs: true, sleepMinutes: 30, darkPages: false, darkSkip: [], sponsorblock: true, passwords: true,
    importDone: false },
  bookmarks: [
    { title: 'YouTube', url: 'https://www.youtube.com/' },
    { title: 'Twitch', url: 'https://www.twitch.tv/' },
  ],
  history: {},          // url → { title, count, last }
  permissions: {},      // "origin|permission" → true/false
  session: [],          // [{ urls: [...], active: n }]
});

class Store {
  constructor(dir) {
    this.file = path.join(dir, 'creative.json');
    this.data = DEFAULTS();
    try {
      const raw = JSON.parse(fs.readFileSync(this.file, 'utf8'));
      const d = DEFAULTS();
      this.data = {
        ...d, ...raw,
        settings: { ...d.settings, ...(raw.settings || {}) },
        bookmarks: Array.isArray(raw.bookmarks) ? raw.bookmarks : d.bookmarks,
        history: raw.history && typeof raw.history === 'object' ? raw.history : {},
        permissions: raw.permissions && typeof raw.permissions === 'object' ? raw.permissions : {},
        session: Array.isArray(raw.session) ? raw.session : [],
      };
    } catch (_) { /* erste Nutzung oder kaputte Datei */ }
    // Suche per Adressleiste geht an Google, solange niemand selbst eine Suchmaschine gewählt hat
    // (früher war Brave Search voreingestellt).
    if (!this.data.settings.engineChosen && this.data.settings.engine === 'brave') this.data.settings.engine = 'google';
    this.timer = null;
  }

  save(now = false) {
    clearTimeout(this.timer);
    const write = () => {
      try {
        fs.mkdirSync(path.dirname(this.file), { recursive: true });
        fs.writeFileSync(this.file + '.tmp', JSON.stringify(this.data, null, 1));
        fs.renameSync(this.file + '.tmp', this.file);
      } catch (e) { console.error('Browser: speichern ging nicht:', e.message); }
    };
    if (now) write(); else this.timer = setTimeout(write, 800);
  }

  get settings() { return this.data.settings; }
  engine() { return ENGINES[this.data.settings.engine] || ENGINES.google; }

  // ---- Lesezeichen ----
  isBookmarked(url) { return this.data.bookmarks.some((b) => b.url === url); }
  toggleBookmark(url, title, icon) {
    const i = this.data.bookmarks.findIndex((b) => b.url === url);
    if (i >= 0) this.data.bookmarks.splice(i, 1);
    else this.data.bookmarks.push({ title: title || url, url, ...(/^https?:|^data:image\//.test(icon || '') ? { icon } : {}) });
    this.save();
    return i < 0;
  }
  // Symbol einer Seite merken (aus dem Tab), damit die Lesezeichenleiste das richtige zeigt
  setBookmarkIcon(url, icon) {
    if (!/^https?:|^data:image\//.test(icon || '') || icon.length > 200000) return false;
    const b = this.data.bookmarks.find((x) => x.url === url);
    if (!b || b.icon === icon) return false;
    b.icon = icon;
    this.save();
    return true;
  }
  // ---- Ordner (ein Lesezeichen hat optional „folder“; leer = direkt in der Leiste) ----
  folders() {
    const seen = [];
    for (const b of this.data.bookmarks) if (b.folder && !seen.includes(b.folder)) seen.push(b.folder);
    return seen;
  }
  setBookmarkFolder(url, folder) {
    const b = this.data.bookmarks.find((x) => x.url === url);
    if (!b) return;
    const f = String(folder || '').trim().slice(0, 80);
    if (f) b.folder = f; else delete b.folder;
    this.save();
  }
  renameFolder(from, to) {
    const t = String(to || '').trim().slice(0, 80);
    if (!t) return;
    for (const b of this.data.bookmarks) if (b.folder === from) b.folder = t;
    this.save();
  }
  dissolveFolder(name) {
    for (const b of this.data.bookmarks) if (b.folder === name) delete b.folder;
    this.save();
  }
  // Import: nur neue Adressen, Reihenfolge bleibt
  addImported(list) {
    const have = new Set(this.data.bookmarks.map((b) => b.url));
    let n = 0;
    for (const it of list || []) {
      if (!it || !/^https?:/.test(it.url) || have.has(it.url)) continue;
      have.add(it.url);
      const b = { title: String(it.title || it.url).slice(0, 300), url: it.url };
      if (it.folder) b.folder = String(it.folder).slice(0, 80);
      this.data.bookmarks.push(b);
      n += 1;
    }
    this.data.settings.importDone = true;
    this.save();
    return n;
  }

  removeBookmark(url) {
    this.data.bookmarks = this.data.bookmarks.filter((b) => b.url !== url);
    this.save();
  }
  renameBookmark(url, title) {
    const b = this.data.bookmarks.find((x) => x.url === url);
    if (b && title.trim()) { b.title = title.trim(); this.save(); }
  }
  moveBookmark(url, index) {
    const i = this.data.bookmarks.findIndex((b) => b.url === url);
    if (i < 0) return;
    const [b] = this.data.bookmarks.splice(i, 1);
    this.data.bookmarks.splice(Math.max(0, Math.min(index, this.data.bookmarks.length)), 0, b);
    this.save();
  }

  // ---- Verlauf ----
  visit(url, title) {
    if (!/^https?:/.test(url)) return;
    const h = this.data.history[url] || { title: '', count: 0, last: 0 };
    h.count += 1; h.last = Date.now();
    if (title) h.title = title;
    this.data.history[url] = h;
    const keys = Object.keys(this.data.history);
    if (keys.length > 4000) {
      keys.sort((a, b) => this.data.history[a].last - this.data.history[b].last)
        .slice(0, keys.length - 3000).forEach((k) => delete this.data.history[k]);
    }
    this.save();
  }
  title(url, title) {
    const h = this.data.history[url];
    if (h && title && h.title !== title) { h.title = title; this.save(); }
  }
  clearHistory() { this.data.history = {}; this.save(); }

  suggest(text, limit = 6) {
    const q = text.trim().toLowerCase();
    if (!q) return [];
    const seen = new Set();
    const out = [];
    const score = (url, title, base) => {
      const u = url.toLowerCase().replace(/^https?:\/\/(www\.)?/, '');
      const t = (title || '').toLowerCase();
      if (u.startsWith(q)) return base + 3;
      if (t.split(/\s+/).some((w) => w.startsWith(q))) return base + 2;
      if (u.includes(q) || t.includes(q)) return base + 1;
      return 0;
    };
    for (const b of this.data.bookmarks) {
      const s = score(b.url, b.title, 100);
      if (s) out.push({ url: b.url, title: b.title, s, bookmark: true });
    }
    for (const [url, h] of Object.entries(this.data.history)) {
      const s = score(url, h.title, Math.min(60, h.count * 3) + (Date.now() - h.last < 7 * 864e5 ? 10 : 0));
      if (s) out.push({ url, title: h.title, s });
    }
    out.sort((a, b) => b.s - a.s);
    return out.filter((x) => (seen.has(x.url) ? false : seen.add(x.url))).slice(0, limit);
  }
}

module.exports = { Store, ENGINES };
