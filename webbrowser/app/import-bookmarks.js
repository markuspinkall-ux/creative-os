'use strict';
// Lesezeichen aus anderen Browsern übernehmen: Chrome, Chromium, Brave, Edge, Vivaldi, Opera
// (Datei „Bookmarks“, JSON) und Firefox (places.sqlite, gelesen über python3/sqlite3 an einer Kopie –
// das Original ist gesperrt, solange Firefox läuft). Auch Flatpak-Installationen.
//
// Ergebnis: [{ title, url, folder }] – folder "" = direkt in die Lesezeichenleiste.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const CHROMIUM = [
  ['Google Chrome', ['.config/google-chrome', '.var/app/com.google.Chrome/config/google-chrome']],
  ['Chromium', ['.config/chromium', '.var/app/org.chromium.Chromium/config/chromium']],
  ['Brave', ['.config/BraveSoftware/Brave-Browser', '.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser']],
  ['Microsoft Edge', ['.config/microsoft-edge', '.var/app/com.microsoft.Edge/config/microsoft-edge']],
  ['Vivaldi', ['.config/vivaldi', '.var/app/com.vivaldi.Vivaldi/config/vivaldi']],
  ['Opera', ['.config/opera', '.var/app/com.opera.Opera/config/opera']],
];
const FIREFOX = [
  ['Firefox', ['.mozilla/firefox', '.config/mozilla/firefox', '.var/app/org.mozilla.firefox/.mozilla/firefox',
    '.var/app/org.mozilla.firefox/config/mozilla/firefox']],
  ['LibreWolf', ['.librewolf', '.var/app/io.gitlab.librewolf-community/.librewolf']],
  ['Zen', ['.zen', '.var/app/app.zen_browser.zen/.zen']],
];

function listDir(dir) {
  try { return fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return []; }
}

// Alle Profile mit Lesezeichen, z. B. { id, name: "Google Chrome", kind: "chromium", file }
function findSources(home = os.homedir()) {
  const out = [];
  for (const [name, dirs] of CHROMIUM) {
    for (const d of dirs) {
      const base = path.join(home, d);
      for (const p of listDir(base)) {
        if (!p.isDirectory() || !(p.name === 'Default' || /^Profile \d+$/.test(p.name))) continue;
        const file = path.join(base, p.name, 'Bookmarks');
        if (fs.existsSync(file)) out.push({ id: file, name: p.name === 'Default' ? name : `${name} (${p.name})`, kind: 'chromium', file });
      }
    }
  }
  for (const [name, dirs] of FIREFOX) {
    for (const d of dirs) {
      const base = path.join(home, d);
      for (const p of listDir(base)) {
        const file = path.join(base, p.name, 'places.sqlite');
        if (p.isDirectory() && fs.existsSync(file)) {
          const prof = p.name.replace(/^[a-z0-9]+\./i, '');
          out.push({ id: file, name: /default/i.test(prof) ? name : `${name} (${prof})`, kind: 'firefox', file });
        }
      }
    }
  }
  return out;
}

const okUrl = (u) => /^https?:\/\//i.test(u || '');

function fromChromium(file) {
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  const out = [];
  const walk = (node, folder) => {
    if (!node) return;
    if (node.type === 'url' && okUrl(node.url)) out.push({ title: node.name || node.url, url: node.url, folder });
    for (const c of node.children || []) {
      if (c.type === 'folder') walk(c, folder ? `${folder} / ${c.name}` : c.name);
      else walk(c, folder);
    }
  };
  const roots = data.roots || {};
  walk(roots.bookmark_bar, '');
  walk(roots.other, 'Weitere Lesezeichen');
  return out;
}

const PY_FIREFOX = `
import json, shutil, sqlite3, sys, tempfile, os
src = sys.argv[1]
tmp = tempfile.mkdtemp()
dst = os.path.join(tmp, "p.sqlite")
shutil.copy2(src, dst)
for ext in ("-wal", "-shm"):
    if os.path.exists(src + ext):
        shutil.copy2(src + ext, dst + ext)
con = sqlite3.connect(dst)
folders = {r[0]: {"parent": r[1], "title": r[2] or "", "guid": r[3]} for r in con.execute(
    "select id, parent, title, guid from moz_bookmarks where type = 2")}
items = [{"parent": r[0], "title": r[1] or "", "url": r[2]} for r in con.execute(
    "select b.parent, b.title, p.url from moz_bookmarks b join moz_places p on b.fk = p.id where b.type = 1 order by b.parent, b.position")]
con.close()
shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps({"folders": folders, "items": items}))
`;

function fromFirefox(file) {
  const raw = execFileSync('python3', ['-c', PY_FIREFOX, file], { encoding: 'utf8', timeout: 20000, maxBuffer: 64 * 1024 * 1024 });
  const { folders, items } = JSON.parse(raw);
  const ROOTS = { toolbar_____: '', menu________: 'Weitere Lesezeichen', unfiled_____: 'Weitere Lesezeichen', mobile______: 'Handy' };
  const nameOf = (id) => {
    const parts = [];
    let f = folders[id];
    for (let guard = 0; f && guard < 20; guard += 1) {
      if (f.guid in ROOTS) { if (ROOTS[f.guid]) parts.unshift(ROOTS[f.guid]); break; }
      if (f.guid === 'root________') break;
      parts.unshift(f.title);
      f = folders[f.parent];
    }
    return parts.join(' / ');
  };
  return items.filter((i) => okUrl(i.url) && !/^place:/.test(i.url))
    .map((i) => ({ title: i.title || i.url, url: i.url, folder: nameOf(i.parent) }));
}

function readSource(src) {
  return src.kind === 'firefox' ? fromFirefox(src.file) : fromChromium(src.file);
}

module.exports = { findSources, readSource, fromChromium, fromFirefox };
