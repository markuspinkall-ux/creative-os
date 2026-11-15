'use strict';
// Läuft in WhatsApp Web (eigene, für die Seite unsichtbare Welt). Hängt sich in die Benachrichtigungen:
// Nicht stören, Vorschau aus, Ton aus – und ein Klick auf die Benachrichtigung holt das Fenster nach vorn.
const { contextBridge, ipcRenderer, webFrame } = require('electron');

let state = { notify: true, preview: true, sound: true, quiet: false };
ipcRenderer.on('wa:state', (_e, s) => { state = { ...state, ...s }; });

contextBridge.exposeInMainWorld('__creativeWA', {
  quiet: () => !state.notify || state.quiet,
  preview: () => state.preview,
  sound: () => state.sound,
  clicked: () => ipcRenderer.send('wa:focus'),
});

function inject() {
  const Orig = window.Notification;
  const api = window.__creativeWA;
  if (!Orig || !api || Orig.__creative) return;
  // Stumme Benachrichtigung (Nicht stören): verhält sich für die Seite wie eine echte, zeigt aber nichts
  class Silent extends EventTarget {
    constructor(title, options) {
      super();
      this.title = title;
      this.body = (options && options.body) || '';
      this.tag = (options && options.tag) || '';
      this.data = options && options.data;
      this.onclick = null; this.onclose = null; this.onshow = null; this.onerror = null;
    }
    close() {}
  }
  function CreativeNotification(title, options) {
    if (api.quiet()) return new Silent(title, options);
    const o = Object.assign({}, options || {});
    if (!api.preview()) { title = 'WhatsApp'; o.body = 'Neue Nachricht'; delete o.image; delete o.icon; }
    if (!api.sound()) o.silent = true;
    const n = new Orig(title, o);
    n.addEventListener('click', () => api.clicked());
    return n;
  }
  CreativeNotification.prototype = Orig.prototype;
  CreativeNotification.__creative = true;
  Object.defineProperty(CreativeNotification, 'permission', { get: () => Orig.permission });
  Object.defineProperty(CreativeNotification, 'maxActions', { get: () => Orig.maxActions || 0 });
  CreativeNotification.requestPermission = (...a) => Orig.requestPermission(...a);
  window.Notification = CreativeNotification;
}
webFrame.executeJavaScript(`(${inject.toString()})();`).catch(() => {});
