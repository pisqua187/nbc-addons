"""Testi del modulo privacy e consenso informato.

UNICO punto da modificare quando il consulente privacy rivede i testi: l'app sull'iPad e il PDF
firmato usano entrambi queste costanti. Ogni modifica sostanziale deve cambiare TEXT_VERSION,
cosi' ogni PDF firmato riporta la versione del testo che la cliente ha letto.
"""

TEXT_VERSION = "2026-11-18 (bozza da validare)"

TITOLARE = {
    "nome": "New Body Center sas di Pasqualon Eleonora & C.",
    "indirizzo": "via Lazzaretto 16b, 35010 Carmignano di Brenta (PD)",
    "piva": "04769250285",
    "pec": "nbcestetica@pec.it",
    "tel": "049 5958035",
}
INTESTAZIONE = "NEW BODY CENTER"
LUOGO_DEFAULT = "Carmignano di Brenta"
CONSERVAZIONE_ANNI = 10

# Stato di salute: le voci del modulo cartaceo, nello stesso ordine.
HEALTH_ITEMS = [
    "Gravidanza", "Allattamento", "Pace Maker e dispositivi elettronici", "Epilessia",
    "Allergie cutanee", "Malattie della pelle", "Diabete", "Problemi circolatori",
    "Patologie ormonali", "Ovaio policistico", "Interventi ginecologici",
    "Spirale/Diaframma/Protesi metalliche", "Anticoagulanti, Cortisone, Antibiotici",
    "Chemio Radio Terapie",
]

DICHIARAZIONE_SCHEDA = (
    "Dichiaro che le informazioni sul mio stato di salute riportate in questa scheda sono veritiere "
    "e complete, e mi impegno a comunicare ogni variazione prima dei trattamenti successivi."
)

CONSENSO_TITOLO = "CONSENSO INFORMATO AL TRATTAMENTO EPILAZIONE LASER FIBRASI"
CONSENSO_INTRO = [
    "Di seguito Le verranno indicati i benefici in relazione a quanto Le verrà praticato, i possibili rischi "
    "e le eventuali alternative, così da consentirLe una volontaria e conseguente consapevole decisione in merito.",
    "È importante che Lei ritenga le spiegazioni fornite esaurienti e chiare ed in particolare che abbia bene "
    "presente quanto Le viene proposto.",
    "Per questo Le viene fornita anche per iscritto un'informazione. Se lo ritiene necessario non abbia alcun "
    "timore nel richiedere tutte le ulteriori informazioni che crede utili al fine di risolvere eventuali dubbi "
    "o chiarire alcuni aspetti di quanto esposto che non ha pienamente compreso.",
    "La invitiamo pertanto, prima di prestare il Suo consenso firmando il presente modulo, a chiarire con chi "
    "glielo sottopone ogni aspetto che non Le appare sufficientemente comprensibile.",
]
CONSENSO_PUNTI = [
    "L'energia emessa dal laser sui tessuti è assorbita maggiormente dai pigmenti del pelo. Questo causa un "
    "significativo aumento della temperatura del bulbo del pelo, mentre il resto della pelle assorbe meno energia "
    "e non si scalda. Quando le cellule nel follicolo che producono il pelo raggiungono una temperatura "
    "sufficiente, si danneggiano a tal punto da non rigenerarsi più e non produrre più il pelo.",
    "I peli hanno un ciclo di vita costante e ripetitivo. Solo quelli in fase di crescita (Anagen) saranno "
    "danneggiati dall'energia irradiata. Ad ogni seduta di trattamento solo una percentuale (60/90%) dei peli in "
    "fase Anagen verrà eliminata. Per questo motivo occorrono sedute ripetute per eliminare i peli dalla medesima "
    "zona. Il numero delle sedute necessarie varia da soggetto a soggetto e secondo la zona del corpo.",
    "Allo stesso modo il livello di sensazione del dolore varia a seconda della persona e della zona. È normale "
    "ad esempio che la parte superiore della schiena sia meno sensibile della zona inguinale.",
    "È normale in caso di peli biondi, rossi o molto sottili attendersi una risposta più lenta al trattamento "
    "rispetto ai peli scuri e grossi.",
    "In alcuni casi, dopo il trattamento, si può presentare un temporaneo arrossamento. Di solito scompare entro "
    "un periodo che può variare da 15 min a poche ore. Più raramente l'arrossamento dura alcuni giorni (è simile "
    "ad una leggera scottatura solare).",
    "Controindicazioni al trattamento: diabete, epilessia, pace maker e dispositivi elettronici, alcune malattie "
    "cutanee (tutte le dermatosi fotosensibili, nevi nell'area da trattare, tatuaggi, eczemi diffusi) la "
    "gravidanza e l'allattamento, la presenza di dispositivi anticoncezionali (spirale e diaframma). Deve essere "
    "evitata l'esposizione al sole e lampade abbronzanti nei 3 giorni precedenti e 5 giorni successivi al "
    "trattamento. Da evitare sono tutte le manovre traumatizzanti (sfregamento della zona trattata, utilizzo di "
    "detergenti inadeguati) che aumentano il rischio di effetti collaterali.",
    "Si deve avere un buono stato di salute e soprattutto non essere sotto terapie quali chemio o radio. In caso "
    "di dubbi chiedere al proprio terapista.",
    "Rispettare le date prestabilite dalla direzione tecnica per trattamenti e controlli.",
    "Comunicare sempre le variazioni sullo stato di salute e l'assunzione di farmaci, soprattutto quelli "
    "fotosensibilizzanti, cortisonici e antibiotici.",
]
CONSENSO_DICHIARAZIONI = [
    "Ho ricevuto e compreso le informazioni datemi sia verbalmente che per iscritto: mi sottopongo al "
    "trattamento con laser di mia spontanea volontà e responsabilità e dichiaro di essere in buono stato di salute.",
    "Mi viene confermato che sarà presente durante l'esecuzione della procedura personale qualificato a far "
    "fronte a qualsiasi necessità e che verranno utilizzate le apparecchiature tecniche conformi alle necessità "
    "specifiche.",
]
MAGGIORENNE = "Certifico di essere maggiorenne."
MINORENNE = ("La cliente è minorenne: il genitore o chi esercita la responsabilità genitoriale, dopo aver "
             "ricevuto le stesse informazioni, firma il presente modulo unitamente a lei.")

