"""ตรวจทั้งเล่มรอบสุดท้าย (PLAN.md ระยะ 2): รวมการนับที่ใช้ใน reviews/CROSSCHECK_FINAL.md

ใช้: python -X utf8 tools/check_book.py                 (ทุกส่วน ทุกบท)
     python -X utf8 tools/check_book.py --only names    (names / variants / formulas)
     python -X utf8 tools/check_book.py --chapters 001 002

ส่วนที่ตรวจ
1. names    นับชื่อ/คำเรียกจีน–ไทย
   - ชุดหลัก (CORE_NAMES) แสดงยอดรวมทั้งเล่ม และบทที่พบฝั่งหนึ่งแต่อีกฝั่งไม่พบเลย
   - ทะเบียน CHARACTERS.md (ช่องจีน/ไทยที่ใช้) แสดงบทที่ต้นฉบับมีชื่อจีน แต่คำแปลไม่มีรูปไทยของแถวนั้น
     แถวที่จับคู่ด้วยสตริงไม่ได้ (ชื่ออักษรเดียวทั้งแถว แถวชื่อกลุ่ม ฯลฯ) พิมพ์รหัสและเหตุผลที่ไม่นับ
   วิธีนับตาม CROSSCHECK_FINAL: ต่อบรรทัดจีน ตัดหัวบททั้งสองภาษา ตัดนิยามเชิงอรรถและเครื่องหมายเชิงอรรถไทย
   นับจีนด้วย re.findall ไทยด้วย regex ตัวเลขรวมคำที่เป็นส่วนของชื่อยาวกว่า จึงใช้ชี้ตำแหน่งเทียบเท่านั้น
2. variants รูปแปรของชื่อ เฉพาะชื่อเฉพาะรายคำ (name_terms): ทะเบียนตัวละคร และคำหัวแถวศัพท์กลางที่มีพินอินกำกับเสียง
   - จีน: ชื่อยาว ≥3 อักษรที่ต้นฉบับมีรูปต่างหนึ่งอักษรกลางคำ (ตรรกะ find_variants.py)
   - ไทย: รูปไทยยาว ≥6 อักขระที่คำแปลมีรูปต่างหนึ่งอักขระกลางคำ (แทน หรือตัด/แทรกสระบนล่างและวรรณยุกต์)
   จับแบบซ้อนตำแหน่ง แสดงเฉพาะรูปที่พบน้อย ไม่ใช่รูปที่ลงทะเบียน และอยู่ในบทเดียวกันหรือบทติดกับรูปหลัก
3. formulas สูตรเกริ่น/ปิดบทรายหน่วยเทียบ: จีนในหน่วย ย N มากกว่าสูตรไทยที่รองรับในหน่วยเดียวกัน
   และตรวจว่าหน่วยสุดท้ายของบทที่มี 下回分解 จบด้วย “โปรดติดตามในบทหน้า” หรือรูปตามข้อยกเว้นรายหน่วย
   (CLOSING_EXCEPTIONS) พร้อมแจกแจงคำขึ้นต้นประโยคปิดบท (畢竟)
   ยังไม่นับสูตร 有…為證 อื่นที่ไม่ใช่กวี/เพลง/ร้อยกรอง เช่น 讚 และ 新詞四首

ผลทุกส่วนเป็นรายการให้คนตรวจเทียบบริบท ไม่ตัดสินว่าผิด สคริปต์ออกด้วยรหัส 0 เสมอ
"""
import argparse
import collections
import re

from term_stats import ROOT
from prepare_xiyouji import source_units
from find_variants import glossary_terms
from check_translation import FORMULA_EXCEPTIONS

CJK = r"[㐀-䶿一-鿿豈-﫿]"
THAI = r"[ก-๎]"
MARKER = re.compile(r"<!--\s*ย(\d+)\s*-->")
FOOTNOTE_REF = re.compile(r"\[\^[^\]]+\](?!:)")
FOOTNOTE_DEF = re.compile(r"^\[\^[^\]]+\]:.*$", re.M)

