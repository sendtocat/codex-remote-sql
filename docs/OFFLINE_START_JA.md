# オフライン初期評価: 取得からA4印刷まで

この文書は汎用のOSS取得手順です。職場固有の作業path・要求snapshot・Agent指示は
別途許可されたメール本文から受領してください。既存環境の配備手順ではありません。
添付、外部ログイン、外部編集、職場からのuploadを必要としません。

## 1. ダウンロードするもの

送信者が指定した40桁commitの **source ZIP** を公開GitHubから取得します。
形式は `https://github.com/sendtocat/codex-remote-sql/archive/<40桁commit>.zip` です。
これはGitHubのWebダウンロードであり、メール添付ではありません。
mainの「Code → Download ZIP」は更新で中身が変わるため、版を固定した試験では指定commitを使います。
Release asset、exe、VS Code拡張、Python/PowerShellの追加インストールは不要です。
職場でGitHubのログインを求められる、リダイレクト先が禁止される等の場合は取得未完了として停止します。

## 2. 展開と内容確認

新規のWindowsローカル共有ドライブ上の評価rootを人間が選びます。
例: `C:\OSS\codex-remote-sql-evaluation`。リンク/junction、ネットワーク共有、sync領域を避けます。
Windowsエクスプローラーの「すべて展開」で新規の受領フォルダに展開します。
ZIP内に最上位の `codex-remote-sql-<commit>` フォルダがあります。
その **中身** を、新規の評価root配下 `source` にコピーします。既存版へ上書きしません。
`source/README_JA.md`、`source/tools`、`source/tests` が直接見えることを確認します。
不用意にZIP内のプログラムをダブルクリックしません。人間が展開内容と使用するhelperを確認します。

WSLから、`source` に移動して `sha256sum PACKAGE_MANIFEST.json` を実行し、
別途受領した期待値と比較します。一致後、verifierの内容を確認して:

```sh
python3 -B tools/verify_package.py
```

`PACKAGE_FILES_VERIFIED` と件数を記録します。不一致は再取得/別版混入を確認し、進めません。
この検査はmanifestに載ったファイルの一致検査です。余分なファイルやOS隔離を保証しません。
新規ZIP由来の内容だけを使い、私的な設定・データを `source` に混ぜません。

## 3. メール本文の補足を保存

評価rootに `mail-inbox` を作り、各メール本文全体をVS CodeでUTF-8の `.txt` として保存します。
送信者の期待manifest本文は `mail-inbox/intake-manifest.json` に保存します。
固定のintakeパス・bytes・SHA-256・各part数がメールの一覧と合っていることを確認します。
`BEGIN RAW FILE`〜`END RAW FILE`の内容を加工せず、返信引用記号、手動折返しを加えません。
UTF-8 BOM/CRLFはhelperが正規化します。他の変化はハッシュ不一致で止まります。

評価rootをカレントディレクトリにして、各ファイルを個別に復元します。
複数partは同じコマンドに全partを指定します。送信者の具体的なコマンドを使用してください。

```sh
python3 -B source/tools/restore_mail.py --root . --expected mail-inbox/intake-manifest.json mail-inbox/同じファイルのpart1.txt mail-inbox/同じファイルのpart2.txt
```

helperは欠落/重複/混在/改変/許可外path/上書きを拒否します。失敗を無視して手作業で繋ぎません。
期待manifest自体の真正性はメール経路と人間の確認に依存します。復元は内容の実行ではありません。

## 4. VS Codeを開く

Windows版VS Codeの既存の許可済みWSL接続で評価rootだけを開きます。
WSL terminalで評価rootへ移動して `code -n .`、またはコマンドパレットの
「WSL: Connect to WSL」相当から「ファイル → フォルダーを開く」でWSL側pathを選びます。
既存のWSL拡張/VS Code serverが使えない場合は勝手に追加インストールせず未実施とします。
左下に `WSL: <distro>` があることを確認します。Remote-SSHでサーバーを開きません。
既存業務projectを複数rootワークスペースへ追加しません。
取得コードを人間が確認してから当該フォルダの信頼可否を判断します。

