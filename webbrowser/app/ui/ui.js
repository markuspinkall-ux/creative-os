'use strict';
/* Browser – Oberfläche: Tabs, Adressleiste, Lesezeichen, Menüs. Zustand kommt vom Hauptprozess. */
const api = window.creative;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---- Symbole (Linien wie die Gibeon-Symbole) ----
const P = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="M7 7l10 10M17 7L7 17"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  forward: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  reload: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  stop: '<path d="M7 7l10 10M17 7L7 17"/>',
  home: '<path d="M4 11l8-7 8 7"/><path d="M6 10v10h12V10"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8L3.5 9.7l5.9-.9z"/>',
  menu: '<circle cx="12" cy="5.5" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="12" cy="18.5" r="1.3"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17"/>',
  up: '<path d="M6 15l6-6 6 6"/>',
  down: '<path d="M6 9l6 6 6-6"/>',
  speaker: '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/>',
  muted: '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 9l5 5M21 9l-5 5"/>',
  window: '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><path d="M3.5 9h17"/>',
  privat: '<path d="M3 11h18M6 11l2-6h8l2 6"/><circle cx="7.5" cy="16" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/><path d="M10 16h4"/>',
  print: '<path d="M7 9V4h10v5"/><rect x="4" y="9" width="16" height="7" rx="2"/><path d="M7 14h10v6H7z"/>',
  code: '<path d="M9 7l-5 5 5 5M15 7l5 5-5 5"/>',
  trash: '<path d="M4 7h16M10 7V4h4v3M6 7l1 13h10l1-13"/>',
  folder: '<path d="M3.5 7a2 2 0 0 1 2-2H10l2 2h6.5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  full: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  minus: '<path d="M5 12h14"/>',
  open: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  pause: '<path d="M9 6v12M15 6v12"/>',
  play: '<path d="M8 5l11 7-11 7z"/>',
  power: '<path d="M12 3v8M6.3 7a8 8 0 1 0 11.4 0"/>',
  bookmark: '<path d="M7 4h10v16l-5-4-5 4z"/>',
  pip: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><rect x="12" y="11" width="7" height="6" rx="1.2"/>',
  reader: '<path d="M4 5.5h6.5a2 2 0 0 1 1.5.7 2 2 0 0 1 1.5-.7H20v13h-6.5a2 2 0 0 0-1.5.7 2 2 0 0 0-1.5-.7H4z"/><path d="M12 6.2v13"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l8-8M16 7l3 3"/>',
  translate: '<path d="M4 5h9M8.5 3v2c0 4-2 7-5 8.5M6 9c1 2 3 3.5 5.5 4"/><path d="M13 20l4-9 4 9M14.3 17h5.4"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  sleep: '<path d="M9 5h6l-6 7h6M14 14h5l-5 6h5"/>',
  import: '<path d="M12 15V4M7 10l5 5 5-5"/><path d="M4 15v4h16v-4"/>',
  shield: '<path d="M12 3l7 3v5c0 4.4-3 8.3-7 10-4-1.7-7-5.6-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
};
const icon = (name, size = 18, fill = false) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${fill ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="${fill ? 0 : 1.8}" stroke-linecap="round" stroke-linejoin="round">${P[name]}</svg>`;

for (const [id, name] of [['newtab', 'plus'], ['back', 'back'], ['forward', 'forward'], ['reload', 'reload'], ['home', 'home'],
  ['menu-btn', 'menu'], ['find-prev', 'up'], ['find-next', 'down'], ['find-close', 'close']]) $(id).innerHTML = icon(name);
$('downloads-btn').insertAdjacentHTML('beforeend', icon('download'));
$('pip-btn').innerHTML = icon('pip');
$('reader-btn').innerHTML = icon('reader');
$('pip-btn').onclick = () => api.cmd('pip');
$('reader-btn').onclick = () => api.cmd('reader');
$('menu-btn').innerHTML = icon('menu', 18, true);

const isPrivate = new URLSearchParams(location.search).get('privat') === '1';
document.body.classList.toggle('private', isPrivate);
// Web-App (WhatsApp, Claude …): keine Tabs, keine Adressleiste – nur Rückfragen, Suche und Menüs
document.body.classList.toggle('appmode', new URLSearchParams(location.search).get('app') === '1');

let S = { tabs: [], active: null, bookmarks: [], downloads: [], settings: {}, engines: [] };

// ---- Höhe der Leiste melden ----
const chrome = $('chrome');
new ResizeObserver(() => api.cmd('chrome-height', chrome.offsetHeight)).observe(chrome);

// ---- Schicht für Menüs ----
const popups = ['suggest', 'menu', 'downloads', 'ctx', 'dialog', 'shield-panel', 'boost-panel'];
function openLayer(id) {
  for (const p of popups) $(p).hidden = p !== id;
  $('layer').hidden = false;
  api.cmd('overlay', true);
}
function closeLayer() {
  if ($('layer').hidden) return;
  for (const p of popups) $(p).hidden = true;
  $('layer').hidden = true;
  api.cmd('overlay', false);
}
$('backdrop').addEventListener('mousedown', closeLayer);
api.on('close-overlays', closeLayer);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('layer').hidden) { closeLayer(); e.preventDefault(); }
});

// ---- Tabs ----
const tabEls = new Map();
function tabEl(t) {
  let el = tabEls.get(t.id);
  if (!el) {
    el = document.createElement('div');
    el.className = 'tab';
    el.setAttribute('role', 'tab');
    el.draggable = true;
    el.innerHTML = '<div class="fav"></div><div class="title"></div><button class="audio" tabindex="-1"></button><button class="close" tabindex="-1" aria-label="Tab schließen"></button>';
    el.querySelector('.close').innerHTML = icon('close', 14);
    el.querySelector('.close').addEventListener('click', (e) => { e.stopPropagation(); api.cmd('close-tab', t.id); });
    el.querySelector('.audio').addEventListener('click', (e) => { e.stopPropagation(); api.cmd('mute-tab', t.id); });
    el.addEventListener('mousedown', (e) => {
      if (e.button === 0 && !e.target.closest('button')) api.cmd('activate', t.id);
      if (e.button === 1) { e.preventDefault(); api.cmd('close-tab', t.id); }
    });
    el.addEventListener('contextmenu', (e) => { e.preventDefault(); tabMenu(t.id, e.clientX, e.clientY); });
    el.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/x-tab', String(t.id)); el.classList.add('dragging'); });
    el.addEventListener('dragstart', () => { dragLeftWindow = false; });
    el.addEventListener('dragend', (e) => {
      el.classList.remove('dragging');
      // Außerhalb der Tab-Leiste losgelassen (z. B. auf einem anderen Bildschirm): eigenes Fenster.
      // Unter Wayland kennt der Browser die Stelle außerhalb seines Fensters nicht – dann meldet er die
      // letzte Stelle im Fenster (beim Ziehen nach links z. B. x≈0 auf Höhe der Tabs). Darum zählt auch,
      // ob der Zeiger das Fenster verlassen hat.
      const strip = $('tabstrip').getBoundingClientRect();
      const offStrip = e.clientY > strip.bottom + 40 || e.clientY < -10 || e.clientX < -10 || e.clientX > innerWidth + 10
        || (e.clientX === 0 && e.clientY === 0);
      if (e.dataTransfer.dropEffect === 'none' && (offStrip || dragLeftWindow)) api.cmd('tear-off', t.id);
      dragLeftWindow = false;
    });
    el.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('text/x-tab')) { e.preventDefault(); el.classList.add('drop-before'); } });
    el.addEventListener('dragleave', () => el.classList.remove('drop-before'));
    el.addEventListener('drop', (e) => {
      el.classList.remove('drop-before');
      const id = Number(e.dataTransfer.getData('text/x-tab'));
      const to = S.tabs.findIndex((x) => x.id === Number(el.dataset.id));
      const from = S.tabs.findIndex((x) => x.id === id);
      if (id && to >= 0) api.cmd('move-tab', id, from < to ? to - 1 : to);
    });
    tabEls.set(t.id, el);
  }
  el.dataset.id = t.id;
  return el;
}

// Hat ein gezogener Tab das Browserfenster verlassen? (dragleave ohne neues Ziel im Fenster)
var dragLeftWindow = false;
document.addEventListener('dragleave', (e) => { if (!e.relatedTarget) dragLeftWindow = true; });
document.addEventListener('dragenter', () => { dragLeftWindow = false; });

function renderTabs() {
  const box = $('tabs');
  const ids = new Set(S.tabs.map((t) => t.id));
  for (const [id, el] of tabEls) if (!ids.has(id)) { el.remove(); tabEls.delete(id); }
  S.tabs.forEach((t, i) => {
    const el = tabEl(t);
    if (box.children[i] !== el) box.insertBefore(el, box.children[i] || null);
    el.classList.toggle('active', S.active && t.id === S.active.id);
    el.classList.toggle('sleeping', !!t.sleeping);
    el.setAttribute('aria-selected', String(S.active && t.id === S.active.id));
    el.title = t.sleeping ? `${t.title} (schläft – wird beim Anklicken neu geladen)` : t.title;
    const title = el.querySelector('.title');
    if (title.textContent !== t.title) title.textContent = t.title;
    const fav = el.querySelector('.fav');
    const favKey = t.loading ? 'loading' : t.crashed ? 'crashed' : (t.start ? 'start' : t.favicon || 'globe');
    if (fav.dataset.k !== favKey) {
      fav.dataset.k = favKey;
      if (t.loading) fav.innerHTML = '<div class="spinner"></div>';
      else if (t.start) fav.innerHTML = icon('home', 15);
      else if (t.favicon) {
        fav.innerHTML = '<img alt="">';
        const img = fav.querySelector('img');
        img.onerror = () => { fav.innerHTML = icon('globe', 15); };
        img.src = t.favicon;
      } else fav.innerHTML = icon('globe', 15);
    }
    const audio = el.querySelector('.audio');
    audio.hidden = !(t.audible || t.muted);
    audio.innerHTML = icon(t.muted ? 'muted' : 'speaker', 15);
    audio.title = t.muted ? 'Ton an' : 'Stummschalten';
  });
  const width = box.clientWidth / Math.max(1, S.tabs.length);
  for (const el of tabEls.values()) el.classList.toggle('narrow', width < 96);
}

function tabMenu(id, x, y) {
  const t = S.tabs.find((v) => v.id === id);
  if (!t) return;
  showMenu($('ctx'), [
    { label: 'Neuer Tab', icon: 'plus', run: () => api.cmd('new-tab') },
    '-',
    { label: 'Neu laden', icon: 'reload', run: () => api.cmd('reload-tab', id) },
    { label: 'Duplizieren', icon: 'window', run: () => api.cmd('duplicate-tab', id) },
    { label: 'In neues Fenster verschieben', icon: 'open', enabled: S.tabs.length > 1, run: () => api.cmd('tear-off', id) },
    { label: t.muted ? 'Ton wieder an' : 'Tab stummschalten', icon: t.muted ? 'speaker' : 'muted', enabled: !t.sleeping, run: () => api.cmd('mute-tab', id) },
    { label: 'Tab schlafen legen', icon: 'sleep', enabled: !t.sleeping && !(S.active && S.active.id === id) && !t.start && !t.audible, run: () => api.cmd('sleep-tab', id) },
    '-',
    { label: 'Andere Tabs schließen', run: () => api.cmd('close-others', id), enabled: S.tabs.length > 1 },
    { label: 'Tab schließen', icon: 'close', key: 'Strg+W', run: () => api.cmd('close-tab', id) },
  ], x, y);
}

// ---- Navigationsleiste ----
const addr = $('address');
let editing = false;
$('back').onclick = () => api.cmd('back');
$('forward').onclick = () => api.cmd('forward');
$('reload').onclick = () => api.cmd(S.active && S.active.loading ? 'stop' : 'reload');
$('home').onclick = () => api.cmd('home');
$('newtab').onclick = () => api.cmd('new-tab');
$('star').onclick = () => api.cmd('toggle-bookmark');
$('zoom-badge').onclick = () => api.cmd('zoom', 0);
$('tabstrip').addEventListener('dblclick', (e) => { if (e.target.id === 'tabstrip' || e.target.id === 'tabs') api.cmd('new-tab'); });
$('tabstrip').addEventListener('mousedown', (e) => { if (e.button === 1 && (e.target.id === 'tabstrip' || e.target.id === 'tabs')) api.cmd('new-tab'); });

function renderNav() {
  const a = S.active || {};
  $('back').disabled = !a.canBack;
  $('forward').disabled = !a.canForward;
  $('reload').innerHTML = icon(a.loading ? 'stop' : 'reload');
  $('reload').title = a.loading ? 'Laden abbrechen (Esc)' : 'Neu laden (F5)';
  if (!editing) addr.value = a.url || '';
  $('lock').innerHTML = a.url ? icon(a.secure ? 'lock' : 'globe', 15) : icon('search', 15);
  $('lock').title = a.secure ? 'Verbindung ist verschlüsselt' : (a.url ? 'Verbindung ist nicht verschlüsselt' : '');
  $('star').innerHTML = icon('star', 17, !!a.bookmarked);
  $('star').classList.toggle('on', !!a.bookmarked);
  $('star').hidden = !a.url;
  renderShield(a.adblock);
  $('pip-btn').classList.toggle('show', !!a.hasVideo);
  $('reader-btn').classList.toggle('show', !!a.web);
  renderBoost(a);
  $('zoom-badge').textContent = `${a.zoom || 100} %`;
  $('zoom-badge').classList.toggle('show', !!a.zoom && a.zoom !== 100);
  const prog = $('progress');
  if (a.loading) { prog.className = 'loading'; } else if (prog.classList.contains('loading')) { prog.className = 'done'; }
}

// ---- Werbeblocker ----
function renderShield(ab) {
  const b = $('shield');
  b.hidden = !ab || !ab.host;
  if (!ab) return;
  const on = ab.enabled && !ab.siteAllowed && ab.available;
  b.classList.toggle('off', !on);
  if (!b.querySelector('svg')) b.insertAdjacentHTML('afterbegin', icon('shield', 17));
  $('shield-count').textContent = on && ab.blocked ? (ab.blocked > 99 ? '99+' : String(ab.blocked)) : '';
  b.title = !ab.available ? (ab.loading ? 'Werbeblocker lädt die Filterliste …' : 'Werbeblocker nicht verfügbar')
    : on ? `Werbeblocker: ${ab.blocked} blockiert` : 'Werbeblocker ist hier aus';
  if (!$('shield-panel').hidden) renderShieldPanel();
}
function renderShieldPanel() {
  const ab = (S.active && S.active.adblock) || {};
  const on = ab.enabled && !ab.siteAllowed;
  const box = $('shield-panel');
  box.innerHTML = `<h3>${icon('shield', 18)} Werbeblocker</h3>
    ${!ab.available ? `<p>${esc(ab.loading ? 'Die Filterliste wird gerade geladen …' : (ab.error || 'Nicht verfügbar'))}</p>` : `
    <div class="big">${on ? ab.blocked : '–'}</div>
    <p>${on ? 'Werbungen und Tracker auf dieser Seite blockiert' : (ab.enabled ? `Auf ${esc(ab.host)} ausgeschaltet` : 'Werbeblocker ist überall aus')}</p>
    ${ab.videoPortal && ab.enabled ? `<p class="hint">Auf YouTube und Twitch filtert der Werbeblocker das Netz nicht – Videos laden so schnell wie ohne. Videowerbung wird stattdessen direkt in der Seite übersprungen (Versuch). Auf Twitch steckt die Werbung im Stream: dort wird sie stumm geschaltet und abgedeckt.</p>` : ''}`}
    ${ab.videoPortal ? `<div class="switchrow"><span>Videowerbung überspringen <small>(Versuch)</small></span>
      <button class="switch${ab.videoAd ? ' on' : ''}" id="sw-video" aria-label="Videowerbung überspringen" ${ab.enabled ? '' : 'disabled'}></button></div>` : ''}
    <div class="switchrow"><span>Auf <b>${esc(ab.host || 'dieser Seite')}</b> blockieren</span>
      <button class="switch${!ab.siteAllowed ? ' on' : ''}" id="sw-site" aria-label="Auf dieser Seite blockieren" ${ab.enabled ? '' : 'disabled'}></button></div>
    <div class="switchrow"><span>Werbeblocker überall</span>
      <button class="switch${ab.enabled ? ' on' : ''}" id="sw-all" aria-label="Werbeblocker überall"></button></div>`;
  $('sw-site').onclick = () => api.cmd('adblock-site', !ab.siteAllowed);
  $('sw-all').onclick = () => api.cmd('adblock', !ab.enabled);
  if ($('sw-video')) $('sw-video').onclick = () => api.cmd('adblock-video', !ab.videoAd);
}
$('shield').onclick = () => {
  const box = $('shield-panel');
  renderShieldPanel();
  const r = $('shield').getBoundingClientRect();
  box.style.top = `${r.bottom + 8}px`;
  box.style.left = `${Math.max(8, Math.min(r.right - 330, innerWidth - 338))}px`;
  openLayer('shield-panel');
};

// ---- Lautstärke-Verstärker ----
$('boost-btn').insertAdjacentHTML('afterbegin', icon('speaker'));
function renderBoost(a) {
  const b = $('boost-btn');
  const boost = a.boost || 1;
  b.classList.toggle('show', !!a.audible || boost > 1);
  b.classList.toggle('on', boost > 1);
  $('boost-badge').textContent = boost > 1 ? `${Math.round(boost * 100)}` : '';
  if (!$('boost-panel').hidden) renderBoostPanel();
}
function renderBoostPanel() {
  const boost = (S.active && S.active.boost) || 1;
  const box = $('boost-panel');
  const pct = Math.round(boost * 100);
  if (!box.querySelector('input')) {
    box.innerHTML = `<h3>${icon('speaker', 18)} Lautstärke-Verstärker</h3><div class="big" id="boost-val"></div>
      <input type="range" id="boost-range" min="100" max="600" step="25" aria-label="Verstärkung">
      <div class="presets">${[100, 200, 300, 400, 600].map((v) => `<button class="btn" data-v="${v}">${v} %</button>`).join('')}</div>
      <p>Macht leise Videos lauter – über 100 % hinaus. Gilt für diesen Tab, bis du ihn schließt. Sehr hohe Werte können übersteuern.</p>`;
    $('boost-range').addEventListener('input', (e) => { $('boost-val').textContent = `${e.target.value} %`; api.cmd('boost', Number(e.target.value) / 100); });
    box.querySelectorAll('[data-v]').forEach((el) => el.addEventListener('click', () => api.cmd('boost', Number(el.dataset.v) / 100)));
  }
  $('boost-val').textContent = `${pct} %`;
  if (document.activeElement !== $('boost-range')) $('boost-range').value = pct;
  box.querySelectorAll('[data-v]').forEach((el) => el.classList.toggle('sel', Number(el.dataset.v) === pct));
}
$('boost-btn').onclick = () => {
  const box = $('boost-panel');
  const r = $('boost-btn').getBoundingClientRect();
  box.style.top = `${r.bottom + 8}px`;
  box.style.left = `${Math.max(8, Math.min(r.right - 320, innerWidth - 328))}px`;
  box.style.right = 'auto';
  renderBoostPanel();
  openLayer('boost-panel');
};

// Adressleiste mit Vorschlägen
let sugItems = [];
let sugSel = 0;
addr.addEventListener('focus', () => { editing = true; setTimeout(() => addr.select(), 0); });
addr.addEventListener('blur', () => { editing = false; setTimeout(() => { if (!$('suggest').hidden) closeLayer(); renderNav(); }, 150); });
addr.addEventListener('input', async () => {
  const text = addr.value;
  if (!text.trim()) { if (!$('suggest').hidden) closeLayer(); return; }
  const found = await api.suggest(text);
  if (addr.value !== text) return;
  const looksUrl = /^[^\s]+\.[a-z]{2,}(\/|$)|^[a-z]+:\/\//i.test(text.trim());
  const engine = (S.engines.find((e) => e.id === S.settings.engine) || {}).name || 'Suche';
  sugItems = [{ kind: 'go', text, title: looksUrl ? text : `${text}`, sub: looksUrl ? 'Öffnen' : `Mit ${engine} suchen` },
    ...found.map((f) => ({ kind: 'url', url: f.url, title: f.title || f.url, sub: f.url, bookmark: f.bookmark }))];
  sugSel = 0;
  renderSuggest();
});
addr.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const it = !$('suggest').hidden ? sugItems[sugSel] : null;
    go(it && it.kind === 'url' ? it.url : addr.value, e.altKey);
    e.preventDefault();
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if ($('suggest').hidden) return;
    sugSel = (sugSel + (e.key === 'ArrowDown' ? 1 : -1) + sugItems.length) % sugItems.length;
    renderSuggest();
    e.preventDefault();
  } else if (e.key === 'Escape') {
    addr.value = (S.active && S.active.url) || '';
    closeLayer();
    addr.blur();
  }
});
function go(text, newTab = false) {
  closeLayer();
  editing = false;
  addr.blur();
  if (!text.trim()) return;
  if (newTab) api.cmd('new-tab', text); else api.cmd('navigate', text);
}
function renderSuggest() {
  const box = $('suggest');
  const r = $('omnibox').getBoundingClientRect();
  box.style.left = `${r.left}px`; box.style.top = `${r.bottom + 6}px`; box.style.width = `${r.width}px`;
  box.innerHTML = sugItems.map((s, i) => `<div class="sug${i === sugSel ? ' sel' : ''}" data-i="${i}" role="option">
      <span class="ico">${icon(s.kind === 'go' ? (s.sub === 'Öffnen' ? 'globe' : 'search') : (s.bookmark ? 'star' : 'globe'), 16, s.bookmark)}</span>
      <span class="t">${esc(s.title)}</span><span class="u">${esc(s.kind === 'go' ? s.sub : s.sub.replace(/^https?:\/\/(www\.)?/, ''))}</span></div>`).join('');
  box.querySelectorAll('.sug').forEach((el) => el.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const it = sugItems[Number(el.dataset.i)];
    go(it.kind === 'url' ? it.url : it.text);
  }));
  if ($('suggest').hidden) openLayer('suggest');
}
api.on('focus-address', () => { addr.focus(); addr.select(); });

// ---- Lesezeichenleiste ----
function letterFor(title, url) {
  const t = (title || url || '?').replace(/^https?:\/\/(www\.)?/, '').trim();
  return esc((t[0] || '?').toUpperCase());
}
function faviconFor(url) {
  // Favicon über die Seite selbst – ohne Dritt-Dienst
  try { return `${new URL(url).origin}/favicon.ico`; } catch (_) { return ''; }
}
function renderBookmarks() {
  const bar = $('bookmarks');
  bar.hidden = !S.settings.bookmarksBar;
  const sig = JSON.stringify(S.bookmarks);
  if (bar.dataset.sig === sig) return;
  bar.dataset.sig = sig;
  if (!S.bookmarks.length) {
    bar.innerHTML = '<span class="bm-empty">Lesezeichen mit dem Stern in der Adressleiste hinzufügen</span>';
    return;
  }
  const folderNames = [];
  for (const b of S.bookmarks) if (b.folder && !folderNames.includes(b.folder)) folderNames.push(b.folder);
  // Ordner zuerst (wie in anderen Browsern), dann die einzelnen Lesezeichen
  bar.innerHTML = folderNames.map((f) => `<button class="bm folder" data-folder="${esc(f)}" title="${esc(f)}">
      <span class="ico">${icon('folder', 16)}</span><span>${esc(f)}</span></button>`).join('')
    + S.bookmarks.map((b, i) => (b.folder ? '' : `<button class="bm" data-i="${i}" title="${esc(b.title)}\n${esc(b.url)}">
      <span class="ico"><img src="${esc(b.icon || faviconFor(b.url))}" width="16" height="16" alt="" data-letter="${letterFor(b.title, b.url)}" data-fallback="${b.icon ? esc(faviconFor(b.url)) : ''}"></span>
      <span>${esc(b.title)}</span></button>`)).join('');
  bar.querySelectorAll('img[data-letter]').forEach((img) => {
    const toLetter = () => {
      const d = document.createElement('div');
      d.className = 'letter';
      d.textContent = img.dataset.letter;
      img.replaceWith(d);
    };
    // erst das Symbol der Seite, dann /favicon.ico, sonst der Anfangsbuchstabe
    img.addEventListener('error', function onErr() {
      if (img.dataset.fallback) { const f = img.dataset.fallback; img.dataset.fallback = ''; img.src = f; return; }
      img.removeEventListener('error', onErr);
      toLetter();
    });
    // Winzige oder leere Bilder (z. B. 1×1-Platzhalter) gelten nicht als Symbol
    img.addEventListener('load', () => { if (img.naturalWidth < 8 || img.naturalHeight < 8) toLetter(); }, { once: true });
  });
  bar.querySelectorAll('.bm.folder').forEach((el) => {
    const f = el.dataset.folder;
    el.addEventListener('click', () => {
      const r = el.getBoundingClientRect();
      const items = S.bookmarks.filter((b) => b.folder === f);
      showMenu($('ctx'), [
        ...items.map((b) => ({ label: b.title || b.url, icon: 'globe', run: () => api.cmd('open-url', b.url, true), ctx: b })),
        '-',
        { label: `Alle ${items.length} in Tabs öffnen`, icon: 'plus', enabled: items.length > 0, run: () => items.forEach((b) => api.cmd('open-url-tab', b.url, true)) },
      ], r.left, r.bottom + 4);
      // Rechtsklick auf ein Lesezeichen im Ordner
      $('ctx').querySelectorAll('.item').forEach((btn, i) => {
        if (i < items.length) btn.addEventListener('contextmenu', (e) => { e.preventDefault(); bookmarkMenu(items[i], -1, e.clientX, e.clientY); });
      });
    });
    el.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showMenu($('ctx'), [
        { label: 'Ordner umbenennen …', run: () => renameFolder(f) },
        { label: 'Ordner auflösen', icon: 'trash', run: () => api.cmd('folder-dissolve', f) },
      ], e.clientX, e.clientY);
    });
  });
  bar.querySelectorAll('.bm:not(.folder)').forEach((el) => {
    const b = S.bookmarks[Number(el.dataset.i)];
    el.addEventListener('click', (e) => api.cmd(e.ctrlKey ? 'open-url-tab' : 'open-url', b.url, true));
    el.addEventListener('auxclick', (e) => { if (e.button === 1) api.cmd('open-url-tab', b.url, true); });
    el.addEventListener('contextmenu', (e) => { e.preventDefault(); bookmarkMenu(b, Number(el.dataset.i), e.clientX, e.clientY); });
  });
}
function bookmarkMenu(b, i, x, y) {
  const folderNames = [...new Set(S.bookmarks.map((v) => v.folder).filter(Boolean))];
  showMenu($('ctx'), [
    { label: 'Öffnen', icon: 'open', run: () => api.cmd('open-url', b.url) },
    { label: 'In neuem Tab öffnen', icon: 'plus', run: () => api.cmd('open-url-tab', b.url, false) },
    '-',
    { label: 'Umbenennen …', run: () => renameBookmark(b) },
    ...(i >= 0 ? [
      { label: 'Nach links', enabled: i > 0, run: () => api.cmd('move-bookmark', b.url, i - 1) },
      { label: 'Nach rechts', enabled: i < S.bookmarks.length - 1, run: () => api.cmd('move-bookmark', b.url, i + 1) },
    ] : []),
    { html: '<div class="label">IN ORDNER</div>' },
    ...folderNames.filter((f) => f !== b.folder).map((f) => ({ label: f, icon: 'folder', run: () => api.cmd('bm-folder', b.url, f) })),
    { label: 'Neuer Ordner …', icon: 'plus', run: () => newFolder(b) },
    ...(b.folder ? [{ label: 'Aus dem Ordner nehmen', run: () => api.cmd('bm-folder', b.url, '') }] : []),
    '-',
    { label: 'Entfernen', icon: 'trash', run: () => api.cmd('remove-bookmark', b.url) },
  ], x, y);
}
function newFolder(b) {
  dialog(`<h3>Neuer Ordner</h3><input type="text" id="dlg-input" placeholder="Name des Ordners">
    <div class="row"><button class="btn" id="dlg-no">Abbrechen</button><button class="btn primary" id="dlg-yes">Anlegen</button></div>`,
  () => { const v = $('dlg-input').value.trim(); if (v) api.cmd('bm-folder', b.url, v); });
}
function renameFolder(f) {
  dialog(`<h3>Ordner umbenennen</h3><input type="text" id="dlg-input" value="${esc(f)}">
    <div class="row"><button class="btn" id="dlg-no">Abbrechen</button><button class="btn primary" id="dlg-yes">Speichern</button></div>`,
  () => { const v = $('dlg-input').value.trim(); if (v) api.cmd('folder-rename', f, v); });
}
function renameBookmark(b) {
  dialog(`<h3>Lesezeichen umbenennen</h3><input type="text" id="dlg-input" value="${esc(b.title)}">
    <div class="row"><button class="btn" id="dlg-no">Abbrechen</button><button class="btn primary" id="dlg-yes">Speichern</button></div>`,
  () => { api.cmd('rename-bookmark', b.url, $('dlg-input').value); });
}

// ---- Menüs ----
function showMenu(box, items, x, y) {
  box.innerHTML = '';
  for (const it of items) {
    if (it === '-') { box.insertAdjacentHTML('beforeend', '<div class="sep"></div>'); continue; }
    if (it.html) { const d = document.createElement('div'); d.innerHTML = it.html; box.append(...d.childNodes); continue; }
    const b = document.createElement('button');
    b.className = 'item';
    b.setAttribute('role', 'menuitem');
    b.disabled = it.enabled === false;
    b.innerHTML = `<span class="ico">${it.check !== undefined ? (it.check ? '✓' : '') : (it.icon ? icon(it.icon, 16) : '')}</span>
      <span class="grow">${esc(it.label)}</span>${it.key ? `<span class="key">${esc(it.key)}</span>` : ''}`;
    b.addEventListener('click', () => { if (!it.keep) closeLayer(); it.run(); });
    box.append(b);
  }
  openLayer(box.id);
  if (x !== undefined) {
    const w = box.offsetWidth; const h = box.offsetHeight;
    box.style.left = `${Math.max(6, Math.min(x, innerWidth - w - 6))}px`;
    box.style.top = `${Math.max(6, Math.min(y, innerHeight - h - 6))}px`;
    box.style.right = 'auto';
  }
}

$('menu-btn').onclick = () => {
  const a = S.active || {};
  const m = $('menu');
  m.style.top = `${$('navbar').getBoundingClientRect().bottom - 4}px`;
  m.style.right = '8px'; m.style.left = 'auto';
  showMenu(m, [
    { label: 'Neuer Tab', icon: 'plus', key: 'Strg+T', run: () => api.cmd('new-tab') },
    { label: 'Neues Fenster', icon: 'window', key: 'Strg+N', run: () => api.cmd('new-window') },
    { label: 'Neues privates Fenster', icon: 'privat', key: 'Strg+Umschalt+N', run: () => api.cmd('new-private') },
    '-',
    { html: `<div class="zoomrow"><span class="grow">Zoom</span>
      <button class="icon small" id="z-out" aria-label="Verkleinern">${icon('minus', 16)}</button>
      <span class="val">${a.zoom || 100} %</span>
      <button class="icon small" id="z-in" aria-label="Vergrößern">${icon('plus', 16)}</button>
      <button class="icon small" id="z-full" title="Vollbild (F11)" aria-label="Vollbild">${icon('full', 16)}</button></div>` },
    '-',
    { label: 'Downloads', icon: 'download', key: 'Strg+J', run: () => openDownloads() },
    { label: 'Auf der Seite suchen', icon: 'search', key: 'Strg+F', run: () => openFind() },
    { label: 'Drucken …', icon: 'print', key: 'Strg+P', run: () => api.cmd('print') },
    { label: 'Leseansicht', icon: 'reader', enabled: !!a.web, run: () => api.cmd('reader') },
    { label: 'Seite übersetzen', icon: 'translate', enabled: !!a.web, run: () => api.cmd('translate') },
    { label: 'Ganze Seite als Bild speichern', icon: 'camera', enabled: !!a.web, run: () => api.cmd('fullshot') },
    { label: 'Entwicklerwerkzeuge', icon: 'code', key: 'F12', run: () => api.cmd('devtools') },
    '-',
    { label: 'Lesezeichen importieren …', icon: 'import', run: () => openImport() },
    { label: 'Passwörter …', icon: 'key', run: () => openPasswords() },
    '-',
    { label: 'Werbeblocker', check: !!S.settings.adblock, run: () => api.cmd('adblock', !S.settings.adblock) },
    { label: 'Gesponserte Abschnitte überspringen (YouTube)', check: !!S.settings.sponsorblock, run: () => api.cmd('set-setting', 'sponsorblock', !S.settings.sponsorblock) },
    { label: 'Dunkelmodus für helle Seiten', check: !!S.settings.darkPages, run: () => api.cmd('set-setting', 'darkPages', !S.settings.darkPages) },
    ...(S.settings.darkPages && a.web ? [{ label: `Dunkelmodus auf ${a.site || 'dieser Seite'}`, check: !a.darkSkipped, run: () => api.cmd('dark-site', !a.darkSkipped) }] : []),
    { label: 'Unbenutzte Tabs schlafen legen', check: !!S.settings.sleepTabs, run: () => api.cmd('set-setting', 'sleepTabs', !S.settings.sleepTabs) },
    ...(isPrivate ? [] : [{ label: 'Passwörter speichern anbieten', check: !!S.settings.passwords, run: () => api.cmd('set-setting', 'passwords', !S.settings.passwords) }]),
    { label: 'Lesezeichenleiste anzeigen', check: !!S.settings.bookmarksBar, run: () => api.cmd('toggle-bookmarks-bar') },
    { label: 'Tabs beim Start wiederherstellen', check: !!S.settings.restoreSession, run: () => api.cmd('restore-session', !S.settings.restoreSession) },
    { html: '<div class="label">SUCHMASCHINE</div>' },
    ...S.engines.map((e) => ({ label: e.name, check: S.settings.engine === e.id, run: () => api.cmd('engine', e.id) })),
    '-',
    { label: 'Verlauf löschen', icon: 'trash', run: () => api.cmd('clear-history') },
    { label: 'Alle Browserdaten löschen …', icon: 'trash', run: () => confirmClear() },
    '-',
    { label: 'Beenden', icon: 'power', run: () => api.cmd('quit') },
  ]);
  $('z-out').onclick = () => { api.cmd('zoom', -1); setTimeout(() => $('menu-btn').onclick(), 60); };
  $('z-in').onclick = () => { api.cmd('zoom', 1); setTimeout(() => $('menu-btn').onclick(), 60); };
  $('z-full').onclick = () => { closeLayer(); api.cmd('fullscreen'); };
};

function dialog(html, onYes) {
  const d = $('dialog');
  d.innerHTML = html;
  openLayer('dialog');
  const input = $('dlg-input');
  if (input) { input.focus(); input.select(); input.addEventListener('keydown', (e) => { if (e.key === 'Enter') $('dlg-yes').click(); }); }
  $('dlg-no').onclick = closeLayer;
  $('dlg-yes').onclick = () => { onYes(); closeLayer(); };
}
function confirmClear() {
  dialog(`<h3>Alle Browserdaten löschen?</h3>
    <p>Verlauf, Cookies, Anmeldungen und gespeicherte Seitendaten werden gelöscht. Du wirst auf allen Seiten abgemeldet. Lesezeichen bleiben erhalten.</p>
    <div class="row"><button class="btn" id="dlg-no">Abbrechen</button><button class="btn danger" id="dlg-yes">Löschen</button></div>`,
  () => api.cmd('clear-all'));
}

// ---- Rechtsklick in der Seite ----
api.on('context-menu', ({ x, y, items }) => {
  showMenu($('ctx'), items.map((it) => (it.id === '-' ? '-' : { label: it.label, enabled: it.enabled, run: () => api.cmd('context-action', it.id) })), x, y);
});

// ---- Downloads ----
const fmt = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} kB`);
$('downloads-btn').onclick = () => openDownloads();
api.on('open-downloads', () => openDownloads());
api.on('download-started', () => {
  const b = $('downloads-btn');
  b.classList.remove('pulse'); void b.offsetWidth; b.classList.add('pulse');
});
function openDownloads() {
  const box = $('downloads');
  box.style.top = `${$('navbar').getBoundingClientRect().bottom - 4}px`;
  renderDownloads();
  openLayer('downloads');
}
function renderDownloads() {
  const box = $('downloads');
  const list = S.downloads;
  box.innerHTML = (list.length ? list.map((d) => {
    const pct = d.total ? Math.round((100 * d.received) / d.total) : 0;
    const sub = d.state === 'completed' ? `${fmt(d.received)} · fertig`
      : d.state === 'cancelled' ? 'Abgebrochen' : d.state === 'interrupted' ? 'Unterbrochen'
        : `${fmt(d.received)}${d.total ? ` von ${fmt(d.total)}` : ''}${d.paused ? ' · pausiert' : ''}`;
    const buttons = d.state === 'completed'
      ? `<button class="icon small" data-a="download-open" title="Öffnen">${icon('open', 16)}</button><button class="icon small" data-a="download-show" title="Im Ordner zeigen">${icon('folder', 16)}</button>`
      : d.state === 'progressing'
        ? `<button class="icon small" data-a="download-pause" title="${d.paused ? 'Fortsetzen' : 'Pausieren'}">${icon(d.paused ? 'play' : 'pause', 16)}</button><button class="icon small" data-a="download-cancel" title="Abbrechen">${icon('close', 16)}</button>`
        : '';
    return `<div class="dl" data-id="${d.id}"><div class="info"><div class="name">${esc(d.name)}</div><div class="sub">${sub}</div>
      ${d.state === 'progressing' ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ''}</div>${buttons}</div>`;
  }).join('') : '<div class="dl-empty">Noch keine Downloads</div>')
    + `<div class="sep"></div><div class="dl-foot"><button class="btn" id="dl-folder">Downloads-Ordner</button>
       <button class="btn" id="dl-clear">Liste leeren</button></div>`;
  box.querySelectorAll('[data-a]').forEach((b) => b.addEventListener('click', () => api.cmd(b.dataset.a, Number(b.closest('.dl').dataset.id))));
  box.querySelectorAll('.dl').forEach((el) => el.addEventListener('dblclick', () => api.cmd('download-open', Number(el.dataset.id))));
  $('dl-folder').onclick = () => { closeLayer(); api.cmd('downloads-folder'); };
  $('dl-clear').onclick = () => api.cmd('downloads-clear');
}
function renderDownloadButton() {
  const b = $('downloads-btn');
  b.classList.toggle('show', S.downloads.length > 0);
  const running = S.downloads.filter((d) => d.state === 'progressing' && d.total);
  const pct = running.length ? running.reduce((s, d) => s + d.received / d.total, 0) / running.length : 0;
  $('dl-ring').style.background = running.length
    ? `conic-gradient(var(--accent) ${pct * 360}deg, transparent 0) border-box` : 'none';
  $('dl-ring').style.webkitMask = running.length ? 'radial-gradient(circle, transparent 12px, #000 12.5px)' : 'none';
  if (!$('downloads').hidden) renderDownloads();
}

