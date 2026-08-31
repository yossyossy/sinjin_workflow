# -*- coding: utf-8 -*-
"""工程ファイルの様式チェック。AI非依存・単体で動く。

  python scripts/wf_lint.py                 # 作業中の案件を全工程チェック
  python scripts/wf_lint.py W3              # 工程を指定
  python scripts/wf_lint.py --case <dir>    # 案件を指定
  python scripts/wf_lint.py --file <path>   # ファイル単体
  python scripts/wf_lint.py --quiet         # error のみ出力
終了コード: error があれば 1
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf  # noqa: E402
from wf import PLACEHOLDER, body_lines, find_section, is_filled, sections, strip_guidance  # noqa: E402

Issue = tuple  # (level, message)

# 差分に良し悪しを付けていないか（W2）
JUDGEMENT = ["の方が良い", "のほうが良い", "が正しい", "が適切", "べきである", "べきだ",
             "望ましい", "が劣る", "は誤り", "は間違", "優れている", "改善すべき", "問題がある"]
# 仮説が断定になっていないか（W3）
HEDGE = ["推測", "可能性", "と思われ", "と考えられ", "かもしれ", "だろう", "ではないか",
         "見込み", "推定", "仮説", "らしい", "おそれ"]
# 手段を聞いていないか（W4）
ASKING_HOW = ["教えてください", "教えて下さい", "ご教示", "どうすればいい", "どうしたらいい",
              "どうすれば良い", "どのように作れば", "方針を決めてください"]
CONFIRMING = ["推測", "合っていますか", "合ってますか", "という理解で", "で合っている"]


def _sec(secs, *kw):
    return find_section(secs, *kw)


def _missing(kw):
    return "見出しが見つからない: " + "/".join(kw)


def lint_w0(text, case):
    out = []
    secs = sections(text)
    required = [
        (("求められている結果",), "error", "求められている結果が空。ここが空だと以降すべてが推測になる"),
        (("なぜ",), "warn", "背景が空。誰が困っているかが分からない"),
        (("守るべき制約",), "error", "制約が空。期限・影響範囲・変えてはいけないものを聞く"),
        (("完了の条件",), "error", "完了の条件が空。終わりが定義できていない"),
        (("自分で決める",), "error", "「自分で決める部分」が空。最重要項目。W1以降の対象範囲そのもの"),
        (("参考", "所在"), "warn", "資料の所在が空。存在するのに探せず作り直すのは純損失。必ず聞く"),
    ]
    for kw, level, msg in required:
        hit = _sec(secs, *kw)
        if hit is None:
            out.append(("warn", _missing(kw)))
        elif not is_filled(hit[1]):
            out.append((level, msg))

    unfilled = [n for n, b in secs.items() if not is_filled(b)]
    q = _sec(secs, "質問リスト")
    if q and not is_filled(q[1]) and unfilled:
        out.append(("warn", "書けなかった項目があるのに質問リストが空。書けなかった項目がそのまま質問になる"))

    ag = _sec(secs, "復唱")
    if ag and not is_filled(ag[1]):
        out.append(("warn", "復唱と合意が未記入。先輩の工数を最も減らすのがここ（1〜2分で済む）"))

    if case:
        inst = None
        for cand in ("指示文.md", "指示文.txt"):
            p = case / cand
            if p.exists():
                inst = p.read_text(encoding="utf-8")
                break
        if inst:
            own = strip_guidance(text).replace(PLACEHOLDER, "")
            runs = wf.verbatim_runs(own, inst, min_len=15)
            ratio = wf.ngram_overlap(own, inst, n=3)
            for r in runs[:5]:
                out.append(("error", "指示文からの転記の疑い（%d字そのまま一致）: 「%s」" % (len(r), r[:40])))
            if ratio >= 0.55 and not runs:
                out.append(("warn", "指示文との語句重複率 %.0f%%。指示文の語を使わずに書き直す" % (ratio * 100)))
            elif runs:
                out.append(("info", "指示文との語句重複率 %.0f%%" % (ratio * 100)))
        else:
            out.append(("info", "指示文.md が無いため転記チェックは省略"))
    return out


def lint_w1(text, case):
    out = []
    secs = sections(text)
    keep = _sec(secs, "踏襲する部分")
    chg = _sec(secs, "変える部分")
    for kw, level, msg in [
        (("自分ならこうする",), "error", "自分の案が空。ここが本体"),
        (("そう考えた理由",), "error", "理由が空。後から書くと結論に合わせた後付けになる"),
        (("採らなかった案",), "error", "採らなかった案が空。採用案だけでは判断の根拠を復元できない"),
        (("迷っている点",), "warn", "迷っている点が空。W2の比較対象を決める材料になる"),
    ]:
        hit = _sec(secs, *kw)
        if hit is None:
            out.append(("warn", _missing(kw)))
        elif not is_filled(hit[1]):
            out.append((level, msg))
    kf = bool(keep) and is_filled(keep[1])
    cf = bool(chg) and is_filled(chg[1])
    if not kf and not cf:
        out.append(("error", "踏襲する部分／変える部分がどちらも空"))
    elif not kf:
        out.append(("error", "「踏襲する部分」が空。踏襲は「変えない」という判断であり理由が要る。事故はここから出る"))
    elif not cf:
        out.append(("warn", "「変える部分」が空。無いなら「無い」と理由つきで書く"))
    return out


def lint_w2(text, case):
    out = []
    secs = sections(text)
    tgt = _sec(secs, "比較対象")
    if tgt:
        rows = [l for l in tgt[1].splitlines() if l.strip().startswith("|")]
        filled = [r for r in rows
                  if PLACEHOLDER not in r
                  and not re.match(r"^\s*\|[\s\-|]+\|\s*$", r)
                  and "種類" not in r]
        if len(filled) < 3:
            out.append(("error", "比較対象が %d 件。2つ（対比）だと優劣判断で終わる。3つ以上並べると外れ値が浮かぶ" % len(filled)))

    diff = _sec(secs, "差分")
    if diff:
        items = [l for l in body_lines(diff[1]) if PLACEHOLDER not in l]
        if not items:
            out.append(("error", "差分が空"))
        for line in items:
            for w in JUDGEMENT:
                if w in line:
                    out.append(("error", "差分に良し悪しの判定（「%s」）: 「%s」— 列挙のみ。判定した時点でこの工程は失敗" % (w, line[:40])))
                    break

    q = _sec(secs, "問い")
    if q:
        items = [l for l in body_lines(q[1]) if PLACEHOLDER not in l]
        if not items:
            out.append(("error", "問いへの変換が空"))
        for line in items:
            if not ("なぜ" in line and ("ではないのか" in line or "でないのか" in line)):
                out.append(("warn", "「なぜ X であって Y ではないのか」の形になっていない: 「%s」" % line[:40]))

    if "[AI]" not in text:
        out.append(("info", "AI由来の記述に [AI] 印が付いていない。W3で「確認済み」への混入を防げなくなる"))
    return out


def _hypotheses(text):
    """### 仮説N：... 単位で切り出す。"""
    out = []
    cur, buf = None, []
    for line in text.splitlines():
        m = re.match(r"^###\s+(仮説.*?)\s*$", line)
        if m:
            if cur:
                out.append((cur, "\n".join(buf)))
            cur, buf = m.group(1), []
        elif cur is not None:
            if re.match(r"^##\s", line):
                out.append((cur, "\n".join(buf)))
                cur, buf = None, []
            else:
                buf.append(line)
    if cur:
        out.append((cur, "\n".join(buf)))
    return out