`intake/START_HERE.txt` を開き、そこにある初回promptをChatへ貼ります。
確認済みの社内モデル/Chat経路を使い、設定変更・外部ログインを必要としません。
最初は受領確認と計画。各コマンドを人間が確認して承認します。
toolが使えなければAgentは案のみ、人間が保存/実行します。

## 5. ローカル架空試験

WSL terminalのカレントディレクトリを `source` にします。

```sh
python3 --version
python3 -B -m unittest discover -s tests -p test_contracts.py -v
python3 -B -m unittest discover -s tests -p test_delivery.py -v
```

期待は各39件/8件PASS。runtime未導入はNOT_RUN、試験失敗はFAILです。
`python3 -m unittest discover`だけでは専用境界fixtureまでimportするため使いません。
Windows PowerShellを専用子processで確認します（WSL標準のCドライブmountを前提）:

```sh
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoLogo -NoProfile -NonInteractive -Command '$PSVersionTable.PSVersion.ToString(); [Environment]::Is64BitProcess'
```

Major=5を確認。exeの `v1.0` というディレクトリ名はPS言語版ではありません。
人間がsource内の試験・moduleを確認後、同じWSL terminalで:

```sh
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoLogo -NoProfile -NonInteractive -File "$(wslpath -w "$PWD/tests/Test-CodexSqlEvidence.ps1")"
python3 -B tests/test_ps5_csv_boundary.py
```

PSログmockは自作tempへ架空SQLを保存し、同じtempだけ削除します。
既定ログrootや業務ログrootへの書込み試験ではありません。
CSV境界は架空の日本語・カンマ・TAB・quote・改行を検査します。
PS5/interop/共有配置/実行許可がない場合はNOT_RUN。ExecutionPolicy Bypass、管理者起動、
別runtimeのインストールで回避しません。PS7の成功をPS5の成功に読み替えません。
各command終了直後の終了codeを `echo $?` で記録します。
失敗時のraw出力は職場内に保持し、モデルへ送信可能な抽象化した理由だけ渡します。

## 6. 既存資産の調査と次の判断

ローカル試験の後、私的START指示の範囲で人間が選んだrootのmetadata inventoryのみ実施します。
全drive/home/ネットワークを走査しません。既存helper実行、接続、設定変更を行いません。
SSH/Oracle接続・導入・本番切替へ進むには、具体的な対象/権限/負荷/証跡/停止/復旧計画が必要です。
PASSだけで業務利用可能としません。PS5未実施なら関連部分の評価を保留します。

## 7. 印刷

評価rootの新規session内に `reports/RETURN_REPORT_TEMPLATE.html` のコピーを保存します。
VS Codeでコピーの「ここへ非秘密の要約を記入」等を置換し、UTF-8で保存します。
HTMLは入力formではありません。`<`、`>`、`&`はそれぞれ `&lt;`、`&gt;`、`&amp;` とします。
匿名化した環境/受領版/試験/未確認/次の計画を書き、人間が持出し内容を確認します。
Windows側ブラウザでローカルのHTMLコピーを開き、Ctrl+P → A4 → 両面設定を確認。
「4枚程度」は4ページ以内を基準とし、印刷previewの総ページ数を確認します。
はみ出したら本文を短くし、詳細は職場内へ残します。余分なページを単に印刷範囲から外しません。
検証不能時もNOT_RUNと原因・次の入力を4ページ内に記録して印刷できます。
社外へ返す手段はこの許可済み紙だけです。メール返信/添付/外部upload/GitHub issueは使いません。

## 8. 不具合と更新

職場では修正案と必要な試験を職場内で検討し、社外に出せる抽象要約のみ紙で返します。
自宅側で汎用修正をbranch→試験→PR→レビュー→mainへmergeします。
次のメールは新しいcommit/manifest SHAを指定し、新規版フォルダへ再取得します。
職場固有のコード・設定は公開PRにしません。公開コードの上書きと既存配備の更新を同時に行いません。