# ชุดหลักจาก CROSSCHECK_FINAL: (รูปจีนหลายรูปนับรวม, รูปไทยที่นับเป็น regex)
CORE_NAMES = [
    (("孫悟空",), "ซุนอู้คง"),
    (("悟空",), "อู้คง"),
    (("行者",), "สิงเจ่อ"),
    (("大聖", "大圣"), "ต้าเซิ่ง"),
    (("三藏",), "ซานจั้ง"),
    (("唐僧",), "พระถัง"),
    (("八戒",), "ปาเจี้ย"),
    (("沙僧", "沙和尚"), "พระซา"),
    (("觀音",), "กวนอิน"),
    (("如來",), "ตถาคต"),
    (("揭諦",), "เจียตี้"),
    (("哪吒", "哪咤"), "เหนอจา"),
    (("天竺",), "เทียนจู๋"),
    (("玉華",), "อวี้หวา"),
    (("王子",), "ราชบุตร(?!เขย)"),   # ราชบุตรเขย = 駙馬
    (("黃河",), "แม่น้ำหวงเหอ"),
]

# คำจีนในทะเบียนที่เป็นคำนามทั่วไปหรือคำพ้องรูปกับคำอื่น นับรายบทแล้วได้แต่ผลบังเอิญ
# (CROSSCHECK_FINAL: 清風/明月 พบเป็นลมและจันทร์)
GENERIC_ZH = {"老者", "婦人", "道人", "童兒", "清風", "明月", "山神", "土地", "兇徒", "強盜",
              "先鋒", "女童", "毛女", "高才", "建成", "降龍", "伏虎", "黃袍", "媽媽兒",
              "老王"}   # 老王 ใน 088–090 คือราชาอวี้หวา ไม่ใช่ C097 (CROSSCHECK_FINAL)

# สูตรรายหน่วย: (ชื่อสูตร, รูปจีน regex, รูปไทย regex) ไม่ตัดสินความหมาย เป็นเพียงตัวชี้
FORMULAS = [
    ("詩曰", r"(?<![福祿壽])詩曰|詩云",
     r"มีบทกวีกล่าว(?:เป็นพยาน)?ไว้ว่า|บทกวี(?:แห่ง[^\s>“”]{1,20})?นั้นว่า|บทกวีว่า|กวีโบราณว่า"),
    ("福/祿/壽詩曰", r"[福祿壽]詩曰", r"บทกวีแห่ง[^\s>“”]{1,20}นั้นว่า"),
    ("有詩為證", r"有詩為[證証]", r"มีบทกวี(?:กล่าว)?เป็นพยาน"),
    # “…為證。…曰” ที่ติดกันนับเป็นสูตรเดียวทั้งจีนและไทย (เช่น 010:ย1 “มีบทเพลงทำนอง…เป็นพยาน บทเพลงนั้นว่า”)
    # ฝั่งไทยจับเฉพาะวลีเกริ่น ไม่จับคำว่า “บทเพลง” ในเนื้อความ (RBOOKCHECK-C4)
    # 《ชื่อทำนอง》為證／可證 (010:ย1) ไทยใช้ “มี(บทเพลง)ทำนอง…เป็นพยาน”
    ("詞/《曲》為證", r"》詞?[為可][證証](?:。?詞曰)?|詞為[證証](?:。?詞曰)?|詞曰",
     r"มี(?:บทเพลง)?ทำนอง\S+?เป็นพยาน(?:\s*บทเพลงนั้นว่า)?|มีบทเพลง(?:เป็นพยาน|ว่า)|บทเพลงนั้นว่า"),
    ("賦曰/賦為證", r"賦為[證証](?:。?賦曰)?|賦曰",
     r"มีบทร้อยกรองเป็นพยาน(?:\s*ร้อยกรองนั้นว่า)?|ร้อยกรองนั้นว่า"),
    ("下回分解", r"下回分解", r"โปรดติดตามในบทหน้า"),
]
CLOSING_TH = "โปรดติดตามในบทหน้า"
# ข้อยกเว้นปิดบทผูกกับหน่วย: (บท, หน่วย) -> (รูปปิดไทยที่ต้องอยู่ท้ายหน่วย, หลักฐาน) (RBOOKCHECK-C5)
CLOSING_EXCEPTIONS = {
    (85, 30): ("จบบท", FORMULA_EXCEPTIONS[(85, "下回分解")][1]),
}


