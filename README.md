<div align="center">

# Kotone

<img src="kotone.jpg" alt="Kotone" width="120" />

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![UI](https://img.shields.io/badge/UI-PySide6-41cd52)
![Status](https://img.shields.io/badge/status-unofficial-orange)

Yay! の非公式デスクトップクライアント（[yaylib](https://github.com/qvco/yaylib) 利用、PySide6 製）。

</div>

---

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## 環境変数

VC（音声通話）機能を使うには `KOTONE_AGORA_APP_ID` の設定が必要です。

`.env.example` を `.env` にコピーして値を設定し、シェル起動時に読み込む運用でも構いません（`.env` 自体はコミット対象外）。

値の由来は `kotone/core/agora_config.py` のコメントを参照してください。

### VCの既知の制限

Yay!の通話にはAgora経由のものと、agora_channel/agora_tokenが空で別サーバー
（プロトコル未解析）経由のものが混在しています。後者の通話に「参加する」
「VC」ボタンを押すと、参加を試みる代わりにエラーメッセージが表示されます
（`kotone/ui/call/call_dialog.py`の`is_agora_call`で判定）。

## 起動方法（動作確認）

セットアップ後、以下のいずれかで起動します。

```powershell
# コンソールスクリプトとして
kotone

# もしくはモジュールとして直接
python -m kotone.main
```

初回はログイン画面が表示されます。ログインに成功するとメールアドレスが保存され、
次回以降はセッション復元（パスワード不要）でメイン画面まで自動的に進みます。

自動テストは未整備です。変更を確認する際は上記コマンドでアプリを実際に起動し、
ログイン・タイムライン表示・チャットなど触る機能に応じて手動で確認してください。

## ログ

`%APPDATA%\Kotone\logs\kotone.log` にログを出力します（ローテーション付き、
最大1MB×3世代）。ソースから起動している場合はコンソールにも同じ内容が出ます。
未処理の例外も`sys.excepthook`経由でここに記録されるため、exe版（コンソール
非表示）で問題が起きた場合もこのファイルを確認してください。

ログレベルは環境変数 `KOTONE_LOG_LEVEL`（既定 `INFO`）で変更できます:

```powershell
$env:KOTONE_LOG_LEVEL = "DEBUG"
```

## exe ビルド

[PyInstaller](https://pyinstaller.org/) を使い、単一 exe（`Kotone.spec` 定義）としてビルドします。

```powershell
pip install pyinstaller
pyinstaller Kotone.spec
```

成功すると `dist/Kotone.exe` が生成されます。ビルド設定（アイコン・同梱アセット等）を
変更したい場合は `Kotone.spec` を編集してください。

## 既知の問題

- **プロフィールアイコン/カバー画像が保存後に「未設定」に戻る**: 保存直後は
  反映されるが、しばらくするとYay!側で消えることがある。クライアント側の
  リクエスト内容（ファイル名・拡張子・署名）は正規実装と一致しており、
  原因はYay!サーバー側の非同期モデレーション処理と推測されるが未解決（TODO）。

## 開発フロー

ブランチ運用・PRの出し方は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

