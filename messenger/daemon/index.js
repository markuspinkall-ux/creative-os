#!/usr/bin/env node
'use strict';
// Orbit OS Messenger – Hintergrunddienst
//
// Jede Installation hat ein Schlüsselpaar und eine Orbit-ID (z. B. markus.orbitos2801).
// Rechner finden sich über ein verteiltes Netz (Hyperswarm/HyperDHT, kein eigener Server) und
// verbinden sich direkt; die Verbindung ist mit den Schlüsseln beider Rechner verschlüsselt
// (Noise). Ist der Empfänger offline, bleibt die Nachricht in der Warteschlange und geht raus,
// sobald beide online sind. Kontakte entstehen nur über angenommene Anfragen; danach ist der
// Schlüssel des Kontakts fest gemerkt (niemand kann sich als er ausgeben).
//
// Oberfläche (Tray, Fenster) spricht über einen Unix-Socket mit diesem Dienst (JSON-Zeilen).
//
//   orbit-messenger                 Dienst starten (systemd: orbit-messenger.service)
//   orbit-messenger --cli '<json>'  einen Befehl an den laufenden Dienst schicken (für Tests)

const fs = require('fs');
const os = require('os');
const net = require('net');
const path = require('path');
const crypto = require('crypto');
const { execFile } = require('child_process');

const VERSION = 1;
const ID_RE = /^[a-z0-9]{1,24}\.orbitos[0-9]{4}$/;
const MAX_TEXT = 4000;
const MAX_CHAT = 2000;          // so viele Nachrichten je Chat werden aufbewahrt

const DATA = process.env.ORBIT_MESSENGER_DATA
  || path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share'), 'orbit-messenger');
const SOCK = process.env.ORBIT_MESSENGER_SOCKET
  || path.join(process.env.XDG_RUNTIME_DIR || os.tmpdir(), 'orbit-messenger.sock');

// ---- Hilfen -------------------------------------------------------------------------------------

function slug(name) {
  return String(name || '').toLowerCase()
    .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
    .normalize('NFKD').replace(/[^a-z0-9]+/g, '').slice(0, 24) || 'orbit';
}

function cleanName(name) {
  return String(name || '').replace(/[\u0000-\u001f]/g, '').trim().slice(0, 40);
}

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (_) { return fallback; }
}

function writeJson(file, data, mode) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 1), { mode: mode || 0o600 });
  fs.renameSync(tmp, file);
}

// ---- Gespeicherter Zustand ----------------------------------------------------------------------

const IDENTITY = path.join(DATA, 'identity.json');
const STATE = path.join(DATA, 'state.json');

let identity = readJson(IDENTITY, null);            // {name, id, seed}
const state = Object.assign({ contacts: {}, chats: {}, unread: {}, dnd: false },
  readJson(STATE, {}));

let saveTimer = null;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => writeJson(STATE, state), 150);
}

function saveNow() {
  clearTimeout(saveTimer);
  writeJson(STATE, state);
}

function makeIdentity(name) {
  const digits = String(crypto.randomInt(0, 10000)).padStart(4, '0');
  identity = { name: cleanName(name) || 'Orbit', id: `${slug(name)}.orbitos${digits}`,
               seed: crypto.randomBytes(32).toString('hex'), created: new Date().toISOString() };
  writeJson(IDENTITY, identity, 0o600);
}

// ---- Netz (Hyperswarm) --------------------------------------------------------------------------

let Hyperswarm, b4a, hcrypto;
let swarm = null;
const peers = new Map();        // Schlüssel (hex) -> {conn, key, id, name, buf}
const joined = new Map();       // Orbit-ID -> Discovery
let ui = { active: '', focused: false };

function topic(id) {
  return hcrypto.hash(b4a.from(`orbit-messenger/v${VERSION}/${id}`));
}

function bootstrap() {
  const raw = process.env.ORBIT_MESSENGER_BOOTSTRAP;
  if (!raw) return undefined;
  try { return JSON.parse(raw); } catch (_) { return undefined; }
}

async function startSwarm() {
  if (swarm || !identity) return;
  Hyperswarm = require('hyperswarm');
  b4a = require('b4a');
  hcrypto = require('hypercore-crypto');
  const keyPair = hcrypto.keyPair(b4a.from(identity.seed, 'hex'));
  swarm = new Hyperswarm({ keyPair, bootstrap: bootstrap() });
  swarm.on('connection', onConnection);
  // unter der eigenen ID erreichbar sein …
  swarm.join(topic(identity.id), { server: true, client: false });
  // … und die eigenen Kontakte suchen
  for (const id of Object.keys(state.contacts)) watch(id);
  log(`online als ${identity.id} (Schlüssel ${b4a.toString(keyPair.publicKey, 'hex').slice(0, 12)}…)`);
}

