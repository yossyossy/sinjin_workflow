# -*- coding: utf-8 -*-
"""wf_hook / gate_write の回帰。python scripts/test_wf_hook.py"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf_hook  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / ".claude" / "hooks" / "gate_write.py"
LINT_HOOK = ROOT / ".claude" / "hooks" / "lint_after_write.py"


def _run_hook(script: Path, payload: dict) -> subprocess.CompletedProcess:
    env = dict(__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        capture_output=True,
        check=False,
        env=env,
    )


def test_extract_copilot_create_file():
    paths = wf_hook.iter_paths({"filePath": "cases/x/W1_先出し.md", "content": "x"})
    assert paths == ["cases/x/W1_先出し.md"]
    assert wf_hook.is_write_tool("create_file")


def test_extract_copilot_editfiles():
    paths = wf_hook.iter_paths({"files": ["cases/x/W2_並べる.md", {"path": "cases/x/W3_仕分け.md"}]})
    assert "cases/x/W2_並べる.md" in paths
    assert "cases/x/W3_仕分け.md" in paths
    assert wf_hook.is_write_tool("editFiles")


def test_extract_copilot_multi_replace():
    paths = wf_hook.iter_paths({
        "replacements": [
            {"filePath": "cases/a/W0_受領と復元.md", "oldString": "a", "newString": "b"},
        ]
    })
    assert paths == ["cases/a/W0_受領と復元.md"]
    assert wf_hook.is_write_tool("multi_replace_string_in_file")


def test_extract_claude_write():
    paths = wf_hook.iter_paths({"file_path": "cases/x/W1_先出し.md"})
    assert paths == ["cases/x/W1_先出し.md"]
    assert wf_hook.is_write_tool("Write")
    assert wf_hook.is_shell_tool("run_in_terminal")


def test_gate_denies_copilot_w1_write():
    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp) / "case"
        case.mkdir()
        w1 = case / "W1_先出し.md"
        w1.write_text("dummy", encoding="utf-8")
        proc = _run_hook(GATE, {
            "tool_name": "create_file",
            "tool_input": {"filePath": str(w1), "content": "no"},
        })
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "W1" in data["hookSpecificOutput"]["permissionDecisionReason"]


def test_gate_allows_read_and_non_case():
    proc = _run_hook(GATE, {
        "tool_name": "read_file",
        "tool_input": {"filePath": "templates/W1_先出し.md"},
    })
    assert proc.returncode == 0, proc.stderr
    assert not (proc.stdout or "").strip()


def test_gate_blocks_w2_if_w1_empty():
    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp) / "case"
        case.mkdir()
        (case / "W1_先出し.md").write_text("（ここに書く）\n", encoding="utf-8")
        w2 = case / "W2_並べる.md"
        w2.write_text("x", encoding="utf-8")
        proc = _run_hook(GATE, {
            "tool_name": "replace_string_in_file",
            "tool_input": {"filePath": str(w2), "oldString": "x", "newString": "y"},
        })
        data = json.loads(proc.stdout)
        assert data["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "W1" in data["hookSpecificOutput"]["permissionDecisionReason"]


def test_lint_hook_copilot_payload():
    sample = ROOT / "templates" / "W0_受領と復元.md"
    proc = _run_hook(LINT_HOOK, {
        "tool_name": "editFiles",
        "tool_input": {"files": [str(sample)]},
    })
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert "[wf_lint]" in ctx
    assert "W0" in ctx or "受領" in ctx


def main() -> int:
    tests = [
        test_extract_copilot_create_file,
        test_extract_copilot_editfiles,
        test_extract_copilot_multi_replace,
        test_extract_claude_write,
        test_gate_denies_copilot_w1_write,
        test_gate_allows_read_and_non_case,
        test_gate_blocks_w2_if_w1_empty,
        test_lint_hook_copilot_payload,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("ok  %s" % fn.__name__)
        except Exception as e:
            failed += 1
            print("NG  %s: %s" % (fn.__name__, e))
    print("%d/%d passed" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
