<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Interliga os aplicativos da suíte omega, em uma máquina e em toda a rede**

> Desenvolvido por [kraynux](https://github.com/kraynux) para [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Página oficial: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/pt-BR/) &nbsp; Prévia: [Capturas de tela](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interface disponível em **17 idiomas** — veja [Idiomas da interface](#idiomas-da-interface).  
**Idiomas:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** é o interconector da suíte `omega-`: ele encontra os aplicativos omega instalados (omega-serv, omega-fire, omega-jail…) nesta máquina e nas máquinas da sua rede, mostra o que está vinculado entre eles ou não, e restabelece o que falta — sempre mostrando antes o que vai fazer. Uma vez vinculados, os aplicativos se encontram entre si sem que o omega-connect esteja em execução.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-connect/D.png" width="24%" />
</p>

## 1. Visão e escopo

Os aplicativos omega são feitos para trabalhar juntos: os logs do omega-serv são lidos pelas jails do omega-jail, os banimentos do fail2ban chegam à lista negra do omega-serv, e o omega-fire exibe tudo isso. Mas ainda é preciso que os arquivos estejam no lugar certo, com as permissões certas, e que cada aplicativo saiba onde estão os outros. O Omega-connect cuida disso.

### O que o Omega-connect faz

- Encontra os aplicativos omega desta máquina (pasta pessoal, serviços systemd, OpenRC ou runit, `/srv`, registro das instâncias do omega-serv) e os das outras máquinas, acessadas por SSH com suas chaves.
- Mantém um **registro** de todos os aplicativos de todas as máquinas, com sua versão e seu estado.
- Verifica cada **vínculo** entre aplicativos (logs lidos pelas jails, ponte para a lista negra, lista protegida, arquivos do omega-jail no fail2ban, carteiras de identidade, espaço compartilhado) e diz o que não está bem.
- **Sincroniza**: cria as carteiras de identidade que faltam e prepara o **espaço compartilhado** onde os aplicativos se encontram entre si.
- **Repara**: faz cada divergência ser corrigida pelo aplicativo dono do arquivo; nunca o omega-connect no lugar dele.
- **Atualiza ou reinstala** um aplicativo antigo demais ou mal instalado de uma máquina da rede, a partir da sua Release no GitHub (hash verificado).
- Age sobre uma máquina da rede **a partir do seu computador**: nada a digitar lá, e a senha dela é pedida uma vez, pela própria máquina.
- Produz um **relatório** completo (texto, JSON ou página HTML).

### O que o Omega-connect não faz

- Ele não substitui nenhum aplicativo: fail2ban, omega-fire, omega-jail e omega-serv mantêm cada um o seu papel.
- Ele nunca reescreve o arquivo de outro aplicativo.
- Ele não instala nada permanente em uma máquina da rede para escaneá-la, e não deixa nenhum serviço em execução.
- Ele nunca pede a senha SSH, e nunca vê sua senha de administrador.

## 2. Instalação

### Pré-requisitos

- Linux, Python 3.10+.
- Para as máquinas da rede: acesso SSH por chave, e Python 3.10+ nessas máquinas.
- Conexão com a Internet para as dependências (e para as atualizações a partir do GitHub).

### Instalação

A partir da pasta onde está o arquivo compactado:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Cria o ambiente virtual `.venv` (um `.venv` incompleto é deixado de lado e recriado).
2. Instala o omega-lib (biblioteca da suíte, fornecida no arquivo compactado) e o omega-connect.
3. Torna `omega-connect.sh` e `install.sh` executáveis.
4. Adiciona o alias `connect` a `~/.bashrc` e `~/.zshrc` (sem duplicata).

Nenhuma etapa pede privilégio de administrador.

### Atualização

A partir da pasta que CONTÉM `omega-connect/` (nunca de dentro dela: o `tar` criaria uma pasta aninhada), extraia o novo arquivo compactado por cima e execute `install.sh` de novo. O arquivo compactado não contém nenhum dado local (`var/`: registro das máquinas, configurações, exportações): nada do que já existe é sobrescrito.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Uso

### Modo interativo (TUI)

```bash
./omega-connect.sh
```

ou, se o alias tiver sido criado, `connect`.

O menu principal tem duas colunas:

| Gerenciamento | Manutenção |
|---|---|
| **Registro** — todos os aplicativos de todas as máquinas, sua versão e seu estado | **Reparar** — a lista de tudo o que não está bem, e você escolhe |
| **Escanear** — esta máquina, e a adição das máquinas da rede | **Relatório** — um documento completo, para exportar |
| **Vínculos** — o que está vinculado ou não, com seu estado | **Configurações** — idioma, temas, pastas, limpeza |
| **Sincronização** — vincular os aplicativos, em todas as máquinas | **Ajuda** — cada menu, sua função e os detalhes |
| **Painel** — a visão geral | **Sair** |

Percurso típico: **Escanear** (esta máquina, depois suas outras máquinas, sugeridas a partir dos seus perfis Unison, de `~/.ssh/config` e de `known_hosts`) → **Registro** (atualizar ou reinstalar um aplicativo antigo) → **Sincronização** (marcar, depois sincronizar) → **Vínculos** e **Painel** para ver o resultado → **Reparar** se ainda restar alguma divergência.

Cada ação mostra primeiro o seu plano; nada é executado antes da sua aprovação. Para uma máquina da rede, a interface cede lugar ao terminal durante a ação: a própria máquina pede a sua senha, uma vez.

#### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `↑` / `↓` | Passar de um elemento a outro |
| `Tab` / `Shift+Tab` | Passar de uma área da tela a outra |
| `Enter` / `Espaço` | Ativar; marcar uma linha (Sincronização) |
| `Esc` | Voltar à tela anterior |
| `a` | Ajuda |
| `s` | Configurações |
| `t` | Próximo tema |
| `r` | Redesenhar a tela |
| `q` | Sair (com confirmação) |
| `Ctrl+P` | Comandos: tema, captura de tela, sair |

### Estados

| Aplicativos | Vínculos |
|---|---|
| ● Vinculada — no espaço compartilhado, atualizada | OK |
| ◐ Inscrita — tem sua carteira de identidade, ainda não está no espaço compartilhado | a reparar |
| ○ Detectada — sem carteira de identidade | a reparar (bloqueante) |
| ▲ A reparar — uma divergência | ausente — nada a vincular |
| ◌ Versão antiga — a atualizar | não verificável |
| ◇ Instalação incompleta — a reinstalar | |
| ✕ Inacessível — a máquina não responde mais | |

### Idiomas da interface

A interface está disponível em 17 idiomas: francês, inglês, espanhol, português (Brasil), italiano, alemão, holandês, polonês, russo, chinês simplificado, vietnamita, tailandês, indonésio, japonês, coreano, hindi e árabe. A escolha é feita nas Configurações (« Langue / Language ») e vale após reiniciar a interface; a variável `OMEGA_CONNECT_LANG` (por exemplo `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) força um idioma durante uma sessão. Em um console de texto Linux (TTY), os idiomas com escrita não latina são exibidos em inglês durante a sessão. A linha de comando continua em francês.

### Contato e suporte

A ajuda (tecla `a`) oferece uma tela **Contato e suporte**: *Pagar um café* (página PayPal do desenvolvedor), *Contatar o suporte* (endereço de e-mail e formulário de contato do site, exibidos por extenso), *Declarar-me usuário (anônimo)* e *Verificar atualizações*. A declaração é voluntária, desativada por padrão e enviada uma única vez: serve apenas para contar os usuários e, se você quiser, o seu continente ou país (listas fechadas, nunca texto livre). Ela envia uma chave sorteada ao acaso, o nome do software (`omega-connect`) e sua versão; nunca nome, nome de máquina, endereço ou configuração. O endereço IP não é registrado nas declarações, mas passa, como qualquer visita, pelos controles de segurança e pelo log do servidor de recepção. Você pode se retirar a qualquer momento pela mesma tela. A verificação de atualizações lê apenas a lista das versões publicadas, e nunca sem um clique.

### Modo scriptável (CLI)

Qualquer comando ativa o modo linha de comando:

```bash
# Aplicativos desta máquina, ou de uma máquina da rede (SSH com suas chaves)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Vincular os aplicativos desta máquina, ou de uma máquina da rede
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Atualizar os aplicativos antigos demais de uma máquina da rede (Release no GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Reparar: esta máquina, ou uma máquina da rede
./omega-connect.sh reparer --machine moi@192.168.1.109

# Estado de cada vínculo, e relatório completo
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` mostra o plano sem executar nada; `--oui` executa sem fazer a pergunta; `--toutes-machines` encadeia todas as máquinas conhecidas, uma por uma.

## 4. Máquinas da rede

- **Conexão:** somente SSH com suas chaves; `~/.ssh/config` é respeitado (alias, porta, usuário). Uma chave protegida por senha (passphrase) precisa estar carregada no agente SSH.
- **Primeira conexão:** a impressão digital da chave da máquina é mostrada antes de tudo; uma chave que mudou é recusada.
- **Escaneamento:** um programa é enviado na memória, somente leitura; nada é instalado nem gravado, nenhuma senha é pedida.
- **Ação** (sincronizar, reparar, atualizar): uma pasta privada temporária recebe o programa e, se for o caso, os arquivos compactados; ela é apagada no fim. A senha de administrador é pedida pela própria máquina, uma vez.
- **Identidade:** uma máquina é reconhecida pelo hash do seu identificador de sistema, não pelo seu endereço: acessada por duas redes, ela continua sendo uma única máquina.
- **Atualizações:** a partir da Release no GitHub de cada aplicativo; o hash do arquivo compactado é verificado com `sha.txt` antes de qualquer envio, e de novo na máquina. Cada aplicativo é instalado como indica a seção « Atualização » do seu README.

## 5. Carteira de identidade e espaço compartilhado

- **Carteira de identidade:** na instalação, cada aplicativo omega grava um pequeno arquivo que diz quem ele é (aplicativo, versão, identificador, máquina). Legível por todos, nunca modificável pelas outras contas.
- **Espaço compartilhado:** `/var/lib/omega-synchro`, reservado ao grupo `omega-synchro`, onde só o administrador grava. O Omega-connect copia para ele as carteiras de identidade e a descrição de cada aplicativo; os aplicativos se encontram ali entre si, mesmo quando o omega-connect não está em execução.
- **Registro do espaço compartilhado:** tudo o que o omega-connect cria é inscrito nele; uma remoção só desfaz o que está inscrito ali, e um arquivo desconhecido nunca é apagado.

## 6. Segurança

- Nenhuma elevação na inicialização: o omega-connect roda na sua conta; o sudo é pedido ação por ação, com o comando exibido antes.
- As correções são feitas pelo aplicativo dono do arquivo (omega-jail para o que ele coloca no fail2ban, omega-serv para as permissões do seu `var/`, cada aplicativo para a sua carteira de identidade).
- Nenhum aplicativo é executado se houver risco de ele pedir uma senha sem terminal.
- A busca nunca segue um link simbólico, não muda de sistema de arquivos e ignora as montagens de rede.
- A limpeza das pastas de exportação e de capturas recusa as pastas do sistema, as pastas pessoais e a do omega-connect.

## 7. Exportações

- **Relatório**: balanço de todas as máquinas, lista precisa do que ainda falta fazer, registro, máquinas da rede, vínculos de cada máquina, espaço compartilhado. Texto, JSON ou página HTML (tema à escolha).
- **Ajuda**: exportável como página HTML.
- **Capturas de tela**: `Ctrl+P` → « Captura de tela » (SVG).
- Pastas padrão: `var/exports/` e `var/screenshots/` da pasta do omega-connect, modificáveis nas Configurações.

## 8. Arquitetura

Clean Architecture, como o resto da suíte: `domain/` (regras puras), `application/` (casos de uso), `ports/`, `infrastructure/` (SSH, arquivos, GitHub, área de transferência), `interfaces/` (linha de comando e interface Textual), `app/` (montagem). As dependências sempre apontam para dentro, verificadas pelo `import-linter`. Os contratos compartilhados entre aplicativos (carteira de identidade, descrição, espaço compartilhado) ficam no `omega-lib`.

## 9. Testes

```bash
source .venv/bin/activate
lint-imports        # verifica a regra das dependências
pytest -q
ruff check src tests
mypy src
```

Os testes nunca tocam no `var/` real, nem na rede, nem no sudo: SSH falso executado localmente, GitHub falso, pastas temporárias.

## 10. Fora do escopo

- Substituir o fail2ban, o omega-fire ou o omega-jail.
- Monitorar continuamente (nenhum serviço permanente).
- Instalar um aplicativo omega pela primeira vez em uma máquina da rede.
- Painel web.

## Licença

MIT — veja [LICENSE](../../../LICENSE).

---

> Omega-connect — Encontrar, vincular, reparar.
> Os aplicativos omega conversam entre si; o omega-connect garante que eles possam.
