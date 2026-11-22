// Probe für tools/regionen-worker/worker.js mit nachgebautem KV
import worker from "../tools/regionen-worker/worker.js";
const store = new Map();
const env = {
  SCHLUESSEL: "geheim",
  ZAHLEN: {
    get: async (k) => store.get(k) ?? null,
    put: async (k, v) => { store.set(k, v); },
    list: async ({ prefix }) => ({ keys: [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true }),
  },
};
const post = (b) => worker.fetch(new Request("https://x/melden", { method: "POST", body: JSON.stringify(b) }), env);
const ok = (c, m) => { if (!c) { console.error("FEHLER:", m); process.exit(1); } };
ok((await post({ land: "DE", monat: "2026-11", neu: true })).status === 200, "melden");
ok((await post({ land: "de", monat: "2026-11", neu: false })).status === 200, "klein geschrieben");
ok((await post({ land: "AT", monat: "2026-11", neu: true })).status === 200, "AT");
ok((await post({ land: "Deutschland", monat: "2026-11" })).status === 400, "ungültiges Land");
ok((await post({ land: "DE", monat: "11/2026" })).status === 400, "ungültiger Monat");
ok((await worker.fetch(new Request("https://x/zahlen?monat=2026-11"), env)).status === 401, "ohne Schlüssel");
const r = await worker.fetch(new Request("https://x/zahlen?monat=2026-11", { headers: { Authorization: "Bearer geheim" } }), env);
const d = await r.json();
ok(d.installationen.DE === 1 && d.installationen.AT === 1, JSON.stringify(d));
ok(d.aktiv.DE === 2 && d.aktiv.AT === 1, JSON.stringify(d));
ok(![...store.keys()].some((k) => /\d+\.\d+\.\d+\.\d+/.test(k)), "keine IP");
console.log("Regionen-Worker: in Ordnung", JSON.stringify(d));
