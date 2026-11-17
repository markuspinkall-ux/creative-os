'use strict';
// Prüft den Orbit Messenger mit zwei echten Diensten in einem lokalen Test-Netz (HyperDHT-Testnet):
// Einrichten, Anfrage, Annehmen, Nachricht, Warteschlange bei ausgeschaltetem Empfänger, Gelesen.
//   node tools/messenger-test.js   (im Ordner mit messenger/daemon/node_modules)
const path = require('path');
const os = require('os');
const fs = require('fs');
const { spawn, execFileSync } = require('child_process');

const DAEMON = path.join(__dirname, '..', 'messenger', 'daemon', 'index.js');
const createTestnet = require(path.join(__dirname, '..', 'messenger', 'daemon', 'node_modules', 'hyperdht', 'testnet'));

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'orbit-messenger-test-'));
let failures = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function check(name, ok) {
  console.log(`${ok ? 'ok    ' : 'FEHLER'} ${name}`);
  if (!ok) failures += 1;
}

function env(who, bootstrap) {
  return Object.assign({}, process.env, {
    ORBIT_MESSENGER_DATA: path.join(root, who),
    ORBIT_MESSENGER_SOCKET: path.join(root, `${who}.sock`),
    ORBIT_MESSENGER_BOOTSTRAP: JSON.stringify(bootstrap),
    ORBIT_MESSENGER_NO_NOTIFY: '1',
    ORBIT_MESSENGER_REFRESH_MS: '2000'
  });
}

function start(who, bootstrap) {
  const p = spawn(process.execPath, [DAEMON], { env: env(who, bootstrap), stdio: ['ignore', 'pipe', 'pipe'] });
  p.stdout.on('data', (d) => process.stdout.write(`[${who}] ${d}`));
  p.stderr.on('data', (d) => process.stdout.write(`[${who}!] ${d}`));
  return p;
}

function cmd(who, bootstrap, obj) {
  const out = execFileSync(process.execPath, [DAEMON, '--cli', JSON.stringify(obj)], { env: env(who, bootstrap) });
  return JSON.parse(out.toString());
}

async function until(what, fn, ms) {
  const end = Date.now() + (ms || 30000);
  while (Date.now() < end) {
    try { if (fn()) return true; } catch (_) { /* Dienst startet noch */ }
    await sleep(300);
  }
  console.log(`  (Zeit abgelaufen: ${what})`);
  return false;
}

async function main() {
  const testnet = await createTestnet(3);
  const bs = testnet.bootstrap;
  let a = start('a', bs);
  let b = start('b', bs);
  await until('Dienste bereit', () => cmd('a', bs, { cmd: 'state' }) && cmd('b', bs, { cmd: 'state' }), 10000);

  const sa = cmd('a', bs, { cmd: 'setup', name: 'Markus' });
  const sb = cmd('b', bs, { cmd: 'setup', name: 'Jonas Ärger' });
  check('Orbit-ID aus dem Namen + 4 Ziffern', /^markus\.orbitos\d{4}$/.test(sa.me.id) && /^jonasaerger\.orbitos\d{4}$/.test(sb.me.id));
  console.log(`  A = ${sa.me.id}, B = ${sb.me.id}`);

  let err = '';
  try { cmd('a', bs, { cmd: 'add', id: 'keine-id' }); } catch (e) { err = String(e.stdout); }
  check('Falsche ID wird abgelehnt', err.includes('keine Orbit-ID'));

  cmd('a', bs, { cmd: 'add', id: sb.me.id });
  check('B bekommt die Anfrage', await until('Anfrage', () =>
    cmd('b', bs, { cmd: 'state' }).contacts.some((c) => c.id === sa.me.id && c.status === 'incoming' && c.name === 'Markus')));
  cmd('b', bs, { cmd: 'accept', id: sa.me.id });
  check('A sieht die Annahme', await until('Annahme', () =>
    cmd('a', bs, { cmd: 'state' }).contacts.some((c) => c.id === sb.me.id && c.status === 'accepted' && c.online)));

  cmd('a', bs, { cmd: 'send', id: sb.me.id, text: 'Hallo Jonas!' });
  check('B empfängt die Nachricht', await until('Nachricht', () =>
    cmd('b', bs, { cmd: 'messages', id: sa.me.id }).some((m) => m.text === 'Hallo Jonas!' && !m.me)));
  check('A sieht „zugestellt“', await until('zugestellt', () =>
    cmd('a', bs, { cmd: 'messages', id: sb.me.id }).some((m) => m.text === 'Hallo Jonas!' && m.state === 'delivered')));
  check('B hat 1 ungelesene', cmd('b', bs, { cmd: 'state' }).unread === 1);

  // Warteschlange: B ist aus
  b.kill('SIGTERM');
  await new Promise((r) => b.once('exit', r));
  check('A sieht B offline', await until('offline', () =>
    !cmd('a', bs, { cmd: 'state' }).contacts.find((c) => c.id === sb.me.id).online, 20000));
  cmd('a', bs, { cmd: 'send', id: sb.me.id, text: 'Bist du da?' });
  const q = cmd('a', bs, { cmd: 'messages', id: sb.me.id }).find((m) => m.text === 'Bist du da?');
  check('Nachricht wartet in der Warteschlange', q && q.state === 'queued' && cmd('a', bs, { cmd: 'state' }).queued === 1);
  await sleep(1500);
  b = start('b', bs);
  check('Nach dem Start von B kommt sie an', await until('Warteschlange', () =>
    cmd('b', bs, { cmd: 'messages', id: sa.me.id }).some((m) => m.text === 'Bist du da?'), 45000));
  check('… und A sieht „zugestellt“', await until('zugestellt 2', () =>
    cmd('a', bs, { cmd: 'messages', id: sb.me.id }).every((m) => m.state !== 'queued')));

  cmd('b', bs, { cmd: 'read', id: sa.me.id });
  check('A sieht „gelesen“', await until('gelesen', () =>
    cmd('a', bs, { cmd: 'messages', id: sb.me.id }).every((m) => m.state === 'read')));
  check('Ungelesen bei B wieder 0', cmd('b', bs, { cmd: 'state' }).unread === 0);

  // Ein Fremder ohne angenommene Anfrage kann nicht schreiben
  const c = start('c', bs);
  await until('C bereit', () => cmd('c', bs, { cmd: 'state' }), 10000);
  cmd('c', bs, { cmd: 'setup', name: 'Fremd' });
  err = '';
  try { cmd('c', bs, { cmd: 'send', id: sa.me.id, text: 'Spam' }); } catch (e) { err = String(e.stdout); }
  check('Fremde können ohne Annahme nicht schreiben', err.includes('Kein angenommener Kontakt'));

  // Identität und Kontakte überleben einen Neustart
  const keep = cmd('b', bs, { cmd: 'state' });
  check('Kontakt bleibt gespeichert', keep.contacts.some((x) => x.id === sa.me.id && x.status === 'accepted'));
  const mode = fs.statSync(path.join(root, 'a', 'identity.json')).mode & 0o777;
  check('Schlüssel nur für den Besitzer lesbar (600)', mode === 0o600);

  for (const p of [a, b, c]) p.kill('SIGTERM');
  await sleep(500);
  await testnet.destroy();
  console.log(failures ? `Messenger: ${failures} Prüfung(en) FEHLGESCHLAGEN` : 'Messenger: alle Prüfungen bestanden');
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
