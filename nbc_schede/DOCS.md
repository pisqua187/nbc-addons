# NBC Schede Tecniche

Si apre dalla barra laterale di Home Assistant ("Schede Tecniche") o dalla card della dashboard NBC Studio.
Serve il login di Home Assistant: senza, le schede non si vedono.

Database: `/data/salone.db` dentro l'add-on. E' compreso nei backup di Home Assistant.

## Modulo privacy e consenso informato

Dalla scheda cliente: **📝 Fai firmare il modulo**. L'iPad passa in modalità cliente (niente menu):
la cliente compila dati e stato di salute, legge consenso informato e informativa, firma con il dito.
Il check up tecnico lo compila l'operatrice nella scheda Fotoepilazione.

Ogni modulo firmato diventa un PDF:
- salvato dentro l'add-on (`/data/consensi`, compreso nei backup di Home Assistant);
- copiato nella cartella indicata nell'opzione `archivio_consensi` (il Synology).

### Collegare il Synology
1. Sul Synology: un utente dedicato (es. `homeassistant`) con lettura/scrittura sulla cartella condivisa
   "Documenti Importanti" e SMB attivo.
2. Home Assistant → Impostazioni → Sistema → Archiviazione → **Aggiungi archiviazione di rete**:
   nome `documenti_importanti`, utilizzo **Condivisione**, protocollo Samba/Windows (CIFS),
   server = IP del Synology, condivisione remota `Documenti Importanti`, utente e password del punto 1.
3. Opzione dell'add-on `archivio_consensi`: `/share/documenti_importanti/Clienti/Consensi` (predefinita).
4. Riavvia l'add-on. In Impostazioni dell'app, "Archivio moduli firmati" deve dire **raggiungibile**.

Se il Synology è spento, i moduli restano salvati nell'add-on e vengono copiati appena torna raggiungibile
(all'avvio, alla firma di un nuovo modulo o con "Riprova la copia").

I testi (consenso, informativa) sono in `app/texts.py`: **bozza da far validare dal consulente privacy**.
