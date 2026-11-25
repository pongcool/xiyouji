"""สร้างฉบับรวมเล่ม (PLAN.md ระยะ 3): HTML ไฟล์เดียว และ EPUB 3 ด้วย Python ล้วน

ใช้: python -X utf8 tools/build_book.py                  (สร้างทั้ง HTML และ EPUB ลง build/)
     python -X utf8 tools/build_book.py --format html
     python -X utf8 tools/build_book.py --check          (แปลงและตรวจ ไม่เขียนไฟล์)
     python -X utf8 tools/build_book.py --out DIR

ข้อมูลเข้า
- translations/th/001.md–100.md  คำแปล
- book/metadata.json             ชื่อเล่ม ผู้แต่ง ผู้แปล สัญญาอนุญาต แหล่งต้นฉบับ (ไม่มีไฟล์ใช้ค่าเริ่มต้น)
- book/front/*.md, book/back/*.md  ส่วนหน้า/ส่วนท้าย เรียงตามชื่อไฟล์ (ไม่มีโฟลเดอร์ก็ข้าม)

Markdown ที่รองรับ (เท่าที่คำแปลใช้)
- `# หัวเรื่อง` บรรทัดแรกของไฟล์ (บท: `# บทที่ N ชื่อบท`) มีเชิงอรรถได้ สารบัญตัดเครื่องหมายเชิงอรรถออก;
  ส่วนหน้า/ท้ายใช้ `## หัวข้อย่อย` ได้
- ย่อหน้าร้อยแก้วหนึ่งบรรทัด คั่นด้วยบรรทัดว่าง
- กวี `>` ต่อเนื่องเป็น blockquote บรรทัด `>` ว่างแบ่งวรรค บรรทัดในวรรคตัดด้วย <br/>
- รายการ `- `
- เชิงอรรถ `[^id]` และนิยาม `[^id]: ข้อความ` (ลำดับเลขแสดงผลตามลำดับที่อ้างครั้งแรกในไฟล์)
- ป้ายหน่วยเทียบ `<!-- ยN -->` ถูกตัดทิ้ง
รูปแบบอื่น (ตาราง, ###, ตัวหนา, ลิงก์, HTML, บรรทัดร้อยแก้วหลายบรรทัดติดกัน) ถือเป็นข้อผิด เพื่อไม่ให้หลุดเข้าเล่มเงียบ ๆ

ตรวจก่อนเขียนไฟล์: บทครบ 001–100 ตามลำดับ เลขในหัวบทตรงชื่อไฟล์ เชิงอรรถที่อ้างมีนิยาม นิยามทุกรายการถูกอ้าง
ไม่มีป้ายหรือเครื่องหมาย Markdown ตกค้าง XHTML ทุกหน้า parse ได้; มีข้อผิดจะไม่เขียนไฟล์และออกด้วยรหัส 1
"""
import argparse
import datetime
import html
import json
import re
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from xml.dom import minidom

ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS = ROOT / "translations" / "th"
BOOK_DIR = ROOT / "book"
CHAPTER_COUNT = 100

DEFAULT_METADATA = {
    "title": "ซีโหยวจี้",
    "original_title": "西遊記",
    "language": "th",
    "creators": [],
    "contributors": [],
    "license": None,
    "sources": [],
}

MARKER_LINE = re.compile(r"^\s*<!--\s*ย\d+\s*-->\s*$")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.+)$")
FOOTNOTE_REF = re.compile(r"\[\^([^\]\s]+)\]")
CHAPTER_HEAD = re.compile(r"^# บทที่ (\d+) (.+)$")
# เครื่องหมายที่ไม่ควรเหลือหลังแปลง (ตรวจในข้อความดิบหลังตัดเชิงอรรถ)
LEFTOVER = re.compile(r"<!--|-->|\*\*|__|`|\]\(|^#{1,6} |^\|", re.M)

