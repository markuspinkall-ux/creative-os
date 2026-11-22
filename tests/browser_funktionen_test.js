'use strict';
// Browser: Lesezeichen-Import (Chrome/Firefox), Ordner, Passwörter – ohne Electron prüfbar.
//   node tests/browser_funktionen_test.js
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const APP = path.join(__dirname, '..', 'webbrowser', 'app');
const imp = require(path.join(APP, 'import-bookmarks.js'));
const { Passwords } = require(path.join(APP, 'passwords.js'));

const home = fs.mkdtempSync(path.join(os.tmpdir(), 'bm-'));

// --- Chrome ---
const chromeDir = path.join(home, '.config', 'google-chrome', 'Default');
fs.mkdirSync(chromeDir, { recursive: true });
fs.writeFileSync(path.join(chromeDir, 'Bookmarks'), JSON.stringify({ roots: {
  bookmark_bar: { type: 'folder', children: [
    { type: 'url', name: 'Gibeon', url: 'https://gibeon.de/' },
    { type: 'folder', name: 'Arbeit', children: [
      { type: 'url', name: 'GitHub', url: 'https://github.com/' },
      { type: 'folder', name: 'Tief', children: [{ type: 'url', name: 'Tief drin', url: 'https://tief.de/' }] },
    ] },
    { type: 'url', name: 'Kaputt', url: 'javascript:alert(1)' },
  ] },
  other: { type: 'folder', children: [{ type: 'url', name: 'Rest', url: 'https://rest.de/' }] },
} }));

// --- Firefox ---
const ffDir = path.join(home, '.mozilla', 'firefox', 'abcd.default-release');
fs.mkdirSync(ffDir, { recursive: true });
execFileSync('python3', ['-c', `
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.executescript("""
create table moz_places (id integer primary key, url text);
create table moz_bookmarks (id integer primary key, type int, fk int, parent int, position int, title text, guid text);
insert into moz_bookmarks values (1,2,null,0,0,'','root________');
insert into moz_bookmarks values (2,2,null,1,0,'Menü','menu________');
insert into moz_bookmarks values (3,2,null,1,1,'Symbolleiste','toolbar_____');
insert into moz_bookmarks values (4,2,null,3,0,'Spiele','abc123456789');
insert into moz_places values (10,'https://mozilla.org/');
insert into moz_places values (11,'https://steam.com/');
insert into moz_places values (12,'place:sort=8');
insert into moz_places values (13,'https://menu.de/');
insert into moz_bookmarks values (20,1,10,3,0,'Mozilla','x1');
insert into moz_bookmarks values (21,1,11,4,0,'Steam','x2');
insert into moz_bookmarks values (22,1,12,3,1,'Zuletzt','x3');
insert into moz_bookmarks values (23,1,13,2,0,'Im Menü','x4');
""")
c.commit()
`, path.join(ffDir, 'places.sqlite')]);
fs.writeFileSync(path.join(home, '.mozilla', 'firefox', 'profiles.ini'), '[Profile0]\nName=default\nPath=abcd.default-release\nIsRelative=1\n');

const sources = imp.findSources(home);
const names = sources.map((s) => s.name);
assert.ok(names.some((n) => /Chrome/.test(n)), `Chrome gefunden: ${names}`);
assert.ok(names.some((n) => /Firefox/.test(n)), `Firefox gefunden: ${names}`);

const chrome = imp.readSource(sources.find((s) => /Chrome/.test(s.name)));
assert.deepStrictEqual(chrome.map((b) => [b.title, b.folder]), [
  ['Gibeon', ''], ['GitHub', 'Arbeit'], ['Tief drin', 'Arbeit / Tief'], ['Rest', 'Weitere Lesezeichen']]);

