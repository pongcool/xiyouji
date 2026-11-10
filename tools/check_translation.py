"""ตรวจคำแปลเทียบต้นฉบับแบบอัตโนมัติ

ใช้: python -X utf8 tools/check_translation.py 001 002
     python -X utf8 tools/check_translation.py --all   (ตรวจทุกไฟล์ใน translations/th/)

ตรวจ:
- หัวบทรูป "# บทที่ N ชื่อบท"
- ป้ายย่อหน้า <!-- ยN --> ครบ ไม่ซ้ำ เรียงลำดับ และมีเนื้อความตามหลัง (ข้อยุติ X003)
- อักษรจีนหลงในเนื้อเรื่อง, [TODO], เชิงอรรถไม่ครบคู่หรือผิดรหัส
- รูปในคอลัมน์ "รูปที่ไม่ใช้ปะปน" ของ GLOSSARY.md
- คำเตือน: เลขอารบิกในเนื้อเรื่อง, เครื่องหมายคำพูดไม่ครบคู่, จำนวนสูตรการเล่าน้อยกว่าต้นฉบับ

ผ่านสคริปต์นี้ไม่ได้แปลว่าตรวจความหมายแล้ว ต้องตรวจตาม TRANSLATION_GUIDE.md ต่อ
"""
import argparse
import pathlib
import re
import sys

from term_stats import ROOT
from prepare_xiyouji import source_units

CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
MARKER = re.compile(r"<!--\s*ย(\d+)\s*-->")
FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\](?!:)")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:", re.M)

# คำที่บอกว่าเชิงอรรถกำลังเล่าขั้นตอนหรือข้อสงสัยของผู้แปล
TRANSLATOR_NOTE_PHRASES = ["ฉบับแปล", "คำแปลชั่วคราว", "ผู้แปล", "ยังไม่อาจยืนยัน", "ไม่มีหลักฐาน", "โดยคาดเดา"]

# (คำจีน, รูปไทยที่รองรับ) เป็นเพียงตัวชี้ให้ตรวจสูตรเล่า ไม่ตัดสินความหมาย
FORMULAS = [
    ("詩曰", ("มีบทกวีกล่าวไว้ว่า", "มีบทกวีกล่าวเป็นพยานไว้ว่า", "บทกวีนั้นว่า")),
    ("有詩為證", ("มีบทกวีเป็นพยาน", "มีบทกวีกล่าวเป็นพยาน")),
    ("下回分解", ("โปรดติดตามในบทหน้า",)),
]



def quote_warnings(body):
    """เปิดซ้ำต้นย่อหน้าได้เมื่อผู้พูดเดิมกล่าวต่อ แต่ต้องปิดเมื่อจบคำพูด"""
    opened = False
    warnings = []
    for match in re.finditer("[“”]", body):
        if match.group() == "“":
            if opened:
                paragraph_start = body.rfind("\n\n", 0, match.start())
                prefix = body[paragraph_start + 2 if paragraph_start >= 0 else 0:match.start()]
                if prefix.strip(" >\t\r\n"):
                    warnings.append("พบเครื่องหมาย “ ซ้อนในคำพูดที่ยังไม่ปิด")
            opened = True
        elif not opened:
            warnings.append("พบเครื่องหมาย ” โดยไม่มีเครื่องหมายเปิด")
        else:
            opened = False
    if opened:
        warnings.append("คำพูดท้ายเนื้อเรื่องยังไม่มีเครื่องหมาย ” ปิด")
    return warnings


def source_paragraphs(num):
    path = ROOT / "chapters" / f"{num:03d}.md"
    text = path.read_text(encoding="utf-8")
    return path, source_units(text.partition("\n")[2])


