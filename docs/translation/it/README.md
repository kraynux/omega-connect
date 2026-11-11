<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="512">
</div>

# 🔗 OMEGA-CONNECT

**Collega tra loro le applicazioni della suite omega, su una macchina e su tutta la rete**

> Realizzato da [kraynux](https://github.com/kraynux) per [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Pagina ufficiale: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/it/) &nbsp; Anteprima: [Screenshot](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interfaccia disponibile in **17 lingue** — vedi [Lingue dell'interfaccia](#lingue-dellinterfaccia).  
**Lingue:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** è l'interconnettore della suite `omega-`: trova le applicazioni omega installate (omega-serv, omega-fire, omega-jail…) su questa macchina e sulle macchine della tua rete, mostra cosa è collegato tra loro e cosa no, e rimette a posto ciò che manca — mostrando sempre prima cosa farà. Una volta collegate, le applicazioni si trovano tra loro senza che omega-connect sia avviato.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/it/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/it/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/it/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/it/omega-connect/D.png" width="24%" />
</p>

## 1. Visione e perimetro

Le applicazioni omega sono fatte per lavorare insieme: i log di omega-serv vengono letti dalle jail di omega-jail, i ban di fail2ban finiscono nella lista nera di omega-serv, omega-fire mostra tutto questo. Bisogna però che i file siano al posto giusto, con i permessi giusti, e che ogni applicazione sappia dove sono le altre. Omega-connect se ne occupa.

### Cosa fa Omega-connect

- Trova le applicazioni omega di questa macchina (cartella personale, servizi systemd, OpenRC o runit, `/srv`, registro delle istanze di omega-serv) e quelle delle altre macchine, raggiunte via SSH con le tue chiavi.
- Tiene un **registro** di tutte le applicazioni di tutte le macchine, con la loro versione e il loro stato.
- Verifica ogni **collegamento** tra applicazioni (log letti dalle jail, ponte verso la lista nera, lista protetta, file di omega-jail in fail2ban, carte d'identità, spazio condiviso) e dice cosa non va.
- **Sincronizza**: crea le carte d'identità mancanti e prepara lo **spazio condiviso** dove le applicazioni si trovano tra loro.
- **Ripara**: fa correggere ogni anomalia dall'applicazione proprietaria del file; mai omega-connect al suo posto.
- **Aggiorna o reinstalla** un'applicazione troppo vecchia o installata male su una macchina di rete, dalla sua Release GitHub (impronta verificata).
- Agisce su una macchina di rete **dalla tua postazione**: niente da digitare laggiù, la sua password viene chiesta una volta, dalla macchina stessa.
- Produce un **rapporto** completo (testo, JSON o pagina HTML).

### Cosa non fa Omega-connect

- Non sostituisce nessuna applicazione: fail2ban, omega-fire, omega-jail e omega-serv mantengono ciascuno il proprio ruolo.
- Non riscrive mai il file di un'altra applicazione.
- Non installa nulla di permanente su una macchina di rete per scansionarla, e non lascia nessun servizio in esecuzione.
- Non chiede mai la password SSH, e non vede mai la tua password di amministratore.

## 2. Installazione

### Prerequisiti

- Linux, Python 3.10+.
- Per le macchine di rete: un accesso SSH con chiave, e Python 3.10+ su quelle macchine.
- Connessione Internet per le dipendenze (e per gli aggiornamenti da GitHub).

### Installazione

Dalla cartella in cui si trova l'archivio:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Crea l'ambiente virtuale `.venv` (un `.venv` incompleto viene messo da parte e ricreato).
2. Installa omega-lib (libreria della suite, fornita nell'archivio) e omega-connect.
3. Rende eseguibili `omega-connect.sh` e `install.sh`.
4. Aggiunge l'alias `connect` a `~/.bashrc` e `~/.zshrc` (senza duplicati).

Nessun passaggio richiede privilegi di amministratore.

### Aggiornamento

Dalla cartella che CONTIENE `omega-connect/` (mai dall'interno: `tar` creerebbe una cartella annidata), estrai il nuovo archivio sopra quello esistente, poi rilancia `install.sh`. L'archivio non contiene alcun dato locale (`var/`: registro delle macchine, impostazioni, esportazioni): nulla di ciò che esiste viene sovrascritto.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Utilizzo

### Modalità interattiva (TUI)

```bash
./omega-connect.sh
```

oppure, se l'alias è stato creato, `connect`.

Il menu principale ha due colonne:

| Gestione | Manutenzione |
|---|---|
| **Registro** — tutte le applicazioni di tutte le macchine, la loro versione e il loro stato | **Ripara** — l'elenco di tutto ciò che non va, e scegli tu |
| **Scansiona** — questa macchina, e l'aggiunta delle macchine di rete | **Rapporto** — un documento completo, da esportare |
| **Collegamenti** — ciò che è collegato o no, con il suo stato | **Impostazioni** — lingua, temi, cartelle, pulizia |
| **Sincronizzazione** — collegare le applicazioni, su tutte le macchine | **Aiuto** — ogni menu, la sua funzione e il dettaglio |
| **Dashboard** — la panoramica | **Esci** |

Percorso tipico: **Scansiona** (questa macchina, poi le tue altre macchine, proposte in base ai tuoi profili Unison, a `~/.ssh/config` e a `known_hosts`) → **Registro** (aggiornare o reinstallare un'applicazione vecchia) → **Sincronizzazione** (spuntare, poi sincronizzare) → **Collegamenti** e **Dashboard** per vedere il risultato → **Ripara** se resta un'anomalia.

Ogni azione mostra prima il suo piano; nulla viene avviato prima del tuo consenso. Per una macchina di rete, l'interfaccia lascia il posto al terminale per la durata dell'azione: è la macchina stessa a chiedere la sua password, una volta.

#### Scorciatoie da tastiera

| Tasto | Azione |
|---|---|
| `↑` / `↓` | Passare da un elemento all'altro |
| `Tab` / `Maiusc+Tab` | Passare da una zona dello schermo all'altra |
| `Invio` / `Spazio` | Attivare; spuntare una riga (Sincronizzazione) |
| `Esc` | Tornare alla schermata precedente |
| `a` | Aiuto |
| `s` | Impostazioni |
| `t` | Tema successivo |
| `r` | Ridisegnare lo schermo |
| `q` | Uscire (con conferma) |
| `Ctrl+P` | Comandi: tema, screenshot, uscire |

### Stati

| Applicazioni | Collegamenti |
|---|---|
| ● Collegata — nello spazio condiviso, aggiornata | OK |
| ◐ Registrata — ha la sua carta d'identità, non ancora nello spazio condiviso | da riparare |
| ○ Rilevata — senza carta d'identità | da riparare (bloccante) |
| ▲ Da riparare — un'anomalia | assente — niente da collegare |
| ◌ Versione obsoleta — da aggiornare | non verificabile |
| ◇ Installazione incompleta — da reinstallare | |
| ✕ Irraggiungibile — la macchina non risponde più | |

### Lingue dell'interfaccia

L'interfaccia è disponibile in 17 lingue: francese, inglese, spagnolo, portoghese (Brasile), italiano, tedesco, olandese, polacco, russo, cinese semplificato, vietnamita, thailandese, indonesiano, giapponese, coreano, hindi e arabo. La scelta si fa nelle Impostazioni (« Langue / Language ») e si applica dopo un riavvio dell'interfaccia; la variabile `OMEGA_CONNECT_LANG` (ad esempio `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) forza una lingua per la durata di una sessione. Su una console testuale Linux (TTY), le lingue con scrittura non latina vengono mostrate in inglese per la sessione. La riga di comando resta in francese.

### Contatti e supporto

L'aiuto (tasto `a`) propone una schermata **Contatti e supporto**: *Offrire un caffè* (pagina PayPal dello sviluppatore), *Contattare il supporto* (indirizzo e-mail e modulo di contatto del sito, mostrati in chiaro), *Dichiararmi utente (anonimo)* e *Verifica aggiornamenti*. La dichiarazione è volontaria, disattivata di default e inviata una sola volta: serve solo a contare gli utenti e, se lo desideri, il loro continente o paese (elenchi chiusi, mai testo libero). Invia una chiave estratta a caso, il nome del software (`omega-connect`) e la sua versione; mai nomi, nome della macchina, indirizzo o impostazioni. L'indirizzo IP non viene registrato nelle dichiarazioni, ma passa, come ogni visita, dai controlli di sicurezza e dal log del server di ricezione. Puoi ritirarti in qualsiasi momento dalla stessa schermata. La verifica degli aggiornamenti legge solo l'elenco delle versioni pubblicate, e mai senza un clic.

### Modalità scriptabile (CLI)

Qualsiasi comando attiva la modalità riga di comando:

```bash
# Applicazioni di questa macchina, o di una macchina di rete (SSH con le tue chiavi)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Collegare le applicazioni di questa macchina, o di una macchina di rete
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Aggiornare le applicazioni troppo vecchie di una macchina di rete (Release GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Riparare: questa macchina, o una macchina di rete
./omega-connect.sh reparer --machine moi@192.168.1.109

# Stato di ogni collegamento, e rapporto completo
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` mostra il piano senza avviare nulla; `--oui` avvia senza fare la domanda; `--toutes-machines` concatena tutte le macchine conosciute, una alla volta.

## 4. Macchine di rete

- **Connessione:** solo SSH con le tue chiavi; `~/.ssh/config` viene rispettato (alias, porta, utente). Una chiave protetta da passphrase deve essere caricata nell'agente SSH.
- **Prima connessione:** l'impronta della chiave della macchina viene mostrata prima di tutto; una chiave che è cambiata viene rifiutata.
- **Scansione:** un programma viene inviato in memoria, in sola lettura; nulla viene installato né scritto, nessuna password viene chiesta.
- **Azione** (sincronizzare, riparare, aggiornare): una cartella privata temporanea riceve il programma e, se serve, gli archivi; viene cancellata alla fine. La password di amministratore viene chiesta dalla macchina stessa, una volta.
- **Identità:** una macchina viene riconosciuta dall'impronta del suo identificativo di sistema, non dal suo indirizzo: raggiunta da due reti, resta una sola macchina.
- **Aggiornamenti:** dalla Release GitHub di ogni applicazione; l'impronta dell'archivio viene verificata con `sha.txt` prima di ogni invio, poi di nuovo sulla macchina. Ogni applicazione viene installata come indica la sezione « Aggiornamento » del suo README.

## 5. Carta d'identità e spazio condiviso

- **Carta d'identità:** alla sua installazione, ogni applicazione omega scrive un piccolo file che dice chi è (applicazione, versione, identificativo, macchina). Leggibile da tutti, mai modificabile dagli altri account.
- **Spazio condiviso:** `/var/lib/omega-synchro`, riservato al gruppo `omega-synchro`, dove scrive solo l'amministratore. Omega-connect vi copia le carte d'identità e la descrizione di ogni applicazione; le applicazioni vi si trovano tra loro, anche quando omega-connect non è avviato.
- **Registro dello spazio condiviso:** tutto ciò che omega-connect crea vi viene registrato; una rimozione disfa solo ciò che vi è registrato, e un file sconosciuto non viene mai eliminato.

## 6. Sicurezza

- Nessuna elevazione all'avvio: omega-connect gira con il tuo account; sudo viene chiesto azione per azione, con il comando mostrato prima.
- Le correzioni vengono fatte dall'applicazione proprietaria del file (omega-jail per ciò che mette in fail2ban, omega-serv per i permessi del suo `var/`, ogni applicazione per la sua carta d'identità).
- Nessuna applicazione viene avviata se rischia di chiedere una password senza terminale.
- La ricerca non segue mai un link simbolico, non cambia file system e ignora i mount di rete.
- La pulizia delle cartelle di esportazione e degli screenshot rifiuta le cartelle di sistema, quelle personali e quella di omega-connect.

## 7. Esportazioni

- **Rapporto**: bilancio di tutte le macchine, elenco preciso di ciò che resta da fare, registro, macchine di rete, collegamenti di ogni macchina, spazio condiviso. Testo, JSON o pagina HTML (tema a scelta).
- **Aiuto**: esportabile come pagina HTML.
- **Screenshot**: `Ctrl+P` → « Screenshot » (SVG).
- Cartelle predefinite: `var/exports/` e `var/screenshots/` della cartella di omega-connect, modificabili nelle Impostazioni.

## 8. Architettura

Clean Architecture, come il resto della suite: `domain/` (regole pure), `application/` (casi d'uso), `ports/`, `infrastructure/` (SSH, file, GitHub, appunti), `interfaces/` (riga di comando e interfaccia Textual), `app/` (assemblaggio). Le dipendenze vanno sempre verso l'interno, verificate da `import-linter`. I contratti condivisi tra applicazioni (carta d'identità, descrizione, spazio condiviso) vivono in `omega-lib`.

## 9. Test

```bash
source .venv/bin/activate
lint-imports        # verifica la regola delle dipendenze
pytest -q
ruff check src tests
mypy src
```

I test non toccano mai il vero `var/`, né la rete, né sudo: SSH finto eseguito in locale, GitHub finto, cartelle temporanee.

## 10. Fuori perimetro

- Sostituire fail2ban, omega-fire o omega-jail.
- Sorvegliare in continuo (nessun servizio permanente).
- Installare un'applicazione omega per la prima volta su una macchina di rete.
- Dashboard web.

## Licenza

MIT — vedi [LICENSE](../../../LICENSE).

---

> Omega-connect — Trovare, collegare, riparare.
> Le applicazioni omega si parlano; omega-connect si assicura che possano farlo.