CSS = """\
@charset "utf-8";
body { font-family: "Sarabun", "Noto Serif Thai", "Noto Sans Thai", "Tahoma", serif; line-height: 1.8; margin: 0 auto; max-width: 42em; padding: 0 1em; }
h1 { font-size: 1.4em; line-height: 1.5; margin: 2em 0 1.2em; text-align: center; }
h1 .num { display: block; font-size: 0.8em; font-weight: normal; margin-bottom: 0.3em; }
h2 { font-size: 1.15em; margin: 1.6em 0 0.6em; }
p { margin: 0 0 0.8em; text-indent: 0; }
blockquote { margin: 0.6em 0 1em 1.5em; }
blockquote p { margin: 0 0 0.6em; }
ul { margin: 0 0 1em 1.5em; padding: 0; }
a.noteref { font-size: 0.75em; vertical-align: super; line-height: 0; text-decoration: none; }
section.notes { border-top: 1px solid #999; margin-top: 2em; padding-top: 0.5em; font-size: 0.9em; }
section.notes p { margin: 0 0 0.4em; }
.title-page { text-align: center; margin-top: 30%; }
.title-page .title { font-size: 2.2em; font-weight: bold; margin: 0; }
.title-page .original { font-size: 1.4em; margin: 0.3em 0 1.5em; }
.colophon { font-size: 0.9em; margin-top: 3em; }
nav ol { list-style: none; padding-left: 0; }
nav li { margin: 0.3em 0; }
.chapter-sep { page-break-before: always; break-before: page; }
"""


class BuildError(Exception):
    pass


def esc(text):
    return html.escape(text, quote=False)


def esc_attr(text):
    return html.escape(text, quote=True)


class Doc:
    """เอกสารหนึ่งไฟล์ (บท หรือส่วนหน้า/ท้าย) ที่แปลงแล้ว"""

    def __init__(self, key, kind, title, number=None):
        self.key = key            # ใช้เป็นชื่อไฟล์และคำนำหน้า id: "c001", "front-01-preface"
        self.kind = kind          # chapter / front / back
        self.title = FOOTNOTE_REF.sub("", title).strip()   # สำหรับสารบัญ/ชื่อหน้า
        self.title_html = esc(self.title)                 # หัวเรื่องพร้อมเครื่องหมายเชิงอรรถ
        self.number = number
        self.body = []            # ส่วน XHTML ของเนื้อหา
        self.notes = []           # (เลขแสดง, id, ข้อความ XHTML, [ref ids])

    def heading_html(self):
        if self.kind == "chapter":
            return (f'<h1 id="{self.key}"><span class="num">บทที่ {self.number}</span>'
                    f'{self.title_html}</h1>')
        return f'<h1 id="{self.key}">{self.title_html}</h1>'

    def toc_label(self):
        if self.kind == "chapter":
            return f"บทที่ {self.number} {self.title}"
        return self.title

    def content_html(self, epub):
        parts = [self.heading_html(), *self.body]
        if self.notes:
            sect = ' epub:type="endnotes"' if epub else ""
            parts.append(f'<section class="notes"{sect} role="doc-endnotes">')
            for num, nid, text, refs in self.notes:
                back = "".join(
                    f' <a href="#{r}" role="doc-backlink">↩</a>' for r in refs)
                if epub:
                    parts.append(f'<aside id="{nid}" epub:type="footnote" role="doc-footnote">'
                                 f'<p>{num}. {text}{back}</p></aside>')
                else:
                    parts.append(f'<p id="{nid}" role="doc-footnote">{num}. {text}{back}</p>')
            parts.append("</section>")
        return "\n".join(parts)


