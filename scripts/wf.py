# -*- coding: utf-8 -*-
"""案件遂行ワークフロー ハーネス共通モジュール。

工程ファイルは `W<n>_<和名>.md`。ゲート判定は ASCII の `W<n>_` 接頭辞のみに依存する
（和名部分は自由に変えてよい）。
"""
from __future__ import annotations

import io
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

PLACEHOLDER = "（ここに書く）"
PHASE_RE = re.compile(r"^W([0-5])_.*\.md$")
PHASE_LABEL = {
    0: "W0 受領と復元",
    1: "W1 先出し",
    2: "W2 並べる",
    3: "W3 仕分け",
    4: "W4 レビュー依頼",
    5: "W5 記録",
}


def force_utf8() -> None:
    for s in ("stdout", "stderr"):
        st = getattr(sys, s, None)
        if isinstance(st, io.TextIOWrapper):
            st.reconfigure(encoding="utf-8", errors="replace")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cases_dir() -> Path:
    return repo_root() / "cases"


def current_case() -> Path | None:
    """作業中の案件ディレクトリ。cases/.current が指す先。"""
    marker = cases_dir() / ".current"
    if marker.exists():
        name = marker.read_text(encoding="utf-8").strip()
        d = cases_dir() / name
        if d.is_dir():
            return d
    return None


def resolve_case(spec: str | None) -> Path | None:
    if not spec:
        return current_case()
    p = Path(spec)
    if p.is_dir():
        return p.resolve()
    d = cases_dir() / spec
    return d.resolve() if d.is_dir() else None


def phase_of(path: str | Path) -> int | None:
    """パスから工程番号を返す。工程ファイルでなければ None。"""
    m = PHASE_RE.match(Path(str(path)).name)
    return int(m.group(1)) if m else None


def phase_file(case: Path, n: int) -> Path | None:
    for p in sorted(case.glob(f"W{n}_*.md")):
        return p
    return None


def case_meta(case: Path) -> dict:
    f = case / "case.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_meta(case: Path, meta: dict) -> None:
    (case / "case.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --- 本文の解析 -----------------------------------------------------------

def strip_guidance(text: str) -> str:
    """引用（`>` で始まる解説行）と見出しを落として、本人が書いた本文だけ残す。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(">") or s.startswith("#") or s.startswith("---"):
            continue
        out.append(line)
    return "\n".join(out)


def sections(text: str) -> "dict[str, str]":
    """`## ■ 見出し` 単位で本文を切り出す（引用行は除去済み）。"""
    result: dict[str, str] = {}
    key = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+■\s*(.+?)\s*$", line)
        if m:
            if key is not None:
                result[key] = strip_guidance("\n".join(buf))
            key = m.group(1)
            buf = []
        elif key is not None:
            buf.append(line)
    if key is not None:
        result[key] = strip_guidance("\n".join(buf))
    return result


def body_lines(body: str) -> "list[str]":
    """箇条書き記号やチェックボックスを外した、意味のある行だけ。"""
    out = []
    for line in body.splitlines():
        s = re.sub(r"^\s*(?:[-*+]|\d+\.)\s*", "", line).strip()
        s = re.sub(r"^\[[ xX]\]\s*", "", s).strip()
        if s and s not in ("|", "---"):
            out.append(s)
    return out


def is_filled(body: str) -> bool:
    """記入済みと判定できるか。

    第一条件は「プレースホルダが1つも残っていないこと」。
    テンプレには表の見出しラベルや定型句（「現場の実績」「なぜ〜ではないのか」等）が
    あらかじめ埋め込まれており、それらの文字数だけで「記入済み」と誤判定しないよう、
    プレースホルダ残存を最優先で見る。
    """
    if PLACEHOLDER in body:
        return False
    txt = re.sub(r"[\s\-*+.|:／/（）()\[\]xX。、]", "", body)
    txt = re.sub(r"(高|中|低|YYYY|MM|DD|未|読んだ|資料なし)", "", txt)
    return len(txt) >= 8


def find_section(secs: "dict[str, str]", *keywords: str) -> "tuple[str, str] | None":
    for name, body in secs.items():
        if all(k in name for k in keywords):
            return name, body
    return None


def file_filled(path: Path, min_ratio: float = 0.5) -> bool:
    """工程ファイルが実質記入済みか（順序ゲートの判定に使う）。

    見出しの半分以上（既定）が埋まっていれば「着手済み」とみなす。
    完了判定（error 0件）はリンタの役目で、ここでは順序の粗いゲートのみ行う。
    """
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    secs = sections(text)
    if not secs:
        return is_filled(strip_guidance(text))
    filled = sum(1 for b in secs.values() if is_filled(b))
    return filled >= max(1, round(len(secs) * min_ratio))


# --- 転記検出 -------------------------------------------------------------

def _normalize(s: str) -> str:
    return re.sub(r"[\s\u3000]+", "", s)


def verbatim_runs(a: str, b: str, min_len: int = 15) -> "list[str]":
    """a と b の間で min_len 文字以上そのまま一致する断片。W0の転記検出に使う。"""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return []
    sm = SequenceMatcher(None, na, nb, autojunk=False)
    return [na[i : i + size] for i, _j, size in sm.get_matching_blocks() if size >= min_len]


def ngram_overlap(a: str, b: str, n: int = 3) -> float:
    """a の n-gram のうち b にも現れる割合。"""
    na, nb = _normalize(a), _normalize(b)
    if len(na) < n:
        return 0.0
    ga = {na[i : i + n] for i in range(len(na) - n + 1)}
    gb = {nb[i : i + n] for i in range(len(nb) - n + 1)}
    return len(ga & gb) / len(ga) if ga else 0.0
