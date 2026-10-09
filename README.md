# ParMA — guida al progetto

Sito del gruppo di ricerca ParMA, Inria Saclay, CNRS e Université Paris-Saclay.

**Sito online:** [parma-inria.github.io](https://parma-inria.github.io/) · **Progetto:** [GitHub](https://github.com/parma-inria/parma-inria.github.io)

## Da quale file comincio?

| Voglio modificare… | Apro… |
| --- | --- |
| Introduzione e temi di ricerca della home | `content/home.json` |
| Nomi, ruoli, istituzioni e siti personali dei membri | `content/team.json` |
| Programma, abstract e archivio del seminario | `content/seminar.html` |
| Riassunto della prossima sessione nella home | `content/home.json` → `next_session` |
| Email, indirizzo e contatti | `content/contact.json` |
| Titoli dei banner, menu e piè di pagina | `content/site.json` |
| Colori, dimensioni del banner e impaginazione | `assets/css/site.css` |
| Fotografia del banner e logo | `assets/images/` |
| Struttura HTML di una pagina | `templates/pages/` |
| Elementi comuni e schede | `templates/partials/` |
| Ricerca dei membri e menu mobile | `assets/js/site.js` |

Per le modifiche quotidiane inizia da **`content/`**. Le pagine in **`public/`** sono create automaticamente: una modifica fatta lì viene sovrascritta alla generazione successiva.

## Lavorare da VS Code

Apri questa cartella come progetto. È sufficiente **Python 3.10 o successivo**; non servono npm, pacchetti Python o estensioni aggiuntive.

1. Apri il file indicato nella tabella e salva le modifiche.
2. Dal menu **Terminale → Esegui attività**, scegli **ParMA: anteprima locale**.
3. Apri [l'anteprima nel browser](http://127.0.0.1:8765/). Quando salvi altri cambiamenti, aggiorna la pagina: il sito viene rigenerato automaticamente.
4. Prima di pubblicare, esegui l'attività **ParMA: controlla il sito**. Genera le pagine e segnala eventuali collegamenti o immagini locali mancanti.

Per fermare l'anteprima premi **Ctrl+C** nel suo terminale. **Ctrl+Maiusc+B** esegue l'attività **ParMA: genera il sito** senza avviare il browser.

Gli stessi strumenti si possono avviare dal terminale del progetto:

```sh
python tools/build.py
python tools/check.py
python tools/preview.py
```

Se la porta dell'anteprima è già occupata, usa `python tools/preview.py --port 8770` e apri `http://127.0.0.1:8770/`.

## Esempi di modifica

### Aggiungere un membro o il suo sito personale

In `content/team.json`, individua il gruppo corretto e aggiungi un oggetto nella sua lista `members`:

```json
{
  "name": "Nome Cognome",
  "affiliation": "Inria, CR",
  "url": "https://esempio.fr/"
}
```

Usa `"url": null` se la persona non ha un sito. Se ha un indirizzo, il nome diventa automaticamente cliccabile. I gruppi e i membri appaiono nell'ordine del file; **Former members** resta una sezione sempre visibile, con lo stesso formato delle altre.

Nei file JSON conserva virgolette e virgole: una virgola separa due elementi, ma non va dopo l'ultimo elemento di una lista. Per un elenco vuoto usa `[]`.

### Aggiornare il seminario

`content/seminar.html` contiene sezioni commentate per organizzatori, sede, prossima sessione, calendario e archivio. Copia una scheda `session-card` per aggiungere una sessione; conserva la struttura `talk` per ciascun intervento. Quando una sessione è passata, sposta la scheda nell'anno corrispondente dell'archivio.

Aggiorna anche `next_session` in `content/home.json`: è il breve annuncio della home, senza abstract. La pagina completa del seminario è generata da `content/seminar.html`.

### Cambiare immagine e altezza del banner

Sostituisci `assets/images/mountains.jpg` con la nuova fotografia mantenendo il nome. In `assets/css/site.css`, cerca la sezione **Banner**: `.hero-home` regola l'altezza della home, `.hero` quella delle altre pagine. `background-position` regola quale parte dell'immagine viene mostrata. Più avanti trovi le regole per tablet, telefono e stampa.

## Come sono organizzate le cartelle?

```text
parma-site/
├── README.md                 ← questa guida
├── content/                  ← contenuti da aggiornare
├── templates/
│   ├── layout.html           ← documento HTML comune
│   ├── pages/                ← home, membri e contatti
│   └── partials/             ← menu, banner, footer e schede
├── assets/
│   ├── css/site.css          ← stile
│   ├── js/site.js            ← menu e ricerca
│   └── images/               ← fotografia, logo e icona
├── tools/
│   ├── build.py              ← genera public/
│   ├── check.py              ← controlla file e link locali
│   └── preview.py            ← avvia l'anteprima
├── docs/sources/             ← provenienza dei materiali importati
├── public/                   ← sito generato, escluso da Git
├── .vscode/                  ← attività e impostazioni del progetto
└── .github/workflows/        ← pubblicazione automatica
```

I modelli usano segnaposto come `$introduction` e `${prefix}`. Lo strumento di generazione inserisce i contenuti e calcola i percorsi relativi. `content/seminar.html` è già il corpo HTML del seminario e viene inserito nel documento comune.

Le quattro pagine conservano gli indirizzi `/`, `/team-members/`, `/francais-gdt-edp-ot-ml/` e `/contact/`. Le varianti `/en/` sono generate dagli stessi contenuti.

## Pubblicare una modifica

Nel pannello **Controllo del codice sorgente** di VS Code, verifica le modifiche, scrivi una breve descrizione, crea il commit e usa **Push**. Al caricamento su `main`, GitHub genera il sito, controlla i collegamenti e pubblica **soltanto `public/`**. Non devi caricare a mano le pagine generate.

Su GitHub la scheda **Actions** mostra il risultato dell'attività **Pubblica il sito ParMA**. La sorgente in **Settings → Pages** deve essere **GitHub Actions**. Una proposta di modifica in un altro branch viene controllata prima della pubblicazione su `main`.

Il controllo locale verifica pagine, immagini e sezioni del sito; i collegamenti a siti esterni restano da verificare nel browser quando li modifichi.

## Materiali originali e documentazione

La migrazione mantiene i testi scientifici, i collegamenti personali e i materiali del [sito Inria originale](https://team.inria.fr/parma/). La loro provenienza è documentata in `docs/sources/`; quella cartella non alimenta il sito. Fotografie, logo e testi mantengono le condizioni d'uso originali.

Il sito usa HTML, CSS, JavaScript e la libreria standard di Python. Non include analytics, font esterni o strumenti di tracciamento.

Riferimenti tecnici: [pubblicazione con GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [caricamento delle pagine generate](https://github.com/actions/upload-pages-artifact), [pubblicazione dell'artefatto](https://github.com/actions/deploy-pages).
