"use strict";
/* Modulo privacy e consenso informato (firmato sull'iPad), check up tecnico, archivio moduli.
   Usa gli aiuti definiti in app.js ($, api, post, esc, toast...): queste funzioni vengono chiamate
   solo dopo che app.js e' stato caricato. */

/* link diretti ai PDF (con la chiave se si usa la porta diretta con API_KEY) */
const pdfLink = (path) => path + (apiKey ? (path.includes("?") ? "&" : "?") + "key=" + encodeURIComponent(apiKey) : "");

/* pulsante di stampa: disattivato mentre invia, messaggio chiaro se la stampante non risponde */
function printButton(el, send, okMsg) {
  if (!el) return;
  const label = el.innerHTML;
  el.onclick = safe(async () => {
    el.disabled = true; el.innerHTML = "⏳ Invio alla stampante…";
    try { const r = await send(); toast(typeof okMsg === "function" ? okMsg(r) : okMsg); }
    finally { el.disabled = false; el.innerHTML = label; }
  });
}

/* consenso presente: modulo digitale firmato oppure cartaceo registrato */
const hasConsent = (c) => !!(c.last_consent || c.paper_consent);

/* "Ha gia' firmato il cartaceo": piccolo form sotto il pulsante (data firma, nota) */
function paperConsentButtons(c) {
  $$(".paperBtn").forEach(btn => btn.onclick = () => {
    const box = btn.closest(".card").querySelector(".paperForm");
    box.hidden = !box.hidden;
    if (box.hidden) return;
    box.innerHTML = `<div class="grid" style="margin-top:10px;grid-template-columns:200px 1fr">
        <div><label>Data della firma sul foglio</label><input type="date" class="pday" value="${todayIso()}" max="${todayIso()}"></div>
        <div><label>Nota (facoltativa, es. dove è archiviato)</label><input class="pnote" placeholder="es. raccoglitore consensi 2025" autocomplete="off"></div></div>
      <div class="bar" style="margin-top:10px"><button class="primary psave">Registra consenso cartaceo</button><button class="pcancel">Annulla</button></div>`;
    $(".pcancel", box).onclick = () => { box.hidden = true; };
    $(".psave", box).onclick = safe(async () => {
      await post(`/api/clients/${c.id}/paper-consents`, {
        signed_on: $(".pday", box).value || null, note: $(".pnote", box).value.trim() || null,
        operator: store.get("salone.operator") || null });
      toast("Consenso cartaceo registrato"); router();
    });
  });
}

let textsCache = null;
async function consentTexts() { return textsCache ??= await api("/api/texts"); }
const ageAt = (iso) => { if (!iso) return null; const b = new Date(iso + "T12:00"), n = new Date();
  return n.getFullYear() - b.getFullYear() - (n < new Date(n.getFullYear(), b.getMonth(), b.getDate()) ? 1 : 0); };

/* ---------- area firma (dito o Apple Pencil) ---------- */
function signaturePad(el) {
  el.innerHTML = `<canvas></canvas><div class="sigline"></div><div class="ph">Firma qui con il dito</div>`;
  const cv = $("canvas", el), ph = $(".ph", el), ctx = cv.getContext("2d");
  let drawing = false, strokes = 0, last = null;
  const size = () => {
    const r = el.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = r.width * dpr; cv.height = r.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.lineWidth = 2.6; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = "#16224a";
  };
  size();
  const pt = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener("pointerdown", (e) => {
    e.preventDefault(); cv.setPointerCapture(e.pointerId); drawing = true; last = pt(e);
    ctx.beginPath(); ctx.arc(last[0], last[1], 1.2, 0, Math.PI * 2); ctx.fillStyle = "#16224a"; ctx.fill();
    ph.hidden = true;
  });
  cv.addEventListener("pointermove", (e) => {
    if (!drawing) return; e.preventDefault();
    const evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
    for (const ev of evs) {
      const p = pt(ev); ctx.beginPath(); ctx.moveTo(last[0], last[1]); ctx.lineTo(p[0], p[1]); ctx.stroke(); last = p;
    }
  });
  const stop = () => { if (drawing) strokes++; drawing = false; };
  cv.addEventListener("pointerup", stop); cv.addEventListener("pointercancel", stop);
  return {
    empty: () => strokes === 0,
    clear: () => { ctx.clearRect(0, 0, cv.width, cv.height); strokes = 0; ph.hidden = false; },
    png: () => cv.toDataURL("image/png"),
  };
}

