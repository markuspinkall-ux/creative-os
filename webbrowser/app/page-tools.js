'use strict';
// Werkzeuge für Webseiten: Bild im Bild, Leseansicht, Übersetzen, SponsorBlock (YouTube),
// Dunkelmodus für Webseiten und die ganze Seite als Bild.

const fs = require('fs');
const path = require('path');

// ---- Bild im Bild ---------------------------------------------------------------------------------
// Das größte laufende (sonst größte) Video der Seite – braucht eine „Nutzer-Geste“, darum
// executeJavaScript(…, true) aus einem Klick heraus.
const PIP_SCRIPT = `(() => {
  if (document.pictureInPictureElement) { document.exitPictureInPicture(); return 'aus'; }
  const vids = [...document.querySelectorAll('video')].filter((v) => v.readyState > 0 && !v.disablePictureInPicture);
  if (!vids.length) return 'keins';
  vids.sort((a, b) => (!b.paused - !a.paused) || (b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight));
  return vids[0].requestPictureInPicture().then(() => 'an', () => 'fehler');
})()`;
const HAS_VIDEO_SCRIPT = "document.querySelectorAll('video').length > 0";

// ---- Leseansicht ----------------------------------------------------------------------------------
// Sucht den Textblock mit den meisten Absätzen und baut daraus eine ruhige Seite im Gibeon-Look.
const READER_EXTRACT = `(() => {
  const score = (el) => [...el.querySelectorAll(':scope > p, :scope > div > p')].reduce((n, p) => n + (p.innerText || '').trim().length, 0);
  const cands = [...document.querySelectorAll('article, main, [role=main], .post, .article, .content, .entry-content, #content, section, div')];
  let best = null, bestScore = 0;
  for (const el of cands) { const s = score(el); if (s > bestScore) { best = el; bestScore = s; } }
  if (!best || bestScore < 400) return null;
  const clone = best.cloneNode(true);
  clone.querySelectorAll('script, style, noscript, iframe, form, button, nav, aside, footer, header, svg, [aria-hidden=true], .ad, .ads, [class*=share], [class*=comment]').forEach((e) => e.remove());
  clone.querySelectorAll('*').forEach((e) => {
    for (const a of [...e.attributes]) if (!['href', 'src', 'alt', 'srcset'].includes(a.name)) e.removeAttribute(a.name);
  });
  clone.querySelectorAll('img').forEach((img) => { if (img.getAttribute('src') && !/^https?:/.test(img.getAttribute('src'))) img.src = new URL(img.getAttribute('src'), location.href).href; });
  clone.querySelectorAll('a').forEach((a) => { if (a.getAttribute('href')) a.href = new URL(a.getAttribute('href'), location.href).href; });
  const h1 = document.querySelector('h1');
  return { title: (h1 && h1.innerText.trim()) || document.title, site: location.hostname.replace(/^www\\./, ''), url: location.href, html: clone.innerHTML };
})()`;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function readerPage(art, look) {
  const light = look && look.light;
  const bg = light ? '#f4f7fb' : '#12151b';
  const fg = light ? '#1c2433' : '#dce6ff';
  const muted = light ? '#5b667e' : '#8f9ab3';
  const accent = (look && look.accentColor) || '#8fb3ff';
  // Inhalt kommt aus der Seite – Skripte sind entfernt, zusätzlich verbietet die CSP alles Ausführbare
  return `<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: http: data:; style-src 'unsafe-inline'">
<title>${esc(art.title)} – Leseansicht</title>
<style>
body{margin:0;background:${bg};color:${fg};font:19px/1.7 Georgia,"Liberation Serif",serif}
main{max-width:720px;margin:0 auto;padding:48px 24px 96px}
.site{font:600 13px/1.4 Arial,sans-serif;color:${accent};letter-spacing:.4px;text-transform:uppercase}
h1{font:700 34px/1.25 Arial,sans-serif;margin:10px 0 28px}
a{color:${accent}} img,figure,video{max-width:100%;height:auto;border-radius:12px}
h2,h3{font-family:Arial,sans-serif;line-height:1.3} blockquote{border-left:3px solid ${accent};margin:0;padding-left:18px;color:${muted}}
pre,code{font-size:15px;background:${light ? '#e3e9f2' : '#1c2029'};border-radius:8px;padding:2px 6px} pre{padding:12px;overflow:auto}
.orig{font:13px Arial,sans-serif;color:${muted};margin-top:48px}
</style></head><body><main>
<div class="site">${esc(art.site)}</div><h1>${esc(art.title)}</h1>
${art.html}
<p class="orig">Original: <a href="${esc(art.url)}">${esc(art.url)}</a></p>
</main></body></html>`;
}

// ---- Übersetzen -------------------------------------------------------------------------------------
const translatePageUrl = (url) => `https://translate.google.com/translate?sl=auto&tl=de&u=${encodeURIComponent(url)}`;
const translateTextUrl = (text) => `https://translate.google.com/?sl=auto&tl=de&op=translate&text=${encodeURIComponent(text.slice(0, 4000))}`;