def lint_w3(text, case):
    out = []
    secs = sections(text)

    conf = _sec(secs, "確認済み")
    if conf:
        lines = [l for l in body_lines(conf[1]) if PLACEHOLDER not in l]
        for line in lines:
            if "[AI]" in line:
                out.append(("error", "「確認済み」にAI由来の記述: 「%s」— 推測が事実に化ける。仮説か未解明に移す" % line[:40]))
        if not lines:
            out.append(("warn", "確認済みが空。W0で確認した要件もここに入る"))

    hyps = [(n, b) for n, b in _hypotheses(text) if is_filled(strip_guidance(b))]
    if not hyps:
        out.append(("warn", "仮説が1件も書かれていない"))
    for name, body in hyps:
        fields = {}
        for line in body.splitlines():
            m = re.match(r"^\s*[-*]\s*(内容|根拠|確度|反証条件|外れた場合に変わること|対抗仮説)\s*[:：]\s*(.*)$", line)
            if m:
                fields[m.group(1)] = m.group(2).strip()
        checks = [
            ("内容", "error", "内容が無い"),
            ("根拠", "error", "根拠が無い"),
            ("確度", "warn", "確度が無い"),
            ("反証条件", "error", "反証条件が無い。仮説の質は確認の安さで測れる"),
            ("外れた場合に変わること", "error", "外れた場合に変わることが無い。変わらないなら装飾なので落とす"),
            ("対抗仮説", "error", "対抗仮説が無い。1つしかないものは最初に思いついただけ"),
        ]
        for key, level, msg in checks:
            if key not in fields:
                out.append((level, "%s: %s（項目そのものが無い）" % (name, msg)))
                continue
            v = fields[key].replace(PLACEHOLDER, "").replace("高 / 中 / 低", "")
            v = re.sub(r"[\s、。]", "", v)
            if v in ("", "もし", "もしが事実ならこの仮説は成り立たない"):
                out.append((level, "%s: %s" % (name, msg)))
        content = fields.get("内容", "")
        if content and PLACEHOLDER not in content and not any(h in content for h in HEDGE):
            out.append(("warn", "%s: 断定で書かれている（「〜と推測する」「〜の可能性がある」の形にする）: 「%s」" % (name, content[:40])))

    unk = _sec(secs, "未解明")
    if unk:
        items = [l for l in body_lines(unk[1]) if PLACEHOLDER not in l]
        if not items:
            out.append(("warn", "未解明が0件。疑問が出てこなくなると、全部が推測のまま実装まで通る。W2に戻る"))
    return out


