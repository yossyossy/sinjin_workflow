---
description: "Use when editing W0–W5 case files, 指示文.md, or running the sinjin workflow (/w0 /w1 /wf-new)."
applyTo: "cases/**/*.md"
---

# 工程ファイルを触るとき

- W1 はユーザーが手で書く。AIは書き込まない
- W2 の差分に良し悪しを書かない。AI由来は `[AI]`
- W3 の「確認済み」に `[AI]` を入れない。仮説は断定しない
- W4 は「〜と推測しましたが合っていますか」の形。手段そのものを聞かない
- 書き換えたら `python scripts/wf_lint.py --file <path>` を実行する