INFORMATIVA_TITOLO = "INFORMATIVA SUL TRATTAMENTO DEI DATI PERSONALI (art. 13 Reg. UE 2016/679 - GDPR)"
INFORMATIVA = [
    ("Titolare del trattamento",
     f"{TITOLARE['nome']}, {TITOLARE['indirizzo']}, P.IVA {TITOLARE['piva']}. "
     f"Contatti: PEC {TITOLARE['pec']}, tel. {TITOLARE['tel']}."),
    ("Dati trattati",
     "Dati anagrafici e di contatto; dati relativi alla salute indicati nella scheda (stato di salute, farmaci, "
     "controindicazioni); dati tecnici dei trattamenti eseguiti (zone, parametri, date, operatrice); la firma."),
    ("Finalità e base giuridica",
     "a) eseguire i trattamenti estetici richiesti e gestire la scheda tecnica (art. 6.1.b GDPR: esecuzione del "
     "contratto); b) valutare l'idoneità al trattamento e prevenire rischi per la salute, trattando dati relativi "
     "alla salute (art. 9.2.a GDPR: consenso esplicito); c) adempiere a obblighi di legge, ad esempio fiscali "
     "(art. 6.1.c GDPR)."),
    ("Natura del conferimento",
     "Il conferimento dei dati e il consenso al trattamento dei dati relativi alla salute sono necessari: senza "
     "di essi non è possibile eseguire il trattamento in sicurezza."),
    ("Modalità e luogo",
     "I dati sono trattati con strumenti elettronici e cartacei, da personale autorizzato e istruito, e sono "
     "conservati su sistemi situati presso la sede del Titolare, protetti da accesso con credenziali e copie di "
     "sicurezza. Non sono diffusi né trasferiti fuori dall'Unione Europea."),
    ("Destinatari",
     "I dati possono essere comunicati solo a soggetti che forniscono al Titolare servizi tecnici o "
     "amministrativi (es. assistenza informatica, consulenza fiscale), nominati responsabili del trattamento, "
     "e alle autorità quando previsto dalla legge."),
    ("Conservazione",
     f"La scheda e il presente modulo sono conservati per {CONSERVAZIONE_ANNI} anni dall'ultimo trattamento "
     "eseguito, poi cancellati."),
    ("Diritti dell'interessato",
     "Può chiedere in ogni momento l'accesso ai dati, la rettifica, la cancellazione, la limitazione, "
     "l'opposizione e la portabilità (artt. 15-22 GDPR), e revocare il consenso senza pregiudicare la liceità "
     "del trattamento svolto prima della revoca, scrivendo ai contatti del Titolare. Ha diritto di proporre "
     "reclamo al Garante per la protezione dei dati personali (www.garanteprivacy.it)."),
]
CONSENSO_PRIVACY = (
    "Letta l'informativa, ai sensi degli artt. 6 e 9 del Regolamento UE 2016/679 (GDPR) e del D.lgs. 196/2003 "
    "come modificato dal D.lgs. 101/2018, presto il mio consenso esplicito al trattamento dei miei dati personali "
    "e relativi alla salute, esclusivamente con le modalità e per le finalità strettamente connesse alla gestione "
    "del rapporto e all'esecuzione dei trattamenti."
)

# Check up: compilato dall'operatrice nella scheda, non dalla cliente.
CHECKUP = [
    ("fototipo", "Fototipo", ["1", "2", "3", "4", "5", "6"], False),
    ("colore", "Colore del pelo", ["scuro", "castano", "biondo", "rosso"], False),
    ("spessore", "Spessore del pelo", ["sottile", "medio", "grosso"], False),
    ("densita", "Densità pilifera", ["rado", "normale", "folto"], False),
    ("abitudini", "Abitudini", ["ceretta", "rasoio", "crema depilatoria"], True),
    ("frequenza", "Frequenza", ["regolare", "occasionale"], False),
    ("reazioni", "Reazioni cutanee", ["follicolite", "peli incarniti", "arrossamento"], True),
    ("particolarita", "Particolarità", ["irsutismo", "ipertricosi"], True),
]


def as_dict() -> dict:
    """Tutti i testi per l'app (cosi' iPad e PDF mostrano esattamente le stesse parole)."""
    return {
        "version": TEXT_VERSION, "titolare": TITOLARE, "intestazione": INTESTAZIONE,
        "luogo_default": LUOGO_DEFAULT, "health_items": HEALTH_ITEMS,
        "dichiarazione_scheda": DICHIARAZIONE_SCHEDA,
        "consenso_titolo": CONSENSO_TITOLO, "consenso_intro": CONSENSO_INTRO,
        "consenso_punti": CONSENSO_PUNTI, "consenso_dichiarazioni": CONSENSO_DICHIARAZIONI,
        "maggiorenne": MAGGIORENNE, "minorenne": MINORENNE,
        "informativa_titolo": INFORMATIVA_TITOLO,
        "informativa": [{"titolo": t, "testo": x} for t, x in INFORMATIVA],
        "consenso_privacy": CONSENSO_PRIVACY,
        "checkup": [{"key": k, "label": l, "options": o, "multi": m} for k, l, o, m in CHECKUP],
    }
