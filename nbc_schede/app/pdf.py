"""PDF del modulo firmato: scheda cliente, consenso informato, informativa privacy (A4 verticale)."""

import io
from datetime import date, datetime

from fpdf import FPDF

from . import texts

ACCENT = (45, 74, 122)
INK = (31, 42, 58)
MUTED = (107, 118, 134)


def _t(s) -> str:
    """I font standard del PDF usano latin-1: le lettere accentate italiane ci sono, i simboli no."""
    s = str(s or "")
    for a, b in {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                 "…": "...", "²": "2"}.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def _day(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


class Modulo(FPDF):
    footer_text = ""

    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*ACCENT)
        self.cell(0, 8, _t(texts.INTESTAZIONE), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        t = texts.TITOLARE
        self.cell(0, 4, _t(f"{t['nome']} - {t['indirizzo']} - P.IVA {t['piva']}"), align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self.set_text_color(*INK)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 3, _t(self.footer_text + f"  -  Pagina {self.page_no()}/{{nb}}"), align="C")
        self.set_text_color(*INK)

    # --- mattoncini --------------------------------------------------------------
    def section(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ACCENT)
        y = self.get_y() + 3
        w = self.get_string_width(_t(title)) + 8
        x0 = (self.w - w) / 2
        self.set_draw_color(*ACCENT)
        self.line(self.l_margin, y, x0, y)
        self.line(x0 + w, y, self.w - self.r_margin, y)
        self.cell(0, 6, _t(title), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)
        self.set_draw_color(0, 0, 0)
        self.ln(1)

    def field(self, label: str, value: str, w: float):
        x, y = self.get_x(), self.get_y()
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(w, 4, _t(label))
        self.set_xy(x, y + 4)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*INK)
        self.cell(w - 4, 6, _t(value), border="B")
        self.set_xy(x + w, y)

    def checkbox(self, checked: bool, label: str, size: float = 3.6):
        x, y = self.get_x(), self.get_y()
        self.rect(x, y + 0.8, size, size)
        if checked:
            self.set_line_width(0.5)
            self.line(x + 0.6, y + 1.4, x + size - 0.6, y + 0.2 + size)
            self.line(x + size - 0.6, y + 1.4, x + 0.6, y + 0.2 + size)
            self.set_line_width(0.2)
        self.set_x(x + size + 2.5)
        self.set_font("Helvetica", "B" if checked else "", 10)
        self.multi_cell(0, 5.2, _t(label), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)

    def para(self, text: str, size: float = 9.5, bold: bool = False, h: float = 4.6):
        self.set_font("Helvetica", "B" if bold else "", size)
        self.multi_cell(0, h, _t(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1.2)

    def bullet(self, text: str, size: float = 9.2):
        self.set_font("Helvetica", "", size)
        x = self.get_x()
        self.cell(5, 4.4, _t("-"))
        self.set_x(x + 5)
        self.multi_cell(0, 4.4, _t(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.8)

    def signature(self, png: bytes, label: str, place_date: str):
        if self.get_y() > self.h - 60:
            self.add_page()
        self.ln(3)
        y = self.get_y()
        half = (self.w - self.l_margin - self.r_margin) / 2
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.cell(half, 4, _t("Luogo e data"))
        self.cell(half, 4, _t(label), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)
        self.set_font("Helvetica", "", 11)
        self.set_xy(self.l_margin, y + 14)
        self.cell(half - 8, 6, _t(place_date), border="B")
        self.image(io.BytesIO(png), x=self.l_margin + half, y=y + 4, h=18, keep_aspect_ratio=True,
                   w=half - 4)
        self.line(self.l_margin + half, y + 20, self.w - self.r_margin, y + 20)
        self.set_xy(self.l_margin, y + 24)


def build_pdf(data: dict, sig: bytes, sig_tutore: bytes | None, signed: datetime, consent_id: int,
              fingerprint: str) -> bytes:
    pdf = Modulo(format="A4")
    pdf.set_margins(16, 12, 16)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_title(_t(f"Modulo privacy e consenso - {data['nome']} {data['cognome']}"))
    pdf.set_author(_t(texts.TITOLARE["nome"]))
    pdf.footer_text = (f"Modulo n. {consent_id} firmato elettronicamente su tablet il "
                       f"{signed.strftime('%d/%m/%Y alle %H:%M')} - testi versione {texts.TEXT_VERSION} - "
                       f"impronta SHA-256 {fingerprint}")
    place_date = f"{data['luogo']}, {signed.strftime('%d/%m/%Y')}"
    full_w = pdf.w - pdf.l_margin - pdf.r_margin

    # ---------------- pagina 1: scheda cliente ----------------
    pdf.add_page()
    pdf.section("SCHEDA CLIENTE")
    pdf.field("Nome", data["nome"], full_w / 2); pdf.field("Cognome", data["cognome"], full_w / 2); pdf.ln(12)
    sesso = {"F": "F", "M": "M"}.get(data.get("sesso") or "", "")
    pdf.field("Data di nascita", _day(data["birth_date"]), full_w / 2); pdf.field("Sesso", sesso, full_w / 2); pdf.ln(12)
    pdf.field("Indirizzo", data.get("indirizzo") or "", full_w); pdf.ln(12)
    pdf.field("Tel", data.get("tel") or "", full_w / 2); pdf.field("Mail", data.get("email") or "", full_w / 2); pdf.ln(14)

    pdf.section("STATO DI SALUTE")
    health = set(data["health"])
    for item in texts.HEALTH_ITEMS:
        pdf.checkbox(item in health, item)
    pdf.checkbox(bool(data.get("altro")), "Altro" + (f": {data['altro']}" if data.get("altro") else ""))
    pdf.checkbox(bool(data.get("nessuna")), "Nessuna delle condizioni elencate")
    pdf.ln(2)
    pdf.checkbox(True, texts.DICHIARAZIONE_SCHEDA)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4, _t("Il check up tecnico (fototipo, caratteristiche del pelo) è compilato dall'operatrice "
                            "nella scheda trattamenti."), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)

    # ---------------- pagina 2: consenso informato ----------------
    pdf.add_page()
    pdf.section(texts.CONSENSO_TITOLO)
    for p in texts.CONSENSO_INTRO:
        pdf.para(p)
    for p in texts.CONSENSO_PUNTI:
        pdf.bullet(p)
    pdf.ln(1)
    for p in texts.CONSENSO_DICHIARAZIONI:
        pdf.checkbox(True, p)
    if data.get("minorenne"):
        pdf.checkbox(True, texts.MINORENNE + f" Genitore/tutore: {data.get('tutore')}.")
    else:
        pdf.checkbox(True, texts.MAGGIORENNE)

    # ---------------- pagina 3: informativa e consenso privacy + firma ----------------
    pdf.add_page()
    pdf.section("INFORMATIVA PRIVACY")
    pdf.para(texts.INFORMATIVA_TITOLO, size=9.5, bold=True)
    for title, text in texts.INFORMATIVA:
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(0, 4.4, _t(title), new_x="LMARGIN", new_y="NEXT")
        pdf.para(text, size=9, h=4.3)
    pdf.section("AUTORIZZO")
    pdf.checkbox(True, texts.CONSENSO_PRIVACY)
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.multi_cell(0, 4, _t("La firma sottostante, apposta una sola volta al termine della lettura, vale per tutte "
                            "le dichiarazioni contrassegnate in questo modulo (scheda cliente, consenso informato, "
                            "consenso al trattamento dei dati)."), new_x="LMARGIN", new_y="NEXT")
    pdf.signature(sig, "Firma leggibile della cliente", place_date)
    if sig_tutore:
        pdf.signature(sig_tutore, f"Firma del genitore/tutore ({data.get('tutore')})", place_date)
    return bytes(pdf.output())
