'use strict';
// Brücke zwischen Oberfläche (ui/) und Hauptprozess – nur diese Funktionen sind sichtbar.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('creative', {
  cmd: (name, a1, a2) => ipcRenderer.send('cmd', name, a1, a2),
  suggest: (text) => ipcRenderer.invoke('suggest', text),
  call: (name, a1) => ipcRenderer.invoke('ui-call', name, a1),
  on: (channel, fn) => {
    const allowed = ['state', 'focus-address', 'find-open', 'find-result', 'context-menu', 'permission',
      'download-started', 'open-downloads', 'close-overlays', 'pw-offer', 'toast'];
    if (allowed.includes(channel)) ipcRenderer.on(channel, (_e, payload) => fn(payload));
  },
});
