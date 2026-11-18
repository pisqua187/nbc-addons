"""Avvio dell'add-on: legge le opzioni, al primo avvio importa il database, poi parte il server."""

import json
import os
import shutil
from pathlib import Path

import uvicorn

DB = Path(os.environ["DB_PATH"])
IMPORT_DIR = Path("/share/nbc_schede")  # cartella "share" di Home Assistant, raggiungibile da Samba

opts = {}
try:
    opts = json.loads(Path("/data/options.json").read_text())
except (OSError, ValueError):
    pass
os.environ["API_KEY"] = opts.get("api_key") or ""
# cartella del Synology (archivio di rete collegato a Home Assistant) dove copiare i moduli firmati
os.environ["ARCHIVE_DIR"] = (opts.get("archivio_consensi") or "").strip()
os.environ.setdefault("CONSENTS_DIR", "/data/consensi")
# stampante di rete (IPP): indirizzo IP oppure ipp://indirizzo/percorso
os.environ["PRINTER"] = (opts.get("stampante") or "").strip()
# indirizzo della dashboard per il tasto "Dashboard", es. /dashboard-nbc/0
os.environ["DASHBOARD_URL"] = (opts.get("dashboard_url") or "/").strip() or "/"

# Primo avvio: se c'e' un database copiato dal PC in /share/nbc_schede, lo usa.
# Non sovrascrive MAI un database gia' presente.
if not DB.exists():
    for name in ("salone.db", "demo.db"):
        src = IMPORT_DIR / name
        if src.exists():
            DB.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, DB)
            for ext in ("-wal", "-shm"):
                if Path(str(src) + ext).exists():
                    shutil.copy2(str(src) + ext, str(DB) + ext)
            print(f"Database importato da {src}", flush=True)
            break
    else:
        print("Nessun database da importare: parto con un database vuoto", flush=True)

uvicorn.run("app.main:create_app", factory=True, host="0.0.0.0", port=8077,
            proxy_headers=True, forwarded_allow_ips="*")