// ---- Auf der Seite suchen ----
function openFind() {
  $('findbar').hidden = false;
  $('find-input').focus();
  $('find-input').select();
}
api.on('find-open', openFind);
$('find-input').addEventListener('input', () => { api.cmd('find', $('find-input').value, true); if (!$('find-input').value) $('find-count').textContent = ''; });
$('find-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { api.cmd('find', $('find-input').value, !e.shiftKey); e.preventDefault(); }
  if (e.key === 'Escape') closeFind();
});
$('find-next').onclick = () => api.cmd('find', $('find-input').value, true);
$('find-prev').onclick = () => api.cmd('find', $('find-input').value, false);
$('find-close').onclick = () => closeFind();
function closeFind() { $('findbar').hidden = true; $('find-count').textContent = ''; api.cmd('find-stop'); }
api.on('find-result', ({ active, total }) => { $('find-count').textContent = total ? `${active} von ${total}` : 'Keine Treffer'; });

// ---- Berechtigungen ----
const permQueue = [];
api.on('permission', (p) => { permQueue.push(p); showPermission(); });
function showPermission() {
  const p = permQueue[0];
  $('permission').hidden = !p;
  if (!p) return;
  $('perm-text').innerHTML = `<b>${esc(p.origin)}</b> möchte: ${esc(p.label)}`;
  $('perm-remember').checked = true;
}
function answer(allow) {
  const p = permQueue.shift();
  if (p) api.cmd('permission', p.id, { allow, remember: $('perm-remember').checked });
  showPermission();
}
$('perm-allow').onclick = () => answer(true);
$('perm-deny').onclick = () => answer(false);

