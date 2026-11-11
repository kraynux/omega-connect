<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Links the applications of the omega suite together, on one machine and across the whole network**

> Developed by [kraynux](https://github.com/kraynux) for [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Official page: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/en/) &nbsp; Preview: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interface available in **17 languages** — see [Interface languages](#interface-languages).  
**Languages:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** is the interconnector of the `omega-` suite: it finds the installed omega applications (omega-serv, omega-fire, omega-jail…) on this machine and on the machines of your network, shows what is linked together and what is not, and puts back what is missing — always showing first what it is going to do. Once linked, the applications find each other without omega-connect running.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-connect/D.png" width="24%" />
</p>

## 1. Vision and scope

The omega applications are made to work together: omega-serv's logs are read by omega-jail's jails, fail2ban bans reach omega-serv's blocklist, omega-fire displays all of it. That still requires the files to be in the right place, with the right permissions, and each application to know where the others are. Omega-connect takes care of that.

### What Omega-connect does

- Finds the omega applications of this machine (home folder, systemd, OpenRC or runit services, `/srv`, omega-serv's instance registry) and those of the other machines, reached over SSH with your keys.
- Keeps a **registry** of all the applications of all the machines, with their version and their state.
- Checks each **link** between applications (logs read by the jails, bridge to the blocklist, protected list, omega-jail's files in fail2ban, identity cards, shared space) and says what is wrong.
- **Synchronizes**: creates the missing identity cards and prepares the **shared space** where the applications find each other.
- **Repairs**: has each discrepancy fixed by the application that owns the file; never omega-connect in its place.
- **Updates or reinstalls** a too-old or badly installed application on a network machine, from its GitHub Release (checksum verified).
- Acts on a network machine **from your computer**: nothing to type over there, its password asked once, by the machine itself.
- Produces a complete **report** (text, JSON or HTML page).

### What Omega-connect does not do

- It replaces no application: fail2ban, omega-fire, omega-jail and omega-serv each keep their role.
- It never rewrites another application's file.
- It installs nothing permanent on a network machine to scan it, and leaves no service running.
- It never asks for the SSH password, and never sees your administrator password.

## 2. Installation

### Requirements

- Linux, Python 3.10+.
- For network machines: key-based SSH access, and Python 3.10+ on those machines.
- Internet connection for the dependencies (and for updates from GitHub).

### Installation

From the folder where the archive is located:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Creates the virtual environment `.venv` (an incomplete `.venv` is set aside and recreated).
2. Installs omega-lib (the suite's library, shipped in the archive) and omega-connect.
3. Makes `omega-connect.sh` and `install.sh` executable.
4. Adds the `connect` alias to `~/.bashrc` and `~/.zshrc` (without duplicates).

No step requires administrator privileges.

### Update

From the folder that CONTAINS `omega-connect/` (never from inside it: `tar` would create a nested folder), extract the new archive over it, then run `install.sh` again. The archive contains no local data (`var/`: machine registry, settings, exports): nothing that exists is overwritten.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Usage

### Interactive mode (TUI)

```bash
./omega-connect.sh
```

or, if the alias was created, `connect`.

The main menu has two columns:

| Management | Maintenance |
|---|---|
| **Registry** — all the applications of all the machines, their version and their state | **Repair** — the list of everything that is wrong, and you choose |
| **Scan** — this machine, and adding the network machines | **Report** — a complete document, to export |
| **Links** — what is linked or not, with its state | **Settings** — language, themes, folders, purge |
| **Synchronization** — link the applications, on all the machines | **Help** — each menu, what it does and the details |
| **Dashboard** — the overview | **Quit** |

Typical path: **Scan** (this machine, then your other machines, suggested from your Unison profiles, `~/.ssh/config` and `known_hosts`) → **Registry** (update or reinstall an old application) → **Synchronization** (check, then synchronize) → **Links** and **Dashboard** to see the result → **Repair** if a discrepancy remains.

Each action first displays its plan; nothing is run before you agree. For a network machine, the interface gives way to the terminal for the duration of the action: the machine asks for its password itself, once.

#### Keyboard shortcuts

| Key | Action |
|---|---|
| `↑` / `↓` | Move from one item to another |
| `Tab` / `Shift+Tab` | Move from one area of the screen to another |
| `Enter` / `Space` | Activate; check a row (Synchronization) |
| `Esc` | Go back to the previous screen |
| `a` | Help |
| `s` | Settings |
| `t` | Next theme |
| `r` | Redraw the screen |
| `q` | Quit (with confirmation) |
| `Ctrl+P` | Commands: theme, screenshot, quit |

### States

| Applications | Links |
|---|---|
| ● Linked — in the shared space, up to date | OK |
| ◐ Enrolled — has its identity card, not yet in the shared space | needs repair |
| ○ Detected — without an identity card | needs repair (blocking) |
| ▲ Needs repair — a discrepancy | missing — nothing to link |
| ◌ Old version — to be updated | not verifiable |
| ◇ Incomplete installation — to be reinstalled | |
| ✕ Unreachable — the machine no longer responds | |

### Interface languages

The interface is available in 17 languages: French, English, Spanish, Portuguese (Brazil), Italian, German, Dutch, Polish, Russian, Simplified Chinese, Vietnamese, Thai, Indonesian, Japanese, Korean, Hindi and Arabic. The choice is made in the Settings (“Langue / Language”) and applies after the interface restarts; the `OMEGA_CONNECT_LANG` variable (for example `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) forces a language for one session. On a Linux text console (TTY), languages with a non-Latin script are displayed in English for the session. The command line stays in French.

### Contact and support

Help (`a` key) offers a **Contact and support** screen: *Buy me a coffee* (the developer's PayPal page), *Contact support* (mail address and the site's contact form, shown in plain text), *Declare myself as a user (anonymous)* and *Check for updates*. The declaration is voluntary, off by default and sent only once: it is only used to count users and, if you wish, their continent or country (closed lists, never free text). It sends a randomly drawn key, the software name (`omega-connect`) and its version; never a name, machine name, address or setting. The IP address is not recorded in the declarations, but like any visit it goes through the security checks and the log of the receiving server. Withdraw at any time from the same screen. The update check only reads the list of published versions, and never without a click.

### Scriptable mode (CLI)

Any command triggers command-line mode:

```bash
# Applications of this machine, or of a network machine (SSH with your keys)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Link the applications of this machine, or of a network machine
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Update the too-old applications of a network machine (GitHub Release)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Repair: this machine, or a network machine
./omega-connect.sh reparer --machine moi@192.168.1.109

# State of each link, and complete report
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` shows the plan without running anything; `--oui` runs without asking; `--toutes-machines` goes through all the known machines, one by one.

## 4. Network machines

- **Connection:** SSH with your keys only; `~/.ssh/config` is respected (alias, port, user). A key protected by a passphrase must be loaded into the SSH agent.
- **First connection:** the fingerprint of the machine's key is shown before anything else; a key that has changed is rejected.
- **Scan:** a program is sent in memory, read-only; nothing is installed or written, no password is asked.
- **Action** (synchronize, repair, update): a temporary private folder receives the program and, where needed, the archives; it is deleted at the end. The administrator password is asked by the machine itself, once.
- **Identity:** a machine is recognized by the fingerprint of its system identifier, not by its address: reached through two networks, it remains a single machine.
- **Updates:** from each application's GitHub Release; the archive checksum is verified with `sha.txt` before anything is sent, then again on the machine. Each application is installed as described in the “Update” section of its README.

## 5. Identity card and shared space

- **Identity card:** when it is installed, each omega application writes a small file saying who it is (application, version, identifier, machine). Readable by everyone, never modifiable by other accounts.
- **Shared space:** `/var/lib/omega-synchro`, reserved for the `omega-synchro` group, where only the administrator writes. Omega-connect copies the identity cards and the description of each application there; the applications find each other there, even when omega-connect is not running.
- **Shared space registry:** everything omega-connect creates is recorded in it; a removal only undoes what is recorded there, and an unknown file is never deleted.

## 6. Security

- No elevation at launch: omega-connect runs under your account; sudo is asked action by action, with the command displayed beforehand.
- Fixes are made by the application that owns the file (omega-jail for what it places in fail2ban, omega-serv for the permissions of its `var/`, each application for its identity card).
- No application is launched if it might ask for a password without a terminal.
- The search never follows a symbolic link, never changes file system and ignores network mounts.
- Purging the export and screenshot folders refuses system folders, home folders and omega-connect's own folder.

## 7. Exports

- **Report**: overview of all the machines, precise list of what remains to be done, registry, network machines, links of each machine, shared space. Text, JSON or HTML page (theme of your choice).
- **Help**: exportable as an HTML page.
- **Screenshots**: `Ctrl+P` → “Screenshot” (SVG).
- Default folders: `var/exports/` and `var/screenshots/` in the omega-connect folder, changeable in the Settings.

## 8. Architecture

Clean Architecture, like the rest of the suite: `domain/` (pure rules), `application/` (use cases), `ports/`, `infrastructure/` (SSH, files, GitHub, clipboard), `interfaces/` (command line and Textual interface), `app/` (assembly). Dependencies always point inward, checked by `import-linter`. The contracts shared between applications (identity card, description, shared space) live in `omega-lib`.

## 9. Tests

```bash
source .venv/bin/activate
lint-imports        # checks the dependency rule
pytest -q
ruff check src tests
mypy src
```

The tests never touch the real `var/`, the network or sudo: fake SSH run locally, fake GitHub, temporary folders.

## 10. Out of scope

- Replacing fail2ban, omega-fire or omega-jail.
- Continuous monitoring (no permanent service).
- Installing an omega application for the first time on a network machine.
- Web dashboard.

## License

MIT — see [LICENSE](../../../LICENSE).

---

> Omega-connect — Find, link, repair.
> The omega applications talk to each other; omega-connect makes sure they can.
