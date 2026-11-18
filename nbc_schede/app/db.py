"""Database SQLite: clienti, storico smalti, trattamenti di fotoepilazione."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id           INTEGER PRIMARY KEY,
    external_id  TEXT UNIQUE,              -- Cod. Cliente Vaniglia (NULL se creata dall'app)
    name         TEXT NOT NULL,
    phone        TEXT,
    birth_date   TEXT,                     -- YYYY-MM-DD
    notes        TEXT,
    origin       TEXT NOT NULL DEFAULT 'app',  -- 'app' (creata sull'iPad) o 'import' (export Vaniglia)
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);

CREATE TABLE IF NOT EXISTS polish_records (
    id          INTEGER PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES clients(id),
    day         TEXT NOT NULL,             -- YYYY-MM-DD
    polish      TEXT NOT NULL,             -- scritto dall'operatrice, es. "OPI N25 Big Apple Red"
    notes       TEXT,
    operator    TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_records_client ON polish_records(client_id, day DESC);
CREATE INDEX IF NOT EXISTS idx_records_polish ON polish_records(polish COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS operators (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active  INTEGER NOT NULL DEFAULT 1
);

-- Scheda fotoepilazione: una riga per trattamento
CREATE TABLE IF NOT EXISTS laser_treatments (
    id          INTEGER PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES clients(id),
    day         TEXT NOT NULL,             -- data del trattamento, YYYY-MM-DD
    zone        TEXT NOT NULL,             -- zona trattata
    fluence     TEXT,                      -- Freq. J/cm2 (testo: accetta "12,5")
    hz          TEXT,                      -- Freq. Hz
    operator    TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_laser_client ON laser_treatments(client_id, day);

-- Modulo privacy + consenso informato firmato sull'iPad. Non si modifica: se cambia, se ne firma uno nuovo.
CREATE TABLE IF NOT EXISTS consents (
    id                INTEGER PRIMARY KEY,
    client_id         INTEGER NOT NULL REFERENCES clients(id),
    signed_at         TEXT NOT NULL,          -- ora locale ISO, es. 2026-11-18T10:32:05+01:00
    text_version      TEXT NOT NULL,          -- versione dei testi letti (app/texts.py)
    data              TEXT NOT NULL,          -- JSON: anagrafica, stato di salute, conferme
    signature         BLOB NOT NULL,          -- PNG della firma
    signature_tutore  BLOB,                   -- PNG firma genitore/tutore (solo minorenni)
    fingerprint       TEXT NOT NULL,          -- SHA-256 di dati + firme, stampato sul PDF
    device            TEXT,                   -- browser/dispositivo usato per firmare
    pdf_file          TEXT NOT NULL,          -- nome del PDF nella cartella consensi
    pdf_sha256        TEXT,
    copied_at         TEXT,                   -- quando e' stato copiato sul Synology (NULL = in sospeso)
    copy_error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_consents_client ON consents(client_id, id DESC);

-- Consenso gia' firmato su carta (prima dell'app): solo un'annotazione, il foglio resta in archivio cartaceo.
CREATE TABLE IF NOT EXISTS paper_consents (
    id          INTEGER PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES clients(id),
    signed_on   TEXT NOT NULL,                -- data della firma sul foglio, YYYY-MM-DD
    note        TEXT,                         -- es. "raccoglitore 2025"
    operator    TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_paper_client ON paper_consents(client_id, signed_on DESC);

-- Check up tecnico della cliente (fototipo, pelo...), compilato dall'operatrice.
CREATE TABLE IF NOT EXISTS checkups (
    client_id   INTEGER PRIMARY KEY REFERENCES clients(id),
    data        TEXT NOT NULL,                -- JSON
    operator    TEXT,
    updated_at  TEXT NOT NULL
);

"""


DEFAULT_OPERATORS = ["Alexa", "Anna", "Camilla", "Eleonora"]


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Una connessione PER THREAD: le richieste arrivano in parallelo (FastAPI le esegue su piu'
        # thread) e una connessione sqlite3 condivisa fra thread si rompe ("bad parameter or other
        # API misuse", errori 500 e falsi "Cliente non trovata"). In WAL le letture vanno in parallelo,
        # le scritture si mettono in coda da sole (timeout).
        self._local = threading.local()
        if path == ":memory:":  # test: database in memoria condiviso fra le connessioni
            self._target, self._uri = f"file:mem{id(self)}?mode=memory&cache=shared", True
            self._anchor = self._connect()  # tiene in vita il database in memoria
        else:
            self._target, self._uri = path, False
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        # 1.6.0: la potenza si inserisce, i J/cm2 (fluence) si calcolano = potenza / 2
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(laser_treatments)")}
        if "power" not in cols:
            self.conn.execute("ALTER TABLE laser_treatments ADD COLUMN power TEXT")
        # Operatrici di partenza. INSERT OR IGNORE: una tolta dalle Impostazioni resta tolta.
        self.conn.executemany("INSERT OR IGNORE INTO operators(name) VALUES (?)",
                              [(n,) for n in DEFAULT_OPERATORS])

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._target, uri=self._uri, isolation_level=None, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = self._local.conn = self._connect()
        return c

    @contextmanager
    def tx(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    def query(self, sql: str, params=()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params=()) -> dict | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None
