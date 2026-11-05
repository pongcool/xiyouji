"""ดึงแถวเอกสารกลางที่เกี่ยวกับต้นฉบับบท NNN ในครั้งเดียว (X014)

ใช้: python -X utf8 tools/chapter_lookup.py NNN [--only glossary,characters,world,sources,relations]
     [--full] [--width N]

แหล่งที่ดึง (แสดงเลขบรรทัดเพื่ออ่านหรือแก้แถวเต็มได้ตรงจุด):
- GLOSSARY.md, WORLD.md: แถวที่คำจีนในช่องแรกปรากฏในต้นฉบับบทนี้ หรือช่องอ้างอิงมีรหัสบทนี้ (เช่น 006:)
- CHARACTERS.md ทะเบียน: แถวที่คำจีนในช่องชื่อจีนหรือชื่ออื่น/ฉายาปรากฏในต้นฉบับบทนี้ หรือช่องอ้างอิงมีรหัสบทนี้
- CHARACTERS.md “บันทึกความสัมพันธ์และสรรพนาม”: แถวที่ทุกรหัส C ฝั่งผู้พูด/ผู้ฟังอยู่ในบทนี้
  (แถวที่ไม่มีรหัส C ใช้คำจีนในช่องผู้พูด/ผู้ฟังแทน)
- docs/SOURCE_ISSUES.md: แถวที่ช่องตำแหน่งอ้างบทนี้ (เช่น 006:ย3 หรือ 047: หัวบท)

ค่าเริ่มต้นเป็นโหมดดัชนี: ตัดช่องยาวเกิน --width (ลงท้าย …) และไม่แสดงช่องที่ยาวแต่ไม่ใช้ตัดสินคำ
- GLOSSARY: จีน | ไทย | ประเภท | หมายเหตุ | สถานะ | รูปที่ไม่ใช้ปะปน
- CHARACTERS: รหัส | จีน | ไทย | ชื่ออื่น | ฐานะ | ความสัมพันธ์ | สถานะ
- WORLD: จีน | ไทย | ประเภท | เจ้าของ | บทอ้างอิง (ตัดสั้น) | สถานะ — ไม่แสดงข้อเท็จจริง/ข้อจำกัด
ถ้าฉากใช้คุณสมบัติหรือข้อจำกัดของรายการใด ให้อ่านแถวเต็มที่เลขบรรทัดนั้น หรือรันซ้ำด้วย
--only ส่วนนั้น --full --width 0
คำจีนตัวเดียวไม่นำมาจับ (ขึ้นแทบทุกบท) ถ้าต้องการให้ rg เอง
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0002ffff]{2,}")
CODE = re.compile(r"C\d{3}")
HEADER_FIRST = {"จีน", "รหัส", "ผู้พูด"}


def chapter_text(num: str) -> str:
    path = ROOT / "chapters" / f"{num}.md"
    if not path.exists():
        sys.exit(f"ไม่พบต้นฉบับ {path}")
    return path.read_text(encoding="utf-8")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_rows(path: Path, section: str | None = None):
    """แถวตาราง (ไม่รวมหัว/เส้นคั่น) ถ้าระบุ section จะเอาเฉพาะใต้หัวข้อ ## ที่มีคำนั้น
    ถ้า section เป็น "" จะเอาเฉพาะก่อนหัวข้อ ## แรก"""
    current = ""
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            current = line[3:]
            continue
        if section is not None and (section not in current if section else current):
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        row = cells(line)
        if row and row[0] not in HEADER_FIRST:
            yield no, line, row


def terms_in(cell: str, text: str) -> list[str]:
    cell = re.sub(r"[（(][^）)]*[）)]", "", cell)
    return [t for t in CJK.findall(cell) if t in text]


def cites(cell: str, num: str) -> bool:
    return re.search(rf"(?<!\d){num}:", cell) is not None


def clip(p: str, w: int) -> str:
    return p if w <= 0 or len(p) <= w else p[:w] + "…"


# คอลัมน์ที่แสดงในโหมดดัชนี (นับจาก 0) ตามจำนวนช่องของแถว และช่องอ้างอิงที่ตัดสั้น
INDEX_COLS = {
    "glossary": {7: [0, 1, 2, 3, 5, 6]},
    "characters": {8: [0, 1, 2, 3, 4, 5, 7]},
    "world": {8: [0, 1, 2, 3, 6, 7]},
}
REF_COL = {"world": 6}
REF_WIDTH = 60


def render(key: str, line: str, width: int, full: bool) -> str:
    parts = cells(line)
    keep = None if full else INDEX_COLS.get(key, {}).get(len(parts))
    idx = keep if keep is not None else range(len(parts))
    out = []
    for i in idx:
        w = min(width, REF_WIDTH) if keep and REF_COL.get(key) == i and width > 0 else width
        out.append(clip(parts[i], w))
    return "| " + " | ".join(out) + " |"


def by_term(path: Path, cols: tuple, ref_col: int, text: str, num: str, section=None):
    return [(no, line) for no, line, row in table_rows(path, section)
            if any(len(row) > c and terms_in(row[c], text) for c in cols)
            or (len(row) > ref_col and cites(row[ref_col], num))]


def sources(num: str):
    return [(no, line) for no, line, row in table_rows(ROOT / "docs" / "SOURCE_ISSUES.md")
            if len(row) > 1 and cites(row[1], num)]


def relations(text: str, num: str):
    path = ROOT / "CHARACTERS.md"
    present = {cells(line)[0] for _, line in by_term(path, (1, 3), 6, text, num, "")}
    out = []
    for no, line, row in table_rows(path, "ความสัมพันธ์"):
        if len(row) < 2:
            continue
        sides = row[0] + " " + row[1]
        codes = set(CODE.findall(sides))
        if codes:
            hit = codes <= present
        else:
            hit = bool(terms_in(sides, text))
        if hit or (len(row) > 5 and cites(row[5], num)):
            out.append((no, line))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("num")
    ap.add_argument("--only", default="glossary,characters,world,sources,relations")
    ap.add_argument("--width", type=int, default=100, help="ความยาวสูงสุดต่อช่อง 0 = ไม่ตัด")
    ap.add_argument("--full", action="store_true", help="แสดงทุกช่อง ไม่ใช้โหมดดัชนี")
    args = ap.parse_args()
    num = args.num.zfill(3)
    text = chapter_text(num)
    want = set(args.only.split(","))
    groups = [
        ("glossary", "GLOSSARY.md",
         lambda: by_term(ROOT / "GLOSSARY.md", (0,), 4, text, num)),
        ("characters", "CHARACTERS.md ทะเบียน",
         lambda: by_term(ROOT / "CHARACTERS.md", (1, 3), 6, text, num, "")),
        ("world", "WORLD.md",
         lambda: by_term(ROOT / "WORLD.md", (0,), 6, text, num)),
        ("sources", "docs/SOURCE_ISSUES.md", lambda: sources(num)),
        ("relations", "CHARACTERS.md ความสัมพันธ์และสรรพนาม", lambda: relations(text, num)),
    ]
    for key, label, fn in groups:
        if key not in want:
            continue
        rows = fn()
        print(f"\n=== {label}: {len(rows)} แถว ===")
        for no, line in rows:
            print(f"{no}: {render(key, line, args.width, args.full)}")


if __name__ == "__main__":
    main()
