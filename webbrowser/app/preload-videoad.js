'use strict';
// Videowerbung auf YouTube und Twitch (Versuch) – so wie Brave es macht: die Gegenmaßnahmen laufen
// FRÜH und SYNCHRON im Hauptkontext der Seite, bevor YouTubes eigene Skripte die Werbedaten lesen.
// (Der normale Werbeblocker spritzt seine Skripte erst später ein – dann ist der Player schon
// fertig und die Werbung läuft trotzdem.)
//
// Läuft als Sitzungs-Preload in jedem Tab, tut aber nur auf youtube.com / twitch.tv etwas.
// Kein Netzfilter: Videos laden so schnell wie ohne Blocker.

const { contextBridge, ipcRenderer, webFrame } = require('electron');

// ---- YouTube: Werbedaten aus den Player-Antworten entfernen ------------------------------------
// Die Funktion wird als Quelltext in den Hauptkontext der Seite gebracht – sie darf nichts von
// außen benutzen.
function youtubeMain() {
  const AD_KEYS = ['adPlacements', 'adSlots', 'playerAds', 'adBreakHeartbeatParams'];
  const looksLikeAds = (o) => o && typeof o === 'object'
    && (AD_KEYS.some((k) => k in o) || (o.playerResponse && typeof o.playerResponse === 'object'
      && AD_KEYS.some((k) => k in o.playerResponse)));
  const prune = (o) => {
    if (!o || typeof o !== 'object') return o;
    for (const k of AD_KEYS) if (k in o) delete o[k];
    if (o.playerResponse && typeof o.playerResponse === 'object') prune(o.playerResponse);
    if (Array.isArray(o)) o.forEach(prune);
    return o;
  };
  // Ersetzte Funktionen sehen nach außen aus wie die echten (toString, name, length) – Proxy
  const wrap = (obj, name, apply) => {
    const orig = obj[name];
    if (typeof orig !== 'function') return;
    try { obj[name] = new Proxy(orig, { apply }); } catch (_) { /* nicht beschreibbar */ }
  };
  // 1) Erste Seite: YouTube legt die Daten als globale Variablen ab
  for (const name of ['ytInitialPlayerResponse']) {
    let value;
    try {
      Object.defineProperty(window, name, {
        configurable: true,
        enumerable: true,
        get() { return value; },
        set(v) { value = prune(v); },
      });
    } catch (_) { /* schon festgelegt */ }
  }
  // 2) Alles, was als JSON-Text ankommt (u. a. beim Weiterklicken)
  wrap(JSON, 'parse', (target, self, args) => {
    const r = Reflect.apply(target, self, args);
    try { if (looksLikeAds(r)) prune(r); } catch (_) { /* egal */ }
    return r;
  });
  // 3) Antworten von fetch() (/youtubei/v1/player, /next …)
  if (window.Response && Response.prototype) {
    wrap(Response.prototype, 'json', (target, self, args) => Reflect.apply(target, self, args).then((r) => {
      try { if (looksLikeAds(r)) prune(r); } catch (_) { /* egal */ }
      return r;
    }));
  }
  // 4) Rückfallebene: rutscht doch eine Werbung durch, wird sie stumm vorgespult und übersprungen
  const SKIP = '.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-overlay-close-button';
  let wasAd = false;
  setInterval(() => {
    const player = document.querySelector('#movie_player, .html5-video-player');
    const ad = !!(player && player.classList.contains('ad-showing'));
    const video = player && player.querySelector('video');
    if (ad && video) {
      if (!wasAd) { video.dataset.creativeMuted = video.muted ? '1' : '0'; }
      video.muted = true;
      if (Number.isFinite(video.duration) && video.duration > 0) {
        try { video.currentTime = Math.max(video.currentTime, video.duration - 0.1); } catch (_) { /* egal */ }
      }
      video.playbackRate = 16;
      const btn = document.querySelector(SKIP);
      if (btn) btn.click();
    } else if (wasAd && video) {
      video.playbackRate = 1;
      if (video.dataset.creativeMuted === '0') video.muted = false;
    }
    wasAd = ad;
  }, 250);
}