def chapter_nums(args):
    if args.chapters:
        return [int(c) for c in args.chapters]
    return [int(p.stem) for p in sorted((ROOT / "translations" / "th").glob("[0-9][0-9][0-9].md"))]


def load(num):
    """คืน (หน่วยจีนที่ต่อบรรทัดแล้ว, {N: เนื้อไทยของหน่วย N ไม่รวมนิยาม/เครื่องหมายเชิงอรรถ})"""
    src = (ROOT / "chapters" / f"{num:03d}.md").read_text(encoding="utf-8")
    zh_units = ["".join(l.strip() for l in u.splitlines()) for u in source_units(src.partition("\n")[2])]
    th = (ROOT / "translations" / "th" / f"{num:03d}.md").read_text(encoding="utf-8")
    th = FOOTNOTE_DEF.sub("", th.partition("\n")[2])
    th = FOOTNOTE_REF.sub("", th)
    parts = MARKER.split(th)
    th_units = {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}
    return zh_units, th_units


def strip_parens(cell):
    """ลบวงเล็บรวมวงเล็บซ้อน เช่น (… S133(5)) (RBOOKCHECK-C1)"""
    prev = None
    while prev != cell:
        prev, cell = cell, re.sub(r"\([^()]*\)|（[^（）]*）", "", cell)
    return cell


def split_cell(cell, sep):
    cell = strip_parens(cell)
    return [p.strip() for p in re.split(sep, cell) if p.strip()]


def register_pairs(skipped=None):
    """คืน [(รหัส, [จีน], [ไทย])] จากช่อง จีน / ไทยที่ใช้ ของทะเบียน CHARACTERS.md
    แถวที่จับคู่ด้วยสตริงไม่ได้ (ชื่ออักษรเดียวทั้งแถว หรือช่องไม่มีชื่อจีน/ไทยที่ใช้) ใส่ใน skipped พร้อมเหตุผล"""
    rows = []
    in_register = False
    for line in (ROOT / "CHARACTERS.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and "ไทยที่ใช้" in line:
            in_register = True
        elif line.startswith("#"):
            in_register = False
        if not in_register:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"C\d+", cells[0]) or not re.match(CJK, cells[1]):
            continue
        raw = split_cell(cells[1], r"\s*/\s*|、")
        zhs = [z for z in raw if re.fullmatch(CJK + "{2,}", z)]
        ths = [t for t in split_cell(cells[2], r"\s*/\s*") if re.search(THAI, t)]
        if zhs and ths:
            rows.append((cells[0], zhs, ths))
        elif skipped is not None:
            if raw and all(re.fullmatch(CJK, z) for z in raw):
                why = "ชื่ออักษรเดียวทั้งแถว นับด้วยสตริงจะจับคำทั่วไป"
            elif any("ฯลฯ" in z for z in raw):
                why = "แถวชื่อกลุ่ม (ฯลฯ) ให้ดูแถวรายตัว"
            else:
                why = "ช่องจีน/ไทยไม่มีรูปที่จับคู่ได้"
            skipped.append((cells[0], cells[1], why))
    return rows


