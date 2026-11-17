'use strict';
// Werbeblocker: Ghostery-Adblocker (MPL-2.0, kompatibel zu uBlock-Origin- und EasyList-Filtern).
// Blockiert Werbung und Tracker im Netz, blendet Werbeflächen aus und nutzt die
// uBlock-Skripte gegen Videowerbung (YouTube & Co.).
// Die Filterliste wird im Hintergrund geladen und für zwei Tage zwischengespeichert.

const fs = require('fs');
const path = require('path');
const { webContents } = require('electron');

let ElectronBlocker = null;
let loadError = '';
try {
  ({ ElectronBlocker } = require('@ghostery/adblocker-electron'));
} catch (e) {
  loadError = e.message;
}

const MAX_AGE = 2 * 24 * 3600 * 1000;

// Videodaten selbst (YouTube-Videostücke, Twitch-Segmente …) enthalten nie Werbung, die sich per
// Netzfilter blocken ließe – YouTube-Werbung entfernen die Skripte in der Seite. Diese Anfragen
// (bei einem Video hunderte) gehen deshalb ohne Prüfung durch: weniger Arbeit im Hauptprozess,
// das Video startet schneller.
const MEDIA_FAST = [
  /^https:\/\/[^/]+\.googlevideo\.com\/videoplayback/,
  /^https:\/\/[^/]+\.ytimg\.com\/(vi|vi_webp|sb)\//,
  /^https:\/\/[^/]+\.(ttvnw|twitchcdn)\.net\//,
  /^https:\/\/[^/]+\.(akamaized|fastly|cloudfront)\.net\/.*\.(m4s|ts|mp4|webm)(\?|$)/,
];
const isMediaFast = (url) => MEDIA_FAST.some((r) => r.test(url));
// Videoportale: Dort bringt der Blocker mehr Ärger (Ladehänger, Werbeblocker-Sperren) als Nutzen.
// Von Haus aus ausgeschaltet – Netzfilter, Ausblenden und Seiten-Skripte; im Schild wieder einschaltbar.
const VIDEO_PORTALS = ['youtube.com', 'youtu.be', 'youtube-nocookie.com', 'twitch.tv'];
const hostIn = (host, list) => !!host && list.some((h) => host === h || host.endsWith(`.${h}`));
const isVideoPortal = (host) => hostIn(host, VIDEO_PORTALS);
const hostOfUrl = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (_) { return ''; } };
// Zähler und Anzeige höchstens alle 400 ms neu zeichnen (statt bei jeder geblockten Anfrage)
const COUNT_DELAY = 400;

class AdBlock {
  constructor(dir, store, onChange) {
    this.dir = dir;
    this.store = store;
    this.onChange = onChange;     // Zähler oder Zustand geändert → Oberfläche neu zeichnen
    this.blocker = null;
    this.sessions = new Set();
    this.active = new Set();      // Sitzungen, in denen gerade blockiert wird
    this.counts = new Map();      // webContentsId → blockierte Anfragen auf der aktuellen Seite
    this.error = loadError;
    this.countTimer = null;
    this.fastPassed = 0;          // ungeprüft durchgelassene Videoanfragen (Selbsttest/Statistik)
    this.ready = this.init();
  }

  get enabled() { return this.store.settings.adblock !== false; }

  allowedHosts() { return this.store.settings.adblockAllow || []; }

  forcedHosts() { return this.store.settings.adblockForce || []; }   // Videoportale, auf denen trotzdem geblockt wird

  // Videowerbung auf YouTube/Twitch (Versuch, preload-videoad.js): an, solange der Blocker überall an ist
  get videoAd() { return this.enabled && this.store.settings.adblockVideo !== false; }

  videoAdFor(host) { return this.videoAd && isVideoPortal(String(host || '').replace(/^www\./, '')); }

  setVideoAd(on) {
    this.store.settings.adblockVideo = !!on;
    this.store.save();
    this.onChange();
  }

  hostOf(id) {
    try {
      const wc = webContents.fromId(id);
      return wc ? new URL(wc.getURL()).hostname.replace(/^www\./, '') : '';
    } catch (_) { return ''; }
  }

  countChanged() {
    if (this.countTimer) return;
    this.countTimer = setTimeout(() => { this.countTimer = null; this.onChange(); }, COUNT_DELAY);
  }

  isAllowed(id) {
    return id !== undefined && this.isAllowedHost(this.hostOf(id));
  }

  isAllowedHost(host) {
    if (!host) return false;
    if (isVideoPortal(host)) return !hostIn(host, this.forcedHosts());
    return hostIn(host, this.allowedHosts());
  }