// ---- Passwort speichern? ----
const pwQueue = [];
api.on('pw-offer', (p) => { if (!pwQueue.some((q) => q.site === p.site && q.user === p.user)) pwQueue.push(p); showPw(); });
function showPw() {
  const p = pwQueue[0];
  $('pwbar').hidden = !p;
  if (!p) return;
  $('pw-text').innerHTML = `${icon('key', 15)} ${p.update ? 'Passwort aktualisieren' : 'Passwort speichern'} für <b>${esc(p.user || 'ohne Namen')}</b> auf <b>${esc(p.site)}</b>?`;
}
function pwAnswer(choice) { const p = pwQueue.shift(); if (p) api.cmd('pw-answer', p.id, choice); showPw(); }
$('pw-yes').onclick = () => pwAnswer('save');
$('pw-no').onclick = () => pwAnswer('no');
$('pw-never').onclick = () => pwAnswer('never');

async function openPasswords() {
  const data = (await api.call('passwords-list')) || { items: [], never: [], available: false };
  const rows = data.items;
  dialog(`<h3>${icon('key', 18)} Gespeicherte Passwörter</h3>
    ${data.available ? '' : '<p class="hint">Der Schlüsselbund des Systems ist nicht erreichbar – Passwörter können gerade nicht gespeichert werden.</p>'}
    <div class="pwlist">${rows.length ? rows.map((r, i) => `<div class="pw" data-i="${i}"><div class="info"><div>${esc(r.site)}</div>
      <div class="sub">${esc(r.user || '(ohne Namen)')}</div></div>
      <button class="btn" data-a="copy">Kopieren</button><button class="icon small" data-a="del" title="Löschen">${icon('trash', 16)}</button></div>`).join('')
    : '<p>Noch keine Passwörter gespeichert. Wenn du dich auf einer Seite anmeldest, fragt der Browser, ob er das Passwort speichern soll.</p>'}</div>
    ${data.never.length ? `<div class="label">NIE SPEICHERN</div><div class="pwlist">${data.never.map((o, i) => `<div class="pw" data-n="${i}"><div class="info"><div>${esc(o.replace(/^https?:\/\/(www\.)?/, ''))}</div></div>
      <button class="icon small" data-a="unnever" title="Entfernen">${icon('close', 16)}</button></div>`).join('')}</div>` : ''}
    <p class="hint">Passwörter werden mit dem Schlüsselbund deines Benutzerkontos verschlüsselt. Beim Kopieren wird die Zwischenablage nach 30 Sekunden geleert.</p>
    <div class="row"><button class="btn" id="dlg-no">Schließen</button><button class="btn primary" id="dlg-yes">Fertig</button></div>`, () => {});
  $('dialog').querySelectorAll('[data-a]').forEach((b) => b.addEventListener('click', () => {
    const row = b.closest('.pw');
    if (b.dataset.a === 'unnever') { api.cmd('pw-never-remove', data.never[Number(row.dataset.n)]); row.remove(); return; }
    const r = rows[Number(row.dataset.i)];
    if (b.dataset.a === 'copy') { api.cmd('pw-copy', r.origin, r.user); toast('Passwort kopiert'); }
    if (b.dataset.a === 'del') { api.cmd('pw-remove', r.origin, r.user); row.remove(); }
  }));
}