def convert(path, kind, key, errors):
    """แปลง Markdown หนึ่งไฟล์เป็น Doc; ข้อผิดเก็บลง errors (ไม่หยุดทันที เพื่อแสดงครบ)"""
    name = path.relative_to(ROOT).as_posix()
    lines = path.read_text(encoding="utf-8").split("\n")

    def err(lineno, msg):
        errors.append(f"{name}:{lineno}: {msg}")

    # ตัดป้ายหน่วยเทียบและเก็บนิยามเชิงอรรถ
    body_lines = []          # (lineno, text)
    defs = {}                # id -> (lineno, text)
    for i, line in enumerate(lines, 1):
        line = line.rstrip("\r")
        if MARKER_LINE.match(line):
            continue
        m = FOOTNOTE_DEF.match(line)
        if m:
            if m.group(1) in defs:
                err(i, f"นิยามเชิงอรรถซ้ำ [^{m.group(1)}]")
            defs[m.group(1)] = (i, m.group(2))
            continue
        body_lines.append((i, line))

    # หัวเรื่อง
    while body_lines and not body_lines[0][1].strip():
        body_lines.pop(0)
    if not body_lines or not body_lines[0][1].startswith("# "):
        err(1, "บรรทัดแรกต้องเป็นหัวเรื่อง `# `")
        return None
    head_no, head = body_lines.pop(0)
    if kind == "chapter":
        m = CHAPTER_HEAD.match(head)
        if not m:
            err(head_no, "หัวบทไม่อยู่ในรูป `# บทที่ N ชื่อบท`")
            return None
        number = int(m.group(1))
        if f"{number:03d}" != path.stem:
            err(head_no, f"เลขหัวบท {number} ไม่ตรงชื่อไฟล์ {path.name}")
        doc = Doc(key, kind, m.group(2).strip(), number)
    else:
        doc = Doc(key, kind, head[2:].strip())
    raw_title = m.group(2).strip() if kind == "chapter" else head[2:].strip()

    # จัดกลุ่มบล็อกด้วยบรรทัดว่าง
    blocks, cur = [], []
    for lineno, line in body_lines:
        if line.strip():
            cur.append((lineno, line))
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)

    note_order = {}          # id -> (เลขแสดง, [ref ids])

    def inline(lineno, text):
        if LEFTOVER.search(text):
            err(lineno, f"มีรูปแบบที่ไม่รองรับหรือป้ายตกค้าง: {text[:40]}")
        if "<" in text or ">" in text:
            err(lineno, f"มีอักขระ < หรือ > ในเนื้อความ: {text[:40]}")
        out, pos = [], 0
        for m in FOOTNOTE_REF.finditer(text):
            out.append(esc(text[pos:m.start()]))
            fid = m.group(1)
            if fid not in defs:
                err(lineno, f"อ้างเชิงอรรถ [^{fid}] แต่ไม่มีนิยาม")
            num, refs = note_order.setdefault(fid, (len(note_order) + 1, []))
            rid = f"{doc.key}-ref-{fid}-{len(refs) + 1}"
            refs.append(rid)
            out.append(f'<a class="noteref" id="{rid}" href="#{doc.key}-fn-{fid}"'
                       f' role="doc-noteref"{{EPUB_NOTEREF}}>{num}</a>')
            pos = m.end()
        out.append(esc(text[pos:]))
        joined = "".join(out)
        if "[^" in joined or "^]" in joined:
            err(lineno, "เครื่องหมายเชิงอรรถตกค้าง")
        return joined

    doc.title_html = inline(head_no, raw_title)
    for block in blocks:
        first_no, first = block[0]
        kinds = set()
        for _, line in block:
            if line.startswith(">"):
                kinds.add("quote")
            elif line.startswith("- "):
                kinds.add("list")
            elif line.startswith("## ") and kind != "chapter":
                kinds.add("h2")
            else:
                kinds.add("para")
        if len(kinds) != 1:
            err(first_no, f"บล็อกปนหลายรูปแบบ {sorted(kinds)} ต้องคั่นด้วยบรรทัดว่าง")
            continue
        k = kinds.pop()
        if k == "quote":
            stanzas, cur = [], []
            for lineno, line in block:
                if line != ">" and not line.startswith("> "):
                    err(lineno, "บรรทัดกวีต้องขึ้นต้นด้วย `> ` หรือเป็น `>` ว่าง")
                    continue
                t = line[2:].strip()
                if t:
                    cur.append(inline(lineno, t))
                elif cur:
                    stanzas.append(cur)
                    cur = []
            if cur:
                stanzas.append(cur)
            doc.body.append("<blockquote>" + "".join(
                "<p>" + "<br/>".join(s) + "</p>" for s in stanzas) + "</blockquote>")
        elif k == "list":
            doc.body.append("<ul>" + "".join(
                f"<li>{inline(n, l[2:].strip())}</li>" for n, l in block) + "</ul>")
        elif k == "h2":
            if len(block) != 1:
                err(first_no, "หัวข้อ `## ` ต้องอยู่บรรทัดเดียวโดด")
            doc.body.append(f"<h2>{inline(first_no, first[3:].strip())}</h2>")
        else:
            if len(block) != 1:
                err(block[1][0], "ย่อหน้าร้อยแก้วต้องอยู่บรรทัดเดียว (พบหลายบรรทัดติดกัน)")
            if first.startswith("#"):
                err(first_no, "ไม่รองรับหัวข้อระดับนี้ในไฟล์นี้")
            doc.body.append(f"<p>{inline(first_no, ' '.join(l.strip() for _, l in block))}</p>")

    for fid, (lineno, _) in defs.items():
        if fid not in note_order:
            err(lineno, f"นิยามเชิงอรรถ [^{fid}] ไม่ถูกอ้าง")
    for fid, (num, refs) in sorted(note_order.items(), key=lambda kv: kv[1][0]):
        if fid in defs:
            lineno, text = defs[fid]
            doc.notes.append((num, f"{doc.key}-fn-{fid}", inline(lineno, text), refs))
    return doc


