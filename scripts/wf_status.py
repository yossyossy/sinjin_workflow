# -*- coding: utf-8 -*-
"""作業中の案件の進捗を表示する。

  python scripts/wf_status.py
  python scripts/wf_status.py --case <dir>
  python scripts/wf_status.py --list        # 全案件を一覧
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf  # noqa: E402


def _print_case(case: Path) -> None:
    meta = wf.case_meta(case)
    print("案件: %s" % meta.get("案件", case.name))
    print("パス: %s" % case)
    if meta.get("期限"):
        print("期限: %s" % meta["期限"])
    print()
    for n in range(6):
        f = wf.phase_file(case, n)
        label = wf.PHASE_LABEL[n]
        if f is None:
            print("  [ ] %s（未作成）" % label)
            continue
        filled = wf.file_filled(f)
        mark = "x" if filled else " "
        print("  [%s] %s" % (mark, label))


def main() -> int:
    wf.force_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--case")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        cur = wf.current_case()
        for d in sorted(wf.cases_dir().iterdir()):
            if not d.is_dir():
                continue
            meta = wf.case_meta(d)
            mark = "*" if cur and d.resolve() == cur.resolve() else " "
            print("%s %s  (%s)" % (mark, d.name, meta.get("案件", "")))
        return 0

    case = wf.resolve_case(a.case)
    if case is None:
        print("作業中の案件がありません。`python scripts/wf_new.py <案件名>` で作成してください。")
        return 1
    _print_case(case)
    return 0


if __name__ == "__main__":
    sys.exit(main())