function watch(id) {
  if (!swarm || joined.has(id) || id === identity.id) return;
  joined.set(id, swarm.join(topic(id), { server: false, client: true }));
}

function unwatch(id) {
  const d = joined.get(id);
  if (d) { joined.delete(id); swarm.leave(topic(id)).catch(() => {}); }
}

function onConnection(conn) {
  const key = b4a.toString(conn.remotePublicKey, 'hex');
  const peer = { conn, key, id: '', name: '', buf: '' };
  const old = peers.get(key);
  if (old && old.conn !== conn) old.conn.destroy();
  peers.set(key, peer);
  conn.on('data', (d) => {
    peer.buf += b4a.toString(d);
    if (peer.buf.length > 1_000_000) { conn.destroy(); return; }
    let i;
    while ((i = peer.buf.indexOf('\n')) >= 0) {
      const line = peer.buf.slice(0, i);
      peer.buf = peer.buf.slice(i + 1);
      try { onPeerMessage(peer, JSON.parse(line)); } catch (_) { /* kaputte Zeile */ }
    }
  });
  conn.on('error', () => {});
  conn.on('close', () => {
    if (peers.get(key) === peer) peers.delete(key);
    changed();
  });
  send(peer, { t: 'hello', v: VERSION, id: identity.id, name: identity.name });
}

function send(peer, msg) {
  try { peer.conn.write(b4a.from(JSON.stringify(msg) + '\n')); } catch (_) { /* Verbindung weg */ }
}

function peerFor(id) {
  const c = state.contacts[id];
  for (const p of peers.values()) {
    if (p.id !== id) continue;
    if (c && c.status === 'accepted' && c.key && c.key !== p.key) continue;   // fremder Schlüssel
    return p;
  }
  return null;
}

function isOnline(id) {
  const c = state.contacts[id];
  return !!(c && c.status === 'accepted' && peerFor(id));
}

function chat(id) {
  if (!state.chats[id]) state.chats[id] = [];
  return state.chats[id];
}

function flush(id) {
  const c = state.contacts[id];
  const p = peerFor(id);
  if (!c || c.status !== 'accepted' || !p) return;
  for (const m of chat(id)) {
    if (m.me && m.state === 'queued') send(p, { t: 'msg', mid: m.mid, text: m.text, ts: m.ts });
  }
}

function onPeerMessage(peer, msg) {
  if (!msg || typeof msg.t !== 'string') return;
  if (msg.t === 'hello') {
    if (!ID_RE.test(msg.id || '')) return;
    peer.id = msg.id;
    peer.name = cleanName(msg.name);
    const c = state.contacts[peer.id];
    if (c && c.status === 'outgoing') send(peer, { t: 'request', name: identity.name });
    if (c && c.status === 'accepted' && c.key === peer.key) {
      if (peer.name && c.name !== peer.name) { c.name = peer.name; save(); }
      flush(peer.id);
    }
    changed();
    return;
  }
  if (!peer.id) return;                                   // erst Hallo, dann alles andere
  const c = state.contacts[peer.id];
  const trusted = c && c.status === 'accepted' && c.key === peer.key;
  switch (msg.t) {
    case 'request':
      if (trusted) { send(peer, { t: 'accept' }); break; }
      if (c && c.status === 'accepted') break;            // gleiche ID, anderer Schlüssel: ignorieren
      if (c && c.status === 'outgoing') {                 // beide haben sich angefragt
        Object.assign(c, { status: 'accepted', key: peer.key, name: peer.name || c.name });
        send(peer, { t: 'accept' });
        save(); changed();
        break;
      }
      state.contacts[peer.id] = { id: peer.id, name: peer.name || peer.id, key: peer.key,
                                  status: 'incoming', since: Date.now() };
      watch(peer.id);
      save(); changed();
      notify('Kontaktanfrage', `${peer.name || peer.id} (${peer.id}) möchte mit dir schreiben.`);
      break;
    case 'accept':
      if (c && c.status === 'outgoing') {
        Object.assign(c, { status: 'accepted', key: peer.key, name: peer.name || c.name });
        save(); changed();
        notify('Messenger', `${c.name} hat deine Anfrage angenommen.`);
        flush(peer.id);
      }
      break;
    case 'decline':
      if (c && c.status === 'outgoing') {
        delete state.contacts[peer.id];
        unwatch(peer.id);
        save(); changed();
      }
      break;
    case 'msg': {
      if (!trusted || typeof msg.text !== 'string' || typeof msg.mid !== 'string') break;
      const list = chat(peer.id);
      if (!list.some((m) => m.mid === msg.mid && !m.me)) {
        const text = msg.text.slice(0, MAX_TEXT);
        list.push({ mid: msg.mid.slice(0, 64), me: false, text, ts: Date.now(), sent: Number(msg.ts) || 0 });
        if (list.length > MAX_CHAT) list.splice(0, list.length - MAX_CHAT);
        const looking = ui.focused && ui.active === peer.id;
        if (!looking) {
          state.unread[peer.id] = (state.unread[peer.id] || 0) + 1;
          notify(c.name, text);
        }
        save(); changed();
      }
      send(peer, { t: 'ack', mid: msg.mid });
      break;
    }
    case 'ack':
      if (!trusted) break;
      for (const m of chat(peer.id)) {
        if (m.me && m.mid === msg.mid && m.state === 'queued') { m.state = 'delivered'; save(); changed(); }
      }
      break;
    case 'read':
      if (!trusted || !Array.isArray(msg.mids)) break;
      for (const m of chat(peer.id)) {
        if (m.me && msg.mids.includes(m.mid)) m.state = 'read';
      }
      save(); changed();
      break;
    default:
      break;
  }
}

