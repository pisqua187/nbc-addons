"use strict";
/* App del salone per iPad: clienti, smalti, fotoepilazione.
   Navigazione con #hash, cosi' "indietro" e ricarica pagina funzionano. */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDay = (d) => d ? d.split("-").reverse().join("/") : "";
const age = (d) => { if (!d) return ""; const b = new Date(d), n = new Date();
  return n.getFullYear() - b.getFullYear() - (n < new Date(n.getFullYear(), b.getMonth(), b.getDate()) ? 1 : 0); };
const todayIso = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
const store = {
  get(k, def = "") { try { return localStorage.getItem(k) ?? def; } catch { return def; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};

let apiKey = store.get("salone.key");
async function api(path, opts = {}) {
  // percorso relativo: funziona sia su http://ip:8077/ sia dentro Home Assistant (Ingress)
  const res = await fetch(path.replace(/^\//, ""), { ...opts, headers: { "Content-Type": "application/json", "X-Api-Key": apiKey } });
  if (res.status === 401) {
    const k = prompt("Chiave di accesso del server");
    if (k === null) throw new Error("Serve la chiave di accesso");
    apiKey = k; store.set("salone.key", k);
    return api(path, opts);
  }
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    const msg = typeof e.detail === "string" ? e.detail
      : Array.isArray(e.detail) ? e.detail.map(d => d.msg.replace(/^Value error, /, "")).join("; ") : "Errore " + res.status;
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}
const post = (p, body, method = "POST") => api(p, { method, body: JSON.stringify(body) });

function toast(msg, ok = true) {
  const t = $("#toast"); t.textContent = msg; t.style.background = ok ? "var(--ok)" : "var(--err)";
  t.style.display = "block"; clearTimeout(t._h); t._h = setTimeout(() => t.style.display = "none", 2600);
}
const debounce = (fn, ms = 200) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const safe = (fn) => (...a) => Promise.resolve().then(() => fn(...a)).catch(e => toast(e.message, false));
const val = (id) => ($("#" + id)?.value ?? "").trim();
const go = (hash) => { location.hash = hash; };

/* ---------- operatrici (per i menu a tendina) ---------- */
let operatorsCache = null;
async function operators() { return operatorsCache ??= await api("/api/operators"); }
function operatorSelect(id, selected) {
  const ops = operatorsCache || [];
  const sel = selected ?? store.get("salone.operator");
  const names = ops.map(o => o.name);
  if (sel && !names.includes(sel)) names.push(sel); // operatrice tolta ma presente in schede vecchie
  return `<select id="${id}"><option value="">—</option>${names.map(n =>
    `<option${n === sel ? " selected" : ""}>${esc(n)}</option>`).join("")}</select>`;
}

/* ---------- router ---------- */
const routes = [
  [/^#?\/?$/, homeView],
  [/^#\/nuova$/, () => clientForm(null)],
  [/^#\/c\/(\d+)$/, (id) => clientView(+id, "smalti")],
  [/^#\/c\/(\d+)\/laser$/, (id) => clientView(+id, "laser")],
  [/^#\/c\/(\d+)\/modifica$/, (id) => clientForm(+id)],
  [/^#\/impostazioni$/, settingsView],
  [/^#\/c\/(\d+)\/modulo$/, (id) => consentFormView(+id)],
  [/^#\/modulo\/(\d+)$/, (id) => consentDetailView(+id)],
];
let depth = 0;
async function router() {
  const h = location.hash || "#/";
  document.body.classList.toggle("kiosk", /\/modulo$/.test(h)); // modulo da firmare: niente menu
  $("#back").hidden = h === "#/" || h === "";
  window.scrollTo(0, 0);
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) {
      try { await operators(); await fn(...m.slice(1)); }
      catch (e) { $("#view").innerHTML = `<div class="card empty">${esc(e.message)}</div>`; }
      return;
    }
  }
  go("#/");
}
window.addEventListener("hashchange", () => { depth++; router(); });
$("#back").onclick = () => depth > 0 ? history.back() : go("#/");
$("#settingsBtn").onclick = () => go("#/impostazioni");

/* Tasto "Dashboard": visibile solo quando l'app gira dentro Home Assistant (Ingress, in un riquadro).
   Naviga la pagina di Home Assistant come fa HA stesso (stessa origine), senza ricaricarla. */
(() => {
  let top = null;
  try { if (window.top !== window && window.top.location.origin === location.origin) top = window.top; } catch {}
  if (!top) return;
  const url = document.body.dataset.dashboard || "/";
  $("#dash").hidden = false;
  $("#dash").onclick = () => {
    try {
      top.history.pushState(null, "", url);
      top.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    } catch { top.location.href = url; }
  };
})();
const setTitle = (t) => { $("#title").textContent = t; document.title = t + " · Salone"; };

/* ---------- home: ricerca + recenti ---------- */
const clientRow = (c) => `<a class="row" href="#/c/${c.id}">
  <span class="grow"><b>${esc(c.name)}</b>${c.phone ? `<br><span class="sub">${esc(c.phone)}</span>` : ""}</span>
  ${c.origin === "app" && !c.external_id ? `<span class="pill">creata nell'app</span>` : ""}<span class="sub">›</span></a>`;

async function homeView() {
  setTitle("Clienti");
  const q0 = sessionStorage.getItem("salone.q") || "";
  $("#view").innerHTML = `
    <div class="card">
      <div class="bar">
        <input id="q" class="search grow" type="search" placeholder="Cerca per nome, cognome o cellulare"
               autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" value="${esc(q0)}">
        <button class="primary" id="newC">+ Nuova cliente</button>
      </div>
    </div>
    <div class="card" id="res"></div>`;
  const q = $("#q");
  const run = safe(async () => {
    const text = q.value.trim();
    sessionStorage.setItem("salone.q", q.value);
    if (!text) {
      const rows = await api("/api/clients/recent");
      $("#res").innerHTML = `<h2>Recenti</h2>` + (rows.map(clientRow).join("")
        || `<div class="empty">Cerca una cliente per iniziare</div>`);
      return;
    }
    const rows = await api("/api/clients?q=" + encodeURIComponent(text));
    $("#res").innerHTML = rows.length ? rows.map(clientRow).join("") + (rows.length === 50 ? `<div class="empty">Mostrate le prime 50: scrivi qualche lettera in più</div>` : "")
      : `<div class="empty">Nessuna cliente trovata.<br><br><button class="primary" id="newC2">+ Crea “${esc(text)}”</button></div>`;
    $("#newC2")?.addEventListener("click", () => { sessionStorage.setItem("salone.newname", text); go("#/nuova"); });
  });
  q.oninput = debounce(run, 180);
  $("#newC").onclick = () => { sessionStorage.setItem("salone.newname", q.value.trim()); go("#/nuova"); };
  if (matchMedia("(pointer:fine)").matches) q.focus(); // sull'iPad non apriamo la tastiera da soli
  await run();
}

/* ---------- nuova / modifica cliente ---------- */
async function clientForm(id) {
  const c = id ? await api("/api/clients/" + id) : { name: sessionStorage.getItem("salone.newname") || "", phone: "", birth_date: "", notes: "" };
  sessionStorage.removeItem("salone.newname");
  setTitle(id ? "Modifica cliente" : "Nuova cliente");
  $("#view").innerHTML = `<div class="card">
    <div class="grid">
      <div><label>Nome e cognome *</label><input id="name" value="${esc(c.name)}" autocapitalize="words" autocomplete="off"></div>
      <div><label>Cellulare</label><input id="phone" type="tel" inputmode="tel" value="${esc(c.phone)}" autocomplete="off"></div>
      <div><label>Data di nascita</label><input id="birth" type="date" value="${esc(c.birth_date)}"></div>
    </div>
    <div style="margin-top:12px"><label>Note</label><textarea id="notes">${esc(c.notes)}</textarea></div>
    ${c.external_id ? `<p class="sub">Collegata all'anagrafica Vaniglia (${esc(c.external_id)}): un nuovo import può aggiornare nome, cellulare e data di nascita (se nell'export sono vuoti, restano questi).</p>` : ""}
    <div id="dups"></div>
    <div class="bar" style="margin-top:14px"><button class="primary" id="save">Salva</button></div></div>`;
  if (!id) {
    const check = safe(async () => {
      const n = val("name"); if (n.length < 3) { $("#dups").innerHTML = ""; return; }
      const rows = (await api("/api/clients?q=" + encodeURIComponent(n))).slice(0, 5);
      $("#dups").innerHTML = rows.length ? `<p class="sub" style="margin-top:14px">Esiste già? Toccala per aprirla:</p>${rows.map(clientRow).join("")}` : "";
    });
    $("#name").oninput = debounce(check, 300); check();
  }
  $("#save").onclick = safe(async () => {
    const body = { name: val("name"), phone: val("phone") || null, birth_date: val("birth") || null, notes: val("notes") || null };
    const saved = id ? await post("/api/clients/" + id, body, "PUT") : await post("/api/clients", body);
    toast("Salvata");
    if (id) history.back(); else location.replace("#/c/" + saved.id);
  });
}

/* ---------- scheda cliente: smalti | fotoepilazione ---------- */
async function clientView(id, tab) {
  const c = await api("/api/clients/" + id);
  setTitle(c.name);
  $("#view").innerHTML = `
    <div class="card no-print"><div class="bar">
      <a class="grow namelink" href="#/c/${id}/modifica" title="Modifica i dati della cliente">
        <b style="font-size:20px">${esc(c.name)}</b> <span class="pencil">✎</span>
        <div class="sub">${c.birth_date ? `${fmtDay(c.birth_date)} (${age(c.birth_date)} anni)` : "Data di nascita non indicata"} · ${c.phone ? esc(c.phone) : "nessun cellulare"}${c.notes ? " · " + esc(c.notes) : ""}</div></a>
      <button id="switchC">⇄ Cambia cliente</button></div>
      <div class="bar consent-line ${c.last_consent ? "ok" : "missing"}">
        <span class="grow">${c.last_consent
          ? `✅ Modulo privacy firmato il ${fmtDay(c.last_consent.signed_at.slice(0, 10))} · <a href="#/modulo/${c.last_consent.id}">vedi</a>`
          : "⚠️ Modulo privacy e consenso non ancora firmato"}</span>
        <a class="btn ${c.last_consent ? "" : "pinkbtn"}" href="#/c/${id}/modulo">📝 ${c.last_consent ? "Nuovo modulo" : "Fai firmare il modulo"}</a></div>
      <div id="switchBox" hidden style="margin-top:12px">
        <input id="sq" class="search" type="search" placeholder="Cerca un'altra cliente" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
        <div id="sres"></div></div></div>
    <nav class="tabs no-print"><a href="#/c/${id}" class="${tab === "smalti" ? "on" : ""}">💅 Smalti</a>
      <a href="#/c/${id}/laser" class="${tab === "laser" ? "on" : ""}">✨ Fotoepilazione</a></nav>
    <div id="tab"></div>`;
  const suffix = tab === "laser" ? "/laser" : "";
  $("#switchC").onclick = () => {
    const box = $("#switchBox"); box.hidden = !box.hidden;
    if (!box.hidden) { $("#sq").value = ""; $("#sres").innerHTML = ""; $("#sq").focus(); }
  };
  $("#sq").oninput = debounce(safe(async () => {
    const text = val("sq");
    if (!text) { $("#sres").innerHTML = ""; return; }
    const rows = (await api("/api/clients?q=" + encodeURIComponent(text))).filter(r => r.id !== id).slice(0, 8);
    $("#sres").innerHTML = rows.map(r => `<a class="row" href="#/c/${r.id}${suffix}">
      <span class="grow"><b>${esc(r.name)}</b>${r.phone ? `<br><span class="sub">${esc(r.phone)}</span>` : ""}</span><span class="sub">›</span></a>`).join("")
      || `<div class="empty">Nessuna cliente trovata</div>`;
  }), 180);
  if (tab === "smalti") await polishTab(c); else { await laserTab(c); await laserExtras(c); }
  swipeToDelete($("#tab"));
}

/* ---------- scorri a sinistra per eliminare (righe .swipe con data-del) ---------- */
function swipeToDelete(root) {
  $$(".swipe", root).forEach(el => {
    let x0 = null, y0 = 0;
    el.addEventListener("pointerdown", e => { x0 = e.clientX; y0 = e.clientY; el._swiped = false; });
    el.addEventListener("pointermove", e => {
      if (x0 === null) return;
      const dx = e.clientX - x0, dy = e.clientY - y0;
      if (Math.abs(dx) < 35 || Math.abs(dy) > Math.abs(dx)) return;
      x0 = null; el._swiped = true;
      if (dx < 0) { $$(".swipe.open").forEach(o => o.classList.remove("open")); el.classList.add("open"); }
      else el.classList.remove("open");
    });
    const end = () => { x0 = null; };
    el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
    $(".sdel", el).onclick = safe(async () => {
      await api(el.dataset.del, { method: "DELETE" }); toast(el.dataset.msg || "Eliminato"); router();
    });
  });
}
// Dopo uno scorrimento il "clic" non deve aprire la riga; con una riga aperta, un tocco altrove la richiude.
document.addEventListener("click", e => {
  const sw = e.target.closest?.(".swipe");
  if (sw && sw._swiped) { sw._swiped = false; e.stopPropagation(); e.preventDefault(); return; }
  const open = $$(".swipe.open");
  if (open.length && !e.target.closest(".sdel")) {
    open.forEach(o => o.classList.remove("open")); e.stopPropagation(); e.preventDefault();
  }
}, true);

async function polishTab(c) {
  $("#tab").innerHTML = `
    <div class="card"><h2>Smalto di oggi</h2>
      <div class="grid" style="grid-template-columns:2fr 1fr 1fr">
        <div><label>Smalto</label><input id="polish" placeholder="es. OPI N25 Big Apple Red" autocomplete="off" autocorrect="off" spellcheck="false"></div>
        <div><label>Note</label><input id="pnotes" placeholder="es. french" autocomplete="off"></div>
        <div><label>Operatrice</label>${operatorSelect("pop")}</div>
      </div>
      <div class="chips" id="chips"></div>
      <button class="pink" id="psave">Salva smalto</button>
    </div>
    <div class="card"><h2>Storico smalti</h2>${c.polish_history.length ? `<p class="sub hint">Scorri una riga verso sinistra per eliminarla</p>` + c.polish_history.map(r => `
      <div class="row swipe" data-del="/api/records/${r.id}" data-msg="Smalto eliminato"><span class="grow"><b>${esc(r.polish)}</b><br>
        <span class="sub">${fmtDay(r.day)}${r.operator ? " · " + esc(r.operator) : ""}${r.notes ? " · " + esc(r.notes) : ""}</span></span>
        <button class="sdel">Elimina</button></div>`).join("") : `<div class="empty">Ancora nessuno smalto registrato</div>`}
    </div>`;
  const polish = $("#polish");
  const suggest = safe(async () => {
    const list = await api("/api/suggestions?q=" + encodeURIComponent(polish.value));
    $("#chips").innerHTML = list.map((s, i) => `<span class="chip" data-i="${i}">${esc(s)}</span>`).join("")
      || `<span class="sub">${polish.value ? "Smalto nuovo: verrà suggerito le prossime volte" : "Gli smalti già usati compariranno qui"}</span>`;
    $$(".chip", $("#chips")).forEach(el => el.onclick = () => { polish.value = list[+el.dataset.i]; suggest(); });
  });
  polish.oninput = debounce(suggest, 150);
  $("#pop").onchange = () => store.set("salone.operator", $("#pop").value);
  $("#psave").onclick = safe(async () => {
    if (!val("polish")) { polish.focus(); throw new Error("Scrivi lo smalto"); }
    await post(`/api/clients/${c.id}/records`, { polish: val("polish"), notes: val("pnotes") || null, operator: val("pop") || null });
    toast("Smalto salvato"); router();
  });
  await suggest();
}

async function laserTab(c) {
  const rows = await api(`/api/clients/${c.id}/laser`);
  const zones = await api("/api/laser-zones");
  const last = rows[rows.length - 1] || {};
  const blanks = Math.max(0, 15 - rows.length); // righe vuote in stampa, da compilare a mano
  $("#tab").innerHTML = `
    <div class="card">
      <div class="print-only print-title">NEW BODY CENTER <span>— DIARIO TRATTAMENTI</span></div>
      <div class="meta">
        <div><b>Nome e cognome</b>${esc(c.name)}</div>
        <div><b>Data di nascita</b>${c.birth_date ? fmtDay(c.birth_date) : `<a class="no-print" href="#/c/${c.id}/modifica">aggiungi</a>`}</div>
        <div class="no-print bar" style="justify-content:flex-end"><button id="print">🖨 Stampa scheda</button>
          <a class="btn" href="${pdfLink(`api/clients/${c.id}/laser/pdf`)}" target="_blank" rel="noopener">📄 PDF</a></div>
      </div>
      <div class="scroll-x"><table class="sheet">
        <thead><tr><th>Data</th><th>Zona trattata</th><th>Freq. J/cm²</th><th>Freq. Hz</th><th>Operatore</th><th class="act"></th></tr></thead>
        <tbody>${rows.map(t => `<tr class="click swipe" data-id="${t.id}" data-del="/api/laser/${t.id}" data-msg="Trattamento eliminato">
          <td>${fmtDay(t.day)}</td><td>${esc(t.zone)}</td><td>${esc(t.fluence)}</td><td>${esc(t.hz)}</td><td>${esc(t.operator)}</td>
          <td class="act"><button class="link">Modifica</button><button class="sdel">Elimina</button></td></tr>`).join("")}
          ${'<tr class="blank print-only-row"><td></td><td></td><td></td><td></td><td></td><td class="act"></td></tr>'.repeat(blanks)}
        </tbody></table></div>
      ${rows.length ? `<p class="sub hint no-print">Tocca un trattamento per modificarlo, scorrilo verso sinistra per eliminarlo</p>` : `<div class="empty no-print">Nessun trattamento registrato</div>`}
    </div>
    <div class="card no-print" id="tForm"></div>`;
  printButton($("#print"), () => post(`/api/clients/${c.id}/laser/print`, { copies: 1 }), "Scheda inviata alla stampante");

  const newT = { zone: last.zone, fluence: last.fluence, hz: last.hz };
  const form = (t) => {
    const editing = !!t.id;
    $$("tr.editing").forEach(r => r.classList.remove("editing"));
    if (editing) $(`tr[data-id="${t.id}"]`)?.classList.add("editing");
    // zone salvate come "Ascelle, Inguine, <testo personalizzato>"
    const parts = (t.zone || "").split(",").map(z => z.trim()).filter(Boolean);
    const selected = new Set(parts.filter(p => zones.includes(p)));
    const custom = parts.filter(p => !zones.includes(p)).join(", ");
    $("#tForm").innerHTML = `
      <h2>${editing ? "Modifica trattamento del " + fmtDay(t.day) : "Nuovo trattamento"}</h2>
      ${!editing && last.id ? `<p class="sub" style="margin-top:-6px">Precompilato con zona e parametri dell'ultimo trattamento: cambia solo quello che serve.</p>` : ""}
      <div class="grid">
        <div><label>Data del trattamento</label><input id="tday" type="date" value="${esc(t.day || todayIso())}"></div>
        <div style="grid-column:1 / -1"><label>Zona trattata (puoi sceglierne più di una)</label>
          <div class="zones">${zones.map(z => `<button type="button" class="zchip${selected.has(z) ? " on" : ""}" data-z="${esc(z)}">${esc(z)}</button>`).join("")}
            <button type="button" class="zchip${custom ? " on" : ""}" id="zcustom">✎ Personalizzato</button></div>
          <input id="tzcustom" placeholder="Scrivi la zona" value="${esc(custom)}" autocomplete="off"${custom ? "" : " hidden"} style="margin-top:8px"></div>
        <div><label>Freq. J/cm²</label><input id="tflu" inputmode="decimal" value="${esc(t.fluence)}" autocomplete="off"></div>
        <div><label>Freq. Hz</label><input id="thz" inputmode="decimal" value="${esc(t.hz)}" autocomplete="off"></div>
        <div><label>Operatore</label>${operatorSelect("top", editing ? t.operator : undefined)}</div>
      </div>
      <div class="bar" style="margin-top:14px">
        <button class="primary" id="tsave">${editing ? "Salva modifiche" : "Registra trattamento"}</button>
        ${editing ? `<button id="tcancel">Annulla</button><span class="grow"></span><button class="danger" id="tdel">Elimina</button>` : ""}
      </div>`;
    $("#top").onchange = () => store.set("salone.operator", $("#top").value);
    $$(".zchip[data-z]").forEach(b => b.onclick = () => {
      selected.has(b.dataset.z) ? selected.delete(b.dataset.z) : selected.add(b.dataset.z);
      b.classList.toggle("on");
    });
    $("#zcustom").onclick = () => {
      const on = $("#zcustom").classList.toggle("on");
      $("#tzcustom").hidden = !on;
      if (on) $("#tzcustom").focus();
    };
    $("#tsave").onclick = safe(async () => {
      const customOn = $("#zcustom").classList.contains("on") && val("tzcustom");
      const zone = [...zones.filter(z => selected.has(z)), ...(customOn ? [val("tzcustom")] : [])].join(", ");
      const body = { day: val("tday") || null, zone, fluence: val("tflu") || null,
                     hz: val("thz") || null, operator: val("top") || null };
      if (!body.zone) throw new Error("Scegli almeno una zona trattata");
      if (!editing && !c.last_consent &&
          !confirm("La cliente non ha ancora firmato il modulo privacy e consenso. Registrare comunque il trattamento?")) return;
      if (editing) await post("/api/laser/" + t.id, body, "PUT");
      else await post(`/api/clients/${c.id}/laser`, body);
      toast(editing ? "Trattamento aggiornato" : "Trattamento registrato"); router();
    });
    $("#tcancel")?.addEventListener("click", () => form(newT));
    $("#tdel")?.addEventListener("click", safe(async () => {
      if (!confirm(`Eliminare il trattamento del ${fmtDay(t.day)}?`)) return;
      await api("/api/laser/" + t.id, { method: "DELETE" }); toast("Trattamento eliminato"); router();
    }));
  };
  $$("tr.click").forEach(tr => tr.onclick = () => {
    form(rows.find(t => t.id === +tr.dataset.id));
    $("#tForm").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  form(newT);
}

/* ---------- impostazioni ---------- */
async function settingsView() {
  setTitle("Impostazioni");
  operatorsCache = null; await operators();
  const st = await api("/api/status");
  $("#view").innerHTML = `
    <div class="card"><h2>Operatrici</h2>
      ${operatorsCache.map(o => `<div class="row"><span class="grow">${esc(o.name)}</span>
        <button class="danger" data-op="${o.id}">Togli</button></div>`).join("") || `<div class="empty">Nessuna operatrice</div>`}
      <div class="bar" style="margin-top:10px"><input id="opname" class="grow" placeholder="Nome operatrice" style="flex:1" autocapitalize="words">
        <button class="primary" id="opadd">Aggiungi</button></div>
    </div>
    <div class="card" id="printerCard"></div>
    <div class="card" id="archCard"></div>
    <div class="card"><h2>Anagrafica clienti</h2>
      <p class="sub">In archivio: <b>${st.clients}</b> clienti. Per aggiornarla esporta le clienti da Vaniglia Pro in CSV e caricalo qui:
        le clienti esistenti si aggiornano, le nuove si aggiungono, storico smalti e schede restano intatti.
        Si importano solo nome, cognome, cellulare, data di nascita e codice cliente.</p>
      <input id="csv" type="file" accept=".csv,text/csv">
      <div id="impres"></div>
    </div>`;
  $$("[data-op]").forEach(b => b.onclick = safe(async () => {
    await api("/api/operators/" + b.dataset.op, { method: "DELETE" }); toast("Tolta"); settingsView();
  }));
  await archiveCard($("#archCard"));
  printerCard($("#printerCard")).catch(e => { $("#printerCard").innerHTML = `<h2>Stampante</h2><p class="sub">${esc(e.message)}</p>`; });
  $("#opadd").onclick = safe(async () => {
    if (!val("opname")) return;
    await post("/api/operators", { name: val("opname") }); toast("Aggiunta"); settingsView();
  });
  $("#csv").onchange = safe(async () => {
    const f = $("#csv").files[0]; if (!f) return;
    const buf = await f.arrayBuffer();
    let text; try { text = new TextDecoder("utf-8", { fatal: true }).decode(buf); } catch { text = new TextDecoder("windows-1252").decode(buf); }
    const preview = await post("/api/import-clients", { csv: text, apply: false });
    const desc = (s) => `${s.righe} righe: <b>${s.nuove}</b> nuove, <b>${s.aggiornate}</b> aggiornate, ${s.collegate} collegate a clienti create nell'app, ${s.invariate} invariate${s.scartate_senza_nome ? `, ${s.scartate_senza_nome} scartate (senza nome)` : ""}.`;
    $("#impres").innerHTML = `<p>${desc(preview)}</p><button class="primary" id="impok">Importa</button> <button id="impno">Annulla</button>`;
    $("#impno").onclick = () => { $("#impres").innerHTML = ""; $("#csv").value = ""; };
    $("#impok").onclick = safe(async () => {
      const done = await post("/api/import-clients", { csv: text, apply: true });
      $("#impres").innerHTML = `<p style="color:var(--ok)">Fatto. ${desc(done)}</p>`; toast("Import completato");
    });
  });
}

router();