const ff = imp.readSource(sources.find((s) => /Firefox/.test(s.name)));
const ffMap = Object.fromEntries(ff.map((b) => [b.title, b.folder]));
assert.deepStrictEqual(ffMap, { Mozilla: '', Steam: 'Spiele', 'Im Menü': 'Weitere Lesezeichen' });

// --- Store: Import, doppelte, Ordner ---
const { Store } = require(path.join(APP, 'store.js'));
const sdir = fs.mkdtempSync(path.join(os.tmpdir(), 'store-'));
const store = new Store(sdir);
const n1 = store.addImported(chrome);
const n2 = store.addImported(chrome);
assert.strictEqual(n1, 4);
assert.strictEqual(n2, 0, 'keine doppelten');
assert.ok(store.settings.importDone);
assert.ok(store.folders().includes('Arbeit'));
store.renameFolder('Arbeit', 'Job');
assert.ok(store.folders().includes('Job') && !store.folders().includes('Arbeit'));
store.dissolveFolder('Job');
assert.ok(!store.folders().includes('Job'));
store.setBookmarkFolder('https://gibeon.de/', 'Neu');
assert.ok(store.folders().includes('Neu'));

// --- Passwörter (falscher Schlüsselbund, der „verschlüsselt“ umdreht) ---
const fakeSafe = {
  isEncryptionAvailable: () => true,
  encryptString: (s) => Buffer.from([...s].reverse().join('')),
  decryptString: (b) => [...b.toString()].reverse().join(''),
};
const pdir = fs.mkdtempSync(path.join(os.tmpdir(), 'pw-'));
const pw = new Passwords(pdir, fakeSafe);
const o = 'https://login.de';
assert.ok(pw.needsAsk(o, 'markus', 'geheim'));
pw.store(o, 'markus', 'geheim');
assert.ok(!pw.needsAsk(o, 'markus', 'geheim'), 'gleiches Passwort: nicht erneut fragen');
assert.ok(pw.needsAsk(o, 'markus', 'neu'), 'geändertes Passwort: fragen');
assert.deepStrictEqual(pw.users(o), ['markus']);
assert.strictEqual(pw.reveal(o, 'markus'), 'geheim');
const raw = fs.readFileSync(path.join(pdir, 'passwoerter.json'), 'utf8');
assert.ok(!raw.includes('geheim'), 'kein Klartext in der Datei');
assert.strictEqual((fs.statSync(path.join(pdir, 'passwoerter.json')).mode & 0o777), 0o600);
pw.never('https://bank.de');
assert.ok(!pw.needsAsk('https://bank.de', 'x', 'y'));
const noSafe = new Passwords(fs.mkdtempSync(path.join(os.tmpdir(), 'pw2-')), { isEncryptionAvailable: () => false });
assert.ok(!noSafe.needsAsk(o, 'a', 'b'), 'ohne Schlüsselbund nichts speichern');
assert.strictEqual(Passwords.origin('https://a.de/x?y'), 'https://a.de');
assert.strictEqual(Passwords.origin('file:///etc/passwd'), '');

// --- Seitenwerkzeuge ---
const tools = require(path.join(APP, 'page-tools.js'));
assert.strictEqual(tools.youtubeId('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3'), 'dQw4w9WgXcQ');
assert.strictEqual(tools.youtubeId('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
assert.strictEqual(tools.youtubeId('https://example.org/'), '');
for (const s of [tools.PIP_SCRIPT, tools.HAS_VIDEO_SCRIPT, tools.READER_EXTRACT, tools.IS_LIGHT_SCRIPT,
  tools.sponsorScript('x', [{ segment: [1, 2], category: 'sponsor' }])]) new Function(s);
const html = tools.readerPage({ title: '<b>T</b>', html: '<p>x</p>', site: 's', byline: '' }, { light: false });
assert.ok(html.includes('Content-Security-Policy') && !html.includes('<b>T</b>'), 'Titel maskiert, CSP gesetzt');

console.log('Browser-Funktionen: alle Prüfungen bestanden');
