# -*- coding: utf-8 -*-
"""案件完了時にW5の記録を knowledge/制約カタログ.md へ集約し、作業中案件の指定を外す。

  python scripts/wf_archive.py [--case <dir>] [--force]

W0〜W4にerrorが残っている場合は既定では止める。--force で無視して集約する。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf  # noqa: E402
from wf_lint import lint_file  # noqa: E402

CATALOG_HEADER = (
    "# 制約カタログ\n\n"
    "案件完了後にW5で記録された「外した仮説」を集約したもの。\n"
    "設計書に残らない「なぜ」が理由つきで蓄積される。新規参画者の立ち上がり資料、引き継ぎ資料としてそのまま使う。\n\n"
    "| 日付 | 案件 | 立てた仮説 | 実際の理由 | 自分の想定とのズレ |\n"
    "|---|---|---|---|---|\n"
)


def extract_w5_rows(w5_text: str) -> list[str]:
    rows = [l for l in w5_text.splitlines() if l.strip().startswith("|")]
    data = [r for r in rows if not re.match(r"^\s*\|[\s\-|]+\|\s*$", r) and "立てた仮説" not in r]
    return [r for r in data if wf.PLACEHOLDER not in r and "YYYY-MM-DD" not in r]


def main() -> int:
    wf.force_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--case")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    case = wf.resolve_case(a.case)
    if case is None:
        print("作業中の案件がありません。")
        return 1

    if not a.force:
        errors = 0
        for n in range(5):
            f = wf.phase_file(case, n)
            if f:
                errors += sum(1 for lvl, _ in lint_file(f, case) if lvl == "error")
        if errors:
            print("W0〜W4に error が %d 件残っています。先に解消するか --force を付けてください。" % errors)
            return 1

    w5 = wf.phase_file(case, 5)
    rows = extract_w5_rows(w5.read_text(encoding="utf-8")) if w5 else []

    catalog = wf.repo_root() / "knowledge" / "制約カタログ.md"
    if not catalog.exists():
        catalog.write_text(CATALOG_HEADER, encoding="utf-8")
    if rows:
        with catalog.open("a", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        print("制約カタログに %d 件を追記しました: %s" % (len(rows), catalog))
    else:
        print("W5に記録済みの行が無かったため、カタログへの追記はありません。")

    meta = wf.case_meta(case)
    meta["phase"] = "完了"
    meta["完了日"] = date.today().isoformat()
    wf.save_meta(case, meta)

    marker = wf.cases_dir() / ".current"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == case.name:
        marker.unlink()
        print("作業中案件の指定を解除しました。")

    print("案件を完了扱いにしました: %s" % case.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