// ---- Benachrichtigungen -------------------------------------------------------------------------

function notify(title, body) {
  if (state.dnd || process.env.ORBIT_MESSENGER_NO_NOTIFY) return;
  execFile('gdbus', ['call', '--session', '--dest', 'org.freedesktop.Notifications',
    '--object-path', '/org/freedesktop/Notifications', '--method', 'org.freedesktop.Notifications.Notify',
    'Messenger', '0', 'orbit-messenger', String(title).slice(0, 80), String(body).slice(0, 300),
    '[]', '{}', '6000'], { timeout: 5000 }, () => {});
}

// ---- Schnittstelle für Tray und Fenster ---------------------------------------------------------

const clients = new Set();

function snapshot() {
  const contacts = Object.values(state.contacts).map((c) => {
    const list = state.chats[c.id] || [];
    const last = list[list.length - 1] || null;
    return {
      id: c.id, name: c.name || c.id, status: c.status, online: isOnline(c.id),
      unread: state.unread[c.id] || 0,
      last: last ? { text: last.text, me: last.me, ts: last.ts, state: last.state || '' } : null,
      since: c.since || 0,
      fingerprint: c.key ? c.key.slice(0, 8).match(/.{4}/g).join(' ') : ''
    };
  }).sort((a, b) => ((b.last && b.last.ts) || b.since) - ((a.last && a.last.ts) || a.since));
  const queued = Object.values(state.chats).reduce((n, l) => n + l.filter((m) => m.me && m.state === 'queued').length, 0);
  return {
    ready: !!identity,
    me: identity ? { id: identity.id, name: identity.name } : null,
    online: !!swarm,
    dnd: !!state.dnd,
    unread: Object.values(state.unread).reduce((a, b) => a + b, 0),
    queued,
    contacts
  };
}

let changeTimer = null;
function changed() {
  clearTimeout(changeTimer);
  changeTimer = setTimeout(() => {
    const line = JSON.stringify({ ev: 'changed', state: snapshot() }) + '\n';
    for (const c of clients) c.write(line);
  }, 30);
}

function markRead(id) {
  const theirs = chat(id).filter((m) => !m.me && !m.readSent).slice(-200);
  if (state.unread[id]) { state.unread[id] = 0; save(); changed(); }
  const p = peerFor(id);
  if (p && theirs.length && state.contacts[id] && state.contacts[id].status === 'accepted') {
    send(p, { t: 'read', mids: theirs.map((m) => m.mid) });
    for (const m of theirs) m.readSent = true;
    save();
  }
}

