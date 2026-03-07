<div align="center">

![Zotero PDF2zh](./favicon@0.5x.svg)

<h2 id="title">Zotero PDF2zh</h2>

[![zotero target version](https://img.shields.io/badge/Zotero-8-blue?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/download/)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

Zoteroで[PDF2zh](https://github.com/Byaidu/PDFMathTranslate)と[PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)を使用してPDF翻訳を行う

バージョン v4.0.0 | [旧バージョン v2.4.3](./2.4.3%20version/README.md)

**📝 利用可能な言語:** [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Italiano](README.it.md) | [Français](README.fr.md)

> **注意:** この翻訳はAIによって生成されたものであり、不正確な情報が含まれている可能性があります。最も正確な情報については、[元の中国語版](README.md)を参照してください。

</div>


# プラグインの使用方法

このガイドでは、Zotero PDF2zhプラグインのインストールと設定について説明します。

❓ ヘルプが必要ですか？

- FAQへ移動: [よくある質問](#frequently-asked-questions-faq)
- 基本的な質問（Pythonのインストール方法など）はAIに質問してください
- GitHub Issuesで質問する
- QQグループに参加: 5群 1064435415（入群答え: github）

# インストールガイド

## ステップ0: PythonとZoteroをインストール

- [Pythonダウンロードリンク](https://www.python.org/downloads/) - バージョン3.12.0推奨

- プラグインは[Zotero 8](https://www.zotero.org/download/)をサポートしています

- ターミナル/cmdを開く（Windowsユーザーはcmd.exeを**管理者権限**で実行）

## ステップ1: uv/condaをインストール

**uvインストール（推奨）**

1. uvをインストール
```shell
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# またはpipを使用
pip install uv
```

2. uvインストールを確認
```shell
# uvバージョンが表示されればインストール完了
uv --version
```

**condaインストール**

1. condaをインストール: https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt

2. condaインストールを確認
```shell
conda --version
```

## ステップ2: プロジェクトファイルをダウンロード

```shell
# 1. zotero-pdf2zhフォルダを作成して移動
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. serverフォルダをダウンロードして展開
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. serverフォルダに入る
cd server
```

## ステップ3: 環境を準備して実行

このプロジェクトのPythonスクリプトは実行中に仮想環境を起動し、必要なパッケージをインストールし、pdf2zhとpdf2zh_nextの2つのエンジンの仮想環境を切り替えることができます。

仮想環境ツールを1つ選択してください：`uv`または`conda`

**1. uvを選択する場合（推奨）**

```shell
# uv runは自動的に仮想環境を作成し、必要な依存関係をインストールします
uv run --with flask --with toml --with pypdf --with pymupdf --with packaging server.py
```

**2. condaを選択する場合**

以下の手順で操作してください（**順番に実行**し、手順を飛ばさないでください）。

**手順1：メイン仮想環境を作成**（1回だけ実行）

```shell
# zotero-pdf2zh-server という名前のconda環境を作成
conda create -n zotero-pdf2zh-server python=3.12 -y
```

**手順2：環境をアクティベート**

```shell
conda activate zotero-pdf2zh-server
```

**手順3：依存関係をインストール**

```shell
pip install -r requirements.txt
```

**手順4：サービスを起動**

```shell
python server.py --env_tool=conda
```

::: danger 重要
翻訳機能はPythonスクリプトに依存しているため、**スクリプトを実行したままにする必要があります**。翻訳機能を使用している間は、**このPythonスクリプトウィンドウを閉じないでください**。スクリプトを閉じると翻訳機能が使用できなくなります。
:::

### デフォルト設定

**`python server.py`で起動時のデフォルトオプション：**
- 仮想環境管理：有効
- 環境ツール：自動検出（uv/conda）
- Pythonバージョン：3.12
- 自動インストール依存関係：有効
- 自動更新チェック：有効
- 更新ソース：gitee
- ポート番号：8890
- ミラーソース：中科大

### よく使うコマンドラインパラメータ

| パラメータ | 説明 | 使用方法 |
|-----------|-------------|----------|
| 基本起動 | デフォルト設定 | `python server.py` |
| `--port` | ポート番号を変更 | `python server.py --port=9999` |
| `--check_update` | 自動更新チェック | `python server.py --check_update=False` |
| `--update_source` | 更新ソース選択 | `python server.py --update_source="github"` |
| `--enable_mirror` | ミラー加速 | `python server.py --enable_mirror=False` |
| `--mirror_source` | カスタムミラーソース | `python server.py --mirror_source="URL"` |
| `--enable_winexe` | Windows exeモード | `python server.py --enable_winexe=True --winexe_path='PATH'` |

::: tip 注意
- update_source の選択肢：`github` / `gitee`（デフォルト）
- mirror_source デフォルト：中科大ミラー
:::

### 注意事項

- uv方式を使用する場合、インストール後にserverフォルダを移動したり名前を変更したりしないでください（仮想環境パスに影響します）。
- conda方式を使用する場合、仮想環境はcondaのenvsディレクトリに保存されるため、serverフォルダを安全に移動できます。
- 起動時の更新チェックが失敗した場合は、ネットワーク状況に応じて更新ソースを切り替えてください：`python server.py --update_source="gitee"` または `python server.py --update_source="github"`

## ステップ4: プラグインをダウンロードしてインストール

v4.0.0 [ダウンロード](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v4.0.0/zotero-pdf-2-zh.xpi)

Zoteroで「ツール→プラグイン」を開き、xpiファイルをドラッグしてインストールします。必要に応じてZoteroを再起動してください。

## ステップ5: Zoteroプラグイン設定

**設定オプション**

- `pdf2zh`/`pdf2zh_next`翻訳エンジンの切り替え

**翻訳エンジンの比較**

| 特徴 | PDF2ZH (旧版) | PDF2ZH Next (新版) |
|------|---------------|-------------------|
| **メンテナンス状態** | ❌ メンテナンス終了 | ✅ 継続的に更新中 |
| **翻訳速度** | ⚡ 高速 | やや遅い |
| **カスタムフォント** | ✅ カスタムフォント対応 | ❌ 非対応 |
| **設定ファイル** | `config.json` | `config.toml` |
| **デュアルレイアウト** | 基本的なデュアルレイアウトのみ | 左右/上下の複数モード対応 |
| **用語集機能** | ❌ 非対応 | ✅ 用語集の自動抽出・使用 |
| **表翻訳** | ❌ 非対応 | ✅ 表内テキスト翻訳対応 |
| **OCR互換性** | ❌ 非対応 | ✅ OCR互換モード・自動OCR対応 |
| **透かし削除** | ❌ 非対応 | ✅ 透かしなしモード対応 |
| **対応サービス** | 比較的少ない | より多くのサービス対応（無料 siliconflowfree 含む） |
| **上流プロジェクト** | [Byaidu/PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) | [PDFMathTranslate-next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) |

::: tip 推奨
カスタムフォントが必要であったり、最高速度を求める場合を除き、**PDF2ZH Next** エンジンの使用をお勧めします。
:::

- サービスプロバイダーに基づいて**qps**と**poolsize**を設定
- pdf2zhエンジンのカスタムフォント

**翻訳サービス**

| サービスタイプ | サービス名 | 説明 |
|--------------|--------------|-------------|
| 無料・設定不要 | siliconflowfree | SiliconFlowのGLM4-9Bモデル（pdf2zh_nextのみ） |
| 無料・設定不要 | bing/google | 公式機械翻訳 |
| 割引あり | openaliked | 火山エンジン協業プラン - 50万トークン/日 |
| 割引あり | silicon | 招待リワードあり |
| 高品質 | deepseek | 翻訳品質が良い、キャッシュメカニズムあり |
| 高品質 | aliyunDashScope | 良い結果、新規ユーザーボーナス |

## ステップ6: 翻訳オプション

Zoteroでエントリ/PDFを右クリックし、PDF2zh翻訳オプションを選択します。

オプション:
- **PDF翻訳**: 翻訳されたPDFを生成
- **PDFクロップ**: モバイル閲覧用にクロップして結合
- **PDF比較**: 元のテキストと翻訳を並べて表示
- **クロップ比較**: デュアルカラムPDF用

## ステップ7: パッケージ更新（新機能）

プラグインとサーバーは自動更新をサポートしています。手動更新の場合:

1. 仮想環境に入る
2. 実行: `pip install --upgrade pdf2zh_next babeldoc`

### ワンクリック起動スクリプト

利便性のため、ワンクリック起動を設定できます：

**Windowsユーザー - デスクトップショートカットスクリプトを作成：**

1. デスクトップに新しいテキストファイルを作成し、以下を入力：
```bat
@echo off
cd /d D:\zotero-pdf2zh\server
python server.py
pause
```

2. `start-pdf2zh.bat` にリネーム（拡張子は `.bat` である必要があります）

3. ダブルクリックで起動

**macOS / Linuxユーザー - エイリアス（alias）を設定：**

1. シェル設定ファイルを編集：
```shell
# zshを使用する場合（macOSデフォルト）
nano ~/.zshrc
# bashを使用する場合
nano ~/.bashrc
```

2. ファイルの末尾にエイリアスを追加（必要に応じてパスを変更）：
```shell
alias pdf2zh-start='cd /path/to/zotero-pdf2zh/server && python server.py'
```

3. 保存して実行：
```shell
source ~/.zshrc
# または
source ~/.bashrc
```

4. ターミナルで `pdf2zh-start` と入力するだけで起動できます

# よくある質問（FAQ）

### 仮想環境について

**Q: uv/condaのインストールに失敗しました。仮想環境をスキップできますか？**

A: 1つのエンジンのみを使用し、グローバルPythonが3.12.0の場合、仮想環境管理を無効にできます:
```shell
python server.py --enable_venv=False
```

### ネットワークについて

**Q: リソースの取得時にネットワークエラーが発生しました？**

A:
- プラグインがバージョン3.0.xであることを確認
- server.pyを実行したままにする
- ポート8890が占有されているか確認
- ポートを切り替えてみる
- ファイアウォールとアンチウイルスを確認

**Q: 翻訳が特定の場所で止まってしまいます？**

A: pdf2zh_nextは初回実行時にアセットをダウンロードします。これは遅いです。exeパッケージをダウンロードして一度実行してアセットをキャッシュできます。

### 環境について

**Q: DLL初期ルーチンが失敗しました？**

A:
- 仮想環境でonnxパッケージをバージョン`1.16.1`にダウングレード
- vs_redist.x86.exeをインストールしてみる
- macOSの古いバージョンの場合、Python 3.11を使用

### リモートサービスについて

**Q: API設定なしで使用できますか？**

A: siliconflowfreeやbing/googleなどの無料サービスのみがAPIなしで動作します。

**Q: トークンの消費が多すぎます？**

A: 10ページの論文は通常70〜100kトークンを消費します。pdf2zh_next設定で用語抽出を無効にしてみてください。

### プラグイン機能について

**Q: スキャン済みPDFが検出されました、翻訳に失敗しました？**

A: プラグインはOCRを提供しません。スキャン済みPDFは他のツールでOCR処理を行ってください。

### 質問について

**Q: 効果的にトラブルシューティングするには？**

A:
- ガイドを注意深く読む
- ターミナル出力をtxtにコピー
- Zotero設定のスクリーンショット
- これら3つをQQグループで共有: チェックした内容、試した方法、見たチュートリアル

# 謝辞

- @Byaidu [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)
- @awwaawwa [PDF2zh_next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)
- @windingwind [zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template)
- [Immersive Translate](https://immersivetranslate.com) Proメンバーシップの提供

# コントリビューター

すべてのコントリビューターに感謝します！

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors"> <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" /></a>

# サポート方法

💐 無料のオープンソースプラグイン、あなたのサポートが開発の原動力です！

- ☕️ [Buy me a coffee (WeChat/Alipay)](https://github.com/guaguastandup/guaguastandup)
- 🐳 [AiDian](https://afdian.com/a/guaguastandup)
- 🤖 [SiliconFlow招待リンク](https://cloud.siliconflow.cn/i/WLYnNanQ)

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=guaguastandup/zotero-pdf2zh&type=Date)](https://www.star-history.com/#guaguastandup/zotero-pdf2zh&Date)