def load_metadata():
    meta = dict(DEFAULT_METADATA)
    path = BOOK_DIR / "metadata.json"
    if path.exists():
        meta.update(json.loads(path.read_text(encoding="utf-8")))
    return meta


def collect(errors):
    docs = []
    for sub, kind in (("front", "front"),):
        for p in sorted((BOOK_DIR / sub).glob("*.md")) if (BOOK_DIR / sub).is_dir() else []:
            docs.append(convert(p, kind, f"{kind}-{p.stem}", errors))
    found = sorted(TRANSLATIONS.glob("*.md"))
    expected = [f"{i:03d}.md" for i in range(1, CHAPTER_COUNT + 1)]
    if [p.name for p in found] != expected:
        missing = sorted(set(expected) - {p.name for p in found})
        extra = sorted({p.name for p in found} - set(expected))
        errors.append(f"translations/th: บทไม่ครบหรือมีไฟล์เกิน ขาด {missing} เกิน {extra}")
    for p in found:
        if p.name in expected:
            docs.append(convert(p, "chapter", f"c{p.stem}", errors))
    for p in sorted((BOOK_DIR / "back").glob("*.md")) if (BOOK_DIR / "back").is_dir() else []:
        docs.append(convert(p, "back", f"back-{p.stem}", errors))
    return [d for d in docs if d is not None]


def build_date():
    """วันที่ของ commit ล่าสุด (UTC) เพื่อให้สร้างซ้ำได้ผลเดิม; ไม่มี git ใช้เวลาปัจจุบัน"""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        ts = datetime.datetime.fromtimestamp(int(out), datetime.timezone.utc)
    except (OSError, ValueError, subprocess.CalledProcessError):
        ts = datetime.datetime.now(datetime.timezone.utc)
    return ts.replace(microsecond=0)


def title_page_html(meta, date):
    lines = ['<section class="title-page">',
             f'<p class="title">{esc(meta["title"])}</p>']
    if meta.get("original_title"):
        lines.append(f'<p class="original" lang="zh-Hant">{esc(meta["original_title"])}</p>')
    for c in meta.get("creators", []):
        lines.append(f'<p>{esc(c["label"])}</p>')
    for c in meta.get("contributors", []):
        lines.append(f'<p>{esc(c["label"])}</p>')
    lines.append("</section>")
    lines.append('<section class="colophon">')
    if meta.get("license"):
        lines.append(f'<p>{esc(meta["license"])}</p>')
    else:
        lines.append("<p>ฉบับร่าง ยังไม่กำหนดสัญญาอนุญาตของคำแปล ยังไม่เผยแพร่</p>")
    if meta.get("sources"):
        lines.append("<p>ต้นฉบับที่ใช้</p><ul>")
        lines.extend(f"<li>{esc(s)}</li>" for s in meta["sources"])
        lines.append("</ul>")
    lines.append(f"<p>สร้างเมื่อ {date.date().isoformat()}</p>")
    lines.append("</section>")
    return "\n".join(lines)