async function command(req) {
  const id = typeof req.id === 'string' ? req.id.trim().toLowerCase() : '';
  switch (req.cmd) {
    case 'state':
      return snapshot();
    case 'setup': {
      const name = cleanName(req.name);
      if (!name) throw new Error('Bitte einen Namen eingeben.');
      if (identity) { identity.name = name; writeJson(IDENTITY, identity, 0o600); }
      else makeIdentity(name);
      await startSwarm();
      for (const p of peers.values()) send(p, { t: 'hello', v: VERSION, id: identity.id, name: identity.name });
      changed();
      return snapshot();
    }
    case 'messages':
      return (state.chats[id] || []).slice(-(Number(req.limit) || 300))
        .map((m) => ({ mid: m.mid, me: m.me, text: m.text, ts: m.ts, state: m.state || '' }));
    case 'add': {
      if (!identity) throw new Error('Messenger ist noch nicht eingerichtet.');
      if (!ID_RE.test(id)) throw new Error('Das ist keine Orbit-ID (Beispiel: jonas.orbitos4417).');
      if (id === identity.id) throw new Error('Das ist deine eigene Orbit-ID.');
      const c = state.contacts[id];
      if (c && c.status === 'incoming') return command({ cmd: 'accept', id });
      if (c) return snapshot();
      state.contacts[id] = { id, name: id.split('.')[0], key: null, status: 'outgoing', since: Date.now() };
      watch(id);
      const p = peerFor(id);
      if (p) send(p, { t: 'request', name: identity.name });
      save(); changed();
      return snapshot();
    }
    case 'accept': {
      const c = state.contacts[id];
      if (!c || c.status !== 'incoming') throw new Error('Keine offene Anfrage.');
      c.status = 'accepted';
      const p = peerFor(id);
      if (p && p.key === c.key) send(p, { t: 'accept' });
      save(); changed();
      return snapshot();
    }
    case 'decline':
    case 'remove': {
      const c = state.contacts[id];
      if (!c) return snapshot();
      const p = peerFor(id);
      if (p && c.status === 'incoming') send(p, { t: 'decline' });
      delete state.contacts[id];
      if (req.cmd === 'remove') { delete state.chats[id]; delete state.unread[id]; }
      unwatch(id);
      save(); changed();
      return snapshot();
    }
    case 'send': {
      const c = state.contacts[id];
      const text = String(req.text || '').trim().slice(0, MAX_TEXT);
      if (!c || c.status !== 'accepted') throw new Error('Kein angenommener Kontakt.');
      if (!text) return snapshot();
      const m = { mid: crypto.randomBytes(9).toString('base64url'), me: true, text, ts: Date.now(), state: 'queued' };
      const list = chat(id);
      list.push(m);
      if (list.length > MAX_CHAT) list.splice(0, list.length - MAX_CHAT);
      const p = peerFor(id);
      if (p) send(p, { t: 'msg', mid: m.mid, text: m.text, ts: m.ts });
      save(); changed();
      return { mid: m.mid };
    }
    case 'read':
      markRead(id);
      return snapshot();
    case 'ui':                           // welcher Chat ist gerade sichtbar (keine Meldung dafür)
      ui = { active: id, focused: !!req.focused };
      if (ui.focused && ui.active) markRead(ui.active);
      return { ok: true };
    case 'dnd':
      state.dnd = !!req.on;
      save(); changed();
      return snapshot();
    default:
      throw new Error(`Unbekannter Befehl: ${req.cmd}`);
  }
}

function startSocket() {
  try { fs.unlinkSync(SOCK); } catch (_) { /* gab keinen */ }
  const server = net.createServer((sock) => {
    clients.add(sock);
    let buf = '';
    sock.on('data', (d) => {
      buf += d.toString('utf8');
      if (buf.length > 200_000) { sock.destroy(); return; }
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i);
        buf = buf.slice(i + 1);
        let req;
        try { req = JSON.parse(line); } catch (_) { continue; }
        command(req).then(
          (result) => sock.write(JSON.stringify({ re: req.req || 0, ok: true, result }) + '\n'),
          (err) => sock.write(JSON.stringify({ re: req.req || 0, ok: false, error: String(err.message || err) }) + '\n'));
      }
    });
    sock.on('error', () => {});
    sock.on('close', () => clients.delete(sock));
  });
  server.listen(SOCK, () => { try { fs.chmodSync(SOCK, 0o600); } catch (_) { /* egal */ } });
  return server;
}

function log(text) {
  process.stdout.write(`orbit-messenger: ${text}\n`);
}

// ---- Kommandozeile (Tests) ----------------------------------------------------------------------

function cli(json) {
  const sock = net.createConnection(SOCK);
  let buf = '';
  sock.on('connect', () => sock.write(JSON.stringify(Object.assign({ req: 1 }, JSON.parse(json))) + '\n'));
  sock.on('data', (d) => {
    buf += d.toString();
    for (const line of buf.split('\n')) {
      if (!line) continue;
      let msg;
      try { msg = JSON.parse(line); } catch (_) { continue; }
      if (msg.re === 1) {
        process.stdout.write(JSON.stringify(msg.ok ? msg.result : { error: msg.error }) + '\n');
        process.exit(msg.ok ? 0 : 1);
      }
    }
  });
  sock.on('error', (e) => { process.stderr.write(`Dienst nicht erreichbar: ${e.message}\n`); process.exit(2); });
}

async function main() {
  if (process.argv[2] === '--cli') return cli(process.argv[3] || '{"cmd":"state"}');
  if (process.argv[2] === '--version') { log(`Version ${VERSION}`); return undefined; }
  fs.mkdirSync(DATA, { recursive: true, mode: 0o700 });
  const server = startSocket();
  if (identity) await startSwarm();
  else log('noch nicht eingerichtet – wartet auf den Namen');
  const stop = async () => {
    saveNow();
    server.close();
    try { fs.unlinkSync(SOCK); } catch (_) { /* egal */ }
    if (swarm) await swarm.destroy().catch(() => {});
    process.exit(0);
  };
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
  return undefined;
}

if (require.main === module) main();

module.exports = { slug, ID_RE };
