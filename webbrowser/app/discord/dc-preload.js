'use strict';
// Läuft in Discord Web (eigene, für die Seite unsichtbare Welt): ein Klick auf eine Benachrichtigung
// holt das Discord-Fenster nach vorn. Sonst bleibt Discord unverändert.
const { contextBridge, ipcRenderer, webFrame } = require('electron');

contextBridge.exposeInMainWorld('__gibeonDiscord', { clicked: () => ipcRenderer.send('dc:focus') });

function inject() {
  const Orig = window.Notification;
  const api = window.__gibeonDiscord;
  if (!Orig || !api || Orig.__gibeon) return;
  function GibeonNotification(title, options) {
    const n = new Orig(title, options);
    n.addEventListener('click', () => api.clicked());
    return n;
  }
  GibeonNotification.prototype = Orig.prototype;
  GibeonNotification.__gibeon = true;
  Object.defineProperty(GibeonNotification, 'permission', { get: () => Orig.permission });
  Object.defineProperty(GibeonNotification, 'maxActions', { get: () => Orig.maxActions || 0 });
  GibeonNotification.requestPermission = (...a) => Orig.requestPermission(...a);
  window.Notification = GibeonNotification;
}
webFrame.executeJavaScript(`(${inject.toString()})();`).catch(() => {});