def section_names(data):
    print("## 1. ชื่อและคำเรียก")
    print("### ชุดหลัก (ยอดรวมทั้งเล่ม)")
    print("| จีน | ไทย | จีน | ไทย | บทที่มีจีนแต่ไม่มีไทย | บทที่มีไทยแต่ไม่มีจีน |")
    print("|---|---|---:|---:|---|---|")
    for zhs, th in CORE_NAMES:
        zh_total = th_total = 0
        only_zh, only_th = [], []
        for num, (zh_text, th_text) in data.items():
            z = sum(len(re.findall(re.escape(f), zh_text)) for f in zhs)
            t = len(re.findall(th, th_text))
            zh_total += z
            th_total += t
            if z and not t:
                only_zh.append(f"{num:03d}")
            if t and not z:
                only_th.append(f"{num:03d}")
        print(f"| {'／'.join(zhs)} | {th.split('(')[0]} | {zh_total:,} | {th_total:,} | {', '.join(only_zh) or '—'} | {', '.join(only_th) or '—'} |")
    print()
    print("### ทะเบียน CHARACTERS.md: บทที่ต้นฉบับมีชื่อจีน แต่ไม่มีรูปไทยที่ใช้ของแถวนั้น")
    core_zh = {z for zhs, _ in CORE_NAMES for z in zhs}
    skipped = []
    register = register_pairs(skipped)
    for code, zh, why in skipped:
        print(f"- ไม่นับ {code} {zh}: {why}")
    shared = collections.Counter(z for _, zhs, _ in register for z in set(zhs))
    skip = core_zh | GENERIC_ZH | {z for z, n in shared.items() if n > 1}
    print(f"ข้ามคำจีนชุดหลัก คำนามทั่วไป และคำที่ลงหลายแถว {len(skip)} คำ"
          f" (คำนามทั่วไปที่ข้าม: {'、'.join(sorted(GENERIC_ZH))})")
    rows = 0
    for code, zhs, ths in register:
        zhs = [z for z in zhs if z not in skip]
        if not zhs:
            continue
        miss = []
        for num, (zh_text, th_text) in data.items():
            z = sum(zh_text.count(f) for f in zhs)
            if z and not any(t in th_text for t in ths):
                miss.append(f"{num:03d}({z})")
        if miss:
            rows += 1
            print(f"- {code} {'/'.join(zhs)} → {' / '.join(ths)}: {', '.join(miss)}")
    print(f"\nรวม {rows} แถวทะเบียนที่มีบทให้เทียบบริบท\n")


# พินอินต้องมีสระกำกับเสียง จึงไม่รับอักษรโรมันอื่นในหมายเหตุ เช่น ADDRESS_TERMS (RBOOKCHECK-C2)
PINYIN = re.compile(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]")
MARKS = "ัิ-ฺ็-๎"          # สระบน/ล่าง วรรณยุกต์ การันต์
MARK = "[" + MARKS + "]"


