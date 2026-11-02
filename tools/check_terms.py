"""ตรวจว่าคำแปลใช้รูปไทยตามศัพท์กลาง เมื่อต้นฉบับบทนั้นมีคำจีนที่ลงทะเบียนไว้

ใช้: python -X utf8 tools/check_terms.py 001 002
     python -X utf8 tools/check_terms.py --all

ตรวจเฉพาะคำจีนยาวตั้งแต่ 2 ตัวอักษร ถ้าช่องจีนและช่องไทยมีหลายรูปคั่นด้วย “ / ” จำนวนเท่ากัน
จะจับคู่ตามลำดับ ไม่เช่นนั้นถือว่ารูปไทยใดก็ได้ในช่องนั้น
ผลเป็นรายการให้คนตรวจ คำบางคำแปลตามบริบทได้ เช่น คำนามทั่วไปหรือสูตรที่รวมกับสูตรอื่น
"""
import argparse
import re

from term_stats import ROOT

CJK = r"[㐀-䶿一-鿿豈-﫿]"


def split_forms(cell):
    cell = re.sub(r"\(.*?\)", "", cell)
    return [f.strip() for f in cell.split(" / ") if f.strip()]


def glossary_pairs():
    pairs = []
    for line in (ROOT / "GLOSSARY.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| จีน"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        zh_forms = split_forms(cells[0])
        th_forms = split_forms(cells[1])
        if len(zh_forms) == len(th_forms):
            mapping = [(z, [t]) for z, t in zip(zh_forms, th_forms)]
        else:
            mapping = [(z, th_forms) for z in zh_forms]
        for zh, ths in mapping:
            if re.fullmatch(CJK + "{2,}", zh) and ths and all("…" not in t for t in ths):
                pairs.append((zh, ths))
    return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapters", nargs="*")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    th_dir = ROOT / "translations" / "th"
    if args.all:
        nums = [int(p.stem) for p in sorted(th_dir.glob("[0-9][0-9][0-9].md"))]
    else:
        nums = [int(c) for c in args.chapters]
    pairs = glossary_pairs()
    if args.all and not nums:
        print("ยังไม่มีไฟล์คำแปลใน translations/th/")
        return
    if not nums:
        parser.error("ระบุเลขบท หรือใช้ --all")
    for num in nums:
        source = (ROOT / "chapters" / f"{num:03d}.md").read_text(encoding="utf-8")
        source = "".join(line.strip() for line in source.splitlines())
        text = (th_dir / f"{num:03d}.md").read_text(encoding="utf-8")
        missing = [(zh, ths) for zh, ths in pairs if zh in source and not any(t in text for t in ths)]
        print(f"== บท {num:03d}: ไม่พบรูปไทยตามศัพท์กลาง {len(missing)} รายการ")
        for zh, ths in missing:
            print(f"  {zh} ({source.count(zh)} ครั้ง) → {' / '.join(ths)}")


if __name__ == "__main__":
    main()
