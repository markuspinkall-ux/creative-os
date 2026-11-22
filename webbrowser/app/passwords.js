'use strict';
// Passwörter speichern und ausfüllen. Verschlüsselt mit dem Schlüsselbund des Systems
// (Electron safeStorage → KWallet/GNOME-Schlüsselbund). Ist keiner da, speichert der Browser
// keine Passwörter (lieber gar nicht als im Klartext).
// Datei: ~/.config/creative-browser/passwoerter.json
//   { "sites": { "https://beispiel.de": [{ "u": "name", "p": "<base64, verschlüsselt>", "t": 1700000000000 }] },
//     "never": ["https://bank.de"] }

const fs = require('fs');
const path = require('path');

class Passwords {
  constructor(dir, safeStorage) {
    this.file = path.join(dir, 'passwoerter.json');
    this.safe = safeStorage;
    this.data = { sites: {}, never: [] };
    try {
      const raw = JSON.parse(fs.readFileSync(this.file, 'utf8'));
      if (raw && typeof raw === 'object') {
        this.data.sites = raw.sites && typeof raw.sites === 'object' ? raw.sites : {};
        this.data.never = Array.isArray(raw.never) ? raw.never : [];
      }
    } catch (_) { /* noch keine */ }
  }

  available() {
    try { return !!this.safe && this.safe.isEncryptionAvailable(); } catch (_) { return false; }
  }

  save() {
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      fs.writeFileSync(this.file + '.tmp', JSON.stringify(this.data, null, 1), { mode: 0o600 });
      fs.renameSync(this.file + '.tmp', this.file);
    } catch (e) { console.error('Browser: Passwörter nicht gespeichert:', e.message); }
  }

  static origin(url) {
    try { const u = new URL(url); return /^https?:$/.test(u.protocol) ? u.origin : ''; } catch (_) { return ''; }
  }

  // Für das Ausfüllen: nur Namen (das Passwort gibt es einzeln über reveal)
  users(origin) {
    return (this.data.sites[origin] || []).map((e) => e.u);
  }

  reveal(origin, user) {
    const e = (this.data.sites[origin] || []).find((x) => x.u === user);
    if (!e || !this.available()) return null;
    try { return this.safe.decryptString(Buffer.from(e.p, 'base64')); } catch (_) { return null; }
  }

  isNever(origin) { return this.data.never.includes(origin); }

  // Muss der Browser fragen? (neues Konto oder geändertes Passwort)
  needsAsk(origin, user, password) {
    if (!origin || !password || !this.available() || this.isNever(origin)) return false;
    const known = this.reveal(origin, user);
    return known !== password;
  }

  store(origin, user, password) {
    if (!origin || !password || !this.available()) return false;
    const list = this.data.sites[origin] || [];
    const p = this.safe.encryptString(password).toString('base64');
    const e = list.find((x) => x.u === user);
    if (e) { e.p = p; e.t = Date.now(); } else list.push({ u: user || '', p, t: Date.now() });
    this.data.sites[origin] = list;
    this.save();
    return true;
  }

  never(origin) {
    if (origin && !this.isNever(origin)) { this.data.never.push(origin); this.save(); }
  }

  remove(origin, user) {
    const list = (this.data.sites[origin] || []).filter((x) => x.u !== user);
    if (list.length) this.data.sites[origin] = list; else delete this.data.sites[origin];
    this.save();
  }

  removeNever(origin) {
    this.data.never = this.data.never.filter((o) => o !== origin);
    this.save();
  }

  // Übersicht für die Oberfläche (ohne Passwörter)
  list() {
    const out = [];
    for (const [origin, l] of Object.entries(this.data.sites)) {
      for (const e of l) out.push({ origin, site: origin.replace(/^https?:\/\/(www\.)?/, ''), user: e.u, time: e.t || 0 });
    }
    out.sort((a, b) => a.site.localeCompare(b.site));
    return { items: out, never: this.data.never.slice(), available: this.available() };
  }
}

module.exports = { Passwords };
