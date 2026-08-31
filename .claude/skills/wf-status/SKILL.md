---
name: wf-status
description: 作業中の案件の進捗（W0〜W5の記入状況）を表示する。全案件の一覧表示にも使う。
user_invocable: true
model: inherit
---

# wf-status｜進捗確認

- 作業中の案件の状況：`python scripts/wf_status.py`
- 全案件の一覧：`python scripts/wf_status.py --list`（`*` が作業中の案件）

実行結果をそのままユーザーに見せる。加工しない。