  async init() {
    if (!ElectronBlocker) {
      console.error('Browser: Werbeblocker nicht verfügbar:', this.error);
      return false;
    }
    const cache = path.join(this.dir, 'werbeblocker.bin');
    try {
      if (Date.now() - fs.statSync(cache).mtimeMs > MAX_AGE) fs.unlinkSync(cache);
    } catch (_) { /* noch keine Liste */ }
    try {
      this.blocker = await ElectronBlocker.fromPrebuiltAdsAndTracking(globalThis.fetch, {
        path: cache,
        read: fs.promises.readFile,
        write: async (file, data) => { await fs.promises.mkdir(path.dirname(file), { recursive: true }); return fs.promises.writeFile(file, data); },
      });
    } catch (e) {
      this.error = `Filterliste ließ sich nicht laden (${e.message})`;
      console.error('Browser:', this.error);
      return false;
    }
    // Ausnahmen (Seiten, auf denen der Nutzer den Blocker ausgeschaltet hat) und Zähler pro Tab:
    // die Prüfung jeder Anfrage läuft über unsere Hülle.
    const original = this.blocker.onBeforeRequest;
    this.blocker.onBeforeRequest = (details, callback) => {
      if (details.resourceType === 'media' || isMediaFast(details.url)) {
        this.fastPassed += 1;
        callback({});
        return;
      }
      const id = details.webContentsId;
      if (this.isAllowed(id)) { callback({}); return; }
      original.call(this.blocker, details, (response) => {
        if (response && (response.cancel || response.redirectURL) && id !== undefined) {
          this.counts.set(id, (this.counts.get(id) || 0) + 1);
          this.countChanged();
        }
        callback(response);
      });
    };
    const originalHeaders = this.blocker.onHeadersReceived;
    if (originalHeaders) {
      this.blocker.onHeadersReceived = (details, callback) => {
        // Kopfzeilen braucht der Blocker nur für Seiten und Rahmen (Inhaltsrichtlinie), nicht für Videostücke
        if (details.resourceType === 'media' || isMediaFast(details.url)) { callback({}); return; }
        if (this.isAllowed(details.webContentsId)) { callback({}); return; }
        originalHeaders.call(this.blocker, details, callback);
      };
    }
    // Ausblenden und Seiten-Skripte (u. a. gegen Videowerbung) auf erlaubten Seiten und Videoportalen weglassen –
    // geprüft wird der Rahmen selbst (eingebettete YouTube-Videos) und die Seite drumherum.
    const originalCosmetics = this.blocker.onInjectCosmeticFilters;
    if (originalCosmetics) {
      this.blocker.onInjectCosmeticFilters = async (event, url, msg) => {
        const page = event && event.sender ? hostOfUrl(event.sender.getURL()) : '';
        if (this.isAllowedHost(hostOfUrl(url)) || this.isAllowedHost(page)) return;
        return originalCosmetics.call(this.blocker, event, url, msg);
      };
    }
    for (const ses of this.sessions) this.apply(ses);
    this.onChange();
    return true;
  }

  attach(ses) {
    this.sessions.add(ses);
    this.apply(ses);
  }

  apply(ses) {
    if (!this.blocker) return;
    const on = this.enabled;
    try {
      if (on && !this.active.has(ses)) { this.blocker.enableBlockingInSession(ses); this.active.add(ses); }
      if (!on && this.active.has(ses)) { this.blocker.disableBlockingInSession(ses); this.active.delete(ses); }
    } catch (e) { console.error('Browser: Werbeblocker:', e.message); }
  }

  setEnabled(on) {
    this.store.settings.adblock = !!on;
    this.store.save();
    for (const ses of this.sessions) this.apply(ses);
    this.onChange();
  }

  setAllowed(host, allowed) {
    if (!host) return;
    if (isVideoPortal(host)) {
      // Videoportal: „blockieren“ heißt hier, es in die Zwangsliste aufzunehmen
      const base = VIDEO_PORTALS.find((h) => host === h || host.endsWith(`.${h}`));
      const force = this.forcedHosts().filter((h) => h !== base);
      if (!allowed) force.push(base);
      this.store.settings.adblockForce = force;
      this.store.save();
      this.onChange();
      return;
    }
    const list = this.allowedHosts().filter((h) => h !== host);
    if (allowed) list.push(host);
    this.store.settings.adblockAllow = list;
    this.store.save();
    this.onChange();
  }

  resetCount(id) { if (this.counts.delete(id)) this.onChange(); }

  count(id) { return this.counts.get(id) || 0; }

  info(wc) {
    const host = wc ? (() => { try { return new URL(wc.getURL()).hostname.replace(/^www\./, ''); } catch (_) { return ''; } })() : '';
    return {
      available: !!this.blocker,
      loading: !this.blocker && !this.error,
      error: this.error,
      enabled: this.enabled,
      host,
      siteAllowed: this.isAllowedHost(host),
      videoPortal: isVideoPortal(host),
      videoAd: this.videoAd,
      blocked: wc ? this.count(wc.id) : 0,
    };
  }
}

module.exports = { AdBlock, isMediaFast, isVideoPortal };