def lint_w4(text, case):
    out = []
    secs = sections(text)
    for kw, level, msg in [
        (("依頼内容の理解",), "error", "依頼内容の理解が空"),
        (("方針",), "error", "方針が空"),
        (("採らなかった案",), "error", "採らなかった案が空。後から判断の根拠を復元できなくなる"),
    ]:
        hit = _sec(secs, *kw)
        if hit and not is_filled(hit[1]):
            out.append((level, msg))

    q = _sec(secs, "確認したいこと")
    if q:
        items = [l for l in body_lines(q[1])
                 if PLACEHOLDER not in l and not l.startswith("（もし")]
        if not items:
            out.append(("error", "確認したいことが空。未解明が無いなら、W4に持ち込む必要がない"))
        for line in items:
            asked_how = next((w for w in ASKING_HOW if w in line), None)
            if asked_how:
                out.append(("error", "手段を聞いている（「%s」）: 「%s」— 返答がそのまま自分の案になる" % (asked_how, line[:40])))
            elif not any(c in line for c in CONFIRMING):
                out.append(("error", "推測が付いていない: 「%s」— 「〜と推測しましたが合っていますか」の形にする" % line[:40]))

    if case:
        w3 = wf.phase_file(case, 3)
        if w3 and w3.exists():
            s3 = sections(w3.read_text(encoding="utf-8"))
            u = find_section(s3, "未解明")
            if u and not [l for l in body_lines(u[1]) if PLACEHOLDER not in l]:
                out.append(("warn", "W3の未解明が0件のままW4を作っている"))
    return out


def lint_w5(text, case):
    out = []
    rows = [l for l in text.splitlines() if l.strip().startswith("|")]
    data = [r for r in rows
            if not re.match(r"^\s*\|[\s\-|]+\|\s*$", r) and "立てた仮説" not in r]
    real = [r for r in data if PLACEHOLDER not in r and "YYYY-MM-DD" not in r]
    if not real:
        out.append(("warn", "外した仮説が1件も無い。全部当たったなら仮説の確度が高すぎるか、記録し忘れ"))
    for r in real:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cells) >= 4 and not cells[3]:
            out.append(("error", "「実際の理由」が空: 「%s」— 4列目が本体" % cells[1][:30]))
        if len(cells) >= 5:
            if not cells[4]:
                out.append(("warn", "「自分の想定とのズレ」が空: 「%s」" % cells[1][:30]))
            elif re.search(r"(現場が変|おかしい|変な|意味不明)", cells[4]):
                out.append(("warn", "「現場が変だ」で止まっている: 「%s」— 「自分が知らない制約が効いていた」に変換する" % cells[4][:30]))
    return out


LINTERS = {0: lint_w0, 1: lint_w1, 2: lint_w2, 3: lint_w3, 4: lint_w4, 5: lint_w5}
ICON = {"error": "NG ", "warn": "！ ", "info": "・ "}


def lint_file(path, case):
    n = wf.phase_of(path)
    if n is None:
        return []
    return LINTERS[n](path.read_text(encoding="utf-8"), case)


def main():
    wf.force_utf8()
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("phase", nargs="?", help="W0〜W5")
    ap.add_argument("--case")
    ap.add_argument("--file")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    targets = []
    if a.file:
        p = Path(a.file).resolve()
        fallback = p.parent if (p.parent / "case.json").exists() else None
        targets = [(p, wf.resolve_case(a.case) or fallback)]
    else:
        case = wf.resolve_case(a.case)
        if case is None:
            print("作業中の案件がありません。`python scripts/wf_new.py <案件名>` で作成してください。")
            return 1
        if a.phase and re.fullmatch(r"[Ww][0-5]", a.phase):
            nums = [int(a.phase[1])]
        else:
            nums = list(range(6))
        for n in nums:
            f = wf.phase_file(case, n)
            if f:
                targets.append((f, case))

    errors = 0
    for path, case in targets:
        issues = lint_file(path, case)
        if a.quiet:
            issues = [i for i in issues if i[0] == "error"]
        n = wf.phase_of(path)
        head = "[%s] %s" % (wf.PHASE_LABEL.get(n, path.name), path.name)
        if not issues:
            if not a.quiet:
                print(head + "\n  OK\n")
            continue
        print(head)
        for level, msg in issues:
            print("  " + ICON[level] + msg)
            if level == "error":
                errors += 1
        print()
    if errors:
        print("error %d 件" % errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
