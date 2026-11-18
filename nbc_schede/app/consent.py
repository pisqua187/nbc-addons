"""Modulo privacy e consenso informato firmato sull'iPad, e check up tecnico della cliente.

Ogni modulo firmato diventa un PDF:
  - salvato in CONSENTS_DIR (dentro /data dell'add-on, quindi nei backup di Home Assistant);
  - copiato in ARCHIVE_DIR (cartella del Synology collegata a Home Assistant). Se il Synology non e'
    raggiungibile la copia resta in sospeso e viene ritentata (avvio, Impostazioni, nuovo modulo).
Un modulo firmato non si modifica e non si cancella dall'app: se cambia qualcosa se ne firma uno nuovo.
"""

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from . import texts
from .db import Database
from .pdf import build_diary_pdf, build_pdf
from .printing import PrinterError, print_pdf, printer_info

PAGE_RE = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")  # conta le pagine di un PDF

log = logging.getLogger("salone.consensi")
MAX_SIGNATURE_BYTES = 600_000
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ConsentIn(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    cognome: str = Field(min_length=1, max_length=80)
    birth_date: date
    sesso: str | None = Field(default=None, pattern="^(F|M)$")
    indirizzo: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=120)
    tel: str | None = Field(default=None, max_length=40)
    health: list[str] = Field(default_factory=list, max_length=len(texts.HEALTH_ITEMS))
    altro: str | None = Field(default=None, max_length=500)
    nessuna: bool = False
    accetta_scheda: bool = False
    accetta_consenso: bool = False
    accetta_privacy: bool = False
    luogo: str | None = Field(default=None, max_length=80)
    tutore: str | None = Field(default=None, max_length=120)
    signature: str = Field(max_length=MAX_SIGNATURE_BYTES * 2)
    signature_tutore: str | None = Field(default=None, max_length=MAX_SIGNATURE_BYTES * 2)


class PaperIn(BaseModel):
    signed_on: date | None = None    # default: oggi
    note: str | None = Field(default=None, max_length=300)
    operator: str | None = Field(default=None, max_length=60)


class PrintIn(BaseModel):
    copies: int = Field(default=1, ge=1, le=10)


class PrintAllIn(BaseModel):
    dal: date | None = None      # data firma, inclusa
    al: date | None = None       # data firma, inclusa
    dry_run: bool = True         # True = conta soltanto, non stampa


class CheckupIn(BaseModel):
    data: dict[str, list[str] | str | None]
    operator: str | None = Field(default=None, max_length=60)


def _clean(v: str | None) -> str | None:
    v = " ".join((v or "").split())
    return v or None


def _png(data_url: str | None, what: str) -> bytes:
    m = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", (data_url or "").strip())
    if not m:
        raise HTTPException(422, f"Manca la {what}")
    raw = base64.b64decode(m.group(1))
    if not raw.startswith(PNG_MAGIC) or len(raw) > MAX_SIGNATURE_BYTES:
        raise HTTPException(422, f"La {what} non è valida, riprova")
    return raw


def age_on(birth: date, day: date) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "cliente"


