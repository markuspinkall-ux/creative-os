// Gibeon OS – Sammelstelle „Regionen“ (Cloudflare Worker + KV)
//
// POST /melden   {"land": "DE", "monat": "2026-11", "neu": true}
//                Gibeon OS meldet – nur mit Zustimmung – einmal im Monat sein Land.
//                Gespeichert werden nur Zähler je Land. Keine IP, keine Kennung.
// GET  /zahlen   Authorization: Bearer <SCHLUESSEL>
//                → {"installationen": {"DE": 12}, "monat": "2026-11", "aktiv": {"DE": 9}}
//                Nur für das Entwickler-Widget (Schlüssel als Secret SCHLUESSEL hinterlegt).
//
// Bindung: KV-Namespace „ZAHLEN“, Secret „SCHLUESSEL“ (siehe ANLEITUNG.md).

const LAND = /^[A-Z]{2}$/;
const MONAT = /^20\d\d-(0[1-9]|1[0-2])$/;

async function plusEins(env, key) {
  const n = parseInt((await env.ZAHLEN.get(key)) || "0", 10) || 0;
  await env.ZAHLEN.put(key, String(n + 1));
}

async function liste(env, prefix) {
  const out = {};
  let cursor;
  do {
    const page = await env.ZAHLEN.list({ prefix, cursor });
    for (const k of page.keys) {
      out[k.name.slice(prefix.length)] = parseInt((await env.ZAHLEN.get(k.name)) || "0", 10) || 0;
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return out;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/melden") {
      const text = await request.text();
      if (text.length > 200) return json({ fehler: "zu groß" }, 413);
      let d;
      try { d = JSON.parse(text); } catch { return json({ fehler: "kein JSON" }, 400); }
      const land = String(d.land || "").toUpperCase();
      const monat = String(d.monat || "");
      if (!LAND.test(land) || !MONAT.test(monat)) return json({ fehler: "ungültig" }, 400);
      if (d.neu === true) await plusEins(env, `inst:${land}`);
      await plusEins(env, `aktiv:${monat}:${land}`);
      return json({ ok: true });
    }

    if (request.method === "GET" && url.pathname === "/zahlen") {
      const auth = request.headers.get("Authorization") || "";
      if (!env.SCHLUESSEL || auth !== `Bearer ${env.SCHLUESSEL}`) return json({ fehler: "kein Zugang" }, 401);
      const jetzt = new Date();
      const monat = url.searchParams.get("monat")
        || `${jetzt.getUTCFullYear()}-${String(jetzt.getUTCMonth() + 1).padStart(2, "0")}`;
      if (!MONAT.test(monat)) return json({ fehler: "ungültig" }, 400);
      return json({
        installationen: await liste(env, "inst:"),
        monat,
        aktiv: await liste(env, `aktiv:${monat}:`),
      });
    }

    return json({ dienst: "Gibeon OS Regionen" }, 404);
  },
};