def glossary_rows():
    for line in (ROOT / "GLOSSARY.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("| จีน"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4:
                yield cells


def name_terms():
    """ชื่อเฉพาะรายคำ คืน (ชุดจีน, ชุดไทย) (RBOOKCHECK-C2)
    - ศัพท์กลาง: แถวที่ช่องพินอินมีพินอินกำกับเสียง รับเฉพาะคำหัวแถว (พินอินเขียนให้คำแรก)
      และรูปย่อที่อยู่ในคำหัวแถว เช่น 豬八戒 / 八戒 ส่วนแถวดัชนีที่รวมหลายประเภท
      เช่น แถวที่มี 翠雲山 กับ 點心 รับเพียงคำหัวแถว
    - ทะเบียนตัวละคร: ทุกชื่อในช่องจีน/ไทยที่ใช้"""
    zh, th = set(), set()
    for cells in glossary_rows():
        if not PINYIN.search(cells[3]):
            continue
        zhs = split_cell(cells[0], r"\s*/\s*")
        ths = split_cell(cells[1], r"\s*/\s*")
        if not zhs or not ths:
            continue
        head_zh, head_th = zhs[0], ths[0]
        pairs = [(head_zh, head_th)]
        if len(zhs) == len(ths):
            pairs += [(z, t) for z, t in zip(zhs[1:], ths[1:]) if z in head_zh]
        for z, t in pairs:
            if re.fullmatch(CJK + "{3,}", z):
                zh.add(z)
            th.add(t)
    for _, zhs, ths in register_pairs():
        zh.update(z for z in zhs if len(z) >= 3)
        th.update(ths)
    return zh, {t for t in th if re.fullmatch(THAI + "{6,}", t)}


def near(chapters, base_chapters):
    """รูปแปรที่น่าเป็นรอยพิมพ์ผิดมักอยู่ในบทเดียวกันหรือบทติดกับรูปหลัก"""
    return [c for c in chapters if any(abs(c - b) <= 1 for b in base_chapters)]


def report_variants(data, side, terms, known, variant_regex, max_ratio):
    count = 0
    for term in sorted(terms):
        base_ch = [num for num, texts in data.items() if term in texts[side]]
        if not base_ch:
            continue
        base = sum(data[num][side].count(term) for num in base_ch)
        found = collections.Counter()
        scope = sorted({n for b in base_ch for n in (b - 1, b, b + 1) if n in data})
        corpus = "\n".join(data[n][side] for n in scope)
        # จับแบบซ้อนตำแหน่งด้วย lookahead แล้วจึงคัดรูปหลักและรูปที่รู้จัก (RBOOKCHECK-C3)
        for regex in variant_regex(term):
            for m in regex.finditer(corpus):
                v = m.group(1)
                if v != term and v not in known and not any(v in k for k in known if k != term):
                    found[v] += 1
        for variant, n in sorted(found.items()):
            if n > max(1, base * max_ratio):
                continue
            where = near([num for num, texts in data.items() if variant in texts[side]], base_ch)
            if where:
                print(f"- {term}({base}) {variant}({n}) บท {', '.join(f'{w:03d}' for w in where[:10])}")
                count += 1
    print(f"\nรวม {count} รายการ\n")


def lookahead(alts):
    """ทางเลือกในชุดเดียวกันยาวเท่ากัน จึงได้สตริงเดียวกันไม่ว่าทางเลือกใดตรงที่ตำแหน่งนั้น"""
    return re.compile("(?=(" + "|".join(alts) + "))") if alts else None


def zh_variant_regex(term):
    alts = [re.escape(term[:i]) + CJK + re.escape(term[i + 1:]) for i in range(1, len(term) - 1)]
    return [r for r in (lookahead(alts),) if r]


def th_variant_regex(form):
    sub, dele, ins = [], [], []
    for i in range(1, len(form) - 1):
        pre, post = re.escape(form[:i]), re.escape(form[i + 1:])
        sub.append(pre + THAI + post)                                   # แทนอักขระกลางคำ
        if re.match(MARK, form[i]):
            dele.append(pre + post)                                     # ตัดสระ/วรรณยุกต์
    for i in range(1, len(form)):
        ins.append(re.escape(form[:i]) + MARK + re.escape(form[i:]))    # แทรกสระ/วรรณยุกต์
    return [r for r in (lookahead(sub), lookahead(dele), lookahead(ins)) if r]


def section_variants(data, max_ratio):
    zh_names, th_names = name_terms()
    print("## 2. รูปแปรของชื่อ")
    print("เฉพาะชื่อเฉพาะ (แถวศัพท์กลางที่มีพินอิน และทะเบียนตัวละคร) รูปแปรต้องพบไม่เกินสัดส่วนที่กำหนด"
          " และอยู่ในบทเดียวกันหรือบทติดกับรูปหลัก")
    print("### จีน: รูปต่างหนึ่งอักษรกลางคำ (ข้อมูลต้นฉบับ เทียบ docs/SOURCE_ISSUES.md และคำแปลจุดนั้น)")
    report_variants(data, 0, zh_names, glossary_terms() | zh_names, zh_variant_regex, max_ratio)
    print("### ไทย: แทนอักขระกลางคำ หรือตัด/แทรกสระบนล่างและวรรณยุกต์")
    th_known = th_names | {t for cells in glossary_rows() for t in split_cell(cells[1], r"\s*/\s*")}
    report_variants(data, 1, th_names, th_known, th_variant_regex, max_ratio)


def section_formulas(units):
    print("## 3. สูตรเกริ่นและปิดบท (รายหน่วย)")
    print("| สูตร | จีนทั้งเล่ม | ไทยที่รองรับ | หน่วยที่ไทยน้อยกว่าจีน |")
    print("|---|---:|---:|---|")
    for name, zh_re, th_re in FORMULAS:
        zh_total = th_total = 0
        short = []
        for num, (zh_units, th_units) in units.items():
            for i, zu in enumerate(zh_units, 1):
                z = len(re.findall(zh_re, zu))
                t = len(re.findall(th_re, th_units.get(i, "")))
                zh_total += z
                th_total += min(t, z) if z else 0
                excused = 0
                if name == "下回分解" and (num, i) in CLOSING_EXCEPTIONS:
                    form = CLOSING_EXCEPTIONS[(num, i)][0]
                    excused = 1 if th_units.get(i, "").rstrip().endswith(form) else 0
                if z - excused > t:
                    short.append(f"{num:03d}:ย{i}({z}/{t})")
        print(f"| {name} | {zh_total} | {th_total} | {', '.join(short) or '—'} |")
    print("\nตัวเลขในวงเล็บคือ จีน/ไทย ในหน่วยนั้น สูตรที่แปลตามบริบทต่างรูปได้ให้เทียบเนื้อหาแทน\n")

    print("### ปิดบท")
    starters = collections.Counter()
    examples = collections.defaultdict(list)
    problems = []
    for num, (zh_units, th_units) in units.items():
        last = len(zh_units)
        zh_last, th_last = zh_units[-1], th_units.get(last, "").strip()
        # ตรวจวลีปิดที่ปลายหน่วยหลังตัดช่องว่าง ไม่ใช่ที่ใดก็ได้ในหน่วย (RBOOKCHECK-C5)
        if (num, last) in CLOSING_EXCEPTIONS:
            form = CLOSING_EXCEPTIONS[(num, last)][0]
            if not th_last.endswith(form):
                problems.append(f"{num:03d}:ย{last} (ข้อยกเว้นต้องจบด้วย “{form}”)")
        elif "下回分解" in zh_last and not th_last.endswith(CLOSING_TH):
            problems.append(f"{num:03d}:ย{last}")
        if "畢竟" in zh_last:
            # ประโยคปิดบทคือย่อหน้าสุดท้ายของหน่วย
            para = th_last.split("\n\n")[-1].strip()
            m = re.search(r"(?:ถึง|ท้าย)ที่สุด", para)
            if not m:
                key = "ไม่มี “ถึงที่สุด/ท้ายที่สุด”"
            elif re.match(r"(?:[อ้าโอ!]+\s*)?$", para[:m.start()]):
                key = m.group(0) + " (ขึ้นต้นประโยค)"
            else:
                key = m.group(0) + " (กลางประโยค)"
            starters[key] += 1
            examples[key].append(f"{num:03d}")
    print(f"- หน่วยสุดท้ายที่มี 下回分解 แต่ไม่จบด้วย “{CLOSING_TH}” หรือรูปตามข้อยกเว้น: {', '.join(problems) or 'ไม่พบ'}")
    for (num, i), (form, why) in CLOSING_EXCEPTIONS.items():
        print(f"- ข้อยกเว้น {num:03d}:ย{i} จบด้วย “{form}”: {why}")
    print("- คำขึ้นต้นประโยคปิดบทที่จีนใช้ 畢竟:")
    for key, n in starters.most_common():
        print(f"  - {key} {n} บท: {', '.join(examples[key])}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapters", nargs="*", help="เลขบท ค่าเริ่มต้นทุกบทที่มีคำแปล")
    parser.add_argument("--only", choices=["names", "variants", "formulas"])
    parser.add_argument("--max-ratio", type=float, default=0.1,
                        help="รูปแปรที่พบไม่เกินสัดส่วนนี้ของรูปหลัก")
    args = parser.parse_args()
    nums = chapter_nums(args)
    units = {num: load(num) for num in nums}
    data = {num: ("".join(z), "\n".join(t.values())) for num, (z, t) in units.items()}
    print(f"# check_book: {len(nums)} บท ({nums[0]:03d}–{nums[-1]:03d})\n")
    if args.only in (None, "names"):
        section_names(data)
    if args.only in (None, "variants"):
        section_variants(data, args.max_ratio)
    if args.only in (None, "formulas"):
        section_formulas(units)


if __name__ == "__main__":
    main()
