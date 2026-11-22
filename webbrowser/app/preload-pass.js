'use strict';
// Passwörter in Webseiten: gespeicherte Anmeldung ausfüllen und nach dem Anmelden fragen, ob der
// Browser sie sich merken soll. Läuft als Sitzungs-Preload in jeder Seite (eigene, für die Seite
// unsichtbare Welt) – das Passwort selbst fragt die Seite nie ab, es wird nur in das Feld gesetzt.
const { ipcRenderer } = require('electron');

if (/^https?:$/.test(location.protocol) && window.top === window) {
  const visible = (el) => !!el && el.offsetParent !== null && !el.disabled && !el.readOnly;
  const pwFields = () => [...document.querySelectorAll('input[type="password"]')].filter(visible);
  // Benutzername: Feld mit autocomplete=username/email, sonst das sichtbare Textfeld vor dem Passwort
  const userFieldFor = (pw) => {
    const scope = pw.form || document;
    const fields = [...scope.querySelectorAll('input')].filter((i) => visible(i)
      && /^(text|email|tel|)$/.test(i.type));
    const tagged = fields.find((i) => /username|email/.test(i.autocomplete || ''));
    if (tagged) return tagged;
    const before = fields.filter((i) => i.compareDocumentPosition(pw) & Node.DOCUMENT_POSITION_FOLLOWING);
    return before[before.length - 1] || null;
  };
  // Wert so setzen, dass auch React & Co. ihn mitbekommen
  const setValue = (el, v) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };

  let filled = false;
  async function tryFill() {
    if (filled) return;
    const pw = pwFields()[0];
    if (!pw || pw.value) return;
    // Neues Passwort festlegen (Registrierung)? Dann nicht ausfüllen
    if (pw.autocomplete === 'new-password') return;
    const users = await ipcRenderer.invoke('pw-users', location.origin);
    if (!users || !users.length) return;
    const uf = userFieldFor(pw);
    const typed = uf && uf.value;
    const user = typed && users.includes(typed) ? typed : users[0];
    const pass = await ipcRenderer.invoke('pw-reveal', location.origin, user);
    if (pass == null) return;
    filled = true;
    if (uf && !uf.value && user) setValue(uf, user);
    setValue(pw, pass);
    pw.style.backgroundColor = 'rgba(143, 179, 255, 0.18)';
  }

  let last = { user: '', pass: '' };
  const remember = () => {
    const pw = pwFields().find((f) => f.value) || [...document.querySelectorAll('input[type="password"]')].find((f) => f.value);
    if (!pw) return;
    const uf = userFieldFor(pw);
    last = { user: (uf && uf.value) || '', pass: pw.value };
  };
  const offer = () => {
    remember();
    if (!last.pass) return;
    ipcRenderer.send('pw-offer', { origin: location.origin, user: last.user, pass: last.pass });
    last = { user: '', pass: '' };
  };

  window.addEventListener('DOMContentLoaded', () => {
    setTimeout(tryFill, 300);
    // Anmeldefelder, die erst später erscheinen (Einzelseiten-Apps)
    let t = null;
    new MutationObserver(() => { clearTimeout(t); t = setTimeout(tryFill, 400); })
      .observe(document.documentElement, { childList: true, subtree: true });
  });
  // Eingaben merken, gefragt wird beim Absenden (Formular, Enter im Passwortfeld, Anmelde-Knopf)
  document.addEventListener('input', (e) => { if (e.target && e.target.type === 'password') remember(); }, true);
  document.addEventListener('submit', offer, true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target && e.target.type === 'password') setTimeout(offer, 0); }, true);
  document.addEventListener('click', (e) => {
    const b = e.target && e.target.closest && e.target.closest('button, input[type="submit"], [role="button"]');
    if (b && last.pass && /anmeld|einlog|log ?in|sign ?in|weiter|continue|next|submit|senden/i.test(b.textContent || b.value || b.type || '')) {
      setTimeout(offer, 0);
    }
  }, true);
  window.addEventListener('pagehide', () => { if (last.pass) offer(); });
}
