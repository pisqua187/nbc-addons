"""Stampa diretta sulla stampante di rete con il protocollo IPP (porta 631), senza driver.

La quasi totalita' delle stampanti di rete recenti (AirPrint / IPP Everywhere / Mopria) accetta
un PDF via IPP: l'add-on genera il PDF e lo invia, cosi' la stampa non dipende dall'iPad
(AirPrint non attraversa reti diverse) ne' dal browser dentro Home Assistant.
"""

import struct
import urllib.error
import urllib.request
from itertools import count

# tag IPP (RFC 8010)
OP_ATTRS, JOB_ATTRS, END = 0x01, 0x02, 0x03
INTEGER, BOOLEAN, ENUM = 0x21, 0x22, 0x23
TEXT, NAME, KEYWORD, URI, CHARSET, LANG, MIME = 0x41, 0x42, 0x44, 0x45, 0x47, 0x48, 0x49
PRINT_JOB, GET_PRINTER_ATTRIBUTES = 0x0002, 0x000B
PRINTER_STATES = {3: "pronta", 4: "sta stampando", 5: "ferma"}
_ids = count(1)
# la stampante e' in rete locale: mai passare da un proxy, anche se l'ambiente ne definisce uno
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class PrinterError(Exception):
    pass


def _attr(tag: int, name: str, value) -> bytes:
    if tag in (INTEGER, ENUM):
        raw = struct.pack(">i", value)
    elif tag == BOOLEAN:
        raw = b"\x01" if value else b"\x00"
    else:
        raw = str(value).encode("utf-8")
    n = name.encode()
    return struct.pack(">BH", tag, len(n)) + n + struct.pack(">H", len(raw)) + raw


def _request(op: int, printer_uri: str, op_attrs: list[bytes], job_attrs: list[bytes] = ()) -> bytes:
    body = struct.pack(">BBHI", 2, 0, op, next(_ids))
    body += bytes([OP_ATTRS]) + _attr(CHARSET, "attributes-charset", "utf-8")
    body += _attr(LANG, "attributes-natural-language", "it")
    body += _attr(URI, "printer-uri", printer_uri)
    body += b"".join(op_attrs)
    if job_attrs:
        body += bytes([JOB_ATTRS]) + b"".join(job_attrs)
    return body + bytes([END])


def _parse(resp: bytes) -> tuple[int, dict]:
    if len(resp) < 8:
        raise PrinterError("Risposta della stampante non valida")
    status = struct.unpack(">H", resp[2:4])[0]
    attrs: dict[str, list] = {}
    i, last = 8, None
    while i < len(resp):
        tag = resp[i]; i += 1
        if tag == END:
            break
        if tag < 0x10:  # inizio di un nuovo gruppo
            continue
        nlen = struct.unpack(">H", resp[i:i + 2])[0]; i += 2
        name = resp[i:i + nlen].decode("utf-8", "replace"); i += nlen
        vlen = struct.unpack(">H", resp[i:i + 2])[0]; i += 2
        raw = resp[i:i + vlen]; i += vlen
        if tag in (INTEGER, ENUM) and vlen == 4:
            val = struct.unpack(">i", raw)[0]
        elif tag == BOOLEAN:
            val = raw == b"\x01"
        elif tag in (0x35, 0x36):  # text/name con lingua: salta la lingua
            ll = struct.unpack(">H", raw[:2])[0]
            tl = struct.unpack(">H", raw[2 + ll:4 + ll])[0]
            val = raw[4 + ll:4 + ll + tl].decode("utf-8", "replace")
        else:
            val = raw.decode("utf-8", "replace")
        if nlen:
            last = name
            attrs.setdefault(name, []).append(val)
        elif last:  # valore aggiuntivo dello stesso attributo
            attrs[last].append(val)
    return status, attrs


def _candidates(address: str) -> list[str]:
    """Da '192.168.40.23' prova i percorsi IPP piu' comuni; un indirizzo completo ipp:// si usa cosi' com'e'."""
    a = address.strip()
    if a.startswith(("ipp://", "http://")):
        return [a]
    host = a if ":" in a else a + ":631"
    return [f"ipp://{host}/ipp/print", f"ipp://{host}/ipp", f"ipp://{host}/"]


def _post(printer_uri: str, body: bytes, timeout: float) -> tuple[int, dict]:
    http = "http://" + printer_uri.split("://", 1)[1]
    req = urllib.request.Request(http, data=body, method="POST",
                                 headers={"Content-Type": "application/ipp"})
    try:
        with _opener.open(req, timeout=timeout) as r:
            return _parse(r.read())
    except urllib.error.HTTPError as e:
        raise PrinterError(f"La stampante ha risposto con errore HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise PrinterError(f"Stampante non raggiungibile ({reason})") from e


def printer_info(address: str, timeout: float = 6) -> dict:
    if not address:
        raise PrinterError("Indirizzo della stampante non impostato")
    wanted = ["printer-make-and-model", "printer-state", "printer-state-message",
              "document-format-supported", "printer-name"]
    last_err: Exception | None = None
    for uri in _candidates(address):
        req_attrs = [_attr(NAME, "requesting-user-name", "NBC Schede")]
        req_attrs.append(_attr(KEYWORD, "requested-attributes", wanted[0]))
        req_attrs += [_attr(KEYWORD, "", w) for w in wanted[1:]]
        try:
            status, attrs = _post(uri, _request(GET_PRINTER_ATTRIBUTES, uri, req_attrs), timeout)
        except PrinterError as e:
            last_err = e
            if "non raggiungibile" in str(e):
                raise  # host irraggiungibile: inutile provare altri percorsi
            continue
        if status < 0x0100 and attrs.get("printer-state"):
            formats = attrs.get("document-format-supported", [])
            return {
                "uri": uri,
                "model": (attrs.get("printer-make-and-model") or attrs.get("printer-name") or ["?"])[0],
                "state": PRINTER_STATES.get(attrs["printer-state"][0], str(attrs["printer-state"][0])),
                "message": (attrs.get("printer-state-message") or [""])[0],
                "pdf": "application/pdf" in formats,
                "formats": formats,
            }
        last_err = PrinterError(f"La stampante ha rifiutato la richiesta (codice IPP 0x{status:04x})")
    raise last_err or PrinterError("Stampante non trovata")


def print_pdf(address: str, pdf: bytes, job_name: str, copies: int = 1) -> dict:
    info = printer_info(address)
    if not info["pdf"]:
        raise PrinterError(f"La stampante {info['model']} non accetta PDF via rete "
                           f"(formati: {', '.join(info['formats']) or 'nessuno'})")
    op = [_attr(NAME, "requesting-user-name", "NBC Schede"), _attr(NAME, "job-name", job_name[:120]),
          _attr(MIME, "document-format", "application/pdf")]
    job = [_attr(INTEGER, "copies", max(1, min(int(copies), 10)))] if copies != 1 else []
    status, attrs = _post(info["uri"], _request(PRINT_JOB, info["uri"], op, job) + pdf, timeout=60)
    if status >= 0x0100:
        msg = (attrs.get("status-message") or [""])[0]
        raise PrinterError(f"Stampa rifiutata dalla stampante (codice IPP 0x{status:04x}) {msg}".strip())
    return {"job_id": (attrs.get("job-id") or [None])[0], "printer": info["model"]}
