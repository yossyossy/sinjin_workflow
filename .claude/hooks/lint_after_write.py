# -*- coding: utf-8 -*-
"""PostToolUse hook: W0〜W5のファイルが書き換わったら即リンタを走らせ、結果をAIに返す。

ブロックはしない（PostToolUseはブロックできない）。error/warnをその場で本人へフィードバックし、
「後で気づく」を防ぐのが目的。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import wf  # noqa: E402
import wf_hook  # noqa: E402
from wf_lint import lint_file  # noqa: E402

wf.force_utf8()


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = wf_hook.tool_name_of(data)
    if not wf_hook.is_write_tool(tool_name):
        sys.exit(0)

    tool_input = wf_hook.tool_input_of(data)
    blocks = []
    for fp in wf_hook.iter_paths(tool_input):
        path = Path(fp)
        n = wf.phase_of(path)
        if n is None or not path.exists():
            continue
        case = path.parent if (path.parent / "case.json").exists() else None
        issues = lint_file(path, case)
        if not issues:
            blocks.append("[wf_lint] %s: OK" % path.name)
            continue
        lines = ["[wf_lint] %s の様式チェック結果（%d件）:" % (path.name, len(issues))]
        for level, msg in issues:
            tag = {"error": "NG", "warn": "！", "info": "・"}.get(level, "・")
            lines.append("  %s %s" % (tag, msg))
        errs = sum(1 for lv, _ in issues if lv == "error")
        if errs:
            lines.append("この工程を完了扱いにする前に、NGを解消してください。")
        blocks.append("\n".join(lines))

    if not blocks:
        sys.exit(0)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(blocks),
        }
    }, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