def xhtml_page(title, body, lang, epub):
    ns = ' xmlns:epub="http://www.idpf.org/2007/ops"' if epub else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml"{ns} lang="{lang}" xml:lang="{lang}">\n'
            f'<head><meta charset="utf-8"/><title>{esc(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            f"<body>\n{body}\n</body>\n</html>\n")


def fill_noteref(text, epub):
    return text.replace("{EPUB_NOTEREF}", ' epub:type="noteref"' if epub else "")


def check_xml(name, text, errors):
    try:
        minidom.parseString(text.encode("utf-8"))
    except Exception as e:   # ExpatError และอื่น ๆ
        errors.append(f"{name}: XHTML ไม่สมบูรณ์: {e}")


def build_html(meta, docs, date):
    lang = meta["language"]
    toc = ['<nav id="toc" role="doc-toc"><h1>สารบัญ</h1><ol>']
    toc += [f'<li><a href="#{d.key}">{esc(d.toc_label())}</a></li>' for d in docs]
    toc.append("</ol></nav>")
    body = [title_page_html(meta, date), *toc]
    for d in docs:
        body.append(f'<section class="chapter-sep" id="sec-{d.key}">'
                    f"{fill_noteref(d.content_html(epub=False), False)}</section>")
    return ("<!DOCTYPE html>\n"
            f'<html lang="{lang}">\n<head><meta charset="utf-8"/>'
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
            f"<title>{esc(meta['title'])}</title><style>\n{CSS}</style></head>\n"
            "<body>\n" + "\n".join(body) + "\n</body>\n</html>\n")


