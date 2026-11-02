"""หาชื่อในต้นฉบับที่ต่างจากคำในศัพท์กลางหนึ่งตัวอักษร เพื่อชี้รูปแปรให้คนตรวจ

ใช้: python -X utf8 tools/find_variants.py [--max-ratio 0.1]
ตรวจเฉพาะคำยาวตั้งแต่ 3 ตัวอักษร และแทนเฉพาะตัวกลางคำ เพราะตัวหัวหรือท้ายคำมักจับคำข้างเคียงที่บังเอิญติดกัน
ใช้ --edges เพื่อแทนตัวหัวและท้ายด้วย (ผลบังเอิญจำนวนมาก)
ผลลัพธ์เป็นรายการให้คนตรวจ ไม่ได้ยืนยันว่าเป็นข้อผิดพลาด บันทึกที่ยืนยันแล้วใน docs/SOURCE_ISSUES.md
"""
import argparse
import collections
import re

from term_stats import ROOT, load_chapters

CJK = r"[㐀-䶿一-鿿豈-﫿]"


def glossary_terms():
    terms = set()
    for line in (ROOT / "GLOSSARY.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        first = line.split("|")[1]
        for part in first.split("/"):
            term = re.sub(r"\(.*?\)", "", part).strip()
            if re.fullmatch(CJK + "+", term):
                terms.add(term)
    return terms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-ratio", type=float, default=0.1,
                        help="แสดงรูปแปรที่พบไม่เกินสัดส่วนนี้ของคำหลัก")
    parser.add_argument("--edges", action="store_true", help="แทนตัวอักษรหัวและท้ายคำด้วย")
    args = parser.parse_args()
    chapters = load_chapters()
    corpus = "\n".join(text for _, text in chapters)
    known = glossary_terms()
    for term in sorted(t for t in known if len(t) >= 3):
        base = corpus.count(term)
        if not base:
            continue
        found = collections.Counter()
        positions = range(len(term)) if args.edges else range(1, len(term) - 1)
        for i in positions:
            pattern = re.escape(term[:i]) + "(" + CJK + ")" + re.escape(term[i + 1:])
            for m in re.finditer(pattern, corpus):
                if m.group(0) != term and m.group(0) not in known:
                    found[m.group(0)] += 1
        for variant, count in found.items():
            if count <= max(1, base * args.max_ratio):
                where = [f"{num:03d}" for num, text in chapters if variant in text]
                print(f"{term}({base})\t{variant}({count})\tบท {', '.join(where[:10])}")


if __name__ == "__main__":
    main()
