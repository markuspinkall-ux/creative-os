'use strict';
// Prüft das Videowerbung-Skript (preload-videoad.js) ohne Electron: node tools/browser-videowerbung-test.js
const vm = require('vm'); const fs = require('fs');
const src = fs.readFileSync(process.argv[2] || require('path').join(__dirname, '..', 'webbrowser', 'app', 'preload-videoad.js'), 'utf8');
const mod = { exports: {} };
new Function('require', 'module', src)(() => ({ contextBridge: {}, ipcRenderer: {}, webFrame: {} }), mod);
const { youtubeMain, siteFor } = mod.exports;
const assert = require('assert');
assert(siteFor('www.youtube.com') && siteFor('m.youtube.com') && siteFor('www.twitch.tv') && !siteFor('example.org') && !siteFor('notyoutube.com'));
// Seite nachbauen
const ctx = { setInterval: () => 0, document: { querySelector: () => null } };
ctx.window = ctx; ctx.JSON = JSON.parse === undefined ? null : vm.runInNewContext('JSON');
vm.createContext(ctx);
vm.runInContext('class Response { json() { return Promise.resolve(JSON.parse(this.body)); } constructor(b){this.body=b;} }; window.Response = Response;', ctx);
vm.runInContext(`(${youtubeMain.toString()})()`, ctx);
const out = vm.runInContext(`
  var ytInitialPlayerResponse = { videoDetails: { videoId: 'x' }, adPlacements: [1], playerAds: [2], adSlots: [3] };
  const a = JSON.parse('{"playerResponse":{"adPlacements":[1],"streamingData":{}},"adSlots":[1]}');
  const p = new Response('{"adPlacements":[1],"videoDetails":{}}').json();
  const plain = JSON.parse('{"a":1}');
  ({ init: ytInitialPlayerResponse, a, p, plain, native: JSON.parse.toString(), name: JSON.parse.name });`, ctx);
assert.strictEqual(out.init.adPlacements, undefined); assert.strictEqual(out.init.playerAds, undefined);
assert.strictEqual(out.init.videoDetails.videoId, 'x');
assert.strictEqual(out.a.playerResponse.adPlacements, undefined); assert.strictEqual(out.a.adSlots, undefined);
assert.ok(out.a.playerResponse.streamingData);
assert.strictEqual(JSON.stringify(out.plain), '{"a":1}');
assert.ok(/native code/.test(out.native) && out.name === 'parse', out.native);
out.p.then((r) => { assert.strictEqual(r.adPlacements, undefined); assert.ok(r.videoDetails); console.log('Videowerbung-Skript: alles ok'); });