def build_router(db: Database, now: Callable[[], datetime], consents_dir: str, archive_dir: str) -> APIRouter:
    r = APIRouter()
    store = Path(consents_dir)
    store.mkdir(parents=True, exist_ok=True)
    archive = Path(archive_dir) if archive_dir else None

    def sync_pending() -> dict:
        """Copia sul Synology i PDF non ancora copiati. Non crea la cartella: deve esistere gia'
        (se manca, il Synology non e' collegato e non vogliamo scrivere dentro il Pi per sbaglio)."""
        rows = db.query("SELECT id, pdf_file FROM consents WHERE copied_at IS NULL ORDER BY id")
        if not rows:
            return {"pending": 0, "copied": 0, "error": None}
        if not archive or not archive.is_dir():
            err = f"Cartella archivio non raggiungibile: {archive_dir or '(non impostata)'}"
            db.conn.execute("UPDATE consents SET copy_error = ? WHERE copied_at IS NULL", (err,))
            return {"pending": len(rows), "copied": 0, "error": err}
        copied, err = 0, None
        for row in rows:
            try:
                shutil.copy2(store / row["pdf_file"], archive / row["pdf_file"])
                db.conn.execute("UPDATE consents SET copied_at = ?, copy_error = NULL WHERE id = ?",
                                (now().isoformat(timespec="seconds"), row["id"]))
                copied += 1
            except OSError as e:
                err = f"Copia non riuscita: {e}"
                db.conn.execute("UPDATE consents SET copy_error = ? WHERE id = ?", (err, row["id"]))
                log.warning("copia modulo %s fallita: %s", row["id"], e)
        return {"pending": len(rows) - copied, "copied": copied, "error": err}

    r.sync_pending = sync_pending  # usato all'avvio

    def client_or_404(client_id: int) -> dict:
        c = db.one("SELECT id, name, phone, birth_date FROM clients WHERE id = ?", (client_id,))
        if not c:
            raise HTTPException(404, "Cliente non trovata")
        return c

    COLS = ("id, client_id, signed_at, text_version, pdf_file, pdf_sha256, copied_at, copy_error, "
            "json_extract(data, '$.health') AS health, json_extract(data, '$.altro') AS altro, "
            "json_extract(data, '$.nessuna') AS nessuna")

    @r.get("/api/texts")
    def get_texts():
        return texts.as_dict()

    @r.get("/api/clients/{client_id}/consents")
    def list_consents(client_id: int):
        client_or_404(client_id)
        rows = db.query(f"SELECT {COLS} FROM consents WHERE client_id = ? ORDER BY id DESC", (client_id,))
        for row in rows:
            row["health"] = json.loads(row["health"] or "[]")
        return rows

    @r.post("/api/clients/{client_id}/consents", status_code=201)
    def sign_consent(client_id: int, body: ConsentIn, request: Request):
        client = client_or_404(client_id)
        ts = now()
        health = [h for h in texts.HEALTH_ITEMS if h in set(body.health)]
        if len(health) != len(set(body.health)):
            raise HTTPException(422, "Voce dello stato di salute non riconosciuta")
        altro = _clean(body.altro)
        if body.nessuna and (health or altro):
            raise HTTPException(422, "Hai indicato «nessuna» ma anche delle condizioni: controlla lo stato di salute")
        if not (body.nessuna or health or altro):
            raise HTTPException(422, "Stato di salute: spunta le voci che ti riguardano oppure «nessuna»")
        if not (body.accetta_scheda and body.accetta_consenso and body.accetta_privacy):
            raise HTTPException(422, "Per procedere servono tutte e tre le conferme")
        if body.birth_date > ts.date():
            raise HTTPException(422, "Controlla la data di nascita")
        minor = age_on(body.birth_date, ts.date()) < 18
        sig = _png(body.signature, "firma")
        sig_t = None
        if minor:
            if not _clean(body.tutore):
                raise HTTPException(422, "Cliente minorenne: serve il nome del genitore o tutore")
            sig_t = _png(body.signature_tutore, "firma del genitore o tutore")

        data = {
            "nome": _clean(body.nome), "cognome": _clean(body.cognome), "birth_date": body.birth_date.isoformat(),
            "sesso": body.sesso, "indirizzo": _clean(body.indirizzo), "email": _clean(body.email),
            "tel": _clean(body.tel), "health": health, "altro": altro, "nessuna": body.nessuna,
            "accetta_scheda": True, "accetta_consenso": True, "accetta_privacy": True,
            "luogo": _clean(body.luogo) or texts.LUOGO_DEFAULT, "minorenne": minor,
            "tutore": _clean(body.tutore) if minor else None,
        }
        signed_at = ts.isoformat(timespec="seconds")
        device = (request.headers.get("user-agent") or "")[:300]
        # Impronta di dati + firme: stampata sul PDF, permette di riconoscere modifiche successive.
        fingerprint = hashlib.sha256(json.dumps(
            {"data": data, "signed_at": signed_at, "text_version": texts.TEXT_VERSION,
             "sig": hashlib.sha256(sig).hexdigest(),
             "sig_t": hashlib.sha256(sig_t).hexdigest() if sig_t else None},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()

        with db.tx() as conn:
            cid = conn.execute(
                "INSERT INTO consents(client_id, signed_at, text_version, data, signature, signature_tutore, "
                "fingerprint, device, pdf_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')",
                (client_id, signed_at, texts.TEXT_VERSION, json.dumps(data, ensure_ascii=False), sig, sig_t,
                 fingerprint, device)).lastrowid
            fname = f"{_slug(data['cognome'])}_{_slug(data['nome'])}_{ts.date().isoformat()}_modulo{cid}.pdf"
            pdf = build_pdf(data, sig, sig_t, ts, cid, fingerprint)
            tmp = store / (fname + ".tmp")
            tmp.write_bytes(pdf)
            tmp.replace(store / fname)
            conn.execute("UPDATE consents SET pdf_file = ?, pdf_sha256 = ? WHERE id = ?",
                         (fname, hashlib.sha256(pdf).hexdigest(), cid))
            # completa la scheda cliente solo dove e' vuota (nome/cellulare li gestisce l'import Vaniglia)
            if not client["birth_date"]:
                conn.execute("UPDATE clients SET birth_date = ? WHERE id = ?", (data["birth_date"], client_id))
            if not client["phone"] and data["tel"]:
                conn.execute("UPDATE clients SET phone = ? WHERE id = ?", (data["tel"], client_id))
        sync = sync_pending()
        out = db.one(f"SELECT {COLS} FROM consents WHERE id = ?", (cid,))
        out["health"] = health
        out["archive_error"] = sync["error"]
        return out

    @r.get("/api/consents/status")
    def consents_status():
        pending = db.one("SELECT COUNT(*) AS n, MAX(copy_error) AS err FROM consents WHERE copied_at IS NULL")
        return {"archive_dir": archive_dir, "archive_ok": bool(archive and archive.is_dir()),
                "pending": pending["n"], "error": pending["err"],
                "total": db.one("SELECT COUNT(*) AS n FROM consents")["n"], "diagnosi": diagnose()}

    def diagnose() -> list[dict]:
        """Per ogni livello del percorso: esiste? e cosa c'e' dentro l'ultimo livello raggiunto.
        Serve a capire dalle Impostazioni dove si blocca il collegamento al Synology."""
        if not archive:
            return []
        out, cur = [], Path("/")
        for part in archive.parts[1:]:
            cur = cur / part
            try:
                ok = cur.is_dir()
            except OSError:
                ok = False
            out.append({"path": str(cur), "ok": ok})
            if not ok:
                parent = cur.parent
                try:
                    inside = sorted(x.name for x in parent.iterdir() if x.is_dir())[:30]
                except OSError as e:
                    inside = [f"(non leggibile: {e.strerror})"]
                out[-1]["dentro_al_livello_sopra"] = inside
                break
        return out

    @r.get("/api/consents/{consent_id}")
    def consent_detail(consent_id: int):
        row = db.one("SELECT id, client_id, signed_at, text_version, data, signature, signature_tutore, "
                     "fingerprint, pdf_file, pdf_sha256, copied_at, copy_error FROM consents WHERE id = ?",
                     (consent_id,))
        if not row:
            raise HTTPException(404, "Modulo non trovato")
        row["data"] = json.loads(row["data"])
        for k in ("signature", "signature_tutore"):
            row[k] = "data:image/png;base64," + base64.b64encode(row[k]).decode() if row[k] else None
        return row

    @r.get("/api/consents/{consent_id}/pdf")
    def consent_pdf(consent_id: int):
        row = db.one("SELECT pdf_file FROM consents WHERE id = ?", (consent_id,))
        if not row or not row["pdf_file"] or not (store / row["pdf_file"]).is_file():
            raise HTTPException(404, "Modulo non trovato")
        return FileResponse(store / row["pdf_file"], media_type="application/pdf", filename=row["pdf_file"],
                            content_disposition_type="inline")

    @r.post("/api/consents/sync")
    def consents_sync():
        return sync_pending()

    # --- consenso cartaceo gia' firmato -----------------------------------------
    @r.get("/api/clients/{client_id}/paper-consents")
    def list_paper(client_id: int):
        client_or_404(client_id)
        return db.query("SELECT id, signed_on, note, operator, created_at FROM paper_consents "
                        "WHERE client_id = ? ORDER BY signed_on DESC, id DESC", (client_id,))

    @r.post("/api/clients/{client_id}/paper-consents", status_code=201)
    def add_paper(client_id: int, body: PaperIn):
        client_or_404(client_id)
        day = body.signed_on or now().date()
        if day > now().date():
            raise HTTPException(422, "La data della firma non può essere nel futuro")
        pid = db.conn.execute(
            "INSERT INTO paper_consents(client_id, signed_on, note, operator) VALUES (?, ?, ?, ?)",
            (client_id, day.isoformat(), _clean(body.note), _clean(body.operator))).lastrowid
        return db.one("SELECT id, signed_on, note, operator, created_at FROM paper_consents WHERE id = ?", (pid,))

    @r.delete("/api/paper-consents/{paper_id}", status_code=204)
    def delete_paper(paper_id: int):
        if db.conn.execute("DELETE FROM paper_consents WHERE id = ?", (paper_id,)).rowcount == 0:
            raise HTTPException(404, "Registrazione non trovata")

    # --- stampa sulla stampante di rete ---------------------------------------
    printer = os.getenv("PRINTER", "").strip()

    def send(pdf: bytes, name: str, copies: int = 1) -> dict:
        try:
            return print_pdf(printer, pdf, name, copies)
        except PrinterError as e:
            raise HTTPException(502, str(e))

    def consent_bytes(consent_id: int) -> tuple[bytes, str]:
        row = db.one("SELECT pdf_file FROM consents WHERE id = ?", (consent_id,))
        if not row or not (store / row["pdf_file"]).is_file():
            raise HTTPException(404, "Modulo non trovato")
        return (store / row["pdf_file"]).read_bytes(), row["pdf_file"]

    def print_many(ids: list[int]) -> dict:
        done = 0
        for i in ids:
            pdf, name = consent_bytes(i)
            try:
                print_pdf(printer, pdf, name)
            except PrinterError as e:
                raise HTTPException(502, f"{e}. Stampati {done} moduli su {len(ids)}.")
            done += 1
        return {"printed": done}

    @r.get("/api/printer")
    def get_printer():
        try:
            return {"address": printer, **printer_info(printer)}
        except PrinterError as e:
            return {"address": printer, "error": str(e)}

    @r.post("/api/consents/{consent_id}/print")
    def print_consent(consent_id: int, body: PrintIn):
        pdf, name = consent_bytes(consent_id)
        return send(pdf, name, body.copies)

    @r.post("/api/clients/{client_id}/consents/print")
    def print_client_consents(client_id: int):
        client_or_404(client_id)
        ids = [x["id"] for x in db.query("SELECT id FROM consents WHERE client_id = ? ORDER BY id", (client_id,))]
        if not ids:
            raise HTTPException(404, "Nessun modulo firmato da stampare")
        return print_many(ids)

    @r.post("/api/consents/print-all")
    def print_all_consents(body: PrintAllIn):
        """Tutti i moduli dell'archivio (eventualmente in un intervallo di date), in ordine di cognome."""
        where, params = [], []
        if body.dal:
            where.append("substr(signed_at, 1, 10) >= ?"); params.append(body.dal.isoformat())
        if body.al:
            where.append("substr(signed_at, 1, 10) <= ?"); params.append(body.al.isoformat())
        rows = db.query("SELECT id FROM consents" + (" WHERE " + " AND ".join(where) if where else "")
                        + " ORDER BY json_extract(data, '$.cognome') COLLATE NOCASE, "
                          "json_extract(data, '$.nome') COLLATE NOCASE, id", params)
        ids = [x["id"] for x in rows]
        if body.dry_run:
            pages = 0
            for i in ids:  # conta le pagine dai PDF (3 o piu' a modulo)
                pdf, _ = consent_bytes(i)
                pages += max(1, len(PAGE_RE.findall(pdf)))
            return {"count": len(ids), "pages": pages}
        if not ids:
            raise HTTPException(404, "Nessun modulo firmato nel periodo scelto")
        return print_many(ids)

    def diary(client_id: int) -> tuple[bytes, str]:
        c = db.one("SELECT id, name, birth_date FROM clients WHERE id = ?", (client_id,))
        if not c:
            raise HTTPException(404, "Cliente non trovata")
        rows = db.query("SELECT day, zone, power, fluence, hz, hydration, operator FROM laser_treatments WHERE client_id = ? "
                        "ORDER BY day, id", (client_id,))
        cu = db.one("SELECT data FROM checkups WHERE client_id = ?", (client_id,))
        name = f"Diario_{_slug(c['name'])}.pdf"
        return build_diary_pdf(c, rows, json.loads(cu["data"]) if cu else {}), name

    @r.get("/api/clients/{client_id}/laser/pdf")
    def diary_pdf(client_id: int):
        pdf, name = diary(client_id)
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{name}"'})

    @r.post("/api/clients/{client_id}/laser/print")
    def diary_print(client_id: int, body: PrintIn):
        pdf, name = diary(client_id)
        return send(pdf, name, body.copies)

    # --- check up tecnico (compilato dall'operatrice) ---------------------------
    @r.get("/api/clients/{client_id}/checkup")
    def get_checkup(client_id: int):
        client_or_404(client_id)
        row = db.one("SELECT data, operator, updated_at FROM checkups WHERE client_id = ?", (client_id,))
        return {"data": json.loads(row["data"]) if row else {}, "operator": row["operator"] if row else None,
                "updated_at": row["updated_at"] if row else None}

    @r.put("/api/clients/{client_id}/checkup")
    def put_checkup(client_id: int, body: CheckupIn):
        client_or_404(client_id)
        allowed = {k: (opts, multi) for k, _, opts, multi in texts.CHECKUP}
        clean: dict = {}
        for k, v in body.data.items():
            if k == "frequenza_cad":
                clean[k] = _clean(v if isinstance(v, str) else None)
                continue
            if k not in allowed:
                raise HTTPException(422, f"Campo check up sconosciuto: {k}")
            opts, multi = allowed[k]
            vals = v if isinstance(v, list) else ([v] if v else [])
            if any(x not in opts for x in vals) or (not multi and len(vals) > 1):
                raise HTTPException(422, f"Valore non valido per {k}")
            clean[k] = vals if multi else (vals[0] if vals else None)
        db.conn.execute(
            "INSERT INTO checkups(client_id, data, operator, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(client_id) DO UPDATE SET data = excluded.data, operator = excluded.operator, "
            "updated_at = excluded.updated_at",
            (client_id, json.dumps(clean, ensure_ascii=False), _clean(body.operator),
             now().isoformat(timespec="seconds")))
        return get_checkup(client_id)

    return r


def default_dirs() -> tuple[str, str]:
    db_dir = Path(os.getenv("DB_PATH", "data/salone.db")).parent
    return (os.getenv("CONSENTS_DIR", str(db_dir / "consensi")), os.getenv("ARCHIVE_DIR", ""))
