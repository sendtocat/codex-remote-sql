# codex-remote-sql candidates v0.1.2

[English](README.md) / [取得・配置・試験・印刷の手順](docs/OFFLINE_START_JA.md)

SSH/Oracle共通化のための独立した候補部品です。MIT License。

Python標準ライブラリだけで動く設定validator、metadata inventory、CSV境界、
SQL変更証跡の検証器と、Windows PowerShell 5向けSQL証跡logger候補を含みます。
Oracle executor、SSH executor、承認・資格情報制御の完成品ではありません。
本パッケージの試験は架空データ・ローカルtempのみです。

Python:
    python3 -B -m unittest discover -s tests -p test_contracts.py -v
    python3 -B -m unittest discover -s tests -p test_delivery.py -v

配布側Linuxでは契約39件・受渡し8件PASS。職場での合否は別途記録してください。

Windows PowerShell 5:
    powershell.exe -NoLogo -NoProfile -NonInteractive -File tests/Test-CodexSqlEvidence.ps1

PS5 CSV境界試験はWSL2とWindowsの共有配置を仮定する実験用fixtureです。
Windows共有ドライブ上の配置からwslpathでWindows側のfixtureパスを導出します。
特定の職場ディレクトリには固定しません。Windows標準インストールのPS実行ファイルを前提とします。
実行制限をBypassへ変更しません。PS5実行試験はこの配布環境では未実施。

loggerは受け取ったSQL文字列を保存します。秘密情報除外の完成品ではありません。
実DB・業務SQLへの組込みと導入は追加設計・試験を必要とします。

評価中は本体を新規ディレクトリに置き、絶対パスで利用します。PATHやprofile変更、
既存projectへの組込みは不要です。myssh.shやOracle接続コマンドはまだ同梱されていません。
公開版に職場の要求正本、HANDOFF、接続情報、ログ、既存ソースは含めません。
付属の本文復元helperは別途受領した許可済みsnapshotのテキスト保存だけを行います。
GitHubのsource ZIPは添付せず、受領者が許可された公開ダウンロード経路で取得します。
不具合や改善は職場からuploadせず、許可された非秘密の印刷要約をもとに自宅側でPRを作成します。
