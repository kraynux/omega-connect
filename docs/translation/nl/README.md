<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Koppelt de toepassingen van de omega-suite aan elkaar, op één machine en over het hele netwerk**

> Ontwikkeld door [kraynux](https://github.com/kraynux) voor [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Officiële pagina: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/nl/) &nbsp; Voorbeeld: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interface beschikbaar in **17 talen** — zie [Talen van de interface](#talen-van-de-interface).  
**Talen:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** is de verbinder van de `omega-`-suite: hij vindt de geïnstalleerde omega-toepassingen (omega-serv, omega-fire, omega-jail…) op deze machine en op de machines van uw netwerk, laat zien wat wel of niet aan elkaar gekoppeld is, en zet terug wat ontbreekt — en laat daarbij altijd eerst zien wat hij gaat doen. Eenmaal gekoppeld vinden de toepassingen elkaar, zonder dat omega-connect hoeft te draaien.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-connect/D.png" width="24%" />
</p>

## 1. Visie en reikwijdte

De omega-toepassingen zijn gemaakt om samen te werken: de logs van omega-serv worden gelezen door de jails van omega-jail, de bans van fail2ban komen terecht op de zwarte lijst van omega-serv, omega-fire toont dat allemaal. Dan moeten de bestanden wel op de juiste plek staan, met de juiste rechten, en moet elke toepassing weten waar de andere zijn. Daar zorgt Omega-connect voor.

### Wat Omega-connect doet

- Vindt de omega-toepassingen van deze machine (persoonlijke map, diensten van systemd, OpenRC of runit, `/srv`, instantieregister van omega-serv) en die van de andere machines, bereikt via SSH met uw sleutels.
- Houdt een **register** bij van alle toepassingen op alle machines, met hun versie en hun status.
- Controleert elke **koppeling** tussen toepassingen (logs gelezen door de jails, brug naar de zwarte lijst, beschermde lijst, bestanden van omega-jail in fail2ban, identiteitskaarten, gedeelde ruimte) en zegt wat er niet klopt.
- **Synchroniseert**: maakt de ontbrekende identiteitskaarten aan en bereidt de **gedeelde ruimte** voor waarin de toepassingen elkaar vinden.
- **Herstelt**: laat elke afwijking corrigeren door de toepassing die eigenaar is van het bestand; nooit omega-connect in haar plaats.
- **Werkt bij of installeert opnieuw** een te oude of slecht geïnstalleerde toepassing op een netwerkmachine, vanuit haar GitHub-release (controlesom gecontroleerd).
- Handelt op een netwerkmachine **vanaf uw eigen computer**: daar hoeft u niets te typen, het wachtwoord wordt één keer gevraagd, door de machine zelf.
- Maakt een volledig **rapport** (tekst, JSON of HTML-pagina).

### Wat Omega-connect niet doet

- Hij vervangt geen enkele toepassing: fail2ban, omega-fire, omega-jail en omega-serv behouden elk hun eigen rol.
- Hij herschrijft nooit het bestand van een andere toepassing.
- Hij installeert niets blijvends op een netwerkmachine om die te scannen, en laat geen dienst draaien.
- Hij vraagt nooit om het SSH-wachtwoord en ziet nooit uw beheerderswachtwoord.

## 2. Installatie

### Vereisten

- Linux, Python 3.10+.
- Voor de netwerkmachines: SSH-toegang met een sleutel, en Python 3.10+ op die machines.
- Internetverbinding voor de afhankelijkheden (en voor de updates vanaf GitHub).

### Installatie

Vanuit de map waarin het archief staat:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Maakt de virtuele omgeving `.venv` aan (een onvolledige `.venv` wordt opzijgezet en opnieuw aangemaakt).
2. Installeert omega-lib (bibliotheek van de suite, meegeleverd in het archief) en omega-connect.
3. Maakt `omega-connect.sh` en `install.sh` uitvoerbaar.
4. Voegt de alias `connect` toe aan `~/.bashrc` en `~/.zshrc` (zonder dubbele vermelding).

Geen enkele stap vraagt om beheerdersrechten.

### Bijwerken

Pak vanuit de map die `omega-connect/` BEVAT (nooit van binnenuit: `tar` zou een geneste map aanmaken) het nieuwe archief eroverheen uit en start daarna `install.sh` opnieuw. Het archief bevat geen lokale gegevens (`var/`: register van de machines, instellingen, exports): niets van wat er al is wordt overschreven.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Gebruik

### Interactieve modus (TUI)

```bash
./omega-connect.sh
```

of, als de alias is aangemaakt, `connect`.

Het hoofdmenu heeft twee kolommen:

| Beheer | Onderhoud |
|---|---|
| **Register** — alle toepassingen op alle machines, hun versie en hun status | **Herstellen** — de lijst van alles wat niet in orde is, en u kiest |
| **Scannen** — deze machine, en het toevoegen van de netwerkmachines | **Rapport** — een volledig document, om te exporteren |
| **Koppelingen** — wat wel of niet gekoppeld is, met de status | **Instellingen** — taal, thema's, mappen, opschonen |
| **Synchronisatie** — de toepassingen koppelen, op alle machines | **Help** — elk menu, zijn functie en de details |
| **Dashboard** — het overzicht | **Afsluiten** |

Typisch verloop: **Scannen** (deze machine, daarna uw andere machines, voorgesteld op basis van uw Unison-profielen, `~/.ssh/config` en `known_hosts`) → **Register** (een oude toepassing bijwerken of opnieuw installeren) → **Synchronisatie** (aanvinken, daarna synchroniseren) → **Koppelingen** en **Dashboard** om het resultaat te zien → **Herstellen** als er nog een afwijking overblijft.

Elke actie toont eerst haar plan; er wordt niets gestart zonder uw akkoord. Voor een netwerkmachine maakt de interface tijdens de actie plaats voor de terminal: de machine vraagt zelf om haar wachtwoord, één keer.

#### Sneltoetsen

| Toets | Actie |
|---|---|
| `↑` / `↓` | Van het ene element naar het andere gaan |
| `Tab` / `Shift+Tab` | Van de ene schermzone naar de andere gaan |
| `Enter` / `Spatie` | Activeren; een regel aanvinken (Synchronisatie) |
| `Esc` | Terug naar het vorige scherm |
| `a` | Help |
| `s` | Instellingen |
| `t` | Volgend thema |
| `r` | Het scherm opnieuw tekenen |
| `q` | Afsluiten (met bevestiging) |
| `Ctrl+P` | Opdrachten: thema, schermafbeelding, afsluiten |

### Statussen

| Toepassingen | Koppelingen |
|---|---|
| ● Gekoppeld — in de gedeelde ruimte, up-to-date | OK |
| ◐ Ingeschreven — heeft haar identiteitskaart, nog niet in de gedeelde ruimte | te herstellen |
| ○ Gedetecteerd — zonder identiteitskaart | te herstellen (blokkerend) |
| ▲ Te herstellen — een afwijking | ontbreekt — niets te koppelen |
| ◌ Oude versie — bij te werken | niet controleerbaar |
| ◇ Onvoltooide installatie — opnieuw te installeren | |
| ✕ Onbereikbaar — de machine reageert niet meer | |

### Talen van de interface

De interface is beschikbaar in 17 talen: Frans, Engels, Spaans, Portugees (Brazilië), Italiaans, Duits, Nederlands, Pools, Russisch, vereenvoudigd Chinees, Vietnamees, Thai, Indonesisch, Japans, Koreaans, Hindi en Arabisch. De keuze gebeurt in de Instellingen (« Langue / Language ») en wordt toegepast nadat de interface opnieuw is gestart; de variabele `OMEGA_CONNECT_LANG` (bijvoorbeeld `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) dwingt een taal af voor de duur van een sessie. In een Linux-tekstconsole (TTY) worden talen met een niet-Latijns schrift voor de sessie in het Engels weergegeven. De opdrachtregel blijft in het Frans.

### Contact en ondersteuning

De help (toets `a`) biedt een scherm **Contact en ondersteuning**: *Trakteer op een koffie* (PayPal-pagina van de ontwikkelaar), *Contact opnemen met ondersteuning* (e-mailadres en contactformulier van de site, leesbaar weergegeven), *Mij aanmelden als gebruiker (anoniem)* en *Updates controleren*. De aanmelding is vrijwillig, staat standaard uit en wordt maar één keer verstuurd: ze dient alleen om gebruikers te tellen en, desgewenst, hun continent of land (gesloten lijsten, nooit vrije tekst). Ze verstuurt een willekeurig getrokken sleutel, de naam van de software (`omega-connect`) en de versie ervan; nooit een naam, machinenaam, adres of instelling. Het IP-adres wordt niet vastgelegd in de aanmeldingen, maar gaat zoals elk bezoek door de beveiligingscontroles en het logboek van de ontvangende server. Op elk moment in te trekken via hetzelfde scherm. De controle op updates leest alleen de lijst van gepubliceerde versies, en nooit zonder klik.

### Scriptbare modus (CLI)

Elke opdracht schakelt de opdrachtregelmodus in:

```bash
# Toepassingen van deze machine, of van een netwerkmachine (SSH met uw sleutels)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# De toepassingen van deze machine, of van een netwerkmachine, koppelen
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# De te oude toepassingen van een netwerkmachine bijwerken (GitHub-release)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Herstellen: deze machine, of een netwerkmachine
./omega-connect.sh reparer --machine moi@192.168.1.109

# Status van elke koppeling, en volledig rapport
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` toont het plan zonder iets te starten; `--oui` start zonder de vraag te stellen; `--toutes-machines` werkt alle bekende machines een voor een af.

## 4. Netwerkmachines

- **Verbinding:** alleen SSH met uw sleutels; `~/.ssh/config` wordt gerespecteerd (alias, poort, gebruiker). Een sleutel die met een wachtwoordzin is beveiligd, moet in de SSH-agent geladen zijn.
- **Eerste verbinding:** de vingerafdruk van de sleutel van de machine wordt eerst getoond; een gewijzigde sleutel wordt geweigerd.
- **Scan:** er wordt een programma naar het geheugen gestuurd, alleen-lezen; er wordt niets geïnstalleerd of geschreven, er wordt geen wachtwoord gevraagd.
- **Actie** (synchroniseren, herstellen, bijwerken): een tijdelijke privémap ontvangt het programma en, indien nodig, de archieven; die wordt aan het einde gewist. Het beheerderswachtwoord wordt door de machine zelf gevraagd, één keer.
- **Identiteit:** een machine wordt herkend aan de vingerafdruk van haar systeem-ID, niet aan haar adres: bereikt via twee netwerken blijft het één machine.
- **Updates:** vanuit de GitHub-release van elke toepassing; de controlesom van het archief wordt vóór elke verzending gecontroleerd met `sha.txt`, en daarna opnieuw op de machine. Elke toepassing wordt geïnstalleerd zoals de sectie „Bijwerken” van haar README zegt.

## 5. Identiteitskaart en gedeelde ruimte

- **Identiteitskaart:** bij haar installatie schrijft elke omega-toepassing een klein bestand dat zegt wie ze is (toepassing, versie, ID, machine). Leesbaar voor iedereen, nooit te wijzigen door andere accounts.
- **Gedeelde ruimte:** `/var/lib/omega-synchro`, voorbehouden aan de groep `omega-synchro`, waarin alleen de beheerder schrijft. Omega-connect kopieert er de identiteitskaarten en de beschrijving van elke toepassing naartoe; de toepassingen vinden elkaar daar, ook wanneer omega-connect niet draait.
- **Register van de gedeelde ruimte:** alles wat omega-connect aanmaakt, wordt erin ingeschreven; een verwijdering maakt alleen ongedaan wat erin is ingeschreven, en een onbekend bestand wordt nooit verwijderd.

## 6. Beveiliging

- Geen verhoging van rechten bij het starten: omega-connect draait onder uw account; sudo wordt actie per actie gevraagd, met de opdracht vooraf getoond.
- De correcties worden uitgevoerd door de toepassing die eigenaar is van het bestand (omega-jail voor wat het in fail2ban plaatst, omega-serv voor de rechten van zijn `var/`, elke toepassing voor haar identiteitskaart).
- Er wordt geen enkele toepassing gestart als die zonder terminal om een wachtwoord zou kunnen vragen.
- Het zoeken volgt nooit een symbolische link, wisselt niet van bestandssysteem en negeert netwerkkoppelpunten.
- Het opschonen van de export- en schermafbeeldingsmappen weigert systeemmappen, persoonlijke mappen en die van omega-connect.

## 7. Exports

- **Rapport**: overzicht van alle machines, precieze lijst van wat er nog te doen is, register, netwerkmachines, koppelingen van elke machine, gedeelde ruimte. Tekst, JSON of HTML-pagina (thema naar keuze).
- **Help**: exporteerbaar als HTML-pagina.
- **Schermafbeeldingen**: `Ctrl+P` → „Schermafbeelding” (SVG).
- Standaardmappen: `var/exports/` en `var/screenshots/` in de map van omega-connect, aan te passen in de Instellingen.

## 8. Architectuur

Clean Architecture, zoals de rest van de suite: `domain/` (pure regels), `application/` (use cases), `ports/`, `infrastructure/` (SSH, bestanden, GitHub, klembord), `interfaces/` (opdrachtregel en Textual-interface), `app/` (samenstelling). De afhankelijkheden wijzen altijd naar binnen, gecontroleerd door `import-linter`. De contracten die toepassingen met elkaar delen (identiteitskaart, beschrijving, gedeelde ruimte) staan in `omega-lib`.

## 9. Tests

```bash
source .venv/bin/activate
lint-imports        # controleert de afhankelijkheidsregel
pytest -q
ruff check src tests
mypy src
```

De tests raken nooit de echte `var/` aan, noch het netwerk, noch sudo: nep-SSH lokaal uitgevoerd, nep-GitHub, tijdelijke mappen.

## 10. Buiten de reikwijdte

- fail2ban, omega-fire of omega-jail vervangen.
- Continu bewaken (geen permanente dienst).
- Een omega-toepassing voor het eerst installeren op een netwerkmachine.
- Webdashboard.

## Licentie

MIT — zie [LICENSE](../../../LICENSE).

---

> Omega-connect — Vinden, koppelen, herstellen.
> De omega-toepassingen praten met elkaar; omega-connect zorgt ervoor dat ze dat kunnen.
