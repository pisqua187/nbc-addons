# NBC Studio add-ons per Home Assistant

- **nbc_schede** — storico smalti e schede di fotoepilazione delle clienti.

In Home Assistant: Impostazioni → Componenti aggiuntivi → Store → ⋮ → Repository → incolla
`https://github.com/pisqua187/nbc-addons`.

Questo repository contiene solo il codice. I dati delle clienti restano nel database dentro Home Assistant
e non vanno mai caricati qui (vedi `.gitignore`).

Per pubblicare una modifica: cambiare il codice e alzare `version` in `nbc_schede/config.yaml`;
in Home Assistant comparira' "Aggiorna".
