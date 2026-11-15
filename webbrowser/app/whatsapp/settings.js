'use strict';
const q = new URLSearchParams(location.search);
document.body.dataset.design = q.get('design') === 'porzellan' ? 'porzellan' : 'graphit';
if (q.get('accent')) document.body.style.setProperty('--accent', q.get('accent'));

const from = document.getElementById('dndFrom');
const to = document.getElementById('dndTo');
let current = {};

function render(s) {
  current = s;
  for (const b of document.querySelectorAll('.switch')) {
    const on = !!s[b.dataset.key];
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
    b.setAttribute('role', 'switch');
    b.disabled = !!b.dataset.needs && !s[b.dataset.needs];
  }
  if (document.activeElement !== from) from.value = s.dndFrom;
  if (document.activeElement !== to) to.value = s.dndTo;
  from.disabled = to.disabled = !s.dndTimes;
  document.getElementById('quiet').hidden = !s.quietNow;
}

async function set(patch) { render(await window.wa.set(patch)); }

for (const b of document.querySelectorAll('.switch')) {
  b.addEventListener('click', () => set({ [b.dataset.key]: !current[b.dataset.key] }));
}
for (const input of [from, to]) {
  input.addEventListener('change', () => { if (/^\d\d:\d\d$/.test(input.value)) set({ [input.id]: input.value }); });
}
document.getElementById('logout').addEventListener('click', async () => {
  if (confirm('Von WhatsApp auf diesem PC abmelden? Deine Chats bleiben auf dem Handy erhalten.')) await window.wa.logout();
});
window.wa.onChange(render);
window.wa.get().then(render);
