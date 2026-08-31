# -*- coding: utf-8 -*-
"""Hook 入力の正規化。Claude Code と GitHub Copilot のツール名／ペイロード差を吸収する。"""
from __future__ import annotations

import re
from typing import Any, Iterable

# Copilot の公式例は editFiles。実ツールは create_file / replace_string_in_file 等。
WRITE_TOOLS = {
    "write",
    "edit",
    "notebookedit",
    "editfiles",
    "create_file",
    "replace_string_in_file",
    "multi_replace_string_in_file",
    "edit_notebook_file",
    "create_new_jupyter_notebook",
    "applypatch",
    "apply_patch",
}
SHELL_TOOLS = {
    "bash",
    "powershell",
    "run_in_terminal",
    "shell",
    "terminal",
}
PATH_KEYS = {
    "file_path",
    "filepath",
    "path",
    "target_file",
    "targetfile",
    "file",
}
FILE_MENTION = re.compile(r"(W[0-5]_[^\s\"'>|]*\.md)")


def tool_name_of(data: dict) -> str:
    return str(data.get("tool_name") or data.get("toolName") or "")


def tool_input_of(data: dict) -> dict:
    raw = data.get("tool_input")
    if raw is None:
        raw = data.get("toolInput")
    return raw if isinstance(raw, dict) else {}


def normalize_tool(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def is_write_tool(name: str) -> bool:
    return normalize_tool(name) in WRITE_TOOLS


def is_shell_tool(name: str) -> bool:
    return normalize_tool(name) in SHELL_TOOLS


def _as_str_paths(value: Any) -> Iterable[str]:
    if isinstance(value, str) and value.strip():
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            key = str(k).lower().replace("-", "")
            if key in PATH_KEYS or key == "files":
                yield from _as_str_paths(v)
            elif isinstance(v, (dict, list)):
                yield from _as_str_paths(v)
    elif isinstance(value, list):
        for item in value:
            yield from _as_str_paths(item)


def iter_paths(tool_input: dict) -> list[str]:
    seen: list[str] = []
    for p in _as_str_paths(tool_input):
        if p not in seen:
            seen.append(p)
    return seen


def iter_commands(tool_input: dict) -> list[str]:
    out: list[str] = []
    for key in ("command", "cmd", "script"):
        v = tool_input.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v)
    return out


def mentioned_phase_files(*texts: str) -> list[str]:
    seen: list[str] = []
    for text in texts:
        for m in FILE_MENTION.finditer(text or ""):
            name = m.group(1)
            if name not in seen:
                seen.append(name)
    return seen