// ---- SponsorBlock (YouTube) ---------------------------------------------------------------------
// Gesponserte Abschnitte überspringen – Daten von sponsor.ajay.app (Gemeinschaftsprojekt, ohne Konto).
const SB_CATEGORIES = ['sponsor', 'selfpromo', 'interaction', 'intro', 'outro'];
function youtubeId(url) {
  try {
    const u = new URL(url);
    if (!/(^|\.)youtube\.com$/.test(u.hostname)) return '';
    if (u.pathname === '/watch') return u.searchParams.get('v') || '';
    const m = /^\/(shorts|live)\/([\w-]{6,})/.exec(u.pathname);
    return m ? m[2] : '';
  } catch (_) { return ''; }
}
async function sponsorSegments(net, id) {
  const url = `https://sponsor.ajay.app/api/skipSegments?videoID=${encodeURIComponent(id)}&categories=${encodeURIComponent(JSON.stringify(SB_CATEGORIES))}`;
  const r = await net.fetch(url);
  if (r.status === 404) return [];
  if (!r.ok) throw new Error(`SponsorBlock ${r.status}`);
  const data = await r.json();
  return (Array.isArray(data) ? data : []).map((s) => ({ start: s.segment[0], end: s.segment[1], cat: s.category }))
    .filter((s) => s.end > s.start);
}
// Läuft in einer eigenen Welt der Seite: springt über die Abschnitte, zeigt kurz einen Hinweis
function sponsorScript(id, segs) {
  return `(() => {
    const id = ${JSON.stringify(id)}, segs = ${JSON.stringify(segs)};
    window.__gibeonSB = { id, segs };
    if (window.__gibeonSBTimer) return;
    const names = { sponsor: 'Sponsor', selfpromo: 'Eigenwerbung', interaction: 'Abo-Aufruf', intro: 'Intro', outro: 'Abspann' };
    const toast = (t) => {
      let el = document.getElementById('gibeon-sb'); if (!el) { el = document.createElement('div'); el.id = 'gibeon-sb';
        el.style.cssText = 'position:fixed;left:50%;bottom:90px;transform:translateX(-50%);z-index:2147483647;background:#1c2029;color:#dce6ff;font:14px Arial,sans-serif;padding:9px 16px;border-radius:18px;border:1px solid #8fb3ff;pointer-events:none;transition:opacity .4s';
        document.documentElement.appendChild(el); }
      el.textContent = t; el.style.opacity = '1'; clearTimeout(el._t); el._t = setTimeout(() => { el.style.opacity = '0'; }, 2200);
    };
    window.__gibeonSBTimer = setInterval(() => {
      const s = window.__gibeonSB; const v = document.querySelector('video');
      if (!s || !v || v.paused) return;
      const cur = new URLSearchParams(location.search).get('v') || (location.pathname.split('/')[2] || '');
      if (cur !== s.id) return;
      for (const g of s.segs) {
        if (v.currentTime >= g.start && v.currentTime < g.end - 0.3) {
          v.currentTime = g.end;
          toast('Übersprungen: ' + (names[g.cat] || g.cat));
          break;
        }
      }
    }, 300);
  })()`;
}

// ---- Dunkelmodus für Webseiten -------------------------------------------------------------------
// Nur für Seiten ohne eigenes dunkles Aussehen: Farben umkehren, Bilder/Videos zurückdrehen.
const IS_LIGHT_SCRIPT = `(() => {
  const c = getComputedStyle(document.body || document.documentElement).backgroundColor;
  const html = getComputedStyle(document.documentElement).backgroundColor;
  const pick = (/rgba\\(0, 0, 0, 0\\)|transparent/.test(c) ? html : c);
  const m = pick.match(/\\d+(\\.\\d+)?/g);
  if (!m || (m[3] !== undefined && Number(m[3]) === 0)) return true;      // nichts gesetzt = weiß
  const [r, g, b] = m.map(Number);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150;
})()`;
const DARK_CSS = `
html { filter: invert(0.9) hue-rotate(180deg) !important; background: #fff !important; }
img, video, picture, canvas, iframe, svg image, [style*="background-image"], embed, object { filter: invert(1) hue-rotate(180deg) !important; }
`;

// ---- Ganze Seite als Bild ------------------------------------------------------------------------
async function fullPageShot(wc, dir) {
  const dbg = wc.debugger;
  let attached = false;
  try {
    if (!dbg.isAttached()) { dbg.attach('1.3'); attached = true; }
    const m = await dbg.sendCommand('Page.getLayoutMetrics');
    const size = m.cssContentSize || m.contentSize;
    const width = Math.ceil(size.width);
    const height = Math.min(Math.ceil(size.height), 16000);     // sehr lange Seiten: bis 16 000 Pixel
    const shot = await dbg.sendCommand('Page.captureScreenshot', {
      format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width, height, scale: 1 },
    });
    fs.mkdirSync(dir, { recursive: true });
    const host = (() => { try { return new URL(wc.getURL()).hostname.replace(/^www\./, ''); } catch (_) { return 'Seite'; } })();
    const stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19);
    const file = path.join(dir, `Webseite ${host} ${stamp}.png`);
    fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
    return file;
  } finally {
    if (attached) { try { dbg.detach(); } catch (_) { /* schon weg */ } }
  }
}

module.exports = {
  PIP_SCRIPT, HAS_VIDEO_SCRIPT, READER_EXTRACT, readerPage, translatePageUrl, translateTextUrl,
  youtubeId, sponsorSegments, sponsorScript, IS_LIGHT_SCRIPT, DARK_CSS, fullPageShot, SB_CATEGORIES,
};
