"""นับจำนวนครั้งและบทที่พบของคำจีนในต้นฉบับ

ใช้: python -X utf8 tools/term_stats.py 孫悟空 豬八戒 貧僧
หรือ: python -X utf8 tools/term_stats.py --file terms.txt (หนึ่งคำต่อบรรทัด)
"""
import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_chapters():
    chapters = []
    for path in sorted((ROOT / "chapters").glob("*.md")):
        num = int(re.match(r"(\d+)", path.name).group(1))
        text = path.read_text(encoding="utf-8")
        # ชื่อหรือคำอาจถูกพับบรรทัดกลางคำในไฟล์ Gutenberg
        text = "".join(line.strip() for line in text.splitlines())
        chapters.append((num, text))
    return chapters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="*")
    parser.add_argument("--file")
    args = parser.parse_args()
    terms = list(args.terms)
    if args.file:
        terms += [t.strip() for t in pathlib.Path(args.file).read_text(encoding="utf-8").splitlines() if t.strip()]
    chapters = load_chapters()
    print("คำ\tรวม\tจำนวนบท\tบทแรก\tบทสุดท้าย")
    for term in terms:
        hits = [(num, text.count(term)) for num, text in chapters if term in text]
        total = sum(c for _, c in hits)
        if hits:
            print(f"{term}\t{total}\t{len(hits)}\t{hits[0][0]:03d}\t{hits[-1][0]:03d}")
        else:
            print(f"{term}\t0\t0\t—\t—")


if __name__ == "__main__":
    main()
