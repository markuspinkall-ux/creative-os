'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('wa', {
  get: () => ipcRenderer.invoke('settings:get'),
  set: (next) => ipcRenderer.invoke('settings:set', next),
  logout: () => ipcRenderer.invoke('settings:logout'),
  onChange: (fn) => ipcRenderer.on('settings', (_e, s) => fn(s)),
});