// Werbeflächen auf YouTube (Startseite, Suche, neben dem Video, Banner)
const YOUTUBE_CSS = `
ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer, ytd-promoted-sparkles-web-renderer,
ytd-promoted-video-renderer, ytd-display-ad-renderer, ytd-banner-promo-renderer, ytd-statement-banner-renderer,
ytd-player-legacy-desktop-watch-ads-renderer, ytd-companion-slot-renderer, ytd-action-companion-ad-renderer,
ytd-rich-item-renderer:has(> #content > ytd-ad-slot-renderer), #masthead-ad, #player-ads,
ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-ads"],
.ytp-ad-overlay-container, .ytp-ad-image-overlay, ytm-promoted-sparkles-web-renderer, ad-slot-renderer
{ display: none !important; }`;

// ---- Twitch: Werbung steckt im Videostrom selbst ----------------------------------------------
// Sie lässt sich nicht sauber herausschneiden. Während einer Werbepause wird das Video deshalb
// stumm und abgedunkelt, mit Hinweis – danach geht es normal weiter.
function twitchMain() {
  const AD = '[data-a-target="video-ad-label"], [data-a-target="video-ad-countdown"], .video-ad-label, [data-test-selector="ad-banner-default-text"]';
  let state = null;
  setInterval(() => {
    const video = document.querySelector('video');
    const ad = !!document.querySelector(AD);
    if (ad && video && !state) {
      state = { muted: video.muted };
      video.muted = true;
      const box = video.parentElement;
      if (box) {
        const note = document.createElement('div');
        note.id = 'creative-werbepause';
        note.textContent = 'Werbepause – Ton aus, gleich geht es weiter';
        note.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;'
          + 'background:#0b0d12;color:#e8ecf4;font:600 18px sans-serif;z-index:9;pointer-events:none';
        box.appendChild(note);
      }
    } else if (!ad && state) {
      if (video) video.muted = state.muted;
      const note = document.getElementById('creative-werbepause');
      if (note) note.remove();
      state = null;
    }
  }, 300);
}

const TWITCH_CSS = `
[data-test-selector="sad-overlay"], .stream-display-ad__wrapper, [data-a-target="ads-banner"],
.top-bar--pointer-enabled [data-test-selector="ad-banner"], div[data-a-target="outstream-ax-overlay"]
{ display: none !important; }`;

const SITES = [
  { hosts: ['youtube.com', 'youtube-nocookie.com'], main: youtubeMain, css: YOUTUBE_CSS },
  { hosts: ['twitch.tv'], main: twitchMain, css: TWITCH_CSS },
];

function siteFor(host) {
  host = String(host || '').replace(/^www\./, '');
  return SITES.find((s) => s.hosts.some((h) => host === h || host.endsWith(`.${h}`))) || null;
}

function run() {
  const site = siteFor(location.hostname);
  if (!site) return;                              // alle anderen Seiten: nichts tun, nichts fragen
  let on = false;
  try { on = !!ipcRenderer.sendSync('creative-videoad', location.hostname); } catch (_) { on = false; }
  if (!on) return;
  try {
    contextBridge.executeInMainWorld({ func: site.main });
  } catch (e) {
    // ältere Electron-Version: über webFrame (läuft ebenfalls im Hauptkontext)
    try { webFrame.executeJavaScript(`(${site.main.toString()})()`); } catch (_) { /* aufgeben */ }
  }
  try { webFrame.insertCSS(site.css); } catch (_) { /* egal */ }
}

if (typeof location !== 'undefined') run();

// Für die Prüfung (Node, ohne Electron): Funktionen zugänglich machen
if (typeof module !== 'undefined' && module && module.exports && typeof location === 'undefined') {
  module.exports = { youtubeMain, twitchMain, siteFor };
}
