<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Verbindet die Anwendungen der omega-Suite miteinander, auf einem Rechner und im ganzen Netzwerk**

> Entwickelt von [kraynux](https://github.com/kraynux) für [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Offizielle Seite: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/de/) &nbsp; Vorschau: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Oberfläche in **17 Sprachen** verfügbar — siehe [Sprachen der Oberfläche](#sprachen-der-oberfläche).  
**Sprachen:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** ist der Verbinder der `omega-`-Suite: Er findet die installierten omega-Anwendungen (omega-serv, omega-fire, omega-jail…) auf diesem Rechner und auf den Rechnern Ihres Netzwerks, zeigt, was miteinander verbunden ist und was nicht, und stellt wieder her, was fehlt — und zeigt dabei immer zuerst, was er tun wird. Einmal verbunden, finden sich die Anwendungen gegenseitig, ohne dass omega-connect laufen muss.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-connect/D.png" width="24%" />
</p>

## 1. Vision und Umfang

Die omega-Anwendungen sind für die Zusammenarbeit gemacht: Die Logs von omega-serv werden von den Jails von omega-jail gelesen, die Sperren von fail2ban landen in der Sperrliste von omega-serv, omega-fire zeigt all das an. Dafür müssen die Dateien aber am richtigen Ort liegen, mit den richtigen Rechten, und jede Anwendung muss wissen, wo die anderen sind. Darum kümmert sich Omega-connect.

### Was Omega-connect tut

- Findet die omega-Anwendungen dieses Rechners (persönlicher Ordner, Dienste von systemd, OpenRC oder runit, `/srv`, Instanzregister von omega-serv) und die der anderen Rechner, erreicht per SSH mit Ihren Schlüsseln.
- Führt ein **Register** aller Anwendungen aller Rechner, mit ihrer Version und ihrem Zustand.
- Prüft jede **Verbindung** zwischen Anwendungen (von den Jails gelesene Logs, Brücke zur Sperrliste, Schutzliste, Dateien von omega-jail in fail2ban, Ausweise, gemeinsamer Bereich) und sagt, was nicht stimmt.
- **Synchronisiert**: erstellt die fehlenden Ausweise und bereitet den **gemeinsamen Bereich** vor, in dem sich die Anwendungen gegenseitig finden.
- **Repariert**: lässt jede Abweichung von der Anwendung korrigieren, der die Datei gehört; niemals omega-connect an ihrer Stelle.
- **Aktualisiert oder installiert neu** eine zu alte oder fehlerhaft installierte Anwendung eines Netzwerkrechners, aus ihrem GitHub-Release (Prüfsumme verifiziert).
- Handelt auf einem Netzwerkrechner **von Ihrem Arbeitsplatz aus**: dort ist nichts einzutippen, sein Passwort wird einmal abgefragt, von ihm selbst.
- Erstellt einen vollständigen **Bericht** (Text, JSON oder HTML-Seite).

### Was Omega-connect nicht tut

- Er ersetzt keine Anwendung: fail2ban, omega-fire, omega-jail und omega-serv behalten jeweils ihre Rolle.
- Er schreibt niemals die Datei einer anderen Anwendung um.
- Er installiert nichts Dauerhaftes auf einem Netzwerkrechner, um ihn zu scannen, und lässt keinen Dienst laufen.
- Er fragt niemals nach dem SSH-Passwort und sieht niemals Ihr Administratorpasswort.

## 2. Installation

### Voraussetzungen

- Linux, Python 3.10+.
- Für die Netzwerkrechner: ein SSH-Zugang per Schlüssel und Python 3.10+ auf diesen Rechnern.
- Internetverbindung für die Abhängigkeiten (und für die Aktualisierungen von GitHub).

### Installation

Aus dem Ordner, in dem das Archiv liegt:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Erstellt die virtuelle Umgebung `.venv` (eine unvollständige `.venv` wird beiseitegelegt und neu erstellt).
2. Installiert omega-lib (Bibliothek der Suite, im Archiv enthalten) und omega-connect.
3. Macht `omega-connect.sh` und `install.sh` ausführbar.
4. Fügt den Alias `connect` zu `~/.bashrc` und `~/.zshrc` hinzu (ohne Duplikat).

Kein Schritt verlangt Administratorrechte.

### Aktualisierung

Aus dem Ordner, der `omega-connect/` ENTHÄLT (niemals von innen: `tar` würde einen verschachtelten Ordner erstellen), entpacken Sie das neue Archiv darüber und starten dann `install.sh` erneut. Das Archiv enthält keine lokalen Daten (`var/`: Register der Rechner, Einstellungen, Exporte): Nichts Vorhandenes wird überschrieben.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Verwendung

### Interaktiver Modus (TUI)

```bash
./omega-connect.sh
```

oder, wenn der Alias angelegt ist, `connect`.

Das Hauptmenü hat zwei Spalten:

| Verwaltung | Wartung |
|---|---|
| **Register** — alle Anwendungen aller Rechner, ihre Version und ihr Zustand | **Reparieren** — die Liste von allem, was nicht stimmt, und Sie wählen aus |
| **Scannen** — dieser Rechner und das Hinzufügen der Netzwerkrechner | **Bericht** — ein vollständiges Dokument zum Exportieren |
| **Verbindungen** — was verbunden ist und was nicht, mit seinem Zustand | **Einstellungen** — Sprache, Themes, Ordner, Bereinigen |
| **Synchronisierung** — die Anwendungen verbinden, auf allen Rechnern | **Hilfe** — jedes Menü, seine Funktion und die Details |
| **Dashboard** — die Gesamtübersicht | **Beenden** |

Typischer Ablauf: **Scannen** (dieser Rechner, dann Ihre anderen Rechner, vorgeschlagen anhand Ihrer Unison-Profile, `~/.ssh/config` und `known_hosts`) → **Register** (eine alte Anwendung aktualisieren oder neu installieren) → **Synchronisierung** (abhaken, dann synchronisieren) → **Verbindungen** und **Dashboard**, um das Ergebnis zu sehen → **Reparieren**, falls noch eine Abweichung bleibt.

Jede Aktion zeigt zuerst ihren Plan; nichts wird ohne Ihre Zustimmung gestartet. Bei einem Netzwerkrechner überlässt die Oberfläche dem Terminal für die Dauer der Aktion den Platz: Der Rechner fragt selbst nach seinem Passwort, einmal.

#### Tastenkürzel

| Taste | Aktion |
|---|---|
| `↑` / `↓` | Von einem Element zum nächsten wechseln |
| `Tab` / `Umschalt+Tab` | Von einem Bildschirmbereich zum nächsten wechseln |
| `Eingabe` / `Leertaste` | Aktivieren; eine Zeile abhaken (Synchronisierung) |
| `Esc` | Zurück zum vorherigen Bildschirm |
| `a` | Hilfe |
| `s` | Einstellungen |
| `t` | Nächstes Theme |
| `r` | Bildschirm neu zeichnen |
| `q` | Beenden (mit Bestätigung) |
| `Ctrl+P` | Befehle: Theme, Bildschirmfoto, Beenden |

### Zustände

| Anwendungen | Verbindungen |
|---|---|
| ● Verbunden — im gemeinsamen Bereich, aktuell | OK |
| ◐ Eingetragen — hat ihren Ausweis, noch nicht im gemeinsamen Bereich | zu reparieren |
| ○ Erkannt — ohne Ausweis | zu reparieren (blockierend) |
| ▲ Zu reparieren — eine Abweichung | fehlt — nichts zu verbinden |
| ◌ Alte Version — zu aktualisieren | nicht prüfbar |
| ◇ Unvollständige Installation — neu zu installieren | |
| ✕ Nicht erreichbar — der Rechner antwortet nicht mehr | |

### Sprachen der Oberfläche

Die Oberfläche ist in 17 Sprachen verfügbar: Französisch, Englisch, Spanisch, Portugiesisch (Brasilien), Italienisch, Deutsch, Niederländisch, Polnisch, Russisch, vereinfachtes Chinesisch, Vietnamesisch, Thailändisch, Indonesisch, Japanisch, Koreanisch, Hindi und Arabisch. Die Auswahl erfolgt in den Einstellungen (« Langue / Language ») und wird nach einem Neustart der Oberfläche angewendet; die Variable `OMEGA_CONNECT_LANG` (zum Beispiel `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) erzwingt eine Sprache für die Dauer einer Sitzung. In einer Linux-Textkonsole (TTY) werden Sprachen mit nicht-lateinischer Schrift für die Sitzung auf Englisch angezeigt. Die Befehlszeile bleibt auf Französisch.

### Kontakt und Support

Die Hilfe (Taste `a`) bietet einen Bildschirm **Kontakt und Support**: *Einen Kaffee spendieren* (PayPal-Seite des Entwicklers), *Support kontaktieren* (E-Mail-Adresse und Kontaktformular der Website, im Klartext angezeigt), *Mich als Nutzer melden (anonym)* und *Updates prüfen*. Die Meldung ist freiwillig, standardmäßig ausgeschaltet und wird nur einmal gesendet: Sie dient nur dazu, die Nutzer zu zählen und, wenn gewünscht, ihren Kontinent oder ihr Land (geschlossene Listen, nie Freitext). Gesendet werden ein zufällig gezogener Schlüssel, der Name der Software (`omega-connect`) und ihre Version; niemals ein Name, ein Rechnername, eine Adresse oder eine Einstellung. Die IP-Adresse wird in den Meldungen nicht gespeichert, durchläuft aber wie jeder Besuch die Sicherheitsprüfungen und das Protokoll des empfangenden Servers. Rückzug jederzeit über denselben Bildschirm. Die Update-Prüfung liest nur die Liste der veröffentlichten Versionen, und niemals ohne Klick.

### Skriptfähiger Modus (CLI)

Jeder Befehl löst den Befehlszeilenmodus aus:

```bash
# Anwendungen dieses Rechners oder eines Netzwerkrechners (SSH mit Ihren Schlüsseln)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Die Anwendungen dieses Rechners oder eines Netzwerkrechners verbinden
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Die zu alten Anwendungen eines Netzwerkrechners aktualisieren (GitHub-Release)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Reparieren: dieser Rechner oder ein Netzwerkrechner
./omega-connect.sh reparer --machine moi@192.168.1.109

# Zustand jeder Verbindung und vollständiger Bericht
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` zeigt den Plan, ohne etwas zu starten; `--oui` startet ohne Rückfrage; `--toutes-machines` arbeitet alle bekannten Rechner nacheinander ab.

## 4. Netzwerkrechner

- **Verbindung:** nur SSH mit Ihren Schlüsseln; `~/.ssh/config` wird beachtet (Alias, Port, Benutzer). Ein mit einer Passphrase geschützter Schlüssel muss im SSH-Agenten geladen sein.
- **Erste Verbindung:** Der Fingerabdruck des Schlüssels des Rechners wird vor allem anderen angezeigt; ein geänderter Schlüssel wird abgelehnt.
- **Scan:** Ein Programm wird in den Arbeitsspeicher gesendet, nur lesend; nichts wird installiert oder geschrieben, kein Passwort wird abgefragt.
- **Aktion** (synchronisieren, reparieren, aktualisieren): Ein privater temporärer Ordner nimmt das Programm und gegebenenfalls die Archive auf; er wird am Ende gelöscht. Das Administratorpasswort wird vom Rechner selbst abgefragt, einmal.
- **Identität:** Ein Rechner wird am Fingerabdruck seiner Systemkennung erkannt, nicht an seiner Adresse: Über zwei Netzwerke erreicht, bleibt er ein einziger Rechner.
- **Aktualisierungen:** aus dem GitHub-Release jeder Anwendung; die Prüfsumme des Archivs wird vor jedem Senden mit `sha.txt` geprüft, dann erneut auf dem Rechner. Jede Anwendung wird so installiert, wie es der Abschnitt „Aktualisierung“ ihres README beschreibt.

## 5. Ausweis und gemeinsamer Bereich

- **Ausweis:** Bei ihrer Installation schreibt jede omega-Anwendung eine kleine Datei, die sagt, wer sie ist (Anwendung, Version, Kennung, Rechner). Für alle lesbar, niemals durch andere Konten änderbar.
- **Gemeinsamer Bereich:** `/var/lib/omega-synchro`, der Gruppe `omega-synchro` vorbehalten, in den nur der Administrator schreibt. Omega-connect kopiert die Ausweise und die Beschreibung jeder Anwendung dorthin; die Anwendungen finden sich dort gegenseitig, auch wenn omega-connect nicht läuft.
- **Register des gemeinsamen Bereichs:** Alles, was omega-connect erstellt, wird dort eingetragen; ein Entfernen macht nur rückgängig, was dort eingetragen ist, und eine unbekannte Datei wird niemals gelöscht.

## 6. Sicherheit

- Keine Rechteerhöhung beim Start: omega-connect läuft unter Ihrem Konto; sudo wird Aktion für Aktion abgefragt, der Befehl wird vorher angezeigt.
- Die Korrekturen werden von der Anwendung vorgenommen, der die Datei gehört (omega-jail für das, was es in fail2ban ablegt, omega-serv für die Rechte seines `var/`, jede Anwendung für ihren Ausweis).
- Keine Anwendung wird gestartet, wenn sie ohne Terminal nach einem Passwort fragen könnte.
- Die Suche folgt niemals einem symbolischen Link, wechselt nicht das Dateisystem und ignoriert Netzwerk-Einhängepunkte.
- Die Bereinigung der Export- und Screenshot-Ordner verweigert System- und persönliche Ordner sowie den von omega-connect.

## 7. Exporte

- **Bericht**: Bilanz aller Rechner, genaue Liste dessen, was noch zu tun ist, Register, Netzwerkrechner, Verbindungen jedes Rechners, gemeinsamer Bereich. Text, JSON oder HTML-Seite (Theme nach Wahl).
- **Hilfe**: als HTML-Seite exportierbar.
- **Bildschirmfotos**: `Ctrl+P` → „Bildschirmfoto“ (SVG).
- Standardordner: `var/exports/` und `var/screenshots/` im Ordner von omega-connect, in den Einstellungen änderbar.

## 8. Architektur

Clean Architecture, wie der Rest der Suite: `domain/` (reine Regeln), `application/` (Anwendungsfälle), `ports/`, `infrastructure/` (SSH, Dateien, GitHub, Zwischenablage), `interfaces/` (Befehlszeile und Textual-Oberfläche), `app/` (Zusammensetzung). Die Abhängigkeiten zeigen immer nach innen, geprüft durch `import-linter`. Die zwischen Anwendungen geteilten Verträge (Ausweis, Beschreibung, gemeinsamer Bereich) liegen in `omega-lib`.

## 9. Tests

```bash
source .venv/bin/activate
lint-imports        # prüft die Abhängigkeitsregel
pytest -q
ruff check src tests
mypy src
```

Die Tests berühren niemals das echte `var/`, weder das Netzwerk noch sudo: falsches SSH, lokal ausgeführt, falsches GitHub, temporäre Ordner.

## 10. Außerhalb des Umfangs

- fail2ban, omega-fire oder omega-jail ersetzen.
- Kontinuierlich überwachen (kein dauerhafter Dienst).
- Eine omega-Anwendung zum ersten Mal auf einem Netzwerkrechner installieren.
- Web-Dashboard.

## Lizenz

MIT — siehe [LICENSE](../../../LICENSE).

---

> Omega-connect — Finden, verbinden, reparieren.
> Die omega-Anwendungen sprechen miteinander; omega-connect sorgt dafür, dass sie es können.
