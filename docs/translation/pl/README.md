<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Łączy ze sobą aplikacje pakietu omega, na jednej maszynie i w całej sieci**

> Stworzony przez [kraynux](https://github.com/kraynux) dla [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Strona oficjalna: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/pl/) &nbsp; Podgląd: [Zrzuty ekranu](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interfejs dostępny w **17 językach** — zobacz [Języki interfejsu](#języki-interfejsu).  
**Języki:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** to łącznik pakietu `omega-`: znajduje zainstalowane aplikacje omega (omega-serv, omega-fire, omega-jail…) na tej maszynie i na maszynach w twojej sieci, pokazuje, co jest między nimi połączone, a co nie, i przywraca to, czego brakuje — zawsze najpierw pokazując, co zamierza zrobić. Po połączeniu aplikacje odnajdują się nawzajem, nawet gdy omega-connect nie jest uruchomiony.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-connect/D.png" width="24%" />
</p>

## 1. Wizja i zakres

Aplikacje omega są stworzone do współpracy: logi omega-serv są czytane przez jaile omega-jail, bany fail2ban trafiają na czarną listę omega-serv, a omega-fire to wszystko wyświetla. Trzeba jednak, aby pliki były we właściwym miejscu, z właściwymi uprawnieniami, i aby każda aplikacja wiedziała, gdzie są pozostałe. Tym właśnie zajmuje się Omega-connect.

### Co robi Omega-connect

- Znajduje aplikacje omega na tej maszynie (katalog domowy, usługi systemd, OpenRC lub runit, `/srv`, rejestr instancji omega-serv) oraz na innych maszynach, osiąganych przez SSH z twoimi kluczami.
- Prowadzi **rejestr** wszystkich aplikacji ze wszystkich maszyn, z ich wersją i stanem.
- Sprawdza każde **powiązanie** między aplikacjami (logi czytane przez jaile, most do czarnej listy, lista chroniona, pliki omega-jail w fail2ban, karty identyfikacyjne, przestrzeń współdzielona) i mówi, co nie działa.
- **Synchronizuje**: tworzy brakujące karty identyfikacyjne i przygotowuje **przestrzeń współdzieloną**, w której aplikacje odnajdują się nawzajem.
- **Naprawia**: każdą niezgodność poprawia aplikacja, do której należy plik; nigdy omega-connect zamiast niej.
- **Aktualizuje lub instaluje ponownie** zbyt starą lub źle zainstalowaną aplikację na maszynie w sieci, z jej Release GitHub (suma kontrolna sprawdzona).
- Działa na maszynie w sieci **z twojego komputera**: nic nie trzeba tam wpisywać, jej hasło jest wymagane raz, przez nią samą.
- Tworzy pełny **raport** (tekst, JSON lub strona HTML).

### Czego Omega-connect nie robi

- Nie zastępuje żadnej aplikacji: fail2ban, omega-fire, omega-jail i omega-serv zachowują swoje role.
- Nigdy nie nadpisuje pliku innej aplikacji.
- Nie instaluje niczego na stałe na maszynie w sieci, aby ją przeskanować, i nie zostawia działającej usługi.
- Nigdy nie pyta o hasło SSH i nigdy nie widzi twojego hasła administratora.

## 2. Instalacja

### Wymagania

- Linux, Python 3.10+.
- Dla maszyn w sieci: dostęp SSH z kluczem oraz Python 3.10+ na tych maszynach.
- Połączenie z Internetem dla zależności (i dla aktualizacji z GitHub).

### Instalacja

Z katalogu, w którym znajduje się archiwum:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Tworzy środowisko wirtualne `.venv` (niekompletne `.venv` jest odkładane na bok i tworzone od nowa).
2. Instaluje omega-lib (bibliotekę pakietu, dostarczoną w archiwum) i omega-connect.
3. Nadaje `omega-connect.sh` i `install.sh` prawa wykonywania.
4. Dodaje alias `connect` do `~/.bashrc` i `~/.zshrc` (bez duplikatów).

Żaden krok nie wymaga uprawnień administratora.

### Aktualizacja

Z katalogu, który ZAWIERA `omega-connect/` (nigdy z jego wnętrza: `tar` utworzyłby zagnieżdżony katalog), rozpakuj nowe archiwum na istniejącą instalację, a potem ponownie uruchom `install.sh`. Archiwum nie zawiera żadnych danych lokalnych (`var/`: rejestr maszyn, ustawienia, eksporty): nic z tego, co istnieje, nie zostaje nadpisane.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Użycie

### Tryb interaktywny (TUI)

```bash
./omega-connect.sh
```

lub, jeśli alias został utworzony, `connect`.

Menu główne ma dwie kolumny:

| Zarządzanie | Utrzymanie |
|---|---|
| **Rejestr** — wszystkie aplikacje ze wszystkich maszyn, ich wersja i stan | **Napraw** — lista wszystkiego, co nie działa, z wyborem |
| **Skanuj** — ta maszyna i dodawanie maszyn w sieci | **Raport** — pełny dokument do eksportu |
| **Powiązania** — co jest połączone, a co nie, z jego stanem | **Ustawienia** — język, motywy, katalogi, czyszczenie |
| **Synchronizacja** — łączenie aplikacji na wszystkich maszynach | **Pomoc** — każde menu, jego funkcja i szczegóły |
| **Pulpit** — przegląd całości | **Wyjdź** |

Typowy przebieg: **Skanuj** (ta maszyna, potem twoje pozostałe maszyny, proponowane na podstawie twoich profili Unison, `~/.ssh/config` i `known_hosts`) → **Rejestr** (zaktualizuj lub zainstaluj ponownie starą aplikację) → **Synchronizacja** (zaznacz, a potem synchronizuj) → **Powiązania** i **Pulpit**, aby zobaczyć wynik → **Napraw**, jeśli pozostała niezgodność.

Każda akcja najpierw wyświetla swój plan; nic nie jest uruchamiane bez twojej zgody. W przypadku maszyny w sieci interfejs ustępuje miejsca terminalowi na czas akcji: maszyna sama prosi o swoje hasło, jeden raz.

#### Skróty klawiszowe

| Klawisz | Akcja |
|---|---|
| `↑` / `↓` | Przejście między elementami |
| `Tab` / `Shift+Tab` | Przejście między strefami ekranu |
| `Enter` / `Spacja` | Aktywacja; zaznaczenie wiersza (Synchronizacja) |
| `Esc` | Powrót do poprzedniego ekranu |
| `a` | Pomoc |
| `s` | Ustawienia |
| `t` | Następny motyw |
| `r` | Przerysowanie ekranu |
| `q` | Wyjście (z potwierdzeniem) |
| `Ctrl+P` | Paleta poleceń: motyw, zrzut ekranu, wyjście |

### Stany

| Aplikacje | Powiązania |
|---|---|
| ● Połączona — w przestrzeni współdzielonej, aktualna | OK |
| ◐ Zarejestrowana — ma kartę identyfikacyjną, jeszcze nie w przestrzeni współdzielonej | do naprawy |
| ○ Wykryta — bez karty identyfikacyjnej | do naprawy (blokujące) |
| ▲ Do naprawy — niezgodność | brak — nic do połączenia |
| ◌ Stara wersja — do zaktualizowania | nie do sprawdzenia |
| ◇ Niedokończona instalacja — do ponownej instalacji | |
| ✕ Nieosiągalna — maszyna przestała odpowiadać | |

### Języki interfejsu

Interfejs jest dostępny w 17 językach: francuskim, angielskim, hiszpańskim, portugalskim (Brazylia), włoskim, niemieckim, niderlandzkim, polskim, rosyjskim, chińskim uproszczonym, wietnamskim, tajskim, indonezyjskim, japońskim, koreańskim, hindi i arabskim. Wybór odbywa się w Ustawieniach (« Langue / Language ») i działa po ponownym uruchomieniu interfejsu; zmienna `OMEGA_CONNECT_LANG` (na przykład `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) wymusza język na czas jednej sesji. W tekstowej konsoli Linuksa (TTY) języki o piśmie niełacińskim są wyświetlane po angielsku na czas sesji. Wiersz poleceń pozostaje po francusku.

### Kontakt i wsparcie

Pomoc (klawisz `a`) zawiera ekran **Kontakt i wsparcie**: *Postaw kawę* (strona PayPal twórcy), *Skontaktuj się ze wsparciem* (adres e-mail i formularz kontaktowy strony, wyświetlone jawnie), *Zgłoś mnie jako użytkownika (anonimowo)* i *Sprawdź aktualizacje*. Zgłoszenie jest dobrowolne, domyślnie wyłączone i wysyłane tylko raz: służy wyłącznie do liczenia użytkowników i, jeśli chcesz, ich kontynentu lub kraju (zamknięte listy, nigdy dowolny tekst). Wysyła losowo wygenerowany klucz, nazwę programu (`omega-connect`) i jego wersję; nigdy imienia, nazwy maszyny, adresu ani ustawień. Adres IP nie jest zapisywany w zgłoszeniach, ale — jak każda wizyta — przechodzi przez kontrole bezpieczeństwa i log serwera odbierającego. Wycofanie w dowolnym momencie z tego samego ekranu. Sprawdzanie aktualizacji odczytuje jedynie listę opublikowanych wersji i nigdy bez kliknięcia.

### Tryb skryptowy (CLI)

Każde polecenie uruchamia tryb wiersza poleceń:

```bash
# Aplikacje tej maszyny lub maszyny w sieci (SSH z twoimi kluczami)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Połączenie aplikacji tej maszyny lub maszyny w sieci
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Aktualizacja zbyt starych aplikacji maszyny w sieci (Release GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Naprawa: ta maszyna lub maszyna w sieci
./omega-connect.sh reparer --machine moi@192.168.1.109

# Stan każdego powiązania i pełny raport
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` pokazuje plan bez uruchamiania czegokolwiek; `--oui` uruchamia bez zadawania pytania; `--toutes-machines` przetwarza wszystkie znane maszyny, jedną po drugiej.

## 4. Maszyny w sieci

- **Połączenie:** SSH wyłącznie z twoimi kluczami; `~/.ssh/config` jest respektowany (alias, port, użytkownik). Klucz chroniony hasłem musi być załadowany do agenta SSH.
- **Pierwsze połączenie:** najpierw pokazywany jest odcisk klucza maszyny; klucz, który się zmienił, jest odrzucany.
- **Skanowanie:** program jest wysyłany do pamięci, tylko do odczytu; nic nie jest instalowane ani zapisywane, nie jest wymagane żadne hasło.
- **Akcja** (synchronizacja, naprawa, aktualizacja): tymczasowy katalog prywatny otrzymuje program i, w razie potrzeby, archiwa; jest usuwany na końcu. Hasło administratora jest wymagane przez samą maszynę, jeden raz.
- **Tożsamość:** maszyna jest rozpoznawana po odcisku swojego identyfikatora systemowego, a nie po adresie: osiągana przez dwie sieci, pozostaje jedną maszyną.
- **Aktualizacje:** z Release GitHub każdej aplikacji; suma kontrolna archiwum jest sprawdzana z `sha.txt` przed jakąkolwiek wysyłką, a potem ponownie na maszynie. Każda aplikacja jest instalowana zgodnie z sekcją „Aktualizacja” swojego README.

## 5. Karta identyfikacyjna i przestrzeń współdzielona

- **Karta identyfikacyjna:** przy instalacji każda aplikacja omega zapisuje mały plik, który mówi, czym jest (aplikacja, wersja, identyfikator, maszyna). Czytelny dla wszystkich, nigdy niemodyfikowalny przez inne konta.
- **Przestrzeń współdzielona:** `/var/lib/omega-synchro`, zarezerwowana dla grupy `omega-synchro`, w której zapisuje tylko administrator. Omega-connect kopiuje tam karty identyfikacyjne i opis każdej aplikacji; aplikacje odnajdują się w niej nawzajem, nawet gdy omega-connect nie jest uruchomiony.
- **Rejestr przestrzeni współdzielonej:** wszystko, co tworzy omega-connect, jest w nim wpisywane; usunięcie cofa tylko to, co jest w nim wpisane, a nieznany plik nigdy nie jest usuwany.

## 6. Bezpieczeństwo

- Brak podniesienia uprawnień przy uruchomieniu: omega-connect działa na twoim koncie; sudo jest wymagane akcja po akcji, z poleceniem wyświetlonym wcześniej.
- Poprawki wykonuje aplikacja, do której należy plik (omega-jail dla tego, co umieszcza w fail2ban, omega-serv dla uprawnień swojego `var/`, każda aplikacja dla swojej karty identyfikacyjnej).
- Żadna aplikacja nie jest uruchamiana, jeśli mogłaby poprosić o hasło bez terminala.
- Wyszukiwanie nigdy nie podąża za dowiązaniem symbolicznym, nie zmienia systemu plików i pomija montowania sieciowe.
- Czyszczenie katalogów eksportów i zrzutów odmawia działania dla katalogów systemowych, domowych i katalogu samego omega-connect.

## 7. Eksporty

- **Raport**: podsumowanie wszystkich maszyn, dokładna lista tego, co pozostało do zrobienia, rejestr, maszyny w sieci, powiązania każdej maszyny, przestrzeń współdzielona. Tekst, JSON lub strona HTML (motyw do wyboru).
- **Pomoc**: możliwa do wyeksportowania jako strona HTML.
- **Zrzuty ekranu**: `Ctrl+P` → „Zrzut ekranu” (SVG).
- Katalogi domyślne: `var/exports/` i `var/screenshots/` w katalogu omega-connect, do zmiany w Ustawieniach.

## 8. Architektura

Clean Architecture, jak w reszcie pakietu: `domain/` (czyste reguły), `application/` (przypadki użycia), `ports/`, `infrastructure/` (SSH, pliki, GitHub, schowek), `interfaces/` (wiersz poleceń i interfejs Textual), `app/` (składanie całości). Zależności zawsze prowadzą do wewnątrz, co sprawdza `import-linter`. Kontrakty współdzielone między aplikacjami (karta identyfikacyjna, opis, przestrzeń współdzielona) znajdują się w `omega-lib`.

## 9. Testy

```bash
source .venv/bin/activate
lint-imports        # sprawdza regułę zależności
pytest -q
ruff check src tests
mypy src
```

Testy nigdy nie dotykają prawdziwego `var/`, sieci ani sudo: fałszywy SSH wykonywany lokalnie, fałszywy GitHub, katalogi tymczasowe.

## 10. Poza zakresem

- Zastępowanie fail2ban, omega-fire lub omega-jail.
- Ciągłe monitorowanie (brak stale działającej usługi).
- Pierwsza instalacja aplikacji omega na maszynie w sieci.
- Webowy panel kontrolny.

## Licencja

MIT — zobacz [LICENSE](../../../LICENSE).

---

> Omega-connect — Znaleźć, połączyć, naprawić.
> Aplikacje omega rozmawiają ze sobą; omega-connect dba o to, by mogły.
