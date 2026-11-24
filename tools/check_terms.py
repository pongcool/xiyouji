"""ตรวจว่าคำแปลใช้รูปไทยตามศัพท์กลาง เมื่อต้นฉบับบทนั้นมีคำจีนที่ลงทะเบียนไว้

ใช้: python -X utf8 tools/check_terms.py 001 002
     python -X utf8 tools/check_terms.py --all

ตรวจเฉพาะคำจีนยาวตั้งแต่ 2 ตัวอักษร ถ้าช่องจีนและช่องไทยมีหลายรูปคั่นด้วย “ / ” จำนวนเท่ากัน
จะจับคู่ตามลำดับ ไม่เช่นนั้นถือว่ารูปไทยใดก็ได้ในช่องนั้น
ผลเป็นรายการให้คนตรวจ คำบางคำแปลตามบริบทได้ เช่น คำนามทั่วไปหรือสูตรที่รวมกับสูตรอื่น

ตัวกรองค่าเริ่มต้น (ปิดด้วย --raw):
- คำจีนเดียวกันที่ลงหลายแถว รวมรูปไทยทุกแถว พบรูปใดก็ผ่าน (คำหลายความหมาย)
- ลบเครื่องหมายเชิงอรรถ [^NNN-N] ออกจากคำแปลก่อนค้น เพราะอาจแทรกกลางคำ
- รับรูปไทยจาก CHARACTERS.md (ชื่อ ชื่ออื่น และคำเรียกในตารางสรรพนาม) เป็นรูปเพิ่มของคำจีนที่ลงใน GLOSSARY
  เช่น 三藏 ทั้ง “ไตรปิฎก” และ “ซานจั้ง” โดยไม่สร้างรายการตรวจใหม่จาก CHARACTERS.md
- คำจีนที่ทุกครั้งในบทอยู่ภายในคำจีนที่ยาวกว่าซึ่งคำแปลใช้รูปไทยตามศัพท์กลางแล้ว ไม่นับ
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


FOOTNOTE = re.compile(r"\[\^[0-9]{3}-[0-9]+\]")


CHAR_ITEM = re.compile(r"^(" + CJK + r"[" + CJK[1:-1] + r"/、]*)\s+([^(（→]+)")


def character_forms():
    """คืน {จีน: [ไทย]} จากตาราง CHARACTERS.md"""
    forms = {}

    def add(zh, th):
        zhs = [z for z in re.split(r"[/、]", zh) if z]
        ths = [t.strip() for t in th.split("/") if t.strip()]
        pairs = zip(zhs, ths) if len(zhs) == len(ths) else ((z, t) for z in zhs for t in ths)
        for z, t in pairs:
            forms.setdefault(z, [])
            if t not in forms[z]:
                forms[z].append(t)

    path = ROOT / "CHARACTERS.md"
    if not path.exists():
        return forms
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| C"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"C\d+", cells[0]) and re.match(CJK, cells[1]):
            add(cells[1], cells[2])
            items = cells[3].split(";")
        else:
            items = [i for c in cells[2:4] for i in c.split(";")]
        for item in items:
            m = CHAR_ITEM.match(item.strip())
            if m:
                add(m.group(1), m.group(2).strip())
    return forms


def merge_pairs(pairs, extra=None):
    merged = {}
    for zh, ths in pairs:
        forms = merged.setdefault(zh, [])
        forms.extend(t for t in ths if t not in forms)
    for zh, forms in merged.items():
        forms.extend(t for t in (extra or {}).get(zh, []) if t not in forms)
    return list(merged.items())


def find_missing(source, text, pairs, raw=False):
    if raw:
        return [(zh, ths, source.count(zh)) for zh, ths in pairs
                if zh in source and not any(t in text for t in ths)]
    text = FOOTNOTE.sub("", text)
    covered = [False] * len(source)
    missing = []
    for zh, ths in sorted(pairs, key=lambda p: len(p[0]), reverse=True):
        spans = [m.span() for m in re.finditer(re.escape(zh), source)]
        free = sum(1 for a, b in spans if not all(covered[a:b]))
        if not free:
            continue
        if any(t in text for t in ths):
            for a, b in spans:
                covered[a:b] = [True] * (b - a)
        else:
            missing.append((zh, ths, free))
    order = {zh: i for i, (zh, _) in enumerate(pairs)}
    return sorted(missing, key=lambda m: order[m[0]])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapters", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--raw", action="store_true", help="ไม่ใช้ตัวกรอง แสดงทุกแถวที่ไม่พบรูปไทย")
    args = parser.parse_args()
    th_dir = ROOT / "translations" / "th"
    if args.all:
        nums = [int(p.stem) for p in sorted(th_dir.glob("[0-9][0-9][0-9].md"))]
    else:
        nums = [int(c) for c in args.chapters]
    pairs = glossary_pairs() if args.raw else merge_pairs(glossary_pairs(), character_forms())
    if args.all and not nums:
        print("ยังไม่มีไฟล์คำแปลใน translations/th/")
        return
    if not nums:
        parser.error("ระบุเลขบท หรือใช้ --all")
    total = 0
    for num in nums:
        source = (ROOT / "chapters" / f"{num:03d}.md").read_text(encoding="utf-8")
        source = "".join(line.strip() for line in source.splitlines())
        text = (th_dir / f"{num:03d}.md").read_text(encoding="utf-8")
        missing = find_missing(source, text, pairs, args.raw)
        total += len(missing)
        print(f"== บท {num:03d}: ไม่พบรูปไทยตามศัพท์กลาง {len(missing)} รายการ")
        for zh, ths, count in missing:
            print(f"  {zh} ({count} ครั้ง) → {' / '.join(ths)}")
    if len(nums) > 1:
        print(f"== รวม {total} รายการใน {len(nums)} บท")


if __name__ == "__main__":
    main()
