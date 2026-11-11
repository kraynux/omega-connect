<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**omega 제품군의 애플리케이션을 한 머신에서도, 네트워크 전체에서도 서로 연결합니다**

> [kraynux](https://github.com/kraynux)가 [Omega-Server](https://kraynux.snake-mackarel.ts.net)를 위해 개발   

공식 페이지: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/ko/) &nbsp; 미리 보기: [스크린샷](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 인터페이스를 **17개 언어**로 제공합니다 — [인터페이스 언어](#인터페이스-언어)를 참고하세요.  
**언어:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect**는 `omega-` 제품군의 상호 연결 도구입니다: 이 머신과 네트워크의 머신들에 설치된 omega 애플리케이션(omega-serv, omega-fire, omega-jail…)을 찾고, 무엇이 서로 연결되어 있고 무엇이 아닌지 보여 주며, 빠진 것을 복구합니다. 항상 무엇을 할지 먼저 보여 준 다음에 작업합니다. 한번 연결되면 omega-connect가 실행되지 않아도 애플리케이션끼리 서로 찾을 수 있습니다.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-connect/D.png" width="24%" />
</p>

## 1. 비전과 범위

omega 애플리케이션은 함께 동작하도록 만들어졌습니다: omega-serv의 로그는 omega-jail의 jail이 읽고, fail2ban의 차단은 omega-serv의 블랙리스트에 합류하며, omega-fire는 이 모든 것을 보여 줍니다. 그러려면 파일이 올바른 위치에 올바른 권한으로 있어야 하고, 각 애플리케이션이 다른 애플리케이션의 위치를 알아야 합니다. 이를 맡는 것이 Omega-connect입니다.

### Omega-connect가 하는 일

- 이 머신의 omega 애플리케이션(개인 폴더, systemd, OpenRC 또는 runit 서비스, `/srv`, omega-serv 인스턴스 레지스트리)과, 사용자의 키로 SSH 접속한 다른 머신의 애플리케이션을 찾습니다.
- 모든 머신의 모든 애플리케이션을 버전, 상태와 함께 **레지스트리**에 기록합니다.
- 애플리케이션 사이의 각 **연결**(jail이 읽는 로그, 블랙리스트로 가는 브리지, 보호 목록, fail2ban 안의 omega-jail 파일, ID 카드, 공유 공간)을 확인하고 무엇이 잘못되었는지 알려 줍니다.
- **동기화**: 없는 ID 카드를 만들고, 애플리케이션끼리 서로 찾는 **공유 공간**을 준비합니다.
- **복구**: 각 불일치는 해당 파일을 소유한 애플리케이션이 고치게 합니다. omega-connect가 대신 고치는 일은 절대 없습니다.
- 네트워크 머신에서 너무 오래되었거나 잘못 설치된 애플리케이션을 그 GitHub Release에서 **업데이트하거나 재설치**합니다(해시 확인).
- 네트워크 머신에 **사용자의 컴퓨터에서** 작업합니다: 그곳에서 입력할 것은 없으며, 비밀번호는 그 머신이 직접 한 번만 묻습니다.
- 완전한 **보고서**(텍스트, JSON 또는 HTML 페이지)를 만듭니다.

### Omega-connect가 하지 않는 일

- 어떤 애플리케이션도 대신하지 않습니다: fail2ban, omega-fire, omega-jail, omega-serv는 각자의 역할을 유지합니다.
- 다른 애플리케이션의 파일을 절대 다시 쓰지 않습니다.
- 네트워크 머신을 스캔하려고 상주하는 것을 설치하지 않으며, 서비스를 계속 실행해 두지도 않습니다.
- SSH 비밀번호를 절대 묻지 않으며, 사용자의 관리자 비밀번호를 절대 보지 않습니다.

## 2. 설치

### 필요 조건

- Linux, Python 3.10+.
- 네트워크 머신의 경우: 키 기반 SSH 접속과 해당 머신의 Python 3.10+.
- 의존성 설치를 위한 인터넷 연결(GitHub에서 업데이트할 때도 필요).

### 설치

아카이브가 있는 폴더에서:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`는:

1. 가상 환경 `.venv`를 만듭니다(불완전한 `.venv`는 따로 보관하고 다시 만듭니다).
2. omega-lib(제품군 라이브러리, 아카이브에 포함)와 omega-connect를 설치합니다.
3. `omega-connect.sh`와 `install.sh`를 실행 가능하게 만듭니다.
4. 별칭 `connect`를 `~/.bashrc`와 `~/.zshrc`에 추가합니다(중복 없음).

관리자 권한이 필요한 단계는 없습니다.

### 업데이트

`omega-connect/`를 포함하는 폴더에서(절대 그 안에서가 아니라: `tar`가 중첩된 폴더를 만들게 됩니다) 새 아카이브를 덮어써서 압축을 푼 다음, `install.sh`를 다시 실행합니다. 아카이브에는 로컬 데이터(`var/`: 머신 레지스트리, 설정, 내보내기)가 전혀 없으므로 기존의 어떤 것도 덮어쓰지 않습니다.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. 사용법

### 대화형 모드(TUI)

```bash
./omega-connect.sh
```

또는 별칭이 만들어졌다면 `connect`.

메인 메뉴는 두 열입니다:

| 관리 | 유지 관리 |
|---|---|
| **레지스트리** — 모든 머신의 모든 애플리케이션과 그 버전, 상태 | **복구** — 문제가 있는 모든 것의 목록에서 고릅니다 |
| **스캔** — 이 머신, 그리고 네트워크 머신 추가 | **보고서** — 내보낼 수 있는 전체 문서 |
| **연결** — 연결된 것과 안 된 것, 그 상태 | **설정** — 언어, 테마, 폴더, 정리 |
| **동기화** — 모든 머신에서 애플리케이션 연결 | **도움말** — 각 메뉴, 그 기능과 세부 내용 |
| **대시보드** — 전체 보기 | **종료** |

일반적인 흐름: **스캔**(이 머신, 그다음 다른 머신들. Unison 프로필, `~/.ssh/config`, `known_hosts`를 바탕으로 제안) → **레지스트리**(오래된 애플리케이션 업데이트 또는 재설치) → **동기화**(선택한 다음 동기화) → **연결**과 **대시보드**에서 결과 확인 → 불일치가 남아 있으면 **복구**.

각 작업은 먼저 계획을 보여 주며, 사용자가 동의하기 전에는 아무것도 실행하지 않습니다. 네트워크 머신의 경우 작업하는 동안 인터페이스가 터미널에 자리를 내줍니다: 비밀번호는 그 머신이 직접 한 번만 묻습니다.

#### 키보드 단축키

| 키 | 동작 |
|---|---|
| `↑` / `↓` | 요소 간 이동 |
| `Tab` / `Shift+Tab` | 화면 영역 간 이동 |
| `Enter` / `Space` | 실행. 행 선택 또는 해제(동기화) |
| `Esc` | 이전 화면으로 돌아가기 |
| `a` | 도움말 |
| `s` | 설정 |
| `t` | 다음 테마 |
| `r` | 화면 다시 그리기 |
| `q` | 종료(확인 있음) |
| `Ctrl+P` | 명령: 테마, 스크린샷, 종료 |

### 상태

| 애플리케이션 | 연결 |
|---|---|
| ● 연결됨 — 공유 공간에 있으며 최신 상태 | OK |
| ◐ 등록됨 — ID 카드가 있지만 아직 공유 공간에 없음 | 복구 필요 |
| ○ 감지됨 — ID 카드가 없음 | 복구 필요 (차단) |
| ▲ 복구 필요 — 불일치 있음 | 없음 — 연결할 것이 없음 |
| ◌ 구버전 — 업데이트 필요 | 확인 불가 |
| ◇ 설치 미완료 — 재설치 필요 | |
| ✕ 응답 없음 — 머신이 더 이상 응답하지 않음 | |

### 인터페이스 언어

인터페이스는 17개 언어로 제공됩니다: 프랑스어, 영어, 스페인어, 포르투갈어(브라질), 이탈리아어, 독일어, 네덜란드어, 폴란드어, 러시아어, 중국어 간체, 베트남어, 태국어, 인도네시아어, 일본어, 한국어, 힌디어, 아랍어. 설정(「Langue / Language」, 이 레이블은 번역하지 않음)에서 고르며, 인터페이스를 다시 시작한 뒤 적용됩니다. 변수 `OMEGA_CONNECT_LANG`(예: `OMEGA_CONNECT_LANG=en ./omega-connect.sh`)은 한 세션 동안 언어를 강제로 지정합니다. Linux 텍스트 콘솔(TTY)에서는 라틴 문자가 아닌 언어가 해당 세션 동안 영어로 표시됩니다. 명령줄은 프랑스어로 유지됩니다.

### 문의 및 지원

도움말(`a` 키)에는 **문의 및 지원** 화면이 있습니다: *커피 한 잔 사기*(개발자의 PayPal 페이지), *지원팀에 문의*(사이트의 메일 주소와 문의 양식을 그대로 표시), *사용자로 등록(익명)*, *업데이트 확인*. 등록은 자발적이며 기본적으로 꺼져 있고 한 번만 보내집니다: 사용자 수와, 원하면 대륙 또는 국가를 세는 데만 쓰입니다(닫힌 목록, 자유 입력 없음). 무작위로 생성된 키, 소프트웨어 이름(`omega-connect`), 그 버전만 보내며, 이름, 머신 이름, 주소, 설정은 절대 보내지 않습니다. IP 주소는 등록 정보에 기록되지 않지만, 모든 방문과 마찬가지로 수신 서버의 보안 검사와 로그를 거칩니다. 같은 화면에서 언제든지 철회할 수 있습니다. 업데이트 확인은 게시된 버전 목록만 읽으며, 클릭 없이는 절대 실행되지 않습니다.

### 스크립트 모드(CLI)

명령을 지정하면 명령줄 모드로 실행됩니다:

```bash
# 이 머신 또는 네트워크 머신(사용자의 키로 SSH)의 애플리케이션
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# 이 머신 또는 네트워크 머신의 애플리케이션 연결
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# 네트워크 머신의 너무 오래된 애플리케이션 업데이트(GitHub Release)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# 복구: 이 머신 또는 네트워크 머신
./omega-connect.sh reparer --machine moi@192.168.1.109

# 각 연결의 상태와 전체 보고서
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation`은 아무것도 실행하지 않고 계획을 보여 줍니다. `--oui`는 묻지 않고 실행합니다. `--toutes-machines`는 알려진 모든 머신을 하나씩 차례로 처리합니다.

## 4. 네트워크 머신

- **연결:** 사용자의 키만 사용하는 SSH. `~/.ssh/config`를 따릅니다(별칭, 포트, 사용자). 암호로 보호된 키는 SSH 에이전트에 로드해야 합니다.
- **첫 연결:** 무엇보다 먼저 머신 키의 지문이 표시됩니다. 바뀐 키는 거부됩니다.
- **스캔:** 프로그램이 메모리로 보내져 읽기 전용으로 실행됩니다. 아무것도 설치하거나 쓰지 않으며, 비밀번호를 묻지 않습니다.
- **작업**(동기화, 복구, 업데이트): 임시 개인 폴더가 프로그램과 필요한 경우 아카이브를 받으며, 끝나면 지워집니다. 관리자 비밀번호는 그 머신이 직접 한 번만 묻습니다.
- **식별:** 머신은 주소가 아니라 시스템 식별자의 지문으로 인식됩니다. 두 네트워크로 접속해도 하나의 머신으로 남습니다.
- **업데이트:** 각 애플리케이션의 GitHub Release에서. 아카이브의 해시는 보내기 전에 `sha.txt`로 확인하고, 머신에서 다시 확인합니다. 각 애플리케이션은 그 README의 “업데이트” 절에 적힌 대로 설치됩니다.

## 5. ID 카드와 공유 공간

- **ID 카드:** 각 omega 애플리케이션은 설치할 때 자신이 누구인지 알려 주는 작은 파일(애플리케이션, 버전, 식별자, 머신)을 씁니다. 누구나 읽을 수 있지만 다른 계정은 절대 수정할 수 없습니다.
- **공유 공간:** `/var/lib/omega-synchro`. `omega-synchro` 그룹 전용이며 관리자만 씁니다. Omega-connect는 각 애플리케이션의 ID 카드와 설명을 여기에 복사합니다. omega-connect가 실행되지 않을 때에도 애플리케이션끼리 여기서 서로 찾습니다.
- **공유 공간 레지스트리:** omega-connect가 만드는 모든 것은 여기에 기록됩니다. 제거 작업은 여기에 기록된 것만 되돌리며, 알 수 없는 파일은 절대 삭제하지 않습니다.

## 6. 보안

- 실행할 때 권한 상승이 없습니다: omega-connect는 사용자의 계정으로 실행됩니다. sudo는 작업마다 요청되며, 명령이 먼저 표시됩니다.
- 수정은 파일을 소유한 애플리케이션이 합니다(fail2ban에 둔 것은 omega-jail, `var/`의 권한은 omega-serv, ID 카드는 각 애플리케이션).
- 터미널 없이 비밀번호를 물을 수 있는 애플리케이션은 절대 실행하지 않습니다.
- 검색은 심볼릭 링크를 절대 따라가지 않고, 파일 시스템을 넘나들지 않으며, 네트워크 마운트를 무시합니다.
- 내보내기 폴더와 스크린샷 폴더 정리는 시스템 폴더, 개인 폴더, omega-connect 폴더를 거부합니다.

## 7. 내보내기

- **보고서**: 모든 머신의 요약, 남은 할 일의 자세한 목록, 레지스트리, 네트워크 머신, 각 머신의 연결, 공유 공간. 텍스트, JSON 또는 HTML 페이지(테마 선택 가능).
- **도움말**: HTML 페이지로 내보낼 수 있습니다.
- **스크린샷**: `Ctrl+P` → “스크린샷”(SVG).
- 기본 폴더: omega-connect 폴더의 `var/exports/`와 `var/screenshots/`. 설정에서 바꿀 수 있습니다.

## 8. 아키텍처

제품군의 다른 도구와 같은 클린 아키텍처: `domain/`(순수 규칙), `application/`(유스케이스), `ports/`, `infrastructure/`(SSH, 파일, GitHub, 클립보드), `interfaces/`(명령줄과 Textual 인터페이스), `app/`(조립). 의존성은 항상 안쪽을 향하며 `import-linter`로 검증합니다. 애플리케이션 간에 공유되는 계약(ID 카드, 설명, 공유 공간)은 `omega-lib`에 있습니다.

## 9. 테스트

```bash
source .venv/bin/activate
lint-imports        # 의존성 규칙 확인
pytest -q
ruff check src tests
mypy src
```

테스트는 실제 `var/`, 네트워크, sudo를 절대 건드리지 않습니다: 로컬에서 실행되는 가짜 SSH, 가짜 GitHub, 임시 폴더를 씁니다.

## 10. 범위 밖

- fail2ban, omega-fire, omega-jail 대체.
- 지속적인 감시(상주 서비스 없음).
- 네트워크 머신에 omega 애플리케이션을 처음으로 설치하는 일.
- 웹 대시보드.

## 라이선스

MIT — [LICENSE](../../../LICENSE)를 참고하세요.

---

> Omega-connect — 찾고, 연결하고, 복구합니다.
> omega 애플리케이션은 서로 대화합니다. omega-connect는 그것이 가능한지 확인합니다.
