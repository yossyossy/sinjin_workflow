# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: 作業中の案件と現在の工程をAIに常時知らせる。

案件が無いターンでは何も注入しない（案件遂行ワークフローと無関係な会話を汚さない）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import wf  # noqa: E402


def main() -> None:
    try:
        json.load(sys.stdin)
    except Exception:
        pass

    case = wf.current_case()
    if case is None:
        sys.exit(0)

    meta = wf.case_meta(case)
    lines = [
        "[案件遂行ワークフロー] 作業中の案件: %s (%s)" % (meta.get("案件", case.name), case.name),
    ]
    if meta.get("期限"):
        lines.append("期限: %s" % meta["期限"])
    states = []
    next_phase = None
    for n in range(6):
        f = wf.phase_file(case, n)
        filled = bool(f) and wf.file_filled(f)
        states.append("W%d:%s" % (n, "済" if filled else "未"))
        if not filled and next_phase is None:
            next_phase = n
    lines.append("進捗: " + " ".join(states))
    if next_phase is not None:
        lines.append(
            "次の工程は W%d。`/w%d` スキルを使うこと。W1は本人が書く工程でありAIによる書き込みは拒否される。"
            % (next_phase, next_phase)
        )
    else:
        lines.append("W0〜W5すべて記入済み。`python scripts/wf_archive.py` での完了処理を促してよい。")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(lines),
        }
    }, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
