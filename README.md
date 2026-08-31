# sinjin_workflow

[案件遂行ワークフロー（実務運用版）](言語化ワークフロー_実務組み込み版.md)を、Claude Code のハーネス（skills / hooks / リンタ）で実行するための仕組み。

手順書そのものは読み物として残しつつ、ここでは「AIに何をさせないか」を構造で担保する。

## 使い方

```
/wf-new     案件を立ち上げる（cases/ 配下に W0〜W5 のテンプレを配置）
/w0         受領と復元
/w1         先出し（AIは書かない・書けない）
/w2         並べる
/w3         仕分け
/w4         レビュー依頼
/w5         確定後の記録
/wf-status  進捗確認
```

CLIから直接実行する場合：

```
python scripts/wf_new.py "案件名" [--due YYYY-MM-DD] [--owner 担当] [--from 指示文ファイル]
python scripts/wf_lint.py [W0..W5] [--case cases/xxx] [--file path]
python scripts/wf_status.py [--list]
python scripts/wf_archive.py   # W5完了後、knowledge/制約カタログ.md に集約
```

## 構成

| パス | 役割 |
|---|---|
| `templates/W*.md` | 各工程のテンプレ本体 |
| `scripts/wf.py` | 共通ロジック（案件解決・記入判定・転記検出） |
| `scripts/wf_lint.py` | 様式チェック（AI非依存。単体で動く） |
| `scripts/wf_new.py` / `wf_status.py` / `wf_archive.py` | 案件のライフサイクル管理 |
| `.claude/skills/w0`〜`w5`, `wf-new`, `wf-status` | slash command 化 |
| `.claude/hooks/gate_write.py` | **W1への書き込みを常時拒否**。W2〜W5は前工程未着手なら拒否（順序ゲート） |
| `.claude/hooks/lint_after_write.py` | 書き込み直後に自動リンタを実行し、結果をAIへ返す |
| `.claude/hooks/inject_status.py` | 会話の各ターンに、作業中の案件と進捗を注入 |
| `cases/` | 案件データ（案件ごとに1ディレクトリ、`.current` が作業中案件） |
| `knowledge/制約カタログ.md` | W5の蓄積（完了案件から自動集約） |

## 設計の要点

- **W1の「AI不使用」は hook でハードブロックする。** 注意力ではなく構造で守る（手順書9章の × 項目）。
- **リンタはAI非依存。** 手順書11章「AIが使えない環境でも成立する」を満たすため、Python標準ライブラリのみで動く。
- **W3の「確認済み」への AI由来記述の混入**は `[AI]` マーカーとリンタで検出する。
- **W0の転記検出**は `指示文.md`（原文）との一致率で機械的に測る。