def forbidden_forms():
    forms = {}
    header = None
    for line in (ROOT / "GLOSSARY.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if line.startswith("|---"):
            continue
        if header is None:
            header = cells
            continue
        if "รูปที่ไม่ใช้ปะปน" not in header:
            continue
        value = cells[header.index("รูปที่ไม่ใช้ปะปน")]
        for form in value.split(" / "):
            form = form.strip()
            if form and form != "—":
                forms[form] = cells[1]
    return forms


def check(num, forbidden):
    errors, warnings = [], []
    path = ROOT / "translations" / "th" / f"{num:03d}.md"
    if not path.exists():
        return [f"ไม่พบไฟล์ {path.relative_to(ROOT)}"], []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        _, paras = source_paragraphs(num)
    except FileNotFoundError:
        return [f"ไม่พบต้นฉบับ chapters/{num:03d}.md"], []

    if not lines or not re.match(rf"^# บทที่ {num} \S", lines[0]):
        errors.append(f"บรรทัดแรกต้องเป็น '# บทที่ {num} ชื่อบทภาษาไทย'")

    # ป้ายย่อหน้า
    markers = [(int(m.group(1)), text.count("\n", 0, m.start()) + 1) for m in MARKER.finditer(text)]
    seen = [n for n, _ in markers]
    expected = list(range(1, len(paras) + 1))
    missing = sorted(set(expected) - set(seen))
    extra = sorted(set(seen) - set(expected))
    dupes = sorted({n for n in seen if seen.count(n) > 1})
    if missing:
        errors.append(f"ขาดย่อหน้าต้นฉบับ {len(missing)} ย่อหน้า: {compact(missing)} (ต้นฉบับมี {len(paras)})")
    if extra:
        errors.append(f"ป้ายเกินจำนวนย่อหน้าต้นฉบับ: {compact(extra)}")
    if dupes:
        errors.append(f"ป้ายซ้ำ: {compact(dupes)}")
    if seen != sorted(seen):
        errors.append("ป้ายย่อหน้าไม่เรียงลำดับ")
    body_parts = MARKER.split(text)
    for i in range(1, len(body_parts), 2):
        content = body_parts[i + 1]
        # นิยามเชิงอรรถ/HTML comment ไม่ใช่เนื้อแปล
        content = re.sub(r"<!--.*?-->", "", content, flags=re.S)
        content = re.sub(r"^\[\^[^\]]+\]:.*$", "", content, flags=re.M)
        if not content.strip():
            errors.append(f"ป้าย ย{body_parts[i]} ไม่มีเนื้อความตามหลัง")

    # เนื้อเรื่อง = ไม่รวมหัวบท ป้าย และนิยามเชิงอรรถ
    body_lines = []
    for lineno, line in enumerate(lines[1:], 2):
        if FOOTNOTE_DEF.match(line):
            continue
        body_lines.append((lineno, MARKER.sub("", line)))

    for lineno, line in body_lines:
        if CJK.search(line):
            errors.append(f"บรรทัด {lineno}: มีอักษรจีนในเนื้อเรื่อง: {CJK.findall(line)[:5]}")
        if "TODO" in line:
            errors.append(f"บรรทัด {lineno}: มี TODO")
        stripped = FOOTNOTE_REF.sub("", line)
        if re.search(r"\d", stripped):
            warnings.append(f"บรรทัด {lineno}: มีเลขอารบิกในเนื้อเรื่อง (ร้อยแก้วควรเขียนเป็นคำ)")
        for form, correct in forbidden.items():
            # ไม่นับเมื่ออยู่หลังสระหน้า เช่น 'ต้าหยวน' ใน 'จางเต้าหยวน' (張道源)
            if re.search(r"(?<![เแโใไ])" + re.escape(form), line):
                errors.append(f"บรรทัด {lineno}: ใช้ '{form}' ซึ่งศัพท์กลางห้ามใช้ (ใช้ '{correct}')")

    # เชิงอรรถ
    refs = FOOTNOTE_REF.findall(text)
    defs = FOOTNOTE_DEF.findall(text)
    for label in sorted(set(refs) - set(defs)):
        errors.append(f"เชิงอรรถ [^{label}] ไม่มีคำอธิบายท้ายบท")
    for label in sorted(set(defs) - set(refs)):
        errors.append(f"คำอธิบาย [^{label}] ไม่มีจุดอ้างในเนื้อเรื่อง")
    # เชิงอรรถเป็นของผู้อ่าน
    for lineno, line in enumerate(lines[1:], 2):
        if not FOOTNOTE_DEF.match(line):
            continue
        if CJK.search(line):
            errors.append(f"บรรทัด {lineno}: มีอักษรจีนในเชิงอรรถ: {CJK.findall(line)[:5]}")
        for phrase in TRANSLATOR_NOTE_PHRASES:
            if phrase in line:
                warnings.append(f"บรรทัด {lineno}: เชิงอรรถมีคำว่า '{phrase}' อาจเป็นบันทึกผู้แปล ให้ย้ายไป reviews/")
    order = []
    for label in refs:
        if label not in order:
            order.append(label)
    for i, label in enumerate(order, 1):
        if label != f"{num:03d}-{i}":
            errors.append(f"เชิงอรรถลำดับที่ {i} ควรเป็น [^{num:03d}-{i}] แต่พบ [^{label}]")
            break

    # คำเตือนอื่น
    body = "\n".join(l for _, l in body_lines)
    warnings.extend(quote_warnings(body))
    # ต่อบรรทัดพับคำก่อนนับสูตรจีนที่อาจถูกตัดกลางคำ
    source = "".join(line.strip() for p in paras for line in p.splitlines())
    for zh, forms in FORMULAS:
        translated_count = sum(body.count(form) for form in forms)
        if source.count(zh) > translated_count:
            warnings.append(
                f"ต้นฉบับมี {zh} {source.count(zh)} ครั้ง แต่คำแปลมีสูตรที่รองรับ "
                f"{translated_count} ครั้ง ({' / '.join(forms)})"
            )

    return errors, warnings


def compact(nums):
    if len(nums) > 15:
        return ", ".join(map(str, nums[:15])) + f" … (รวม {len(nums)})"
    return ", ".join(map(str, nums))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapters", nargs="*", help="เลขบท เช่น 001 หรือ 1")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all:
        nums = [int(p.stem) for p in sorted((ROOT / "translations" / "th").glob("[0-9][0-9][0-9].md"))]
    else:
        nums = [int(c) for c in args.chapters]
    if args.all and not nums:
        print("ยังไม่มีไฟล์คำแปลใน translations/th/")
        return
    if not nums:
        parser.error("ระบุเลขบท หรือใช้ --all")
    forbidden = forbidden_forms()
    failed = False
    for num in nums:
        errors, warnings = check(num, forbidden)
        status = "ไม่ผ่าน" if errors else "ผ่านการตรวจอัตโนมัติ"
        print(f"== บท {num:03d}: {status} (ผิด {len(errors)}, เตือน {len(warnings)})")
        for e in errors:
            print(f"  ผิด: {e}")
        for w in warnings:
            print(f"  เตือน: {w}")
        failed |= bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