// ---- Lesezeichen importieren ----
let importSources = null;
async function loadImportSources() { importSources = (await api.call('import-sources')) || []; return importSources; }
async function openImport() {
  const list = await loadImportSources();
  dialog(`<h3>${icon('import', 18)} Lesezeichen importieren</h3>
    ${list.length ? `<p>Aus welchem Browser? Ordner bleiben erhalten, doppelte Lesezeichen werden übersprungen.</p>
      <div class="implist">${list.map((s, i) => `<button class="btn" data-i="${i}">${esc(s.name)}</button>`).join('')}</div>`
    : '<p>Kein anderer Browser mit Lesezeichen gefunden (Chrome, Chromium, Edge, Brave, Vivaldi, Opera, Firefox, LibreWolf, Zen).</p>'}
    <div class="row"><button class="btn" id="dlg-no">Schließen</button><button class="btn primary" id="dlg-yes" hidden>OK</button></div>`, () => {});
  $('dialog').querySelectorAll('[data-i]').forEach((b) => b.addEventListener('click', () => runImport(list[Number(b.dataset.i)])));
}
async function runImport(src) {
  closeLayer();
  const r = await api.call('import-run', src.id);
  $('importbar').hidden = true;
  if (!r || r.error) toast(`Import ging nicht: ${(r && r.error) || 'unbekannter Fehler'}`);
  else toast(r.count ? `${r.count} Lesezeichen aus ${r.name} importiert` : `Keine neuen Lesezeichen in ${r.name}`);
}
let importOffered = false;
async function maybeOfferImport() {
  if (importOffered || isPrivate || document.body.classList.contains('appmode') || S.settings.importDone !== false) return;
  importOffered = true;
  const list = await loadImportSources();
  if (!list.length || S.settings.importDone) return;
  $('import-text').innerHTML = `${icon('import', 15)} Lesezeichen aus <b>${esc(list[0].name)}</b>${list.length > 1 ? ` (oder ${list.length - 1} weiteren Browsern)` : ''} übernehmen?`;
  $('importbar').hidden = false;
  $('import-yes').onclick = () => (list.length > 1 ? openImport() : runImport(list[0]));
  $('import-no').onclick = () => { $('importbar').hidden = true; api.cmd('import-dismiss'); };
}

// ---- Kurze Hinweise ----
let toastTimer = 0;
function toast(text) {
  const t = $('toast');
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4500);
}
api.on('toast', toast);

// ---- Zustand ----
function applyLook(look, isPriv) {
  if (!look) return;
  document.body.dataset.design = look.design;
  const root = document.body.style;
  root.setProperty('--accent', isPriv ? look.privateColor : look.accentColor);
}

api.on('state', (s) => {
  S = s;
  document.body.classList.toggle('private', s.private);
  applyLook(s.look, s.private);
  renderTabs();
  renderNav();
  renderBookmarks();
  renderDownloadButton();
  maybeOfferImport();
});
window.addEventListener('resize', () => renderTabs());
