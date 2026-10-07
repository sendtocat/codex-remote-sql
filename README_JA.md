# codex-remote-sql candidates v0.1.1

SSH/Oracle共通化のための独立した候補部品です。MIT License。

Python標準ライブラリだけで動く設定validator、metadata inventory、CSV境界、
SQL変更証跡の検証器と、Windows PowerShell 5向けSQL証跡logger候補を含みます。
Oracle executor、SSH executor、承認・資格情報制御の完成品ではありません。
本パッケージの試験は架空データ・ローカルtempのみです。

Python:
    python3 -B -m unittest discover -s tests -p test_contracts.py -v

Windows PowerShell 5:
    powershell.exe -NoLogo -NoProfile -NonInteractive -File tests/Test-CodexSqlEvidence.ps1

PS5 CSV境界試験はWSL2とWindowsの共有配置を仮定する実験用fixtureです。
配置依存の定数があります。実行前に tests/test_ps5_csv_boundary.py を確認してください。
実行制限をBypassへ変更しません。PS5実行試験はこの配布環境では未実施。

loggerは受け取ったSQL文字列を保存します。秘密情報除外の完成品ではありません。
実DB・業務SQLへの組込みと導入は追加設計・試験を必要とします。
