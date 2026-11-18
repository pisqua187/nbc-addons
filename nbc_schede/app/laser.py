"""Fotoepilazione: trattamenti per cliente, e lista operatrici."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .db import Database

# Zone da selezionare sull'iPad (in ordine alfabetico). Oltre a queste c'e' "Personalizzato".
ZONES = sorted(["Inguine", "Inguine parziale", "Ascelle", "Schiena", "Petto", "Addome", "Braccia",
                "Mento", "Viso", "Baffetti", "Gamba intera", "Mezza gamba", "Glutei"], key=str.lower)


def _num(d: Decimal) -> str:
    """12.50 -> '12,5'; 25 -> '25' (virgola italiana, senza zeri inutili)."""
    s = format(d.normalize(), "f")
    return s.replace(".", ",")


def _clean(v: str | None) -> str | None:
    v = " ".join((v or "").split())
    return v or None


class OperatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class TreatmentIn(BaseModel):
    day: date | None = None                               # data del trattamento (default oggi)
    zone: str = Field(min_length=1, max_length=400)       # zone trattate, es. "Ascelle, Inguine"
    power: str | None = Field(default=None, max_length=20)    # Potenza impostata sull'apparecchio
    fluence: str | None = Field(default=None, max_length=20)  # J/cm²: calcolato = potenza / 2 (vecchie schede: inserito a mano)
    hz: str | None = Field(default=None, max_length=20)       # Freq. Hz
    hydration: str | None = Field(default=None, pattern="^(basso|medio|alto)$")  # idratazione pelle
    operator: str | None = Field(default=None, max_length=60)


def build_router(db: Database, today: Callable[[], date]) -> APIRouter:
    r = APIRouter()

    # --- operatrici -------------------------------------------------------------
    @r.get("/api/operators")
    def operators():
        return db.query("SELECT id, name FROM operators WHERE active = 1 ORDER BY name COLLATE NOCASE")

    @r.post("/api/operators", status_code=201)
    def add_operator(body: OperatorIn):
        name = _clean(body.name)
        db.conn.execute(
            "INSERT INTO operators(name) VALUES (?) ON CONFLICT(name) DO UPDATE SET active = 1", (name,))
        return db.one("SELECT id, name FROM operators WHERE name = ?", (name,))

    @r.delete("/api/operators/{op_id}", status_code=204)
    def remove_operator(op_id: int):
        # disattivata, non cancellata: i trattamenti vecchi mantengono il nome
        if db.conn.execute("UPDATE operators SET active = 0 WHERE id = ?", (op_id,)).rowcount == 0:
            raise HTTPException(404, "Operatrice non trovata")

    # --- trattamenti ------------------------------------------------------------
    def values(body: TreatmentIn):
        zone = _clean(body.zone)
        if not zone:
            raise HTTPException(422, "Indica la zona trattata")
        power, fluence = _clean(body.power), _clean(body.fluence)
        if power:
            try:
                p = Decimal(power.replace(",", "."))
            except InvalidOperation:
                raise HTTPException(422, "Potenza: scrivi un numero, es. 25 oppure 24,5")
            if p <= 0 or p > 1000:
                raise HTTPException(422, "Potenza: valore non valido")
            power, fluence = _num(p), _num(p / 2)   # J/cm² = metà della potenza
        return ((body.day or today()).isoformat(), zone, power, fluence, _clean(body.hz),
                body.hydration, _clean(body.operator))

    @r.get("/api/clients/{client_id}/laser")
    def client_treatments(client_id: int):
        return db.query("SELECT * FROM laser_treatments WHERE client_id = ? ORDER BY day, id", (client_id,))

    @r.post("/api/clients/{client_id}/laser", status_code=201)
    def add_treatment(client_id: int, body: TreatmentIn):
        if not db.one("SELECT 1 FROM clients WHERE id = ?", (client_id,)):
            raise HTTPException(404, "Cliente non trovata")
        cur = db.conn.execute(
            "INSERT INTO laser_treatments(client_id, day, zone, power, fluence, hz, hydration, operator) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_id, *values(body)))
        return db.one("SELECT * FROM laser_treatments WHERE id = ?", (cur.lastrowid,))

    @r.put("/api/laser/{treatment_id}")
    def update_treatment(treatment_id: int, body: TreatmentIn):
        cur = db.conn.execute(
            "UPDATE laser_treatments SET day = ?, zone = ?, power = ?, fluence = ?, hz = ?, hydration = ?, "
            "operator = ? WHERE id = ?",
            (*values(body), treatment_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Trattamento non trovato")
        return db.one("SELECT * FROM laser_treatments WHERE id = ?", (treatment_id,))

    @r.delete("/api/laser/{treatment_id}", status_code=204)
    def delete_treatment(treatment_id: int):
        if db.conn.execute("DELETE FROM laser_treatments WHERE id = ?", (treatment_id,)).rowcount == 0:
            raise HTTPException(404, "Trattamento non trovato")

    @r.get("/api/laser-zones")
    def zones():
        """Zone predefinite, in ordine alfabetico."""
        return ZONES

    return r
