# -*- coding: utf-8 -*-
"""案件ディレクトリを作り、W0〜W5のテンプレを配置する。

  python scripts/wf_new.py "Playbook構成の見直し" [--due 2026-09-10] [--from <指示文ファイル>]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf  # noqa: E402

UNSAFE = re.compile(r'[\\/:*?"<>|\s]+')


def slug(name):
    return UNSAFE.sub("-", name.strip()).strip("-")[:60]


def main():
    wf.force_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="案件名")
    ap.add_argument("--due", default="", help="期限 YYYY-MM-DD")
    ap.add_argument("--owner", default="", help="担当")
    ap.add_argument("--from", dest="src", default="", help="指示文（メール/チケット/議事録）のファイル")
    a = ap.parse_args()

    root = wf.repo_root()
    case = wf.cases_dir() / ("%s_%s" % (date.today().isoformat(), slug(a.name)))
    if case.exists():
        print("既に存在します: %s" % case)
        return 1
    case.mkdir(parents=True)

    for t in sorted((root / "templates").glob("W*.md")):
        shutil.copy2(t, case / t.name)

    if a.src:
        src = Path(a.src)
        if not src.exists():
            print("指示文が見つかりません: %s" % src)
            return 1
        (case / "指示文.md").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        (case / "指示文.md").write_text(
            "<!-- 受け取った指示（メール・チケット・議事録）を原文のまま貼る。\n"
            "     W0の転記チェックはこの原文との一致で判定する。 -->\n",
            encoding="utf-8",
        )

    wf.save_meta(case, {
        "案件": a.name,
        "作成日": date.today().isoformat(),
        "期限": a.due,
        "担当": a.owner,
        "phase": "W0",
        "資料の所在": [],
    })
    (wf.cases_dir() / ".current").write_text(case.name, encoding="utf-8")

    print("案件を作成し、作業中に設定しました: cases/%s" % case.name)
    print("")
    print("  1. 指示文.md に受け取った指示を原文のまま貼る")
    print("  2. /w0 で要件と不明点を洗い出す（AIは要件を補完しない）")
    print("")
    print("※ W1_先出し.md はAIの書き込みが拒否される。自分の手で書くこと。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
