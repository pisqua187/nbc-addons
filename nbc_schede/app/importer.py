"""Import dell'anagrafica clienti dall'export CSV di Vaniglia Pro.

Si possono reimportare export successivi: le clienti si riconoscono dal "Cod. Cliente"
e vengono aggiornate, non duplicate. Storico smalti e fotoepilazione non si toccano.

Si importano SOLO nome, cognome, cellulare, data di nascita e codice cliente: indirizzo,
codice fiscale, email ecc. non servono all'app e restano fuori (minimizzazione GDPR).
"""

import csv
import io
import re
from datetime import date, timedelta

from .db import Database

REQUIRED = {"Nome", "Cognome", "Tel. Cellulare", "Cod. Cliente"}


def decode(raw: bytes) -> str:
    """L'export di Vaniglia e' in Windows-1252; si accetta anche UTF-8."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Codifica del file non riconosciuta")


def nice_name(s: str) -> str:
    """'ROSSI' / 'rossi' -> 'Rossi', "d'angelo" -> "D'Angelo"; 'McKenzie' resta com'e'."""
    words = []
    for w in s.split():
        if w.isupper() or w.islower():
            w = re.sub(r"[^\W\d_]+", lambda m: m.group(0).capitalize(), w.lower())
        words.append(w)
    return " ".join(words)


def clean_phone(s: str) -> str | None:
    s = re.sub(r"[^\d+]", "", s or "")
    return s if len(re.sub(r"\D", "", s)) >= 6 else None


def parse_birth(s: str | None) -> str | None:
    """'1985-03-12' -> stessa data; '0000-00-00', vuote o non plausibili -> None."""
    try:
        d = date.fromisoformat((s or "").strip())
    except ValueError:
        return None
    return d.isoformat() if 1900 <= d.year and d <= date.today() - timedelta(days=365 * 5) else None


def import_clients(db: Database, text: str, apply: bool) -> dict:
    """Importa il CSV. Con apply=False non scrive nulla e restituisce solo il riepilogo."""
    reader = csv.DictReader(io.StringIO(text))
    missing = REQUIRED - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Il file non sembra l'export clienti di Vaniglia: mancano le colonne "
                         f"{', '.join(sorted(missing))}")

    stats = {"righe": 0, "nuove": 0, "aggiornate": 0, "invariate": 0,
             "collegate": 0, "scartate_senza_nome": 0}
    db.conn.execute("BEGIN IMMEDIATE")
    try:
        for row in reader:
            stats["righe"] += 1
            name = nice_name(f"{row['Nome'] or ''} {row['Cognome'] or ''}")
            if not name:
                stats["scartate_senza_nome"] += 1
                continue
            code = (row["Cod. Cliente"] or "").strip() or None
            phone = clean_phone(row["Tel. Cellulare"])
            stats[_upsert(db, code, name, phone, parse_birth(row.get("Data Nascita")))] += 1
    except BaseException:
        db.conn.execute("ROLLBACK")
        raise
    db.conn.execute("COMMIT" if apply else "ROLLBACK")
    stats["applicato"] = apply
    return stats


def _upsert(db: Database, code: str | None, name: str, phone: str | None, birth: str | None) -> str:
    """I campi vuoti nel file non cancellano mai quelli scritti nell'app."""
    c = db.conn
    now = "strftime('%Y-%m-%d %H:%M:%f', 'now')"
    if code:
        cur = c.execute("SELECT id, name, phone, birth_date FROM clients WHERE external_id = ?",
                        (code,)).fetchone()
        if cur:
            new = (name, phone or cur["phone"], birth or cur["birth_date"])
            if (cur["name"], cur["phone"], cur["birth_date"]) == new:
                return "invariate"
            c.execute(f"UPDATE clients SET name = ?, phone = ?, birth_date = ?, updated_at = {now} "
                      "WHERE id = ?", (*new, cur["id"]))
            return "aggiornate"
    # cliente senza codice con stesso nome e cellulare compatibile: si collega invece di duplicarla
    matches = c.execute(
        "SELECT id FROM clients WHERE external_id IS NULL AND name = ? COLLATE NOCASE "
        "AND (phone IS NULL OR ? IS NULL OR phone = ?)", (name, phone, phone)).fetchall()
    if len(matches) == 1:
        if not code:
            return "invariate"
        c.execute(f"UPDATE clients SET external_id = ?, name = ?, phone = COALESCE(?, phone), "
                  f"birth_date = COALESCE(?, birth_date), updated_at = {now} WHERE id = ?",
                  (code, name, phone, birth, matches[0]["id"]))
        return "collegate"
    c.execute("INSERT INTO clients(external_id, name, phone, birth_date, origin) "
              "VALUES (?, ?, ?, ?, 'import')", (code, name, phone, birth))
    return "nuove"
