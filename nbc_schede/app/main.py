"""Server del salone: clienti, storico smalti, fotoepilazione. API REST + app web per iPad."""

import logging
import os
import secrets
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .db import Database
from .importer import import_clients
from .laser import build_router

log = logging.getLogger("salone")
TZ = ZoneInfo(os.getenv("TZ_NAME", "Europe/Rome"))
STATIC = Path(__file__).parent / "static"


def today() -> date:
    return datetime.now(TZ).date()


def clean(v: str | None) -> str | None:
    v = " ".join((v or "").split())
    return v or None


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


# --- modelli richieste ----------------------------------------------------------
class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    birth_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not clean(v):
            raise ValueError("Scrivi il nome")
        return clean(v)


class RecordIn(BaseModel):
    polish: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    operator: str | None = Field(default=None, max_length=60)
    day: date | None = None  # default: oggi

    @field_validator("polish")
    @classmethod
    def polish_not_blank(cls, v: str) -> str:
        if not clean(v):
            raise ValueError("Scrivi lo smalto")
        return clean(v)


class ImportIn(BaseModel):
    csv: str = Field(max_length=20_000_000)  # testo del file, gia' decodificato dal browser
    apply: bool = False


# --- app ------------------------------------------------------------------------
def create_app(db_path: str | None = None, api_key: str | None = None) -> FastAPI:
    db = Database(db_path or os.getenv("DB_PATH", "data/salone.db"))
    key = api_key if api_key is not None else os.getenv("API_KEY", "")

    def check_key(x_api_key: str = Header(default="")):
        if key and not secrets.compare_digest(x_api_key, key):
            raise HTTPException(401, "Chiave di accesso mancante o errata")

    app = FastAPI(title="Salone")
    app.state.db = db
    api = Depends(check_key)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        # ?v=<data modifica> obbliga Safari a scaricare app.js nuovo dopo ogni aggiornamento
        v = int((STATIC / "app.js").stat().st_mtime)
        html = (STATIC / "index.html").read_text(encoding="utf-8").replace(
            '"static/app.js"', f'"static/app.js?v={v}"')
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @app.get("/api/status", dependencies=[api])
    def status():
        return {"today": today().isoformat(),
                "clients": db.one("SELECT COUNT(*) AS n FROM clients")["n"]}

    # --- clienti ----------------------------------------------------------------
    COLS = "id, name, phone, birth_date, notes, external_id, origin"

    def client_or_404(client_id: int) -> dict:
        c = db.one(f"SELECT {COLS} FROM clients WHERE id = ?", (client_id,))
        if not c:
            raise HTTPException(404, "Cliente non trovata")
        return c

    @app.get("/api/clients", dependencies=[api])
    def search_clients(q: str = Query(default="", max_length=60)):
        """Ogni parola deve comparire nel nome o nel cellulare: 'rossi giu' trova 'Giulia Rossi'."""
        words = q.split()[:5]
        if not words:
            return []
        where = " AND ".join(["(name LIKE ? OR phone LIKE ?)"] * len(words))
        params = [p for w in words for p in (f"%{w}%", f"%{w}%")]
        return db.query(f"SELECT {COLS} FROM clients WHERE {where} "
                        "ORDER BY name COLLATE NOCASE LIMIT 50", params)

    @app.get("/api/clients/recent", dependencies=[api])
    def recent_clients():
        """Clienti con attivita' recente (smalto, fotoepilazione) o appena create dall'app."""
        return db.query(
            """
            SELECT c.id, c.name, c.phone, c.birth_date, c.notes, c.external_id, c.origin,
                   MAX(x.at) AS last
            FROM clients c JOIN (
                SELECT client_id, created_at AS at FROM polish_records
                UNION ALL SELECT client_id, created_at FROM laser_treatments
                UNION ALL SELECT id, created_at FROM clients WHERE origin = 'app'
            ) x ON x.client_id = c.id
            GROUP BY c.id ORDER BY last DESC, c.id DESC LIMIT 20
            """
        )

    @app.post("/api/clients", dependencies=[api], status_code=201)
    def create_client(body: ClientIn):
        cur = db.conn.execute("INSERT INTO clients(name, phone, birth_date, notes) VALUES (?, ?, ?, ?)",
                              (body.name, clean(body.phone), iso(body.birth_date), clean(body.notes)))
        return client_or_404(cur.lastrowid)

    @app.put("/api/clients/{client_id}", dependencies=[api])
    def update_client(client_id: int, body: ClientIn):
        client_or_404(client_id)
        db.conn.execute("UPDATE clients SET name = ?, phone = ?, birth_date = ?, notes = ?, "
                        "updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
                        (body.name, clean(body.phone), iso(body.birth_date), clean(body.notes), client_id))
        return client_or_404(client_id)

    @app.get("/api/clients/{client_id}", dependencies=[api])
    def client_detail(client_id: int):
        c = client_or_404(client_id)
        c["polish_history"] = db.query(
            "SELECT id, day, polish, notes, operator FROM polish_records "
            "WHERE client_id = ? ORDER BY day DESC, id DESC", (client_id,))
        return c

    # --- smalti -----------------------------------------------------------------
    @app.post("/api/clients/{client_id}/records", dependencies=[api], status_code=201)
    def add_record(client_id: int, body: RecordIn):
        client_or_404(client_id)
        cur = db.conn.execute(
            "INSERT INTO polish_records(client_id, day, polish, notes, operator) VALUES (?, ?, ?, ?, ?)",
            (client_id, (body.day or today()).isoformat(), body.polish, clean(body.notes),
             clean(body.operator)))
        return {"id": cur.lastrowid}

    @app.delete("/api/records/{record_id}", dependencies=[api], status_code=204)
    def delete_record(record_id: int):
        if db.conn.execute("DELETE FROM polish_records WHERE id = ?", (record_id,)).rowcount == 0:
            raise HTTPException(404, "Registrazione non trovata")

    @app.get("/api/suggestions", dependencies=[api])
    def suggestions(q: str = Query(default="", max_length=60)):
        """Smalti gia' scritti che contengono tutte le parole digitate, dai piu' usati."""
        words = q.split()[:5]
        where = " AND ".join(["polish LIKE ?"] * len(words)) or "1"
        rows = db.query(
            f"SELECT polish, COUNT(*) AS n, MAX(day) AS last FROM polish_records WHERE {where} "
            "GROUP BY polish COLLATE NOCASE ORDER BY n DESC, last DESC LIMIT 6",
            tuple(f"%{w}%" for w in words))
        return [r["polish"] for r in rows]

    # --- import anagrafica dall'export di Vaniglia -----------------------------
    @app.post("/api/import-clients", dependencies=[api])
    def import_endpoint(body: ImportIn):
        try:
            return import_clients(db, body.csv, apply=body.apply)
        except (ValueError, KeyError) as e:
            raise HTTPException(422, str(e))

    app.include_router(build_router(db, today), dependencies=[api])
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Avvio: uvicorn --factory app.main:create_app