def build_epub(meta, docs, date, errors):
    lang = meta["language"]
    ident = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL,
                                         "xiyouji-th:" + meta["title"]))
    modified = date.strftime("%Y-%m-%dT%H:%M:%SZ")
    pages = [("title", "title.xhtml", meta["title"],
              xhtml_page(meta["title"], title_page_html(meta, date), lang, True))]
    for d in docs:
        fname = f"{d.key}.xhtml"
        pages.append((d.key, fname, d.toc_label(),
                      xhtml_page(d.toc_label(), fill_noteref(d.content_html(True), True),
                                 lang, True)))

    first_chapter = next((f"{d.key}.xhtml" for d in docs if d.kind == "chapter"), None)
    nav_items = "".join(f'<li><a href="{f}">{esc(label)}</a></li>'
                        for key, f, label, _ in pages if key != "title")
    nav = xhtml_page("สารบัญ",
                     '<nav epub:type="toc" id="toc" role="doc-toc"><h1>สารบัญ</h1>'
                     f"<ol>{nav_items}</ol></nav>\n"
                     '<nav epub:type="landmarks" hidden="hidden"><ol>'
                     '<li><a epub:type="titlepage" href="title.xhtml">หน้าชื่อเรื่อง</a></li>'
                     '<li><a epub:type="toc" href="nav.xhtml">สารบัญ</a></li>'
                     + (f'<li><a epub:type="bodymatter" href="{first_chapter}">เนื้อเรื่อง</a></li>'
                        if first_chapter else "")
                     + "</ol></nav>", lang, True)

    ncx_points = "".join(
        f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{esc(label)}</text></navLabel>'
        f'<content src="{f}"/></navPoint>'
        for i, (_, f, label, _) in enumerate(pages, 1))
    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{ident}"/></head>'
           f"<docTitle><text>{esc(meta['title'])}</text></docTitle>"
           f"<navMap>{ncx_points}</navMap></ncx>\n")

    dc = [f'<dc:identifier id="bookid">{ident}</dc:identifier>',
          f"<dc:title>{esc(meta['title'])}</dc:title>",
          f"<dc:language>{lang}</dc:language>",
          f'<meta property="dcterms:modified">{modified}</meta>']
    for i, c in enumerate(meta.get("creators", []), 1):
        dc.append(f'<dc:creator id="cre{i}">{esc(c["name"])}</dc:creator>')
        if c.get("role"):
            dc.append(f'<meta refines="#cre{i}" property="role" scheme="marc:relators">'
                      f'{esc_attr(c["role"])}</meta>')
    for i, c in enumerate(meta.get("contributors", []), 1):
        dc.append(f'<dc:contributor id="con{i}">{esc(c["name"])}</dc:contributor>')
        if c.get("role"):
            dc.append(f'<meta refines="#con{i}" property="role" scheme="marc:relators">'
                      f'{esc_attr(c["role"])}</meta>')
    if meta.get("license"):
        dc.append(f"<dc:rights>{esc(meta['license'])}</dc:rights>")
    for s in meta.get("sources", []):
        dc.append(f"<dc:source>{esc(s)}</dc:source>")

    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>']
    manifest += [f'<item id="{key}" href="{f}" media-type="application/xhtml+xml"/>'
                 for key, f, _, _ in pages]
    spine = ['<itemref idref="title"/>', '<itemref idref="nav"/>']
    spine += [f'<itemref idref="{key}"/>' for key, _, _, _ in pages if key != "title"]
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
           f'unique-identifier="bookid" xml:lang="{lang}">\n'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n' + "\n".join(dc) +
           "\n</metadata>\n<manifest>\n" + "\n".join(manifest) +
           '\n</manifest>\n<spine toc="ncx">\n' + "\n".join(spine) + "\n</spine>\n</package>\n")
    container = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/></rootfiles></container>\n')

    files = [("META-INF/container.xml", container), ("OEBPS/content.opf", opf),
             ("OEBPS/nav.xhtml", nav), ("OEBPS/toc.ncx", ncx), ("OEBPS/style.css", CSS)]
    files += [(f"OEBPS/{f}", text) for _, f, _, text in pages]
    for name, text in files:
        if not name.endswith(".css"):
            check_xml(name, text, errors)
    return files


def write_epub(path, files, date):
    stamp = date.timetuple()[:6]
    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo("mimetype", stamp)
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, "application/epub+zip")
        for name, text in files:
            info = zipfile.ZipInfo(name, stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text.encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--format", choices=["all", "html", "epub"], default="all")
    ap.add_argument("--out", default=str(ROOT / "build"))
    ap.add_argument("--check", action="store_true", help="แปลงและตรวจ ไม่เขียนไฟล์")
    args = ap.parse_args()

    errors = []
    meta = load_metadata()
    docs = collect(errors)
    date = build_date()
    page = build_html(meta, docs, date)
    files = build_epub(meta, docs, date, errors)

    chapters = [d for d in docs if d.kind == "chapter"]
    notes = sum(len(d.notes) for d in docs)
    print(f"บท {len(chapters)} | ส่วนหน้า {sum(d.kind == 'front' for d in docs)} "
          f"| ส่วนท้าย {sum(d.kind == 'back' for d in docs)} | เชิงอรรถ {notes}")
    if not meta.get("license"):
        print("คำเตือน: ยังไม่กำหนดสัญญาอนุญาต (book/metadata.json: license) หน้าลิขสิทธิ์ระบุว่าเป็นฉบับร่าง")
    if errors:
        print(f"ข้อผิด {len(errors)} รายการ ไม่เขียนไฟล์")
        for e in errors:
            print("  " + e)
        return 1
    if args.check:
        print("ตรวจผ่าน (--check ไม่เขียนไฟล์)")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.format in ("all", "html"):
        (out / "xiyouji.html").write_text(page, encoding="utf-8")
        print(f"เขียน {out / 'xiyouji.html'}")
    if args.format in ("all", "epub"):
        write_epub(out / "xiyouji.epub", files, date)
        print(f"เขียน {out / 'xiyouji.epub'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