/* Tocco affidabile: dopo un tratto di firma alcuni browser perdono il "click" del tocco successivo.
   Qui il pulsante reagisce al sollevamento del dito (pointerup) e il click che segue viene ignorato. */
function onTap(el, fn) {
  if (!el) return;
  let downOn = false, last = 0;
  el.addEventListener("pointerdown", (e) => { downOn = e.pointerType !== "mouse"; });
  el.addEventListener("pointerup", (e) => {
    if (!downOn) return; downOn = false; last = Date.now(); fn(e);
  });
  el.addEventListener("pointercancel", () => { downOn = false; });
  el.addEventListener("click", (e) => { if (Date.now() - last < 800) return; fn(e); });
}

const toggleRow = (key, label, on) =>
  `<button type="button" class="toggle${on ? " on" : ""}" data-t="${esc(key)}"><span class="box"></span><span>${esc(label)}</span></button>`;

/* ---------- modulo da compilare e firmare (modalita' cliente) ---------- */
async function consentFormView(id) {
  const [c, T] = await Promise.all([api("/api/clients/" + id), consentTexts()]);
  setTitle("Modulo privacy");
  const parts = (c.name || "").split(" ");
  const nome0 = parts.shift() || "", cognome0 = parts.join(" ");
  const state = { health: new Set(), nessuna: false, scheda: false, consenso: false, privacy: false, sesso: null };

  $("#view").innerHTML = `
    <div class="kiosk-top"><h1>${esc(T.intestazione)} · Scheda cliente e consensi</h1>
      <button id="kexit">Annulla</button></div>
    <p class="sub" style="margin-top:-8px">Compila i tuoi dati, leggi le informazioni e firma in fondo. Ci vogliono circa 3 minuti.</p>

    <div class="card"><h2><span class="step">1</span>I tuoi dati</h2>
      <div class="grid">
        <div><label>Nome *</label><input id="fnome" value="${esc(nome0)}" autocapitalize="words" autocomplete="off"></div>
        <div><label>Cognome *</label><input id="fcognome" value="${esc(cognome0)}" autocapitalize="words" autocomplete="off"></div>
        <div><label>Data di nascita *</label><input id="fbirth" type="date" value="${esc(c.birth_date)}"></div>
        <div><label>Sesso</label><div class="seg" id="fsesso"><button type="button" data-s="F">F</button><button type="button" data-s="M">M</button></div></div>
        <div style="grid-column:1 / -1"><label>Indirizzo</label><input id="findirizzo" autocomplete="off"></div>
        <div><label>Telefono</label><input id="ftel" type="tel" inputmode="tel" value="${esc(c.phone)}" autocomplete="off"></div>
        <div><label>Email</label><input id="femail" type="email" inputmode="email" autocapitalize="off" autocomplete="off"></div>
      </div>
      <div id="minorBox" hidden style="margin-top:12px"><label>Sei minorenne: nome e cognome del genitore o tutore *</label>
        <input id="ftutore" autocapitalize="words" autocomplete="off"></div>
    </div>

    <div class="card"><h2><span class="step">2</span>Stato di salute</h2>
      <p class="sub" style="margin-top:-6px">Tocca le voci che ti riguardano, anche se passate o in cura.</p>
      <div class="health">${T.health_items.map(h => toggleRow("h:" + h, h, false)).join("")}</div>
      <label style="margin-top:6px">Altro (scrivi qui altre patologie, farmaci o informazioni utili)</label>
      <input id="faltro" autocomplete="off">
      <div style="margin-top:10px">${toggleRow("nessuna", "Nessuna delle condizioni elencate", false)}</div>
      <div style="margin-top:6px">${toggleRow("scheda", T.dichiarazione_scheda, false)}</div>
    </div>

    <div class="card"><h2><span class="step">3</span>${esc(T.consenso_titolo)}</h2>
      <div class="legal">${T.consenso_intro.map(p => `<p>${esc(p)}</p>`).join("")}
        <ul>${T.consenso_punti.map(p => `<li>${esc(p)}</li>`).join("")}</ul>
        ${T.consenso_dichiarazioni.map(p => `<p><b>${esc(p)}</b></p>`).join("")}
        <p><b id="ageText">${esc(T.maggiorenne)}</b></p></div>
      ${toggleRow("consenso", "Ho letto e compreso le informazioni e acconsento al trattamento", false)}
    </div>

    <div class="card"><h2><span class="step">4</span>Privacy</h2>
      <div class="legal"><p><b>${esc(T.informativa_titolo)}</b></p>
        ${T.informativa.map(x => `<p><b>${esc(x.titolo)}.</b> ${esc(x.testo)}</p>`).join("")}</div>
      ${toggleRow("privacy", T.consenso_privacy, false)}
    </div>

    <div class="card"><h2><span class="step">5</span>Firma</h2>
      <div class="grid" style="margin-bottom:10px">
        <div><label>Luogo</label><input id="fluogo" value="${esc(T.luogo_default)}" autocomplete="off"></div>
        <div><label>Data</label><input value="${esc(fmtDay(todayIso()))}" disabled></div></div>
      <label>Firma della cliente</label><div class="sigpad" id="sig"></div>
      <div class="bar" style="margin-top:6px"><button id="sigclear">Cancella firma</button></div>
      <div id="tutoreSig" hidden style="margin-top:14px"><label>Firma del genitore o tutore</label><div class="sigpad" id="sig2"></div>
        <div class="bar" style="margin-top:6px"><button id="sig2clear">Cancella firma</button></div></div>
      <p class="sub">La firma vale per tutte le dichiarazioni spuntate sopra. Riceverai copia del modulo su richiesta.</p>
      <div class="bar"><button class="pink" id="fsend" style="font-size:19px;padding:14px 28px">Firma e invia</button></div>
    </div>`;

  const pad = signaturePad($("#sig")), pad2 = signaturePad($("#sig2"));
  onTap($("#sigclear"), () => pad.clear());
  onTap($("#sig2clear"), () => pad2.clear());
  onTap($("#kexit"), () => { if (confirm("Uscire dal modulo senza firmare? I dati inseriti andranno persi.")) go("#/c/" + id); });

  const setOn = (key, on) => $(`[data-t="${CSS.escape(key)}"]`).classList.toggle("on", on);
  $$(".toggle").forEach(b => onTap(b, () => {
    const k = b.dataset.t, on = !b.classList.contains("on");
    b.classList.toggle("on", on);
    if (k.startsWith("h:")) {
      on ? state.health.add(k.slice(2)) : state.health.delete(k.slice(2));
      if (on && state.nessuna) { state.nessuna = false; setOn("nessuna", false); }
    } else if (k === "nessuna") {
      state.nessuna = on;
      if (on) { state.health.clear(); $$('.toggle[data-t^="h:"]').forEach(x => x.classList.remove("on")); $("#faltro").value = ""; }
    } else state[k] = on;
  }));
  $("#faltro").oninput = () => { if (val("faltro") && state.nessuna) { state.nessuna = false; setOn("nessuna", false); } };
  $$("#fsesso button").forEach(b => onTap(b, () => {
    state.sesso = b.dataset.s; $$("#fsesso button").forEach(x => x.classList.toggle("on", x === b));
  }));
  const minorCheck = () => {
    const a = ageAt(val("fbirth")), minor = a !== null && a < 18;
    $("#minorBox").hidden = !minor; $("#tutoreSig").hidden = !minor;
    $("#ageText").textContent = minor ? T.minorenne : T.maggiorenne;
    return minor;
  };
  $("#fbirth").onchange = minorCheck; minorCheck();

  const need = (cond, msg, el) => { if (!cond) { el?.scrollIntoView({ behavior: "smooth", block: "center" }); throw new Error(msg); } };
  let sending = false;
  onTap($("#fsend"), safe(async () => {
    if (sending) return;
    need(val("fnome") && val("fcognome"), "Scrivi nome e cognome", $("#fnome"));
    need(val("fbirth"), "Indica la data di nascita", $("#fbirth"));
    const minor = minorCheck();
    if (minor) need(val("ftutore"), "Scrivi nome e cognome del genitore o tutore", $("#ftutore"));
    need(state.health.size || val("faltro") || state.nessuna, "Stato di salute: tocca le voci che ti riguardano oppure «Nessuna»", $(".health"));
    need(state.scheda, "Conferma che le informazioni sullo stato di salute sono veritiere", $('[data-t="scheda"]'));
    need(state.consenso, "Conferma di aver letto il consenso informato", $('[data-t="consenso"]'));
    need(state.privacy, "Serve il consenso al trattamento dei dati per procedere", $('[data-t="privacy"]'));
    need(!pad.empty(), "Manca la firma", $("#sig"));
    if (minor) need(!pad2.empty(), "Manca la firma del genitore o tutore", $("#sig2"));
    $("#fsend").disabled = true; sending = true;
    try {
      const res = await post(`/api/clients/${id}/consents`, {
        nome: val("fnome"), cognome: val("fcognome"), birth_date: val("fbirth"), sesso: state.sesso,
        indirizzo: val("findirizzo") || null, email: val("femail") || null, tel: val("ftel") || null,
        health: [...state.health], altro: val("faltro") || null, nessuna: state.nessuna,
        accetta_scheda: state.scheda, accetta_consenso: state.consenso, accetta_privacy: state.privacy,
        luogo: val("fluogo") || null, tutore: minor ? val("ftutore") : null,
        signature: pad.png(), signature_tutore: minor ? pad2.png() : null,
      });
      window.scrollTo(0, 0);
      $("#view").innerHTML = `<div class="card" style="text-align:center;padding:48px 20px">
        <div style="font-size:56px">✅</div><h2 style="font-size:26px">Grazie, ${esc(val("fnome") || "")}!</h2>
        <p style="font-size:19px">Il modulo è stato firmato. Puoi restituire l'iPad all'operatrice.</p>
        ${res.archive_error ? `<p class="sub" style="color:var(--err)">Per l'operatrice: modulo salvato, ma la copia sul Synology è in sospeso (${esc(res.archive_error)}).</p>` : ""}
        <div class="bar" style="justify-content:center;margin-top:16px">
          <button id="kprint">🖨 Stampa una copia per la cliente</button>
          <button class="primary" id="kdone">Torna alla scheda (operatrice)</button></div></div>`;
      printButton($("#kprint"), () => post(`/api/consents/${res.id}/print`, { copies: 1 }), "Copia inviata alla stampante");
      onTap($("#kdone"), () => go("#/c/" + id + "/laser"));
    } finally { sending = false; const b = $("#fsend"); if (b) b.disabled = false; }
  }));
}

/* ---------- modulo firmato: consultazione ---------- */
async function consentDetailView(cid) {
  const [m, T] = await Promise.all([api("/api/consents/" + cid), consentTexts()]);
  const d = m.data;
  setTitle("Modulo firmato");
  const yn = (b) => b ? "✓" : "—";
  $("#view").innerHTML = `
    <div class="card"><h2>${esc(d.nome)} ${esc(d.cognome)} · modulo n. ${m.id}</h2>
      <p class="sub">Firmato il ${fmtDay(m.signed_at.slice(0, 10))} alle ${m.signed_at.slice(11, 16)} a ${esc(d.luogo)} · testi versione ${esc(m.text_version)}</p>
      <div class="meta">
        <div><b>Data di nascita</b>${fmtDay(d.birth_date)}${d.minorenne ? " (minorenne)" : ""}</div>
        <div><b>Sesso</b>${esc(d.sesso || "—")}</div><div><b>Telefono</b>${esc(d.tel || "—")}</div>
        <div><b>Email</b>${esc(d.email || "—")}</div><div><b>Indirizzo</b>${esc(d.indirizzo || "—")}</div>
        ${d.tutore ? `<div><b>Genitore/tutore</b>${esc(d.tutore)}</div>` : ""}</div>
      <h2 style="margin-top:14px">Stato di salute</h2>
      <p>${d.nessuna ? "<b>Nessuna delle condizioni elencate</b>" : (d.health.map(esc).join(" · ") || "—")}${d.altro ? `<br><b>Altro:</b> ${esc(d.altro)}` : ""}</p>
      <p class="sub">Dichiarazione veridicità ${yn(d.accetta_scheda)} · Consenso informato ${yn(d.accetta_consenso)} · Consenso privacy ${yn(d.accetta_privacy)}</p>
      <label>Firma</label><img class="sigimg" src="${m.signature}" alt="firma">
      ${m.signature_tutore ? `<label style="margin-top:10px">Firma genitore/tutore</label><img class="sigimg" src="${m.signature_tutore}" alt="firma tutore">` : ""}
      <p class="sub" style="margin-top:12px">Archivio: ${m.copied_at ? `copiato sul Synology il ${fmtDay(m.copied_at.slice(0, 10))}` : `<span style="color:var(--err)">copia sul Synology in sospeso</span>`}
        · file ${esc(m.pdf_file)}<br>Impronta: <span style="font-size:12px">${esc(m.fingerprint)}</span></p>
      <div class="bar"><button class="primary" id="mprint">🖨 Stampa</button>
        <a class="btn" href="${pdfLink(`api/consents/${m.id}/pdf`)}" target="_blank" rel="noopener">📄 Apri il PDF</a>
        <a class="btn" href="#/c/${m.client_id}/laser">Torna alla scheda</a></div>
    </div>`;
  printButton($("#mprint"), () => post(`/api/consents/${m.id}/print`, { copies: 1 }), "Modulo inviato alla stampante");
}

/* ---------- scheda fotoepilazione: avviso modulo, check up, moduli firmati ---------- */
async function laserExtras(c) {
  const [T, cu, list, paper] = await Promise.all([consentTexts(), api(`/api/clients/${c.id}/checkup`),
    api(`/api/clients/${c.id}/consents`), api(`/api/clients/${c.id}/paper-consents`)]);
  const tab = $("#tab");
  if (!hasConsent(c)) {
    tab.insertAdjacentHTML("afterbegin", `<div class="card warn no-print"><div class="bar">
      <span class="grow">⚠️ <b>Manca il modulo privacy e consenso firmato.</b> Fallo firmare prima del primo trattamento.</span>
      <button class="paperBtn">📄 Ha già firmato il cartaceo</button>
      <a class="btn pinkbtn" href="#/c/${c.id}/modulo">📝 Fai firmare</a></div><div class="paperForm" hidden></div></div>`);
    paperConsentButtons(c);
  }

  // riepilogo check up anche nella stampa del diario
  const summary = T.checkup.map(f => {
    const v = cu.data[f.key]; const s = Array.isArray(v) ? v.join(", ") : v;
    return s ? `${f.label}: ${s}${f.key === "frequenza" && cu.data.frequenza_cad ? " (" + cu.data.frequenza_cad + ")" : ""}` : null;
  }).filter(Boolean).join(" · ");
  $(".meta", tab)?.insertAdjacentHTML("afterend", summary ? `<p class="print-only" style="font-size:12px;margin:0 0 8px"><b>Check up:</b> ${esc(summary)}</p>` : "");

  tab.insertAdjacentHTML("beforeend", `
    <div class="card no-print" id="checkupCard"><h2>Check up</h2>
      <div class="cu">${T.checkup.map(f => `<label style="margin:0">${esc(f.label)}</label>
        <div class="zones">${f.options.map(o => {
          const v = cu.data[f.key]; const on = Array.isArray(v) ? v.includes(o) : v === o;
          return `<button type="button" class="zchip${on ? " on" : ""}" data-k="${f.key}" data-m="${f.multi ? 1 : 0}" data-o="${esc(o)}">${esc(o)}</button>`;
        }).join("")}${f.key === "frequenza" ? `<input id="cucad" placeholder="cad. (es. ogni 3 settimane)" value="${esc(cu.data.frequenza_cad)}" style="max-width:260px;min-height:38px">` : ""}</div>`).join("")}
      </div>
      <div class="bar" style="margin-top:12px"><button class="primary" id="cusave">Salva check up</button>
        <span class="sub">${cu.updated_at ? `Aggiornato il ${fmtDay(cu.updated_at.slice(0, 10))}${cu.operator ? " da " + esc(cu.operator) : ""}` : "Non ancora compilato"}</span></div>
    </div>
    <div class="card no-print" id="consentsCard"><div class="bar" style="margin-bottom:8px"><h2 class="grow" style="margin:0">Consensi privacy</h2>
      ${list.length ? `<button id="printAllClient">🖨 Stampa tutti${list.length > 1 ? ` (${list.length})` : ""}</button>` : ""}</div>
      ${list.length ? list.map(m => `<a class="row" href="#/modulo/${m.id}"><span class="grow"><b>Modulo n. ${m.id}</b> · firmato il ${fmtDay(m.signed_at.slice(0, 10))}<br>
        <span class="sub">${m.nessuna ? "Nessuna condizione di salute" : esc([...m.health, m.altro].filter(Boolean).join(", ") || "—")}</span></span>
        ${m.copied_at ? "" : `<span class="pill" style="color:var(--err)">copia Synology in sospeso</span>`}<span class="sub">›</span></a>`).join("")
        : (paper.length ? "" : `<div class="empty">Nessun modulo firmato</div>`)}
      ${paper.map(pc => `<div class="row"><span class="grow"><b>📄 Consenso cartaceo</b> · firmato il ${fmtDay(pc.signed_on)}<br>
        <span class="sub">${[pc.note, pc.operator ? "registrato da " + pc.operator : null].filter(Boolean).map(esc).join(" · ") || "foglio in archivio cartaceo"}</span></span>
        <span class="pill">cartaceo</span><button class="danger" data-paperdel="${pc.id}">Rimuovi</button></div>`).join("")}
    </div>`);
  $$("[data-paperdel]").forEach(b => b.onclick = safe(async () => {
    if (!confirm("Rimuovere la registrazione del consenso cartaceo? (il foglio di carta non viene toccato)")) return;
    await api("/api/paper-consents/" + b.dataset.paperdel, { method: "DELETE" }); toast("Registrazione rimossa"); router();
  }));

  printButton($("#printAllClient"), () => post(`/api/clients/${c.id}/consents/print`, {}),
    (r) => `${r.printed} ${r.printed === 1 ? "modulo inviato" : "moduli inviati"} alla stampante`);
  $$("#checkupCard .zchip").forEach(b => b.onclick = () => {
    if (b.dataset.m !== "1") $$(`#checkupCard .zchip[data-k="${b.dataset.k}"]`).forEach(x => { if (x !== b) x.classList.remove("on"); });
    b.classList.toggle("on");
  });
  $("#cusave").onclick = safe(async () => {
    const data = {};
    for (const f of T.checkup) {
      const on = $$(`#checkupCard .zchip.on[data-k="${f.key}"]`).map(x => x.dataset.o);
      data[f.key] = f.multi ? on : (on[0] || null);
    }
    data.frequenza_cad = val("cucad") || null;
    await post(`/api/clients/${c.id}/checkup`, { data, operator: store.get("salone.operator") || null }, "PUT");
    toast("Check up salvato"); router();
  });
}

/* ---------- impostazioni: stampante di rete ---------- */
async function printerCard(el) {
  el.innerHTML = `<h2>Stampante</h2><p class="sub">Verifica in corso…</p>`;
  const p = await api("/api/printer");
  el.innerHTML = `<h2>Stampante</h2>
    <p class="sub">Indirizzo: <b>${esc(p.address || "non impostato")}</b> (si cambia nella Configurazione dell'add-on, campo «stampante»)<br>
    ${p.error ? `<span style="color:var(--err)">${esc(p.error)}</span>`
      : `<span style="color:var(--ok)">${esc(p.model)} · ${esc(p.state)}</span>${p.message ? " · " + esc(p.message) : ""}<br>
         ${p.pdf ? "Accetta la stampa diretta dei PDF ✅" : `<span style="color:var(--err)">Non accetta PDF via rete: formati ${esc(p.formats.join(", "))}</span>`}`}</p>
    <button id="prRetry">Verifica di nuovo</button>`;
  $("#prRetry").onclick = safe(() => printerCard(el));
}

/* ---------- impostazioni: archivio moduli sul Synology ---------- */
async function archiveCard(el) {
  const st = await api("/api/consents/status");
  el.innerHTML = `<h2>Archivio moduli firmati (Synology)</h2>
    <p class="sub">Cartella: <b>${esc(st.archive_dir || "non impostata")}</b> ·
      ${st.archive_ok ? `<span style="color:var(--ok)">raggiungibile</span>` : `<span style="color:var(--err)">NON raggiungibile</span>`}<br>
      Moduli firmati: <b>${st.total}</b>${st.pending ? ` · <span style="color:var(--err)">${st.pending} da copiare</span>${st.error ? " (" + esc(st.error) + ")" : ""}` : " · tutti copiati"}</p>
    ${!st.archive_ok && st.diagnosi?.length ? `<p class="sub" style="margin-bottom:4px"><b>Diagnosi del percorso:</b></p>
      <div style="font-size:14px;font-family:ui-monospace,monospace">${st.diagnosi.map(d => `<div>${d.ok ? "✅" : "❌"} ${esc(d.path)}${
        d.dentro_al_livello_sopra ? `<div class="sub" style="margin-left:24px">cartelle trovate al livello sopra: ${d.dentro_al_livello_sopra.length ? d.dentro_al_livello_sopra.map(esc).join(", ") : "(nessuna)"}</div>` : ""}</div>`).join("")}</div>` : ""}
    ${st.pending ? `<button class="primary" id="archSync">Riprova la copia</button>` : ""}
    <h2 style="margin-top:18px">Stampa tutti i moduli</h2>
    <p class="sub">Stampa i moduli firmati dell'archivio, in ordine di cognome. Lascia le date vuote per stamparli tutti.</p>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,220px))">
      <div><label>Firmati dal</label><input id="padal" type="date"></div>
      <div><label>al</label><input id="paal" type="date"></div></div>
    <div class="bar" style="margin-top:10px"><button id="pacount">🖨 Stampa tutti i moduli</button></div>
    <div id="pares"></div>`;
  const range = () => ({ dal: val("padal") || null, al: val("paal") || null });
  $("#pacount").onclick = safe(async () => {
    const r = await post("/api/consents/print-all", { ...range(), dry_run: true });
    if (!r.count) { $("#pares").innerHTML = `<p class="sub">Nessun modulo firmato nel periodo scelto.</p>`; return; }
    $("#pares").innerHTML = `<p>Verranno stampati <b>${r.count}</b> moduli, circa <b>${r.pages}</b> pagine.</p>
      <button class="primary" id="pago">Conferma e stampa</button> <button id="pano">Annulla</button>`;
    $("#pano").onclick = () => { $("#pares").innerHTML = ""; };
    printButton($("#pago"), () => post("/api/consents/print-all", { ...range(), dry_run: false }),
      (x) => { $("#pares").innerHTML = ""; return `${x.printed} moduli inviati alla stampante`; });
  });
  $("#archSync")?.addEventListener("click", safe(async () => {
    const r = await post("/api/consents/sync", {});
    toast(r.error ? r.error : `Copiati ${r.copied} moduli`, !r.error); archiveCard(el);
  }));
}
