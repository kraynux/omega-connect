<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="512">
</div>

# 🔗 OMEGA-CONNECT

**omega スイートのアプリケーションを、1 台のマシン上でもネットワーク全体でも互いに連携させます**

> [kraynux](https://github.com/kraynux) が [Omega-Server](https://kraynux.snake-mackarel.ts.net) のために開発   

公式ページ：[OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/ja/) &nbsp; プレビュー：[スクリーンショット](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 インターフェースは **17 言語** に対応しています — [インターフェースの言語](#インターフェースの言語) を参照してください。  
**言語：**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** は `omega-` スイートのインターコネクターです。このマシンとネットワーク上のマシンにインストールされた omega アプリケーション（omega-serv、omega-fire、omega-jail…）を見つけ、何が互いに連携されていて何がされていないかを示し、足りないものを元に戻します。必ず、何をするかを先に見せてから行います。いったん連携されると、omega-connect が起動していなくても、アプリケーション同士が互いを見つけられます。

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-connect/D.png" width="24%" />
</p>

## 1. ビジョンと範囲

omega アプリケーションは一緒に動くように作られています：omega-serv のログは omega-jail の jail が読み、fail2ban の BAN は omega-serv のブラックリストに加わり、omega-fire はそれらすべてを表示します。ただしそのためには、ファイルが正しい場所に正しい権限で置かれ、各アプリケーションがほかのアプリケーションの場所を知っている必要があります。それを引き受けるのが Omega-connect です。

### Omega-connect ができること

- このマシンの omega アプリケーション（ホームフォルダー、systemd・OpenRC・runit のサービス、`/srv`、omega-serv のインスタンスのレジストリ）と、あなたの鍵を使って SSH で接続したほかのマシンのアプリケーションを見つけます。
- すべてのマシンのすべてのアプリケーションを、バージョンと状態とともに **レジストリ** に記録します。
- アプリケーション間の各 **連携**（jail が読むログ、ブラックリストへのブリッジ、保護リスト、fail2ban 内の omega-jail のファイル、ID カード、共有スペース）を確認し、何がうまくいっていないかを示します。
- **同期**：足りない ID カードを作成し、アプリケーション同士が互いを見つけられる **共有スペース** を用意します。
- **修復**：各不整合は、そのファイルを所有するアプリケーションに直させます。omega-connect が代わりに直すことは決してありません。
- ネットワーク上のマシンにある古すぎるアプリケーションや正しくインストールされていないアプリケーションを、その GitHub Release から **更新または再インストール** します（ハッシュを確認）。
- ネットワーク上のマシンに **あなたのマシンから** 作用します：向こうで入力するものは何もなく、パスワードはそのマシン自身が 1 回だけ尋ねます。
- 完全な **レポート** を作成します（テキスト、JSON、HTML ページ）。

### Omega-connect がしないこと

- どのアプリケーションの代わりもしません：fail2ban、omega-fire、omega-jail、omega-serv はそれぞれの役割を保ちます。
- ほかのアプリケーションのファイルを書き換えることは決してありません。
- ネットワーク上のマシンをスキャンするために常駐するものを何もインストールせず、サービスを動かしたままにもしません。
- SSH のパスワードを尋ねることは決してなく、あなたの管理者パスワードを見ることもありません。

## 2. インストール

### 前提条件

- Linux、Python 3.10+。
- ネットワーク上のマシンについて：鍵による SSH アクセスと、それらのマシン上の Python 3.10+。
- 依存関係のためのインターネット接続（GitHub からの更新にも必要）。

### インストール

アーカイブがあるフォルダーから：

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh` は：

1. 仮想環境 `.venv` を作成します（不完全な `.venv` は退避して作り直します）。
2. omega-lib（スイートのライブラリ、アーカイブに同梱）と omega-connect をインストールします。
3. `omega-connect.sh` と `install.sh` を実行可能にします。
4. エイリアス `connect` を `~/.bashrc` と `~/.zshrc` に追加します（重複なし）。

管理者権限を必要とする手順はありません。

### 更新

`omega-connect/` を含むフォルダーから（決してその中からではなく：`tar` が入れ子のフォルダーを作ってしまいます）、新しいアーカイブを上書きで展開し、`install.sh` を再実行します。アーカイブにはローカルデータ（`var/`：マシンのレジストリ、設定、エクスポート）が一切含まれないため、既存のものは何も上書きされません。

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. 使い方

### 対話モード（TUI）

```bash
./omega-connect.sh
```

または、エイリアスが作成されていれば `connect`。

メインメニューは 2 列です：

| 管理 | メンテナンス |
|---|---|
| **レジストリ** — すべてのマシンのすべてのアプリケーションと、そのバージョンと状態 | **修復** — 問題のあるものすべての一覧から選びます |
| **スキャン** — このマシンと、ネットワーク上のマシンの追加 | **レポート** — エクスポートできる完全な文書 |
| **連携** — 連携されているもの・いないものと、その状態 | **設定** — 言語、テーマ、フォルダー、削除 |
| **同期** — すべてのマシンでアプリケーションを連携 | **ヘルプ** — 各メニュー、その機能と詳細 |
| **ダッシュボード** — 全体像 | **終了** |

典型的な流れ：**スキャン**（このマシン、続いてほかのマシン。Unison プロファイル、`~/.ssh/config`、`known_hosts` から候補を表示）→ **レジストリ**（古いアプリケーションを更新または再インストール）→ **同期**（チェックを入れてから同期）→ **連携** と **ダッシュボード** で結果を確認 → 不整合が残っていれば **修復**。

各操作はまず計画を表示し、あなたが同意するまで何も実行しません。ネットワーク上のマシンでは、操作の間インターフェースが端末に場所を譲ります：パスワードはそのマシン自身が 1 回だけ尋ねます。

#### キーボードショートカット

| キー | 操作 |
|---|---|
| `↑` / `↓` | 要素間を移動 |
| `Tab` / `Shift+Tab` | 画面の領域間を移動 |
| `Enter` / `Space` | 実行。行のチェックを切り替え（同期） |
| `Esc` | 前の画面に戻る |
| `a` | ヘルプ |
| `s` | 設定 |
| `t` | 次のテーマ |
| `r` | 画面を再描画 |
| `q` | 終了（確認あり） |
| `Ctrl+P` | コマンド：テーマ、スクリーンショット、終了 |

### 状態

| アプリケーション | 連携 |
|---|---|
| ● 連携済み — 共有スペースにあり、最新 | OK |
| ◐ 登録済み — ID カードはあるが、まだ共有スペースにない | 要修復 |
| ○ 検出済み — ID カードがない | 要修復（重大） |
| ▲ 要修復 — 不整合がある | なし — 連携するものがない |
| ◌ 旧バージョン — 更新が必要 | 確認不可 |
| ◇ インストール未完了 — 再インストールが必要 | |
| ✕ 接続不可 — マシンが応答しない | |

### インターフェースの言語

インターフェースは 17 言語に対応しています：フランス語、英語、スペイン語、ポルトガル語（ブラジル）、イタリア語、ドイツ語、オランダ語、ポーランド語、ロシア語、中国語（簡体字）、ベトナム語、タイ語、インドネシア語、日本語、韓国語、ヒンディー語、アラビア語。設定（「Langue / Language」、このラベルは翻訳されません）で選び、インターフェースの再起動後に適用されます。変数 `OMEGA_CONNECT_LANG`（例：`OMEGA_CONNECT_LANG=en ./omega-connect.sh`）で、そのセッションの間だけ言語を固定できます。Linux のテキストコンソール（TTY）では、ラテン文字以外の言語はそのセッションでは英語で表示されます。コマンドラインはフランス語のままです。

### お問い合わせとサポート

ヘルプ（`a` キー）には **お問い合わせとサポート** 画面があります：*コーヒーをおごる*（開発者の PayPal ページ）、*サポートに連絡*（サイトのメールアドレスとお問い合わせフォームをそのまま表示）、*ユーザーとして登録（匿名）*、*更新を確認*。登録は任意で、初期状態ではオフになっており、送信は 1 回だけです：ユーザー数と、希望すれば大陸または国を数えるためだけに使われます（選択式の一覧のみで、自由記述はありません）。送信されるのはランダムに生成されたキー、ソフトウェア名（`omega-connect`）、そのバージョンだけで、名前、マシン名、アドレス、設定は決して送信されません。IP アドレスは登録情報には記録されませんが、どのアクセスとも同じく受信サーバーのセキュリティチェックとログを通過します。同じ画面からいつでも取り消せます。更新の確認は公開済みバージョンの一覧を読むだけで、クリックなしに行われることはありません。

### スクリプトモード（CLI）

コマンドを指定すると、コマンドラインモードになります：

```bash
# このマシン、またはネットワーク上のマシン（あなたの鍵を使った SSH）のアプリケーション
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# このマシン、またはネットワーク上のマシンのアプリケーションを連携
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# ネットワーク上のマシンの古すぎるアプリケーションを更新（GitHub Release）
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# 修復：このマシン、またはネットワーク上のマシン
./omega-connect.sh reparer --machine moi@192.168.1.109

# 各連携の状態と、完全なレポート
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` は何も実行せずに計画を表示します。`--oui` は確認なしで実行します。`--toutes-machines` は既知のすべてのマシンを 1 台ずつ順に処理します。

## 4. ネットワーク上のマシン

- **接続：** あなたの鍵だけを使った SSH。`~/.ssh/config` に従います（エイリアス、ポート、ユーザー）。パスフレーズで保護された鍵は SSH エージェントに読み込んでおく必要があります。
- **初回接続：** 何よりも先にマシンの鍵のフィンガープリントが表示されます。変更された鍵は拒否されます。
- **スキャン：** プログラムはメモリ上に送られ、読み取り専用で動きます。何もインストール・書き込みせず、パスワードも尋ねません。
- **操作**（同期、修復、更新）：一時的な非公開フォルダーがプログラムと、必要に応じてアーカイブを受け取り、最後に削除されます。管理者パスワードはそのマシン自身が 1 回だけ尋ねます。
- **識別：** マシンはアドレスではなく、システム識別子のフィンガープリントで認識されます。2 つのネットワークから接続しても、1 台のマシンのままです。
- **更新：** 各アプリケーションの GitHub Release から。アーカイブのハッシュは、送信前に `sha.txt` で確認し、マシン上でもう一度確認します。各アプリケーションは、その README の「更新」セクションのとおりにインストールされます。

## 5. ID カードと共有スペース

- **ID カード：** 各 omega アプリケーションはインストール時に、自分が何者かを示す小さなファイルを書き込みます（アプリケーション、バージョン、識別子、マシン）。誰でも読めますが、他のアカウントからは決して変更できません。
- **共有スペース：** `/var/lib/omega-synchro`。`omega-synchro` グループ専用で、書き込めるのは管理者だけです。Omega-connect は各アプリケーションの ID カードと説明をここにコピーします。omega-connect が起動していないときでも、アプリケーション同士がここで互いを見つけます。
- **共有スペースのレジストリ：** omega-connect が作成するものはすべてここに記録されます。削除で元に戻すのはここに記録されたものだけで、不明なファイルが削除されることは決してありません。

## 6. セキュリティ

- 起動時の権限昇格はありません：omega-connect はあなたのアカウントで動きます。sudo は操作ごとに求められ、コマンドは事前に表示されます。
- 修正はファイルを所有するアプリケーションが行います（fail2ban に置いたものは omega-jail、`var/` の権限は omega-serv、ID カードは各アプリケーション）。
- 端末なしでパスワードを求める可能性のあるアプリケーションは決して起動しません。
- 検索はシンボリックリンクを決してたどらず、ファイルシステムをまたがず、ネットワークマウントを無視します。
- エクスポートとスクリーンショットのフォルダーの削除は、システムフォルダー、個人フォルダー、omega-connect のフォルダーを拒否します。

## 7. エクスポート

- **レポート**：全マシンの概要、残っている作業の詳しい一覧、レジストリ、ネットワーク上のマシン、各マシンの連携、共有スペース。テキスト、JSON、HTML ページ（テーマを選択可能）。
- **ヘルプ**：HTML ページとしてエクスポート可能。
- **スクリーンショット**：`Ctrl+P` →「スクリーンショット」（SVG）。
- デフォルトのフォルダー：omega-connect のフォルダー内の `var/exports/` と `var/screenshots/`。設定で変更できます。

## 8. アーキテクチャ

スイートのほかのツールと同じクリーンアーキテクチャ：`domain/`（純粋なルール）、`application/`（ユースケース）、`ports/`、`infrastructure/`（SSH、ファイル、GitHub、クリップボード）、`interfaces/`（コマンドラインと Textual インターフェース）、`app/`（組み立て）。依存関係は常に内側に向かい、`import-linter` で確認されます。アプリケーション間で共有される契約（ID カード、説明、共有スペース）は `omega-lib` にあります。

## 9. テスト

```bash
source .venv/bin/activate
lint-imports        # 依存関係のルールを確認
pytest -q
ruff check src tests
mypy src
```

テストは本物の `var/`、ネットワーク、sudo には決して触れません：ローカルで実行する偽の SSH、偽の GitHub、一時フォルダーを使います。

## 10. 範囲外

- fail2ban、omega-fire、omega-jail の置き換え。
- 継続的な監視（常駐サービスなし）。
- ネットワーク上のマシンへの omega アプリケーションの初回インストール。
- Web のダッシュボード。

## ライセンス

MIT — [LICENSE](../../../LICENSE) を参照してください。

---

> Omega-connect — 見つける、連携する、修復する。
> omega アプリケーションは互いに通信します。omega-connect は、それができることを確かめます。
