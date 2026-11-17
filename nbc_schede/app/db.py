"""Database SQLite: clienti, storico smalti, trattamenti di fotoepilazione."""

import sqlite3
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

"""


DEFAULT_OPERATORS = ["Alexa", "Anna", "Camilla", "Eleonora"]


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Una connessione condivisa: SQLite + un solo processo, il lock lo gestisce lui.
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        # Operatrici di partenza. INSERT OR IGNORE: una tolta dalle Impostazioni resta tolta.
        self.conn.executemany("INSERT OR IGNORE INTO operators(name) VALUES (?)",
                              [(n,) for n in DEFAULT_OPERATORS])

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
