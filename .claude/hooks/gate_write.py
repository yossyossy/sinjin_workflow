# -*- coding: utf-8 -*-
"""PreToolUse hook: W1の書き込みを常時拒否し、W2〜W5は前工程が未着手なら拒否する。

対象: Claude Code（Write/Edit/Bash/PowerShell）と GitHub Copilot
（create_file / replace_string_in_file / editFiles / run_in_terminal 等）。
本人がエディタで直接編集する分には関与しない。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import wf  # noqa: E402
import wf_hook  # noqa: E402

WRITE_INDICATOR = re.compile(
    r"(>>?[^>]|Set-Content|Out-File|Add-Content|\bcp\b|\bcopy\b|\bmv\b|\bmove\b|"
    r"open\([^)]*['\"]a?w['\"]|\.write\(|\bWrite-Output\b\s*\|.*Out-File)",
    re.IGNORECASE,
)


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def allow() -> None:
    sys.exit(0)


def check_phase_path(path_str: str) -> None:
    path = Path(path_str)
    n = wf.phase_of(path)
    if n is None:
        return
    if n == 1:
        deny(
            "W1_先出し.md への書き込みはハーネスにより拒否されます。"
            "先出しは本人が自分の手で書く工程です（AIが書くと以降の工程が全て空になります）。"
            "テンプレの説明や記入後のリンタ実行は行ってよいですが、本文はユーザー自身に書いてもらってください。"
        )
    if n == 0:
        return  # W0はいつでも編集可
    case = path.parent
    prev = wf.phase_file(case, n - 1)
    prev_label = wf.PHASE_LABEL[n - 1]
    if prev is None or not wf.file_filled(prev):
        deny(
            "%s（%s）はまだ着手されていません。順序を飛ばさず、先に前工程を終わらせてください。"
            % (prev.name if prev else "W%d_*.md" % (n - 1), prev_label)
        )


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()
        return

    tool_name = wf_hook.tool_name_of(data)
    tool_input = wf_hook.tool_input_of(data)

    if wf_hook.is_write_tool(tool_name):
        for fp in wf_hook.iter_paths(tool_input):
            check_phase_path(fp)
        allow()
        return

    if wf_hook.is_shell_tool(tool_name):
        for command in wf_hook.iter_commands(tool_input):
            if not WRITE_INDICATOR.search(command):
                continue
            for name in wf_hook.mentioned_phase_files(command):
                # コマンド中のパスは cwd 相対か絶対か分からないため、
                # cases/ 配下のどこかにある同名ファイルを総当たりで探す。
                for cand in wf.cases_dir().glob("*/%s" % name):
                    check_phase_path(str(cand))
        allow()
        return

    allow()


if __name__ == "__main__":
    main()
